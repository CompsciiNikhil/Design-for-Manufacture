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
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Cylinder
        import numpy as np

        d = np.array(direction, dtype=float)
        norm_d = np.linalg.norm(d)
        if norm_d > 0:
            d = d / norm_d

        undercut_area = 0.0
        side_action_area = 0.0
        undercut_face_ids = []
        side_action_face_ids = []
        core_face_ids = []
        cavity_face_ids = []
        crossing_face_ids = []

        # Determine index of axis based on direction vector
        axis_idx = 2  # Default to Z
        if abs(d[0]) > 0.9:
            axis_idx = 0
        elif abs(d[1]) > 0.9:
            axis_idx = 1

        # Pre-compute part bounding box for lateral protrusion size check
        part_bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, part_bbox)
        if not part_bbox.IsVoid():
            pbv = part_bbox.Get()
            part_mins = [pbv[0], pbv[1], pbv[2]]
            part_maxs = [pbv[3], pbv[4], pbv[5]]
        else:
            part_mins = [-1e9, -1e9, -1e9]
            part_maxs = [1e9, 1e9, 1e9]

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
            is_side_action = False
            
            try:
                adaptor = BRepAdaptor_Surface(face_shape)
                if adaptor.GetType() == GeomAbs_Cylinder:
                    cyl = adaptor.Cylinder()
                    axis_vec = cyl.Axis().Direction()
                    axis_dir = np.array([axis_vec.X(), axis_vec.Y(), axis_vec.Z()])
                    cyl_r = cyl.Radius()
                    # Lateral cylinder: axis perpendicular to pull direction
                    if abs(np.dot(axis_dir, d)) < 0.2:
                        # Only flag as side action if the cylinder spans a significant
                        # portion of the part in its axial direction (>=15% of part span).
                        # This distinguishes large protruding port-tubes from small bolt holes.
                        for pi in range(3):
                            if pi == axis_idx:
                                continue
                            pi_axis = np.zeros(3)
                            pi_axis[pi] = 1.0
                            # Is this perpendicular axis roughly aligned with the cylinder's axis?
                            if abs(np.dot(axis_dir, pi_axis)) > 0.8:
                                face_span = bbox_vals[pi + 3] - bbox_vals[pi]
                                part_span = part_maxs[pi] - part_mins[pi]
                                if part_span > 0 and face_span / part_span >= 0.15:
                                    is_side_action = True
                                    break
            except Exception:
                pass

            if face_max < split_val:
                core_face_ids.append(face.face_id)
                if dot_val > 1e-5:
                    is_undercut = True
            elif face_min > split_val:
                cavity_face_ids.append(face.face_id)
                if dot_val < -1e-5:
                    is_undercut = True
            else:
                crossing_face_ids.append(face.face_id)
                if abs(dot_val) > 1e-5:
                    is_undercut = True
                    
            if is_side_action:
                side_action_face_ids.append(face.face_id)
                side_action_area += face.area
                
            if is_undercut and not is_side_action:
                undercut_area += face.area
                undercut_face_ids.append(face.face_id)
                
        return {
            "undercut_count": len(undercut_face_ids),
            "undercut_area": undercut_area,
            "side_action_count": len(side_action_face_ids),
            "side_action_area": side_action_area,
            "crossing_faces": len(crossing_face_ids),
            "undercut_faces": undercut_face_ids,
            "core_faces": len(core_face_ids),
            "cavity_faces": len(cavity_face_ids),
            "core_face_ids": core_face_ids,
            "cavity_face_ids": cavity_face_ids,
            "crossing_face_ids": crossing_face_ids,
            "side_action_faces": side_action_face_ids
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
            
            # Side action ratio
            side_ratio = stats["side_action_count"] / total_faces

            # Moldability Score: 35% Undercut, 20% Count, 15% Crossing, 15% Side-Action, 15% Balance
            score = (
                0.35 * (100.0 - ratio * 100.0) +
                0.20 * (100.0 - cnt_ratio * 100.0) +
                0.15 * (100.0 - cross_ratio * 100.0) +
                0.15 * (100.0 - side_ratio * 100.0) +
                0.15 * (balance * 100.0)
            )
            score = max(0.0, score)

            # Parting Complexity
            complexity = stats["crossing_faces"] + (stats["undercut_count"] / 5.0) + (stats["side_action_count"] / 2.0)

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
        best_side_count = best_stats["side_action_count"]

        if best_stats["undercut_count"] == 0 and best_stats["crossing_faces"] == 0 and best_side_count == 0:
            classification = "MOLDABLE"
        elif best_side_count > 0 and best_area_ratio < 0.20:
            # Has lateral cylinder protrusions requiring side actions/sliders
            classification = "SIDE ACTION REQUIRED"
        elif best_area_ratio < 0.05 and best_crossing_ratio < 0.25 and best_count_ratio < 0.30:
            classification = "PARTIALLY MOLDABLE"
        elif best_area_ratio < 0.15 and best_count_ratio < 0.50:
            classification = "SIDE ACTION REQUIRED"
        else:
            classification = "NOT MOLDABLE"

        best_stats["classification"] = classification

        return best_plane, best_score, best_stats

    def scan_parting_planes(self):
        # Determine the best axis from self.best_direction
        d = np.array(self.best_direction, dtype=float)
        axis_name = "Z"
        axis_idx = 2
        dir_vector = [0.0, 0.0, 1.0]
        if abs(d[0]) > 0.9:
            axis_name = "X"
            axis_idx = 0
            dir_vector = [1.0, 0.0, 0.0]
        elif abs(d[1]) > 0.9:
            axis_name = "Y"
            axis_idx = 1
            dir_vector = [0.0, 1.0, 0.0]
            
        best_z, best_score, best_stats = self.optimize_parting_plane_for_axis(axis_name)

        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, bbox)
        bbox_vals = bbox.Get()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox_vals

        axis_min = bbox_vals[axis_idx]
        axis_max = bbox_vals[axis_idx + 3]

        heights = {
            "Bottom": axis_min + 0.05 * (axis_max - axis_min),
            "Lower": axis_min + 0.25 * (axis_max - axis_min),
            "Middle": best_z,
            "Upper": axis_min + 0.75 * (axis_max - axis_min),
            "Top": axis_min + 0.95 * (axis_max - axis_min)
        }

        total_area = sum(f.area for f in self.part.faces) or 1.0
        total_faces = len(self.part.faces) or 1.0

        def evaluate_height(z_val):
            stats = self.evaluate_pull_direction_and_split(dir_vector, z_val)
            core_cnt = stats["core_faces"]
            cavity_cnt = stats["cavity_faces"]
            max_cnt = max(1.0, max(core_cnt, cavity_cnt))
            balance = min(core_cnt, cavity_cnt) / max_cnt
            ratio = stats["undercut_area"] / total_area
            cnt_ratio = stats["undercut_count"] / total_faces
            cross_ratio = stats["crossing_faces"] / total_faces
            side_ratio = stats.get("side_action_count", 0) / total_faces
            score = (
                0.35 * (100.0 - ratio * 100.0) +
                0.20 * (100.0 - cnt_ratio * 100.0) +
                0.15 * (100.0 - cross_ratio * 100.0) +
                0.15 * (100.0 - side_ratio * 100.0) +
                0.15 * (balance * 100.0)
            )
            score = max(0.0, score)
            side_cnt = stats.get("side_action_count", 0)
            complexity = stats["crossing_faces"] + (stats["undercut_count"] / 5.0) + (side_cnt / 2.0)

            # Classification — side-action lateral cylinders take priority
            if stats["undercut_count"] == 0 and stats["crossing_faces"] == 0 and side_cnt == 0:
                classification = "MOLDABLE"
            elif side_cnt > 0 and ratio < 0.20:
                # Has lateral cylinder protrusions requiring side actions/sliders
                classification = "SIDE ACTION REQUIRED"
            elif ratio < 0.05 and cross_ratio < 0.25 and cnt_ratio < 0.30:
                classification = "PARTIALLY MOLDABLE"
            elif ratio < 0.15 and cnt_ratio < 0.50:
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
        
        # Optimize parting plane for X, Y, and Z axes to find the most moldable direction
        x_split, x_score, x_stats = self.optimize_parting_plane_for_axis("X")
        y_split, y_score, y_stats = self.optimize_parting_plane_for_axis("Y")
        z_split, z_score, z_stats = self.optimize_parting_plane_for_axis("Z")
        
        scores = {"X": x_score, "Y": y_score, "Z": z_score}
        best_axis = max(scores, key=scores.get)
        
        if best_axis == "X":
            self.best_direction = np.array([1.0, 0.0, 0.0])
        elif best_axis == "Y":
            self.best_direction = np.array([0.0, 1.0, 0.0])
        else:
            self.best_direction = np.array([0.0, 0.0, 1.0])
            
        self.confidence = scores[best_axis] / 100.0
        print(f"Optimal axis selected via parting plane scores: {best_axis} (Score: {scores[best_axis]:.2f})")
        
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
        
        # [LEGACY] Plane-intersection parting line detection — kept as fallback
        # Replaced by silhouette-edge detection below
        # from OCC.Core.Bnd import Bnd_Box
        # from OCC.Core.BRepBndLib import brepbndlib
        # bbox = Bnd_Box()
        # brepbndlib.Add(self.part.shape, bbox)
        # bbox_vals = bbox.Get()
        # xmin, ymin, zmin, xmax, ymax, zmax = bbox_vals
        # 
        # from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        # 
        # # Determine the best axis from self.best_direction
        # d = np.array(self.best_direction, dtype=float)
        # axis_name = "Z"
        # dir_vector = gp_Dir(0, 0, 1)
        # pnt_origin = gp_Pnt(0, 0, z_split)
        # if abs(d[0]) > 0.9:
        #     axis_name = "X"
        #     dir_vector = gp_Dir(1, 0, 0)
        #     pnt_origin = gp_Pnt(z_split, 0, 0)
        # elif abs(d[1]) > 0.9:
        #     axis_name = "Y"
        #     dir_vector = gp_Dir(0, 1, 0)
        #     pnt_origin = gp_Pnt(0, z_split, 0)
        #     
        # # Intersect the part shape with the split plane
        # from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        # from OCC.Core.TopExp import TopExp_Explorer
        # from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
        # from OCC.Core.TopoDS import topods
        # from OCC.Core.BRep import BRep_Tool
        # import math
        # 
        # pln = gp_Pln(pnt_origin, dir_vector)
        # section = BRepAlgoAPI_Section(self.part.shape, pln, True)
        # section.Build()
        # 
        # sec_explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
        # section_edges = []
        # while sec_explorer.More():
        #     section_edges.append(topods.Edge(sec_explorer.Current()))
        #     sec_explorer.Next()
        #     
        # # Calculate maximum radius to set dynamic thresholds relative to part bounding box center
        # cx = (bbox_vals[0] + bbox_vals[3]) / 2.0
        # cy = (bbox_vals[1] + bbox_vals[4]) / 2.0
        # cz = (bbox_vals[2] + bbox_vals[5]) / 2.0
        # 
        # def get_edge_radius(edge):
        #     try:
        #         from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        #         adaptor = BRepAdaptor_Curve(edge)
        #         t_mid = (adaptor.FirstParameter() + adaptor.LastParameter()) / 2.0
        #         pt = adaptor.Value(t_mid)
        #         mx, my, mz = pt.X(), pt.Y(), pt.Z()
        #         if axis_name == "X":
        #             return math.sqrt((my - cy)**2 + (mz - cz)**2)
        #         elif axis_name == "Y":
        #             return math.sqrt((mx - cx)**2 + (mz - cz)**2)
        #         else:
        #             return math.sqrt((mx - cx)**2 + (my - cy)**2)
        #     except Exception:
        #         return 0.0
        #     
        # # Compute maximum edge radius from center
        # edge_radii = [get_edge_radius(e) for e in section_edges]
        # max_r = max(edge_radii) if edge_radii else 1.0

        # [NEW] Hybrid Parting Line Detection
        # Z-axis: Uses Silhouette-Edge detection for 3D non-planar parting boundaries
        # X/Y-axes: Uses Plane-Intersection (Section Cut) for planar parting curves on smooth/revolved surfaces
        import math
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_VERTEX
        from OCC.Core.TopoDS import topods
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepTools import breptools
        from OCC.Core.GeomLProp import GeomLProp_SLProps
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_ListIteratorOfListOfShape
        from OCC.Core.TopExp import topexp

        # Bounding box & dimensions
        bbox = Bnd_Box()
        brepbndlib.Add(self.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        _dims = [xmax - xmin, ymax - ymin, zmax - zmin]
        _min_dim = min(d for d in _dims if d > 0)

        # Common loop builder helper
        def build_loops_for_edges(edge_list, tol_val):
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            edge_infos = []
            for e in edge_list:
                try:
                    adaptor = BRepAdaptor_Curve(e)
                    t1 = adaptor.FirstParameter()
                    t2 = adaptor.LastParameter()
                    p1 = adaptor.Value(t1)
                    p2 = adaptor.Value(t2)
                    edge_infos.append({
                        'edge': e,
                        'p1': (p1.X(), p1.Y(), p1.Z()),
                        'p2': (p2.X(), p2.Y(), p2.Z())
                    })
                except Exception:
                    pass
            loops_out = []
            used = set()
            while len(used) < len(edge_infos):
                start_idx = next((i for i in range(len(edge_infos)) if i not in used), -1)
                if start_idx == -1:
                    break
                chain = [dict(edge_infos[start_idx])]
                used.add(start_idx)
                # Grow forward from chain tail
                growing = True
                while growing:
                    growing = False
                    ep = chain[-1]['p2']
                    for i, info in enumerate(edge_infos):
                        if i in used:
                            continue
                        d1 = math.dist(info['p1'], ep)
                        d2 = math.dist(info['p2'], ep)
                        if d1 < tol_val:
                            chain.append(dict(info))
                            used.add(i); growing = True; break
                        elif d2 < tol_val:
                            chain.append({'edge': info['edge'], 'p1': info['p2'], 'p2': info['p1']})
                            used.add(i); growing = True; break
                # Grow backward from chain head
                growing = True
                while growing:
                    growing = False
                    sp = chain[0]['p1']
                    for i, info in enumerate(edge_infos):
                        if i in used:
                            continue
                        d1 = math.dist(info['p1'], sp)
                        d2 = math.dist(info['p2'], sp)
                        if d2 < tol_val:
                            chain.insert(0, dict(info))
                            used.add(i); growing = True; break
                        elif d1 < tol_val:
                            chain.insert(0, {'edge': info['edge'], 'p1': info['p2'], 'p2': info['p1']})
                            used.add(i); growing = True; break
                p_start = chain[0]['p1']
                p_end = chain[-1]['p2']
                is_closed = math.dist(p_start, p_end) < tol_val
                pts = [item['p1'] for item in chain] + [chain[-1]['p2']]
                loops_out.append({
                    'edges': [item['edge'] for item in chain],
                    'is_closed': is_closed,
                    'points': pts
                })
            return loops_out

        if best_axis == "Z":
            # --- Z-Axis: Silhouette-Edge Method ---
            pull_dir = self.best_direction
            pull_gp = gp_Dir(float(pull_dir[0]), float(pull_dir[1]), float(pull_dir[2]))

            face_normal_cache = {}

            def get_face_normal(face):
                h = face.HashCode(20000000)
                if h in face_normal_cache:
                    for f, n in face_normal_cache[h]:
                        if f.IsSame(face):
                            return n
                
                normal_dir = None
                try:
                    surface = BRep_Tool.Surface(face)
                    u_min, u_max, v_min, v_max = breptools.UVBounds(face)
                    u_mid = (u_min + u_max) / 2.0
                    v_mid = (v_min + v_max) / 2.0
                    
                    props = GeomLProp_SLProps(surface, u_mid, v_mid, 1, 1e-6)
                    if props.IsNormalDefined():
                        n = props.Normal()
                        nx, ny, nz = n.X(), n.Y(), n.Z()
                        norm_val = math.sqrt(nx*nx + ny*ny + nz*nz)
                        if norm_val > 1e-6:
                            if face.Orientation() == TopAbs_REVERSED:
                                nx, ny, nz = -nx, -ny, -nz
                            normal_dir = gp_Dir(nx, ny, nz)
                except Exception:
                    normal_dir = None
                    
                if h not in face_normal_cache:
                    face_normal_cache[h] = []
                face_normal_cache[h].append((face, normal_dir))
                return normal_dir

            def classify_face(face, pull_gp):
                normal = get_face_normal(face)
                if normal is None:
                    return "CAVITY"
                dot = normal.Dot(pull_gp)
                if dot >= 0.0:
                    return "CAVITY"
                else:
                    return "CORE"

            edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
            topexp.MapShapesAndAncestors(self.part.shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

            face_explorer = TopExp_Explorer(self.part.shape, TopAbs_FACE)
            face_class_map = {}
            while face_explorer.More():
                f = topods.Face(face_explorer.Current())
                cls = classify_face(f, pull_gp)
                h = f.HashCode(20000000)
                if h not in face_class_map:
                    face_class_map[h] = []
                face_class_map[h].append((f, cls))
                face_explorer.Next()

            parting_edges = []
            for i in range(1, edge_face_map.Size() + 1):
                edge = topods.Edge(edge_face_map.FindKey(i))
                faces_list = edge_face_map.FindFromIndex(i)
                
                adjacent_faces = []
                it = TopTools_ListIteratorOfListOfShape(faces_list)
                while it.More():
                    adjacent_faces.append(topods.Face(it.Value()))
                    it.Next()
                    
                classifications = []
                for f in adjacent_faces:
                    h = f.HashCode(20000000)
                    cls = "SIDE"
                    if h in face_class_map:
                        for cached_f, cached_cls in face_class_map[h]:
                            if cached_f.IsSame(f):
                                cls = cached_cls
                                break
                    classifications.append(cls)
                
                if "CAVITY" in classifications and "CORE" in classifications:
                    parting_edges.append(edge)

            axis_idx = 2
            active_split = z_split
            _part_span = zmax - zmin
            _band = 0.15 * _part_span

            def is_edge_within_band(edge, split_val, band_val, ax):
                try:
                    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
                    adaptor = BRepAdaptor_Curve(edge)
                    t1, t2 = adaptor.FirstParameter(), adaptor.LastParameter()
                    p1 = adaptor.Value(t1)
                    p2 = adaptor.Value(t2)
                    pt_mid = adaptor.Value((t1 + t2) / 2.0)
                    h1  = [p1.X(),     p1.Y(),     p1.Z()    ][ax]
                    h2  = [p2.X(),     p2.Y(),     p2.Z()    ][ax]
                    hm  = [pt_mid.X(), pt_mid.Y(), pt_mid.Z()][ax]
                    return (abs(h1 - split_val) <= band_val and
                            abs(h2 - split_val) <= band_val and
                            abs(hm - split_val) <= band_val)
                except Exception:
                    return False

            parting_edges = [
                e for e in parting_edges
                if is_edge_within_band(e, active_split, _band, axis_idx)
            ]

            LOOP_TOL = 20.0
            all_loops = build_loops_for_edges(parting_edges, LOOP_TOL)
            
            closed_loops = [l for l in all_loops if l['is_closed']]
            if closed_loops:
                def _ll(loop):
                    return sum(self._get_edge_length(e) for e in loop['edges'])
                max_len = max(_ll(l) for l in closed_loops)
                loops = [l for l in closed_loops if _ll(l) >= 0.10 * max_len]
            else:
                loops = []

        else:
            # --- X/Y-Axes: Plane-Intersection (Section Cut) Method ---
            axis_name = "X"
            midplane_val = (xmin + xmax) / 2.0
            dir_vector = gp_Dir(1, 0, 0)
            if best_axis == "Y":
                axis_name = "Y"
                midplane_val = (ymin + ymax) / 2.0
                dir_vector = gp_Dir(0, 1, 0)

            pnt_origin = gp_Pnt(midplane_val, 0, 0) if axis_name == "X" else gp_Pnt(0, midplane_val, 0)
            pln = gp_Pln(pnt_origin, dir_vector)
            section = BRepAlgoAPI_Section(self.part.shape, pln, True)
            section.Build()
            
            sec_explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
            section_edges = []
            while sec_explorer.More():
                section_edges.append(topods.Edge(sec_explorer.Current()))
                sec_explorer.Next()

            LOOP_TOL = min(6.0, _min_dim * 0.1)
            all_loops = build_loops_for_edges(section_edges, LOOP_TOL)
            loops = [l for l in all_loops if l['is_closed']]

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
