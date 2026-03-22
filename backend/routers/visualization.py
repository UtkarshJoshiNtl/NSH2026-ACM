from fastapi import APIRouter
from backend.core.state_manager import state_mgr
from backend.core.ground_station import eci_to_geodetic, get_all_stations

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
            "fuel_kg": round(sat.m_fuel, 2),
            "status": sat.status
        })

    import numpy as np
    from backend.core.ground_station import vectorized_eci_to_geodetic

    debris = state_mgr.get_all_debris()
    if debris:
        r_array = np.array([d.r for d in debris])
        geo_array = vectorized_eci_to_geodetic(r_array, time_s=t_now)
        
        debris_cloud = []
        for i, deb in enumerate(debris):
            lat, lon, alt = geo_array[i]
            debris_cloud.append([deb.id, round(float(lat), 3), round(float(lon), 3), round(float(alt), 1)])
    else:
        debris_cloud = []

    return {
        "timestamp": state_mgr.simulation_time,
        "satellites": satellites_out,
        "debris_cloud": debris_cloud,
        "active_cdms": state_mgr.active_cdms[:20],
        "ground_stations": get_all_stations()
    }
