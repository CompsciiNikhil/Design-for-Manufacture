# Validation & Benchmarking Plan: DfM Intelligence Agent

This document defines the validation, benchmarking, and quality assurance framework for the DfM (Design for Manufacturing) Intelligence Agent. It challenges the correctness of every module, provides a detailed comparison against industry-standard CAD/CAE tools, and defines a step-by-step verification workflow for the Bosch Hackathon.

---

## 1. Algorithmic Validation & Theoretical Correctness

For every analytical module in the pipeline, we review its theoretical foundation, identify limitations, map out failure cases, document how high-end commercial CAD software (Siemens NX, SolidWorks, Moldflow) handles the same task, and define independent verification methods.

### 1.1. STEP File Parsing (`step_parser.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Uses OpenCascade's `STEPControl_Reader` to import the Boundary Representation (BRep) model and parses faces into surface data. It computes the mathematical centroid, area, and face-normal (at the centroid).
    *   *Assessment*: Mathematically correct for flat and single-curvature faces. However, representing a complex freeform face with a single normal evaluated at its centroid is a major geometric simplification.
*   **Limitations & Failure Cases**:
    *   *Normal Evaluation*: Evaluating the normal vector *only* at the centroid fails on highly curved, non-planar, or organic faces (e.g., a dome, a saddle surface, or a twisted rib). The normal at the centroid does not represent the normal distribution across the entire surface.
    *   *Periodic Surfaces*: On closed periodic surfaces (like a complete cylinder or sphere), the computed centroid lies in empty space inside the shape, and evaluating the face surface parameters at the centroid coordinate can yield mathematical errors or undefined behavior.
*   **Industrial CAD Approach**:
    *   Commercial CAD software does not use single-point approximations. They tessellate the boundary representation (BRep) into a dense triangular mesh (using adaptive deflection tolerances) and evaluate the normal, draft, and undercut condition at every mesh vertex or facet center.
*   **Independent Verification**:
    *   Export a simple flat plate, a cylinder, and a sphere. Run the parser and print the face normal and area. Compare the area against analytical formulas ($A_{\text{cylinder}} = 2\pi rh$, $A_{\text{sphere}} = 4\pi r^2$).

### 1.2. Topology Extraction (`topology.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Map-based shared-edge extraction using `TopExp.MapShapesAndAncestors` to build a face adjacency graph.
    *   *Assessment*: Theoretically sound. BRep topology guarantees that solid manifold parts share edges between adjacent faces.
*   **Limitations & Failure Cases**:
    *   *Non-Manifold Geometry*: If the STEP file contains non-manifold geometry (e.g., zero-thickness edges, self-intersecting faces, or open shells), the adjacency graph may report incorrect face neighbors or duplicate edges.
    *   *Tolerant Edges*: In low-quality STEP files with loose sewing tolerances, adjacent faces may not share a topological edge but instead have a geometric gap. The topology extractor will fail to recognize them as neighbors.
*   **Industrial CAD Approach**:
    *   Commercial systems use the native kernel's topological query APIs (Parasolid for NX/SolidWorks, ACIS for Catia/Creo) and run automatic geometry healing ("Sewing") to resolve gaps up to a specified tolerance (e.g., 0.01 mm) before building adjacency maps.
*   **Independent Verification**:
    *   Verify using Euler's formula for polyhedron topology or verify that every inner edge in a closed manifold solid has exactly two face ancestors.

### 1.3. Mold Direction Optimization (`mold_direction.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Fibonacci sphere sampling of $N$ directions, scoring each direction based on draft alignment, safe area, and undercut penalties.
    *   *Assessment*: Heuristic/discretized search. It finds a near-optimal direction within the sampled resolution, but it is not a closed-form global optimization.
*   **Limitations & Failure Cases**:
    *   *Discretization Error*: If the optimal demolding direction is highly sensitive (e.g., a complex part with matching draft angles), a sample size of $N=500$ may miss the absolute mathematical optimum by several degrees.
    *   *Symmetric Ambiguity*: In highly symmetric parts (e.g., a square box), the algorithm may output one of several equivalent directions based on minor numerical noise rather than engineering intent.
*   **Industrial CAD Approach**:
    *   Industrial tools use bounding box alignment, principal moments of inertia, and flat face normal clustering. They identify the axes with the highest density of surface normals and refine the selection using gradient descent.
*   **Independent Verification**:
    *   Rotate the same part in the STEP file by $30^\circ$, $45^\circ$, and $90^\circ$ and re-run. The optimizer should find the exact same relative mold direction vector (rotated by the corresponding transformation matrix).

### 1.4. Draft Analysis (`draft_analysis.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: $\theta_{\text{draft}} = 90^\circ - \arccos(\hat{\mathbf{n}} \cdot \hat{\mathbf{d}})$.
    *   *Assessment*: Mathematically correct for planar faces relative to a constant pull direction vector.
*   **Limitations & Failure Cases**:
    *   *Curved Faces*: For cylindrical, conical, or freeform faces, the draft angle varies continuously across the surface. A single value computed at the centroid is incorrect.
    *   *Flipped Normals*: If the STEP file has inconsistent face orientations (inward-pointing normals), the draft angle sign will flip, leading to false undercut classifications.
*   **Industrial CAD Approach**:
    *   Commercial tools use shader-based GPU rendering or dense vertex evaluation. They color each pixel or triangle of the mesh dynamically based on the local normal vector, allowing a single face to display a color gradient.
*   **Independent Verification**:
    *   Create a test block with draft angles of exactly $0.5^\circ$, $1.0^\circ$, $2.0^\circ$, and $3.0^\circ$. Verify that the computed values match the nominal CAD parameters to within $10^{-5}$ degrees.

### 1.5. Undercut Detection (`undercut_detector.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Face is classified as an undercut if $\hat{\mathbf{n}} \cdot \hat{\mathbf{d}} < 0$.
    *   *Assessment*: Partially correct. It identifies "shadowed" faces relative to the draw axis, but it does not account for line-of-sight occlusion by other features.
*   **Limitations & Failure Cases**:
    *   *Geometric Occlusion*: A face can have a positive normal alignment (draft angle $> 0$) but still be physically blocked by another part of the geometry (e.g., a snap-fit tab inside a pocket). This is a "blind undercut" that simple normal-based algorithms miss.
*   **Industrial CAD Approach**:
    *   Industrial systems use ray-casting or swept-volume projection. A face is an undercut if a ray cast from the face centroid along the pull direction intersects any other face of the solid.
*   **Independent Verification**:
    *   Analyze a part with an overhanging bracket (where the underside has normal $+Z$ but is blocked by the top plate). If the code labels the underside "SAFE", it is a false negative.

### 1.6. Core/Cavity Classification (`core_cavity.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Grouping faces by normal dot-product threshold: Cavity if $\hat{\mathbf{n}} \cdot \hat{\mathbf{d}} > \text{tol}$, Core if $\hat{\mathbf{n}} \cdot \hat{\mathbf{d}} < -\text{tol}$, Neutral otherwise.
    *   *Assessment*: An approximation. True core/cavity separation depends on the parting line, not just local normal direction.
*   **Limitations & Failure Cases**:
    *   *Deep Pockets*: A flat bottom face inside a deep pocket on the cavity side has a normal pointing in $+Z$ (classified as CAVITY), but it must be formed by a core-side steel projection (core insert).
*   **Industrial CAD Approach**:
    *   Commercial tools separate the core and cavity by creating a parting surface. Any face on one side of the parting surface is assigned to the cavity; faces on the other side are assigned to the core.
*   **Independent Verification**:
    *   Run classification on a simple cup. The inside bottom face (pointing $+Z$) should topologically group with the core, while the outer bottom face (pointing $-Z$) groups with the cavity.

### 1.7. Silhouette Detection (`silhouette_detector.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Identifies faces where the normal is perpendicular to the pull direction: $|\hat{\mathbf{n}} \cdot \hat{\mathbf{d}}| < \text{threshold}$.
    *   *Assessment*: Identifies "neutral" or vertical faces, but does not extract the mathematical silhouette *curve*.
*   **Limitations & Failure Cases**:
    *   *Steep Surfaces*: On a sphere, the silhouette is an infinitely thin curve (line of tangency). Our algorithm selects the entire face near the equator, which is geometrically coarse.
*   **Industrial CAD Approach**:
    *   Commercial systems calculate the silhouette curve by finding the locus of points on the BRep surface where $\mathbf{N}(u,v) \cdot \mathbf{D} = 0$ and generate a split curve.
*   **Independent Verification**:
    *   Run on a cylinder. The silhouette faces should be the vertical side walls.

### 1.8. Parting Loop Extractor (`parting_loop_extractor.py`)
*   **Theoretical Correctness**:
    *   *Mechanism*: Vertices of raw boundary edges are snapped using a spatial tolerance ($10^{-3}$ mm) and chained into loops.
    *   *Assessment*: Correct for clean geometry. However, vertex-snapping is highly sensitive to tolerance values.
*   **Limitations & Failure Cases**:
    *   *Branching & Valency*: At corners where three or more boundary candidate edges meet (e.g., step-downs or side actions), the algorithm can choose the wrong path or create open chains.
    *   *Tolerance Sensitivity*: If the gap between two disconnected edges is smaller than the tolerance, the algorithm will falsely connect them, creating a geometrically distorted loop.
*   **Industrial CAD Approach**:
    *   Commercial software uses topological edge traversal (half-edge data structures) rather than purely coordinate-based snapping, enforcing direction consistency and utilizing user-selected guiding curves to resolve branchings.
*   **Independent Verification**:
    *   Check if the extracted parting line is a single, closed, non-self-intersecting loop that divides the surface graph into two distinct components.

---

## 2. Commercial Software Benchmarking Reference

To establish industrial credibility, we define how our tool's outputs correspond to commercial CAD/CAE tools, including Siemens NX, SolidWorks, and Autodesk Moldflow.

| Agent Output | Siemens NX Equivalent | SolidWorks Equivalent | Autodesk Moldflow Equivalent | Engineering Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| **Optimal Direction** | NX Mold Wizard - Pull Direction | Mold Tools - Pull Direction | Moldflow Pull Direction recommendation | Angular deviation $< 0.1^\circ$ |
| **Draft Angles** | Draft Analysis (Color Map) | Draft Analysis tool | Draft Analysis plot | Angle value deviation $< 0.01^\circ$ |
| **Undercut Areas** | Undercut Area validation | Undercut Analysis | Undercut / Shadow area plot | Area deviation $< 0.1\%$ |
| **Core/Cavity Split** | Region Analysis (Core/Cavity) | Parting Line - Core/Cavity Split | Core/Cavity separation | Zero face classification mismatch |
| **Parting Line Wires** | Parting Line / Split Curve | Parting Line tool | Mold parting curve | Edge overlap $= 100\%$ |
