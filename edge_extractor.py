from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods


class EdgeExtractor:

    def __init__(
        self,
        face_map
    ):
        self.face_map = face_map

    def get_face_edges(
        self,
        face
    ):

        edges = []

        explorer = TopExp_Explorer(
            face,
            TopAbs_EDGE
        )

        while explorer.More():

            edge = topods.Edge(
                explorer.Current()
            )

            edges.append(edge)

            explorer.Next()

        return edges

    def find_shared_edge(
        self,
        face_a,
        face_b
    ):

        edges_a = (
            self.get_face_edges(
                face_a
            )
        )

        edges_b = (
            self.get_face_edges(
                face_b
            )
        )

        for edge_a in edges_a:

            for edge_b in edges_b:

                if edge_a.IsSame(edge_b):

                    return edge_a

        return None

    def extract_shared_edges(
        self,
        boundary_pairs
    ):

        shared_edges = []

        for face_id_a, face_id_b in boundary_pairs:

            face_a = (
                self.face_map[
                    face_id_a
                ]
            )

            face_b = (
                self.face_map[
                    face_id_b
                ]
            )

            edge = (
                self.find_shared_edge(
                    face_a,
                    face_b
                )
            )

            if edge is not None:

                shared_edges.append({

                    "face_a":
                        face_id_a,

                    "face_b":
                        face_id_b,

                    "edge":
                        edge
                })

        return shared_edges