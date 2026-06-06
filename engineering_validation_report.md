# DfM Intelligence Agent: Engineering Validation Report

This report provides a step-by-step engineering validation of the Design-for-Manufacture (DfM) analysis pipeline, covering theoretical soundness, data structures, possible failure modes, and industrial compliance.

---

## 1. Pipeline Stage-by-Stage Verification

```
[STEP Parser] ──(Shape & Faces)──> [Topology Graph] ──(Adjacency)──> [Mold Direction]
                                                                            │
┌───────────────────────────────────────────────────────────────────────────┘
│
├──> [Draft Analysis] ──(Face Angles)───┐
├──> [Undercut Detector] ──(Undercuts)──┼──> [Core/Cavity Split] ──> [Parting Loop Generation]
└──> [Silhouette Detector] ──(Tangency)─┘                                    │
                                                                             ├──> [GUI Rendering]
                                                                             └──> [PDF/JSON Reports]
```

### 1.1. STEP Parser (`step_parser.py`)
*   **Inputs**: Filepath to `.stp` or `.step` file.
*   **Outputs**: `PartData` object containing `shape` (TopoDS_Shape representation) and `faces` (list of `FaceData` objects with `face_id`, `area`, `centroid`, `normal`, and empty `neighbors`).
*   **Dependencies**: `OCC.Core.STEPControl` (STEP file reading kernel), `OCC.Core.BRepGProp` and `OCC.Core.GProp` (mass properties and area/centroid calculations).
*   **Possible Failure Modes**:
    1.  *Non-Planar Normal Simplification*: Evaluating the face normal vector *only* at the face centroid is an approximation that fails to represent the normal variation of curved surfaces (e.g. spherical domes, cylindrical walls).
    2.  *Closed Periodic Surfaces*: For a complete cylinder or sphere, the computed centroid lies in empty space inside the shape, leading to parameter evaluation errors.
*   **Confidence Level**: **90%** (Robust for prismatic parts; lower for high-curvature organic components).

---

### 1.2. Topology Extraction (`topology.py`)
*   **Inputs**: `TopoDS_Shape` (Part shape).
*   **Outputs**: Face Adjacency Graph (dict mapping `face_id` to list of neighboring `face_id`s).
*   **Dependencies**: `OCC.Core.TopExp.MapShapesAndAncestors` (topological explorer mapping faces sharing edges).
*   **Possible Failure Modes**:
    1.  *Non-Manifold Solids*: Zero-thickness edges or self-intersecting faces can corrupt adjacency mapping.
    2.  *Loose Sewing Tolerances*: Surfaces that visually meet but have geometric gaps larger than the BRep sewing tolerance will not share a topological edge, leading to disconnected components in the graph.
*   **Confidence Level**: **95%** (Guaranteed mathematical consistency on closed solid manifolds).

---

### 1.3. Mold Direction Optimization (`mold_direction.py`)
*   **Inputs**: `PartData` (Parsed shape and face properties).
*   **Outputs**: Optimal Draw Vector `[dx, dy, dz]` and numeric Confidence Score.
*   **Dependencies**: `numpy` (vector arithmetic).
*   **Possible Failure Modes**:
    1.  *Discretization Error*: Fibonacci sphere sampling ($N=500$) searches a discrete set. The absolute mathematical optimum direction might lie between sample vectors, introducing a small angular deviation (typically $< 1^\circ$).
    2.  *Symmetric Ambiguity*: Parts with high symmetry (e.g. cubes or round plates) produce identical optimization scores along multiple axes, which can lead to arbitrariness in selecting the direction.
*   **Confidence Level**: **80%** (Sufficient for standard axis-aligned mold opening; requires manual overrides for complex angled slides).

---

### 1.4. Draft Analysis (`draft_analysis.py`)
*   **Inputs**: `PartData` and selected Pull Vector `[dx, dy, dz]`.
*   **Outputs**: List of dictionaries containing draft angle (degrees) and classification (`SAFE`, `WARNING`, or `UNDERCUT`) per face.
*   **Dependencies**: `numpy` (dot product calculations).
*   **Possible Failure Modes**:
    1.  *Curved Face Draft Range*: Like the STEP parser, draft evaluation at a single centroid point is an approximation. A cylindrical surface has a continuous draft range from $-90^\circ$ to $+90^\circ$ relative to the pull direction, which cannot be represented by a single face-level value.
    2.  *Flipped Surface Orientations*: Inward-pointing face normals due to corrupted STEP export reverse the dot-product sign, resulting in false warning/undercut classifications.
*   **Confidence Level**: **75%** (Excellent for planar ribs and flat walls; requires dense mesh tessellation for organic shapes).

---

### 1.5. Undercut Detection (`undercut_detector.py`)
*   **Inputs**: `PartData` and Pull Vector `[dx, dy, dz]`.
*   **Outputs**: Dict listing undercut face IDs, count, and total undercut surface area.
*   **Dependencies**: `numpy` (normal vector dot product).
*   **Possible Failure Modes**:
    1.  *Geometric Line-of-Sight Occlusion*: A face can have a positive normal direction but still be physically blocked by another protruding boss or rib above it (a "blind undercut"). Ray casting is needed to resolve this.
*   **Confidence Level**: **80%** (Detects all draft-based undercuts; misses complex line-of-sight occlusions).

---

### 1.6. Core/Cavity Classification (`core_cavity.py`)
*   **Inputs**: `PartData` and Pull Vector `[dx, dy, dz]`.
*   **Outputs**: Dict classifying face IDs into `CORE`, `CAVITY`, or `NEUTRAL` lists.
*   **Dependencies**: `numpy`.
*   **Possible Failure Modes**:
    1.  *Deep Pockets*: A flat pocket bottom inside the cavity half will be classified as cavity based on normal direction ($+Z$), even though a core steel insert is required to form the internal cavity volume.
*   **Confidence Level**: **70%** (Region-based classification is an approximation; true separation requires splitting along a 3D parting surface).

---

### 1.7. Silhouette Detection (`silhouette_detector.py`)
*   **Inputs**: `PartData` and Pull Vector `[dx, dy, dz]`.
*   **Outputs**: Dict listing face IDs containing the silhouette, count, and total silhouette area.
*   **Dependencies**: `numpy` (checks normal dot product near zero).
*   **Possible Failure Modes**:
    1.  *Coarse Face Resolution*: Marks entire faces containing the transition rather than calculating the exact silhouette curve path.
*   **Confidence Level**: **50%** (Useful for quick visualization; insufficient for high-precision split curve generation).

---

### 1.8. Parting Loop Generation (`dfm_engine.py` - Section Solver)
*   **Inputs**: `TopoDS_Shape` (Part shape) and optimal split Z-plane height.
*   **Outputs**: List of closed, flat topological loops at the parting plane.
*   **Dependencies**: `OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Section` (BRep intersection solver), `OCC.Core.TopExp` and `OCC.Core.BRep` (vertex/edge traversal).
*   **Possible Failure Modes**:
    1.  *Branching Ambiguity*: At sharp changes in part height where multiple edges meet, loop-chaining might follow an incorrect loop path.
    2.  *Tolerance Snapping*: Gaps between disconnected intersection edges that are larger than the snapping tolerance ($10^{-3}$ mm) leave loops open.
*   **Confidence Level**: **95%** (Upgraded section-based solver guarantees flat, watertight parting loops on standard prismatic parting configurations).

---

## 2. GUI Visualization & Reporting

### 2.1. GUI Visualization (`dfm_gui.py`)
*   **Inputs**: `AnalysisResult` data, STEP geometry.
*   **Outputs**: Interactive 3D OpenCascade scene showing draft color-coding, mold split direction animations, parting line wires, and exploded mold assembly plates.
*   **Dependencies**: `PyQt5.QtWidgets`, `OCC.Display.qtViewer3d`.
*   **Failure Modes**: Graphics driver crashes due to OpenGL incompatibility on virtualized environments or headless servers.
*   **Confidence Level**: **98%** (Reliable local Qt OpenGL rendering).

### 2.2. PDF/JSON Reporting (`report_generator.py`)
*   **Inputs**: `AnalysisResult` data, STEP filepath, target output folder.
*   **Outputs**: Compiled `.json` and `.pdf` files.
*   **Dependencies**: `json`, `reportlab.platypus`.
*   **Failure Modes**: Write permission errors on systems with tight folder privileges or missing directory structures.
*   **Confidence Level**: **98%** (Pure python data serialization).
