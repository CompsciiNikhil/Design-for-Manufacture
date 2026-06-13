import numpy as np


class UndercutDetector:

    def __init__(self, part):
        self.part = part

    def analyze(
        self,
        pull_direction,
        split_value=None
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

        # Use the externally optimised parting plane if supplied;
        # otherwise fall back to the geometric centroid midpoint.
        if split_value is not None:
            proj_mid = float(split_value)
        else:
            proj_mid = (proj_min + proj_max) / 2.0

        undercut_faces = []
        total_undercut_area = 0.0

        # Dot-product threshold: 0.01 ≈ 0.57°, avoids floating-point noise
        # on near-vertical walls being flagged as undercuts.
        DRAFT_TOL = 0.01

        for face in self.part.faces:
            centroid = np.array(face.centroid)
            proj = np.dot(centroid, d)

            normal = np.array(face.normal, dtype=float)
            norm = np.linalg.norm(normal)
            if norm == 0:
                continue
            normal = normal / norm

            dot_product = np.dot(normal, d)

            # Cavity-side (proj >= proj_mid) pulls along +d: undercut if dot < -DRAFT_TOL
            # Core-side   (proj <  proj_mid) pulls along -d: undercut if dot >  DRAFT_TOL
            is_undercut = False
            if proj >= proj_mid:
                if dot_product < -DRAFT_TOL:
                    is_undercut = True
            else:
                if dot_product > DRAFT_TOL:
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