"""
═══════════════════════════════════════════════════════════════════════════
 ACM API — Telemetry Router
 Telemetry ingestion and constellation status endpoints.
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from ..state_manager import state

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


class TelemetryPayload(BaseModel):
    satellite_id: str
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    alt_km: Optional[float] = Field(None, ge=0, le=2000)
    fuel_kg: Optional[float] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(NOMINAL|EVADING|RECOVERING|EOL)$")


class BulkTelemetryPayload(BaseModel):
    entries: List[TelemetryPayload]


@router.post("/ingest")
async def ingest_telemetry(payload: TelemetryPayload):
    """Ingest telemetry data for a single satellite."""
    sat = state.fleet.satellites.get(payload.satellite_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite {payload.satellite_id} not found")
    
    # Update fields
    if payload.fuel_kg is not None: sat.fuel_kg = payload.fuel_kg
    if payload.status is not None: sat.status = payload.status
    if payload.lat is not None: sat.lat = payload.lat
    if payload.lon is not None: sat.lon = payload.lon
    if payload.alt_km is not None: sat.alt_km = payload.alt_km

    return {"status": "OK", "satellite_id": payload.satellite_id}


@router.post("/ingest/bulk")
async def ingest_bulk(payload: BulkTelemetryPayload):
    """Ingest telemetry for multiple satellites."""
    results, errors = [], []
    for entry in payload.entries:
        telemetry = {k: getattr(entry, k) for k in ["lat","lon","alt_km","fuel_kg","status"] if getattr(entry, k) is not None}
        if state.ingest_telemetry(entry.satellite_id, telemetry):
            results.append(entry.satellite_id)
        else:
            errors.append(entry.satellite_id)
    return {"status": "OK", "ingested": len(results), "failed": len(errors), "errors": errors}


@router.get("/satellite/{satellite_id}")
async def get_satellite(satellite_id: str):
    """Get current telemetry for a satellite."""
    sat = state.fleet.satellites.get(satellite_id)
    if not sat:
        raise HTTPException(status_code=404, detail=f"Satellite {satellite_id} not found")
    return {"satellite": sat.model_dump(), "eci_position": sat.r.model_dump(), "eci_velocity": sat.v.model_dump()}


@router.get("/constellation")
async def get_constellation():
    """Get constellation-wide statistics."""
    return state.get_stats()


@router.get("/cdms")
async def get_cdms():
    """Get active Conjunction Data Messages."""
    return {
        "cdms": [c.model_dump() for c in state.conj.active_cdms],
        "count": len(state.conj.active_cdms),
        "critical": len([c for c in state.conj.active_cdms if c.missDistance < 0.1]),
    }
