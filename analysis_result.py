from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class AnalysisResult:
    filename: str = ""
    material: str = ""
    face_count: int = 0
    mold_direction: List[float] = field(default_factory=lambda: [0.0, 0.0, 1.0])
    draft_analysis: Dict[str, Any] = field(default_factory=lambda: {
        "min_draft_deg": 0.0,
        "max_draft_deg": 0.0,
        "avg_draft_deg": 0.0,
        "draft_violation_count": 0,
        "details": []
    })
    undercuts: Dict[str, Any] = field(default_factory=lambda: {
        "count": 0,
        "total_area_mm2": 0.0,
        "faces": []
    })
    mold_split: Dict[str, Any] = field(default_factory=lambda: {
        "core_faces": 0,
        "cavity_faces": 0,
        "neutral_faces": 0
    })
    parting_line: Dict[str, Any] = field(default_factory=lambda: {
        "edge_count": 0,
        "total_length_mm": 0.0,
        "is_closed_loop": False,
        "method": "silhouette_v2"
    })
    dfm_score: int = 0
    optimal_z: float = 10.0
    parting_plane_z: float = 0.0  # Midplane used for parting line display (may differ from optimal_z)
    optimal_stats: Dict[str, Any] = field(default_factory=dict)
    standard_positions: Dict[str, Any] = field(default_factory=dict)
    moldability_score: float = 0.0
