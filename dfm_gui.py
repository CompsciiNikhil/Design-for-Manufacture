import os
import sys
import math
import numpy as np

# Select the PyQt5 backend before any other OCC imports
import OCC.Display.backend
OCC.Display.backend.load_backend('pyqt5')

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QComboBox, QLabel, 
                             QStatusBar, QFileDialog, QTabWidget, QFrame, 
                             QSplitter, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from OCC.Display.qtDisplay import qtViewer3d
from OCC.Core.gp import gp_Ax1, gp_Ax2, gp_Pnt, gp_Dir, gp_Vec, gp_Trsf

class CustomViewer3d(qtViewer3d):
    def mouseMoveEvent(self, evt):
        pt = evt.pos()
        buttons = evt.buttons()
        modifiers = evt.modifiers()
        
        # Pan with middle button OR Shift + Left button drag
        if (buttons == Qt.MiddleButton) or (buttons == Qt.LeftButton and modifiers == Qt.ShiftModifier):
            dx = pt.x() - self.dragStartPosX
            dy = pt.y() - self.dragStartPosY
            self.dragStartPosX = pt.x()
            self.dragStartPosY = pt.y()
            self.cursor = "pan"
            self._display.Pan(dx, -dy)
            self._drawbox = False
        else:
            super().mouseMoveEvent(evt)
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeCone
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.Aspect import Aspect_TOL_SOLID
from OCC.Core.Prs3d import Prs3d_LineAspect
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.TopoDS import topods

# Import our customized modules
from dfm_engine import DFMEngine

STYLE_SHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    color: #f8f8f2;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QFrame#top_bar {
    background-color: #181825;
    border-bottom: 2px solid #3d3d5c;
    border-radius: 0px;
}
QLabel#app_title {
    color: #e20015;
}
QFrame.panel {
    background-color: #252538;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    padding: 10px;
}
QPushButton {
    background-color: #e20015;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #ff2a3a;
}
QPushButton:pressed {
    background-color: #b30010;
}
QPushButton:disabled {
    background-color: #444454;
    color: #7f7f8f;
}
QComboBox {
    background-color: #252538;
    border: 1px solid #3d3d5c;
    border-radius: 4px;
    padding: 6px;
    color: white;
}
QComboBox QAbstractItemView {
    background-color: #252538;
    selection-background-color: #e20015;
    selection-foreground-color: white;
    color: white;
    border: 1px solid #3d3d5c;
}
QTabWidget::pane {
    border: 1px solid #3d3d5c;
    background-color: #252538;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #181825;
    color: #a0a0a0;
    border: 1px solid #3d3d5c;
    border-bottom: none;
    padding: 10px 20px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #252538;
    color: white;
    border-bottom: 2px solid #e20015;
}
QTabBar::tab:hover {
    background-color: #2d2d44;
    color: white;
}
QLabel.section-title {
    font-weight: bold;
    font-size: 14px;
    color: #e20015;
    margin-top: 15px;
    margin-bottom: 5px;
}
QLabel.lbl-text {
    font-weight: normal;
    color: #c0c0c0;
}
QLabel.val-text {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: bold;
    color: #ffffff;
}
"""

class DFMMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DfM Intelligence Agent — Bosch")
        self.resize(1200, 800)
        
        self.engine = None
        self.analysis_result = None
        self.filepath = None
        
        # Apply global stylesheet
        self.setStyleSheet(STYLE_SHEET)
        
        # Main widget & layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create UI
        self.create_top_bar()
        self.create_main_content()
        self.create_status_bar()
        
        # Update labels with placeholders
        self.update_ui_placeholders()

    def create_top_bar(self):
        top_frame = QFrame()
        top_frame.setObjectName("top_bar")
        top_frame.setFrameShape(QFrame.StyledPanel)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel("DfM Intelligence Agent — Bosch")
        title_label.setObjectName("app_title")
        title_font = QFont("Segoe UI", 14, QFont.Bold)
        title_label.setFont(title_font)
        
        self.open_btn = QPushButton("Open STEP File")
        self.open_btn.clicked.connect(self.on_open_file)
        
        material_layout = QHBoxLayout()
        material_label = QLabel("Material:")
        self.material_combo = QComboBox()
        self.material_combo.addItems(["ABS", "PP", "Nylon", "PC", "POM"])
        self.material_combo.currentTextChanged.connect(self.on_material_changed)
        material_layout.addWidget(material_label)
        material_layout.addWidget(self.material_combo)
        
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self.on_run_analysis)
        
        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.clicked.connect(self.on_reset_view)
        
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addLayout(material_layout)
        top_layout.addWidget(self.open_btn)
        top_layout.addWidget(self.run_btn)
        top_layout.addWidget(self.reset_view_btn)
        
        self.main_layout.addWidget(top_frame)

    def create_main_content(self):
        # Splitter to separate 3D Viewport from Right Panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # 3D Viewport container
        self.canvas = CustomViewer3d(self)
        splitter.addWidget(self.canvas)
        
        # Tab Widget for different views
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # 0. CAD Model Info Tab
        self.model_info_tab = QWidget()
        self.setup_model_info_tab()
        self.tabs.addTab(self.model_info_tab, "CAD Model Info")
        
        # 1. Draft Analysis Tab
        self.draft_tab = QWidget()
        self.setup_draft_tab()
        self.tabs.addTab(self.draft_tab, "Draft Analysis")
        
        # 2. Mold Split Tab
        self.split_tab = QWidget()
        self.setup_split_tab()
        self.tabs.addTab(self.split_tab, "Mold Split")
        
        # 3. Parting Line Tab
        self.parting_tab = QWidget()
        self.setup_parting_tab()
        self.tabs.addTab(self.parting_tab, "Parting Line")
        
        # 4. Exploded Mold View Tab
        self.exploded_tab = QWidget()
        self.setup_exploded_tab()
        self.tabs.addTab(self.exploded_tab, "Exploded Mold View")
        
        # 5. Z = 14.0 Exploded View Tab
        self.z_14_tab = QWidget()
        self.setup_z_14_tab()
        self.tabs.addTab(self.z_14_tab, "Z = 14.0 Exploded View")
        
        splitter.addWidget(self.tabs)
        
        # Set sizes (70% and 30%)
        splitter.setSizes([840, 360])
        
        self.main_layout.addWidget(splitter)

    def create_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("No STEP file loaded.")

    def setup_model_info_tab(self):
        layout = QVBoxLayout(self.model_info_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("CAD Model Specifications")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        _, self.info_val_filename = self.create_stat_row(panel_layout, "Filename:")
        _, self.info_val_faces = self.create_stat_row(panel_layout, "Total Faces:")
        
        title_bbox = QLabel("Bounding Box Dimensions")
        title_bbox.setProperty("class", "section-title")
        panel_layout.addWidget(title_bbox)
        
        _, self.info_val_bbox_x = self.create_stat_row(panel_layout, "X Span:")
        _, self.info_val_bbox_y = self.create_stat_row(panel_layout, "Y Span:")
        _, self.info_val_bbox_z = self.create_stat_row(panel_layout, "Z Span:")
        
        title_surf = QLabel("Surface Type Statistics")
        title_surf.setProperty("class", "section-title")
        panel_layout.addWidget(title_surf)
        
        from PyQt5.QtWidgets import QTextEdit
        self.info_surf_stats_txt = QTextEdit()
        self.info_surf_stats_txt.setReadOnly(True)
        self.info_surf_stats_txt.setStyleSheet("background-color: #181825; border: 1px solid #3d3d5c; font-family: 'Courier New', monospace; font-size: 11px;")
        panel_layout.addWidget(self.info_surf_stats_txt)
        
        panel_layout.addStretch()
        layout.addWidget(panel)

    def update_model_info_tab(self):
        if not self.engine or not self.engine.part:
            self.info_val_filename.setText("-")
            self.info_val_faces.setText("-")
            self.info_val_bbox_x.setText("-")
            self.info_val_bbox_y.setText("-")
            self.info_val_bbox_z.setText("-")
            self.info_surf_stats_txt.setText("No CAD model loaded.")
            return
            
        # Filename
        self.info_val_filename.setText(os.path.basename(self.filepath))
        # Face count
        self.info_val_faces.setText(str(len(self.engine.part.faces)))
        
        # Bounding box
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        self.info_val_bbox_x.setText(f"{dx:.2f} mm  ({xmin:.1f} to {xmax:.1f})")
        self.info_val_bbox_y.setText(f"{dy:.2f} mm  ({ymin:.1f} to {ymax:.1f})")
        self.info_val_bbox_z.setText(f"{dz:.2f} mm  ({zmin:.1f} to {zmax:.1f})")
        
        # Surface type statistics
        from collections import Counter
        surf_types = [face.surface_type for face in self.engine.part.faces]
        counts = Counter(surf_types)
        
        stats_lines = []
        stats_lines.append(f"{'Surface Type':<16} | {'Count':<6} | {'Percentage':<10}")
        stats_lines.append("-" * 38)
        total = len(surf_types) or 1
        for s_type, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100.0
            stats_lines.append(f"{s_type:<16} | {count:<6d} | {pct:.1f}%")
            
        self.info_surf_stats_txt.setText("\n".join(stats_lines))

    def setup_draft_tab(self):
        layout = QVBoxLayout(self.draft_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Draft Analysis")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        _, self.val_min_draft = self.create_stat_row(panel_layout, "Min Draft:")
        _, self.val_max_draft = self.create_stat_row(panel_layout, "Max Draft:")
        _, self.val_avg_draft = self.create_stat_row(panel_layout, "Average Draft:")
        
        title_undercut = QLabel("Undercuts")
        title_undercut.setProperty("class", "section-title")
        panel_layout.addWidget(title_undercut)
        
        _, self.val_undercut_faces = self.create_stat_row(panel_layout, "Undercut Faces:")
        _, self.val_undercut_area = self.create_stat_row(panel_layout, "Undercut Area:")
        
        title_mold_dir = QLabel("Optimal Mold Direction")
        title_mold_dir.setProperty("class", "section-title")
        panel_layout.addWidget(title_mold_dir)
        
        _, self.val_mold_dir_x = self.create_stat_row(panel_layout, "X:")
        _, self.val_mold_dir_y = self.create_stat_row(panel_layout, "Y:")
        _, self.val_mold_dir_z = self.create_stat_row(panel_layout, "Z:")
        _, self.val_mold_dir_conf = self.create_stat_row(panel_layout, "Confidence:")
        
        title_legend = QLabel("Legend")
        title_legend.setProperty("class", "section-title")
        panel_layout.addWidget(title_legend)
        
        panel_layout.addWidget(self.create_legend_row("#00CC00", "> 3.0° (Safe)"))
        panel_layout.addWidget(self.create_legend_row("#99FF66", "1.0° - 3.0° (Acceptable)"))
        panel_layout.addWidget(self.create_legend_row("#FFFF00", "0.0° - 1.0° (Warning)"))
        panel_layout.addWidget(self.create_legend_row("#FF0000", "≈ 0.0° (Critical)"))
        panel_layout.addWidget(self.create_legend_row("#004CFF", "Undercut"))
        
        panel_layout.addStretch()
        layout.addWidget(panel)

    def setup_split_tab(self):
        layout = QVBoxLayout(self.split_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Mold Split Classification")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        _, self.val_core_faces = self.create_stat_row(panel_layout, "Core Faces:")
        _, self.val_cavity_faces = self.create_stat_row(panel_layout, "Cavity Faces:")
        _, self.val_neutral_faces = self.create_stat_row(panel_layout, "Neutral Faces:")
        
        title_silhouette = QLabel("Silhouette Info")
        title_silhouette.setProperty("class", "section-title")
        panel_layout.addWidget(title_silhouette)
        
        _, self.val_silhouette_faces = self.create_stat_row(panel_layout, "Silhouette Faces:")
        _, self.val_silhouette_area = self.create_stat_row(panel_layout, "Silhouette Area:")
        
        title_parting = QLabel("Parting Line Candidates")
        title_parting.setProperty("class", "section-title")
        panel_layout.addWidget(title_parting)
        
        _, self.val_parting_candidates = self.create_stat_row(panel_layout, "Parting Candidates:")
        _, self.val_parting_length_split = self.create_stat_row(panel_layout, "Parting Line Length:")
        
        title_legend = QLabel("Legend")
        title_legend.setProperty("class", "section-title")
        panel_layout.addWidget(title_legend)
        
        panel_layout.addWidget(self.create_legend_row("#E63333", "Cavity Faces"))
        panel_layout.addWidget(self.create_legend_row("#3366E6", "Core Faces"))
        panel_layout.addWidget(self.create_legend_row("#FF0080", "Silhouette Faces"))
        panel_layout.addWidget(self.create_legend_row("#B2B2B2", "Neutral/Remaining"))
        panel_layout.addWidget(self.create_legend_row("#FFCC00", "Parting Line Candidate"))
        
        panel_layout.addStretch()
        layout.addWidget(panel)

    def setup_parting_tab(self):
        layout = QVBoxLayout(self.parting_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Engineering Decision Advisor")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        # Badge layout
        badge_layout = QHBoxLayout()
        self.parting_badge_status = QLabel("-")
        self.parting_badge_status.setAlignment(Qt.AlignCenter)
        self.parting_badge_status.setFixedHeight(30)
        self.parting_badge_status.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.parting_badge_status.setStyleSheet("border-radius: 4px; padding: 4px; color: white;")
        badge_layout.addWidget(self.parting_badge_status)
        panel_layout.addLayout(badge_layout)
        
        # Justification text block
        exp_lbl = QLabel("Engineering Justification:")
        exp_lbl.setProperty("class", "lbl-text")
        exp_lbl.setStyleSheet("font-weight: bold; margin-top: 5px;")
        panel_layout.addWidget(exp_lbl)
        
        self.parting_val_justification = QLabel("-")
        self.parting_val_justification.setWordWrap(True)
        self.parting_val_justification.setStyleSheet("color: #dfdfea; font-size: 11px; padding: 4px; background-color: #181825; border-radius: 4px;")
        panel_layout.addWidget(self.parting_val_justification)
        
        title_metrics = QLabel("Parting Line Metrics")
        title_metrics.setProperty("class", "section-title")
        panel_layout.addWidget(title_metrics)
        
        _, self.val_parting_status = self.create_stat_row(panel_layout, "Status:")
        _, self.val_parting_length = self.create_stat_row(panel_layout, "Line Length:")
        _, self.val_closed_loop = self.create_stat_row(panel_layout, "Closed Loop:")
        _, self.val_loop_count = self.create_stat_row(panel_layout, "Loop Count:")
        
        title_loops = QLabel("Loop Details")
        title_loops.setProperty("class", "section-title")
        panel_layout.addWidget(title_loops)
        
        from PyQt5.QtWidgets import QTextEdit
        self.loop_details_txt = QTextEdit()
        self.loop_details_txt.setReadOnly(True)
        self.loop_details_txt.setMaximumHeight(80)
        self.loop_details_txt.setStyleSheet("background-color: #181825; border: 1px solid #3d3d5c; font-family: 'Courier New', monospace; font-size: 11px;")
        panel_layout.addWidget(self.loop_details_txt)
        
        title_mold = QLabel("Mold Configuration")
        title_mold.setProperty("class", "section-title")
        panel_layout.addWidget(title_mold)
        
        _, self.val_pull_dir = self.create_stat_row(panel_layout, "Pull Direction:")
        _, self.val_parting_plane_pos = self.create_stat_row(panel_layout, "Parting Plane Height:")
        _, self.val_undercut_count = self.create_stat_row(panel_layout, "Undercut Count:")
        _, self.val_draft_violations = self.create_stat_row(panel_layout, "Draft Violations:")
        
        title_score = QLabel("Quality & Score")
        title_score.setProperty("class", "section-title")
        panel_layout.addWidget(title_score)
        
        _, self.val_dfm_score = self.create_stat_row(panel_layout, "Moldability Score:")
        
        title_legend = QLabel("Legend")
        title_legend.setProperty("class", "section-title")
        panel_layout.addWidget(title_legend)
        panel_layout.addWidget(self.create_legend_row("#CCFF00", "Parting Line Wires"))
        panel_layout.addWidget(self.create_legend_row("#00FFFF", "Mold Direction Arrow"))
        panel_layout.addWidget(self.create_legend_row("#E20015", "Cavity Block (70% Transparent)"))
        panel_layout.addWidget(self.create_legend_row("#004CFF", "Core Block (70% Transparent)"))
        
        panel_layout.addStretch()
        
        # Export Buttons
        btn_layout = QHBoxLayout()
        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.setEnabled(False)
        self.btn_export_json.clicked.connect(self.on_export_json)
        
        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.clicked.connect(self.on_export_pdf)
        
        btn_layout.addWidget(self.btn_export_json)
        btn_layout.addWidget(self.btn_export_pdf)
        panel_layout.addLayout(btn_layout)
        
        layout.addWidget(panel)

    def create_stat_row(self, layout, label_text):
        row = QWidget()
        lyt = QHBoxLayout(row)
        lyt.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(label_text)
        lbl.setProperty("class", "lbl-text")
        val = QLabel("-")
        val.setProperty("class", "val-text")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lyt.addWidget(lbl)
        lyt.addWidget(val)
        layout.addWidget(row)
        return row, val

    def create_legend_row(self, color_hex, label_text):
        row = QWidget()
        lyt = QHBoxLayout(row)
        lyt.setContentsMargins(0, 2, 0, 2)
        color_box = QLabel()
        color_box.setFixedSize(14, 14)
        color_box.setStyleSheet(f"background-color: {color_hex}; border-radius: 3px;")
        lbl = QLabel(label_text)
        lyt.addWidget(color_box)
        lyt.addWidget(lbl)
        lyt.addStretch()
        return row

    def init_viewer(self):
        self.canvas.InitDriver()
        self.display = self.canvas._display
        self.display.SetModeShaded()
        self.display.set_bg_gradient_color([30, 30, 40], [15, 15, 25])
        self.display.display_triedron()
        self.canvas.setMouseTracking(True)
        # Register select callback
        self.display.register_select_callback(self.on_select)

    def update_ui_placeholders(self):
        for label in [
            self.info_val_filename, self.info_val_faces,
            self.info_val_bbox_x, self.info_val_bbox_y, self.info_val_bbox_z,
            self.val_min_draft, self.val_max_draft, self.val_avg_draft,
            self.val_undercut_faces, self.val_undercut_area,
            self.val_mold_dir_x, self.val_mold_dir_y, self.val_mold_dir_z, self.val_mold_dir_conf,
            self.val_core_faces, self.val_cavity_faces, self.val_neutral_faces,
            self.val_silhouette_faces, self.val_silhouette_area,
            self.val_parting_candidates, self.val_parting_length_split,
            self.val_parting_status, self.val_parting_length, self.val_closed_loop,
            self.val_loop_count,
            self.val_pull_dir, self.val_parting_plane_pos, self.val_undercut_count, self.val_draft_violations,
            self.val_dfm_score,
            self.demo_val_plane_pos, self.demo_val_classification,
            self.demo_val_score, self.demo_val_undercuts, self.demo_val_area,
            self.demo_val_crossing, self.demo_val_core_faces, self.demo_val_cavity_faces,
            self.demo_val_complexity, self.demo_val_cavity_dir, self.demo_val_core_dir,
            self.z14_val_score, self.z14_val_undercuts, self.z14_val_undercut_area,
            self.z14_val_core_faces, self.z14_val_cavity_faces, self.z14_val_crossing_faces
        ]:
            label.setText("-")
            
        self.info_surf_stats_txt.setText("No CAD model loaded.")
        self.parting_badge_status.setText("-")
        self.parting_badge_status.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px;")
        self.parting_val_justification.setText("No analysis run.")
        
        self.badge_status.setText("-")
        self.badge_status.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px;")
        self.demo_val_reason.setText("No analysis run.")
        self.demo_comp_table.setText("No analysis run.")
        
        self.z14_val_justification.setText("No analysis run.")
        self.z14_badge_status.setText("-")
        self.z14_badge_status.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px;")
            
        self.loop_details_txt.setText("No analysis run.")
        self.btn_export_json.setEnabled(False)
        self.btn_export_pdf.setEnabled(False)

    def on_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select STEP File", "", "STEP Files (*.stp *.step)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        print(f"Loading file: {file_path}", flush=True)
        self.filepath = file_path
        self.engine = DFMEngine(file_path)
        try:
            self.statusBar().showMessage("Loading STEP Geometry...")
            QApplication.processEvents()
            
            num_faces = self.engine.load_part()
            self.statusBar().showMessage(f"Loaded {os.path.basename(file_path)}: {num_faces} faces")
            self.run_btn.setEnabled(True)
            
            # Reset results
            self.analysis_result = None
            self.update_ui_placeholders()
            
            # Draw the part in neutral color first
            self.display.EraseAll()
            self.display.DisplayShape(self.engine.part.shape, update=True)
            self.display.FitAll()
            
            # Update Model Info Tab
            self.update_model_info_tab()
            self.tabs.setCurrentIndex(0) # Switch to Model Info tab on load
            
        except Exception as e:
            print(f"Error loading file: {str(e)}", flush=True)
            self.filepath = None
            self.engine = None
            self.run_btn.setEnabled(False)
            self.update_ui_placeholders()
            self.statusBar().showMessage("No STEP file loaded.")
            QMessageBox.warning(
                self, 
                "Error", 
                "Unable to parse STEP file.\n\nPlease select a valid solid STEP model."
            )

    def on_material_changed(self, text):
        # If we already have an analysis, re-run it with new material
        if self.analysis_result:
            self.on_run_analysis()

    def on_reset_view(self):
        if hasattr(self, "display") and self.display:
            self.display.FitAll()
            self.display.View.SetProj(1.0, -1.0, 0.7)
            self.display.FitAll()
            self.display.View.Redraw()

    def on_run_analysis(self):
        print("on_run_analysis called", flush=True)
        if not self.engine or not self.engine.part:
            print("Engine or part is None", flush=True)
            return
        
        # Disable controls
        self.open_btn.setEnabled(False)
        self.material_combo.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.tabs.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        def progress_callback(msg):
            self.statusBar().showMessage(msg)
            QApplication.processEvents()
            
        material = self.material_combo.currentText()
        print(f"Running DfM analysis for {material}...", flush=True)
        try:
            self.analysis_result = self.engine.run_analysis(material, callback=progress_callback)
            print("Analysis complete", flush=True)
            self.update_ui_stats()
            print("UI stats updated", flush=True)
            self.on_tab_changed(self.tabs.currentIndex())
            print("Tab changed triggered", flush=True)
            self.statusBar().showMessage(f"Analysis complete for {material}. DfM Score: {self.analysis_result.dfm_score}/100")
            
            self.btn_export_json.setEnabled(True)
            self.btn_export_pdf.setEnabled(True)
        except Exception as e:
            print(f"Analysis failed: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Analysis failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{str(e)}")
        finally:
            # Re-enable controls
            self.open_btn.setEnabled(True)
            self.material_combo.setEnabled(True)
            self.run_btn.setEnabled(True)
            self.tabs.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def update_ui_stats(self):
        res = self.analysis_result
        if not res:
            return
            
        # Draft Tab
        self.val_min_draft.setText(f"{res.draft_analysis['min_draft_deg']:.2f}°")
        self.val_max_draft.setText(f"{res.draft_analysis['max_draft_deg']:.2f}°")
        self.val_avg_draft.setText(f"{res.draft_analysis['avg_draft_deg']:.2f}°")
        
        self.val_undercut_faces.setText(str(res.undercuts['count']))
        self.val_undercut_area.setText(f"{res.undercuts['total_area_mm2']:.2f} mm²")
        
        self.val_mold_dir_x.setText(f"{res.mold_direction[0]:.3f}")
        self.val_mold_dir_y.setText(f"{res.mold_direction[1]:.3f}")
        self.val_mold_dir_z.setText(f"{res.mold_direction[2]:.3f}")
        self.val_mold_dir_conf.setText(f"{self.engine.confidence * 100:.1f}%")
        
        # Mold Split Tab
        self.val_core_faces.setText(str(res.mold_split['core_faces']))
        self.val_cavity_faces.setText(str(res.mold_split['cavity_faces']))
        self.val_neutral_faces.setText(str(res.mold_split['neutral_faces']))
        
        self.val_silhouette_faces.setText(str(len(res.mold_split['silhouette_faces'])))
        self.val_silhouette_area.setText(f"{res.mold_split['silhouette_area']:.2f} mm²")
        
        self.val_parting_candidates.setText(str(res.parting_line['edge_count']))
        self.val_parting_length_split.setText(f"{res.parting_line['total_length_mm']:.2f} mm")
        
        # Parting Line Tab
        self.val_parting_status.setText("✅ Detected" if res.parting_line['edge_count'] > 0 else "❌ None")
        self.val_parting_length.setText(f"{res.parting_line['total_length_mm']:.2f} mm")
        self.val_closed_loop.setText("Yes" if res.parting_line['is_closed_loop'] else "No")
        self.val_loop_count.setText(str(len(res.parting_line['loops'])))
        
        loop_details_lines = []
        for i, loop in enumerate(res.parting_line['loops']):
            loop_len = 0.0
            for edge in loop['edges']:
                loop_len += self.engine._get_edge_length(edge)
            status_str = "Closed" if loop['is_closed'] else "Open"
            loop_details_lines.append(f"Loop {i+1:2d}: {status_str:<6} | Length: {loop_len:.2f} mm | Edges: {len(loop['edges'])}")
        
        self.loop_details_txt.setText("\n".join(loop_details_lines) if loop_details_lines else "No loops detected.")
        
        dir_str = f"[{res.mold_direction[0]:.2f}, {res.mold_direction[1]:.2f}, {res.mold_direction[2]:.2f}]"
        self.val_pull_dir.setText(dir_str)
        self.val_parting_plane_pos.setText(f"{res.optimal_z:.2f} mm")
        self.val_undercut_count.setText(str(res.optimal_stats['undercut_count']))
        self.val_draft_violations.setText(str(res.draft_analysis['draft_violation_count']))
        
        score = res.moldability_score
        self.val_dfm_score.setText(f"{score:.2f} / 100")

        classification = res.optimal_stats.get("classification", "PARTIALLY MOLDABLE")
        self.parting_badge_status.setText(classification)
        if classification == "MOLDABLE":
            self.parting_badge_status.setStyleSheet("background-color: #2e7d32; color: white; border-radius: 4px; font-weight: bold;")
        elif classification == "PARTIALLY MOLDABLE":
            self.parting_badge_status.setStyleSheet("background-color: #f9a825; color: black; border-radius: 4px; font-weight: bold;")
        elif classification == "SIDE ACTION REQUIRED":
            self.parting_badge_status.setStyleSheet("background-color: #ff9800; color: white; border-radius: 4px; font-weight: bold;")
        else:
            self.parting_badge_status.setStyleSheet("background-color: #c62828; color: white; border-radius: 4px; font-weight: bold;")

        justification = (
            f"The automatically selected Z = {res.optimal_z:.2f} mm split minimizes undercut area ({res.optimal_stats['undercut_area']:.1f} mm²), "
            f"reduces faces requiring geometric splitting ({res.optimal_stats['crossing_faces']}), and produces the most balanced core/cavity separation. "
            f"This parting plane yields the highest moldability score ({score:.1f}) among all candidate planes. "
            f"Classification: {classification}."
        )
        self.parting_val_justification.setText(justification)

        # Dynamic calculations for Z = 14.0
        stats_z14 = self.engine.evaluate_pull_direction_and_split([0, 0, 1], 14.0)
        total_area = sum(f.area for f in self.engine.part.faces) or 1.0
        total_faces = len(self.engine.part.faces) or 1.0
        ratio_z14 = stats_z14["undercut_area"] / total_area
        cnt_ratio_z14 = stats_z14["undercut_count"] / total_faces
        cross_ratio_z14 = stats_z14["crossing_faces"] / total_faces

        core_cnt_z14 = stats_z14["core_faces"]
        cavity_cnt_z14 = stats_z14["cavity_faces"]
        max_cnt_z14 = max(1.0, max(core_cnt_z14, cavity_cnt_z14))
        balance_z14 = min(core_cnt_z14, cavity_cnt_z14) / max_cnt_z14

        score_z14 = (
            0.40 * (100.0 - ratio_z14 * 100.0) +
            0.25 * (100.0 - cnt_ratio_z14 * 100.0) +
            0.20 * (100.0 - cross_ratio_z14 * 100.0) +
            0.15 * (balance_z14 * 100.0)
        )
        score_z14 = max(0.0, score_z14)

        self.z14_val_score.setText(f"{score_z14:.2f} / 100")
        self.z14_val_undercuts.setText(str(stats_z14["undercut_count"]))
        self.z14_val_undercut_area.setText(f"{stats_z14['undercut_area']:.2f} mm²")
        self.z14_val_core_faces.setText(str(stats_z14["core_faces"]))
        self.z14_val_cavity_faces.setText(str(stats_z14["cavity_faces"]))
        self.z14_val_crossing_faces.setText(str(stats_z14["crossing_faces"]))

        z14_justification = (
            f"At Z = 14.0 mm, the parting plane sits right below the top cap. "
            f"Consequently, the cavity block forms only the top cap cosmetic region, forcing the core block "
            f"to form the entire main body and legs. This traps all bottom-facing features and vertical ribs "
            f"on the core side, creating mechanical locks ({stats_z14['undercut_count']} undercut faces) "
            f"and requiring side actions/sliders for other directions."
        )
        self.z14_val_justification.setText(z14_justification)

        if stats_z14["undercut_count"] == 0 and stats_z14["crossing_faces"] == 0:
            classification_z14 = "MOLDABLE"
        elif ratio_z14 < 0.05 and cross_ratio_z14 < 0.25 and cnt_ratio_z14 < 0.30:
            classification_z14 = "PARTIALLY MOLDABLE"
        elif ratio_z14 < 0.12 and cnt_ratio_z14 < 0.40:
            classification_z14 = "SIDE ACTION REQUIRED"
        else:
            classification_z14 = "NOT MOLDABLE"

        self.z14_badge_status.setText(classification_z14)
        if classification_z14 == "MOLDABLE":
            self.z14_badge_status.setStyleSheet("background-color: #2e7d32; color: white; border-radius: 4px; font-weight: bold;")
        elif classification_z14 == "PARTIALLY MOLDABLE":
            self.z14_badge_status.setStyleSheet("background-color: #f9a825; color: black; border-radius: 4px; font-weight: bold;")
        elif classification_z14 == "SIDE ACTION REQUIRED":
            self.z14_badge_status.setStyleSheet("background-color: #ff9800; color: white; border-radius: 4px; font-weight: bold;")
        else:
            self.z14_badge_status.setStyleSheet("background-color: #c62828; color: white; border-radius: 4px; font-weight: bold;")
        
        # Update demo comparison table
        self.update_demo_comparison_table()
        # Populate initial cases in demo tab
        self.populate_demo_cases()

    def on_tab_changed(self, index):
        print(f"on_tab_changed called with index: {index}", flush=True)
        if not self.engine or not self.engine.part:
            print("on_tab_changed: Engine or part is None", flush=True)
            return
            
        self.display.EraseAll()
        self.display.SetSelectionModeFace()
        
        if self.analysis_result is None:
            print("on_tab_changed: analysis_result is None, displaying neutral shape", flush=True)
            self.display.DisplayShape(self.engine.part.shape, update=True)
            self.display.FitAll()
            return
            
        if index == 0:
            self.display.DisplayShape(self.engine.part.shape, update=True)
            self.display.FitAll()
        elif index == 1:
            self.render_draft_analysis()
        elif index == 2:
            self.render_mold_split()
        elif index == 3:
            self.render_parting_line()
        elif index == 4:
            self.render_exploded_mold()
        elif index == 5:
            self.render_z_14_view()
            
        self.display.View.Redraw()
        self.display.Repaint()
        print("Redraw and Repaint called", flush=True)

    def render_draft_analysis(self):
        print("render_draft_analysis starting", flush=True)
        draft_details = self.analysis_result.draft_analysis["details"]
        print(f"Draft details count: {len(draft_details)}", flush=True)
        for detail in draft_details:
            face_id = detail["face_id"]
            draft_angle = detail["draft_angle"]
            face = self.engine.face_map[face_id]
            
            if draft_angle is None:
                color = Quantity_Color(0.7, 0.7, 0.7, Quantity_TOC_RGB)
            elif draft_angle < 0:
                color = Quantity_Color(0.0, 0.3, 1.0, Quantity_TOC_RGB) # Blue
            elif draft_angle < 0.5:
                color = Quantity_Color(1.0, 0.0, 0.0, Quantity_TOC_RGB) # Red
            elif draft_angle < 1.0:
                color = Quantity_Color(1.0, 1.0, 0.0, Quantity_TOC_RGB) # Yellow
            elif draft_angle < 3.0:
                color = Quantity_Color(0.6, 1.0, 0.4, Quantity_TOC_RGB) # Light Green
            else:
                color = Quantity_Color(0.0, 0.8, 0.0, Quantity_TOC_RGB) # Green
                
            ais_shapes = self.display.DisplayColoredShape(face, color, update=False)
            for ais_shape in ais_shapes:
                ais_shape.SetDisplayMode(1)
        print("render_draft_analysis completed", flush=True)

    def render_mold_split(self):
        print("render_mold_split starting", flush=True)
        details = self.analysis_result.mold_split["details"]
        silhouette_faces = set(self.analysis_result.mold_split["silhouette_faces"])
        print(f"Mold split details: {len(details)}, silhouettes: {len(silhouette_faces)}", flush=True)
        
        for detail in details:
            face_id = detail["face_id"]
            label = detail["classification"]
            face = self.engine.face_map[face_id]
            
            if face_id in silhouette_faces:
                color = Quantity_Color(1.0, 0.0, 0.5, Quantity_TOC_RGB) # Bright Red
            elif label == "CAVITY":
                color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB) # Red
            elif label == "CORE":
                color = Quantity_Color(0.2, 0.4, 0.9, Quantity_TOC_RGB) # Blue
            else:
                color = Quantity_Color(0.7, 0.7, 0.7, Quantity_TOC_RGB) # Gray
                
            ais_shapes = self.display.DisplayColoredShape(face, color, update=False)
            for ais_shape in ais_shapes:
                ais_shape.SetDisplayMode(1)
            
        # Draw Parting Line Edges (Yellow, width 3.0)
        yellow = Quantity_Color(1.0, 0.9, 0.0, Quantity_TOC_RGB)
        aspect = Prs3d_LineAspect(yellow, Aspect_TOL_SOLID, 3.0)
        raw_edges = self.analysis_result.parting_line["raw_edges"]
        print(f"Drawing raw parting line edges: {len(raw_edges)}", flush=True)
        for item in raw_edges:
            edge = item["edge"]
            ais_edges = self.display.DisplayShape(edge, update=False)
            for ais_edge in ais_edges:
                ais_edge.Attributes().SetLineAspect(aspect)
                ais_edge.Attributes().SetWireAspect(aspect)
                ais_edge.Attributes().SetFreeBoundaryAspect(aspect)
                ais_edge.Attributes().SetUnFreeBoundaryAspect(aspect)
                self.display.Context.Redisplay(ais_edge, False)
        print("render_mold_split completed", flush=True)

    def render_parting_line(self):
        print("render_parting_line starting", flush=True)
        if not self.engine or not self.engine.part or not self.analysis_result:
            return
            
        self.display.EraseAll()
        self.display.SetSelectionModeFace()
        
        # 1. Part = Semi-Transparent Gray (0.85, 0.85, 0.85) with 70% transparency
        color = Quantity_Color(0.85, 0.85, 0.85, Quantity_TOC_RGB)
        ais_shape_list = self.display.DisplayShape(self.engine.part.shape, update=False)
        for ais_shape in ais_shape_list:
            ais_shape.SetColor(color)
            ais_shape.SetTransparency(0.7)
            
        # 2. Parting Line Wires = Bright Yellow-Green (0.8, 1.0, 0.0) with width 4.0
        yellow_green = Quantity_Color(0.8, 1.0, 0.0, Quantity_TOC_RGB)
        aspect = Prs3d_LineAspect(yellow_green, Aspect_TOL_SOLID, 4.0)
        loops = self.analysis_result.parting_line["loops"]
        print(f"Drawing parting line loops: {len(loops)}", flush=True)
        for loop in loops:
            for edge in loop["edges"]:
                ais_edges = self.display.DisplayShape(edge, update=False)
                for ais_edge in ais_edges:
                    ais_edge.Attributes().SetLineAspect(aspect)
                    ais_edge.Attributes().SetWireAspect(aspect)
                    ais_edge.Attributes().SetFreeBoundaryAspect(aspect)
                    ais_edge.Attributes().SetUnFreeBoundaryAspect(aspect)
                    self.display.Context.Redisplay(ais_edge, False)
                    
        # 3. Mold Direction Arrow = Cyan
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        cz = (zmin + zmax) / 2.0
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        arrow_shape = self.create_arrow([cx, cy, cz], self.engine.best_direction, dz * 0.4)
        if arrow_shape:
            cyan = Quantity_Color(0.0, 1.0, 1.0, Quantity_TOC_RGB)
            self.display.DisplayColoredShape(arrow_shape, cyan, update=False)
            
        # 4. Core & Cavity blocks = Semi-transparent red and blue, slightly retracted
        bx_min = xmin - dx * 0.15
        bx_max = xmax + dx * 0.15
        by_min = ymin - dy * 0.15
        by_max = ymax + dy * 0.15
        z_split = self.analysis_result.optimal_z
        
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Trsf
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        
        cavity_box = BRepPrimAPI_MakeBox(
            gp_Pnt(bx_min, by_min, z_split),
            gp_Pnt(bx_max, by_max, zmax + dz * 0.3)
        ).Shape()
        
        core_box = BRepPrimAPI_MakeBox(
            gp_Pnt(bx_min, by_min, zmin - dz * 0.3),
            gp_Pnt(bx_max, by_max, z_split)
        ).Shape()
        
        try:
            cavity_cut = BRepAlgoAPI_Cut(cavity_box, self.engine.part.shape).Shape()
            core_cut = BRepAlgoAPI_Cut(core_box, self.engine.part.shape).Shape()
        except Exception as e:
            print("Boolean cut failed, falling back to blank blocks:", e)
            cavity_cut = cavity_box
            core_cut = core_box
            
        # Retract slightly for visual spacing
        trans_z = dz * 0.4
        
        trsf_cavity = gp_Trsf()
        trsf_cavity.SetTranslation(gp_Vec(0, 0, trans_z))
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True).Shape()
        
        trsf_core = gp_Trsf()
        trsf_core.SetTranslation(gp_Vec(0, 0, -trans_z))
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True).Shape()
        
        cavity_color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB)
        ais_cavity = self.display.DisplayColoredShape(cavity_exploded, cavity_color, update=False)
        for ais_c in (ais_cavity if isinstance(ais_cavity, list) else [ais_cavity]):
            ais_c.SetTransparency(0.7)
            
        core_color = Quantity_Color(0.2, 0.4, 0.9, Quantity_TOC_RGB)
        ais_core = self.display.DisplayColoredShape(core_exploded, core_color, update=False)
        for ais_co in (ais_core if isinstance(ais_core, list) else [ais_core]):
            ais_co.SetTransparency(0.7)
            
        print("render_parting_line completed", flush=True)

    def setup_exploded_tab(self):
        # 1. Main layout for the tab
        layout = QVBoxLayout(self.exploded_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 2. Top panel containing selection controls
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Moldability Demonstration")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        # Mode selector
        mode_lbl = QLabel("Analysis Mode:")
        mode_lbl.setProperty("class", "lbl-text")
        self.demo_mode_combo = QComboBox()
        self.demo_mode_combo.addItems(["Mold Opening Axis Analysis", "Parting Plane Analysis"])
        self.demo_mode_combo.currentTextChanged.connect(self.on_demo_mode_changed)
        
        panel_layout.addWidget(mode_lbl)
        panel_layout.addWidget(self.demo_mode_combo)
        
        # Case Selector
        case_lbl = QLabel("Select Test Case:")
        case_lbl.setProperty("class", "lbl-text")
        self.demo_case_combo = QComboBox()
        self.demo_case_combo.currentTextChanged.connect(self.on_demo_case_changed)
        
        panel_layout.addWidget(case_lbl)
        panel_layout.addWidget(self.demo_case_combo)
        
        layout.addWidget(panel)
        
        # 3. Advisor panel showing score and badges
        advisor_panel = QFrame()
        advisor_panel.setProperty("class", "panel")
        adv_layout = QVBoxLayout(advisor_panel)
        
        adv_title = QLabel("Engineering Advisor Results")
        adv_title.setProperty("class", "section-title")
        adv_layout.addWidget(adv_title)
        
        # Badge layout
        badge_layout = QHBoxLayout()
        self.badge_status = QLabel("-")
        self.badge_status.setAlignment(Qt.AlignCenter)
        self.badge_status.setFixedHeight(30)
        self.badge_status.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.badge_status.setStyleSheet("border-radius: 4px; padding: 4px; color: white;")
        badge_layout.addWidget(self.badge_status)
        adv_layout.addLayout(badge_layout)
        
        # Stats
        _, self.demo_val_plane_pos = self.create_stat_row(adv_layout, "Plane Position:")
        _, self.demo_val_classification = self.create_stat_row(adv_layout, "Classification:")
        _, self.demo_val_score = self.create_stat_row(adv_layout, "Moldability Score:")
        _, self.demo_val_undercuts = self.create_stat_row(adv_layout, "Undercut Count:")
        _, self.demo_val_area = self.create_stat_row(adv_layout, "Undercut Area:")
        _, self.demo_val_crossing = self.create_stat_row(adv_layout, "Faces requiring geometric splitting:")
        _, self.demo_val_core_faces = self.create_stat_row(adv_layout, "Core Faces:")
        _, self.demo_val_cavity_faces = self.create_stat_row(adv_layout, "Cavity Faces:")
        _, self.demo_val_complexity = self.create_stat_row(adv_layout, "Parting Complexity:")
        _, self.demo_val_cavity_dir = self.create_stat_row(adv_layout, "Cavity Movement:")
        _, self.demo_val_core_dir = self.create_stat_row(adv_layout, "Core Movement:")
        
        # Explanation
        exp_title = QLabel("Why this plane was selected:")
        exp_title.setProperty("class", "lbl-text")
        exp_title.setStyleSheet("font-weight: bold; margin-top: 5px;")
        adv_layout.addWidget(exp_title)
        
        self.demo_val_reason = QLabel("-")
        self.demo_val_reason.setWordWrap(True)
        self.demo_val_reason.setStyleSheet("color: #dfdfea; font-size: 11px; padding: 4px; background-color: #181825; border-radius: 4px;")
        adv_layout.addWidget(self.demo_val_reason)

        # Future Roadmap footnote
        roadmap_lbl = QLabel("Roadmap: Simultaneous Multi-Axis + Split Surface Optimization")
        roadmap_lbl.setStyleSheet("color: #7f7f8f; font-size: 10px; font-style: italic; margin-top: 5px;")
        adv_layout.addWidget(roadmap_lbl)
        
        layout.addWidget(advisor_panel)
        
        # 4. Comparison Table Panel
        comp_panel = QFrame()
        comp_panel.setProperty("class", "panel")
        comp_layout = QVBoxLayout(comp_panel)
        
        comp_title = QLabel("Mold Opening Axis Comparison Dashboard")
        comp_title.setProperty("class", "section-title")
        comp_layout.addWidget(comp_title)
        
        self.demo_comp_table = QLabel()
        self.demo_comp_table.setWordWrap(True)
        self.demo_comp_table.setStyleSheet("font-family: 'Segoe UI', monospace; font-size: 11px;")
        comp_layout.addWidget(self.demo_comp_table)
        
        layout.addWidget(comp_panel)
        
        layout.addStretch()

    def render_exploded_mold(self):
        print("render_exploded_mold starting", flush=True)
        self.on_demo_case_changed(self.demo_case_combo.currentText())

    def setup_z_14_tab(self):
        layout = QVBoxLayout(self.z_14_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Z = 14.0 Moldability Analysis")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        # Badge layout
        badge_layout = QHBoxLayout()
        self.z14_badge_status = QLabel("PARTIALLY MOLDABLE")
        self.z14_badge_status.setAlignment(Qt.AlignCenter)
        self.z14_badge_status.setFixedHeight(30)
        self.z14_badge_status.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.z14_badge_status.setStyleSheet("background-color: #f9a825; color: black; border-radius: 4px; font-weight: bold;")
        badge_layout.addWidget(self.z14_badge_status)
        panel_layout.addLayout(badge_layout)
        
        # Explanation text block
        exp_lbl = QLabel("Engineering Justification:")
        exp_lbl.setProperty("class", "lbl-text")
        exp_lbl.setStyleSheet("font-weight: bold; margin-top: 5px;")
        panel_layout.addWidget(exp_lbl)
        
        self.z14_val_justification = QLabel("-")
        self.z14_val_justification.setWordWrap(True)
        self.z14_val_justification.setStyleSheet("color: #dfdfea; font-size: 11px; padding: 4px; background-color: #181825; border-radius: 4px;")
        panel_layout.addWidget(self.z14_val_justification)
        
        title_metrics = QLabel("Z = 14.0 Metrics")
        title_metrics.setProperty("class", "section-title")
        panel_layout.addWidget(title_metrics)
        
        _, self.z14_val_score = self.create_stat_row(panel_layout, "Moldability Score:")
        _, self.z14_val_undercuts = self.create_stat_row(panel_layout, "Undercut Faces:")
        _, self.z14_val_undercut_area = self.create_stat_row(panel_layout, "Undercut Area:")
        _, self.z14_val_core_faces = self.create_stat_row(panel_layout, "Core Faces:")
        _, self.z14_val_cavity_faces = self.create_stat_row(panel_layout, "Cavity Faces:")
        _, self.z14_val_crossing_faces = self.create_stat_row(panel_layout, "Crossing Faces:")
        
        title_legend = QLabel("Legend")
        title_legend.setProperty("class", "section-title")
        panel_layout.addWidget(title_legend)
        panel_layout.addWidget(self.create_legend_row("#CCFF00", "Top Parting Line Wires"))
        panel_layout.addWidget(self.create_legend_row("#00FFFF", "Parting Plane Sheet (Z = 14.0)"))
        panel_layout.addWidget(self.create_legend_row("#E20015", "Cavity Block (Exploded Upwards)"))
        panel_layout.addWidget(self.create_legend_row("#004CFF", "Core Block (Exploded Downwards)"))
        
        panel_layout.addStretch()
        layout.addWidget(panel)

    def render_z_14_view(self):
        print("render_z_14_view starting", flush=True)
        if not self.engine or not self.engine.part or not self.analysis_result:
            return
            
        self.display.EraseAll()
        self.display.SetSelectionModeFace()
        
        # 1. Bounding Box
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        # 2. Part = Semi-Transparent Gray
        color = Quantity_Color(0.85, 0.85, 0.85, Quantity_TOC_RGB)
        ais_shape_list = self.display.DisplayShape(self.engine.part.shape, update=False)
        for ais_shape in ais_shape_list:
            ais_shape.SetColor(color)
            ais_shape.SetTransparency(0.7)
            
        # 3. Parting Line Wires at Z = 14.0 using BRepAlgoAPI_Section
        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopoDS import topods
        
        pln = gp_Pln(gp_Pnt(0, 0, 14.0), gp_Dir(0, 0, 1))
        section = BRepAlgoAPI_Section(self.engine.part.shape, pln, True)
        section.Build()
        
        sec_explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
        yellow_green = Quantity_Color(0.8, 1.0, 0.0, Quantity_TOC_RGB)
        aspect = Prs3d_LineAspect(yellow_green, Aspect_TOL_SOLID, 4.0)
        while sec_explorer.More():
            edge = topods.Edge(sec_explorer.Current())
            ais_edges = self.display.DisplayShape(edge, update=False)
            for ais_edge in ais_edges:
                ais_edge.Attributes().SetLineAspect(aspect)
                ais_edge.Attributes().SetWireAspect(aspect)
                ais_edge.Attributes().SetFreeBoundaryAspect(aspect)
                ais_edge.Attributes().SetUnFreeBoundaryAspect(aspect)
                self.display.Context.Redisplay(ais_edge, False)
            sec_explorer.Next()
                
        # 4. Parting Sheet at Z = 14.0
        bx_min = xmin - dx * 0.15
        bx_max = xmax + dx * 0.15
        by_min = ymin - dy * 0.15
        by_max = ymax + dy * 0.15
        margin = dx * 0.08
        
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        parting_sheet = BRepPrimAPI_MakeBox(
            gp_Pnt(bx_min - margin, by_min - margin, 14.0 - 0.15),
            gp_Pnt(bx_max + margin, by_max + margin, 14.0 + 0.15)
        ).Shape()
        
        cyan = Quantity_Color(0.0, 1.0, 1.0, Quantity_TOC_RGB)
        ais_sheet = self.display.DisplayColoredShape(parting_sheet, cyan, update=False)
        for ais_sh in (ais_sheet if isinstance(ais_sheet, list) else [ais_sheet]):
            ais_sh.SetTransparency(0.7)
            
        # 5. Exploded Core & Cavity blocks at Z = 14.0
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCC.Core.gp import gp_Trsf, gp_Vec
        
        cavity_box = BRepPrimAPI_MakeBox(
            gp_Pnt(bx_min, by_min, 14.0),
            gp_Pnt(bx_max, by_max, zmax + dz * 0.3)
        ).Shape()
        
        core_box = BRepPrimAPI_MakeBox(
            gp_Pnt(bx_min, by_min, zmin - dz * 0.3),
            gp_Pnt(bx_max, by_max, 14.0)
        ).Shape()
        
        try:
            cavity_cut = BRepAlgoAPI_Cut(cavity_box, self.engine.part.shape).Shape()
            core_cut = BRepAlgoAPI_Cut(core_box, self.engine.part.shape).Shape()
        except Exception as e:
            print("Boolean cut failed, falling back to blank blocks:", e)
            cavity_cut = cavity_box
            core_cut = core_box
            
        trans_z = dz * 0.4
        
        trsf_cavity = gp_Trsf()
        trsf_cavity.SetTranslation(gp_Vec(0, 0, trans_z))
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True).Shape()
        
        trsf_core = gp_Trsf()
        trsf_core.SetTranslation(gp_Vec(0, 0, -trans_z))
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True).Shape()
        
        cavity_color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB)
        ais_cavity = self.display.DisplayColoredShape(cavity_exploded, cavity_color, update=False)
        for ais_c in (ais_cavity if isinstance(ais_cavity, list) else [ais_cavity]):
            ais_c.SetTransparency(0.7)
            
        core_color = Quantity_Color(0.2, 0.4, 0.9, Quantity_TOC_RGB)
        ais_core = self.display.DisplayColoredShape(core_exploded, core_color, update=False)
        for ais_co in (ais_core if isinstance(ais_core, list) else [ais_core]):
            ais_co.SetTransparency(0.7)
            
        # 6. Direction Arrow
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        cz = (zmin + zmax) / 2.0
        arrow_shape = self.create_arrow([cx, cy, cz], [0, 0, 1], dz * 0.4)
        if arrow_shape:
            self.display.DisplayColoredShape(arrow_shape, cyan, update=False)
            
        print("render_z_14_view completed", flush=True)

    def on_demo_mode_changed(self, text):
        self.populate_demo_cases()

    def populate_demo_cases(self):
        self.demo_case_combo.blockSignals(True)
        self.demo_case_combo.clear()
        mode = self.demo_mode_combo.currentText()
        if mode == "Mold Opening Axis Analysis":
            self.demo_case_combo.addItems(["X-Axis Opening", "Y-Axis Opening", "Z-Axis Opening"])
        else:
            self.demo_case_combo.addItems(["Top", "Upper", "Middle (Optimal) [Auto]", "Lower", "Bottom"])
        self.demo_case_combo.blockSignals(False)
        # Trigger update
        self.on_demo_case_changed(self.demo_case_combo.currentText())

    def update_demo_comparison_table(self):
        if not self.analysis_result or not self.engine:
            self.demo_comp_table.setText("No analysis run.")
            return
            
        axes = ["X", "Y", "Z"]
        
        # Build HTML Table
        html = """
        <table width="100%" style="border-collapse: collapse; color: #f8f8f2;">
          <tr style="background-color: #181825; font-weight: bold; border-bottom: 2px solid #3d3d5c;">
            <th style="padding: 4px; text-align: left;">Axis (Optimal Plane)</th>
            <th style="padding: 4px; text-align: right;">Undercuts</th>
            <th style="padding: 4px; text-align: right;">Area (mm²)</th>
            <th style="padding: 4px; text-align: right;">Crossing</th>
            <th style="padding: 4px; text-align: right;">Complexity</th>
            <th style="padding: 4px; text-align: right;">Score</th>
            <th style="padding: 4px; text-align: center;">Status</th>
          </tr>
        """
            
        for axis_name in axes:
            best_plane, best_score, stats = self.engine.optimize_parting_plane_for_axis(axis_name)
            classification = stats["classification"]
            
            if classification == "MOLDABLE":
                status_color = "#2e7d32"
                status_text = "MOLDABLE"
            elif classification == "PARTIALLY MOLDABLE":
                status_color = "#f9a825"
                status_text = "PARTIAL"
            elif classification == "SIDE ACTION REQUIRED":
                status_color = "#ff9800"
                status_text = "SLIDERS"
            else:
                status_color = "#c62828"
                status_text = "LOCK"
                
            html += f"""
            <tr style="border-bottom: 1px solid #2d2d44;">
              <td style="padding: 4px; font-weight: bold;">{axis_name}-Axis ({axis_name} = {best_plane:.2f} mm)</td>
              <td style="padding: 4px; text-align: right;">{stats['undercut_count']}</td>
              <td style="padding: 4px; text-align: right;">{stats['undercut_area']:.1f}</td>
              <td style="padding: 4px; text-align: right;">{stats['crossing_faces']}</td>
              <td style="padding: 4px; text-align: right;">{stats['complexity']:.1f}</td>
              <td style="padding: 4px; text-align: right; font-weight: bold;">{best_score:.1f}</td>
              <td style="padding: 4px; text-align: center;"><span style="background-color: {status_color}; color: white; padding: 2px 4px; border-radius: 3px; font-size: 10px; font-weight: bold;">{status_text}</span></td>
            </tr>
            """
        html += "</table>"
        self.demo_comp_table.setText(html)

    def on_demo_case_changed(self, text):
        if not text or not self.analysis_result or not self.engine:
            return
            
        mode = self.demo_mode_combo.currentText()
        
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        total_area = sum(f.area for f in self.engine.part.faces) or 1.0
        total_faces = len(self.engine.part.faces) or 1.0
            
        if mode == "Mold Opening Axis Analysis":
            if text == "X-Axis Opening":
                axis_name = "X"
                d_vec = [1.0, 0.0, 0.0]
                cav_dir, core_dir = "+X", "-X"
            elif text == "Y-Axis Opening":
                axis_name = "Y"
                d_vec = [0.0, 1.0, 0.0]
                cav_dir, core_dir = "+Y", "-Y"
            else:
                axis_name = "Z"
                d_vec = [0.0, 0.0, 1.0]
                cav_dir, core_dir = "+Z", "-Z"
                
            best_plane, best_score, best_stats = self.engine.optimize_parting_plane_for_axis(axis_name)
            split_val = best_plane
            stats = best_stats
            score = best_score
            complexity = stats["complexity"]
            classification = stats["classification"]
            
            # Formulate detailed justification
            if axis_name == "Z":
                reason = (
                    f"The selected Z = {best_plane:.2f} mm split minimizes undercut area ({stats['undercut_area']:.1f} mm²), "
                    f"reduces faces requiring geometric splitting ({stats['crossing_faces']}), and produces the most balanced core/cavity separation. "
                    f"This results in the highest moldability score ({best_score:.1f}) among all candidate planes."
                )
            else:
                reason = (
                    f"The selected {axis_name} = {best_plane:.2f} mm split minimizes undercut area, reduces faces requiring geometric splitting, "
                    f"and produces the best balanced separation along the {axis_name}-axis. However, side walls, ribs, "
                    f"slots, and internal features create mechanical lock under standard two-plate mold separation, "
                    f"requiring side actions/sliders."
                )
        else:
            d_vec = [0, 0, 1]
            axis_name = "Z"
            best_plane, best_score, best_stats_opt = self.engine.optimize_parting_plane_for_axis("Z")
            
            planes = {
                "Top": (zmin + 0.95 * dz, "Parting plane sits at the very top. Cavity block is empty, forcing all features into the core block with deep trapped pockets.", "+Z", "-Z"),
                "Upper": (zmin + 0.75 * dz, "Parting plane cuts near the logo. Creates a thin cavity plate and leaves deep core pockets, raising mold cost.", "+Z", "-Z"),
                "Middle (Optimal) [Auto]": (best_plane, "Parting plane is placed at the optimal flange split height. Minimizes undercut area, gives balanced mold split, and yields flat closed parting loops.", "+Z", "-Z"),
                "Lower": (zmin + 0.25 * dz, "Parting plane cuts lower cap ribs. Traps leg geometry on the cavity side, causing pull interference.", "+Z", "-Z"),
                "Bottom": (zmin + 0.05 * dz, "Parting plane is at the very bottom. Cavity block has to form all walls, creating deep trapped undercuts on the cavity side.", "+Z", "-Z")
            }
            split_val, reason, cav_dir, core_dir = planes.get(text, (best_plane, "", "+Z", "-Z"))
            
            stats = self.engine.evaluate_pull_direction_and_split(d_vec, split_val)
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
            
            # Classification based on engineering rules (on this evaluated plane's stats)
            if stats["undercut_count"] == 0 and stats["crossing_faces"] == 0:
                classification = "MOLDABLE"
            elif ratio < 0.05 and cross_ratio < 0.25 and cnt_ratio < 0.30:
                classification = "PARTIALLY MOLDABLE"
            elif ratio < 0.12 and cnt_ratio < 0.40:
                classification = "SIDE ACTION REQUIRED"
            else:
                classification = "NOT MOLDABLE"
            
        self.demo_val_cavity_dir.setText(cav_dir)
        self.demo_val_core_dir.setText(core_dir)
        
        self.demo_val_plane_pos.setText(f"{axis_name} = {split_val:.2f} mm")
        self.demo_val_classification.setText(classification)
        self.demo_val_score.setText(f"{score:.2f} / 100")
        self.demo_val_undercuts.setText(str(stats["undercut_count"]))
        self.demo_val_area.setText(f"{stats['undercut_area']:.2f} mm²")
        self.demo_val_crossing.setText(str(stats["crossing_faces"]))
        self.demo_val_core_faces.setText(str(stats["core_faces"]))
        self.demo_val_cavity_faces.setText(str(stats["cavity_faces"]))
        self.demo_val_complexity.setText(f"{complexity:.2f}")
        self.demo_val_reason.setText(reason)
        
        if classification == "MOLDABLE":
            self.badge_status.setText("MOLDABLE")
            self.badge_status.setStyleSheet("background-color: #2e7d32; color: white; border-radius: 4px; font-weight: bold;")
        elif classification == "PARTIALLY MOLDABLE":
            self.badge_status.setText("PARTIALLY MOLDABLE")
            self.badge_status.setStyleSheet("background-color: #f9a825; color: black; border-radius: 4px; font-weight: bold;")
        elif classification == "SIDE ACTION REQUIRED":
            self.badge_status.setText("SIDE ACTION REQUIRED")
            self.badge_status.setStyleSheet("background-color: #ff9800; color: white; border-radius: 4px; font-weight: bold;")
        else:
            self.badge_status.setText("NOT MOLDABLE")
            self.badge_status.setStyleSheet("background-color: #c62828; color: white; border-radius: 4px; font-weight: bold;")
            
        self.render_demo_viewport(d_vec, split_val, stats["undercut_faces"], mode)

    def render_demo_viewport(self, d_vec, split_val, undercut_faces, mode):
        if not self.engine or not self.engine.part:
            return
            
        self.display.EraseAll()
        self.display.SetSelectionModeFace()
        
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        dx = xmax - xmin
        dy = ymax - ymin
        dz = zmax - zmin
        
        bx_min = xmin - dx * 0.15
        bx_max = xmax + dx * 0.15
        by_min = ymin - dy * 0.15
        by_max = ymax + dy * 0.15
        bz_min = zmin - dz * 0.15
        bz_max = zmax + dz * 0.15
        
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Trsf
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
        
        # Split along projection
        if abs(d_vec[0]) > 0.9:
            # X direction split
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(split_val, by_min, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(split_val, by_max, bz_max)).Shape()
            trans_vec = gp_Vec(dx * 1.3 if d_vec[0] > 0 else -dx * 1.3, 0, 0)
        elif abs(d_vec[1]) > 0.9:
            # Y direction split
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, split_val, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(bx_max, split_val, bz_max)).Shape()
            trans_vec = gp_Vec(0, dy * 1.3 if d_vec[1] > 0 else -dy * 1.3, 0)
        else:
            # Z direction split
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, split_val), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(bx_max, by_max, split_val)).Shape()
            trans_vec = gp_Vec(0, 0, dz * 1.3 if d_vec[2] > 0 else -dz * 1.3)
            
        try:
            cavity_cut = BRepAlgoAPI_Cut(cavity_box, self.engine.part.shape).Shape()
            core_cut = BRepAlgoAPI_Cut(core_box, self.engine.part.shape).Shape()
        except Exception as e:
            print("Boolean cut failed, falling back to blank blocks:", e)
            cavity_cut = cavity_box
            core_cut = core_box
            
        trsf_cavity = gp_Trsf()
        trsf_cavity.SetTranslation(trans_vec)
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True).Shape()
        
        trsf_core = gp_Trsf()
        trsf_core.SetTranslation(-trans_vec)
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True).Shape()
        
        if mode == "Parting Plane Analysis" or abs(d_vec[2]) > 0.9:
            margin = dx * 0.08
            if abs(d_vec[0]) > 0.9:
                parting_sheet = BRepPrimAPI_MakeBox(gp_Pnt(split_val - 0.2, by_min - margin, bz_min - margin), gp_Pnt(split_val + 0.2, by_max + margin, bz_max + margin)).Shape()
            elif abs(d_vec[1]) > 0.9:
                parting_sheet = BRepPrimAPI_MakeBox(gp_Pnt(bx_min - margin, split_val - 0.2, bz_min - margin), gp_Pnt(bx_max + margin, split_val + 0.2, bz_max + margin)).Shape()
            else:
                parting_sheet = BRepPrimAPI_MakeBox(gp_Pnt(bx_min - margin, by_min - margin, split_val - 0.2), gp_Pnt(bx_max + margin, by_max + margin, split_val + 0.2)).Shape()
            
            cyan = Quantity_Color(0.0, 1.0, 1.0, Quantity_TOC_RGB)
            ais_sheet = self.display.DisplayColoredShape(parting_sheet, cyan, update=False)
            for ais_sh in (ais_sheet if isinstance(ais_sheet, list) else [ais_sheet]):
                ais_sh.SetTransparency(0.75)
                
        cavity_color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB)
        ais_cavity = self.display.DisplayColoredShape(cavity_exploded, cavity_color, update=False)
        for ais_c in (ais_cavity if isinstance(ais_cavity, list) else [ais_cavity]):
            ais_c.SetTransparency(0.65)
            
        core_color = Quantity_Color(0.2, 0.4, 0.9, Quantity_TOC_RGB)
        ais_core = self.display.DisplayColoredShape(core_exploded, core_color, update=False)
        for ais_co in (ais_core if isinstance(ais_core, list) else [ais_core]):
            ais_co.SetTransparency(0.65)
            
        yellow_part = Quantity_Color(0.9, 0.9, 0.2, Quantity_TOC_RGB)
        red_undercut = Quantity_Color(1.0, 0.0, 0.0, Quantity_TOC_RGB)
        
        undercut_set = set(undercut_faces)
        for face in self.engine.part.faces:
            face_shape = self.engine.face_map[face.face_id]
            is_uc = face.face_id in undercut_set
            
            color = red_undercut if is_uc else yellow_part
            ais_f = self.display.DisplayColoredShape(face_shape, color, update=False)
            if not is_uc:
                for a_f in (ais_f if isinstance(ais_f, list) else [ais_f]):
                    a_f.SetTransparency(0.4)
            else:
                for a_f in (ais_f if isinstance(ais_f, list) else [ais_f]):
                    a_f.SetDisplayMode(1)
                    
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        cz = (zmin + zmax) / 2.0
        diag = math.sqrt(dx**2 + dy**2 + dz**2)
        
        # Pull arrows for BOTH halves: Cavity (+d_vec) and Core (-d_vec)
        arrow_color = Quantity_Color(0.0, 1.0, 1.0, Quantity_TOC_RGB) # Cyan
        
        # Cavity Arrow
        arrow_cavity = self.create_arrow([cx, cy, cz], d_vec, diag * 0.35)
        if arrow_cavity:
            self.display.DisplayColoredShape(arrow_cavity, arrow_color, update=False)
            
        # Core Arrow
        opp_d_vec = [-d_vec[0], -d_vec[1], -d_vec[2]]
        arrow_core = self.create_arrow([cx, cy, cz], opp_d_vec, diag * 0.35)
        if arrow_core:
            self.display.DisplayColoredShape(arrow_core, arrow_color, update=False)
            
        self.display.View.Redraw()

    def create_arrow(self, centroid, direction, length):
        dir_norm = np.linalg.norm(direction)
        if dir_norm == 0:
            return None
        d = direction / dir_norm
        
        r_cyl = length * 0.02
        h_cyl = length * 0.7
        r_cone = length * 0.05
        h_cone = length * 0.3
        
        try:
            # Cylinder along Z starting at (0,0,0)
            cyl_ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
            cylinder = BRepPrimAPI_MakeCylinder(cyl_ax, r_cyl, h_cyl).Shape()
            
            # Cone along Z starting at (0,0,h_cyl)
            cone_ax = gp_Ax2(gp_Pnt(0, 0, h_cyl), gp_Dir(0, 0, 1))
            cone = BRepPrimAPI_MakeCone(cone_ax, r_cone, 0.0, h_cone).Shape()
            
            # Fuse them
            arrow = BRepAlgoAPI_Fuse(cylinder, cone).Shape()
            
            # Calculate rotation from (0,0,1) to d
            v1 = np.array([0.0, 0.0, 1.0])
            v2 = np.array(d)
            
            trsf = gp_Trsf()
            dot = np.dot(v1, v2)
            cross = np.cross(v1, v2)
            cross_len = np.linalg.norm(cross)
            
            if cross_len < 1e-6:
                if dot < 0:
                    trsf.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1, 0, 0)), math.pi)
            else:
                axis = gp_Dir(cross[0], cross[1], cross[2])
                angle = math.acos(max(-1.0, min(1.0, dot)))
                trsf.SetRotation(gp_Ax1(gp_Pnt(0,0,0), axis), angle)
                
            # Translate so that the center of the arrow is at the centroid
            half_len = (h_cyl + h_cone) / 2.0
            tx = centroid[0] - d[0] * half_len
            ty = centroid[1] - d[1] * half_len
            tz = centroid[2] - d[2] * half_len
            
            trsf_trans = gp_Trsf()
            trsf_trans.SetTranslation(gp_Vec(tx, ty, tz))
            
            # Combine: first rotate, then translate
            trsf_trans.Multiply(trsf)
            
            transformed_arrow = BRepBuilderAPI_Transform(arrow, trsf_trans, True).Shape()
            return transformed_arrow
        except Exception as e:
            print("Error creating arrow:", e)
            return None

    def on_select(self, selected_shapes, x, y):
        if not selected_shapes or not self.analysis_result or not self.engine:
            return
        
        shape = selected_shapes[0]
        if shape.ShapeType() == 4:  # TopAbs_FACE
            face = topods.Face(shape)
            found_id = None
            for fid, f_obj in self.engine.face_map.items():
                if f_obj.IsSame(face):
                    found_id = fid
                    break
            
            if found_id is not None:
                # Find draft angle
                draft_val = None
                for d in self.analysis_result.draft_analysis["details"]:
                    if d["face_id"] == found_id:
                        draft_val = d["draft_angle"]
                        break
                
                # Find mold split classification
                split_val = None
                for d in self.analysis_result.mold_split["details"]:
                    if d["face_id"] == found_id:
                        split_val = d["classification"]
                        break
                        
                is_undercut = found_id in self.analysis_result.undercuts["faces"]
                is_silhouette = found_id in self.analysis_result.mold_split["silhouette_faces"]
                
                status_msg = f"Selected Face ID: {found_id} | "
                if draft_val is not None:
                    status_msg += f"Draft Angle: {draft_val:.2f}° | "
                if split_val is not None:
                    status_msg += f"Group: {split_val} | "
                status_msg += f"Undercut: {'Yes' if is_undercut else 'No'} | "
                status_msg += f"Silhouette: {'Yes' if is_silhouette else 'No'}"
                
                self.statusBar().showMessage(status_msg)

    def on_export_json(self):
        if not self.analysis_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON Report", f"dfm_report_{os.path.splitext(self.analysis_result.filename)[0]}.json", "JSON files (*.json)"
        )
        if file_path:
            try:
                import report_generator
                report_generator.export_json(file_path, self.analysis_result)
                QMessageBox.information(self, "Success", f"JSON report successfully exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export JSON report:\n{str(e)}")

    def on_export_pdf(self):
        if not self.analysis_result:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", f"dfm_report_{os.path.splitext(self.analysis_result.filename)[0]}.pdf", "PDF files (*.pdf)"
        )
        if file_path:
            try:
                import report_generator
                report_generator.export_pdf(file_path, self.analysis_result)
                QMessageBox.information(self, "Success", f"PDF report successfully exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export PDF report:\n{str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DFMMainWindow()
    window.show()
    window.init_viewer()
    sys.exit(app.exec_())
