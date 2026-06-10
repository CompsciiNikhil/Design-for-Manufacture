from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRep import BRep_Tool

from OCC.Core.BRepTools import breptools
from OCC.Core.GeomLProp import GeomLProp_SLProps

from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop

from models import FaceData, PartData


class StepParser:

    SURFACE_NAMES = {
        0: "Plane",
        1: "Cylinder",
        2: "Cone",
        3: "Sphere",
        4: "Torus",
        5: "Bezier",
        6: "BSpline",
        7: "Revolution",
        8: "Extrusion",
        9: "Offset",
        10: "Other"
    }

    def __init__(self, step_path):
        self.step_path = step_path

    def load_shape(self):
        reader = STEPControl_Reader()

        status = reader.ReadFile(self.step_path)

        if status != 1:
            raise RuntimeError(
                f"Failed to load STEP file: {self.step_path}"
            )

        reader.TransferRoots()

        return reader.OneShape()

    def get_surface_type(self, face):
        adaptor = BRepAdaptor_Surface(face)

        surface_type = adaptor.GetType()

        return self.SURFACE_NAMES.get(
            surface_type,
            "Unknown"
        )

    def get_area_and_centroid(self, face):
        props = GProp_GProps()

        brepgprop.SurfaceProperties(face, props)

        area = props.Mass()

        center = props.CentreOfMass()

        centroid = (
            center.X(),
            center.Y(),
            center.Z()
        )

        return area, centroid

    def get_normal(self, face):
        try:
            surface = BRep_Tool.Surface(face)

            u_min, u_max, v_min, v_max = breptools.UVBounds(face)

            u_mid = (u_min + u_max) / 2.0
            v_mid = (v_min + v_max) / 2.0

            props = GeomLProp_SLProps(
                surface,
                u_mid,
                v_mid,
                1,
                1e-6
            )

            if props.IsNormalDefined():

                normal = props.Normal()
                nx, ny, nz = normal.X(), normal.Y(), normal.Z()

                # If the face has reversed orientation, negate the geometric normal
                if face.Orientation() == TopAbs_REVERSED:
                    nx, ny, nz = -nx, -ny, -nz

                return (nx, ny, nz)

        except Exception:
            pass

        return (0.0, 0.0, 0.0)

    def parse(self):

        print(f"Loading STEP file: {self.step_path}")

        shape = self.load_shape()

        explorer = TopExp_Explorer(
            shape,
            TopAbs_FACE
        )

        faces = []

        face_id = 0

        while explorer.More():

            face = topods.Face(
                explorer.Current()
            )

            try:

                surface_type = self.get_surface_type(face)

                area, centroid = (
                    self.get_area_and_centroid(face)
                )

                normal = self.get_normal(face)

                face_data = FaceData(
                    face_id=face_id,
                    surface_type=surface_type,
                    area=area,
                    centroid=centroid,
                    normal=normal,
                    neighbors=[]
                )

                faces.append(face_data)

            except Exception as e:

                print(
                    f"Failed face {face_id}: {e}"
                )

            face_id += 1

            explorer.Next()

        print(
            f"Faces extracted: {len(faces)}"
        )

        return PartData(
            faces=faces,
            shape=shape
            )