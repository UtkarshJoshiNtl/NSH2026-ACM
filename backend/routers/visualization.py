"""
backend/routers/visualization.py — Visualization Endpoints
======================================================
Endpoints for retrieving simulation state for visualization.
"""

from fastapi import APIRouter
from backend.core.state_manager import state_mgr
from backend.core.ground_station import eci_to_geodetic, get_all_stations
import numpy as np

router = APIRouter()

@router.get("/visualization/snapshot")
async def get_snapshot():
    t_now = state_mgr.simulation_time
    satellites_out = []
    for sat in state_mgr.get_all_satellites():
        lat, lon, alt = eci_to_geodetic(sat.r, time_s=t_now)
        satellites_out.append({
            "id": sat.id,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt_km": round(alt, 1),
            "fuel_kg": round(sat.m_fuel, 2),
            "status": sat.status
        })

    import numpy as np
    from backend.core.ground_station import vectorized_eci_to_geodetic

    debris = state_mgr.get_all_debris()
    if debris:
        r_array = np.array([d.r for d in debris])
        geo_array = vectorized_eci_to_geodetic(r_array, time_s=t_now)
        debris_cloud = [
            [deb.id, round(float(geo_array[i][0]), 3), round(float(geo_array[i][1]), 3), round(float(geo_array[i][2]), 1)]
            for i, deb in enumerate(debris)
        ]
    else:
        debris_cloud = []

    # Expose pending burns for Gantt chart
    pending_burns = [
        {
            "burn_id":      b.burn_id,
            "satellite_id": b.satellite_id,
            "burn_type":    b.burn_type,
            "burn_time":    b.burn_time,
        }
        for b in state_mgr.scheduled_maneuvers if not b.executed
    ]

    return {
        "timestamp": t_now,
        "satellites": satellites_out,
        "debris_cloud": debris_cloud,
        "active_cdms": state_mgr.active_cdms,
        "ground_stations": get_all_stations(),
        "pending_burns": state_mgr.get_context("default").scheduled_burns if state_mgr.get_context("default") else []
    }


@router.get("/visualization/fuel-alerts")
async def get_fuel_alerts(threshold_pct: float = 5.0):
    """Get satellites with critically low fuel."""
    depleted = state_mgr.check_fuel_depletion(threshold_pct)
    return {
        "threshold_pct": threshold_pct,
        "alert_count": len(depleted),
        "alerts": depleted
    }
