"""
astrosis/physics/ephemeris.py — Analytical Ephemeris Models
===========================================================
Low-precision analytical models for the Sun and Moon positions (ECI J2000).
Based on Meeus algorithms (Astronomical Algorithms, 2nd ed).
Accuracy: ~1 arcminute for Sun, ~2 arcminutes for Moon (sufficient for third-body).
"""

import math
import numpy as np

def _degrees(rad):
    return rad * 180.0 / math.pi

def _radians(deg):
    return deg * math.pi / 180.0

def sun_position_eci(mjd: float) -> tuple:
    """
    Calculate the ECI J2000 position of the Sun given the Modified Julian Date.
    Returns: (x, y, z) in km
    """
    # Number of days since J2000.0 (MJD 51544.5)
    d = mjd - 51544.5
    
    # Mean anomaly of the Sun
    g = 357.529 + 0.98560028 * d
    g_rad = _radians(g)
    
    # Mean longitude of the Sun
    q = 280.459 + 0.98564736 * d
    
    # Ecliptic longitude
    L = q + 1.915 * math.sin(g_rad) + 0.020 * math.sin(2 * g_rad)
    L_rad = _radians(L)
    
    # Distance to the Sun in AU
    R_au = 1.00014 - 0.01671 * math.cos(g_rad) - 0.00014 * math.cos(2 * g_rad)
    R_km = R_au * 149597870.7  # AU to km
    
    # Obliquity of the ecliptic
    e = 23.439 - 0.00000036 * d
    e_rad = _radians(e)
    
    # Position in ECI coordinates
    x = R_km * math.cos(L_rad)
    y = R_km * math.cos(e_rad) * math.sin(L_rad)
    z = R_km * math.sin(e_rad) * math.sin(L_rad)
    
    return x, y, z

def moon_position_eci(mjd: float) -> tuple:
    """
    Calculate the ECI J2000 position of the Moon given the Modified Julian Date.
    Returns: (x, y, z) in km
    """
    d = mjd - 51544.5
    
    # Moon's mean longitude
    L = 218.316 + 13.176396 * d
    # Moon's mean anomaly
    M = 134.963 + 13.064993 * d
    # Moon's mean distance from ascending node
    F = 93.272 + 13.229350 * d
    
    L_rad = _radians(L)
    M_rad = _radians(M)
    F_rad = _radians(F)
    
    # Ecliptic longitude and latitude
    l_ecl = L_rad + _radians(6.289 * math.sin(M_rad))
    b_ecl = _radians(5.128 * math.sin(F_rad))
    
    # Distance to the Moon in km
    distance_km = 385001.0 - 20905.0 * math.cos(M_rad)
    
    # Obliquity of the ecliptic
    e = 23.439 - 0.00000036 * d
    e_rad = _radians(e)
    
    # Position in ecliptic coordinates
    x_ecl = distance_km * math.cos(b_ecl) * math.cos(l_ecl)
    y_ecl = distance_km * math.cos(b_ecl) * math.sin(l_ecl)
    z_ecl = distance_km * math.sin(b_ecl)
    
    # Transform to ECI coordinates
    x = x_ecl
    y = y_ecl * math.cos(e_rad) - z_ecl * math.sin(e_rad)
    z = y_ecl * math.sin(e_rad) + z_ecl * math.cos(e_rad)
    
    return x, y, z
