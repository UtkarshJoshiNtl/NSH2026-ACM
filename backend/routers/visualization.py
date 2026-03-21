from fastapi import APIRouter
from backend.core.state_manager import state_mgr
from backend.core.ground_station import eci_to_geodetic

router = APIRouter()

@router.get("/visualization/snapshot")
async def get_snapshot():
    satellites_out = []
    for sat in state_mgr.get_all_satellites():
        lat, lon, alt = eci_to_geodetic(sat.r)
        satellites_out.append({
            "id": sat.id,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "fuel_kg": round(sat.m_fuel, 2),
            "status": sat.status
        })

    debris_cloud = []
    for deb in state_mgr.get_all_debris():
        lat, lon, alt = eci_to_geodetic(deb.r)
        debris_cloud.append([deb.id, round(lat, 3), round(lon, 3), round(alt, 1)])

    return {
        "timestamp": state_mgr.simulation_time,
        "satellites": satellites_out,
        "debris_cloud": debris_cloud,
        "active_cdms": state_mgr.active_cdms[:20]
    }
