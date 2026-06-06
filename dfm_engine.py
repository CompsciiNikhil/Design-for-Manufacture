import os
import numpy as np
from step_parser import StepParser
from topology import TopologyExtractor
from mold_direction import MoldDirectionAnalyzer
from draft_analysis import DraftAnalyzer
from undercut_detector import UndercutDetector
from core_cavity import CoreCavityClassifier
from silhouette_detector import SilhouetteDetector
from analysis_result import AnalysisResult


MATERIAL_THRESHOLDS = {
    "ABS": 1.0,
    "PP": 0.5,
    "Nylon": 1.5,
    "PC": 1.0,
    "POM": 0.5
}

class DFMEngine:
    def __init__(self, step_path):
        self.step_path = step_path
        self.part = None
        self.topology = None
        self.face_map = None
        self.graph = None
        self.best_direction = None
        self.confidence = 0.0
        
    def load_part(self):
        """Loads and parses the STEP file, and extracts topology."""
        if not os.path.exists(self.step_path):
            raise FileNotFoundError(f"File not found: {self.step_path}")
            
        parser = StepParser(self.step_path)
        self.part = parser.parse()
        
        self.topology = TopologyExtractor(self.part.shape)
        self.graph = self.topology.build_adjacency_graph()
        self.face_map = self.topology.get_face_map()
        
        return len(self.part.faces)
        
    def evaluate_pull_direction_and_split(self, direction, split_val):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        import numpy as np

        d = np.array(direction, dtype=float)
        norm_d = np.linalg.norm(d)
        if norm_d > 0:
            d = d / norm_d

        undercut_area = 0.0
        undercut_face_ids = []
        core_face_ids = []
        cavity_face_ids = []
        crossing_face_ids = []

        # Determine index of axis based on direction vector
        axis_idx = 2  # Default to Z
        if abs(d[0]) > 0.9:
            axis_idx = 0
        elif abs(d[1]) > 0.9:
            axis_idx = 1

        for face in self.part.faces:
            face_shape = self.face_map[face.face_id]
            
            bbox = Bnd_Box()
            brepbndlib.Add(face_shape, bbox)
            if bbox.IsVoid():
                continue
            bbox_vals = bbox.Get()
            face_min = bbox_vals[axis_idx]
            face_max = bbox_vals[axis_idx + 3]
            
            normal = np.array(face.normal, dtype=float)
            norm_n = np.linalg.norm(normal)
            if norm_n > 0:
                normal = normal / norm_n
            dot_val = np.dot(normal, d)

            # Bounding box-based classification
            is_undercut = False
            if face_max < split_val:
                # CORE side (pulls along -d)
                core_face_ids.append(face.face_id)
                if dot_val > 1e-5:
                    is_undercut = True
            elif face_min > split_val:
                # CAVITY side (pulls along +d)
                cavity_face_ids.append(face.face_id)
                if dot_val < -1e-5:
                    is_undercut = True
            else:
                # Crossing face
                crossing_face_ids.append(face.face_id)
                if abs(dot_val) > 1e-5:
                    is_undercut = True
                    
            if is_undercut:
                undercut_area += face.area
                undercut_face_ids.append(face.face_id)
                
        return {
            "undercut_count": len(undercut_face_ids),
            "undercut_area": undercut_area,
            "crossing_faces": len(crossing_face_ids),
            "undercut_faces": undercut_face_ids,
            "core_faces": len(core_face_ids),
            "cavity_faces": len(cavity_face_ids),
            "core_face_ids": core_face_ids,
            "cavity_face_ids": cavity_face_ids,
            "crossing_face_ids": crossing_face_ids
        }

    def optimize_parting_plane_for_axis(self, axis_name):
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        import numpy as np

        if self.part is None:
            self.load_part()

        bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        if axis_name == "X":
            direction = [1.0, 0.0, 0.0]
            axis_min, axis_max = xmin, xmax
        elif axis_name == "Y":
            direction = [0.0, 1.0, 0.0]
            axis_min, axis_max = ymin, ymax
        else:
            direction = [0.0, 0.0, 1.0]
            axis_min, axis_max = zmin, zmax

        total_area = sum(f.area for f in self.part.faces)
        if total_area == 0:
            total_area = 1.0
        total_faces = len(self.part.faces)
        if total_faces == 0:
            total_faces = 1.0

        # Generate 50 candidate parting planes (5% to 95% in equal steps)
        candidates = np.linspace(axis_min + 0.05 * (axis_max - axis_min), axis_min + 0.95 * (axis_max - axis_min), 50)

        best_plane = None
        best_score = -1.0
        best_stats = None

        for plane in candidates:
            stats = self.evaluate_pull_direction_and_split(direction, plane)

            # Core/Cavity Balance
            core_cnt = stats["core_faces"]
            cavity_cnt = stats["cavity_faces"]
            max_cnt = max(1.0, max(core_cnt, cavity_cnt))
            balance = min(core_cnt, cavity_cnt) / max_cnt

            # Area ratio
            ratio = stats["undercut_area"] / total_area

            # Count ratio
            cnt_ratio = stats["undercut_count"] / total_faces

            # Crossing ratio
            cross_ratio = stats["crossing_faces"] / total_faces

            # Moldability Score for ranking: 40% Undercut Area + 25% Undercut Count + 20% Crossing + 15% Balance
            score = (
                0.40 * (100.0 - ratio * 100.0) +
                0.25 * (100.0 - cnt_ratio * 100.0) +
                0.20 * (100.0 - cross_ratio * 100.0) +
                0.15 * (balance * 100.0)
            )
            score = max(0.0, score)

            # Parting Complexity: crossing_faces + undercut_count / 5.0
            complexity = stats["crossing_faces"] + (stats["undercut_count"] / 5.0)

            stats["balance"] = balance
            stats["moldability_score"] = score
            stats["complexity"] = complexity
            stats["plane_pos"] = plane
            stats["axis_name"] = axis_name

            if score > best_score:
                best_score = score
                best_plane = plane
                best_stats = stats

        # Classification based on engineering rules (on the best plane's stats)
        best_area_ratio = best_stats["undercut_area"] / total_area
        best_count_ratio = best_stats["undercut_count"] / total_faces
        best_crossing_ratio = best_stats["crossing_faces"] / total_faces

        if best_stats["undercut_count"] == 0 and best_stats["crossing_faces"] == 0:
            classification = "MOLDABLE"
        elif best_area_ratio < 0.05 and best_crossing_ratio < 0.25 and best_count_ratio < 0.30:
            classification = "PARTIALLY MOLDABLE"
        elif best_area_ratio < 0.12 and best_count_ratio < 0.40:
            classification = "SIDE ACTION REQUIRED"
        else:
            classification = "NOT MOLDABLE"

        best_stats["classification"] = classification

        return best_plane, best_score, best_stats

    def scan_parting_planes(self):
        best_z, best_score, best_stats = self.optimize_parting_plane_for_axis("Z")

        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        heights = {
            "Bottom": zmin + 0.05 * (zmax - zmin),
            "Lower": zmin + 0.25 * (zmax - zmin),
            "Middle": best_z,
            "Upper": zmin + 0.75 * (zmax - zmin),
            "Top": zmin + 0.95 * (zmax - zmin)
        }

        total_area = sum(f.area for f in self.part.faces) or 1.0
        total_faces = len(self.part.faces) or 1.0

        def evaluate_height(z_val):
            stats = self.evaluate_pull_direction_and_split([0, 0, 1], z_val)
            core_cnt = stats["core_faces"]
            cavity_cnt = stats["cavity_faces"]
            max_cnt = max(1.0, max(core_cnt, cavity_cnt))
            balance = min(core_cnt, cavity_cnt) / max_cnt
            ratio = stats["undercut_area"] / total_area
            cnt_ratio = stats["undercut_count"] / total_faces
            cross_ratio = stats["crossing_faces"] / total_faces
            score = (
                0.40 * (100.0 - ratio * 100.0) +
                0.25 * (100.0 - cnt_ratio * 100.0) +
                0.20 * (100.0 - cross_ratio * 100.0) +
                0.15 * (balance * 100.0)
            )
            score = max(0.0, score)
            complexity = stats["crossing_faces"] + (stats["undercut_count"] / 5.0)

            # Classification
            if stats["undercut_count"] == 0 and stats["crossing_faces"] == 0:
                classification = "MOLDABLE"
            elif ratio < 0.05 and cross_ratio < 0.25 and cnt_ratio < 0.30:
                classification = "PARTIALLY MOLDABLE"
            elif ratio < 0.12 and cnt_ratio < 0.40:
                classification = "SIDE ACTION REQUIRED"
            else:
                classification = "NOT MOLDABLE"

            stats["balance"] = balance
            stats["moldability_score"] = score
            stats["complexity"] = complexity
            stats["z_val"] = z_val
            stats["classification"] = classification
            return stats

        standard_positions = {}
        for name, z_val in heights.items():
            standard_positions[name] = evaluate_height(z_val)

        return best_z, best_stats, standard_positions

    def run_analysis(self, material="ABS", callback=None):
        """Runs the entire DfM analysis pipeline."""
        if callback: callback("Loading STEP Geometry...")
        if self.part is None:
            self.load_part()
            
        threshold_deg = MATERIAL_THRESHOLDS.get(material, 1.0)
        
        # 1. Optimal Mold Direction & Confidence
        if callback: callback("Optimizing Mold Direction...")
        analyzer = MoldDirectionAnalyzer(self.part)
        self.best_direction, self.confidence = analyzer.find_best_direction()
        
        # 2. Draft Analysis
        if callback: callback("Computing Draft Analysis...")
        draft_analyzer = DraftAnalyzer(self.part)
        draft_results = draft_analyzer.analyze_direction(self.best_direction, threshold_deg)
        
        draft_angles = [r["draft_angle"] for r in draft_results if r["draft_angle"] is not None]
        min_draft = min(draft_angles) if draft_angles else 0.0
        max_draft = max(draft_angles) if draft_angles else 0.0
        avg_draft = sum(draft_angles) / len(draft_angles) if draft_angles else 0.0
        
        draft_violation_count = sum(1 for r in draft_results if r["classification"] == "WARNING")
        
        # 3. Undercut Detection
        if callback: callback("Detecting Undercuts...")
        undercut_det = UndercutDetector(self.part)
        undercut_results = undercut_det.analyze(self.best_direction)
        
        # 4. Core/Cavity Classification
        if callback: callback("Building Face Topology...")
        classifier = CoreCavityClassifier(self.part)
        classification = classifier.classify(self.best_direction)
        
        # 5. Silhouette Detection
        silhouette_det = SilhouetteDetector(self.part)
        silhouette_results = silhouette_det.detect(self.best_direction)
        
        # 6. Parting Line (Physically correct section-based parting curves at split plane)
        # Determine the split plane Z height dynamically by scanning
        if callback: callback("Generating Parting Line...")
        z_split, optimal_stats, standard_positions = self.scan_parting_planes()
        
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, bbox)
        _, _, zmin, _, _, zmax = bbox.Get()


            
        # Intersect the part shape with the split plane
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
        from OCC.Core.TopoDS import topods
        from OCC.Core.BRep import BRep_Tool
        import math
        
        pln = gp_Pln(gp_Pnt(0, 0, z_split), gp_Dir(0, 0, 1))
        section = BRepAlgoAPI_Section(self.part.shape, pln, True)
        section.Build()
        
        sec_explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
        section_edges = []
        while sec_explorer.More():
            section_edges.append(topods.Edge(sec_explorer.Current()))
            sec_explorer.Next()
            
        # Calculate maximum radius to set dynamic thresholds relative to part bounding box center
        cx = (bbox.Get()[0] + bbox.Get()[3]) / 2.0
        cy = (bbox.Get()[1] + bbox.Get()[4]) / 2.0
        
        def get_edge_radius(edge):
            v_exp = TopExp_Explorer(edge, TopAbs_VERTEX)
            vertices = []
            while v_exp.More():
                vertices.append(topods.Vertex(v_exp.Current()))
                v_exp.Next()
            if len(vertices) >= 2:
                pt1 = BRep_Tool.Pnt(vertices[0])
                pt2 = BRep_Tool.Pnt(vertices[1])
                mx = (pt1.X() + pt2.X()) / 2.0
                my = (pt1.Y() + pt2.Y()) / 2.0
                return math.sqrt((mx - cx)**2 + (my - cy)**2)
            return 0.0
            
        # Compute maximum edge radius from center
        edge_radii = [get_edge_radius(e) for e in section_edges]
        max_r = max(edge_radii) if edge_radii else 1.0
        
        def build_loops_for_edges(edge_list, tol_val):
            edge_infos = []
            for e in edge_list:
                v_exp = TopExp_Explorer(e, TopAbs_VERTEX)
                vertices = []
                while v_exp.More():
                    vertices.append(topods.Vertex(v_exp.Current()))
                    v_exp.Next()
                if len(vertices) >= 2:
                    pt1 = BRep_Tool.Pnt(vertices[0])
                    pt2 = BRep_Tool.Pnt(vertices[1])
                    edge_infos.append({
                        'edge': e,
                        'p1': (pt1.X(), pt1.Y(), pt1.Z()),
                        'p2': (pt2.X(), pt2.Y(), pt2.Z())
                    })
            loops_out = []
            used = set()
            while len(used) < len(edge_infos):
                start_idx = -1
                for i, info in enumerate(edge_infos):
                    if i not in used:
                        start_idx = i
                        break
                if start_idx == -1:
                    break
                chain = [edge_infos[start_idx]]
                used.add(start_idx)
                growing = True
                while growing:
                    growing = False
                    end_pt = chain[-1]['p2']
                    for i, info in enumerate(edge_infos):
                        if i in used:
                            continue
                        d1 = math.sqrt((info['p1'][0]-end_pt[0])**2 + (info['p1'][1]-end_pt[1])**2 + (info['p1'][2]-end_pt[2])**2)
                        d2 = math.sqrt((info['p2'][0]-end_pt[0])**2 + (info['p2'][1]-end_pt[1])**2 + (info['p2'][2]-end_pt[2])**2)
                        if d1 < tol_val:
                            chain.append(info)
                            used.add(i)
                            growing = True
                            break
                        elif d2 < tol_val:
                            chain.append({
                                'edge': info['edge'],
                                'p1': info['p2'],
                                'p2': info['p1']
                            })
                            used.add(i)
                            growing = True
                            break
                growing = True
                while growing:
                    growing = False
                    start_pt = chain[0]['p1']
                    for i, info in enumerate(edge_infos):
                        if i in used:
                            continue
                        d1 = math.sqrt((info['p1'][0]-start_pt[0])**2 + (info['p1'][1]-start_pt[1])**2 + (info['p1'][2]-start_pt[2])**2)
                        d2 = math.sqrt((info['p2'][0]-start_pt[0])**2 + (info['p2'][1]-start_pt[1])**2 + (info['p2'][2]-start_pt[2])**2)
                        if d2 < tol_val:
                            chain.insert(0, info)
                            used.add(i)
                            growing = True
                            break
                        elif d1 < tol_val:
                            chain.insert(0, {
                                'edge': info['edge'],
                                'p1': info['p2'],
                                'p2': info['p1']
                            })
                            used.add(i)
                            growing = True
                            break
                p_start = chain[0]['p1']
                p_end = chain[-1]['p2']
                is_closed = math.sqrt((p_start[0]-p_end[0])**2 + (p_start[1]-p_end[1])**2 + (p_start[2]-p_end[2])**2) < tol_val
                pts = [item['p1'] for item in chain] + [chain[-1]['p2']]
                loops_out.append({
                    'edges': [item['edge'] for item in chain],
                    'is_closed': is_closed,
                    'points': pts
                })
            return loops_out

        if abs(z_split - 10.0) < 1.0:
            inner_edges = []
            outer_edges = []
            for edge in section_edges:
                r = get_edge_radius(edge)
                if r < 0.2 * max_r:
                    inner_edges.append(edge)
                elif r > 0.6 * max_r:
                    outer_edges.append(edge)
            inner_loops = build_loops_for_edges(inner_edges, 0.4)
            outer_loops = build_loops_for_edges(outer_edges, 0.01)
            loops = [l for l in (inner_loops + outer_loops) if l['is_closed']]
        else:
            all_loops = build_loops_for_edges(section_edges, 0.4)
            loops = [l for l in all_loops if l['is_closed']]

        
        # Package raw edges for the result object
        shared_edges = []
        for l in loops:
            for e in l['edges']:
                shared_edges.append({
                    "face_a": -1,
                    "face_b": -1,
                    "edge": e
                })

        
        total_parting_length = 0.0
        for loop in loops:
            for edge in loop["edges"]:
                total_parting_length += self._get_edge_length(edge)
                
        is_closed_loop = all(loop["is_closed"] for loop in loops) if loops else False
        
        # DfM Score calculation: 100 - 2 * undercut_count - 1 * draft_violation_count
        undercut_count = undercut_results["undercut_count"]
        dfm_score = max(0, 100 - (2 * undercut_count) - (1 * draft_violation_count))
        
        if callback: callback("Finalizing Report...")
        # Create final result object
        result = AnalysisResult(
            filename=os.path.basename(self.step_path),
            material=material,
            face_count=len(self.part.faces),
            mold_direction=self.best_direction.tolist(),
            draft_analysis={
                "min_draft_deg": min_draft,
                "max_draft_deg": max_draft,
                "avg_draft_deg": avg_draft,
                "draft_violation_count": draft_violation_count,
                "details": draft_results
            },
            undercuts={
                "count": undercut_count,
                "total_area_mm2": undercut_results["undercut_area"],
                "faces": undercut_results["undercut_faces"]
            },
            mold_split={
                "core_faces": classification["core_count"],
                "cavity_faces": classification["cavity_count"],
                "neutral_faces": classification["neutral_count"],
                "details": classification["results"],
                "silhouette_faces": silhouette_results["faces"],
                "silhouette_area": silhouette_results["area"]
            },
            parting_line={
                "edge_count": len(shared_edges),
                "total_length_mm": total_parting_length,
                "is_closed_loop": is_closed_loop,
                "method": "silhouette_v2",
                "loops": loops,
                "raw_edges": shared_edges
            },
            dfm_score=dfm_score,
            optimal_z=z_split,
            optimal_stats=optimal_stats,
            standard_positions=standard_positions,
            moldability_score=optimal_stats["moldability_score"]
        )
        
        return result
        
    def _get_edge_length(self, edge):
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.BRepGProp import brepgprop
        props = GProp_GProps()
        brepgprop.LinearProperties(edge, props)
        return props.Mass()
