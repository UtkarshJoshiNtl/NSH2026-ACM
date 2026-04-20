"""
TLE router for satellite data import from Celestrak.
"""

from fastapi import APIRouter, HTTPException, Depends
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
from backend.cache import RedisCache
from backend.middleware import get_current_user, optional_api_key
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
async def ingest_tle(satellite_id: str = None, user: dict = Depends(optional_api_key)):
    """Ingest TLE data from Celestrak into the database."""
    try:
        # Rate limit TLE ingest
        cache = RedisCache()
        if cache.available:
            user_id = user.get("user_id") if user else "anonymous"
            key = f"tle_ingest:{user_id}"
            if not cache.check_rate_limit(key, 10, 60):  # 10 requests per minute
                raise HTTPException(status_code=429, detail="TLE ingest rate limit exceeded (10/min)")
        
        count = await tle_ingestor.ingest(satellite_id)
        return {
            "status": "success",
            "ingested_count": count,
            "message": f"Successfully ingested {count} TLE entries"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tle/fetch-group")
async def fetch_group(req: TLEGroupRequest, user: dict = Depends(optional_api_key)):
    """Fetch TLE data for a satellite group."""
    try:
        # Rate limit TLE fetch
        cache = RedisCache()
        if cache.available:
            user_id = user.get("user_id") if user else "anonymous"
            key = f"tle_fetch:{user_id}"
            if not cache.check_rate_limit(key, 30, 60):  # 30 requests per minute
                raise HTTPException(status_code=429, detail="TLE fetch rate limit exceeded (30/min)")
        
        tles = await fetch_tle_group(req.group)
        return {
            "status": "success",
            "group": req.group,
            "count": len(tles),
            "tles": tles,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tle/fetch-norad")
async def fetch_norad(norad_id: str, user: dict = Depends(optional_api_key)):
    """Fetch TLE data for a specific NORAD ID."""
    try:
        # Rate limit TLE fetch
        cache = RedisCache()
        if cache.available:
            user_id = user.get("user_id") if user else "anonymous"
            key = f"tle_fetch:{user_id}"
            if not cache.check_rate_limit(key, 30, 60):  # 30 requests per minute
                raise HTTPException(status_code=429, detail="TLE fetch rate limit exceeded (30/min)")
        
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
