import numpy as np


class UndercutDetector:

    def __init__(self, part):
        self.part = part

    def is_undercut(
        self,
        face_normal,
        pull_direction
    ):

        normal = np.array(
            face_normal,
            dtype=float
        )

        direction = np.array(
            pull_direction,
            dtype=float
        )

        normal_norm = np.linalg.norm(
            normal
        )

        direction_norm = np.linalg.norm(
            direction
        )

        if normal_norm == 0:
            return False

        if direction_norm == 0:
            return False

        normal = normal / normal_norm
        direction = direction / direction_norm

        dot_product = np.dot(
            normal,
            direction
        )

        return dot_product < 0

    def analyze(
        self,
        pull_direction
    ):

        undercut_faces = []

        total_undercut_area = 0.0

        for face in self.part.faces:

            if self.is_undercut(
                face.normal,
                pull_direction
            ):

                undercut_faces.append(
                    face.face_id
                )

                total_undercut_area += (
                    face.area
                )

        return {
            "undercut_faces":
                undercut_faces,

            "undercut_count":
                len(undercut_faces),

            "undercut_area":
                total_undercut_area
        }