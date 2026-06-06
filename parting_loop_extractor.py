import math
from collections import defaultdict
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_VERTEX
from OCC.Core.TopoDS import topods
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopExp import topexp
from OCC.Core.TopTools import TopTools_IndexedMapOfShape

class PartingLoopExtractor:
    def __init__(self):
        pass

    def build_edge_graph(self, shared_edges):
        """Existing method for backward compatibility."""
        graph = defaultdict(set)
        for item in shared_edges:
            edge = item["edge"]
            vertex_map = TopTools_IndexedMapOfShape()
            topexp.MapShapes(edge, TopAbs_VERTEX, vertex_map)
            if vertex_map.Size() != 2:
                continue
            v1 = topods.Vertex(vertex_map.FindKey(1))
            v2 = topods.Vertex(vertex_map.FindKey(2))
            graph[v1].add(v2)
            graph[v2].add(v1)
        return graph

    def _get_vertex_coords(self, vertex):
        pt = BRep_Tool.Pnt(vertex)
        return (round(pt.X(), 5), round(pt.Y(), 5), round(pt.Z(), 5))

    def _get_edge_vertices(self, edge):
        exp = TopExp_Explorer(edge, TopAbs_VERTEX)
        vertices = []
        while exp.More():
            vertices.append(topods.Vertex(exp.current() if hasattr(exp, 'current') else exp.Current()))
            exp.Next()
        return vertices

    def extract_loops(self, shared_edges):
        """
        Groups the list of shared edges into continuous, ordered loops/chains.
        Args:
            shared_edges: List of dicts, each with {"face_a": int, "face_b": int, "edge": TopoDS_Edge}
        Returns:
            List of dicts: [
                {
                    'edges': List[TopoDS_Edge],
                    'is_closed': bool,
                    'points': List[Tuple[float, float, float]]
                }
            ]
        """
        edges = [item["edge"] for item in shared_edges if "edge" in item and not item["edge"].IsNull()]
        if not edges:
            return []

        edge_infos = []
        for e in edges:
            v_list = self._get_edge_vertices(e)
            if len(v_list) < 2:
                if len(v_list) == 1:
                    v_p = self._get_vertex_coords(v_list[0])
                    edge_infos.append({
                        'edge': e,
                        'p1': v_p,
                        'p2': v_p
                    })
                continue
            p1 = self._get_vertex_coords(v_list[0])
            p2 = self._get_vertex_coords(v_list[1])
            edge_infos.append({
                'edge': e,
                'p1': p1,
                'p2': p2
            })

        def dist(p1, p2):
            return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

        loops = []
        used = set()
        tol = 1e-3  # 0.001 mm tolerance for snapping vertices

        while len(used) < len(edge_infos):
            # Find the first unused edge
            start_idx = -1
            for i, info in enumerate(edge_infos):
                if i not in used:
                    start_idx = i
                    break
            if start_idx == -1:
                break

            chain = [edge_infos[start_idx]]
            used.add(start_idx)

            # Grow the chain at the end
            growing = True
            while growing:
                growing = False
                end_pt = chain[-1]['p2']
                # Search for an unused edge that connects to end_pt
                for i, info in enumerate(edge_infos):
                    if i in used:
                        continue
                    if dist(info['p1'], end_pt) < tol:
                        chain.append(info)
                        used.add(i)
                        growing = True
                        break
                    elif dist(info['p2'], end_pt) < tol:
                        # Add with reversed endpoints
                        chain.append({
                            'edge': info['edge'],
                            'p1': info['p2'],
                            'p2': info['p1']
                        })
                        used.add(i)
                        growing = True
                        break

            # Grow the chain at the start
            growing = True
            while growing:
                growing = False
                start_pt = chain[0]['p1']
                for i, info in enumerate(edge_infos):
                    if i in used:
                        continue
                    if dist(info['p2'], start_pt) < tol:
                        chain.insert(0, info)
                        used.add(i)
                        growing = True
                        break
                    elif dist(info['p1'], start_pt) < tol:
                        chain.insert(0, {
                            'edge': info['edge'],
                            'p1': info['p2'],
                            'p2': info['p1']
                        })
                        used.add(i)
                        growing = True
                        break

            # Check if this chain is closed
            is_closed = dist(chain[0]['p1'], chain[-1]['p2']) < tol
            
            pts = []
            for item in chain:
                pts.append(item['p1'])
            pts.append(chain[-1]['p2'])

            loops.append({
                'edges': [item['edge'] for item in chain],
                'is_closed': is_closed,
                'points': pts
            })

        return loops