import os
import sys

# Set project root in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.gp import gp_Pnt

def export_step(shape, filepath):
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(filepath)
    print(f"Exported STEP model to {filepath}")

def generate_shapes():
    examples_dir = os.path.join(project_root, "examples")
    os.makedirs(examples_dir, exist_ok=True)
    
    # 1. Cube
    cube = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    export_step(cube, os.path.join(examples_dir, "cube.stp"))
    
    # 2. Cylinder
    cylinder = BRepPrimAPI_MakeCylinder(5.0, 20.0).Shape()
    export_step(cylinder, os.path.join(examples_dir, "cylinder.stp"))
    
    # 3. Bracket (fusing base plate and upright flange)
    base = BRepPrimAPI_MakeBox(gp_Pnt(0,0,0), gp_Pnt(30, 20, 5)).Shape()
    flange = BRepPrimAPI_MakeBox(gp_Pnt(0,0,5), gp_Pnt(5, 20, 25)).Shape()
    bracket = BRepAlgoAPI_Fuse(base, flange).Shape()
    export_step(bracket, os.path.join(examples_dir, "bracket.stp"))

if __name__ == "__main__":
    generate_shapes()
