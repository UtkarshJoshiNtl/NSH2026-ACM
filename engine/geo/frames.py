"""
astrosis/frames.py — Coordinate Reference Frames
==================================================
Conversions between ECI (Earth-Centered Inertial), ECEF (Earth-Centered, Earth-Fixed),
and Topocentric (Observer-based) frames.
"""

import numpy as np
from datetime import datetime
from ..constants import RE, F_WGS84, E2_WGS84

def gmst_from_datetime(dt: datetime) -> float:
    """
    Compute Greenwich Mean Sidereal Time (GMST) in radians.
    Uses simplified 1997 IAU formula good for coarse analysis.
    """
    # Julian Date
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    
    if m <= 2:
        y -= 1
        m += 12
        
    A = np.floor(y / 100.0)
    B = 2.0 - A + np.floor(A / 4.0)
    
    jd = np.floor(365.25 * (y + 4716.0)) + np.floor(30.6001 * (m + 1.0)) + d + B - 1524.5
    t_ut1 = (jd - 2451545.0) / 36525.0
    
    # GMST in seconds
    gmst_sec = 67310.54841 + (876600.0 * 3600.0 + 8640184.812866) * t_ut1 + 0.093104 * t_ut1**2 - 6.2e-6 * t_ut1**3
    
    # Radians — np.mod always returns [0, 2π), no negative guard needed
    gmst_rad = np.mod(gmst_sec * (2 * np.pi / 86400.0), 2 * np.pi)
    return gmst_rad

def eci_to_ecef(r_eci: np.ndarray, dt: datetime) -> np.ndarray:
    """
    Convert ECI position vector [km] to ECEF position vector [km].
    r_eci can be shape (3,) or (N, 3).
    """
    theta = gmst_from_datetime(dt)
    
    cost = np.cos(theta)
    sint = np.sin(theta)
    
    R = np.array([
        [cost,  sint, 0],
        [-sint, cost, 0],
        [0,     0,    1]
    ])
    
    # If single vector
    if r_eci.ndim == 1:
        return R @ r_eci
    # If vectorized 
    return (R @ r_eci.T).T

def ecef_to_geodetic(r_ecef: np.ndarray) -> tuple:
    """
    Convert ECEF [x,y,z] km to Geodetic (Lat, Lon, Alt).
    Returns (lat_rad, lon_rad, alt_km).
    Uses Bowring iterative method with a pole singularity guard.
    """
    x, y, z = r_ecef[..., 0], r_ecef[..., 1], r_ecef[..., 2]

    lon = np.arctan2(y, x)
    p = np.sqrt(x**2 + y**2)

    # --- Pole singularity guard ---
    # When p ≈ 0 (at or very near a geographic pole), cos(lat) → 0
    # which causes alt = p / cos(lat) to blow up to nan/inf.
    if np.ndim(p) == 0 and p < 1e-10:
        b = RE * (1 - F_WGS84)
        lat = np.pi / 2 if z >= 0 else -np.pi / 2
        alt = float(np.abs(z)) - b
        return lat, lon, alt

    lat = np.arctan2(z, p * (1 - E2_WGS84))  # Initial approximation
    N = RE

    # Iterate (Bowring, 5 iterations sufficient for mm-level accuracy)
    for _ in range(5):
        sin_lat = np.sin(lat)
        N = RE / np.sqrt(1 - E2_WGS84 * sin_lat**2)
        cos_lat = np.cos(lat)
        # Guard against cos_lat = 0 for vectorised arrays near poles
        safe_cos = np.where(np.abs(cos_lat) < 1e-12, 1e-12, cos_lat) if np.ndim(cos_lat) > 0 else (1e-12 if abs(float(cos_lat)) < 1e-12 else cos_lat)
        alt = p / safe_cos - N
        lat = np.arctan2(z, p * (1 - E2_WGS84 * N / (N + alt)))

    return lat, lon, alt

def geodetic_to_ecef(lat_rad: float, lon_rad: float, alt_km: float) -> np.ndarray:
    """
    Convert Geodetic (Lat, Lon, Alt) to ECEF [x,y,z] in km.
    """
    N = RE / np.sqrt(1 - E2_WGS84 * np.sin(lat_rad)**2)
    x = (N + alt_km) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N + alt_km) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N * (1 - E2_WGS84) + alt_km) * np.sin(lat_rad)
    return np.array([x, y, z])

def topocentric_aer(r_sat_ecef: np.ndarray, lat_rad: float, lon_rad: float, alt_km: float) -> tuple:
    """
    Compute Azimuth (rad), Elevation (rad), and Range (km) for an ECEF satellite position 
    relative to a specific topocentric observer.
    """
    r_obs = geodetic_to_ecef(lat_rad, lon_rad, alt_km)
    
    # Vector from observer to satellite
    rho = r_sat_ecef - r_obs
    
    # Rotation matrix to topocentric ENU (East-North-Up)
    clat = np.cos(lat_rad)
    slat = np.sin(lat_rad)
    clon = np.cos(lon_rad)
    slon = np.sin(lon_rad)
    
    # ECEF -> ENU matrix
    M = np.array([
        [-slon,        clon,        0],
        [-slat*clon,  -slat*slon,  clat],
        [ clat*clon,   clat*slon,  slat]
    ])
    
    # If vectorized
    if rho.ndim == 1:
        enu = M @ rho
    else:
        enu = (M @ rho.T).T
        
    e, n, u = enu[..., 0], enu[..., 1], enu[..., 2]
    
    r = np.sqrt(e**2 + n**2 + u**2)
    el = np.arcsin(u / r)
    az = np.mod(np.arctan2(e, n), 2 * np.pi)
    
    return az, el, r
