"""
High-level wrapped API for the ACM physics engine.
NSH 2026 compliant: J2 perturbation only.
"""

import math
import numpy as np
from scipy.spatial import cKDTree
from .loader import physics as _physics
from .constants import DRY_MASS, ISP, G0, INITIAL_FUEL, RE
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
    """
    Detect conjunctions between objects using KD-Tree for O(N log N) complexity.
    NSH 2026 compliant - migrated from AutoCM.
    """
    if _physics:
        detector = _physics.ConjunctionDetector()
        return detector.detect(states, threshold_km)
    
    # Python fallback with KD-Tree (from AutoCM)
    if len(states) < 2:
        return []
    
    # Extract positions
    positions = np.array([s[:3] for s in states])
    
    # Build KD-Tree
    tree = cKDTree(positions)
    
    # Query for pairs within threshold
    pairs = tree.query_pairs(threshold_km)
    
    # Convert to conjunction format
    conjunctions = []
    for i, j in pairs:
        r1 = states[i][:3]
        r2 = states[j][:3]
        dist = np.linalg.norm(r1 - r2)
        conjunctions.append([i, j, float(dist)])
    
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
