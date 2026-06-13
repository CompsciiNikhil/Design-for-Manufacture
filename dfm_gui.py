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
                             QSplitter, QMessageBox, QSlider, QScrollArea,
                             QStackedWidget, QGroupBox, QDialog, QProgressBar,
                             QToolButton, QGridLayout)
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
from dfm_engine import DFMEngine, MATERIAL_THRESHOLDS

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
QFrame#dropzone {
    border: 2px dashed #585b70;
    border-radius: 8px;
    background-color: #181825;
}
QFrame#dropzone:hover {
    border-color: #e20015;
    background-color: #252538;
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
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background-color: #181825;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #3d3d5c;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background-color: #e20015;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    border: none;
}
"""

class WelcomeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setAcceptDrops(True)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel("📥 DfM Intelligence Agent")
        title_label.setObjectName("welcome_title")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #e20015;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        subtitle = QLabel("Automated Moldability Analysis")
        subtitle.setStyleSheet("font-size: 14px; color: #a0a0c0; font-style: italic;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        self.dropzone = QFrame()
        self.dropzone.setObjectName("dropzone")
        self.dropzone.setFrameStyle(QFrame.StyledPanel)
        
        dropzone_layout = QVBoxLayout(self.dropzone)
        dropzone_layout.setContentsMargins(30, 40, 30, 40)
        dropzone_layout.setSpacing(15)
        dropzone_layout.setAlignment(Qt.AlignCenter)
        
        drop_icon = QLabel("📂")
        drop_icon.setStyleSheet("font-size: 48px;")
        drop_icon.setAlignment(Qt.AlignCenter)
        dropzone_layout.addWidget(drop_icon)
        
        drop_lbl = QLabel("Drag & Drop STEP (.stp / .step) file here")
        drop_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        drop_lbl.setAlignment(Qt.AlignCenter)
        dropzone_layout.addWidget(drop_lbl)
        
        or_lbl = QLabel("— OR —")
        or_lbl.setStyleSheet("font-size: 12px; color: #7f7f8f;")
        or_lbl.setAlignment(Qt.AlignCenter)
        dropzone_layout.addWidget(or_lbl)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.setAlignment(Qt.AlignCenter)
        
        self.select_btn = QPushButton("Select STEP File")
        self.select_btn.setStyleSheet("padding: 10px 20px; font-size: 13px;")
        self.select_btn.clicked.connect(self.on_select_file)
        
        self.sample_btn = QPushButton("Load Sample Part")
        self.sample_btn.setStyleSheet("background-color: #252538; border: 1px solid #e20015; padding: 10px 20px; font-size: 13px;")
        self.sample_btn.clicked.connect(self.on_load_sample)
        
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.sample_btn)
        dropzone_layout.addLayout(btn_layout)
        
        layout.addWidget(self.dropzone)
        
        info_lbl = QLabel("Supported formats: STEP AP203 / AP214 / AP242 (.stp, .step)")
        info_lbl.setStyleSheet("font-size: 11px; color: #7f7f8f;")
        info_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_lbl)
        
        features_frame = QFrame()
        features_frame.setStyleSheet("background-color: #181825; border: 1px solid #3d3d5c; border-radius: 6px; padding: 15px;")
        feat_layout = QHBoxLayout(features_frame)
        feat_layout.setSpacing(20)
        
        def add_feature_card(title, desc):
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(5)
            t = QLabel(title)
            t.setStyleSheet("font-weight: bold; color: #e20015; font-size: 13px;")
            d = QLabel(desc)
            d.setStyleSheet("color: #a0a0a0; font-size: 11px;")
            d.setWordWrap(True)
            l.addWidget(t)
            l.addWidget(d)
            feat_layout.addWidget(w)
            
        add_feature_card("📐 Geometry & Draft", "Scans face orientations to detect undercut sections and draft violations.")
        add_feature_card("⚙️ Direction Optimization", "Evaluates 500 candidate directions to select the best mold pull axis.")
        add_feature_card("🔗 Parting Line Loops", "Generates watertight splitting curves and projects them onto standard blocks.")
        add_feature_card("📦 Core & Cavity Splitting", "Separates core and cavity blocks with animations along the optimized pull vector.")
        
        layout.addWidget(features_frame)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.stp', '.step')) for url in urls):
                event.acceptProposedAction()
                self.dropzone.setStyleSheet("border-color: #e20015; background-color: #212135;")
                
    def dragLeaveEvent(self, event):
        self.dropzone.setStyleSheet("")
        
    def dropEvent(self, event):
        self.dropzone.setStyleSheet("")
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.stp', '.step')):
                self.parent_window.load_file(file_path)
                break
                
    def on_select_file(self):
        self.parent_window.on_open_file()
        
    def on_load_sample(self):
        sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "Part1.stp")
        if os.path.exists(sample_path):
            self.parent_window.load_file(sample_path)
        else:
            QMessageBox.warning(self, "Warning", f"Sample part file not found at:\n{sample_path}")

class DFMProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setWindowTitle("DfM Intelligence Agent")
        self.setFixedSize(400, 420)
        self.setStyleSheet("""
            QDialog { background-color: #1a1c2a; border: 1px solid #3d3d5c; border-radius: 8px; }
            QLabel { color: #f8f8f2; }
            QLabel#title { font-size: 15px; font-weight: bold; color: #e20015; }
            QLabel#phase { color: #bd93f9; font-style: italic; }
            QProgressBar { background-color: #181825; border: 1px solid #3d3d5c; border-radius: 4px; text-align: center; color: white; }
            QProgressBar::chunk { background-color: #e20015; border-radius: 3px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_lbl = QLabel("Manufacturing Analysis in Progress")
        title_lbl.setObjectName("title")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        layout.addWidget(self.progress_bar)
        
        self.phase_lbl = QLabel("Initializing calculations...")
        self.phase_lbl.setObjectName("phase")
        self.phase_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.phase_lbl)
        
        stages_box = QGroupBox("Analysis Pipeline Stages")
        stages_box.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 15px; padding-top: 15px; color: #e20015; }")
        stages_layout = QVBoxLayout(stages_box)
        stages_layout.setContentsMargins(15, 10, 15, 10)
        stages_layout.setSpacing(6)
        
        self.stages = [
            "STEP File Loaded",
            "Geometry Parsed",
            "Topology Extracted",
            "Mold Direction Optimized",
            "Draft Analysis Complete",
            "Undercut Detection Complete",
            "Parting Plane Optimized",
            "Mold Split Generated",
            "Report Ready"
        ]
        self.stage_labels = []
        for stage in self.stages:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            icon = QLabel("⚪")
            icon.setFixedWidth(20)
            lbl = QLabel(stage)
            lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
            
            row_layout.addWidget(icon)
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            stages_layout.addWidget(row)
            
            self.stage_labels.append((icon, lbl))
            
        layout.addWidget(stages_box)
        
        self.close_btn = QPushButton("Open Results")
        self.close_btn.setStyleSheet("padding: 8px;")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
    def update_progress(self, percent, phase_text, completed_stages_count):
        self.progress_bar.setValue(percent)
        self.phase_lbl.setText(phase_text)
        
        for i in range(len(self.stages)):
            icon, lbl = self.stage_labels[i]
            if i < completed_stages_count:
                icon.setText("🟢")
                lbl.setStyleSheet("color: #28a745; font-weight: bold; font-size: 11px;")
            elif i == completed_stages_count:
                icon.setText("▶")
                lbl.setStyleSheet("color: #bd93f9; font-weight: bold; font-size: 11px;")
            else:
                icon.setText("⚪")
                lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
                
    def finish_progress(self):
        self.progress_bar.setValue(100)
        self.phase_lbl.setText("Analysis complete!")
        for icon, lbl in self.stage_labels:
            icon.setText("🟢")
            lbl.setStyleSheet("color: #28a745; font-weight: bold; font-size: 11px;")
        self.close_btn.setEnabled(True)
        self.close_btn.setStyleSheet("background-color: #28a745; font-weight: bold; color: white;")


class DFMMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DfM Intelligence Agent")
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
        
        title_label = QLabel("DfM Intelligence Agent")
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
        # Stacked Widget to hold WelcomeWidget vs Main Layout
        self.stacked_widget = QStackedWidget()
        
        # 1. WelcomeWidget
        self.welcome_widget = WelcomeWidget(self)
        self.stacked_widget.addWidget(self.welcome_widget)
        
        # 2. Main content splitter (CAD Viewport + Tab Dashboard)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        
        # Viewport container widget
        viewport_container = QWidget()
        v_layout = QVBoxLayout(viewport_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        
        # View Preset Toolbar
        view_toolbar = QFrame()
        view_toolbar.setStyleSheet("background-color: #181825; border-bottom: 1px solid #3d3d5c; padding: 4px;")
        view_toolbar.setFixedHeight(40)
        vt_layout = QHBoxLayout(view_toolbar)
        vt_layout.setContentsMargins(10, 2, 10, 2)
        vt_layout.setSpacing(8)
        
        title_vt = QLabel("CAD Camera Presets:")
        title_vt.setStyleSheet("font-size: 11px; font-weight: bold; color: #e20015; margin-right: 5px;")
        vt_layout.addWidget(title_vt)
        
        def create_view_btn(text, slot):
            btn = QToolButton()
            btn.setText(text)
            btn.setStyleSheet("QToolButton { background-color: #252538; color: white; border: 1px solid #3d3d5c; border-radius: 3px; padding: 4px 10px; font-size: 11px; } QToolButton:hover { background-color: #e20015; border-color: #e20015; }")
            btn.clicked.connect(slot)
            return btn
            
        vt_layout.addWidget(create_view_btn("🏠 Home", self.on_view_home))
        vt_layout.addWidget(create_view_btn("📐 Isometric", self.on_view_iso))
        vt_layout.addWidget(create_view_btn("⬆️ Top", self.on_view_top))
        vt_layout.addWidget(create_view_btn("⬇️ Front", self.on_view_front))
        vt_layout.addWidget(create_view_btn("➡️ Side", self.on_view_side))
        vt_layout.addWidget(create_view_btn("🔍 Fit View", self.on_reset_view))
        vt_layout.addStretch()
        
        v_layout.addWidget(view_toolbar)
        
        # 3D Viewport container
        self.canvas = CustomViewer3d(viewport_container)
        v_layout.addWidget(self.canvas)
        
        self.main_splitter.addWidget(viewport_container)
        
        # Tab Widget for different views
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # 0. Overview Tab
        self.overview_tab = QWidget()
        self.setup_overview_tab()
        self.tabs.addTab(self.overview_tab, "Overview")
        
        # 1. Draft Analysis Tab
        self.draft_tab = QWidget()
        self.setup_draft_tab()
        self.tabs.addTab(self.draft_tab, "Draft Analysis")
        
        # 2. Undercuts Tab
        self.undercut_tab = QWidget()
        self.setup_undercut_tab()
        self.tabs.addTab(self.undercut_tab, "Undercuts")
        
        # 3. Parting Line Tab
        self.parting_tab = QWidget()
        self.setup_parting_tab()
        self.tabs.addTab(self.parting_tab, "Parting Line")
        
        # 4. Moldability Advisor Tab
        self.advisor_tab = QWidget()
        self.setup_advisor_tab()
        self.tabs.addTab(self.advisor_tab, "Moldability Advisor")
        
        # 5. Reports Tab
        self.reports_tab = QWidget()
        self.setup_reports_tab()
        self.tabs.addTab(self.reports_tab, "Reports")
        
        self.main_splitter.addWidget(self.tabs)
        
        # Set sizes (70% and 30%)
        self.main_splitter.setSizes([840, 360])
        
        self.stacked_widget.addWidget(self.main_splitter)
        self.main_layout.addWidget(self.stacked_widget)
        
        # Initially show welcome screen
        self.stacked_widget.setCurrentIndex(0)

    def create_scrollable_layout(self, tab_widget):
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(15, 15, 15, 15)
        scroll_layout.setSpacing(10)
        
        scroll.setWidget(scroll_content)
        tab_layout.addWidget(scroll)
        
        return scroll_layout

    def create_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("No STEP file loaded.")

    def setup_overview_tab(self):
        scroll_layout = self.create_scrollable_layout(self.overview_tab)
        
        # 1. Classification banner card
        banner_frame = QFrame()
        banner_frame.setObjectName("banner_card")
        banner_frame.setStyleSheet("background-color: #252538; border: 1px solid #3d3d5c; border-radius: 6px; padding: 12px;")
        bf_layout = QVBoxLayout(banner_frame)
        bf_layout.setContentsMargins(10, 10, 10, 10)
        bf_layout.setSpacing(8)
        
        status_row = QHBoxLayout()
        status_lbl = QLabel("Design for Manufacturability Status:")
        status_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #a0a0c0;")
        self.overview_status_badge = QLabel("-")
        self.overview_status_badge.setFixedWidth(180)
        self.overview_status_badge.setFixedHeight(26)
        self.overview_status_badge.setAlignment(Qt.AlignCenter)
        self.overview_status_badge.setStyleSheet("font-weight: bold; font-size: 12px; border-radius: 4px; background-color: #444454; color: white;")
        
        status_row.addWidget(status_lbl)
        status_row.addWidget(self.overview_status_badge)
        status_row.addStretch()
        bf_layout.addLayout(status_row)
        
        # Action Recommended Row
        self.overview_action_lbl = QLabel("No analysis run yet.")
        self.overview_action_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #e20015; margin-top: 5px;")
        bf_layout.addWidget(self.overview_action_lbl)
        
        # Structured Assistant Explanation
        self.overview_advice_widget = QWidget()
        adv_lyt = QVBoxLayout(self.overview_advice_widget)
        adv_lyt.setContentsMargins(0, 5, 0, 0)
        adv_lyt.setSpacing(6)
        
        self.adv_what = QLabel("• What: -")
        self.adv_why = QLabel("• Why: -")
        self.adv_importance = QLabel("• Importance: -")
        self.adv_action = QLabel("• Improvement: -")
        
        for lbl in [self.adv_what, self.adv_why, self.adv_importance, self.adv_action]:
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 11px; color: #c0c0c0;")
            adv_lyt.addWidget(lbl)
            
        bf_layout.addWidget(self.overview_advice_widget)
        scroll_layout.addWidget(banner_frame)
        
        # 2. KPI Cards Grid
        kpi_group = QGroupBox("Key Manufacturing KPIs")
        kpi_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 10px; padding-top: 15px; color: #e20015; }")
        kpi_grid = QGridLayout(kpi_group)
        kpi_grid.setSpacing(12)
        kpi_grid.setContentsMargins(10, 10, 10, 10)
        
        def create_kpi_card(title):
            card = QFrame()
            card.setStyleSheet("background-color: #1a1c2a; border: 1px solid #3d3d5c; border-radius: 6px; padding: 10px;")
            c_lyt = QVBoxLayout(card)
            c_lyt.setContentsMargins(8, 8, 8, 8)
            c_lyt.setSpacing(4)
            
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("font-size: 11px; color: #a0a0c0; text-transform: uppercase;")
            v_lbl = QLabel("-")
            v_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
            sub_lbl = QLabel("")
            sub_lbl.setStyleSheet("font-size: 10px; color: #7f7f8f;")
            
            c_lyt.addWidget(t_lbl)
            c_lyt.addWidget(v_lbl)
            c_lyt.addWidget(sub_lbl)
            return card, v_lbl, sub_lbl
            
        card_score, self.kpi_val_score, self.kpi_sub_score = create_kpi_card("Moldability Score")
        card_dir, self.kpi_val_dir, self.kpi_sub_dir = create_kpi_card("Recommended Pull Axis")
        card_undercut, self.kpi_val_undercut, self.kpi_sub_undercut = create_kpi_card("Undercut Area")
        card_parting, self.kpi_val_parting, self.kpi_sub_parting = create_kpi_card("Optimal Parting Plane")
        card_draft, self.kpi_val_draft, self.kpi_sub_draft = create_kpi_card("Draft Compliance")
        card_complexity, self.kpi_val_complexity, self.kpi_sub_complexity = create_kpi_card("Parting Line Complexity")
        
        kpi_grid.addWidget(card_score, 0, 0)
        kpi_grid.addWidget(card_dir, 0, 1)
        kpi_grid.addWidget(card_undercut, 1, 0)
        kpi_grid.addWidget(card_parting, 1, 1)
        kpi_grid.addWidget(card_draft, 2, 0)
        kpi_grid.addWidget(card_complexity, 2, 1)
        
        scroll_layout.addWidget(kpi_group)
        
        # 3. Model Spec panel
        spec_group = QGroupBox("CAD Geometry Specifications")
        spec_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 10px; padding-top: 15px; color: #e20015; }")
        spec_lyt = QVBoxLayout(spec_group)
        spec_lyt.setContentsMargins(10, 10, 10, 10)
        
        _, self.spec_val_filename = self.create_stat_row(spec_lyt, "Filename:")
        _, self.spec_val_faces = self.create_stat_row(spec_lyt, "Total Face Count:")
        _, self.spec_val_bbox_x = self.create_stat_row(spec_lyt, "Bounding Box X:")
        _, self.spec_val_bbox_y = self.create_stat_row(spec_lyt, "Bounding Box Y:")
        _, self.spec_val_bbox_z = self.create_stat_row(spec_lyt, "Bounding Box Z:")
        
        scroll_layout.addWidget(spec_group)
        scroll_layout.addStretch()

    def on_view_home(self):
        if hasattr(self, 'canvas') and self.canvas._display:
            self.canvas._display.View.SetProj(1, -1, 1)
            self.canvas._display.View.SetUp(0, 0, 1)
            self.canvas._display.FitAll()
            
    def on_view_iso(self):
        self.on_view_home()
        
    def on_view_top(self):
        if hasattr(self, 'canvas') and self.canvas._display:
            self.canvas._display.View.SetProj(0, 0, 1)
            self.canvas._display.View.SetUp(0, 1, 0)
            self.canvas._display.FitAll()
            
    def on_view_front(self):
        if hasattr(self, 'canvas') and self.canvas._display:
            self.canvas._display.View.SetProj(0, -1, 0)
            self.canvas._display.View.SetUp(0, 0, 1)
            self.canvas._display.FitAll()
            
    def on_view_side(self):
        if hasattr(self, 'canvas') and self.canvas._display:
            self.canvas._display.View.SetProj(1, 0, 0)
            self.canvas._display.View.SetUp(0, 0, 1)
            self.canvas._display.FitAll()

    def render_undercut_view(self):
        print("render_undercut_view starting", flush=True)
        if not self.analysis_result or not self.engine:
            return
        self.display.EraseAll()
        self.display.SetSelectionModeFace()
        draft_details = self.analysis_result.draft_analysis["details"]
        
        for detail in draft_details:
            face_id = detail["face_id"]
            draft_angle = detail["draft_angle"]
            face = self.engine.face_map[face_id]
            
            if draft_angle is not None and draft_angle < 0.0:
                color = Quantity_Color(0.0, 0.3, 1.0, Quantity_TOC_RGB) # Blue undercut
                ais_shapes = self.display.DisplayColoredShape(face, color, update=False)
                for ais_shape in ais_shapes:
                    ais_shape.SetDisplayMode(1)
            else:
                color = Quantity_Color(0.7, 0.7, 0.7, Quantity_TOC_RGB) # Neutral gray
                ais_shapes = self.display.DisplayColoredShape(face, color, update=False)
                for ais_shape in ais_shapes:
                    ais_shape.SetDisplayMode(1)
                    ais_shape.SetTransparency(0.6)
        
        self.display.FitAll()
        print("render_undercut_view completed", flush=True)

    def setup_draft_tab(self):
        scroll_layout = self.create_scrollable_layout(self.draft_tab)
        
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
        scroll_layout.addWidget(panel)

    def setup_undercut_tab(self):
        scroll_layout = self.create_scrollable_layout(self.undercut_tab)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Undercut & Mold Split")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        # Mode selector
        mode_lbl = QLabel("Viewport Visualization:")
        mode_lbl.setProperty("class", "lbl-text")
        self.undercut_view_combo = QComboBox()
        self.undercut_view_combo.addItems(["Highlight Undercuts", "Show Core/Cavity Split"])
        self.undercut_view_combo.currentTextChanged.connect(self.on_undercut_view_changed)
        
        panel_layout.addWidget(mode_lbl)
        panel_layout.addWidget(self.undercut_view_combo)
        
        title_stats = QLabel("Undercut Statistics")
        title_stats.setProperty("class", "section-title")
        panel_layout.addWidget(title_stats)
        
        _, self.undercut_val_count = self.create_stat_row(panel_layout, "Undercut Faces:")
        _, self.undercut_val_area = self.create_stat_row(panel_layout, "Undercut Area:")
        _, self.undercut_val_complexity = self.create_stat_row(panel_layout, "Tooling Complexity:")
        
        title_split = QLabel("Mold Split Classification")
        title_split.setProperty("class", "section-title")
        panel_layout.addWidget(title_split)
        
        _, self.undercut_val_core = self.create_stat_row(panel_layout, "Core Faces:")
        _, self.undercut_val_cavity = self.create_stat_row(panel_layout, "Cavity Faces:")
        _, self.undercut_val_neutral = self.create_stat_row(panel_layout, "Neutral Faces:")
        
        title_silhouette = QLabel("Silhouette Info")
        title_silhouette.setProperty("class", "section-title")
        panel_layout.addWidget(title_silhouette)
        
        _, self.undercut_val_sil_faces = self.create_stat_row(panel_layout, "Silhouette Faces:")
        _, self.undercut_val_sil_area = self.create_stat_row(panel_layout, "Silhouette Area:")
        
        # Legend section
        self.undercut_legend_group = QGroupBox("Legend")
        self.undercut_legend_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 10px; padding-top: 15px; color: #e20015; }")
        self.undercut_legend_layout = QVBoxLayout(self.undercut_legend_group)
        self.undercut_legend_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.addWidget(self.undercut_legend_group)
        
        panel_layout.addStretch()
        scroll_layout.addWidget(panel)
        
        self.update_undercut_legend()

    def update_undercut_legend(self):
        # Clear layout
        while self.undercut_legend_layout.count():
            item = self.undercut_legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                
        mode = self.undercut_view_combo.currentText()
        if mode == "Highlight Undercuts":
            self.undercut_legend_layout.addWidget(self.create_legend_row("#004CFF", "Undercut Face (Blocked)"))
            self.undercut_legend_layout.addWidget(self.create_legend_row("#B2B2B2", "Neutral Face (Safe/Drafted)"))
        else:
            self.undercut_legend_layout.addWidget(self.create_legend_row("#E63333", "Cavity Faces (Pull +)"))
            self.undercut_legend_layout.addWidget(self.create_legend_row("#3366E6", "Core Faces (Pull -)"))
            self.undercut_legend_layout.addWidget(self.create_legend_row("#FF0080", "Silhouette/Transition Faces"))
            self.undercut_legend_layout.addWidget(self.create_legend_row("#B2B2B2", "Neutral/Remaining"))

    def on_undercut_view_changed(self, text):
        self.update_undercut_legend()
        if self.analysis_result:
            self.display.EraseAll()
            if text == "Highlight Undercuts":
                self.render_undercut_view()
            else:
                self.render_mold_split()
            self.display.View.Redraw()

    def setup_parting_tab(self):
        scroll_layout = self.create_scrollable_layout(self.parting_tab)
        
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
        
        # Parting Line Method Selector
        method_row = QWidget()
        method_lyt = QHBoxLayout(method_row)
        method_lyt.setContentsMargins(0, 2, 0, 2)
        method_lbl = QLabel("Parting Line Method:")
        method_lbl.setProperty("class", "lbl-text")
        self.parting_method_combo = QComboBox()
        self.parting_method_combo.addItems(["Hybrid / Silhouette (3D)", "Planar Section (Flat Slice)"])
        self.parting_method_combo.currentTextChanged.connect(self.on_parting_method_changed)
        method_lyt.addWidget(method_lbl)
        method_lyt.addWidget(self.parting_method_combo)
        panel_layout.addWidget(method_row)
        
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

        # ---- Mold Separation Slider ----
        title_sep = QLabel("Mold Separation")
        title_sep.setProperty("class", "section-title")
        panel_layout.addWidget(title_sep)

        sep_desc = QLabel("Drag to animate core/cavity opening:")
        sep_desc.setProperty("class", "lbl-text")
        panel_layout.addWidget(sep_desc)

        self.parting_sep_slider = QSlider(Qt.Horizontal)
        self.parting_sep_slider.setMinimum(0)
        self.parting_sep_slider.setMaximum(200)
        self.parting_sep_slider.setValue(80)   # Default: slightly open
        self.parting_sep_slider.setTickInterval(20)
        self.parting_sep_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background: #3d3d5c; border-radius: 3px; }
            QSlider::handle:horizontal { background: #bd93f9; border: 2px solid #ff79c6;
                width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::sub-page:horizontal { background: #bd93f9; border-radius: 3px; }
        """)

        sep_val_row = QHBoxLayout()
        sep_val_lbl = QLabel("Separation:")
        sep_val_lbl.setProperty("class", "lbl-text")
        self.parting_sep_val_lbl = QLabel("80%")
        self.parting_sep_val_lbl.setProperty("class", "val-text")
        sep_val_row.addWidget(sep_val_lbl)
        sep_val_row.addWidget(self.parting_sep_val_lbl)
        panel_layout.addLayout(sep_val_row)
        panel_layout.addWidget(self.parting_sep_slider)

        def on_sep_slider_changed(val):
            self.parting_separation = val / 100.0
            self.parting_sep_val_lbl.setText(f"{val}%")
            if self.analysis_result and self.engine:
                self.render_parting_line()

        self.parting_sep_slider.valueChanged.connect(on_sep_slider_changed)
        self.parting_separation = 0.80  # initial value
        
        panel_layout.addStretch()
        scroll_layout.addWidget(panel)

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
            self.kpi_val_score, self.kpi_sub_score,
            self.kpi_val_dir, self.kpi_sub_dir,
            self.kpi_val_undercut, self.kpi_sub_undercut,
            self.kpi_val_parting, self.kpi_sub_parting,
            self.kpi_val_draft, self.kpi_sub_draft,
            self.kpi_val_complexity, self.kpi_sub_complexity,
            self.spec_val_filename, self.spec_val_faces,
            self.spec_val_bbox_x, self.spec_val_bbox_y, self.spec_val_bbox_z,
            self.val_min_draft, self.val_max_draft, self.val_avg_draft,
            self.val_undercut_faces, self.val_undercut_area,
            self.val_mold_dir_x, self.val_mold_dir_y, self.val_mold_dir_z, self.val_mold_dir_conf,
            self.undercut_val_count, self.undercut_val_area, self.undercut_val_complexity,
            self.undercut_val_core, self.undercut_val_cavity, self.undercut_val_neutral,
            self.undercut_val_sil_faces, self.undercut_val_sil_area,
            self.val_parting_status, self.val_parting_length, self.val_closed_loop,
            self.val_loop_count,
            self.val_pull_dir, self.val_parting_plane_pos, self.val_undercut_count, self.val_draft_violations,
            self.val_dfm_score,
            self.demo_val_plane_pos, self.demo_val_classification,
            self.demo_val_score, self.demo_val_undercuts, self.demo_val_area,
            self.demo_val_crossing, self.demo_val_core_faces, self.demo_val_cavity_faces,
            self.demo_val_complexity, self.demo_val_cavity_dir, self.demo_val_core_dir
        ]:
            label.setText("-")
            
        self.overview_status_badge.setText("-")
        self.overview_status_badge.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px; font-weight: bold;")
        self.overview_action_lbl.setText("No analysis run yet.")
        self.adv_what.setText("• What: -")
        self.adv_why.setText("• Why: -")
        self.adv_importance.setText("• Importance: -")
        self.adv_action.setText("• Improvement: -")
        
        self.parting_badge_status.setText("-")
        self.parting_badge_status.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px;")
        self.parting_val_justification.setText("No analysis run.")
        
        self.badge_status.setText("-")
        self.badge_status.setStyleSheet("background-color: #444454; color: #a0a0a0; border-radius: 4px;")
        self.demo_val_reason.setText("No analysis run.")
        self.demo_comp_table.setText("No analysis run.")
        
        self.loop_details_txt.setText("No analysis run.")
        self.btn_export_json.setEnabled(False)
        self.btn_export_pdf.setEnabled(False)

    def update_model_info_tab(self):
        if not self.engine or not self.engine.part:
            return
        self.stacked_widget.setCurrentIndex(1)
        self.spec_val_filename.setText(os.path.basename(self.filepath))
        self.spec_val_faces.setText(str(len(self.engine.part.faces)))
        
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        self.spec_val_bbox_x.setText(f"{xmax - xmin:.2f} mm")
        self.spec_val_bbox_y.setText(f"{ymax - ymin:.2f} mm")
        self.spec_val_bbox_z.setText(f"{zmax - zmin:.2f} mm")

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
        
        progress_dialog = DFMProgressDialog(self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()
        QApplication.processEvents()

        msg_to_progress = {
            "Loading STEP Geometry...": (10, "Loading STEP Geometry...", 1),
            "Optimizing Mold Direction...": (30, "Optimizing Mold Direction...", 3),
            "Computing Draft Analysis...": (50, "Computing Draft Analysis...", 4),
            "Detecting Undercuts...": (70, "Detecting Undercuts...", 5),
            "Building Face Topology...": (80, "Building Face Topology...", 6),
            "Generating Parting Line...": (90, "Generating Parting Line...", 7),
            "Finalizing Report...": (95, "Finalizing Report...", 8)
        }

        def progress_callback(msg):
            self.statusBar().showMessage(msg)
            pct, phase, stages_count = msg_to_progress.get(msg, (50, msg, 4))
            progress_dialog.update_progress(pct, phase, stages_count)
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
            
            progress_dialog.finish_progress()
            if os.environ.get("DFM_TEST_MODE") == "1":
                progress_dialog.accept()
            else:
                progress_dialog.exec_()
        except Exception as e:
            print(f"Analysis failed: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Analysis failed: {str(e)}")
            progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{str(e)}")
        finally:
            # Re-enable controls
            self.open_btn.setEnabled(True)
            self.material_combo.setEnabled(True)
            self.run_btn.setEnabled(True)
            self.tabs.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def apply_custom_opening_axis(self, axis_name):
        if not self.engine or not self.engine.part:
            return
        
        # Disable controls
        self.open_btn.setEnabled(False)
        self.material_combo.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.tabs.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        progress_dialog = DFMProgressDialog(self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()
        QApplication.processEvents()

        msg_to_progress = {
            "Loading STEP Geometry...": (10, "Loading STEP Geometry...", 1),
            "Optimizing Mold Direction...": (30, "Optimizing Mold Direction...", 3),
            "Computing Draft Analysis...": (50, "Computing Draft Analysis...", 4),
            "Detecting Undercuts...": (70, "Detecting Undercuts...", 5),
            "Building Face Topology...": (80, "Building Face Topology...", 6),
            "Generating Parting Line...": (90, "Generating Parting Line...", 7),
            "Finalizing Report...": (95, "Finalizing Report...", 8)
        }

        def progress_callback(msg):
            self.statusBar().showMessage(msg)
            pct, phase, stages_count = msg_to_progress.get(msg, (50, msg, 4))
            progress_dialog.update_progress(pct, phase, stages_count)
            QApplication.processEvents()
            
        material = self.material_combo.currentText()
        print(f"Re-running DfM analysis for custom axis {axis_name}...", flush=True)
        try:
            self.analysis_result = self.engine.run_analysis(material, callback=progress_callback, custom_axis=axis_name)
            print("Analysis complete", flush=True)
            self.update_ui_stats()
            self.update_demo_comparison_table()
            self.populate_demo_cases()
            
            print("UI stats updated", flush=True)
            self.on_tab_changed(self.tabs.currentIndex())
            print("Tab changed triggered", flush=True)
            self.statusBar().showMessage(f"Analysis complete for {material} ({axis_name}-Axis). DfM Score: {self.analysis_result.dfm_score}/100")
            
            progress_dialog.finish_progress()
            if os.environ.get("DFM_TEST_MODE") == "1":
                progress_dialog.accept()
            else:
                progress_dialog.exec_()
        except Exception as e:
            print(f"Analysis failed: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Analysis failed: {str(e)}")
            progress_dialog.close()
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
            
        total_area = sum(f.area for f in self.engine.part.faces) or 1.0
        total_faces = len(self.engine.part.faces) or 1.0
        threshold = MATERIAL_THRESHOLDS.get(res.material, 1.0)
        
        # 1. Overview Tab
        score = res.moldability_score
        self.kpi_val_score.setText(f"{score:.1f} / 100")
        if score > 90:
            score_desc = "Excellent"
        elif score > 75:
            score_desc = "Good"
        elif score > 50:
            score_desc = "Fair"
        else:
            score_desc = "Poor"
        self.kpi_sub_score.setText(f"Rating: {score_desc}")
        
        d = res.mold_direction
        d_abs = [abs(x) for x in d]
        max_idx = d_abs.index(max(d_abs))
        if max_idx == 0:
            recommended_axis = "X-Axis"
        elif max_idx == 1:
            recommended_axis = "Y-Axis"
        else:
            recommended_axis = "Z-Axis"
            
        self.kpi_val_dir.setText(recommended_axis)
        self.kpi_sub_dir.setText(f"[{d[0]:.2f}, {d[1]:.2f}, {d[2]:.2f}]")
        
        self.kpi_val_undercut.setText(f"{res.undercuts['count']} Faces")
        self.kpi_sub_undercut.setText(f"{res.undercuts['total_area_mm2']:.1f} mm² ({(res.undercuts['total_area_mm2']/total_area)*100:.1f}%)")
        
        self.kpi_val_parting.setText(f"{recommended_axis[0]} = {res.optimal_z:.2f} mm")
        self.kpi_sub_parting.setText("Flat parting plane")
        
        safe_faces = int(total_faces - res.draft_analysis['draft_violation_count'])
        self.kpi_val_draft.setText(f"{(safe_faces/total_faces)*100:.1f}%")
        self.kpi_sub_draft.setText(f"({safe_faces}/{int(total_faces)} faces safe)")
        
        complexity_score = res.optimal_stats.get("complexity", 0.0)
        if complexity_score > 25:
            complexity_level = "High"
        elif complexity_score > 8:
            complexity_level = "Medium"
        else:
            complexity_level = "Low"
        self.kpi_val_complexity.setText(complexity_level)
        self.kpi_sub_complexity.setText(f"Score: {complexity_score:.1f}")
        
        # Classification banner
        classification = res.optimal_stats.get("classification", "PARTIALLY MOLDABLE")
        self.overview_status_badge.setText(classification)
        if classification == "MOLDABLE":
            self.overview_status_badge.setStyleSheet("font-weight: bold; font-size: 12px; border-radius: 4px; background-color: #28a745; color: white;")
        elif classification == "PARTIALLY MOLDABLE":
            self.overview_status_badge.setStyleSheet("font-weight: bold; font-size: 12px; border-radius: 4px; background-color: #f9a825; color: black;")
        elif classification == "SIDE ACTION REQUIRED":
            self.overview_status_badge.setStyleSheet("font-weight: bold; font-size: 12px; border-radius: 4px; background-color: #fd7e14; color: white;")
        else:
            self.overview_status_badge.setStyleSheet("font-weight: bold; font-size: 12px; border-radius: 4px; background-color: #dc3545; color: white;")
            
        # Recommended manufacturing action
        if classification == "MOLDABLE":
            action_text = "Proceed with current design. Ready for tooling split."
        elif classification == "PARTIALLY MOLDABLE":
            action_text = f"Action Required: Add a minimum {threshold}° draft taper to vertical walls."
        elif classification == "SIDE ACTION REQUIRED":
            if recommended_axis == "Z-Axis":
                action_text = "Add side slider along Y-axis."
            elif recommended_axis == "Y-Axis":
                action_text = "Add side slider along Z-axis."
            else:
                action_text = "Add side slider along Y-axis."
        else:
            action_text = "Redesign locking areas, divide part, or adjust draw orientation."
            
        self.overview_action_lbl.setText(f"Recommended Action: {action_text}")
        
        # Structured Assistant Explanation
        templates = {
            "MOLDABLE": {
                "what": "No draft angle violations or undercut faces detected.",
                "why": f"All part surfaces incline away from the draw axis at angles greater than the material's threshold ({threshold}°).",
                "importance": "Allows the part to slide out of the mold cavity cleanly without rubbing or creating surface scuffs.",
                "action": "Proceed with current design. Ready for tooling split."
            },
            "PARTIALLY MOLDABLE": {
                "what": f"Slight draft violations detected ({res.draft_analysis['draft_violation_count']} vertical wall sections with 0° draft).",
                "why": "Some side walls are parallel to the draw axis, creating frictional resistance during eject.",
                "importance": "Can cause tool wear, part scuffing, or deformation during demolding.",
                "action": f"Add a minimum {threshold}° draft taper to the highlighted warning faces."
            },
            "SIDE ACTION REQUIRED": {
                "what": f"Mechanical locks ({res.undercuts['count']} undercut faces or cylinders) detected perpendicular to the draw direction.",
                "why": "Features protrude outwards (e.g. lateral tubing cylinders), blocking standard two-plate mold separation.",
                "importance": "Forces tool locks, making part ejection impossible without destroying the part or tool.",
                "action": f"Implement lateral mold sliders/lifters perpendicular to the draw direction ({action_text})."
            },
            "NOT MOLDABLE": {
                "what": f"Severe undercut area ({res.undercuts['total_area_mm2']:.1f} mm²) or heavy feature crossings ({res.optimal_stats['crossing_faces']} faces).",
                "why": "Excessive locking geometry or deep internal pockets that cannot be split by standard side actions.",
                "importance": "High risk of eject failure, high tooling cost, or mechanical lockouts.",
                "action": "Redesign locking areas, divide part into sub-assemblies, or adjust draw orientation."
            }
        }
        
        tpl = templates.get(classification, templates["PARTIALLY MOLDABLE"])
        self.adv_what.setText(f"• What: {tpl['what']}")
        self.adv_why.setText(f"• Why: {tpl['why']}")
        self.adv_importance.setText(f"• Importance: {tpl['importance']}")
        self.adv_action.setText(f"• Improvement: {tpl['action']}")
        
        # Geometry Specs
        self.spec_val_filename.setText(res.filename)
        self.spec_val_faces.setText(str(int(total_faces)))
        
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        bbox = Bnd_Box()
        brepbndlib.Add(self.engine.part.shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        self.spec_val_bbox_x.setText(f"{xmax - xmin:.2f} mm")
        self.spec_val_bbox_y.setText(f"{ymax - ymin:.2f} mm")
        self.spec_val_bbox_z.setText(f"{zmax - zmin:.2f} mm")

        # 2. Draft Tab
        self.val_min_draft.setText(f"{res.draft_analysis['min_draft_deg']:.2f}°")
        self.val_max_draft.setText(f"{res.draft_analysis['max_draft_deg']:.2f}°")
        self.val_avg_draft.setText(f"{res.draft_analysis['avg_draft_deg']:.2f}°")
        self.val_undercut_faces.setText(str(res.undercuts['count']))
        self.val_undercut_area.setText(f"{res.undercuts['total_area_mm2']:.2f} mm²")
        self.val_mold_dir_x.setText(f"{res.mold_direction[0]:.3f}")
        self.val_mold_dir_y.setText(f"{res.mold_direction[1]:.3f}")
        self.val_mold_dir_z.setText(f"{res.mold_direction[2]:.3f}")
        self.val_mold_dir_conf.setText(f"{self.engine.confidence * 100:.1f}%")
        
        # 3. Undercuts Tab
        self.undercut_val_count.setText(str(res.undercuts['count']))
        self.undercut_val_area.setText(f"{res.undercuts['total_area_mm2']:.2f} mm² ({(res.undercuts['total_area_mm2']/total_area)*100:.1f}%)")
        self.undercut_val_complexity.setText(complexity_level)
        self.undercut_val_core.setText(str(res.mold_split['core_faces']))
        self.undercut_val_cavity.setText(str(res.mold_split['cavity_faces']))
        self.undercut_val_neutral.setText(str(res.mold_split['neutral_faces']))
        self.undercut_val_sil_faces.setText(str(len(res.mold_split['silhouette_faces'])))
        self.undercut_val_sil_area.setText(f"{res.mold_split['silhouette_area']:.2f} mm²")
        
        # 4. Parting Line Tab
        self.parting_method_combo.blockSignals(True)
        if res.parting_line.get("method") == "planar_section":
            self.parting_method_combo.setCurrentText("Planar Section (Flat Slice)")
        else:
            self.parting_method_combo.setCurrentText("Hybrid / Silhouette (3D)")
        self.parting_method_combo.blockSignals(False)

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
        self.val_dfm_score.setText(f"{score:.2f} / 100")
        
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
        
        # 5. Advisor Tab comparison tables and populate demo
        self.update_demo_comparison_table()
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
            self.on_undercut_view_changed(self.undercut_view_combo.currentText())
        elif index == 3:
            self.render_parting_line()
        elif index == 4:
            self.render_exploded_mold()
        elif index == 5:
            self.display.DisplayShape(self.engine.part.shape, update=True)
            self.display.FitAll()
            
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
    def on_parting_method_changed(self, text):
        if not self.analysis_result or not self.engine:
            return
        
        pl = self.analysis_result.parting_line
        if text == "Planar Section (Flat Slice)":
            pl["loops"] = pl.get("section_loops", [])
            pl["raw_edges"] = pl.get("section_raw_edges", [])
            pl["method"] = "planar_section"
        else:
            pl["loops"] = pl.get("silhouette_loops", [])
            pl["raw_edges"] = pl.get("silhouette_raw_edges", [])
            pl["method"] = "silhouette_topology_v3"
            
        pl["edge_count"] = len(pl["raw_edges"])
        pl["total_length_mm"] = sum(self.engine._get_edge_length(e["edge"]) for e in pl["raw_edges"])
        pl["is_closed_loop"] = all(loop["is_closed"] for loop in pl["loops"]) if pl["loops"] else False
        
        # Update metrics tab display
        self.val_parting_status.setText("✅ Detected" if pl['edge_count'] > 0 else "❌ None")
        self.val_parting_length.setText(f"{pl['total_length_mm']:.2f} mm")
        self.val_closed_loop.setText("Yes" if pl['is_closed_loop'] else "No")
        self.val_loop_count.setText(str(len(pl['loops'])))
        
        loop_details_lines = []
        for i, loop in enumerate(pl['loops']):
            loop_len = sum(self.engine._get_edge_length(edge) for edge in loop['edges'])
            status_str = "Closed" if loop['is_closed'] else "Open"
            loop_details_lines.append(f"Loop {i+1:2d}: {status_str:<6} | Length: {loop_len:.2f} mm | Edges: {len(loop['edges'])}")
        self.loop_details_txt.setText("\n".join(loop_details_lines) if loop_details_lines else "No loops detected.")
        
        # Redraw viewport
        self.render_parting_line()

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

        d = self.analysis_result.mold_direction
        z_split = self.analysis_result.optimal_z
        
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Trsf
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

        bx_min = xmin - dx * 0.15
        bx_max = xmax + dx * 0.15
        by_min = ymin - dy * 0.15
        by_max = ymax + dy * 0.15
        bz_min = zmin - dz * 0.15
        bz_max = zmax + dz * 0.15

        # Build mold half boxes along the correct pull axis
        d_abs = [abs(x) for x in d]
        max_idx = d_abs.index(max(d_abs))
        if max_idx == 0:
            # X-axis pull
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(z_split, by_min, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box   = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(z_split, by_max, bz_max)).Shape()
        elif max_idx == 1:
            # Y-axis pull
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, z_split, bz_min), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box   = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(bx_max, z_split, bz_max)).Shape()
        else:
            # Z-axis pull (default)
            cavity_box = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, z_split), gp_Pnt(bx_max, by_max, bz_max)).Shape()
            core_box   = BRepPrimAPI_MakeBox(gp_Pnt(bx_min, by_min, bz_min), gp_Pnt(bx_max, by_max, z_split)).Shape()

        try:
            cavity_cut = BRepAlgoAPI_Cut(cavity_box, self.engine.part.shape).Shape()
            core_cut   = BRepAlgoAPI_Cut(core_box,   self.engine.part.shape).Shape()
        except Exception as e:
            print("Boolean cut failed, using blank blocks:", e)
            cavity_cut = cavity_box
            core_cut   = core_box

        if cavity_cut is None or cavity_cut.IsNull(): cavity_cut = cavity_box
        if core_cut   is None or core_cut.IsNull():   core_cut   = core_box

        # Separation driven by slider
        sep = getattr(self, 'parting_separation', 0.8)
        if max_idx == 0:
            span = dx
            trans_vec_cav = gp_Vec( span * sep, 0, 0)
            trans_vec_cor = gp_Vec(-span * sep, 0, 0)
        elif max_idx == 1:
            span = dy
            trans_vec_cav = gp_Vec(0,  span * sep, 0)
            trans_vec_cor = gp_Vec(0, -span * sep, 0)
        else:
            span = dz
            trans_vec_cav = gp_Vec(0, 0,  span * sep)
            trans_vec_cor = gp_Vec(0, 0, -span * sep)

        trsf_cavity = gp_Trsf()
        trsf_cavity.SetTranslation(trans_vec_cav)
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True, False).Shape()

        trsf_core = gp_Trsf()
        trsf_core.SetTranslation(trans_vec_cor)
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True, False).Shape()

        cavity_color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB)
        ais_cavity = self.display.DisplayColoredShape(cavity_exploded, cavity_color, update=False)
        for ais_c in (ais_cavity if isinstance(ais_cavity, list) else [ais_cavity]):
            ais_c.SetTransparency(0.7)

        core_color = Quantity_Color(0.2, 0.4, 0.9, Quantity_TOC_RGB)
        ais_core = self.display.DisplayColoredShape(core_exploded, core_color, update=False)
        for ais_co in (ais_core if isinstance(ais_core, list) else [ais_core]):
            ais_co.SetTransparency(0.7)

        print("render_parting_line completed", flush=True)

    def setup_advisor_tab(self):
        # 1. Main layout for the tab
        scroll_layout = self.create_scrollable_layout(self.advisor_tab)
        
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
        
        scroll_layout.addWidget(panel)
        
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
        
        scroll_layout.addWidget(advisor_panel)
        
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
        
        # Add buttons to choose the axis
        btn_layout = QHBoxLayout()
        self.btn_use_x = QPushButton("Use X-Axis")
        self.btn_use_y = QPushButton("Use Y-Axis")
        self.btn_use_z = QPushButton("Use Z-Axis")
        
        btn_style = """
            QPushButton {
                background-color: #2d2d44;
                color: #dfdfea;
                border: 1px solid #3d3d5c;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e20015;
                color: white;
            }
            QPushButton:disabled {
                background-color: #1a1a26;
                color: #555566;
                border-color: #222233;
            }
        """
        self.btn_use_x.setStyleSheet(btn_style)
        self.btn_use_y.setStyleSheet(btn_style)
        self.btn_use_z.setStyleSheet(btn_style)
        
        self.btn_use_x.clicked.connect(lambda: self.apply_custom_opening_axis("X"))
        self.btn_use_y.clicked.connect(lambda: self.apply_custom_opening_axis("Y"))
        self.btn_use_z.clicked.connect(lambda: self.apply_custom_opening_axis("Z"))
        
        btn_layout.addWidget(self.btn_use_x)
        btn_layout.addWidget(self.btn_use_y)
        btn_layout.addWidget(self.btn_use_z)
        comp_layout.addLayout(btn_layout)
        
        scroll_layout.addWidget(comp_panel)
        
        scroll_layout.addStretch()
 
    def render_exploded_mold(self):
        print("render_exploded_mold starting", flush=True)
        self.on_demo_case_changed(self.demo_case_combo.currentText())

    def setup_reports_tab(self):
        scroll_layout = self.create_scrollable_layout(self.reports_tab)
        
        panel = QFrame()
        panel.setProperty("class", "panel")
        panel_layout = QVBoxLayout(panel)
        
        title = QLabel("Manufacturing Report Center")
        title.setProperty("class", "section-title")
        panel_layout.addWidget(title)
        
        desc = QLabel("Generate and download DfM evaluation reports for downstream CAD, tooling design, and manufacturing reviews.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a0a0c0; font-size: 12px; margin-bottom: 15px;")
        panel_layout.addWidget(desc)
        
        # PDF Report Option
        pdf_group = QGroupBox("PDF Engineering Report")
        pdf_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 10px; padding-top: 15px; color: #e20015; }")
        pdf_layout = QVBoxLayout(pdf_group)
        pdf_layout.setContentsMargins(10, 10, 10, 10)
        
        pdf_desc = QLabel("Includes 3D images, optimized pull vector direction, moldability scorecards, and a detailed list of draft/undercut violations.")
        pdf_desc.setWordWrap(True)
        pdf_desc.setStyleSheet("color: #dfdfea; font-size: 11px; margin-bottom: 8px;")
        pdf_layout.addWidget(pdf_desc)
        
        self.btn_export_pdf = QPushButton("Export PDF Report")
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_pdf.clicked.connect(self.on_export_pdf)
        pdf_layout.addWidget(self.btn_export_pdf)
        
        panel_layout.addWidget(pdf_group)
        
        # JSON Report Option
        json_group = QGroupBox("JSON Dataset")
        json_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 6px; margin-top: 15px; padding-top: 15px; color: #e20015; }")
        json_layout = QVBoxLayout(json_group)
        json_layout.setContentsMargins(10, 10, 10, 10)
        
        json_desc = QLabel("Exports raw geometric metadata, optimization scores, and face classifications for downstream database logging or CAD plug-ins.")
        json_desc.setWordWrap(True)
        json_desc.setStyleSheet("color: #dfdfea; font-size: 11px; margin-bottom: 8px;")
        json_layout.addWidget(json_desc)
        
        self.btn_export_json = QPushButton("Export JSON Data")
        self.btn_export_json.setEnabled(False)
        self.btn_export_json.clicked.connect(self.on_export_json)
        json_layout.addWidget(self.btn_export_json)
        
        panel_layout.addWidget(json_group)
        
        panel_layout.addStretch()
        scroll_layout.addWidget(panel)

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
            
        if cavity_cut is None or cavity_cut.IsNull():
            cavity_cut = cavity_box
        if core_cut is None or core_cut.IsNull():
            core_cut = core_box
            
        trsf_cavity = gp_Trsf()
        trsf_cavity.SetTranslation(trans_vec)
        cavity_exploded = BRepBuilderAPI_Transform(cavity_cut, trsf_cavity, True, False).Shape()
        
        trsf_core = gp_Trsf()
        trsf_core.SetTranslation(-trans_vec)
        core_exploded = BRepBuilderAPI_Transform(core_cut, trsf_core, True, False).Shape()
        
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
            
            transformed_arrow = BRepBuilderAPI_Transform(arrow, trsf_trans, True, False).Shape()
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
