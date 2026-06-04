import math
import numpy as np
from undercut_detector import UndercutDetector


class MoldDirectionAnalyzer:

    def __init__(self, part):
        self.part = part

    def generate_candidate_directions(
        self,
        n_samples=500
    ):

        directions = []

        golden_angle = math.pi * (
            3.0 - math.sqrt(5.0)
        )

        for i in range(n_samples):

            z = i / float(n_samples - 1)

            radius = math.sqrt(
                max(0.0, 1.0 - z * z)
            )

            theta = golden_angle * i

            x = radius * math.cos(theta)
            y = radius * math.sin(theta)

            direction = np.array(
                [x, y, z],
                dtype=float
            )

            norm = np.linalg.norm(
                direction
            )

            if norm > 0:

                direction = (
                    direction / norm
                )

                directions.append(
                    direction
                )

        return directions

    def score_direction(
        self,
        direction
    ):

        from draft_analysis import DraftAnalyzer

        draft_analyzer = DraftAnalyzer(
            self.part
        )

        draft_results = (
            draft_analyzer.analyze_direction(
                direction
            )
        )

        alignment_score = 0.0

        safe_area = 0.0
        warning_area = 0.0
        undercut_area = 0.0

        safe_faces = 0
        warning_faces = 0
        undercut_faces = 0

        for face, result in zip(
            self.part.faces,
            draft_results
        ):

            normal = np.array(
                face.normal,
                dtype=float
            )

            norm = np.linalg.norm(
                normal
            )

            if norm > 0:

                normal = normal / norm

                alignment = np.dot(
                    normal,
                    direction
                )

                if alignment > 0:

                    alignment_score += (
                        alignment
                        * face.area
                    )

            classification = (
                result["classification"]
            )

            if classification == "SAFE":

                safe_area += face.area
                safe_faces += 1

            elif classification == "WARNING":

                warning_area += face.area
                warning_faces += 1

            elif classification == "UNDERCUT":

                undercut_area += face.area
                undercut_faces += 1

        score = (
            alignment_score
            +
            5.0 * safe_area
            +
            2.0 * warning_area
            -
            10.0 * undercut_area
            -
            25.0 * undercut_faces
        )

        return score

    def find_best_direction(
        self,
        n_samples=500
    ):

        candidates = (
            self.generate_candidate_directions(
                n_samples
            )
        )

        best_direction = None

        best_score = -1e18

        for direction in candidates:

            score = (
                self.score_direction(
                    direction
                )
            )

            if score > best_score:

                best_score = score

                best_direction = direction

        print(
            f"Best Optimization Score: "
            f"{best_score:.3f}"
        )

        return (
            best_direction,
            best_score
        )