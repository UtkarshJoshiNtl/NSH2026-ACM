"""
engine/physics/accelerator.py — Tiered Backend Bridge
======================================================
Priority: CUDA GPU → C++ CPU → NumPy Batch → Pure Python

Public API is backend-agnostic; callers use the same function signatures
regardless of which tier is active.
"""

import sys
import os
import logging
from typing import List, Optional
import numpy as np

from ..constants import DRY_MASS, INITIAL_FUEL

# Python fallbacks
from .propagator import rk4_py, rk4_py_drag, propagate_batch_numpy
from .fuel import FuelTracker as PyFuelTracker
from .conjunction import ConjunctionDetector as PyConjunctionDetector
from .maneuver import ManeuverCalculator as PyManeuverCalculator

logger = logging.getLogger(__name__)


def _load_physics():
    """Attempt to load the C++ / CUDA physics_engine pybind11 module."""
    _BUILD_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "cpp", "build"))
    _ROOT_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".."))
    for p in [_BUILD_DIR, _ROOT_DIR]:
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import physics_engine as _pe
        return _pe
    except ImportError:
        logger.warning("C++ physics_engine not found — using Python fallback.")
        return None


_physics = _load_physics()

# Detect available tiers at import time
_HAS_CPP  = _physics is not None
_HAS_CUDA = _HAS_CPP and getattr(_physics, "cuda_available", lambda: False)()
_HAS_BATCH_CPP = _HAS_CPP and hasattr(_physics.Propagator, "batch_propagate_steps")

if _HAS_CUDA:
    logger.info("Backend: CUDA GPU acceleration active")
elif _HAS_CPP:
    logger.info("Backend: C++ CPU acceleration active")
else:
    logger.info("Backend: Pure Python / NumPy")


def backend_info() -> dict:
    """Return a dict describing which backends are available."""
    return {
        "cuda":       _HAS_CUDA,
        "cpp":        _HAS_CPP,
        "numpy_batch": True,
        "python":     True,
    }


# ── Single-step propagation ───────────────────────────────────────────────────

def propagate(state: list, dt_seconds: float) -> list:
    """Propagate a single satellite one RK4 step."""
    if _HAS_CPP:
        return list(_physics.Propagator().propagate(state, dt_seconds))
    return list(rk4_py(tuple(state), dt_seconds))


def propagate_with_drag(state: list, dt_seconds: float,
                         area: float = 10.0, mass: float = 1000.0,
                         cd: float = 2.2) -> list:
    """Propagate a single satellite one RK4 step with drag."""
    if _HAS_CPP:
        return list(_physics.Propagator().propagate_with_drag(
            state, dt_seconds, area, mass, cd))
    return list(rk4_py_drag(tuple(state), dt_seconds, area, mass, cd))


def propagate_steps(state: list, total_seconds: float,
                     step_size: float = 10.0) -> list:
    """Propagate a single satellite for a total time window, returning final state."""
    if _HAS_CPP:
        return list(_physics.Propagator().propagate_steps(
            state, total_seconds, step_size))
    states = [list(state)]
    curr = tuple(state)
    rem = total_seconds
    while rem > 0:
        dt = min(step_size, rem)
        curr = rk4_py(curr, dt)
        rem -= dt
    return list(curr)


# ── Batch propagation (N satellites) ─────────────────────────────────────────

def propagate_batch(states: list, dt_seconds: float, steps: int,
                     area: float = 0.0, mass: float = 1.0,
                     cd: float = 2.2, with_drag: bool = False) -> list:
    """
    Propagate N satellites for `steps` RK4 steps.

    Backend priority: CUDA → C++ batch → NumPy batch → Python loop.

    Parameters
    ----------
    states      : list of N 6-element state lists [km, km/s]
    dt_seconds  : step size in seconds
    steps       : number of RK4 steps

    Returns
    -------
    List of N final state lists
    """
    # ── CUDA GPU ──────────────────────────────────────────────────────────────
    if _HAS_CUDA:
        arr = np.array(states, dtype=np.float64).ravel()
        n = len(states)
        if with_drag:
            _physics.cuda_propagate_batch_drag(arr, n, dt_seconds, steps,
                                                area, mass, cd)
        else:
            _physics.cuda_propagate_batch(arr, n, dt_seconds, steps)
        return arr.reshape(n, 6).tolist()

    # ── C++ batch (GIL-released, optionally OpenMP) ───────────────────────────
    if _HAS_BATCH_CPP:
        prop = _physics.Propagator()
        if with_drag:
            return [list(s) for s in prop.batch_propagate_steps_drag(
                states, dt_seconds, steps, area, mass, cd)]
        return [list(s) for s in prop.batch_propagate_steps(
            states, dt_seconds, steps)]

    # ── NumPy vectorized fallback ─────────────────────────────────────────────
    return propagate_batch_numpy(states, dt_seconds, steps,
                                  area, mass, cd, with_drag)


# ── Conjunction detection ─────────────────────────────────────────────────────

def detect_conjunctions(sat_states: list, debris_states: list,
                         lookahead: float = 86400.0,
                         step_s: float = 60.0) -> list:
    """
    All-pairs conjunction screening.
    Backend priority: CUDA → C++ → Python.
    """
    if _HAS_CUDA and hasattr(_physics, "cuda_detect_conjunctions"):
        return _physics.cuda_detect_conjunctions(
            sat_states, debris_states, lookahead, step_s)

    if _HAS_CPP:
        return _physics.ConjunctionDetector().detect(
            sat_states, debris_states, lookahead, step_s)

    detector = PyConjunctionDetector()
    return detector.detect(sat_states, debris_states,
                            lookahead_s=lookahead, step_s=step_s)


# ── Fuel & maneuver ───────────────────────────────────────────────────────────

def compute_fuel_used(delta_v: list, fuel_kg: float = INITIAL_FUEL) -> float:
    if _HAS_CPP:
        return _physics.FuelTracker(fuel_kg, DRY_MASS).calculate_fuel_cost(delta_v)
    return PyFuelTracker(fuel_kg).calculate_fuel_cost(delta_v)


def calculate_maneuver(sat_state: list, warning) -> dict:
    if _HAS_CPP:
        p = _physics.ManeuverCalculator().calculate(sat_state, warning)
        return {
            "evasion_dv":   list(p.evasion_dv_eci),
            "recovery_dv":  list(p.recovery_dv_eci),
            "fuel_cost_kg": p.fuel_cost_kg,
            "burn_timing_offset_s": p.burn_timing_offset_s,
        }
    p = PyManeuverCalculator().calculate(sat_state, warning)
    return {
        "evasion_dv":   p.evasion_dv_eci,
        "recovery_dv":  p.recovery_dv_eci,
        "fuel_cost_kg": p.fuel_cost_kg,
        "burn_timing_offset_s": p.burn_timing_offset_s,
    }
