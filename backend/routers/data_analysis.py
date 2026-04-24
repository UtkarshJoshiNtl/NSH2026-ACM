"""
API router for data analysis features.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.database import get_db, HistoricalConjunction, DebrisDensity
from backend.debris_density import DebrisDensityModel, ConjunctionHistorian
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debris-density")
async def get_debris_density(
    altitude_km: Optional[float] = Query(None, description="Specific altitude to query"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get debris density data."""
    model = DebrisDensityModel()
    
    if altitude_km is not None:
        # Get density at specific altitude
        data = model.get_density_at_altitude(altitude_km)
        model.close()
        return data
    else:
        # Get all density shells
        data = model.get_all_density_shells()
        model.close()
        return {"shells": data}


@router.post("/debris-density/update")
async def update_debris_density():
    """Trigger debris density model update."""
    model = DebrisDensityModel()
    count = model.update_density_database()
    model.close()
    
    return {
        "status": "success",
        "updated_shells": count,
        "message": f"Updated {count} debris density shells"
    }


@router.get("/conjunctions/history")
async def get_conjunction_history(
    satellite_id: Optional[str] = Query(None),
    debris_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get historical conjunction data."""
    historian = ConjunctionHistorian()
    
    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    
    data = historian.get_conjunction_history(
        satellite_id=satellite_id,
        debris_id=debris_id,
        start_time=start_time,
        limit=limit,
    )
    
    historian.close()
    
    return {
        "conjunctions": data,
        "count": len(data),
        "period_days": days,
    }


@router.get("/conjunctions/statistics")
async def get_conjunction_statistics(
    days: int = Query(30, ge=1, le=365),
):
    """Get conjunction statistics for a time period."""
    historian = ConjunctionHistorian()
    
    stats = historian.get_conjunction_statistics(days=days)
    
    historian.close()
    
    return stats


@router.post("/conjunctions/record")
async def record_conjunction(
    satellite_id: str,
    debris_id: str,
    conjunction_time: datetime,
    min_distance_km: float,
    severity: str,
    relative_velocity: List[float],
    probability: Optional[float] = None,
):
    """Record a conjunction event."""
    historian = ConjunctionHistorian()
    
    historian.record_conjunction(
        satellite_id=satellite_id,
        debris_id=debris_id,
        conjunction_time=conjunction_time,
        min_distance_km=min_distance_km,
        severity=severity,
        relative_velocity=relative_velocity,
        probability=probability,
    )
    
    historian.close()
    
    return {
        "status": "success",
        "message": "Conjunction recorded successfully"
    }
