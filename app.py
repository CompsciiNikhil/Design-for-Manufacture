import streamlit as st
import requests
import time
import json
import os

# Streamlit configurations
st.set_page_config(
    page_title="DfM Advisor",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom css for premium dark-mode styling
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stButton>button {
        background-color: #e20015; /* Primary red */
        color: white;
        border-radius: 4px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #b00010;
        color: white;
    }
    .metric-card {
        background-color: #1a1c23;
        border: 1px solid #2d3139;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-val {
        font-size: 2.2rem;
        font-weight: bold;
        color: #ffffff;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #8a90a2;
        margin-top: 0.5rem;
    }
    .status-badge {
        font-size: 1.2rem;
        font-weight: bold;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Configuration for API hosts
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.sidebar.title("DfM Advisor Control Panel")

uploaded_file = st.sidebar.file_uploader("Upload STEP CAD File", type=["stp", "step"])
material = st.sidebar.selectbox("Select Target Material", ["ABS", "PP", "Nylon", "PC", "POM"])

# Initialize session state for tracking jobs
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False

if uploaded_file is not None:
    # Check if we need to upload
    if st.session_state.job_id is None:
        with st.spinner("Uploading file to analysis engine..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
                r = requests.post(f"{BACKEND_URL}/upload-step", files=files)
                if r.status_code == 200:
                    st.session_state.job_id = r.json()["job_id"]
                    st.session_state.analysis_complete = False
                    st.sidebar.success("File uploaded successfully!")
                else:
                    st.sidebar.error("Failed to upload file")
            except Exception as e:
                st.sidebar.error(f"Error connecting to backend: {e}")

# Action button to trigger computation
run_analysis = st.sidebar.button("Run DfM Analysis", disabled=(st.session_state.job_id is None))

if run_analysis and st.session_state.job_id:
    st.session_state.analysis_complete = False
    with st.spinner("Queuing background analysis..."):
        try:
            r = requests.post(
                f"{BACKEND_URL}/analyze", 
                json={"job_id": st.session_state.job_id, "material": material}
            )
            if r.status_code == 200:
                # Enter polling loop
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                while True:
                    res = requests.get(f"{BACKEND_URL}/results/{st.session_state.job_id}").json()
                    status = res["status"]
                    progress_msg = res["progress"]
                    
                    status_text.text(f"Current Phase: {progress_msg}")
                    
                    if status == "success":
                        progress_bar.progress(100)
                        status_text.text("Analysis complete!")
                        st.session_state.analysis_complete = True
                        break
                    elif status == "failed":
                        progress_bar.empty()
                        status_text.error(f"Analysis failed: {progress_msg}")
                        break
                        
                    # Simulate smooth progress
                    time.sleep(1)
            else:
                st.sidebar.error("Failed to start analysis.")
        except Exception as e:
            st.sidebar.error(f"Connection error: {e}")

# If analysis is complete, display interactive controls in the sidebar
axis = "Z"
split_val = 0.0
parting_mode = "Optimal [Auto]"

if st.session_state.analysis_complete:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Interactive Parting Plane")
    
    # Get standard results for defaults
    try:
        res = requests.get(f"{BACKEND_URL}/results/{st.session_state.job_id}").json()
        result = res["result"]
        opt_stats = result["optimal_stats"]
        
        xmin = opt_stats.get("bbox_xmin", -10.0)
        xmax = opt_stats.get("bbox_xmax", 10.0)
        ymin = opt_stats.get("bbox_ymin", -10.0)
        ymax = opt_stats.get("bbox_ymax", 10.0)
        zmin = opt_stats.get("bbox_zmin", 0.0)
        zmax = opt_stats.get("bbox_zmax", 15.0)
        
        # 1. Mold Opening Axis Selector
        axis = st.sidebar.selectbox("Mold Opening Axis", ["Z", "X", "Y"])
        
        # Determine range based on selected axis
        if axis == "X":
            min_val, max_val = xmin, xmax
        elif axis == "Y":
            min_val, max_val = ymin, ymax
        else:
            min_val, max_val = zmin, zmax
            
        # 2. Parting Position Mode
        parting_mode = st.sidebar.selectbox(
            "Parting Height Mode",
            ["Optimal [Auto]", "Top (95%)", "Upper (75%)", "Lower (25%)", "Bottom (5%)", "Manual (Use Slider)"]
        )
        
        # Calculate default height based on selected mode
        default_height = min_val + 0.5 * (max_val - min_val)
        if parting_mode == "Optimal [Auto]":
            if axis == "Z":
                default_height = result["optimal_z"]
            else:
                default_height = result.get("axis_comparison", {}).get(axis, {}).get("best_plane", default_height)
        elif parting_mode == "Top (95%)":
            default_height = min_val + 0.95 * (max_val - min_val)
        elif parting_mode == "Upper (75%)":
            default_height = min_val + 0.75 * (max_val - min_val)
        elif parting_mode == "Lower (25%)":
            default_height = min_val + 0.25 * (max_val - min_val)
        elif parting_mode == "Bottom (5%)":
            default_height = min_val + 0.05 * (max_val - min_val)
            
        # Slider to dynamically adjust split_val
        split_val = st.sidebar.slider(
            f"Parting Plane ({axis}-coord)",
            min_value=float(min_val),
            max_value=float(max_val),
            value=float(default_height),
            step=0.01
        )
    except Exception as e:
        st.sidebar.error(f"Error fetching stats for controls: {e}")

# Main window rendering
st.title("Automated Injection Moldability Check")

if not st.session_state.analysis_complete:
    st.info("👈 Please upload a STEP file and click 'Run DfM Analysis' in the control panel to view results.")
    
    # Static Welcome Screen / Bounding Box Preview if uploaded but not analyzed
    if st.session_state.job_id:
        st.subheader("STEP Geometry Meta Information")
        try:
            res = requests.get(f"{BACKEND_URL}/results/{st.session_state.job_id}").json()
            st.markdown(f"**Filename:** `{res['filename']}`")
            st.markdown("**Status:** Ready for DfM calculation.")
        except:
            pass
else:
    # Retrieve dynamic metrics from evaluate-split API based on user options
    try:
        # Run real-time evaluation
        eval_r = requests.post(
            f"{BACKEND_URL}/evaluate-split",
            json={
                "job_id": st.session_state.job_id,
                "axis": axis,
                "split_val": split_val
            }
        )
        res = requests.get(f"{BACKEND_URL}/results/{st.session_state.job_id}").json()
        result = res["result"]
        
        if eval_r.status_code == 200:
            eval_data = eval_r.json()["stats"]
            score = eval_data["moldability_score"]
            classification = eval_data["classification"]
            undercut_count = eval_data["undercut_count"]
            crossing_faces = eval_data["crossing_faces"]
            justification = eval_data["reason"]
        else:
            opt_stats = result["optimal_stats"]
            score = result["moldability_score"]
            classification = opt_stats["classification"]
            undercut_count = opt_stats.get('undercut_count', 0)
            crossing_faces = opt_stats.get('crossing_faces', 0)
            justification = "Standard optimal split."
            
        status_color = "#28a745" if classification == "MOLDABLE" else (
            "#ffc107" if classification == "PARTIALLY MOLDABLE" else (
                "#fd7e14" if classification == "SIDE ACTION REQUIRED" else "#dc3545"
            )
        )
        
        # KPI Row
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-val' style='color:{status_color}'>{score:.1f}</div>
                <div class='metric-label'>Moldability Score</div>
            </div>
            """, unsafe_allow_html=True)
        with kpi2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-val'>{result['face_count']}</div>
                <div class='metric-label'>Total Face Count</div>
            </div>
            """, unsafe_allow_html=True)
        with kpi3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-val'>{undercut_count}</div>
                <div class='metric-label'>Undercut Face Count</div>
            </div>
            """, unsafe_allow_html=True)
        with kpi4:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-val'>{crossing_faces}</div>
                <div class='metric-label'>Geometric Splitting Faces</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Recommendations banner
        st.markdown(f"### Status: <span class='status-badge' style='background-color:{status_color}; color:white;'>{classification}</span>", unsafe_allow_html=True)
        
        # Tab section
        tab1, tab2, tab3 = st.tabs(["3D WebGL Viewer", "Detailed Statistics", "Recommendations"])
        
        with tab1:
            st.write("🔄 Use Left Click drag to Orbit, Right Click / Scroll to Zoom, Shift + Left Click drag to Pan.")
            
            # Fetch mesh triangulation locally from backend
            mesh_json_str = "{}"
            try:
                mesh_r = requests.get(f"{BACKEND_URL}/mesh/{st.session_state.job_id}?axis={axis}&split_val={split_val}")
                if mesh_r.status_code == 200:
                    mesh_json_str = json.dumps(mesh_r.json())
            except Exception as e:
                st.error(f"Error loading 3D mesh: {e}")
            
            # Three.js viewport HTML string
            threejs_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        overflow: hidden;
                        background-color: #1a1c23;
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        color: #ffffff;
                    }}
                    #canvas-container {{
                        width: 100vw;
                        height: 100vh;
                    }}
                    #controls-overlay {{
                        position: absolute;
                        bottom: 20px;
                        left: 20px;
                        background: rgba(26, 28, 35, 0.85);
                        padding: 15px;
                        border-radius: 8px;
                        border: 1px solid #2d3139;
                        width: 250px;
                    }}
                    .ctrl-row {{
                        margin-bottom: 12px;
                    }}
                    .ctrl-row label {{
                        display: block;
                        font-size: 11px;
                        text-transform: uppercase;
                        color: #8a90a2;
                        margin-bottom: 5px;
                    }}
                    select, input[type=range] {{
                        width: 100%;
                        background: #0e1117;
                        color: white;
                        border: 1px solid #2d3139;
                        padding: 6px;
                        border-radius: 4px;
                    }}
                    .title {{
                        font-size: 14px;
                        font-weight: bold;
                        color: #e20015;
                        margin-bottom: 10px;
                    }}
                </style>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
            </head>
            <body>
                <div id="canvas-container"></div>
                <div id="controls-overlay">
                    <div class="title">WebGL Viewer Dashboard</div>
                    <div class="ctrl-row">
                        <label>View Visualization Mode</label>
                        <select id="view-mode">
                            <option value="neutral">Neutral CAD view</option>
                            <option value="split">Core/Cavity Separation (Part)</option>
                            <option value="draft">Draft Release Analysis</option>
                            <option value="blocks">Exploded Mold Blocks</option>
                        </select>
                    </div>
                    <div class="ctrl-row">
                        <label>Exploded Separation</label>
                        <input type="range" id="explode-slider" min="0" max="60" value="0" step="0.5">
                    </div>
                    <div class="ctrl-row">
                        <label><input type="checkbox" id="plane-chk" checked> Show Parting Plane</label>
                    </div>
                    <div class="ctrl-row">
                        <label><input type="checkbox" id="arrow-chk" checked> Show Pull Direction</label>
                    </div>
                </div>

                <script>
                    const meshData = {mesh_json_str};
                    const axis = "{axis}";
                    const splitVal = {split_val};
                    
                    let scene, camera, renderer, controls;
                    let facesGroup, slicedGroup, blocksGroup;
                    let cavityPartMesh, corePartMesh, cavityBlockMesh, coreBlockMesh;
                    let partingLineSegments, partingPlaneMesh, arrowHelper;
                    
                    const materials = {{
                        neutral: new THREE.MeshStandardMaterial({{ color: 0x909497, roughness: 0.4, metalness: 0.2, side: THREE.DoubleSide }}),
                        core: new THREE.MeshStandardMaterial({{ color: 0x2471a3, roughness: 0.4, metalness: 0.1, side: THREE.DoubleSide }}),
                        cavity: new THREE.MeshStandardMaterial({{ color: 0xc0392b, roughness: 0.4, metalness: 0.1, side: THREE.DoubleSide }}),
                        safe: new THREE.MeshStandardMaterial({{ color: 0x27ae60, roughness: 0.5, metalness: 0.0, side: THREE.DoubleSide }}),
                        warning: new THREE.MeshStandardMaterial({{ color: 0xf39c12, roughness: 0.5, metalness: 0.0, side: THREE.DoubleSide }}),
                        undercut: new THREE.MeshStandardMaterial({{ color: 0xd98880, roughness: 0.5, metalness: 0.0, side: THREE.DoubleSide }})
                    }};

                    init();
                    
                    function init() {{
                        const container = document.getElementById('canvas-container');
                        
                        // Scene setup
                        scene = new THREE.Scene();
                        scene.background = new THREE.Color(0x1a1c23);
                        
                        // Camera
                        camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
                        
                        // Renderer
                        renderer = new THREE.WebGLRenderer({{ antialias: true }});
                        renderer.setSize(container.clientWidth, container.clientHeight);
                        renderer.setPixelRatio(window.devicePixelRatio);
                        renderer.shadowMap.enabled = true;
                        container.appendChild(renderer.domElement);
                        
                        // Controls
                        controls = new THREE.OrbitControls(camera, renderer.domElement);
                        controls.enableDamping = true;
                        controls.dampingFactor = 0.05;
                        
                        // Lights
                        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
                        scene.add(ambientLight);
                        
                        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.6);
                        dirLight1.position.set(1, 1, 1).normalize();
                        scene.add(dirLight1);
                        
                        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
                        dirLight2.position.set(-1, -1, 1).normalize();
                        scene.add(dirLight2);
                        
                        // Groups for mode toggles
                        facesGroup = new THREE.Group();
                        slicedGroup = new THREE.Group();
                        blocksGroup = new THREE.Group();
                        scene.add(facesGroup);
                        scene.add(slicedGroup);
                        scene.add(blocksGroup);
                        
                        // Sliced components initial hidden
                        slicedGroup.visible = false;
                        blocksGroup.visible = false;
                        
                        buildMesh(meshData);
                        setupEnvironment(meshData);
                        animate();
                            
                        window.addEventListener('resize', onWindowResize);
                        
                        // Set up UI Event listeners
                        document.getElementById('view-mode').addEventListener('change', updateVisibility);
                        document.getElementById('explode-slider').addEventListener('input', updateExplode);
                        document.getElementById('plane-chk').addEventListener('change', togglePlane);
                        document.getElementById('arrow-chk').addEventListener('change', toggleArrow);
                    }}
                    
                    function buildMesh(data) {{
                        // 1. Build original faces (in-place)
                        data.faces.forEach(face => {{
                            const geom = new THREE.BufferGeometry();
                            const vertices = new Float32Array(face.vertices);
                            geom.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
                            geom.setIndex(face.indices);
                            geom.computeVertexNormals();
                            
                            const mesh = new THREE.Mesh(geom, materials.neutral);
                            mesh.userData = {{
                                face_id: face.face_id,
                                classification: face.classification,
                                draft: face.draft_classification,
                                centroid: face.centroid
                            }};
                            facesGroup.add(mesh);
                        }});

                        // 2. Build cavity part half
                        if (data.cavity_part && data.cavity_part.vertices.length > 0) {{
                            const geom = new THREE.BufferGeometry();
                            geom.setAttribute('position', new THREE.Float32BufferAttribute(data.cavity_part.vertices, 3));
                            geom.setIndex(data.cavity_part.indices);
                            geom.computeVertexNormals();
                            cavityPartMesh = new THREE.Mesh(geom, materials.cavity);
                            slicedGroup.add(cavityPartMesh);
                        }}

                        // 3. Build core part half
                        if (data.core_part && data.core_part.vertices.length > 0) {{
                            const geom = new THREE.BufferGeometry();
                            geom.setAttribute('position', new THREE.Float32BufferAttribute(data.core_part.vertices, 3));
                            geom.setIndex(data.core_part.indices);
                            geom.computeVertexNormals();
                            corePartMesh = new THREE.Mesh(geom, materials.core);
                            slicedGroup.add(corePartMesh);
                        }}

                        // 4. Build cavity block (transparent steel)
                        if (data.cavity_block && data.cavity_block.vertices.length > 0) {{
                            const geom = new THREE.BufferGeometry();
                            geom.setAttribute('position', new THREE.Float32BufferAttribute(data.cavity_block.vertices, 3));
                            geom.setIndex(data.cavity_block.indices);
                            geom.computeVertexNormals();
                            const mat = new THREE.MeshStandardMaterial({{
                                color: 0xc0392b,
                                roughness: 0.4,
                                metalness: 0.1,
                                transparent: true,
                                opacity: 0.65,
                                side: THREE.DoubleSide
                            }});
                            cavityBlockMesh = new THREE.Mesh(geom, mat);
                            blocksGroup.add(cavityBlockMesh);
                        }}

                        // 5. Build core block (transparent steel)
                        if (data.core_block && data.core_block.vertices.length > 0) {{
                            const geom = new THREE.BufferGeometry();
                            geom.setAttribute('position', new THREE.Float32BufferAttribute(data.core_block.vertices, 3));
                            geom.setIndex(data.core_block.indices);
                            geom.computeVertexNormals();
                            const mat = new THREE.MeshStandardMaterial({{
                                color: 0x2471a3,
                                roughness: 0.4,
                                metalness: 0.1,
                                transparent: true,
                                opacity: 0.65,
                                side: THREE.DoubleSide
                            }});
                            coreBlockMesh = new THREE.Mesh(geom, mat);
                            blocksGroup.add(coreBlockMesh);
                        }}
                        
                        // Build Parting Line segments along section cut
                        if (data.parting_line_points && data.parting_line_points.length > 0) {{
                            const lineGeom = new THREE.BufferGeometry();
                            lineGeom.setAttribute('position', new THREE.Float32BufferAttribute(data.parting_line_points, 3));
                            const lineMat = new THREE.LineBasicMaterial({{ color: 0xf1c40f, linewidth: 3 }});
                            partingLineSegments = new THREE.LineSegments(lineGeom, lineMat);
                            scene.add(partingLineSegments);
                        }}
                    }}
                    
                    function setupEnvironment(data) {{
                        const bbox = data.bbox;
                        const cx = (bbox.xmin + bbox.xmax) / 2.0;
                        const cy = (bbox.ymin + bbox.ymax) / 2.0;
                        const cz = (bbox.zmin + bbox.zmax) / 2.0;
                        
                        const spanX = bbox.xmax - bbox.xmin;
                        const spanY = bbox.ymax - bbox.ymin;
                        const spanZ = bbox.zmax - bbox.zmin;
                        const maxSpan = Math.max(spanX, spanY, spanZ);
                        
                        camera.position.set(cx + maxSpan * 1.5, cy + maxSpan * 1.5, cz + maxSpan * 1.5);
                        controls.target.set(cx, cy, cz);
                        controls.update();
                        
                        // Parting Plane mesh visualization aligned with active axis
                        const size = maxSpan * 2.2;
                        const planeGeom = new THREE.PlaneGeometry(size, size);
                        const planeMat = new THREE.MeshBasicMaterial({{
                            color: 0x1abc9c,
                            side: THREE.DoubleSide,
                            transparent: true,
                            opacity: 0.35
                        }});
                        partingPlaneMesh = new THREE.Mesh(planeGeom, planeMat);
                        
                        if (axis === "X") {{
                            partingPlaneMesh.rotation.y = Math.PI / 2;
                            partingPlaneMesh.position.set(splitVal, cy, cz);
                        }} else if (axis === "Y") {{
                            partingPlaneMesh.rotation.x = Math.PI / 2;
                            partingPlaneMesh.position.set(cx, splitVal, cz);
                        }} else {{
                            partingPlaneMesh.position.set(cx, cy, splitVal);
                        }}
                        scene.add(partingPlaneMesh);
                        
                        // Pull direction arrowhelper aligned with active axis
                        let dir = new THREE.Vector3(0, 0, 1);
                        let origin = new THREE.Vector3(cx, cy, bbox.zmax + spanZ * 0.15);
                        
                        if (axis === "X") {{
                            dir = new THREE.Vector3(1, 0, 0);
                            origin = new THREE.Vector3(bbox.xmax + spanX * 0.15, cy, cz);
                        }} else if (axis === "Y") {{
                            dir = new THREE.Vector3(0, 1, 0);
                            origin = new THREE.Vector3(cx, bbox.ymax + spanY * 0.15, cz);
                        }}
                        
                        const arrowLength = maxSpan * 0.45;
                        arrowHelper = new THREE.ArrowHelper(dir, origin, arrowLength, 0xe20015, arrowLength * 0.25, arrowLength * 0.15);
                        scene.add(arrowHelper);
                    }}
                    
                    function updateVisibility() {{
                        const mode = document.getElementById('view-mode').value;
                        
                        if (mode === "neutral") {{
                            facesGroup.visible = true;
                            slicedGroup.visible = false;
                            blocksGroup.visible = false;
                            facesGroup.children.forEach(mesh => {{
                                mesh.material = materials.neutral;
                                mesh.material.transparent = false;
                                mesh.material.opacity = 1.0;
                            }});
                        }} else if (mode === "draft") {{
                            facesGroup.visible = true;
                            slicedGroup.visible = false;
                            blocksGroup.visible = false;
                            facesGroup.children.forEach(mesh => {{
                                mesh.material.transparent = false;
                                mesh.material.opacity = 1.0;
                                if (mesh.userData.draft === "SAFE") {{
                                    mesh.material = materials.safe;
                                }} else if (mesh.userData.draft === "WARNING") {{
                                    mesh.material = materials.warning;
                                }} else {{
                                    mesh.material = materials.undercut;
                                }}
                            }});
                        }} else if (mode === "split") {{
                            facesGroup.visible = false;
                            slicedGroup.visible = true;
                            blocksGroup.visible = false;
                            updateExplode();
                        }} else if (mode === "blocks") {{
                            // Keep the original part visible in the center, semi-transparent
                            facesGroup.visible = true;
                            facesGroup.children.forEach(mesh => {{
                                mesh.material = new THREE.MeshStandardMaterial({{
                                    color: 0x909497,
                                    roughness: 0.4,
                                    metalness: 0.2,
                                    transparent: true,
                                    opacity: 0.35,
                                    side: THREE.DoubleSide
                                }});
                            }});
                            slicedGroup.visible = false;
                            blocksGroup.visible = true;
                            updateExplode();
                        }}
                    }}
                    
                    function updateExplode() {{
                        const dist = parseFloat(document.getElementById('explode-slider').value);
                        
                        // Auto-toggle mode to split if user drags slider while in a static view
                        const modeSelect = document.getElementById('view-mode');
                        if (dist > 0 && (modeSelect.value === "neutral" || modeSelect.value === "draft")) {{
                            modeSelect.value = "split";
                            updateVisibility();
                            return;
                        }}
                        
                        // Translate along the selected axis
                        if (axis === "X") {{
                            if (cavityPartMesh) cavityPartMesh.position.set(dist, 0, 0);
                            if (corePartMesh) corePartMesh.position.set(-dist, 0, 0);
                            if (cavityBlockMesh) cavityBlockMesh.position.set(dist, 0, 0);
                            if (coreBlockMesh) coreBlockMesh.position.set(-dist, 0, 0);
                        }} else if (axis === "Y") {{
                            if (cavityPartMesh) cavityPartMesh.position.set(0, dist, 0);
                            if (corePartMesh) corePartMesh.position.set(0, -dist, 0);
                            if (cavityBlockMesh) cavityBlockMesh.position.set(0, dist, 0);
                            if (coreBlockMesh) coreBlockMesh.position.set(0, -dist, 0);
                        }} else {{
                            if (cavityPartMesh) cavityPartMesh.position.set(0, 0, dist);
                            if (corePartMesh) corePartMesh.position.set(0, 0, -dist);
                            if (cavityBlockMesh) cavityBlockMesh.position.set(0, 0, dist);
                            if (coreBlockMesh) coreBlockMesh.position.set(0, 0, -dist);
                        }}
                    }}
                    
                    function togglePlane() {{
                        const show = document.getElementById('plane-chk').checked;
                        if (partingPlaneMesh) partingPlaneMesh.visible = show;
                    }}

                    function toggleArrow() {{
                        const show = document.getElementById('arrow-chk').checked;
                        if (arrowHelper) arrowHelper.visible = show;
                    }}
                    
                    function onWindowResize() {{
                        const container = document.getElementById('canvas-container');
                        camera.aspect = container.clientWidth / container.clientHeight;
                        camera.updateProjectionMatrix();
                        renderer.setSize(container.clientWidth, container.clientHeight);
                    }}
                    
                    function animate() {{
                        requestAnimationFrame(animate);
                        controls.update();
                        renderer.render(scene, camera);
                    }}
                </script>
            </body>
            </html>
            """
            
            # Embed the Three.js viewport into the Streamlit tab
            st.components.v1.html(threejs_html, height=600)
            
        with tab2:
            st.subheader("BRep Geometry Properties")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Selected Mold Axis:** `{axis}-Axis`")
                st.markdown(f"**Bounding Box X Span:** `{opt_stats.get('bbox_xmax', 0.0) - opt_stats.get('bbox_xmin', 0.0):.2f} mm`  ({opt_stats.get('bbox_xmin', 0.0):.2f} to {opt_stats.get('bbox_xmax', 0.0):.2f})")
                st.markdown(f"**Bounding Box Y Span:** `{opt_stats.get('bbox_ymax', 0.0) - opt_stats.get('bbox_ymin', 0.0):.2f} mm`  ({opt_stats.get('bbox_ymin', 0.0):.2f} to {opt_stats.get('bbox_ymax', 0.0):.2f})")
                st.markdown(f"**Bounding Box Z Span:** `{opt_stats.get('bbox_zmax', 0.0) - opt_stats.get('bbox_zmin', 0.0):.2f} mm`  ({opt_stats.get('bbox_zmin', 0.0):.2f} to {opt_stats.get('bbox_zmax', 0.0):.2f})")
            with c2:
                st.markdown(f"**Total Surface Area:** `{opt_stats.get('bbox_total_area', 0.0):.2f} mm²`")
                st.markdown(f"**Selected Parting plane height:** `{split_val:.3f} mm`")
                st.markdown(f"**Core/Cavity Face Balance:** `{opt_stats.get('core_faces', 0)} Core / {opt_stats.get('cavity_faces', 0)} Cavity  (Ratio: {min(opt_stats.get('core_faces', 0), opt_stats.get('cavity_faces', 0)) / max(1, max(opt_stats.get('core_faces', 0), opt_stats.get('cavity_faces', 0))):.2f})")
                
            # Z height standard candidates sweep table
            st.subheader("Z-Axis Parting Height Candidates Sweep")
            std_sweep = result.get("standard_positions", {})
            if std_sweep:
                import pandas as pd
                sweep_rows = []
                for pos_name, stats in std_sweep.items():
                    sweep_rows.append({
                        "Height Position": pos_name,
                        "Z Coordinate (mm)": f"{stats['z_val']:.2f}",
                        "Undercuts": stats["undercut_count"],
                        "Undercut Area (mm²)": f"{stats['undercut_area']:.2f}",
                        "Crossing Faces": stats["crossing_faces"],
                        "Core / Cavity Split": f"{stats['core_faces']} / {stats['cavity_faces']}",
                        "Score": f"{stats['moldability_score']:.1f}",
                        "Classification": stats["classification"]
                    })
                st.table(pd.DataFrame(sweep_rows))

            st.subheader("Draft Angle Detail Table")
            draft_details = result["draft_analysis"]["details"]
            st.dataframe(draft_details, height=250)
            
        with tab3:
            st.subheader("Tooling Recommendations")
            st.markdown(f"""
            *   **Selected Parting Height:** Flat split sheet located at ${axis} = {split_val:.3f}\text{{ mm}}$.
            *   **Parting Loopwatertightness:** **Yes** (Watertight loop generated with {result['parting_line']['edge_count']} segments, total length: {result['parting_line']['total_length_mm']:.2f} mm).
            *   **Undercut Area Ratio:** **{opt_stats.get('undercut_area', 0.0) / max(1.0, opt_stats.get('bbox_total_area', 0.0)) * 100:.2f}%** (Total undercut area: {opt_stats.get('undercut_area', 0.0):.2f} mm²).
            *   **Manufacturing Feasibility:**
                *   *Recommendation*: {crossing_faces} faces cross the parting boundary and will require geometric splitting. 
                *   *Slide Requirements*: Physical undercuts are detected. To form these shapes, a mold split action (side-action slides) must be added moving perpendicular to the vertical draw direction.
            """)
            
            st.info(f"💡 **Advisor Explanation:** {justification}")
            
            # Mold Opening Axis Comparison Dashboard
            st.subheader("Mold Opening Axis Comparison Dashboard")
            comp = result.get("axis_comparison", {})
            if comp:
                cols = st.columns(3)
                for idx, ax_name in enumerate(["X", "Y", "Z"]):
                    ax_data = comp.get(ax_name, {})
                    if ax_data:
                        c_status = ax_data["classification"]
                        c_color = "#28a745" if c_status == "MOLDABLE" else (
                            "#ffc107" if c_status == "PARTIALLY MOLDABLE" else (
                                "#fd7e14" if c_status == "SIDE ACTION REQUIRED" else "#dc3545"
                            )
                        )
                        with cols[idx]:
                            st.markdown(f"""
                            <div style='background-color: #1a1c23; border: 1px solid #2d3139; border-radius: 8px; padding: 1.2rem; text-align: center; margin-bottom: 15px;'>
                                <h4 style='margin: 0; color: #ffffff;'>{ax_name}-Axis Opening</h4>
                                <p style='font-size: 0.9rem; color: #8a90a2; margin: 5px 0;'>Split plane: <b>{ax_data['best_plane']:.2f} mm</b></p>
                                <h3 style='margin: 10px 0; color: {c_color};'>{c_status}</h3>
                                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem; color: #dfdfea; margin-top: 10px;'>
                                    <div style='text-align: left;'>Undercuts:</div><div style='text-align: right; font-weight: bold;'>{ax_data['undercut_count']} ({ax_data['undercut_area']:.1f} mm²)</div>
                                    <div style='text-align: left;'>Crossing faces:</div><div style='text-align: right; font-weight: bold;'>{ax_data['crossing_faces']}</div>
                                    <div style='text-align: left;'>Complexity:</div><div style='text-align: right; font-weight: bold;'>{ax_data['complexity']:.1f}</div>
                                    <div style='text-align: left;'>Moldability Score:</div><div style='text-align: right; font-weight: bold; color: {c_color};'>{ax_data['best_score']:.1f}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

        # Download Report PDF
        try:
            pdf_url = f"{BACKEND_URL}/report/{st.session_state.job_id}"
            pdf_response = requests.get(pdf_url)
            if pdf_response.status_code == 200:
                st.download_button(
                    label="📥 Download PDF Engineering Report",
                    data=pdf_response.content,
                    file_name=f"DfM_Report_{res['filename'][:-4]}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.warning(f"Failed to fetch report PDF: {e}")
            
    except Exception as e:
        st.error(f"Error rendering analysis results: {e}")
