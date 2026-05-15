"""
engine/core/accelerator.py — Tiered Backend Bridge
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
from .propagator import rk4_step, propagate_batch_numpy
from .fuel import FuelTracker as PyFuelTracker
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
    """Return a dict describing which backends are available and active."""
    active = "python"
    desc = "Pure Python RK4 / SciPy"
    if _HAS_CUDA:
        active = "cuda"
        desc = "CUDA GPU acceleration (NVIDIA)"
    elif _HAS_BATCH_CPP:
        active = "cpp"
        desc = "C++ multi-threaded (OpenMP)"
    elif _HAS_CPP:
        active = "cpp"
        desc = "C++ single-threaded"

    return {
        "active":     active,
        "backend":    active, # alias for API compatibility
        "cuda":       _HAS_CUDA,
        "cpp":        _HAS_CPP,
        "numpy_batch": True,
        "python":     True,
        "description": desc,
    }


# ── Single-step propagation ───────────────────────────────────────────────────

def propagate(state: list, dt_seconds: float, mjd0: float = 0.0) -> list:
    """Propagate a single satellite one RK4 step."""
    if _HAS_CPP:
        try:
            return list(_physics.Propagator().propagate(state, dt_seconds, mjd0))
        except Exception as e:
            logger.warning(f"C++ propagate failed: {e}. Falling back to Python.")
    return list(rk4_step(tuple(state), dt_seconds, mjd0))


def propagate_with_drag(state: list, dt_seconds: float,
                         area: float = 10.0, mass: float = 1000.0,
                         cd: float = 2.2, cr: float = 1.5, mjd0: float = 0.0) -> list:
    """Propagate a single satellite one RK4 step with drag/SRP."""
    if _HAS_CPP:
        try:
            return list(_physics.Propagator().propagate_with_drag(
                state, dt_seconds, area, mass, cd, cr, mjd0))
        except Exception as e:
            logger.warning(f"C++ propagate_with_drag failed: {e}. Falling back to Python.")
    return list(rk4_step(tuple(state), dt_seconds, mjd0, 0, area, mass, cd, cr))


def propagate_steps(state: list, total_seconds: float,
                     step_size: float = 10.0,
                     area: float = 0.0, mass: float = 1.0, cd: float = 2.2, cr: float = 1.5,
                     with_drag: bool = False, mjd0: float = 0.0) -> list:
    """Propagate a single satellite for a total time window, returning final state."""
    if _HAS_CPP:
        try:
            return list(_physics.Propagator().propagate_steps(
                state, total_seconds, step_size, area, mass, cd, cr, with_drag, mjd0))
        except Exception as e:
            logger.warning(f"C++ propagate_steps failed: {e}. Falling back to Python.")
    curr = tuple(state)
    rem = total_seconds
    steps_taken = 0
    while rem > 0:
        dt = min(step_size, rem)
        curr = rk4_step(curr, dt, mjd0, steps_taken, area if with_drag else 0.0, mass, cd, cr)
        rem -= dt
        steps_taken += 1
    return list(curr)


# ── Batch propagation (N satellites) ─────────────────────────────────────────

def propagate_batch(states: list, dt_seconds: float, steps: int,
                     area: float = 0.0, mass: float = 1.0,
                     cd: float = 2.2, cr: float = 1.5, with_drag: bool = False,
                     mjd0: float = 0.0) -> list:
    """
    Propagate N satellites for `steps` RK4 steps.
    """
    # Convert input list to NumPy array once
    arr = np.array(states, dtype=np.float64)

    # ── CUDA GPU ──────────────────────────────────────────────────────────────
    if _HAS_CUDA:
        try:
            if with_drag:
                res = _physics.cuda_propagate_batch_drag(arr, dt_seconds, steps, area, mass, cd, cr, mjd0)
            else:
                res = _physics.cuda_propagate_batch(arr, dt_seconds, steps, mjd0)
            return res.tolist()
        except Exception as e:
            logger.warning(f"CUDA propagate_batch failed: {e}. Falling back to C++.")

    # ── C++ batch (GIL-released, optionally OpenMP) ───────────────────────────
    if _HAS_BATCH_CPP:
        try:
            prop = _physics.Propagator()
            if with_drag:
                res = prop.batch_propagate_steps_drag(arr, dt_seconds, steps, area, mass, cd, cr, mjd0)
            else:
                res = prop.batch_propagate_steps(arr, dt_seconds, steps, mjd0)
            return res.tolist()
        except Exception as e:
            logger.warning(f"C++ batch_propagate_steps failed: {e}. Falling back to NumPy.")

    # ── NumPy vectorized fallback ─────────────────────────────────────────────
    return propagate_batch_numpy(states, dt_seconds, steps,
                                  area, mass, cd, cr, with_drag, mjd0)


def propagate_batch_full_history(states: list, dt_seconds: float, steps: int,
                                 area: float = 0.0, mass: float = 1.0,
                                 cd: float = 2.2, cr: float = 1.5, with_drag: bool = False,
                                 mjd0: float = 0.0) -> np.ndarray:
    """
    Propagate N satellites for `steps` steps and return the ENTIRE history.
    Returns: NumPy array of shape (steps + 1, N, 6)
    """
    arr = np.array(states, dtype=np.float64)
    
    if _HAS_CUDA:
        try:
            return _physics.cuda_propagate_full_history(arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0)
        except Exception as e:
            logger.warning(f"CUDA propagate_full_history failed: {e}. Falling back to C++.")
    
    if _HAS_BATCH_CPP:
        try:
            return _physics.Propagator().batch_propagate_full_history(arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0)
        except Exception as e:
            logger.warning(f"C++ batch_propagate_full_history failed: {e}. Falling back to NumPy.")
        
    # Fallback (slow)
    n = len(states)
    history = np.zeros((steps + 1, n, 6))
    history[0] = arr
    curr = arr
    for s in range(1, steps + 1):
        step_mjd0 = mjd0 + ((s-1) * dt_seconds) / 86400.0 if mjd0 > 0 else 0.0
        curr = np.array(propagate_batch_numpy(curr.tolist(), dt_seconds, 1, area, mass, cd, cr, with_drag, step_mjd0))
        history[s] = curr
    return history


# ── Conjunction detection ─────────────────────────────────────────────────────

def detect_conjunctions(sat_states: list, debris_states: list,
                         lookahead: float = 86400.0,
                         step_s: float = 60.0,
                         mjd0: float = 0.0) -> list:
    """
    All-pairs conjunction screening.
    """
    if _HAS_CUDA and hasattr(_physics, "cuda_detect_conjunctions"):
        try:
            s_arr = np.array(sat_states, dtype=np.float64)
            d_arr = np.array(debris_states, dtype=np.float64)
            return _physics.cuda_detect_conjunctions(s_arr, d_arr, lookahead, step_s, mjd0)
        except Exception as e:
            logger.warning(f"CUDA detect_conjunctions failed: {e}. Falling back to C++.")

    if _HAS_CPP:
        try:
            s_arr = np.array(sat_states, dtype=np.float64)
            d_arr = np.array(debris_states, dtype=np.float64)
            return _physics.ConjunctionDetector().detect(s_arr, d_arr, lookahead, step_s, mjd0=mjd0)
        except Exception as e:
            logger.warning(f"C++ detect_conjunctions failed: {e}. Falling back to Python.")

    from .conjunction import ConjunctionDetector as PyConjunctionDetector
    detector = PyConjunctionDetector()
    return detector.detect(sat_states, debris_states,
                            lookahead_s=lookahead, step_s=step_s, mjd0=mjd0)


# ── Fuel & maneuver ───────────────────────────────────────────────────────────

def compute_fuel_used(delta_v: list, fuel_kg: float = INITIAL_FUEL) -> float:
    if _HAS_CPP:
        try:
            return _physics.FuelTracker(fuel_kg, DRY_MASS).calculate_fuel_cost(delta_v)
        except Exception as e:
            logger.warning(f"C++ compute_fuel_used failed: {e}. Falling back to Python.")
    return PyFuelTracker(fuel_kg).calculate_fuel_cost(delta_v)


def calculate_maneuver(sat_state: list, warning) -> dict:
    if _HAS_CPP:
        try:
            p = _physics.ManeuverCalculator().calculate(sat_state, warning)
            return {
                "evasion_dv":   list(p.evasion_dv_eci),
                "recovery_dv":  list(p.recovery_dv_eci),
                "fuel_cost_kg": p.fuel_cost_kg,
                "burn_timing_offset_s": p.burn_timing_offset_s,
            }
        except Exception as e:
            logger.warning(f"C++ calculate_maneuver failed: {e}. Falling back to Python.")
    p = PyManeuverCalculator().calculate(sat_state, warning)
    return {
        "evasion_dv":   p.evasion_dv_eci,
        "recovery_dv":  p.recovery_dv_eci,
        "fuel_cost_kg": p.fuel_cost_kg,
        "burn_timing_offset_s": p.burn_timing_offset_s,
    }
