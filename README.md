# AI-Driven Design for Manufacturability Analysis Platform for Injection-Molded Automotive Plastic Components

Automatically analyze STEP (.stp) CAD models to detect optimal mold opening direction, undercuts, draft angle violations, parting lines, and core/cavity classification — providing actionable manufacturability recommendations backed by computational geometry.

## 🎯 Problem Statement

Designing injection-molded plastic parts that are actually manufacturable requires deep expertise in mold design. Engineers must manually check:
- Can the part be pulled out of the mold without getting stuck? (Undercuts)
- Are the walls tapered enough for clean ejection? (Draft Angles)
- Where should the mold split? (Parting Line)
- Which mold half forms which surface? (Core vs. Cavity)

This tool automates the entire analysis pipeline, turning hours of expert review into seconds of computation.

## ✨ Features

| Feature | Status | Description |
| :--- | :--- | :--- |
| 📁 STEP File Parser | ✅ Done | Load and parse .stp/.step CAD files using OpenCascade |
| 🔺 Geometry Tessellation | ✅ Done | Convert B-Rep to triangle meshes with per-face properties |
| 🖥️ Interactive 3D Viewer | ✅ Done | Plotly-based WebGL viewer with zoom, pan, rotate |
| 🎨 Surface Type Analysis | ✅ Done | Classify faces (Plane, Cylinder, Cone, Sphere, Torus, B-Spline) |
| 📊 Model Statistics | ✅ Done | Face count, edge count, area, bounding box, distributions |
| 🧭 Mold Direction Analysis | 🔲 Phase 3 | Generate and rank candidate pull directions |
| 📏 Draft Angle Analysis | 🔲 Phase 4 | Calculate draft angles, color-coded heatmap |
| 🔍 Undercut Detection | 🔲 Phase 5 | Ray-casting and normal analysis |
| ✂️ Parting Line Generation | 🔲 Phase 7 | Graph-based continuous loop detection |
| 🎨 Core/Cavity Classification | 🔲 Phase 8 | Surface classification relative to mold direction |
| 🤖 DfM Recommendations | 🔲 Phase 9 | AI-generated engineering recommendations |
| 📄 PDF Report Export | 🔲 Phase 10 | Complete DfM report generation |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ installed on your system
- pip package manager

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/nischala755/Bosch_DFDM.git
cd Bosch_DFDM

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate sample STEP files for testing
python tests/generate_test_part.py

# 4. Launch the application
streamlit run app.py
```

The app opens at `http://localhost:8501`

### First Run
- Upload `samples/test_bracket.stp` via the sidebar
- Explore the interactive 3D model
- Toggle between **Surface Type**, **Face ID**, and **Uniform** coloring
- Enable wireframe edges and face normals
- Review the face data table and surface type distribution

### 🖱️ 3D Viewer Navigation Controls
When interacting with the 3D model canvas:
- **Rotate / Orbit**: Left-click and drag
- **Pan / Translate**: Middle-click (scroll wheel click) and drag, OR hold `Shift` + Left-click and drag
- **Zoom**: Scroll the mouse wheel, OR Right-click and drag

## 🏗️ Architecture

```text
STEP File (.stp/.step)
        │
        ▼
┌──────────────────┐
│   STEPParser     │  Reads STEP file → OpenCascade TopoDS_Shape
│   (step_parser)  │  Validates format, extracts topology counts
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ ShapeTessellator │  B-Rep → Triangle mesh (per-face)
│   (tessellator)  │  Extracts vertices, triangles, normals, areas
└────────┬─────────┘  Classifies surface types, computes centers
         │
         ▼
┌──────────────────┐
│ModelTessellation  │  Central data structure for ALL analyses
│   (geometry.py)  │  Faces, edges, bounding box, statistics
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ModelViewer      │  Plotly Mesh3d + Scatter3d visualization
│   (viewer.py)    │  Color modes, wireframe, normals, hover info
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Streamlit App   │  Professional dashboard with dark theme
│    (app.py)      │  Upload, view, analyze, export
└──────────────────┘
```

## 📁 Project Structure

```text
Bosch_DFDM/
│
├── app.py                          # Streamlit dashboard (entry point)
├── requirements.txt                # All dependencies (pip install)
├── environment.yml                 # Conda alternative (optional)
├── .gitignore
├── README.md
│
├── .streamlit/
│   └── config.toml                 # Dark theme configuration
│
├── src/                            # Core source code
│   ├── __init__.py
│   │
│   ├── models/                     # Data structures
│   │   ├── __init__.py
│   │   └── geometry.py             # FaceTessellation, ModelTessellation, SurfaceType
│   │
│   ├── cad/                        # CAD parsing engine
│   │   ├── __init__.py
│   │   ├── step_parser.py          # STEP file reader (OpenCascade)
│   │   └── tessellator.py          # B-Rep → triangle mesh conversion
│   │
│   └── visualization/              # 3D rendering
│       ├── __init__.py
│       └── viewer.py               # Plotly 3D viewer with multiple modes
│
├── tests/                          # Testing suite
│   ├── __init__.py
│   ├── generate_test_part.py       # Generate sample STEP files
│   └── test_step_parser.py         # Unit tests (pytest)
│
└── samples/                        # Sample STEP files (generated)
    └── README.md
```

## 🔧 Technology Stack

| Technology | Version | Purpose |
| :--- | :--- | :--- |
| Python | 3.11+ | Core language |
| CadQuery / OCP | 7.8.1 | OpenCascade Python bindings for STEP parsing & B-Rep analysis |
| Streamlit | 1.30+ | Web dashboard framework |
| Plotly | 5.18+ | Interactive 3D visualization (WebGL) |
| NumPy | 1.24+ | Numerical computation for geometry |
| SciPy | 1.11+ | Scientific computing (clustering, optimization) |
| NetworkX | 3.0+ | Graph algorithms (parting line detection) |
| pandas | 2.0+ | Structured data tables |

*All dependencies are pip-installable. No conda required. No cloud APIs. Everything runs locally.*

## 🧪 Testing

```bash
# Generate test STEP files first
python tests/generate_test_part.py

# Run unit tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

### Test Part: `test_bracket.stp`
A parametric bracket with 51 faces including:
- 11 planar faces (flat walls, top, bottom)
- 24 cylindrical faces (mounting holes)
- 12 spherical faces (fillet blends)
- 4 toroidal faces (rounded edges)

## 🗺️ Development Roadmap

| Phase | Module | What it Does | Status |
| :--- | :--- | :--- | :--- |
| 1 | STEP Viewer | Upload, parse, visualize STEP files | ✅ Complete |
| 2 | Geometry Extraction | Extract face normals, areas, centers, types | ✅ Complete (built into Phase 1) |
| 3 | Mold Direction | Generate candidate pull directions via PCA + clustering | 🔲 Next |
| 4 | Draft Analysis | Calculate draft angles, color-coded heatmap | 🔲 Planned |
| 5 | Undercut Detection | Normal analysis + ray casting for undercuts | 🔲 Planned |
| 6 | Direction Optimization | Score and select optimal mold opening direction | 🔲 Planned |
| 7 | Parting Line | Graph-based continuous loop generation | 🔲 Planned |
| 8 | Core/Cavity | Classify surfaces into core and cavity | 🔲 Planned |
| 9 | DfM Agent | AI-generated engineering recommendations | 🔲 Planned |
| 10 | Final Dashboard | Complete UI + PDF export | 🔲 Planned |

## ⚠️ Troubleshooting

| Issue | Solution |
| :--- | :--- |
| `ModuleNotFoundError: No module named 'OCP'` | Run `pip install cadquery` — this installs OCP (OpenCascade bindings) |
| `RuntimeError: OpenCascade failed to read STEP file` | Verify the file is a valid STEP format (not STL/IGES) |
| Streamlit shows blank page | Ensure you run from project root: `streamlit run app.py` |
| `UnicodeEncodeError` on Windows | Set console encoding: `chcp 65001` before running |
| Large file slow to load | Adjust tessellation quality in `ShapeTessellator(linear_deflection=0.5)` |
