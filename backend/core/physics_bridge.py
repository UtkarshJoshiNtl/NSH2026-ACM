"""
backend/core/physics_bridge.py — ACM Physics Bridge
=====================================================
Loads the compiled pybind11 physics_engine module and provides a clean
Python API over it. Falls back gracefully to a pure-Python stub if the
.so is not yet built (useful during development).
"""

import sys
import os
import math
import logging

logger = logging.getLogger(__name__)

# ── Try to import the compiled C++ module ─────────────────────────────────────
_BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "cpp", "build")
_BUILD_DIR = os.path.abspath(_BUILD_DIR)

# Also check project root (Docker copies .so there)
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_physics = None
for _path in [_BUILD_DIR, _ROOT_DIR]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    import physics_engine as _physics  # type: ignore
    logger.info("physics_engine C++ module loaded successfully")
except ImportError as exc:
    logger.warning("physics_engine C++ module not found (%s); using Python fallback", exc)


# ── Constants (mirror C++ values) ────────────────────────────────────────────
MU   = 398600.4418   # km³/s²
RE   = 6378.137      # km
J2   = 1.08263e-3
ISP  = 300.0         # s
G0   = 0.00980665    # km/s²
DRY_MASS     = 500.0  # kg
INITIAL_FUEL = 50.0   # kg
MAX_DV       = 0.015  # km/s (15 m/s)
COOLDOWN_S   = 600.0  # seconds


# ── Python fallback propagator (RK4 + J2) ────────────────────────────────────
def _accel_py(r):
    x, y, z = r
    r2 = x*x + y*y + z*z
    rm = math.sqrt(r2)
    r3 = r2 * rm
    r5 = r3 * r2
    grav = -MU / r3
    j2f  = 1.5 * J2 * MU * RE * RE / r5
    z2r2 = z * z / r2
    return (
        grav*x + j2f*x*(5*z2r2 - 1),
        grav*y + j2f*y*(5*z2r2 - 1),
        grav*z + j2f*z*(5*z2r2 - 3),
    )

def _rk4_py(state, dt):
    def deriv(s):
        a = _accel_py(s[:3])
        return (s[3], s[4], s[5], a[0], a[1], a[2])
    k1 = deriv(state)
    s2 = tuple(state[i] + 0.5*dt*k1[i] for i in range(6))
    k2 = deriv(s2)
    s3 = tuple(state[i] + 0.5*dt*k2[i] for i in range(6))
    k3 = deriv(s3)
    s4 = tuple(state[i] + dt*k3[i] for i in range(6))
    k4 = deriv(s4)
    return tuple(state[i] + (dt/6)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]) for i in range(6))


# ── Public API ────────────────────────────────────────────────────────────────

def propagate(state: list, dt_seconds: float) -> list:
    """
    Propagate a 6-element state vector [x,y,z,vx,vy,vz] (km, km/s) by dt_seconds.
    Uses C++ RK4+J2 if available, otherwise pure-Python fallback.
    """
    if _physics:
        result = _physics.Propagator().propagate(state, dt_seconds)
        return list(result)
    return list(_rk4_py(tuple(state), dt_seconds))


def propagate_steps(state: list, total_seconds: float, step_size: float = 10.0) -> list:
    """Propagate in multiple RK4 steps for numerical stability at large dt."""
    if _physics:
        result = _physics.Propagator().propagate_steps(state, total_seconds, step_size)
        return list(result)
    s = tuple(state)
    remaining = total_seconds
    while remaining > 0:
        dt = min(step_size, remaining)
        s = _rk4_py(s, dt)
        remaining -= dt
    return list(s)


def compute_fuel_used(m_current_kg: float, dv_kms: float) -> float:
    """
    Tsiolkovsky: propellant mass consumed for delta-v in km/s.
    m_current_kg is the total wet mass (dry + remaining fuel).
    Uses C++ FuelTracker if available.
    """
    if dv_kms <= 0:
        return 0.0
    if _physics:
        fuel_mass = max(0.0, m_current_kg - DRY_MASS)   # guard: never negative
        if fuel_mass == 0.0:
            return 0.0
        ft = _physics.FuelTracker(fuel_mass, DRY_MASS)
        return ft.calculate_fuel_cost(dv_kms)
    # Pure-Python fallback (Tsiolkovsky)
    ve = ISP * G0   # exhaust velocity in km/s
    return m_current_kg * (1.0 - math.exp(-dv_kms / ve))


def detect_conjunctions(sat_states: list, debris_states: list,
                         lookahead_s: float = 86400.0,
                         step_s: float = 60.0) -> list:
    """
    Run KD-Tree conjunction detection.
    Returns list of dicts with sat_id, debris_id, distance, tca, severity, rel_vel.
    """
    if not _physics:
        return []

    warnings = _physics.ConjunctionDetector().detect(
        sat_states, debris_states, lookahead_s, step_s
    )
    return [
        {
            "sat_id":     w.sat_id,
            "debris_id":  w.debris_id,
            "distance_km": w.current_distance,
            "tca_s":      w.time_to_closest_approach,
            "severity":   w.severity,
            "rel_vel_kms": w.relative_velocity,
        }
        for w in warnings
    ]


def calculate_maneuver(sat_state: list, warning: dict) -> dict | None:
    """
    Compute evasion + recovery burns using C++ ManeuverCalculator.
    Returns dict with evasion_dv, recovery_dv, fuel_cost_kg, burn_offset_s.
    """
    if not _physics:
        return None

    # Reconstruct a ConjunctionWarning object
    w = _physics.ConjunctionWarning()
    w.sat_id                   = warning["sat_id"]
    w.debris_id                = warning["debris_id"]
    w.current_distance         = warning["distance_km"]
    w.time_to_closest_approach = warning["tca_s"]
    w.severity                 = warning["severity"]
    w.relative_velocity        = warning.get("rel_vel_kms", 0.0)

    plan = _physics.ManeuverCalculator().calculate(sat_state, w)
    return {
        "evasion_dv_eci":    list(plan.evasion_dv_eci),
        "recovery_dv_eci":   list(plan.recovery_dv_eci),
        "fuel_cost_kg":      plan.fuel_cost_kg,
        "burn_offset_s":     plan.burn_timing_offset_s,
    }


def _vec_mag(v: list) -> float:
    """Utility to calculate magnitude of a 3D vector."""
    return math.sqrt(sum(x*x for x in v))
