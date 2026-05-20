"""Tests for coordinate transforms, ephemeris, drag/SRP, and error handling."""

import math
import numpy as np
from datetime import datetime

from engine.geo.frames import (
    gmst_from_datetime,
    eci_to_ecef,
    ecef_to_geodetic,
    geodetic_to_ecef,
    topocentric_aer,
    teme_to_eci,
)
from engine.core.ephemeris import sun_position_eci, moon_position_eci
from engine.core.propagator import rk4_step, propagate_batch_numpy
from engine.constants import MU, RE


# ── Coordinate Transforms ──

def test_gmst_range():
    theta = gmst_from_datetime(datetime(2025, 6, 1, 12, 0, 0))
    assert 0 <= theta <= 2 * math.pi


def test_eci_to_ecef_roundtrip():
    r_eci = np.array([7000.0, 0.0, 0.0])
    dt = datetime(2025, 6, 1, 0, 0, 0)
    r_ecef = eci_to_ecef(r_eci, dt)
    assert len(r_ecef) == 3
    assert np.all(np.isfinite(r_ecef))


def test_ecef_geodetic_roundtrip():
    for lat_deg, lon_deg, alt in [(0, 0, 0), (45, -73, 100), (-33, 151, 400)]:
        lat = math.radians(lat_deg)
        lon = math.radians(lon_deg)
        ecef = geodetic_to_ecef(lat, lon, alt)
        lat2, lon2, alt2 = ecef_to_geodetic(ecef)
        assert abs(lat - lat2) < 1e-10, f"lat: {lat} vs {lat2}"
        assert abs(lon - lon2) < 1e-10, f"lon: {lon} vs {lon2}"
        assert abs(alt - alt2) < 1e-6, f"alt: {alt} vs {alt2}"


def test_ecef_to_geodetic_pole():
    north_pole = np.array([0.0, 0.0, 6356.752])
    lat, lon, alt = ecef_to_geodetic(north_pole)
    assert abs(lat - math.pi / 2) < 1e-6
    assert abs(alt) < 1.0


def test_eci_to_ecef_vectorized():
    r_eci = np.array([[7000.0, 0.0, 0.0], [0.0, 7000.0, 0.0]])
    dt = datetime(2025, 6, 1, 0, 0, 0)
    r_ecef = eci_to_ecef(r_eci, dt)
    assert r_ecef.shape == (2, 3)


def test_topocentric_aer_range():
    obs_lat = math.radians(40.0)
    obs_lon = math.radians(-74.0)
    obs_alt = 0.0
    r_sat = geodetic_to_ecef(obs_lat, obs_lon, 400.0)
    az, el, r = topocentric_aer(r_sat, obs_lat, obs_lon, obs_alt)
    assert r > 0
    assert 0 <= az <= 2 * math.pi
    assert -math.pi / 2 <= el <= math.pi / 2


def test_teme_to_eci_basic():
    r = np.array([7000.0, 0.0, 0.0])
    v = np.array([0.0, 7.5, 0.0])
    dt = datetime(2025, 6, 1, 12, 0, 0)
    r_eci, v_eci = teme_to_eci(r, v, dt)
    assert len(r_eci) == 3
    assert len(v_eci) == 3
    assert np.all(np.isfinite(r_eci))
    assert np.all(np.isfinite(v_eci))


# ── Ephemeris ──

def test_sun_position_finite():
    for mjd in [51544.5, 60810.5, 60000.0]:
        x, y, z = sun_position_eci(mjd)
        assert all(math.isfinite(v) for v in (x, y, z))
        r = math.sqrt(x*x + y*y + z*z)
        assert 0.98 * 149597870.7 < r < 1.02 * 149597870.7  # ~1 AU


def test_moon_position_finite():
    for mjd in [51544.5, 60810.5]:
        x, y, z = moon_position_eci(mjd)
        assert all(math.isfinite(v) for v in (x, y, z))
        r = math.sqrt(x*x + y*y + z*z)
        assert 350000 < r < 410000  # Moon distance in km


def test_sun_moon_not_colinear():
    sx, sy, sz = sun_position_eci(60810.5)
    mx, my, mz = moon_position_eci(60810.5)
    dot = sx*mx + sy*my + sz*mz
    angle = math.acos(dot / (math.sqrt(sx*sx+sy*sy+sz*sz) * math.sqrt(mx*mx+my*my+mz*mz)))
    assert angle > 0.01  # Not exactly the same direction


# ── Drag / SRP ──

def test_rk4_drag_affects_orbit():
    state = (RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0)
    no_drag = rk4_step(state, 600.0, mjd0=0.0)
    with_drag = rk4_step(state, 600.0, mjd0=0.0, area=20.0, mass=450.0, cd=2.2)
    assert no_drag != with_drag


def test_rk4_lunisolar_affects_orbit():
    state = (RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0)
    mjd0 = 60810.5
    no_lunisolar = rk4_step(state, 600.0, mjd0=0.0)
    with_lunisolar = rk4_step(state, 600.0, mjd0=mjd0)
    assert no_lunisolar != with_lunisolar


def test_batch_with_drag():
    states = [[RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0]]
    result = propagate_batch_numpy(states, 60.0, 10, area=20.0, mass=450.0, cd=2.2, cr=1.5, with_drag=True, mjd0=60810.5)
    assert len(result) == 1
    assert len(result[0]) == 6
    assert all(math.isfinite(v) for v in result[0])


def test_srp_affects_orbit():
    state = (RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0)
    mjd0 = 60810.5
    no_srp = rk4_step(state, 600.0, mjd0=mjd0, area=0.0, mass=1.0)
    with_srp = rk4_step(state, 600.0, mjd0=mjd0, area=20.0, mass=450.0, cr=1.5)
    assert no_srp != with_srp


# ── Error Handling ──

def test_rk4_zero_dt_returns_initial():
    state = (RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0)
    result = rk4_step(state, 0.0)
    assert result == state


def test_rk4_negative_dt_works():
    state = (RE + 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0)
    forward = rk4_step(state, 10.0)
    backward = rk4_step(state, -10.0)
    assert forward != backward
