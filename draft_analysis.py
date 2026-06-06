import math
import numpy as np


class DraftAnalyzer:

    def __init__(self, part):
        self.part = part

    def compute_signed_draft_angle(
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

        normal_norm = np.linalg.norm(normal)
        direction_norm = np.linalg.norm(direction)

        if normal_norm == 0:
            return None

        if direction_norm == 0:
            return None

        normal = normal / normal_norm
        direction = direction / direction_norm

        dot_product = np.dot(
            normal,
            direction
        )

        dot_product = max(
            -1.0,
            min(1.0, dot_product)
        )

        angle = math.degrees(
            math.acos(dot_product)
        )

        draft_angle = 90.0 - angle

        return draft_angle

    def classify_face(
        self,
        draft_angle,
        threshold_deg=3.0
    ):

        if draft_angle is None:
            return "UNKNOWN"

        if draft_angle < 0:
            return "UNDERCUT"

        if draft_angle < threshold_deg:
            return "WARNING"

        return "SAFE"

    def analyze_direction(
        self,
        pull_direction,
        threshold_deg=3.0
    ):

        results = []

        for face in self.part.faces:

            draft_angle = (
                self.compute_signed_draft_angle(
                    face.normal,
                    pull_direction
                )
            )

            classification = (
                self.classify_face(
                    draft_angle,
                    threshold_deg
                )
            )

            results.append({
                "face_id": face.face_id,
                "draft_angle": draft_angle,
                "classification": classification,
                "area": face.area
            })

        return results