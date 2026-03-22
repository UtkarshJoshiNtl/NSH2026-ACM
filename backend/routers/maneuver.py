from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from backend.core.state_manager import state_mgr, ScheduledBurn
from backend.core.maneuver_planner import validate_burn, MAX_DV_KMS
from backend.core.ground_station import check_los
import uuid

router = APIRouter()

class BurnItem(BaseModel):
    burn_id: str
    burnTime: float
    deltaV_vector: Dict[str, float]

class ManeuverRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: List[BurnItem]

@router.post("/maneuver/schedule")
async def schedule_maneuver(req: ManeuverRequest):
    sat = state_mgr.get(req.satelliteId)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")

    # Validate each burn in sequence
    for burn in req.maneuver_sequence:
        dv = [burn.deltaV_vector["x"], burn.deltaV_vector["y"], burn.deltaV_vector["z"]]
        dv_mag = sum(x*x for x in dv)**0.5
        
        # We check LOS at current position as an approximation for scheduled time
        val = validate_burn(sat, dv_mag, burn.burnTime)
        if not val["ok"]:
            return {"status": "REJECTED", "reason": val["reason"]}

    # Queue the burns
    for burn in req.maneuver_sequence:
        dv = [burn.deltaV_vector["x"], burn.deltaV_vector["y"], burn.deltaV_vector["z"]]
        sb = ScheduledBurn(
            burn_id=burn.burn_id,
            satellite_id=req.satelliteId,
            burn_time=burn.burnTime,
            delta_v=dv
        )
        state_mgr.queue_burn(sb)

    return {
        "status": "SCHEDULED",
        "validation": {
            "ground_station_los": True,
            "sufficient_fuel": True
        }
    }
