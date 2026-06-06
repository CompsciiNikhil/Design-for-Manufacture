import sys
import os
import numpy as np

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

bbox = Bnd_Box()
brepbndlib.Add(engine.part.shape, bbox)
xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
total_area = sum(f.area for f in engine.part.faces)
total_faces = len(engine.part.faces)

axes_info = {
    "X-Axis": ([1, 0, 0], xmin, xmax),
    "Y-Axis": ([0, 1, 0], ymin, ymax),
    "Z-Axis": ([0, 0, 1], zmin, zmax)
}

print("=== PARTING PLANE OPTIMIZATION SCAN ===")
for name, (vec, axis_min, axis_max) in axes_info.items():
    # Scan candidate positions from 5% to 95% at 5% steps (19 candidates)
    candidates = np.linspace(axis_min + 0.05 * (axis_max - axis_min), axis_min + 0.95 * (axis_max - axis_min), 19)
    
    best_plane = None
    best_score = -1.0
    best_stats = None
    
    for plane in candidates:
        stats = engine.evaluate_pull_direction_and_split(vec, plane)
        
        # Balance
        core_cnt = stats["core_faces"]
        cavity_cnt = stats["cavity_faces"]
        max_cnt = max(1.0, max(core_cnt, cavity_cnt))
        balance = min(core_cnt, cavity_cnt) / max_cnt
        
        # Area ratio
        ratio = stats["undercut_area"] / total_area
        
        # Count ratio
        cnt_ratio = stats["undercut_count"] / total_faces
        
        # Crossing ratio
        cross_ratio = stats["crossing_faces"] / total_faces
        
        # Score calculation: 40% Undercut Area + 25% Undercut Count + 20% Crossing + 15% Balance
        score = (
            0.40 * (100.0 - ratio * 100.0) +
            0.25 * (100.0 - cnt_ratio * 100.0) +
            0.20 * (100.0 - cross_ratio * 100.0) +
            0.15 * (balance * 100.0)
        )
        score = max(0.0, score)
        
        if score > best_score:
            best_score = score
            best_plane = plane
            best_stats = stats
            best_stats["balance"] = balance
            best_stats["score"] = score
            
    # Classification
    if best_score >= 85:
        classification = "MOLDABLE"
    elif best_score >= 70:
        classification = "PARTIALLY MOLDABLE"
    elif best_score >= 50:
        classification = "SIDE ACTION REQUIRED"
    else:
        classification = "NOT MOLDABLE"
        
    print(f"\n{name} Mold Opening:")
    print(f"  Best Split Plane:  {best_plane:.2f} mm")
    print(f"  Moldability Score: {best_score:.2f} / 100")
    print(f"  Classification:    {classification}")
    print(f"  Undercuts:         {best_stats['undercut_count']} count, {best_stats['undercut_area']:.2f} mm2 area")
    print(f"  Crossing Faces:    {best_stats['crossing_faces']}")
    print(f"  Core Faces:        {best_stats['core_faces']}")
    print(f"  Cavity Faces:      {best_stats['cavity_faces']}")
    print(f"  Core/Cavity Bal:   {best_stats['balance']:.2f}")
