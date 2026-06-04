from OCC.Display.SimpleGui import init_display
from OCC.Core.Quantity import (
    Quantity_Color,
    Quantity_NOC_RED,
    Quantity_NOC_YELLOW
)

class PartVisualizer:

    def __init__(self):

        (
            self.display,
            self.start_display,
            _,
            _
        ) = init_display()

    def show_part(
        self,
        shape
    ):

        self.display.DisplayShape(
            shape,
            update=True
        )

    def show_edges(
        self,
        shared_edges
    ):

        for item in shared_edges:

            edge = item["edge"]

            yellow = Quantity_Color(
                Quantity_NOC_YELLOW
            )

            self.display.DisplayColoredShape(
                edge,
                yellow,
                update=False
            )

    def run(self):

        self.display.FitAll()

        self.start_display()

    def show_silhouette_faces(
        self,
        face_map,
        silhouette_face_ids
    ):

        red = Quantity_Color(
            Quantity_NOC_RED
        )

        for face_id in silhouette_face_ids:

            if face_id not in face_map:
                continue

            face = face_map[face_id]

            self.display.DisplayColoredShape(
                face,
                red,
                update=False
            )