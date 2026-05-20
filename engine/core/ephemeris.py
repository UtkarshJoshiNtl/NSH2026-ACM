import math
import numpy as np

__all__ = ["sun_position_eci", "moon_position_eci"]


def _rad(deg):
    return deg * math.pi / 180.0


def sun_position_eci(mjd: float) -> tuple:
    d = mjd - 51544.5
    g = 357.529 + 0.98560028 * d
    g_rad = _rad(g)
    q = 280.459 + 0.98564736 * d
    L = q + 1.915 * math.sin(g_rad) + 0.020 * math.sin(2 * g_rad)
    R_au = 1.00014 - 0.01671 * math.cos(g_rad) - 0.00014 * math.cos(2 * g_rad)
    R_km = R_au * 149597870.7
    e = _rad(23.439 - 0.00000036 * d)
    L_rad = _rad(L)
    return (
        R_km * math.cos(L_rad),
        R_km * math.cos(e) * math.sin(L_rad),
        R_km * math.sin(e) * math.sin(L_rad),
    )


def moon_position_eci(mjd: float) -> tuple:
    d = mjd - 51544.5
    L = 218.316 + 13.176396 * d
    M = 134.963 + 13.064993 * d
    F = 93.272 + 13.229350 * d
    L_rad, M_rad, F_rad = _rad(L), _rad(M), _rad(F)
    l_ecl = L_rad + _rad(6.289 * math.sin(M_rad))
    b_ecl = _rad(5.128 * math.sin(F_rad))
    dist = 385001.0 - 20905.0 * math.cos(M_rad)
    e = _rad(23.439 - 0.00000036 * d)
    x_ecl = dist * math.cos(b_ecl) * math.cos(l_ecl)
    y_ecl = dist * math.cos(b_ecl) * math.sin(l_ecl)
    z_ecl = dist * math.sin(b_ecl)
    return (
        x_ecl,
        y_ecl * math.cos(e) - z_ecl * math.sin(e),
        y_ecl * math.sin(e) + z_ecl * math.cos(e),
    )
