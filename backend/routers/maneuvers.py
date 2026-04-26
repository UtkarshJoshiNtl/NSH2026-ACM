"""
═══════════════════════════════════════════════════════════════════════════
 ACM API — Maneuver Commands Router
 Evasion, recovery, and orbit adjustment maneuver endpoints.
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..state_manager import state

router = APIRouter(prefix="/maneuvers", tags=["Maneuvers"])


class DeltaV(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class ManeuverCommand(BaseModel):
    satellite_id: str
    delta_v: DeltaV
    burn_duration: float = Field(300.0, ge=1, le=3600)
    reason: Optional[str] = None


class ScheduleEvasionCommand(BaseModel):
    satellite_id: str
    cdm_debris_id: Optional[str] = None
    strategy: str = Field("PROGRADE", pattern="^(PROGRADE|RETROGRADE|RADIAL_OUT|RADIAL_IN|NORMAL_POS|NORMAL_NEG)$")
    dv_magnitude_ms: float = Field(10.0, ge=0.1, le=100.0)


@router.post("/execute")
async def execute_maneuver(cmd: ManeuverCommand):
    """Execute a maneuver command on a satellite."""
    result = state.execute_maneuver(
        sat_id=cmd.satellite_id,
        delta_v=cmd.delta_v.model_dump(),
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
    return result


@router.post("/schedule-evasion")
async def schedule_evasion(cmd: ScheduleEvasionCommand):
    """Schedule an autonomous evasion maneuver with RTN geometry."""
    sat = state.satellites.get(cmd.satellite_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite {cmd.satellite_id} not found")
    if sat.status == "EOL":
        raise HTTPException(status_code=400, detail=f"Satellite {cmd.satellite_id} is EOL")

    dv_ms = cmd.dv_magnitude_ms
    r, v = sat.r, sat.v
    r_mag = math.sqrt(r.x**2 + r.y**2 + r.z**2)
    if r_mag < 1:
        raise HTTPException(status_code=500, detail="Invalid satellite position")

    R_hat = (r.x/r_mag, r.y/r_mag, r.z/r_mag)
    N_raw = (r.y*v.z-r.z*v.y, r.z*v.x-r.x*v.z, r.x*v.y-r.y*v.x)
    N_mag = math.sqrt(sum(c**2 for c in N_raw))
    N_hat = tuple(c/N_mag for c in N_raw) if N_mag > 1e-10 else (0, 0, 1)
    T_hat = (N_hat[1]*R_hat[2]-N_hat[2]*R_hat[1], N_hat[2]*R_hat[0]-N_hat[0]*R_hat[2], N_hat[0]*R_hat[1]-N_hat[1]*R_hat[0])

    strategy_map = {
        "PROGRADE": (T_hat, +1), "RETROGRADE": (T_hat, -1),
        "RADIAL_OUT": (R_hat, +1), "RADIAL_IN": (R_hat, -1),
        "NORMAL_POS": (N_hat, +1), "NORMAL_NEG": (N_hat, -1),
    }
    direction, sign = strategy_map.get(cmd.strategy, (T_hat, +1))
    delta_v = {"x": sign*dv_ms*direction[0], "y": sign*dv_ms*direction[1], "z": sign*dv_ms*direction[2]}

    result = state.execute_maneuver(sat_id=cmd.satellite_id, delta_v=delta_v)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    result["strategy"] = cmd.strategy
    result["dv_magnitude_ms"] = cmd.dv_magnitude_ms
    return result


@router.get("/history")
async def get_maneuver_history():
    """Get all maneuver records."""
    return {"maneuvers": [m.model_dump() for m in state.maneuvers]}


@router.get("/history/{satellite_id}")
async def get_satellite_maneuvers(satellite_id: str):
    """Get maneuver history for a specific satellite."""
    sat = state.satellites.get(satellite_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite {satellite_id} not found")
    sat_maneuvers = [m.to_dict() for m in state.maneuvers if m.satelliteId == satellite_id]
    return {"satellite_id": satellite_id, "maneuvers": sat_maneuvers, "count": len(sat_maneuvers)}
