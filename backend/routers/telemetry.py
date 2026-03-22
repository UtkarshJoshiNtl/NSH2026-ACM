from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict
from backend.core.state_manager import state_mgr, ObjectState
from backend.core.conjunction import check_conjunctions_async

router = APIRouter()

class TelemetryObject(BaseModel):
    id: str
    type: str  # "SATELLITE" | "DEBRIS"
    r: Dict[str, float]  # {"x": ..., "y": ..., "z": ...}
    v: Dict[str, float]  # {"vx": ..., "vy": ..., "vz": ...}
    m_fuel: float = 50.0

class TelemetryRequest(BaseModel):
    timestamp: str
    objects: List[TelemetryObject]

@router.post("/telemetry")
async def ingest_telemetry(req: TelemetryRequest):
    count = 0
    for obj in req.objects:
        state = ObjectState(
            id=obj.id,
            obj_type=obj.type,
            r=[obj.r["x"], obj.r["y"], obj.r["z"]],
            v=[obj.v["x"], obj.v["y"], obj.v["z"]],
            m_fuel=obj.m_fuel
        )
        state_mgr.upsert(state)
        count += 1

    # Trigger async conjunction check
    import asyncio
    asyncio.create_task(check_conjunctions_async())

    return {
        "status": "ACK",
        "processed_count": count,
        "active_cdm_warnings": len(state_mgr.active_cdms)
    }
