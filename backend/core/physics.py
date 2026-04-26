"""
═══════════════════════════════════════════════════════════════════════════
 ACM CORE — physics.py
 Pure Python J2-aware RK4 Propagator
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import numpy as np
from typing import Tuple, Dict, Optional

# ── Official Constants (Section 3.2) ──────────────────────────────────────────
MU = 398600.4418      # km^3/s^2 (Earth's Gravitational Parameter)
RE = 6378.137         # km (Earth's Equatorial Radius)
J2 = 1.08263e-3       # Earth's Oblateness Perturbation Constant
EARTH_ROT_RATE = 7.292115e-5 # rad/s (Earth's Rotation Rate)

from datetime import datetime

class J2RK4Propagator:
    # ... (rest of the class remains same)
    @staticmethod
    def get_accelerations(r: np.ndarray, including_j2: bool = True) -> np.ndarray:
        """
        Calculates the instantaneous acceleration vector [ax, ay, az].
        Includes Two-Body gravity and optional J2 perturbation.
        """
        r_mag = np.linalg.norm(r)
        if r_mag < 6300.0:  # Surface/Center trap - prevent NaN/Inf (Earth radius ~6371km, buffer for LEO)
            return np.zeros(3)

        # 1. Two-Body (Point Mass) Acceleration
        a_2body = -MU * r / (r_mag**3)

        if not including_j2:
            return a_2body

        # 2. J2 Perturbation Acceleration (Section 3.2 formula)
        z_sq = r[2]**2
        r_sq = np.dot(r, r)
        
        # factor = (3/2) * J2 * mu * RE^2 / r^5
        factor = (1.5 * J2 * MU * (RE**2)) / (r_mag**5)
        
        # J2 scaling terms
        j2_x = r[0] * (5 * (z_sq / r_sq) - 1)
        j2_y = r[1] * (5 * (z_sq / r_sq) - 1)
        j2_z = r[2] * (5 * (z_sq / r_sq) - 3)
        
        a_j2 = factor * np.array([j2_x, j2_y, j2_z])

        return a_2body + a_j2

    def _f(self, state: np.ndarray, including_j2: bool = True) -> np.ndarray:
        """State derivative function S' = f(S)."""
        v = state[3:]
        a = self.get_accelerations(state[:3], including_j2=including_j2)
        return np.concatenate([v, a])

    def propagate(self, r: np.ndarray, v: np.ndarray, dt: float, including_j2: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Integrate the state forward by dt seconds using RK4.
        """
        s = np.concatenate([r, v])
        
        k1 = self._f(s, including_j2)
        k2 = self._f(s + 0.5 * dt * k1, including_j2)
        k3 = self._f(s + 0.5 * dt * k2, including_j2)
        k4 = self._f(s + dt * k3, including_j2)
        
        s_next = s + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
        
        return s_next[:3], s_next[3:]

    def batch_propagate(self, states: np.ndarray, dt: float) -> np.ndarray:
        """Propagate multiple objects at once."""
        return np.array([self.propagate(s[:3], s[3:], dt) for s in states])

def get_gmst(t: datetime) -> float:
    """
    Returns Greenwich Mean Sidereal Time (GMST) in radians.
    Simplified version using J2000 epoch.
    """
    # Seconds since J2000 epoch (2000-01-01 12:00:00 UTC)
    epoch = datetime(2000, 1, 1, 12, 0, 0)
    # Ensure t is naive or handle timezone
    if t.tzinfo is not None:
        t = t.replace(tzinfo=None)
    
    dt_sec = (t - epoch).total_seconds()
    
    # Rotation angle (rad) = theta0 + omega * dt
    # theta0 at J2000 is approx 4.894961 rad
    theta0 = 4.894961
    return (theta0 + EARTH_ROT_RATE * dt_sec) % (2 * np.pi)

def ecef_to_eci(r_ecef: np.ndarray, t: datetime) -> np.ndarray:
    """Rotates ECEF vector to ECI frame based on time."""
    gmst = get_gmst(t)
    cos_g = np.cos(gmst)
    sin_g = np.sin(gmst)
    
    # Rotation matrix around Z-axis
    rot = np.array([
        [cos_g, -sin_g, 0],
        [sin_g,  cos_g, 0],
        [0,      0,     1]
    ])
    return rot @ r_ecef

def eci_to_ecef(r_eci: np.ndarray, t: datetime) -> np.ndarray:
    """Rotates ECI vector to ECEF frame based on time."""
    gmst = get_gmst(t)
    cos_g = np.cos(gmst)
    sin_g = np.sin(gmst)
    
    # Inverse rotation (transpose)
    rot = np.array([
        [ cos_g, sin_g, 0],
        [-sin_g, cos_g, 0],
        [ 0,     0,     1]
    ])
    return rot @ r_eci

def eci_to_latlon(r: np.ndarray, t: Optional[datetime] = None) -> Tuple[float, float, float]:
    """
    Convert ECI (km) to Lat (deg), Lon (deg), Alt (km).
    If t is provided, accounts for Earth's rotation.
    """
    r_work = eci_to_ecef(r, t) if t else r
    
    x, y, z = r_work
    r_mag = np.linalg.norm(r_work)
    
    lat = np.degrees(np.arcsin(z / r_mag)) if r_mag > 0 else 0
    lon = np.degrees(np.arctan2(y, x))
    alt = r_mag - RE
    
    return float(lat), float(lon), float(alt)

def latlon_to_eci(lat: float, lon: float, alt: float, t: Optional[datetime] = None) -> np.ndarray:
    """
    Convert Lat (deg), Lon (deg), Alt (km) to ECI (km).
    If t is provided, accounts for Earth's rotation.
    """
    r_mag = RE + alt
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    
    x_ecef = r_mag * np.cos(lat_rad) * np.cos(lon_rad)
    y_ecef = r_mag * np.cos(lat_rad) * np.sin(lon_rad)
    z_ecef = r_mag * np.sin(lat_rad)
    
    r_ecef = np.array([x_ecef, y_ecef, z_ecef])
    
    return ecef_to_eci(r_ecef, t) if t else r_ecef

def eci_to_rtn(r: np.ndarray, v: np.ndarray, r_target: np.ndarray) -> np.ndarray:
    """
    Converts a relative ECI vector (r - r_ref) to the RTN frame.
    """
    u_r = r / np.linalg.norm(r)
    h = np.cross(r, v)
    u_n = h / np.linalg.norm(h)
    u_t = np.cross(u_n, u_r)
    
    rot = np.vstack([u_r, u_t, u_n])
    dr = r_target - r
    return rot @ dr

def rtn_to_eci(r: np.ndarray, v: np.ndarray, dr_rtn: np.ndarray) -> np.ndarray:
    """
    Converts a relative vector in RTN to the absolute ECI frame.
    """
    u_r = r / np.linalg.norm(r)
    h = np.cross(r, v)
    u_n = h / np.linalg.norm(h)
    u_t = np.cross(u_n, u_r)
    
    rot_eci_rtn = np.column_stack([u_r, u_t, u_n])
    dr_eci = rot_eci_rtn @ dr_rtn
    return r + dr_eci

