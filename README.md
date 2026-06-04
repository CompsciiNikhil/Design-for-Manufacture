# DFM Agent: Automated Moldability Analysis from STEP Files

## Overview

DFM Agent is an automated Design for Manufacturing (DfM) analysis system for injection molded plastic components.

The system ingests a CAD STEP file, extracts geometric and topological information, determines an optimal mold pull direction, performs manufacturability analysis, identifies undercuts, classifies core and cavity regions, detects potential parting lines, and visualizes the results in a 3D CAD viewer.

The goal is to reduce manual moldability inspection effort and provide engineers with rapid manufacturability feedback during the design stage.

---

## Current Features

### STEP File Parsing

* Reads CAD geometry from STEP files
* Extracts all faces from the model
* Computes:

  * Surface type
  * Surface area
  * Centroid
  * Face normal

Example:

```text
Faces extracted: 311
```

---

### Geometric Feature Extraction

For each face:

```python
FaceData(
    face_id,
    surface_type,
    area,
    centroid,
    normal,
    neighbors
)
```

Extracted properties:

* Face ID
* Surface Type
* Area
* Centroid
* Surface Normal
* Neighbor Information

---

### Topology Graph Generation

Builds a face adjacency graph using OpenCascade topology information.

```text
Face A
    ↔
Face B
```

Two faces are considered adjacent if they share a common CAD edge.

Output:

```python
graph[face_id] = [neighbor_faces]
```

---

### Mold Direction Optimization

A candidate search strategy evaluates multiple pull directions.

Current implementation:

* 500-direction search
* Fibonacci sphere sampling
* Area-weighted evaluation
* Undercut penalty integration

Output:

```text
Best Mold Direction
Optimization Score
```

Current result:

```text
Direction: [0, 0, 1]
```

---

### Draft Analysis

Computes draft angle for every face relative to the selected mold pull direction.

Output:

* Minimum Draft Angle
* Maximum Draft Angle
* Average Draft Angle

Current:

```text
Minimum Draft: -90°
Maximum Draft: 90°
Average Draft: -1.059°
```

---

### Undercut Detection

Identifies faces opposing the mold pull direction.

Outputs:

* Undercut Face Count
* Undercut Area

Current:

```text
Undercut Faces: 148
Undercut Area: 482.821
```

---

### Core / Cavity Classification

Faces are classified based on their relationship to the mold pull direction.

Classes:

* CORE
* CAVITY
* NEUTRAL

Current:

```text
Core Faces: 129
Cavity Faces: 92
Neutral Faces: 90
```

---

### Silhouette Detection

Identifies faces approximately perpendicular to the mold pull direction.

These faces often represent:

* Mold split candidates
* Parting regions
* Vertical manufacturing boundaries

Current:

```text
Silhouette Faces: 90
Silhouette Area: 2090.537
```

---

### Parting Line Detection (Version 1)

Topology-based detection.

Logic:

```text
CORE Face
touches
CAVITY Face
```

Result:

```text
Boundary Pairs: 136
```

---

### Parting Line Detection (Version 2)

Silhouette-based detection.

Logic:

```text
Silhouette Face
touches
Non-Silhouette Face
```

Result:

```text
Boundary Pairs: 308
```

Version 2 better represents real mold split regions and manufacturing boundaries.

---

### Shared CAD Edge Extraction

Extracts actual OpenCascade edges corresponding to detected parting boundaries.

Output:

```text
Shared CAD Edges
```

These edges are used for visualization and future continuous parting-line generation.

---

### 3D Visualization

Built using OpenCascade Viewer.

Visualized entities:

* CAD Model
* Silhouette Faces
* Parting Candidate Faces
* Shared Parting Edges

Current visualization:

* Red = Silhouette Faces
* Yellow = Parting Edges
* Brown = Original CAD Geometry

---

## Project Architecture

```text
STEP File
    ↓
STEP Parser
    ↓
Face Extraction
    ↓
Topology Graph
    ↓
Mold Direction Optimization
    ↓
Draft Analysis
    ↓
Undercut Detection
    ↓
Core/Cavity Classification
    ↓
Silhouette Detection
    ↓
Parting Line Detection
    ↓
Shared Edge Extraction
    ↓
3D Visualization
```

---

## Project Structure

```text
dfm_agent/
│
├── main.py
│
├── models.py
│
├── step_parser.py
│
├── topology.py
│
├── mold_direction.py
│
├── draft_analysis.py
│
├── undercut_detector.py
│
├── core_cavity.py
│
├── silhouette_detector.py
│
├── parting_line.py
│
├── parting_line_v2.py
│
├── edge_extractor.py
│
├── visualizer.py
│
└── Part1.stp
```

---

## Technologies Used

### CAD Kernel

* OpenCascade
* pythonOCC

### Numerical Computation

* NumPy

### Visualization

* OpenCascade Viewer
* PyVista (future support)

### Language

* Python 3.x

---

## Current Results

Test Model:

```text
Part1.stp
```

Results:

```text
Faces Extracted: 311

Core Faces: 129
Cavity Faces: 92
Neutral Faces: 90

Silhouette Faces: 90

Parting Line V1:
136 Boundary Pairs

Parting Line V2:
308 Boundary Pairs

Undercut Faces:
148

Mold Direction:
[0, 0, 1]
```

---

## Future Work

### Short Term

* Continuous parting-line generation
* Mold direction visualization arrow
* Core/Cavity color visualization
* JSON report export
* Automated DFM report generation

### Long Term

* AI-assisted DFM recommendations
* Automatic tooling split generation
* Multi-direction mold analysis
* Web dashboard
* Streamlit interface
* Bosch-grade manufacturability scoring
