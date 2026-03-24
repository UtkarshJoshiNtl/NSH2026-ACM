"""
High-level wrapped API for the ACM physics engine.
"""

import math
from .loader import physics as _physics
from .constants import DRY_MASS, ISP, G0
from .fallback import rk4_py

def propagate(state: list, dt_seconds: float) -> list:
    if _physics:
        result = _physics.Propagator().propagate(state, dt_seconds)
        return list(result)
    return list(rk4_py(tuple(state), dt_seconds))

def propagate_steps(state: list, total_seconds: float, step_size: float = 10.0) -> list:
    if _physics:
        result = _physics.Propagator().propagate_steps(state, total_seconds, step_size)
        return list(result)
    s = tuple(state)
    remaining = total_seconds
    while remaining > 0:
        dt = min(step_size, remaining)
        s = rk4_py(s, dt)
        remaining -= dt
    return list(s)

def compute_fuel_used(m_current_kg: float, dv_kms: float) -> float:
    if dv_kms <= 0: return 0.0
    if _physics:
        fuel_mass = max(0.0, m_current_kg - DRY_MASS)
        if fuel_mass == 0.0: return 0.0
        ft = _physics.FuelTracker(fuel_mass, DRY_MASS)
        return ft.calculate_fuel_cost(dv_kms)
    ve = ISP * G0
    return m_current_kg * (1.0 - math.exp(-dv_kms / ve))

def detect_conjunctions(sat_states: list, debris_states: list,
                          lookahead_s: float = 86400.0,
                          step_s: float = 60.0) -> list:
    if not _physics: return []
    warnings = _physics.ConjunctionDetector().detect(sat_states, debris_states, lookahead_s, step_s)
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
    if not _physics: return None
    w = _physics.ConjunctionWarning()
    w.sat_id = warning["sat_id"]
    w.debris_id = warning["debris_id"]
    w.current_distance = warning["distance_km"]
    w.time_to_closest_approach = warning["tca_s"]
    w.severity = warning["severity"]
    w.relative_velocity = warning.get("rel_vel_kms", 0.0)

    plan = _physics.ManeuverCalculator().calculate(sat_state, w)
    return {
        "evasion_dv_eci":    list(plan.evasion_dv_eci),
        "recovery_dv_eci":   list(plan.recovery_dv_eci),
        "fuel_cost_kg":      plan.fuel_cost_kg,
        "burn_offset_s":     plan.burn_timing_offset_s,
    }
