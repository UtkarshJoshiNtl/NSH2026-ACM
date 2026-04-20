"""
High-level wrapped API for the ACM physics engine.
"""

import math
from .loader import physics as _physics
from .constants import DRY_MASS, ISP, G0, INITIAL_FUEL
from .fallback import rk4_py, rk4_py_drag


def propagate(state: list, dt_seconds: float) -> list:
    if _physics:
        result = _physics.Propagator().propagate(state, dt_seconds)
        return list(result)
    return list(rk4_py(tuple(state), dt_seconds))


def propagate_with_drag(
    state: list,
    dt_seconds: float,
    area: float = 0.1,
    mass: float = 100.0,
    cd: float = 2.2,
) -> list:
    """Propagate state with atmospheric drag for LEO objects.

    Args:
        state: Position and velocity [x, y, z, vx, vy, vz]
        dt_seconds: Time step in seconds
        area: Cross-sectional area in m²
        mass: Object mass in kg
        cd: Drag coefficient

    Returns:
        Updated state list
    """
    if _physics:
        # C++ engine doesn't support drag parameters yet, use Python fallback
        result = rk4_py_drag(tuple(state), dt_seconds, area, mass, cd)
        return list(result)
    return list(rk4_py_drag(tuple(state), dt_seconds, area, mass, cd))


def propagate_steps(state: list, total_seconds: float, step_size: float = 10.0) -> list:
    if _physics:
        result = _physics.Propagator().propagate_steps(state, total_seconds, step_size)
        return list(result)
    # Python fallback implementation
    states = []
    s = tuple(state)
    remaining = total_seconds
    while remaining > 0:
        dt = min(step_size, remaining)
        s = rk4_py(s, dt)
        states.append(list(s))
        remaining -= dt
    return states


def compute_fuel_used(delta_v: list, fuel_kg: float = INITIAL_FUEL) -> float:
    """Compute fuel used for a given delta-v."""
    if _physics:
        tracker = _physics.FuelTracker(fuel_kg, DRY_MASS)
        return tracker.calculate_fuel_cost(delta_v)
    # Python fallback
    dv_mag = math.sqrt(sum(d * d for d in delta_v))
    mass = DRY_MASS + fuel_kg
    return mass * (1.0 - math.exp(-dv_mag / (ISP * G0)))


def detect_conjunctions(states: list, threshold_km: float = 1.0) -> list:
    """Detect conjunctions between objects."""
    if _physics:
        detector = _physics.ConjunctionDetector()
        return detector.detect(states, threshold_km)
    # Python fallback - simple distance check
    conjunctions = []
    for i in range(len(states)):
        for j in range(i + 1, len(states)):
            r1 = states[i][:3]
            r2 = states[j][:3]
            dist = math.sqrt(sum((r1[k] - r2[k]) ** 2 for k in range(3)))
            if dist < threshold_km:
                conjunctions.append([i, j, dist])
    return conjunctions


def calculate_maneuver(sat_state: list, warning: dict) -> dict:
    """Calculate evasion and recovery maneuvers."""
    if _physics:
        calc = _physics.ManeuverCalculator()
        plan = calc.calculate(sat_state, warning)
        return {
            "evasion_dv": list(plan.evasion_dv_eci),
            "recovery_dv": list(plan.recovery_dv_eci),
            "fuel_cost_kg": plan.fuel_cost_kg,
            "burn_timing_offset_s": plan.burn_timing_offset_s,
        }
    # Python fallback - simple perpendicular evasion
    rv = warning.get("relative_velocity", [0, 0, 0])
    rv_mag = math.sqrt(sum(d * d for d in rv))
    if rv_mag < 1e-9:
        return {
            "evasion_dv": [0, 0, 0],
            "recovery_dv": [0, 0, 0],
            "fuel_cost_kg": 0,
            "burn_timing_offset_s": 0,
        }

    # Simple evasion: perpendicular to relative velocity
    r = sat_state[:3]
    cross = [
        rv[1] * r[2] - rv[2] * r[1],
        rv[2] * r[0] - rv[0] * r[2],
        rv[0] * r[1] - rv[1] * r[0],
    ]
    cross_mag = math.sqrt(sum(d * d for d in cross))
    if cross_mag < 1e-9:
        cross = r
        cross_mag = math.sqrt(sum(d * d for d in cross))

    evasion_mag = 0.015  # MAX_DV
    evasion_dv = [(d / cross_mag) * evasion_mag for d in cross]
    recovery_dv = [-d for d in evasion_dv]

    fuel_cost = compute_fuel_used(evasion_dv) + compute_fuel_used(recovery_dv)

    return {
        "evasion_dv": evasion_dv,
        "recovery_dv": recovery_dv,
        "fuel_cost_kg": fuel_cost,
        "burn_timing_offset_s": 600.0,  # COOLDOWN_S
    }
