import numpy as np


class UndercutDetector:

    def __init__(self, part):
        self.part = part

    def analyze(
        self,
        pull_direction
    ):
        d = np.array(pull_direction, dtype=float)
        d_norm = np.linalg.norm(d)
        if d_norm > 0:
            d = d / d_norm

        # Project face centroids along the pull direction
        projections = []
        for face in self.part.faces:
            centroid = np.array(face.centroid)
            projections.append(np.dot(centroid, d))

        proj_min = min(projections) if projections else 0.0
        proj_max = max(projections) if projections else 0.0
        proj_mid = (proj_min + proj_max) / 2.0

        undercut_faces = []
        total_undercut_area = 0.0

        for face in self.part.faces:
            centroid = np.array(face.centroid)
            proj = np.dot(centroid, d)

            normal = np.array(face.normal, dtype=float)
            norm = np.linalg.norm(normal)
            if norm == 0:
                continue
            normal = normal / norm

            dot_product = np.dot(normal, d)

            # Heuristic core/cavity division:
            # Cavity-side (proj >= proj_mid) pulls along +d: undercut if dot_product < -1e-5
            # Core-side (proj < proj_mid) pulls along -d: undercut if dot_product > 1e-5
            is_undercut = False
            if proj >= proj_mid:
                if dot_product < -1e-5:
                    is_undercut = True
            else:
                if dot_product > 1e-5:
                    is_undercut = True

            if is_undercut:
                undercut_faces.append(face.face_id)
                total_undercut_area += face.area

        return {
            "undercut_faces":
                undercut_faces,

            "undercut_count":
                len(undercut_faces),

            "undercut_area":
                total_undercut_area
        }