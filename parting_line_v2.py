class PartingLineV2:

    def __init__(
        self,
        topology_graph,
        silhouette_faces
    ):

        self.graph = topology_graph

        self.silhouette_faces = set(
            silhouette_faces
        )

    def extract_boundary_pairs(self):

        boundary_pairs = []

        visited = set()

        for face_id, neighbors in (
            self.graph.items()
        ):

            is_silhouette = (
                face_id
                in
                self.silhouette_faces
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

                neighbor_silhouette = (
                    neighbor
                    in
                    self.silhouette_faces
                )

                if (
                    is_silhouette
                    !=
                    neighbor_silhouette
                ):

                    boundary_pairs.append(
                        pair
                    )

        return boundary_pairs