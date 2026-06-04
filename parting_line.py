class PartingLineExtractor:

    def __init__(
        self,
        topology_graph,
        classifications
    ):
        self.graph = topology_graph

        self.classifications = {}

        for item in classifications["results"]:

            self.classifications[
                item["face_id"]
            ] = item["classification"]

    def extract_candidates(self):

        candidates = []

        visited = set()

        for face_id, neighbors in self.graph.items():

            face_type = (
                self.classifications.get(
                    face_id,
                    "NEUTRAL"
                )
            )

            for neighbor in neighbors:

                pair = tuple(
                    sorted(
                        [face_id, neighbor]
                    )
                )

                if pair in visited:
                    continue

                visited.add(pair)

                neighbor_type = (
                    self.classifications.get(
                        neighbor,
                        "NEUTRAL"
                    )
                )

                is_boundary = (

                    (face_type == "CORE"
                     and
                     neighbor_type == "CAVITY")

                    or

                    (face_type == "CAVITY"
                     and
                     neighbor_type == "CORE")
                )

                if is_boundary:

                    candidates.append(
                        pair
                    )

        return candidates