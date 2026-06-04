import numpy as np


class SilhouetteDetector:

    def __init__(self, part):
        self.part = part

    def detect(
        self,
        mold_direction,
        threshold=0.15
    ):

        silhouette_faces = []

        silhouette_area = 0.0

        direction = np.array(
            mold_direction,
            dtype=float
        )

        direction_norm = np.linalg.norm(
            direction
        )

        if direction_norm == 0:
            return {
                "faces": [],
                "count": 0,
                "area": 0.0
            }

        direction = (
            direction / direction_norm
        )

        for face in self.part.faces:

            normal = np.array(
                face.normal,
                dtype=float
            )

            normal_norm = np.linalg.norm(
                normal
            )

            if normal_norm == 0:
                continue

            normal = (
                normal / normal_norm
            )

            alignment = abs(
                np.dot(
                    normal,
                    direction
                )
            )

            if alignment < threshold:

                silhouette_faces.append(
                    face.face_id
                )

                silhouette_area += (
                    face.area
                )

        return {

            "faces":
                silhouette_faces,

            "count":
                len(silhouette_faces),

            "area":
                silhouette_area
        }