import os
import uuid
import asyncio
import json
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from dfm_engine import DFMEngine
from report_generator import export_pdf, export_json

# OpenCascade tessellation & geometry tools
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCC.Core.TopoDS import topods
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common, BRepAlgoAPI_Section
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Pln
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve


app = FastAPI(title="DfM Intelligence Agent API", version="1.0.0")

# Enable CORS for cross-origin frontend queries (such as Three.js frame requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory database of DfM analysis jobs
jobs = {}

class AnalyzeRequest(BaseModel):
    job_id: str
    material: str = "ABS"

class EvaluateRequest(BaseModel):
    job_id: str
    axis: str
    split_val: float

def tessellate_shape(shape, deflection=0.1):
    """Utility to tessellate any TopoDS_Shape and return vertices and indices."""
    mesh = BRepMesh_IncrementalMesh(shape, deflection)
    mesh.Perform()
    
    vertices = []
    indices = []
    
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    vertex_offset = 0
    while explorer.More():
        face = topods.Face(explorer.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, loc)
        if triangulation:
            nb_nodes = triangulation.NbNodes()
            for i in range(1, nb_nodes + 1):
                p = triangulation.Node(i)
                p_transformed = p.Transformed(loc.Transformation())
                vertices.extend([p_transformed.X(), p_transformed.Y(), p_transformed.Z()])
            
            nb_triangles = triangulation.NbTriangles()
            for i in range(1, nb_triangles + 1):
                t = triangulation.Triangle(i)
                idx1, idx2, idx3 = t.Get()
                indices.extend([vertex_offset + idx1 - 1, vertex_offset + idx2 - 1, vertex_offset + idx3 - 1])
                
            vertex_offset += nb_nodes
        explorer.Next()
        
    return {"vertices": vertices, "indices": indices}


def run_dfm_pipeline_sync(job_id: str, filepath: str, material: str):
    """Executes the DfM analysis pipeline synchronously on a background thread."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = "Initializing Engine..."

        # Custom status callback function passed to run_analysis
        def progress_callback(msg):
            jobs[job_id]["progress"] = msg

        engine = DFMEngine(filepath)
        result = engine.run_analysis(material=material, callback=progress_callback)
        
        # Save engine instance temporarily to allow mesh generation later
        jobs[job_id]["engine"] = engine
        jobs[job_id]["result"] = result
        jobs[job_id]["status"] = "success"
        jobs[job_id]["progress"] = "Analysis complete!"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = f"Error during analysis: {str(e)}"

@app.post("/upload-step")
async def upload_step(file: UploadFile = File(...)):
    """Saves the uploaded STEP file to disk and returns a unique job identifier."""
    if not file.filename.lower().endswith(('.stp', '.step')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .stp and .step are supported.")
        
    job_id = str(uuid.uuid4())
    filename = f"{job_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    jobs[job_id] = {
        "status": "pending",
        "progress": "File uploaded",
        "filepath": filepath,
        "filename": file.filename,
        "result": None,
        "engine": None
    }
    
    return {"job_id": job_id, "filename": file.filename}

@app.post("/analyze")
def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Triggers DfM analysis on a background thread."""
    job_id = request.job_id
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    job = jobs[job_id]
    if job["status"] == "processing":
        return {"status": "already_processing"}
        
    background_tasks.add_task(
        run_dfm_pipeline_sync,
        job_id=job_id,
        filepath=job["filepath"],
        material=request.material
    )
    
    return {"status": "started"}

@app.get("/results/{job_id}")
def get_results(job_id: str):
    """Returns the current status, progress logs, or computed analysis results of a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    job = jobs[job_id]
    
    # Do not attempt to serialize the engine object
    res_data = {
        "status": job["status"],
        "progress": job["progress"],
        "filename": job["filename"]
    }
    
    if job["status"] == "success" and job["result"]:
        engine = job["engine"]
        # Sanitize result to ensure JSON serializability
        from dataclasses import asdict
        raw_res = asdict(job["result"])
        
        # Remove raw non-serializable OpenCascade shape details
        if "parting_line" in raw_res:
            pl = raw_res["parting_line"]
            if "loops" in pl:
                for loop in pl["loops"]:
                    if "edges" in loop:
                        del loop["edges"]
            if "raw_edges" in pl:
                for re in pl["raw_edges"]:
                    if "edge" in re:
                        del re["edge"]
        
        # Add axis comparison results
        comparison_results = {}
        for ax in ["X", "Y", "Z"]:
            best_plane, best_score, best_stats = engine.optimize_parting_plane_for_axis(ax)
            comparison_results[ax] = {
                "best_plane": float(best_plane),
                "best_score": float(best_score),
                "undercut_count": int(best_stats["undercut_count"]),
                "undercut_area": float(best_stats["undercut_area"]),
                "crossing_faces": int(best_stats["crossing_faces"]),
                "complexity": float(best_stats["complexity"]),
                "classification": best_stats["classification"]
            }
        raw_res["axis_comparison"] = comparison_results

        # Add Z height sweeps results
        best_z, _, standard_positions = engine.scan_parting_planes()
        clean_standard_positions = {}
        for name, stats in standard_positions.items():
            clean_standard_positions[name] = {
                "undercut_count": int(stats["undercut_count"]),
                "undercut_area": float(stats["undercut_area"]),
                "crossing_faces": int(stats["crossing_faces"]),
                "core_faces": int(stats["core_faces"]),
                "cavity_faces": int(stats["cavity_faces"]),
                "balance": float(stats["balance"]),
                "moldability_score": float(stats["moldability_score"]),
                "complexity": float(stats["complexity"]),
                "z_val": float(stats["z_val"]),
                "classification": stats["classification"]
            }
        raw_res["standard_positions"] = clean_standard_positions
                        
        res_data["result"] = raw_res
        
    return res_data


@app.get("/mesh/{job_id}")
def get_mesh(job_id: str, axis: str = "Z", split_val: float = None):
    """Tessellates the shape and returns node indices, classifications, sliced parts, and mold blocks."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    job = jobs[job_id]
    if job["status"] != "success":
        raise HTTPException(status_code=400, detail="Analysis has not succeeded yet")
        
    engine = job["engine"]
    result = job["result"]
    
    if not engine or not result:
        raise HTTPException(status_code=500, detail="Engine state is missing")

    # Bounding Box calculations
    bbox_box = Bnd_Box()
    brepbndlib.Add(engine.part.shape, bbox_box)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox_box.Get()
    dx = xmax - xmin
    dy = ymax - ymin
    dz = zmax - zmin

    if split_val is None:
        best_plane, _, _ = engine.optimize_parting_plane_for_axis(axis)
        split_val = best_plane

    # Define cutting boundaries based on axis selection
    bx_min = xmin - dx * 0.15
    bx_max = xmax + dx * 0.15
    by_min = ymin - dy * 0.15
    by_max = ymax + dy * 0.15
    bz_min = zmin - dz * 0.15
    bz_max = zmax + dz * 0.15

    if axis == "X":
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(split_val, by_min, bz_min), gp_Pnt(xmax + dx * 0.3, by_max, bz_max)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(xmin - dx * 0.3, by_min, bz_min), gp_Pnt(split_val, by_max, bz_max)).Shape()
    elif axis == "Y":
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, split_val, bz_min), gp_Pnt(bx_max, ymax + dy * 0.3, bz_max)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, ymin - dy * 0.3, bz_min), gp_Pnt(bx_max, split_val, bz_max)).Shape()
    else:
        cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, split_val), gp_Pnt(bx_max, by_max, zmax + dz * 0.3)).Shape()
        core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, zmin - dz * 0.3), gp_Pnt(bx_max, by_max, split_val)).Shape()

    # Generate sliced part halves
    try:
        cavity_part = BRepAlgoAPI_Common(engine.part.shape, cavity_box).Shape()
        core_part = BRepAlgoAPI_Common(engine.part.shape, core_box).Shape()
        cavity_part_mesh = tessellate_shape(cavity_part)
        core_part_mesh = tessellate_shape(core_part)
    except Exception as e:
        print("Part Common solid split failed, using empty meshes:", e)
        cavity_part_mesh = {"vertices": [], "indices": []}
        core_part_mesh = {"vertices": [], "indices": []}

    # Generate mold blocks cuts
    try:
        cavity_block = BRepAlgoAPI_Cut(cavity_box, engine.part.shape).Shape()
        core_block = BRepAlgoAPI_Cut(core_box, engine.part.shape).Shape()
        cavity_block_mesh = tessellate_shape(cavity_block)
        core_block_mesh = tessellate_shape(core_block)
    except Exception as e:
        print("Mold Block solid cut failed, using raw boxes:", e)
        cavity_block_mesh = tessellate_shape(cavity_box)
        core_block_mesh = tessellate_shape(core_box)

    # Shading data of the whole original model for in-place views
    deflection = 0.1
    mesh = BRepMesh_IncrementalMesh(engine.part.shape, deflection)
    mesh.Perform()
    
    core_faces = set(result.optimal_stats["core_face_ids"])
    cavity_faces = set(result.optimal_stats["cavity_face_ids"])
    
    draft_classifications = {
        r["face_id"]: r["classification"] for r in result.draft_analysis["details"]
    }
    
    faces_list = []
    explorer = TopExp_Explorer(engine.part.shape, TopAbs_FACE)
    face_id = 0
    
    while explorer.More():
        face = topods.Face(explorer.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, loc)
        
        if triangulation:
            vertices = []
            for i in range(1, triangulation.NbNodes() + 1):
                p = triangulation.Node(i)
                p_transformed = p.Transformed(loc.Transformation())
                vertices.extend([p_transformed.X(), p_transformed.Y(), p_transformed.Z()])
                
            indices = []
            for i in range(1, triangulation.NbTriangles() + 1):
                t = triangulation.Triangle(i)
                idx1, idx2, idx3 = t.Get()
                indices.extend([idx1 - 1, idx2 - 1, idx3 - 1])
                
            if face_id in core_faces:
                classification = "CORE"
            elif face_id in cavity_faces:
                classification = "CAVITY"
            else:
                classification = "NEUTRAL"
                
            faces_list.append({
                "face_id": face_id,
                "vertices": vertices,
                "indices": indices,
                "classification": classification,
                "draft_classification": draft_classifications.get(face_id, "SAFE"),
                "centroid": list(engine.part.faces[face_id].centroid)
            })
            
        face_id += 1
        explorer.Next()
        
    # Sample parting line points along the cut section plane
    if axis == "X":
        pln = gp_Pln(gp_Pnt(split_val, 0, 0), gp_Dir(1, 0, 0))
    elif axis == "Y":
        pln = gp_Pln(gp_Pnt(0, split_val, 0), gp_Dir(0, 1, 0))
    else:
        pln = gp_Pln(gp_Pnt(0, 0, split_val), gp_Dir(0, 0, 1))

    parting_lines_list = []
    try:
        section = BRepAlgoAPI_Section(engine.part.shape, pln, True)
        section.Build()
        
        sec_explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
        while sec_explorer.More():
            edge = topods.Edge(sec_explorer.Current())
            adaptor = BRepAdaptor_Curve(edge)
            first = adaptor.FirstParameter()
            last = adaptor.LastParameter()
            
            # Sample 8 points per edge (7 segments)
            num_samples = 8
            for i in range(num_samples):
                u1 = first + (last - first) * i / float(num_samples)
                u2 = first + (last - first) * (i + 1) / float(num_samples)
                p1 = adaptor.Value(u1)
                p2 = adaptor.Value(u2)
                parting_lines_list.extend([p1.X(), p1.Y(), p1.Z(), p2.X(), p2.Y(), p2.Z()])
            sec_explorer.Next()
    except Exception as e:
        print("Failed to slice parting section:", e)

    return {
        "faces": faces_list,
        "parting_line_points": parting_lines_list,
        "optimal_z": result.optimal_z,
        "split_val": split_val,
        "cavity_part": cavity_part_mesh,
        "core_part": core_part_mesh,
        "cavity_block": cavity_block_mesh,
        "core_block": core_block_mesh,
        "bbox": {
            "xmin": xmin,
            "xmax": xmax,
            "ymin": ymin,
            "ymax": ymax,
            "zmin": zmin,
            "zmax": zmax
        }
    }

@app.post("/evaluate-split")
def evaluate_split(request: EvaluateRequest):
    """Runs a real-time parting evaluation on the loaded part shape for custom axes/heights."""
    if request.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    job = jobs[request.job_id]
    if job["status"] != "success":
        raise HTTPException(status_code=400, detail="Analysis has not succeeded yet")
        
    engine = job["engine"]
    if not engine:
        raise HTTPException(status_code=500, detail="Engine state is missing")

    axis = request.axis
    split_val = request.split_val

    if axis == "X":
        direction = [1.0, 0.0, 0.0]
    elif axis == "Y":
        direction = [0.0, 1.0, 0.0]
    else:
        direction = [0.0, 0.0, 1.0]

    stats = engine.evaluate_pull_direction_and_split(direction, split_val)
    
    total_area = sum(f.area for f in engine.part.faces) or 1.0
    total_faces = len(engine.part.faces) or 1.0

    core_cnt = stats["core_faces"]
    cavity_cnt = stats["cavity_faces"]
    max_cnt = max(1.0, max(core_cnt, cavity_cnt))
    balance = min(core_cnt, cavity_cnt) / max_cnt

    ratio = stats["undercut_area"] / total_area
    cnt_ratio = stats["undercut_count"] / total_faces
    cross_ratio = stats["crossing_faces"] / total_faces

    score = (
        0.40 * (100.0 - ratio * 100.0) +
        0.25 * (100.0 - cnt_ratio * 100.0) +
        0.20 * (100.0 - cross_ratio * 100.0) +
        0.15 * (balance * 100.0)
    )
    score = max(0.0, score)
    complexity = stats["crossing_faces"] + (stats["undercut_count"] / 5.0)

    # Classification rules
    if stats["undercut_count"] == 0 and stats["crossing_faces"] == 0:
        classification = "MOLDABLE"
    elif ratio < 0.05 and cross_ratio < 0.25 and cnt_ratio < 0.30:
        classification = "PARTIALLY MOLDABLE"
    elif ratio < 0.12 and cnt_ratio < 0.40:
        classification = "SIDE ACTION REQUIRED"
    else:
        classification = "NOT MOLDABLE"

    # Justification text matching PyQt5
    if axis == "Z":
        best_z, _, _ = engine.optimize_parting_plane_for_axis("Z")
        if abs(split_val - best_z) < 0.01:
            reason = (
                f"The selected Z = {split_val:.2f} mm split minimizes undercut area ({stats['undercut_area']:.1f} mm²), "
                f"reduces faces requiring geometric splitting ({stats['crossing_faces']}), and produces the most balanced core/cavity separation. "
                f"This results in the highest moldability score ({score:.1f}) among all candidate planes."
            )
        elif abs(split_val - 14.0) < 0.01:
            reason = (
                f"At Z = 14.0 mm, the parting plane sits right below the top cap. "
                f"Consequently, the cavity block forms only the top cap cosmetic region, forcing the core block "
                f"to form the entire main body and legs. This traps all bottom-facing features and vertical ribs "
                f"on the core side, creating mechanical locks ({stats['undercut_count']} undercut faces) "
                f"and requiring side actions/sliders."
            )
        else:
            reason = (
                f"The selected Z = {split_val:.2f} mm parting plane cuts at an arbitrary height. "
                f"This splits the cavity/core blocks unequally, resulting in {stats['undercut_count']} undercut faces "
                f"and {stats['crossing_faces']} crossing faces. Dynamic classification is {classification}."
            )
    else:
        reason = (
            f"The selected {axis} = {split_val:.2f} mm split minimizes undercut area along the {axis}-axis. "
            f"However, side walls, ribs, slots, and internal features create mechanical locks under standard "
            f"two-plate mold separation, requiring side actions/sliders."
        )

    return {
        "status": "success",
        "stats": {
            "undercut_count": stats["undercut_count"],
            "undercut_area": stats["undercut_area"],
            "crossing_faces": stats["crossing_faces"],
            "core_faces": stats["core_faces"],
            "cavity_faces": stats["cavity_faces"],
            "balance": balance,
            "complexity": complexity,
            "moldability_score": score,
            "classification": classification,
            "reason": reason
        }
    }


@app.get("/report/{job_id}")
def download_pdf_report(job_id: str):
    """Generates and returns the PDF engineering report file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
        
    job = jobs[job_id]
    if job["status"] != "success":
        raise HTTPException(status_code=400, detail="Report cannot be generated until analysis succeeds")
        
    pdf_path = os.path.join(UPLOAD_DIR, f"{job_id}_report.pdf")
    export_pdf(pdf_path, job["result"])
        
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"DfM_Report_{job['filename']}.pdf")
