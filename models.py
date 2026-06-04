from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class FaceData:
    face_id: int
    surface_type: str
    area: float
    centroid: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    neighbors: List[int]


@dataclass
class PartData:
    faces: List[FaceData]
    shape: object