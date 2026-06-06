import sys
import os

# Set project root in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dfm_engine import DFMEngine
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

part_path = os.path.join(project_root, "examples", "Part1.stp")
engine = DFMEngine(part_path)
engine.load_part()
result = engine.run_analysis()

bbox = Bnd_Box()
brepbndlib.Add(engine.part.shape, bbox)
xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
total_area = sum(f.area for f in engine.part.faces)

axes = {
    "X-Axis Mold Opening (Core->-X, Cavity->+X)": ([1, 0, 0], (xmin + xmax) / 2.0),
    "Y-Axis Mold Opening (Core->-Y, Cavity->+Y)": ([0, 1, 0], (ymin + ymax) / 2.0),
    "Z-Axis Mold Opening (Core->-Z, Cavity->+Z)": ([0, 0, 1], result.optimal_z)
}

print("=== MOLD OPENING AXIS EVALUATION RESULTS ===")
for name, (vec, split) in axes.items():
    stats = engine.evaluate_pull_direction_and_split(vec, split)
    crossing = stats["crossing_faces"]
    complexity = crossing + (stats["undercut_count"] / 5.0)
    ratio = stats["undercut_area"] / total_area
    score = max(0.0, 100.0 - (ratio * 150.0) - (complexity * 0.2))
    
    status = "MOLDABLE" if score >= 75 else ("PARTIALLY MOLDABLE" if score >= 50 else "NOT MOLDABLE")
    
    print(f"\n{name}:")
    print(f"  Status:            {status}")
    print(f"  Moldability Score: {score:.2f} / 100")
    print(f"  Undercut Count:    {stats['undercut_count']}")
    print(f"  Undercut Area:     {stats['undercut_area']:.2f} mm2")
    print(f"  Crossing Faces:    {crossing}")
    print(f"  Core Faces:        {stats['core_faces']}")
    print(f"  Cavity Faces:      {stats['cavity_faces']}")
