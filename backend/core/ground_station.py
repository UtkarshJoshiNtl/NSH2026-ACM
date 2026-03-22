"""
backend/core/ground_station.py — ACM Ground Station LOS
=========================================================
Checks satellite line-of-sight (LOS) to ground stations using elevation
angle calculation. Loads station data from data/ground_stations.csv.
"""

import math
import os
import csv
import logging
import numpy as np

logger = logging.getLogger(__name__)

RE = 6378.137  # km

# ── Load ground station data ──────────────────────────────────────────────────
_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "ground_stations.csv"
)

_GROUND_STATIONS: list[dict] = []


def _load_stations() -> None:
    global _GROUND_STATIONS
    path = os.path.abspath(_DATA_PATH)
    if not os.path.exists(path):
        logger.warning("ground_stations.csv not found at %s", path)
        return
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            _GROUND_STATIONS.append({
                "id":       row["Station_ID"],
                "name":     row["Station_Name"],
                "lat_rad":  math.radians(float(row["Latitude"])),
                "lon_rad":  math.radians(float(row["Longitude"])),
                "lat_deg":  float(row["Latitude"]),
                "lon_deg":  float(row["Longitude"]),
                "elev_m":   float(row["Elevation_m"]),
                "min_el":   float(row["Min_Elevation_Angle_deg"]),
            })
    logger.info("Loaded %d ground stations", len(_GROUND_STATIONS))


_load_stations()


OMEGA_E = 7.2921159e-5  # rad/s (Earth's rotation rate)

def eci_to_geodetic(r_eci: list, time_s: float = 0.0) -> tuple[float, float, float]:
    """
    Convert ECI [x,y,z] km to (lat_deg, lon_deg, alt_km).
    Accounts for Earth's rotation if time_s (sim time) is provided.
    """
    x, y, z = r_eci
    # Sidereal rotation angle (approximate, starts at 0 RAAN)
    theta = (OMEGA_E * time_s) % (2 * math.pi)
    
    # Position in ECEF (approximate rotation)
    x_rot = x * math.cos(theta) + y * math.sin(theta)
    y_rot = -x * math.sin(theta) + y * math.cos(theta)
    
    lon_deg = math.degrees(math.atan2(y_rot, x_rot))
    lat_deg = math.degrees(math.atan2(z, math.sqrt(x_rot**2 + y_rot**2)))
    alt_km  = math.sqrt(x*x + y*y + z*z) - RE
    
    # Normalize lon to [-180, 180]
    if lon_deg > 180: lon_deg -= 360
    if lon_deg < -180: lon_deg += 360
    
    return lat_deg, lon_deg, alt_km


def vectorized_eci_to_geodetic(r_array: np.ndarray, time_s: float = 0.0) -> np.ndarray:
    """
    Vectorized version for thousands of objects, accounting for Earth rotation.
    r_array: (N, 3) matrix of [x, y, z] km.
    Returns: (N, 3) matrix of [lat_deg, lon_deg, alt_km].
    """
    x = r_array[:, 0]
    y = r_array[:, 1]
    z = r_array[:, 2]

    # Sidereal rotation
    theta = (OMEGA_E * time_s) % (2 * np.pi)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    
    # ECEF rotation
    x_rot = x * cos_t + y * sin_t
    y_rot = -x * sin_t + y * cos_t

    lon_deg = np.degrees(np.arctan2(y_rot, x_rot))
    r_xy = np.sqrt(x_rot**2 + y_rot**2)
    lat_deg = np.degrees(np.arctan2(z, r_xy))
    alt_km = np.sqrt(x**2 + y**2 + z**2) - RE

    # Normalize longitude
    lon_deg = (lon_deg + 180) % 360 - 180

    return np.column_stack([lat_deg, lon_deg, alt_km])


# ── Elevation angle from ground station to satellite ─────────────────────────

def _elevation_angle(gs: dict, sat_lat_deg: float, sat_lon_deg: float,
                     sat_alt_km: float) -> float:
    """
    Returns the elevation angle (degrees) of the satellite as seen from the GS.
    Negative means below the horizon.
    """
    gs_lat = gs["lat_rad"]
    sat_lat = math.radians(sat_lat_deg)
    delta_lon = math.radians(sat_lon_deg - gs["lon_deg"])

    # Spherical law of cosines for central angle
    cos_c = (math.sin(gs_lat) * math.sin(sat_lat) +
             math.cos(gs_lat) * math.cos(sat_lat) * math.cos(delta_lon))
    cos_c = max(-1.0, min(1.0, cos_c))   # clamp for float safety
    central_angle = math.acos(cos_c)

    rho = RE + sat_alt_km
    elev_rad = math.atan2(
        math.cos(central_angle) - RE / rho,
        math.sin(central_angle)
    )
    return math.degrees(elev_rad)


# ── Public API ────────────────────────────────────────────────────────────────

def check_los(r_eci: list) -> bool:
    """
    Returns True if the satellite (given its ECI position) has LOS to at
    least one ground station above the station's minimum elevation angle.
    """
    if not _GROUND_STATIONS:
        return True   # no data → assume LOS (safe default for testing)

    lat, lon, alt = eci_to_geodetic(r_eci)

    for gs in _GROUND_STATIONS:
        elev = _elevation_angle(gs, lat, lon, alt)
        if elev >= gs["min_el"]:
            return True
    return False


def visible_stations(r_eci: list) -> list[str]:
    """Returns list of station IDs currently visible to the satellite."""
    lat, lon, alt = eci_to_geodetic(r_eci)
    return [
        gs["name"] for gs in _GROUND_STATIONS
        if _elevation_angle(gs, lat, lon, alt) >= gs["min_el"]
    ]
