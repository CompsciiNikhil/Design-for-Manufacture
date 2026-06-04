from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods

from OCC.Core.TopTools import (
    TopTools_IndexedDataMapOfShapeListOfShape
)

from OCC.Core.TopExp import topexp


class TopologyExtractor:

    def __init__(self, shape):
        self.shape = shape
        self.face_map = None

    def get_face_map(self):
        return self.build_face_map()

    def build_face_map(self):
        if self.face_map is not None:
            return self.face_map

        explorer = TopExp_Explorer(
            self.shape,
            TopAbs_FACE
        )

        face_map = {}

        face_id = 0

        while explorer.More():

            face = topods.Face(
                explorer.Current()
            )

            face_map[face_id] = face

            face_id += 1

            explorer.Next()
        if self.face_map is not None:
            return self.face_map
        
        return face_map

    def build_adjacency_graph(self):

        face_map = self.build_face_map()

        graph = {
            face_id: set()
            for face_id in face_map
        }

        edge_face_map = (
            TopTools_IndexedDataMapOfShapeListOfShape()
        )

        topexp.MapShapesAndAncestors(
            self.shape,
            6,   # EDGE
            4,   # FACE
            edge_face_map
        )

        for i in range(
            1,
            edge_face_map.Size() + 1
        ):

            faces = edge_face_map.FindFromIndex(i)

            if faces.Size() != 2:
                continue

            face_a = faces.First()
            face_b = faces.Last()

            id_a = None
            id_b = None

            for face_id, face in face_map.items():

                if face.IsSame(face_a):
                    id_a = face_id

                if face.IsSame(face_b):
                    id_b = face_id

            if (
                id_a is not None
                and id_b is not None
            ):
                graph[id_a].add(id_b)
                graph[id_b].add(id_a)

        return {
            k: sorted(list(v))
            for k, v in graph.items()
        }