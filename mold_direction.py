import math
import numpy as np



class MoldDirectionAnalyzer:

    def __init__(self, part):
        self.part = part

    def generate_candidate_directions(
        self,
        n_samples=500
    ):

        directions = []

        # Include principal axes (positive and negative)
        for axis in [
            np.array([0.0, 0.0, 1.0]),
            np.array([0.0, 0.0, -1.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, -1.0, 0.0]),
            np.array([1.0, 0.0, 0.0]),
            np.array([-1.0, 0.0, 0.0]),
        ]:
            directions.append(axis)

        golden_angle = math.pi * (
            3.0 - math.sqrt(5.0)
        )

        # Generate both hemispheres to be thorough
        for i in range(n_samples):
            # Map i to [-1, 1] for full sphere
            z = -1.0 + (2.0 * i) / float(n_samples - 1)

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

        # Calculate a primary score based on area and face counts
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

        # Prioritize vertical-ish (Z-aligned) directions to avoid
        # horizontal directions, which are often less practical or represent
        # a sideways mold opening.
        z_component = abs(direction[2])
        total_area = safe_area + warning_area + undercut_area
        if total_area > 0:
            # Add a significant bonus for Z-alignment (up to 5.0 * total_area)
            score += 5.0 * z_component * total_area

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

        # Calculate confidence score
        # Confidence is higher when we have fewer undercuts and more safe areas.
        from draft_analysis import DraftAnalyzer
        draft_analyzer = DraftAnalyzer(self.part)
        draft_results = draft_analyzer.analyze_direction(best_direction)
        
        total_area = 0.0
        safe_area = 0.0
        undercut_area = 0.0
        
        for face, result in zip(self.part.faces, draft_results):
            total_area += face.area
            if result["classification"] == "SAFE":
                safe_area += face.area
            elif result["classification"] == "UNDERCUT":
                undercut_area += face.area

        confidence = 0.0
        if total_area > 0:
            confidence = (total_area - undercut_area) / total_area
            # reduce confidence if safe area is very low
            confidence *= (0.5 + 0.5 * (safe_area / total_area))

        return best_direction, confidence