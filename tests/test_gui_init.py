import sys
import os

# Set project root in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set PyQt5 backend
import OCC.Display.backend
OCC.Display.backend.load_backend('pyqt5')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# Initialize Qt App
app = QApplication.instance() or QApplication(sys.argv)

from dfm_gui import DFMMainWindow

# Construct MainWindow
window = DFMMainWindow()
window.show()
window.init_viewer()

# Verify initial startup state
print("=== VERIFYING STARTUP STATE ===")
print(f"Initial status bar message: '{window.statusBar().currentMessage()}'")
print(f"Run button enabled: {window.run_btn.isEnabled()}")
print(f"Engine is None: {window.engine is None}")

# Load Part1.stp programmatically (preview/load phase only)
part_path = os.path.join(project_root, "examples", "Part1.stp")
if os.path.exists(part_path):
    print("\n=== SELECTING STEP FILE ===")
    window.load_file(part_path)
    print("File loaded/previewed.")
    print(f"Status bar message after load: '{window.statusBar().currentMessage()}'")
    print(f"Run button enabled: {window.run_btn.isEnabled()}")
    print(f"Analysis result is None: {window.analysis_result is None}")
    print(f"CAD Model Info Face Count: '{window.info_val_faces.text()}'")
    print(f"CAD Model Info X Span: '{window.info_val_bbox_x.text()}'")
    
    # Explicitly run analysis
    print("\n=== RUNNING ANALYSIS ===")
    window.on_run_analysis()
    print("Analysis run completed explicitly!")
    
    # Check that analysis result is correct
    print(f"Analysis result is not None: {window.analysis_result is not None}")
    print(f"Optimal Z split: {window.analysis_result.optimal_z:.4f} mm")
    print(f"Moldability score: {window.analysis_result.moldability_score:.2f}")
    
    # Test switching tabs
    print("\n=== TESTING TAB SWITCHING ===")
    for tab_idx in range(6):
        window.tabs.setCurrentIndex(tab_idx)
        print(f"Switched to tab {tab_idx} ({window.tabs.tabText(tab_idx)}) successfully!")
else:
    print(f"Part1.stp not found at: {part_path}")

# Close window and exit
QTimer.singleShot(100, lambda: (window.close(), app.quit()))
sys.exit(app.exec_())
