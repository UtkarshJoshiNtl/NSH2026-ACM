"""Analytical Sun/Moon positions (Meeus algorithms, ~1 arcmin accuracy)."""

import math

def _radians(deg):
    return deg * math.pi / 180.0

def sun_position_eci(mjd: float) -> tuple:
    """ECI J2000 Sun position from MJD (Meeus algorithm)."""
    d = mjd - 51544.5
    g = 357.529 + 0.98560028 * d
    g_rad = _radians(g)
    q = 280.459 + 0.98564736 * d
    L = q + 1.915 * math.sin(g_rad) + 0.020 * math.sin(2 * g_rad)
    L_rad = _radians(L)
    R_au = 1.00014 - 0.01671 * math.cos(g_rad) - 0.00014 * math.cos(2 * g_rad)
    R_km = R_au * 149597870.7
    e = 23.439 - 0.00000036 * d
    e_rad = _radians(e)
    x = R_km * math.cos(L_rad)
    y = R_km * math.cos(e_rad) * math.sin(L_rad)
    z = R_km * math.sin(e_rad) * math.sin(L_rad)
    return x, y, z

def moon_position_eci(mjd: float) -> tuple:
    """ECI J2000 Moon position from MJD (Meeus algorithm)."""
    d = mjd - 51544.5
    L = 218.316 + 13.176396 * d
    M = 134.963 + 13.064993 * d
    F = 93.272 + 13.229350 * d
    L_rad = _radians(L)
    M_rad = _radians(M)
    F_rad = _radians(F)
    l_ecl = L_rad + _radians(6.289 * math.sin(M_rad))
    b_ecl = _radians(5.128 * math.sin(F_rad))
    distance_km = 385001.0 - 20905.0 * math.cos(M_rad)
    e = 23.439 - 0.00000036 * d
    e_rad = _radians(e)
    x_ecl = distance_km * math.cos(b_ecl) * math.cos(l_ecl)
    y_ecl = distance_km * math.cos(b_ecl) * math.sin(l_ecl)
    z_ecl = distance_km * math.sin(b_ecl)
    x = x_ecl
    y = y_ecl * math.cos(e_rad) - z_ecl * math.sin(e_rad)
    z = y_ecl * math.sin(e_rad) + z_ecl * math.cos(e_rad)
    return x, y, z
