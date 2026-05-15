"""
astrosis/analysis.py — High-Level Analysis Routines
=====================================================
Combines physics propagation, frames, and visibility logic to output
structured JSON reports and event logs.
"""

from datetime import datetime, timedelta
import numpy as np

from ..io.data import tle_ingestor
from .frames import eci_to_ecef, topocentric_aer, gmst_from_datetime
from .visibility import is_optically_visible
from ..core.accelerator import propagate_with_drag
from sgp4.api import Satrec, jday


def _teme_to_eci(r_teme: np.ndarray, v_teme: np.ndarray, dt: datetime):
    """
    TEME is already an inertial frame, differing from ECI/GCRF only by the
    equation of the equinoxes (< 1"). We approximate them as perfectly aligned.
    """
    return r_teme, v_teme


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
        ingestor = tle_ingestor
    satellites = ingestor.get_satellites(satellite_id=str(norad_id), force_refresh=False)
    if not satellites:
        return {"error": "Satellite not found."}

    tle_data = satellites[0]

    # --- Build SGP4 record ---
    satrec = Satrec.twoline2rv(tle_data["line1"], tle_data["line2"])

    # Use sgp4.api.jday for a correct Julian date split (avoids accumulated float error)
    jd, jdfrac = jday(
        start_dt.year, start_dt.month, start_dt.day,
        start_dt.hour, start_dt.minute, start_dt.second + start_dt.microsecond / 1e6,
    )
    err, r_teme, v_teme = satrec.sgp4(jd, jdfrac)

    if err != 0:
        return {"error": f"SGP4 propagation error (code {err})."}

    # --- Fix #2: convert TEME → ECI before handing to RK4 propagator ---
    r_eci0, v_eci0 = _teme_to_eci(np.array(r_teme), np.array(v_teme), start_dt)
    state = list(r_eci0) + list(v_eci0)

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
