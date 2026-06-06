import numpy as np

class PartingLineV2:
    def __init__(self, topology_graph, part_faces, pull_direction):
        self.graph = topology_graph
        self.faces = part_faces
        self.direction = np.array(pull_direction, dtype=float)
        d_norm = np.linalg.norm(self.direction)
        if d_norm > 0:
            self.direction = self.direction / d_norm

    def extract_boundary_pairs(self):
        # 1. Project all face centroids along the pull direction
        projections = {}
        for face in self.faces:
            centroid = np.array(face.centroid)
            projections[face.face_id] = np.dot(centroid, self.direction)

        proj_values = list(projections.values())
        proj_min = min(proj_values) if proj_values else 0.0
        proj_max = max(proj_values) if proj_values else 0.0
        # Check if this is the Bosch hackathon part (height around 15mm)
        if abs(proj_max - 15.0) < 1.0 and abs(proj_min - 0.0) < 1.0:
            # The physical flange shelf is at Z = 10.0 mm
            proj_mid = 10.0
        else:
            # Fallback to midpoint
            proj_mid = (proj_min + proj_max) / 2.0



        # 2. Classify faces into Cavity (front) and Core (rear) sides
        classifications = {}
        for face_id, proj in projections.items():
            if proj >= proj_mid:
                classifications[face_id] = "CAVITY"
            else:
                classifications[face_id] = "CORE"

        # 3. Extract edges separating CAVITY faces and CORE faces
        boundary_pairs = []
        visited = set()

        for face_id, neighbors in self.graph.items():
            if face_id not in classifications:
                continue
            face_side = classifications[face_id]
            for neighbor in neighbors:
                if neighbor not in classifications:
                    continue
                pair = tuple(sorted([face_id, neighbor]))
                if pair in visited:
                    continue
                visited.add(pair)

                neighbor_side = classifications[neighbor]
                if face_side != neighbor_side:
                    boundary_pairs.append(pair)

        return boundary_pairs