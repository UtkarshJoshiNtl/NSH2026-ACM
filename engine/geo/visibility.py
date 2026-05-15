"""
astrosis/visibility.py — Satellite Visibility & Eclipse Logic
=============================================================
Calculates Sun position, Earth shadow (Umbra/Penumbra) interactions, 
and overall satellite visibility conditions based on observer topology.
"""

import numpy as np
from datetime import datetime
from ..constants import RE, RS_SUN, AU

def sun_position_eci(dt: datetime) -> np.ndarray:
    """
    Compute approximate Sun position vector in ECI frame [km].
    Accurate to ~1 arcminute.
    """
    # Julian date
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    
    if m <= 2:
        y -= 1
        m += 12
        
    A = np.floor(y / 100.0)
    B = 2.0 - A + np.floor(A / 4.0)
    jd = np.floor(365.25 * (y + 4716.0)) + np.floor(30.6001 * (m + 1.0)) + d + B - 1524.5
    
    n = jd - 2451545.0
    
    # Mean longitude of Sun
    L = np.mod(280.460 + 0.9856474 * n, 360.0)
    # Mean anomaly of Sun
    g = np.mod(357.528 + 0.9856003 * n, 360.0)
    
    L_rad = np.radians(L)
    g_rad = np.radians(g)
    
    # Ecliptic longitude
    lambda_ecliptic = L_rad + np.radians(1.915 * np.sin(g_rad) + 0.020 * np.sin(2 * g_rad))
    
    # Distance
    R_au = 1.00014 - 0.01671 * np.cos(g_rad) - 0.00014 * np.cos(2 * g_rad)
    R_km = R_au * AU
    
    # Obliquity of ecliptic
    epsilon = np.radians(23.439 - 0.0000004 * n)
    
    x = R_km * np.cos(lambda_ecliptic)
    y = R_km * np.cos(epsilon) * np.sin(lambda_ecliptic)
    z = R_km * np.sin(epsilon) * np.sin(lambda_ecliptic)
    
    return np.array([x, y, z])

def check_eclipse(r_sat: np.ndarray, r_sun: np.ndarray) -> str:
    """
    Check if satellite is in Earth's shadow using the Montenbruck & Gill (2000)
    conical shadow algorithm.

    Args:
        r_sat: Satellite ECI position [km]
        r_sun: Sun ECI position [km] (Earth-centred)

    Returns: "SUNLIGHT", "PENUMBRA", or "UMBRA"
    """
    sat_mag = np.linalg.norm(r_sat)
    sun_mag = np.linalg.norm(r_sun)

    # Unit vector from Earth toward Sun
    sun_hat = r_sun / sun_mag

    # Projection of satellite position onto Earth-Sun direction
    sat_proj = np.dot(r_sat, sun_hat)

    # If satellite is on the sunward side of Earth, it cannot be in shadow
    if sat_proj > 0:
        return "SUNLIGHT"

    # Perpendicular distance from satellite to the Earth-Sun axis
    perp = np.sqrt(max(sat_mag**2 - sat_proj**2, 0.0))

    # Half-angles of penumbra and umbra cones
    # sin_pen > 0 always (penumbra cone opens outward)
    # sin_umb < 0 when umbra cone converges behind Earth (typical LEO/MEO case)
    sin_pen = (RS_SUN + RE) / sun_mag   # penumbra: satellite enters if perp < pen_radius
    sin_umb = (RS_SUN - RE) / sun_mag   # umbra: satellite enters if perp < umb_radius

    # Projected distance along the axis (negative, satellite is on anti-sun side)
    axis_dist = abs(sat_proj)

    pen_radius = RE + axis_dist * sin_pen   # penumbra shadow radius at sat distance
    umb_radius = RE - axis_dist * sin_umb   # umbra shadow radius at sat distance (may be negative for far objects)

    if perp < umb_radius:
        return "UMBRA"
    elif perp < pen_radius:
        return "PENUMBRA"
    else:
        return "SUNLIGHT"

def is_optically_visible(el_rad: float, r_sat_eci: np.ndarray, dt: datetime, min_elevation_deg: float = 10.0) -> bool:
    """
    Check if a satellite is optically visible to an observer.
    Conditions:
    1. Satellite is above the local horizon by minimum elevation
    2. Satellite is illuminated by the Sun
    3. Observer is in darkness (the sun is below local horizon) -- skipped here as it requires observer sun-elevation.
    """
    if np.degrees(el_rad) < min_elevation_deg:
        return False
        
    r_sun = sun_position_eci(dt)
    eclipse_state = check_eclipse(r_sat_eci, r_sun)
    
    return eclipse_state != "UMBRA"
