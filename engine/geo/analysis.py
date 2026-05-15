"""
astrosis/analysis.py — High-Level Analysis Routines
=====================================================
Combines physics propagation, frames, and visibility logic to output
structured JSON reports and event logs.
"""

from datetime import datetime, timedelta
import numpy as np

from .frames import eci_to_ecef, topocentric_aer, gmst_from_datetime
from .visibility import is_optically_visible
from ..core.accelerator import propagate_with_drag


def _julian_date(dt: datetime) -> float:
    """Return the Julian Date for a naïve UTC datetime."""
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
    """
    Approximate equation of the equinoxes in radians.

    This is a small-angle correction, adequate for the validation scripts that
    compare TEME output from SGP4 against the numerical propagator.
    """
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


def _teme_to_eci(r_teme, v_teme, dt: datetime):
    """
    Approximate TEME -> ECI/GCRF conversion.

    The position correction is a small rotation about the z-axis by the
    equation of the equinoxes. Velocity is rotated with the same transform and
    gets a small transport correction from the time derivative of that angle.
    """
    r = np.asarray(r_teme, dtype=np.float64)
    v = np.asarray(v_teme, dtype=np.float64)

    theta = _equation_of_equinoxes(dt)
    c = np.cos(theta)
    s = np.sin(theta)
    rot = np.array([[c, -s, 0.0],
                    [s,  c, 0.0],
                    [0.0, 0.0, 1.0]])

    r_eci = rot @ r

    # Finite-difference the tiny correction angle to capture the transport term.
    theta_prev = _equation_of_equinoxes(dt - timedelta(seconds=1))
    theta_next = _equation_of_equinoxes(dt + timedelta(seconds=1))
    theta_dot = 0.5 * (theta_next - theta_prev)
    omega = np.array([0.0, 0.0, theta_dot], dtype=np.float64)
    v_eci = rot @ v + np.cross(omega, r_eci)
    return r_eci, v_eci


def report_passes(
    norad_id: int,
    lat: float,
    lon: float,
    alt: float,
    start_dt: datetime,
    hours: float,
    dt_step: float = 60.0,
    sat_area: float = 10.0,
    sat_mass: float = 1000.0,
    sat_cd: float = 2.2,
    ingestor=None,   # dependency injection — pass a TLEIngestor or mock; defaults to global singleton
):
    """
    Predict satellite passes for a ground station.

    Args:
        norad_id:  NORAD catalog ID.
        lat, lon:  Ground station coordinates in decimal degrees.
        alt:       Ground station altitude in km.
        start_dt:  Simulation start time (UTC, naïve datetime).
        hours:     Horizon to predict over.
        dt_step:   Propagation time step in seconds (default 60 s).
        sat_area:  Satellite cross-sectional area in m² (drag, default 10 m²).
        sat_mass:  Satellite total mass in kg (drag, default 1000 kg).
        sat_cd:    Drag coefficient (default 2.2).
        ingestor:  TLEIngestor instance (or mock). Defaults to module-level singleton.
    """
    if ingestor is None:
        from ..io.data import tle_ingestor as _tle_ingestor
        ingestor = _tle_ingestor
    satellites = ingestor.get_satellites(satellite_id=str(norad_id), force_refresh=False)
    if not satellites:
        return {"error": "Satellite not found."}

    tle_data = satellites[0]

    # --- Build SGP4 record ---
    from sgp4.api import Satrec, jday
    satrec = Satrec.twoline2rv(tle_data["line1"], tle_data["line2"])

    # Use sgp4.api.jday for a correct Julian date split (avoids accumulated float error)
    jd, jdfrac = jday(
        start_dt.year, start_dt.month, start_dt.day,
        start_dt.hour, start_dt.minute, start_dt.second + start_dt.microsecond / 1e6,
    )
    err, r_teme, v_teme = satrec.sgp4(jd, jdfrac)

    if err != 0:
        return {"error": f"SGP4 propagation error (code {err})."}

    r_eci, v_eci = _teme_to_eci(np.array(r_teme), np.array(v_teme), start_dt)
    state = list(r_eci) + list(v_eci)

    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    passes = []
    current_pass = None

    time_sim = start_dt
    steps = int((hours * 3600) / dt_step)

    for _ in range(steps):
        state = propagate_with_drag(state, dt_step, sat_area, sat_mass, sat_cd)
        time_sim += timedelta(seconds=dt_step)

        r_eci = np.array(state[:3])
        r_ecef = eci_to_ecef(r_eci, time_sim)
        az, el, rng = topocentric_aer(r_ecef, lat_rad, lon_rad, alt)

        el_deg = float(np.degrees(el))
        visible = is_optically_visible(el, r_eci, time_sim, min_elevation_deg=10.0)

        if el_deg >= 10.0:
            if current_pass is None:
                current_pass = {
                    "start_time": time_sim.isoformat(),
                    "max_elevation": el_deg,
                    "visible": visible,
                    "points": [],
                }
            if el_deg > current_pass["max_elevation"]:
                current_pass["max_elevation"] = el_deg
            if visible:
                current_pass["visible"] = True
            current_pass["points"].append({
                "time": time_sim.isoformat(),
                "az_deg": float(np.degrees(az)),
                "el_deg": el_deg,
                "range_km": float(rng),
                "is_illuminated": visible,
            })
        else:
            if current_pass is not None:
                current_pass["end_time"] = time_sim.isoformat()
                passes.append(current_pass)
                current_pass = None

    if current_pass is not None:
        current_pass["end_time"] = time_sim.isoformat()
        passes.append(current_pass)

    return {
        "satellite": tle_data["satellite_name"],
        "norad_id": norad_id,
        "ground_station": {"lat": lat, "lon": lon, "alt_km": alt},
        "drag_params": {"area_m2": sat_area, "mass_kg": sat_mass, "cd": sat_cd},
        "passes": passes,
    }
