"""
═══════════════════════════════════════════════════════════════════════════
 ACM MODELS — models.py
 Pydantic and Dataclass structures for v2
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np

class Vector3(BaseModel):
    x: float
    y: float
    z: float

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])
    
    @classmethod
    def from_np(cls, arr: np.ndarray):
        return cls(x=float(arr[0]), y=float(arr[1]), z=float(arr[2]))

class ObjectState(BaseModel):
    id: str
    r: Vector3
    v: Vector3
    timestamp: datetime

class Satellite(BaseModel):
    id: str
    lat: float = 0.0
    lon: float = 0.0
    alt_km: float = 0.0
    fuel_kg: float = 50.0
    status: str = "NOMINAL"
    r: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    v: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    
    # Mission Slot & Performance Tracking (Section 5.2/7)
    nominal_r: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    nominal_v: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    uptime_seconds: float = 0.0
    uptime_score: float = 1.0  # Normalized 0.0 to 1.0 (Section 5.2)
    is_nominal: bool = True
    outage_events: List[Dict] = Field(default_factory=list)

    @property
    def mass_kg(self) -> float:
        return 500.0 + self.fuel_kg

class Debris(BaseModel):
    id: str
    lat: float
    lon: float
    alt_km: float
    r: Vector3
    v: Vector3

class CDM(BaseModel):
    satelliteId: str
    debrisId: str
    tca: datetime
    missDistance: float
    probability: float
    status: str = "ACTIVE"

class Maneuver(BaseModel):
    burn_id: str
    satelliteId: str
    burnTime: datetime
    deltaV_vector: Vector3
    status: str = "SCHEDULED"
    fuel_cost_kg: float = 0.0
