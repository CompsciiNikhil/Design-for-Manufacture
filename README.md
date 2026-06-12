# DfM Intelligence Agent
### Automated Design for Manufacturability Analysis Platform for Injection-Molded Plastic Components

An advanced engineering platform that automatically analyzes STEP (`.stp`/`.step`) CAD models to detect optimal mold opening directions, evaluate draft angle compliance, locate undercut faces, trace parting lines, and simulate core/cavity splits. Includes a standalone **PyQt5 OpenGL Desktop Application** and a **FastAPI backend + Streamlit Web Application**.

---

## 🎯 Problem Statement

Designing injection-molded plastic parts requires deep expertise in mold tooling design. Wall tapers and split configurations must be carefully aligned with mold-pull directions to prevent ejector locks or part damage. Manual compliance reviews are tedious and prone to oversight. 

This platform automates the entire geometry analysis pipeline, turning hours of expert manual CAD review into seconds of local deterministic computations.

---

## ✨ Features

| Feature | Status | Description |
| :--- | :--- | :--- |
| 📁 **STEP CAD Parser** | ✅ Done | Parses `.stp` / `.step` B-Rep files locally using OpenCascade bindings. |
| 🔺 **Tessellation & Bounding Box** | ✅ Done | Converts B-Rep faces to triangular mesh surfaces and calculates exact physical bounding box dimensions. |
| 🧭 **Mold Axis Optimization** | ✅ Done | Sweeps candidate pull directions across X, Y, and Z axes, scoring them based on undercut and draft conditions. |
| 📏 **Draft Angle Heatmap** | ✅ Done | Computes face draft angles relative to the pull vector and highlights compliant, warning, and vertical faces. |
| 🔍 **Undercut Detection** | ✅ Done | Detects undercut regions, calculates undercut surface areas, and flags necessary side actions. |
| ✂️ **Parting Line Detection** | ✅ Done | Traces watertight parting loops at the optimal split height using topological edge connectivity. |
| 🗜️ **Core & Cavity Boolean Split** | ✅ Done | Dynamically splits the part volume into discrete Core and Cavity blocks using solid Boolean cuts. |
| ↕️ **Exploded Separation Slider** | ✅ Done | Provides a 3D animation slider to separate and review the core and cavity block halves in real time. |
| 📄 **PDF & JSON Reports** | ✅ Done | Generates high-fidelity PDF engineering reports and exports raw metadata to JSON. |
| 🖥️ **PyQt5 Standalone GUI** | ✅ Done | Dark-themed desktop engineering workstation with camera presets, progress dialogs, and coordinate triedrons. |
| 🌐 **FastAPI & Streamlit Web App** | ✅ Done | Client-server web app allowing remote uploads, Plotly-based WebGL rendering, and parameterized analysis sweeps. |

---

## 🚀 Quick Start

### Prerequisites
* Python 3.9 - 3.11
* A python environment with `pythonocc-core` installed (conda-forge is recommended).

### Environment Setup
Create a conda environment and install the required dependencies:
```bash
# 1. Create environment and install packages
conda create -n dfm -c conda-forge python=3.10 pythonocc-core pyqt pyqt5 fastapi uvicorn streamlit plotly pandas requests reportlab numpy -y

# 2. Activate environment
conda activate dfm
```

---

### Running the Applications

#### Option A: Standalone PyQt5 Desktop App (Recommended)
Launch the dark-themed desktop CAD analysis platform directly:
```bash
python dfm_gui.py
```
*Features drag-and-drop loading, built-in sample loaders, viewport camera presets, and real-time computation status logs.*

#### Option B: FastAPI Backend + Streamlit Web App
To run the web version of the application:
1. Start the **FastAPI REST Server** in your terminal:
   ```bash
   python -m uvicorn main_web:app --host 127.0.0.1 --port 8000
   ```
2. Start the **Streamlit Web Dashboard** in a second terminal:
   ```bash
   streamlit run app.py
   ```
3. Open your browser and navigate to `http://localhost:8501`.

---

## 🖱️ 3D Viewer Navigation Controls

### PyQt5 OpenGL Desktop Viewport
* **Rotate / Orbit**: Hold **Left-Click** and drag.
* **Pan / Translate**: Hold **Middle-Click** (scroll wheel button) and drag, OR hold **Shift + Left-Click** and drag.
* **Zoom**: Scroll the **Mouse Wheel**, OR hold **Right-Click** and drag.
* **Fit View / Reset**: Click **Fit View** in the viewport presets toolbar.

### Streamlit Plotly Web Viewer
* **Rotate / Orbit**: Hold **Left-Click** and drag.
* **Pan / Translate**: Hold **Shift + Left-Click** and drag.
* **Zoom**: Scroll the **Mouse Wheel**, OR pinch/zoom on touch pads.

---

## 🏗️ Architecture

```text
STEP File (.stp/.step)
         │
         ▼
┌──────────────────────────────────────────────┐
│        DFMEngine (dfm_engine.py)             │
│  - OpenCascade-powered STEP file parser      │
│  - B-Rep face tessellation & normal analysis │
│  - Pull direction ranking & draft metrics    │
│  - Parting line loop & core/cavity cuts      │
└──────┬────────────────────────────────┬──────┘
       │                                │
       ▼ (Direct Import)                ▼ (JSON / REST API)
┌──────────────────────────┐    ┌──────────────────────────────────┐
│ Standalone Desktop GUI   │    │      FastAPI App (main_web.py)   │
│      (dfm_gui.py)        │    │  Exposes REST endpoints for mesh │
│  - PyQt5-based GUI       │    │  data & parting line algorithms  │
│  - OCC OpenGL Viewport   │    └────────────────┬─────────────────┘
│  - Direct camera presets │                     │
│  - Exploded split slider │                     ▼ (HTTP Requests)
└──────────────────────────┘    ┌──────────────────────────────────┐
                                │      Streamlit Web Dashboard     │
                                │            (app.py)              │
                                │  - Client dashboard UI           │
                                │  - WebGL Plotly 3D Viewer        │
                                │  - Separation slider & settings  │
                                └──────────────────────────────────┘
```

---

## 📁 Project Structure

```text
Design-for-Manufacture/
│
├── dfm_engine.py             # Core geometry, undercut, parting line & split algorithms
├── dfm_gui.py                # Standalone PyQt5 desktop application entry point
├── main_web.py               # FastAPI backend exposing REST endpoints
├── app.py                    # Streamlit web frontend client application
├── report_generator.py       # Exporter for PDF engineering reports & JSON datasets
├── requirements.txt          # Python pip dependencies list
│
├── examples/                 # Built-in sample STEP files for testing
│   ├── Part1.stp             # Complex injection-molded automotive part
│   ├── cube.stp              # Basic test cube
│   ├── cylinder.stp          # Cylindrical test part
│   └── bracket.stp           # Bracket test part
│
└── tests/                    # Computational & GUI test suite
    ├── generate_test_shapes.py # Script to output example geometries
    ├── test_axis_opening_opt.py# Verifies pull axis scoring calculations
    ├── test_flow_sensor.py    # Tests parting line extraction and Boolean splits
    ├── test_gui_init.py       # GUI lifecycle, setup, and tab-switching checks
    └── test_optimal_parting.py# Validates parting plane height sweep searches
```

---

## 🔧 Technology Stack

| Technology | Version | Purpose |
| :--- | :--- | :--- |
| **Python** | 3.9 - 3.11 | Core development language |
| **pythonocc-core** | 7.7.0+ | OpenCascade Python bindings for CAD B-Rep parsing & solid operations |
| **PyQt5** | 5.15+ | Standing window desktop widgets and viewport layout management |
| **FastAPI / Uvicorn** | 0.95+ | Backend REST framework powering the Streamlit web client |
| **Streamlit** | 1.25+ | Client-side web dashboard interface |
| **Plotly** | 5.15+ | WebGL mesh renderer for the browser client |
| **ReportLab** | 4.0+ | Generates structural high-fidelity PDF engineering reports |
| **NumPy** | 1.22+ | Multidimensional vector arithmetic for spatial points and mesh faces |

---

## 🧪 Testing

The testing suite contains unit and integration tests covering calculations and layout lifecycles.

```bash
# 1. Generate testing shapes
python tests/generate_test_shapes.py

# 2. Run core parting line and Boolean splits tests
python tests/test_flow_sensor.py

# 3. Run axis opening direction optimization checks
python tests/test_axis_opening_opt.py

# 4. Run parting plane height optimization sweeps
python tests/test_optimal_parting.py

# 5. Run GUI startup & tab lifecycle integration test
python tests/test_gui_init.py
```

---

## ⚠️ Troubleshooting

| Issue | Solution |
| :--- | :--- |
| `ImportError: DLL load failed...` | Ensure your Conda environment is active (`conda activate dfm`). PythonOCC relies on native C++ DLL paths loaded during conda environment activation. |
| Viewport is blank / coordinates in bottom-left | Ensure you run the latest version of `dfm_gui.py` where canvas parenting is locked to the layout container rather than the top-level window. |
| `ModuleNotFoundError: No module named 'OCC'` | Install OpenCascade conda-forge package: `conda install -c conda-forge pythonocc-core` |
| Plotly viewer displays blank in Streamlit | Ensure the FastAPI server is running on `127.0.0.1:8000` before triggering the analysis on the sidebar. |
