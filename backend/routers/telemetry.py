from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from backend.core.state_manager import state_mgr, ObjectState
from backend.core.conjunction import check_conjunctions_async
import asyncio

router = APIRouter()


class TelemetryObject(BaseModel):
    id: str
    type: str  # "SATELLITE" | "DEBRIS"
    r: Dict[str, float]  # {"x": km, "y": km, "z": km}
    v: Dict[str, float]  # {"x": km/s, "y": km/s, "z": km/s}
    # also accepts "vx"/"vy"/"vz" keys
    m_fuel: float = 50.0


class TelemetryRequest(BaseModel):
    timestamp: str
    objects: List[TelemetryObject]


def _vec(d: Dict[str, float], keys_primary, keys_fallback) -> list:
    """Extract [a, b, c] from a dict that may use either key scheme."""
    try:
        return [d[keys_primary[0]], d[keys_primary[1]], d[keys_primary[2]]]
    except KeyError:
        return [d[keys_fallback[0]], d[keys_fallback[1]], d[keys_fallback[2]]]


@router.post("/telemetry")
async def ingest_telemetry(req: TelemetryRequest):
    count = 0
    for obj in req.objects:
        try:
            r = _vec(obj.r, ["x", "y", "z"], ["rx", "ry", "rz"])
            v = _vec(obj.v, ["x", "y", "z"], ["vx", "vy", "vz"])
        except KeyError as e:
            raise HTTPException(
                status_code=422, detail=f"Object {obj.id}: missing vector key {e}"
            )

        state = ObjectState(
            id=obj.id,
            obj_type=obj.type,
            r=r,
            v=v,
            m_fuel=obj.m_fuel,
        )
        state_mgr.upsert(state)
        count += 1

    # Trigger async conjunction check (non-blocking)
    asyncio.create_task(check_conjunctions_async())

    return {
        "status": "ACK",
        "processed_count": count,
        "active_cdm_warnings": len(state_mgr.active_cdms),
    }
