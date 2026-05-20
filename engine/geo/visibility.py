import numpy as np
from datetime import datetime
from ..constants import RE, RS_SUN, AU
from ..core.ephemeris import sun_position_eci as _sun_eci_mjd

__all__ = ["sun_position_eci", "check_eclipse", "is_optically_visible"]


def _julian_date(dt: datetime) -> float:
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    A = np.floor(y / 100.0)
    B = 2.0 - A + np.floor(A / 4.0)
    jd = np.floor(365.25 * (y + 4716.0)) + np.floor(30.6001 * (m + 1.0)) + d + B - 1524.5
    return jd


def sun_position_eci(dt: datetime) -> np.ndarray:
    mjd = _julian_date(dt) - 2400000.5
    return np.array(_sun_eci_mjd(mjd))


def check_eclipse(r_sat: np.ndarray, r_sun: np.ndarray) -> str:
    sat_mag = np.linalg.norm(r_sat)
    sun_mag = np.linalg.norm(r_sun)
    sun_hat = r_sun / sun_mag
    sat_proj = np.dot(r_sat, sun_hat)

    if sat_proj > 0:
        return "SUNLIGHT"

    perp = np.sqrt(max(sat_mag**2 - sat_proj**2, 0.0))
    sin_pen = (RS_SUN + RE) / sun_mag
    sin_umb = (RS_SUN - RE) / sun_mag
    axis_dist = abs(sat_proj)
    pen_radius = RE + axis_dist * sin_pen
    umb_radius = RE - axis_dist * sin_umb

    if perp < umb_radius:
        return "UMBRA"
    elif perp < pen_radius:
        return "PENUMBRA"
    return "SUNLIGHT"


def is_optically_visible(el_rad: float, r_sat_eci: np.ndarray, dt: datetime, min_elevation_deg: float = 10.0) -> bool:
    if np.degrees(el_rad) < min_elevation_deg:
        return False
    return check_eclipse(r_sat_eci, sun_position_eci(dt)) != "UMBRA"
