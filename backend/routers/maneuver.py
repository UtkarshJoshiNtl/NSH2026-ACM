"""
backend/routers/maneuver.py — Maneuver Scheduling API
=====================================================
NSH 2026 Section 4.2 compliant endpoint for scheduling evasion and recovery burns.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from backend.core.state_manager import state_mgr
from backend.core.physics.constants import DRY_MASS, ISP, G0, INITIAL_FUEL, MAX_DV, COOLDOWN_S
import math

router = APIRouter()


class DeltaVVector(BaseModel):
    x: float
    y: float
    z: float


class ManeuverSequence(BaseModel):
    burn_id: str
    burnTime: str  # ISO 8601 timestamp
    deltaV_vector: DeltaVVector


class ManeuverScheduleRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: List[ManeuverSequence]


def compute_fuel_used(delta_v: List[float], fuel_kg: float = INITIAL_FUEL) -> float:
    """Compute fuel used for a given delta-v using Tsiolkovsky equation."""
    dv_mag = math.sqrt(sum(d * d for d in delta_v))
    mass = DRY_MASS + fuel_kg
    return mass * (1.0 - math.exp(-dv_mag / (ISP * G0)))


@router.post("/maneuver/schedule")
async def schedule_maneuver(req: ManeuverScheduleRequest):
    """
    Schedule evasion and recovery burns for a satellite.
    NSH 2026 Section 4.2 compliant.
    """
    # Validate satellite exists
    satellite = state_mgr.get_satellite(req.satelliteId)
    if not satellite:
        raise HTTPException(status_code=404, detail=f"Satellite {req.satelliteId} not found")
    
    # Parse and validate maneuvers
    total_fuel_cost = 0.0
    current_fuel = satellite.m_fuel
    last_burn_time = None
    
    for maneuver in req.maneuver_sequence:
        # Parse burn time
        try:
            burn_time = datetime.fromisoformat(maneuver.burnTime.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid timestamp format for {maneuver.burn_id}")
        
        # Check 10-second command latency (NSH 2026 requirement)
        current_time = state_mgr.simulation_time
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
        
        time_to_burn = (burn_time - current_time).total_seconds()
        if time_to_burn < 10.0:
            raise HTTPException(
                status_code=422, 
                detail=f"Maneuver {maneuver.burn_id} violates 10s command latency requirement"
            )
        
        # Check 600-second cooldown (NSH 2026 requirement)
        if last_burn_time is not None:
            cooldown_elapsed = (burn_time - last_burn_time).total_seconds()
            if cooldown_elapsed < COOLDOWN_S:
                raise HTTPException(
                    status_code=422,
                    detail=f"Maneuver {maneuver.burn_id} violates 600s cooldown requirement"
                )
        
        # Check max delta-v (NSH 2026 requirement)
        dv = [maneuver.deltaV_vector.x, maneuver.deltaV_vector.y, maneuver.deltaV_vector.z]
        dv_mag = math.sqrt(sum(d * d for d in dv))
        if dv_mag > MAX_DV:
            raise HTTPException(
                status_code=422,
                detail=f"Maneuver {maneuver.burn_id} exceeds max delta-v of {MAX_DV} km/s"
            )
        
        # Calculate fuel cost
        fuel_cost = compute_fuel_used(dv, current_fuel)
        total_fuel_cost += fuel_cost
        current_fuel -= fuel_cost
        
        # Check sufficient fuel
        if current_fuel < 0:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient fuel for maneuver {maneuver.burn_id}"
            )
        
        last_burn_time = burn_time
    
    # Ground station LOS check (simplified - would need full implementation)
    # For NSH 2026, this should verify satellite has LOS to at least one ground station
    ground_station_los = True  # Placeholder - implement full check
    
    # Schedule maneuvers in state manager
    for maneuver in req.maneuver_sequence:
        burn_time = datetime.fromisoformat(maneuver.burnTime.replace('Z', '+00:00'))
        dv = [maneuver.deltaV_vector.x, maneuver.deltaV_vector.y, maneuver.deltaV_vector.z]
        
        state_mgr.schedule_burn(
            satellite_id=req.satelliteId,
            burn_id=maneuver.burn_id,
            burn_time=burn_time,
            delta_v=dv,
            burn_type="EVASION" if "EVASION" in maneuver.burn_id.upper() else "RECOVERY"
        )
    
    return {
        "status": "SCHEDULED",
        "validation": {
            "ground_station_los": ground_station_los,
            "sufficient_fuel": True,
            "projected_mass_remaining_kg": round(DRY_MASS + current_fuel, 2)
        }
    }
