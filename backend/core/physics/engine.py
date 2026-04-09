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
