import numpy as np


class CoreCavityClassifier:

    def __init__(self, part):
        self.part = part

    def classify(
        self,
        mold_direction,
        tolerance=0.15
    ):

        results = []

        core_count = 0
        cavity_count = 0
        neutral_count = 0

        for face in self.part.faces:

            normal = np.array(
                face.normal,
                dtype=float
            )

            norm = np.linalg.norm(
                normal
            )

            if norm == 0:

                label = "NEUTRAL"

            else:

                normal = normal / norm

                dot = np.dot(
                    normal,
                    mold_direction
                )

                if dot > tolerance:

                    label = "CAVITY"
                    cavity_count += 1

                elif dot < -tolerance:

                    label = "CORE"
                    core_count += 1

                else:

                    label = "NEUTRAL"
                    neutral_count += 1

            results.append({

                "face_id":
                    face.face_id,

                "classification":
                    label
            })

        return {

            "results":
                results,

            "core_count":
                core_count,

            "cavity_count":
                cavity_count,

            "neutral_count":
                neutral_count
        }