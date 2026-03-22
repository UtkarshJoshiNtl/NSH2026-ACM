"""
backend/core/maneuver_planner.py — ACM Maneuver Planner
=========================================================
Python-layer maneuver planning: validates constraints (fuel, cooldown,
LOS) and optionally calls the C++ ManeuverCalculator for optimal burns.

All Δv vectors are in ECI frame (km/s).
"""

import math
import logging
from typing import Optional

from backend.core import physics_bridge as phys
from backend.core.ground_station import check_los
from backend.core.state_manager import ObjectState, ScheduledBurn, state_mgr

logger = logging.getLogger(__name__)

COOLDOWN_S   = 600.0   # s between burns on same sat
MAX_DV_KMS   = 0.015   # km/s (15 m/s)
EOL_FUEL_PCT = 0.05    # 5% of initial fuel


# ── Vector helpers ────────────────────────────────────────────────────────────

def _vec_mag(v: list) -> float:
    return math.sqrt(sum(x*x for x in v))


def _vec_scale(v: list, s: float) -> list:
    return [x * s for x in v]


def _cross(a: list, b: list) -> list:
    return [
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    ]


def _normalize(v: list) -> list:
    mag = _vec_mag(v)
    if mag < 1e-12:
        return [0.0, 0.0, 0.0]
    return [x / mag for x in v]


# ── RTN frame construction ────────────────────────────────────────────────────

def _build_rtn(r: list, v: list) -> tuple[list, list, list]:
    """Return (r_hat, t_hat, n_hat) unit vectors for RTN frame."""
    r_hat = _normalize(r)
    n_hat = _normalize(_cross(r, v))
    t_hat = _cross(n_hat, r_hat)
    return r_hat, t_hat, n_hat


def _rtn_to_eci(dv_rtn: list, r_hat: list, t_hat: list, n_hat: list) -> list:
    """Convert a Δv in RTN to ECI frame."""
    return [
        r_hat[i]*dv_rtn[0] + t_hat[i]*dv_rtn[1] + n_hat[i]*dv_rtn[2]
        for i in range(3)
    ]


# ── Burn calculation ──────────────────────────────────────────────────────────

def compute_evasion_burn(sat: ObjectState, warning: dict) -> list:
    """
    Try C++ calculator first; fall back to Python RTN prograde burn.
    Returns Δv in ECI km/s (capped at MAX_DV_KMS).
    """
    result = phys.calculate_maneuver(sat.r + sat.v, warning)
    if result:
        dv = result["evasion_dv_eci"]
        mag = _vec_mag(dv)
        if mag > MAX_DV_KMS:
            dv = _vec_scale(_normalize(dv), MAX_DV_KMS)
        return dv

    # Python fallback: pure prograde (transverse) burn
    r_hat, t_hat, n_hat = _build_rtn(sat.r, sat.v)
    dv_mag = min(MAX_DV_KMS, 0.005)   # 5 m/s default evasion
    return _rtn_to_eci([0.0, dv_mag, 0.0], r_hat, t_hat, n_hat)


def compute_recovery_burn(sat: ObjectState) -> list:
    """
    Retrograde phasing burn to return towards nominal slot.
    Returns Δv in ECI km/s.
    """
    if not sat.nominal_slot:
        return [0.0, 0.0, 0.0]

    r_hat, t_hat, n_hat = _build_rtn(sat.r, sat.v)
    drift   = [sat.nominal_slot[i] - sat.r[i] for i in range(3)]
    drift_m = _vec_mag(drift)

    # Retrograde proportional to drift, capped at max
    dv_mag = min(drift_m * 0.001, MAX_DV_KMS)
    return _rtn_to_eci([0.0, -dv_mag, 0.0], r_hat, t_hat, n_hat)


def estimate_graveyard_burn(sat: ObjectState) -> list:
    """
    Raise perigee to >2000 km (simplified: single prograde impulse).
    Only invoked when sat.m_fuel < EOL threshold.
    """
    r_hat, t_hat, n_hat = _build_rtn(sat.r, sat.v)
    return _rtn_to_eci([0.0, MAX_DV_KMS, 0.0], r_hat, t_hat, n_hat)


# ── Validation helpers ────────────────────────────────────────────────────────

def validate_burn(sat: ObjectState, dv_kms: float, burn_time: float) -> dict:
    """
    Returns {"ok": bool, "reason": str | None}.
    Checks: cooldown, max Δv, sufficient fuel, LOS.
    """
    if burn_time - sat.last_burn_time < COOLDOWN_S:
        return {"ok": False, "reason": f"Thruster cooldown: {COOLDOWN_S:.0f}s required between burns"}

    if dv_kms > MAX_DV_KMS + 1e-9:
        return {"ok": False, "reason": f"|Δv| {dv_kms*1000:.2f} m/s exceeds 15 m/s limit"}

    fuel_needed = phys.compute_fuel_used(sat.m_fuel + sat.dry_mass, dv_kms)
    if fuel_needed > sat.m_fuel:
        return {"ok": False, "reason": f"Insufficient fuel: need {fuel_needed:.2f} kg, have {sat.m_fuel:.2f} kg"}

    if not check_los(sat.r):
        return {"ok": False, "reason": "No ground station LOS at burn time"}

    return {"ok": True, "reason": None}


def apply_burn(sat: ObjectState, dv_vec: list, burn_time: float) -> float:
    """
    Apply a burn to a satellite, updating its velocity, fuel, and last_burn_time.
    Returns the fuel consumed (kg).
    """
    dv_mag = _vec_mag(dv_vec)
    fuel_used = phys.compute_fuel_used(sat.m_fuel + sat.dry_mass, dv_mag)

    sat.v = [sat.v[i] + dv_vec[i] for i in range(3)]
    sat.m_fuel = max(0.0, sat.m_fuel - fuel_used)
    sat.last_burn_time = burn_time

    # Check EOL
    if sat.m_fuel / 50.0 < EOL_FUEL_PCT:
        sat.status = "EOL"
    elif sat.status == "NOMINAL":
        pass
    return fuel_used
