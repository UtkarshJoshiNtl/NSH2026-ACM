"""
engine/physics/accelerator.py — C++ Engine Bridge
==================================================
Handles pybind11 loading and provides high-level fallbacks.
"""

import sys
import os
import logging
from typing import List, Optional

# Constants
from ..constants import DRY_MASS, INITIAL_FUEL

# Fallbacks
from .propagator import rk4_py, rk4_py_drag
from .fuel import FuelTracker as PyFuelTracker
from .conjunction import ConjunctionDetector as PyConjunctionDetector
from .maneuver import ManeuverCalculator as PyManeuverCalculator

logger = logging.getLogger(__name__)

def _load_physics():
    """Attempt to load the C++ accelerator."""
    # Find build dir relative to this file
    # engine/physics/accelerator.py -> ../../cpp/build
    _BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cpp", "build"))
    _ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    for _path in [_BUILD_DIR, _ROOT_DIR]:
        if _path not in sys.path:
            sys.path.insert(0, _path)

    try:
        import physics_engine as _physics
        return _physics
    except ImportError:
        logger.warning("C++ physics_engine not found; using pure Python fallback.")
        return None

_physics = _load_physics()

# ── API ──────────────────────────────────────────────────────────────────────

def propagate(state: list, dt_seconds: float) -> list:
    if _physics:
        return list(_physics.Propagator().propagate(state, dt_seconds))
    return list(rk4_py(tuple(state), dt_seconds))

def propagate_with_drag(
    state: list,
    dt_seconds: float,
    area: float = 10.0,
    mass: float = 1000.0,
    cd: float = 2.2,
) -> list:
    if _physics:
        return list(_physics.Propagator().propagate_with_drag(state, dt_seconds, area, mass, cd))
    return list(rk4_py_drag(tuple(state), dt_seconds, area, mass, cd))

def propagate_steps(state: list, total_seconds: float, step_size: float = 10.0) -> list:
    if _physics:
        return list(_physics.Propagator().propagate_steps(state, total_seconds, step_size))
    
    states = []
    curr = tuple(state)
    rem = total_seconds
    while rem > 0:
        dt = min(step_size, rem)
        curr = rk4_py(curr, dt)
        states.append(list(curr))
        rem -= dt
    return states

def compute_fuel_used(delta_v: list, fuel_kg: float = INITIAL_FUEL) -> float:
    if _physics:
        return _physics.FuelTracker(fuel_kg, DRY_MASS).calculate_fuel_cost(delta_v)
    return PyFuelTracker(fuel_kg).calculate_fuel_cost(delta_v)

def detect_conjunctions(sat_states: list, debris_states: list, lookahead: float = 86400.0) -> list:
    if _physics:
        detector = _physics.ConjunctionDetector()
        return detector.detect(sat_states, debris_states, lookahead)
    
    detector = PyConjunctionDetector()
    results = detector.detect(sat_states, debris_states, lookahead)
    # Convert to list of dicts for uniformity if needed, but here let's keep objects
    return results

def calculate_maneuver(sat_state: list, warning) -> dict:
    if _physics:
        p = _physics.ManeuverCalculator().calculate(sat_state, warning)
        return {
            "evasion_dv": list(p.evasion_dv_eci),
            "recovery_dv": list(p.recovery_dv_eci),
            "fuel_cost_kg": p.fuel_cost_kg,
            "burn_timing_offset_s": p.burn_timing_offset_s
        }
    
    p = PyManeuverCalculator().calculate(sat_state, warning)
    return {
        "evasion_dv": p.evasion_dv_eci,
        "recovery_dv": p.recovery_dv_eci,
        "fuel_cost_kg": p.fuel_cost_kg,
        "burn_timing_offset_s": p.burn_timing_offset_s
    }
