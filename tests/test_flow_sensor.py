import sys
import os
import numpy as np

# Set project root in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from step_parser import StepParser
from dfm_engine import DFMEngine
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Trsf
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCC.Core.TopoDS import topods

def inspect_step_file(filepath):
    print(f"\n==========================================")
    print(f"Inspecting file: {filepath}")
    print(f"==========================================")
    
    if not os.path.exists(filepath):
        print(f"File does not exist: {filepath}")
        return
        
    # 1. Parse shape
    parser = StepParser(filepath)
    part_data = parser.parse()
    shape = part_data.shape
    
    # 2. Extract shape metrics
    print(f"Shape type of imported model: {type(shape)}")
    print(f"Is null shape: {shape.IsNull()}")
    
    # Count faces and solids
    face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_count = 0
    while face_explorer.More():
        face_count += 1
        face_explorer.Next()
        
    solid_explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solid_count = 0
    while solid_explorer.More():
        solid_count += 1
        solid_explorer.Next()
        
    # Bounding box
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    dx = xmax - xmin
    dy = ymax - ymin
    dz = zmax - zmin
    print(f"Face count: {face_count}")
    print(f"Solid count: {solid_count}")
    print(f"Bounding Box: X=[{xmin:.4f}, {xmax:.4f}], Y=[{ymin:.4f}, {ymax:.4f}], Z=[{zmin:.4f}, {zmax:.4f}]")
    print(f"Dimensions: DX={dx:.4f}, DY={dy:.4f}, DZ={dz:.4f}")
    
    # 3. Initialize Engine
    engine = DFMEngine(filepath)
    engine.load_part()
    
    # 4. Simulate optimal Z parting plane split (similar to Parting Line tab)
    print("\n--- Simulating parting line extraction ---")
    
    # Run the dynamic analysis to determine the optimal pull direction
    analysis_res = engine.run_analysis()
    d = analysis_res.mold_direction
    z_split = analysis_res.optimal_z
    
    axis_char = "Z"
    if abs(d[0]) > 0.9:
        axis_char = "X"
    elif abs(d[1]) > 0.9:
        axis_char = "Y"
        
    print(f"Optimal mold direction: {d}")
    print(f"Optimal parting plane: {axis_char} = {z_split:.4f}")
    
    # Cavity and core boxes
    bx_min = xmin - dx * 0.15
    bx_max = xmax + dx * 0.15
    by_min = ymin - dy * 0.15
    by_max = ymax + dy * 0.15
    bz_min = zmin - dz * 0.15
    bz_max = zmax + dz * 0.15
    
    if axis_char == "X":
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(z_split, by_min, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(z_split, by_max, bz_max)).Shape()
    elif axis_char == "Y":
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, z_split, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(bx_max, z_split, bz_max)).Shape()
    else:
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, z_split), gp_Pnt(bx_max, by_max, zmax + dz * 0.3)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, zmin - dz * 0.3), gp_Pnt(bx_max, by_max, z_split)).Shape()
    
    print("Performing Boolean Cut for Cavity...")
    try:
        cavity_cut = BRepAlgoAPI_Cut(cavity_box, shape).Shape()
        if cavity_cut is None or cavity_cut.IsNull():
            raise RuntimeError("Cavity cut shape is None or Null")
        print(f"Cavity Cut Shape Type: {type(cavity_cut)}, IsNull: {cavity_cut.IsNull()}")
        cav_explorer = TopExp_Explorer(cavity_cut, TopAbs_FACE)
        cav_faces = 0
        while cav_explorer.More():
            cav_faces += 1
            cav_explorer.Next()
        print(f"Cavity Cut Face Count: {cav_faces}")
    except Exception as e:
        print("Cavity Cut failed, falling back to blank block:", e)
        cavity_cut = cavity_box
        
    print("Performing Boolean Cut for Core...")
    try:
        core_cut = BRepAlgoAPI_Cut(core_box, shape).Shape()
        if core_cut is None or core_cut.IsNull():
            raise RuntimeError("Core cut shape is None or Null")
        print(f"Core Cut Shape Type: {type(core_cut)}, IsNull: {core_cut.IsNull()}")
        cor_explorer = TopExp_Explorer(core_cut, TopAbs_FACE)
        cor_faces = 0
        while cor_explorer.More():
            cor_faces += 1
            cor_explorer.Next()
        print(f"Core Cut Face Count: {cor_faces}")
    except Exception as e:
        print("Core Cut failed, falling back to blank block:", e)
        core_cut = core_box

    # Now, test the BRepBuilderAPI_Transform calls
    if axis_char == "X":
        default_trans = dx * 1.3
        trans_vec = gp_Vec(default_trans, 0, 0)
    elif axis_char == "Y":
        default_trans = dy * 1.3
        trans_vec = gp_Vec(0, default_trans, 0)
    else:
        default_trans = max(zmax - z_split, z_split - zmin) + dz * 0.35
        trans_vec = gp_Vec(0, 0, default_trans)
    
    trsf_cavity = gp_Trsf()
    trsf_cavity.SetTranslation(trans_vec)
    
    trsf_core = gp_Trsf()
    trsf_core.SetTranslation(-trans_vec)
    
    # Let's inspect the arguments we are passing
    print("\n--- Inspecting Transform Arguments for Cavity ---")
    print(f"1st argument type: {type(cavity_cut)}")
    print(f"1st argument IsNull: {cavity_cut.IsNull() if cavity_cut else 'N/A'}")
    print(f"2nd argument type: {type(trsf_cavity)}")
    print(f"3rd argument (boolean) value: True, type: {type(True)}")
    
    try:
        print("Attempting 3-argument transform for Cavity...")
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True).Shape()
        print("SUCCESS! Cavity exploded transform worked.")
    except Exception as e:
        print(f"FAILED! Cavity exploded transform raised exception: {type(e).__name__}: {e}")
        
    print("\n--- Inspecting Transform Arguments for Core ---")
    print(f"1st argument type: {type(core_cut)}")
    print(f"1st argument IsNull: {core_cut.IsNull() if core_cut else 'N/A'}")
    print(f"2nd argument type: {type(trsf_core)}")
    print(f"3rd argument (boolean) value: True, type: {type(True)}")
    
    try:
        print("Attempting 3-argument transform for Core...")
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True).Shape()
        print("SUCCESS! Core exploded transform worked.")
    except Exception as e:
        print(f"FAILED! Core exploded transform raised exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    part1_path = os.path.join(project_root, "examples", "Part1.stp")
    inspect_step_file(part1_path)
    
    cube_path = os.path.join(project_root, "examples", "cube.stp")
    inspect_step_file(cube_path)
    
    cylinder_path = os.path.join(project_root, "examples", "cylinder.stp")
    inspect_step_file(cylinder_path)
    
    bracket_path = os.path.join(project_root, "examples", "bracket.stp")
    inspect_step_file(bracket_path)
    
    flow_sensor_path = r"C:\Users\comps\Downloads\flow sensor part 2.stp"
    inspect_step_file(flow_sensor_path)
