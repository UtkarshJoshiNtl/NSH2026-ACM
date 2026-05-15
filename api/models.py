"""Astrosis REST API — Pydantic request/response models."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Shared ──────────────────────────────────────────────────────────────────

class StateVector(BaseModel):
    """[x, y, z, vx, vy, vz] in km and km/s (ECI/GCRF)."""
    state: List[float] = Field(..., min_length=6, max_length=6,
                               example=[-6378.137, 0, 0, 0, 7.66, 0])


# ── Propagation ─────────────────────────────────────────────────────────────

class PropagateRequest(BaseModel):
    state: List[float] = Field(..., min_length=6, max_length=6)
    dt_seconds: float = Field(10.0, gt=0, le=86400, description="Step size in seconds")
    steps: int = Field(1, ge=1, le=100_000, description="Number of RK4 steps")
    with_drag: bool = False
    area_m2: float = Field(10.0, gt=0, description="Cross-section area [m²]")
    mass_kg: float = Field(1000.0, gt=0, description="Satellite mass [kg]")
    cd: float = Field(2.2, gt=0, description="Drag coefficient")


class PropagateResponse(BaseModel):
    state: List[float]
    backend: str
    steps_taken: int


class BatchPropagateRequest(BaseModel):
    states: List[List[float]] = Field(..., description="List of (N, 6) state vectors")
    dt_seconds: float = Field(10.0, gt=0)
    steps: int = Field(1, ge=1, le=100_000)
    with_drag: bool = False
    area_m2: float = 10.0
    mass_kg: float = 1000.0
    cd: float = 2.2


class BatchPropagateResponse(BaseModel):
    states: List[List[float]]
    backend: str
    n_satellites: int
    steps_taken: int


# ── Conjunction Detection ────────────────────────────────────────────────────

class ConjunctionRequest(BaseModel):
    sat_states: List[List[float]] = Field(..., description="Satellite state vectors (N, 6)")
    debris_states: List[List[float]] = Field(..., description="Debris state vectors (M, 6)")
    lookahead_s: float = Field(86400.0, gt=0, le=7 * 86400, description="Lookahead window [s]")
    step_s: float = Field(60.0, gt=0, description="Sweep step size [s]")
    tle_age_days: float = Field(1.0, ge=0, description="TLE age for covariance estimate [days]")


class ConjunctionResult(BaseModel):
    sat_id: int
    debris_id: int
    current_distance: float
    time_to_closest_approach: float
    severity: str
    relative_velocity: List[float]
    probability_of_collision: Optional[float] = None


class ConjunctionResponse(BaseModel):
    warnings: List[ConjunctionResult]
    n_pairs_checked: int
    backend: str


# ── Passes ───────────────────────────────────────────────────────────────────

class PassRequest(BaseModel):
    norad_id: int = Field(..., gt=0)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    alt_km: float = Field(0.0, ge=0, le=10.0, description="Ground station altitude [km]")
    hours: float = Field(24.0, gt=0, le=168)
    dt_step_s: float = Field(60.0, gt=0)


# ── Misc ─────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "gamma"


class BackendResponse(BaseModel):
    backend: str
    cuda_available: bool
    cpp_available: bool
    description: str
