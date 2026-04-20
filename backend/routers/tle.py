"""
TLE router for satellite data import from Celestrak.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.core.tle_handler import (
    fetch_tle_group,
    fetch_tle_by_norad_id,
    tle_to_state_vector,
    get_satellite_name,
    get_satellite_groups,
)
from backend.core.state_manager import state_mgr
from backend.tle_ingest import tle_ingestor
import time

router = APIRouter()

class TLEGroupRequest(BaseModel):
    group: str

class TLEImportRequest(BaseModel):
    tle: str
    timestamp: float = None  # If None, use current simulation time

@router.get("/tle/groups")
async def get_groups():
    """Get available satellite groups from Celestrak."""
    return {"groups": get_satellite_groups()}


@router.post("/tle/ingest")
async def ingest_tle(satellite_id: str = None):
    """Ingest TLE data from Celestrak into the database."""
    try:
        count = await tle_ingestor.ingest(satellite_id)
        return {
            "status": "success",
            "ingested_count": count,
            "message": f"Successfully ingested {count} TLE entries"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tle/fetch-group")
async def fetch_group(req: TLEGroupRequest):
    """Fetch TLE data for a satellite group."""
    try:
        tles = await fetch_tle_group(req.group)
        return {
            "status": "success",
            "group": req.group,
            "count": len(tles),
            "tles": tles,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tle/fetch-norad")
async def fetch_norad(norad_id: str):
    """Fetch TLE data for a specific NORAD ID."""
    try:
        tle = await fetch_tle_by_norad_id(norad_id)
        if not tle:
            raise HTTPException(status_code=404, detail=f"Satellite with NORAD ID {norad_id} not found")
        return {
            "status": "success",
            "norad_id": norad_id,
            "tle": tle,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tle/import")
async def import_satellite(req: TLEImportRequest):
    """Import a satellite from TLE into the simulation."""
    try:
        timestamp = req.timestamp or state_mgr.simulation_time or time.time()
        
        # Convert TLE to state vector
        state = tle_to_state_vector(req.tle, timestamp)
        name = get_satellite_name(req.tle)
        
        # Create satellite object
        sat_id = f"TLE-{name.replace(' ', '-')}"
        
        from backend.core.models import Satellite
        satellite = Satellite(
            id=sat_id,
            r=state["r"],
            v=state["v"],
            mass=1000.0,  # Default mass
        )
        
        # Add to state manager
        state_mgr.objects[sat_id] = satellite
        
        return {
            "status": "success",
            "satellite_id": sat_id,
            "name": name,
            "orbital_elements": state["orbital_elements"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tle/import-group")
async def import_group(req: TLEGroupRequest):
    """Import all satellites from a group."""
    try:
        tles = await fetch_tle_group(req.group)
        timestamp = state_mgr.simulation_time or time.time()
        
        imported = []
        for tle in tles:
            try:
                state = tle_to_state_vector(tle, timestamp)
                name = get_satellite_name(tle)
                sat_id = f"TLE-{name.replace(' ', '-')}"
                
                from backend.core.models import Satellite
                satellite = Satellite(
                    id=sat_id,
                    r=state["r"],
                    v=state["v"],
                    mass=1000.0,
                )
                
                state_mgr.objects[sat_id] = satellite
                imported.append({
                    "satellite_id": sat_id,
                    "name": name,
                    "orbital_elements": state["orbital_elements"],
                })
            except Exception as e:
                # Skip failed imports
                continue
        
        return {
            "status": "success",
            "group": req.group,
            "imported_count": len(imported),
            "satellites": imported,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
