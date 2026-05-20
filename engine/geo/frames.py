"""ECI/ECEF/geodetic/topocentric coordinate conversions."""

import numpy as np
from datetime import datetime, timedelta
from ..constants import RE, F_WGS84, E2_WGS84

def gmst_from_datetime(dt: datetime) -> float:
    """GMST in radians (1997 IAU formula)."""
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
    
    # np.mod always returns [0, 2π)
    gmst_rad = np.mod(gmst_sec * (2 * np.pi / 86400.0), 2 * np.pi)
    return gmst_rad

def eci_to_ecef(r_eci: np.ndarray, dt: datetime) -> np.ndarray:
    """ECI to ECEF, handles (3,) and (N,3) arrays."""
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

    # Guard against pole singularity (cos(lat) → 0)
    if np.ndim(p) == 0 and p < 1e-10:
        b = RE * (1 - F_WGS84)
        lat = np.pi / 2 if z >= 0 else -np.pi / 2
        alt = float(np.abs(z)) - b
        return lat, lon, alt

    lat = np.arctan2(z, p * (1 - E2_WGS84))  # Initial approximation
    N = RE

    # Bowring iteration (5 is enough for mm accuracy)
    for _ in range(5):
        sin_lat = np.sin(lat)
        N = RE / np.sqrt(1 - E2_WGS84 * sin_lat**2)
        cos_lat = np.cos(lat)
        # Guard against cos_lat = 0 for vectorized arrays near poles
        safe_cos = np.where(np.abs(cos_lat) < 1e-12, 1e-12, cos_lat) if np.ndim(cos_lat) > 0 else (1e-12 if abs(float(cos_lat)) < 1e-12 else cos_lat)
        alt = p / safe_cos - N
        lat = np.arctan2(z, p * (1 - E2_WGS84 * N / (N + alt)))

    return lat, lon, alt

def geodetic_to_ecef(lat_rad: float, lon_rad: float, alt_km: float) -> np.ndarray:
    """Geodetic (lat, lon, alt) → ECEF [km]."""
    N = RE / np.sqrt(1 - E2_WGS84 * np.sin(lat_rad)**2)
    x = (N + alt_km) * np.cos(lat_rad) * np.cos(lon_rad)
    y = (N + alt_km) * np.cos(lat_rad) * np.sin(lon_rad)
    z = (N * (1 - E2_WGS84) + alt_km) * np.sin(lat_rad)
    return np.array([x, y, z])

def topocentric_aer(r_sat_ecef: np.ndarray, lat_rad: float, lon_rad: float, alt_km: float) -> tuple:
    """Azimuth, elevation, range from an observer to an ECEF position."""
    r_obs = geodetic_to_ecef(lat_rad, lon_rad, alt_km)
    
    # Vector from observer to satellite
    rho = r_sat_ecef - r_obs
    
    # ECEF → ENU rotation
    clat = np.cos(lat_rad)
    slat = np.sin(lat_rad)
    clon = np.cos(lon_rad)
    slon = np.sin(lon_rad)
    
    # ECEF → ENU matrix
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


# TEME → ECI / GCRF (used for SGP4 comparison in validation)

def _julian_date(dt: datetime) -> float:
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60.0 + (dt.second + dt.microsecond / 1e6) / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = int(y / 100)
    b = 2 - a + int(a / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _equation_of_equinoxes(dt: datetime) -> float:
    jd = _julian_date(dt)
    t = (jd - 2451545.0) / 36525.0

    l = np.deg2rad(280.4665 + 36000.7698 * t)
    lp = np.deg2rad(218.3165 + 481267.8813 * t)
    omega = np.deg2rad(125.04452 - 1934.136261 * t)

    dpsi_arcsec = (
        -17.20 * np.sin(omega)
        - 1.32 * np.sin(2.0 * l)
        - 0.23 * np.sin(2.0 * lp)
        + 0.21 * np.sin(2.0 * omega)
    )

    eps0_arcsec = (
        84381.448
        - 46.8150 * t
        - 0.00059 * t * t
        + 0.001813 * t * t * t
    )
    eps_arcsec = eps0_arcsec + (
        9.20 * np.cos(omega)
        + 0.57 * np.cos(2.0 * l)
        + 0.10 * np.cos(2.0 * lp)
        - 0.09 * np.cos(2.0 * omega)
    )

    eps = np.deg2rad(eps_arcsec / 3600.0)
    return np.deg2rad((dpsi_arcsec * np.cos(eps)) / 3600.0)


def teme_to_eci(r_teme, v_teme, dt: datetime):
    r = np.asarray(r_teme, dtype=np.float64)
    v = np.asarray(v_teme, dtype=np.float64)

    theta = _equation_of_equinoxes(dt)
    c = np.cos(theta)
    s = np.sin(theta)
    rot = np.array([[c, -s, 0.0],
                    [s,  c, 0.0],
                    [0.0, 0.0, 1.0]])

    r_eci = rot @ r

    theta_prev = _equation_of_equinoxes(dt - timedelta(seconds=1))
    theta_next = _equation_of_equinoxes(dt + timedelta(seconds=1))
    theta_dot = 0.5 * (theta_next - theta_prev)
    omega = np.array([0.0, 0.0, theta_dot], dtype=np.float64)
    v_eci = rot @ v + np.cross(omega, r_eci)
    return r_eci, v_eci
