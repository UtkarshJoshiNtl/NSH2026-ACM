"""Core physics and analysis helpers.

The accelerator module probes native backends at import time, so importing
engine.core will detect Python / C++ / CUDA availability on import.
"""

from .propagator import rk4_step, rk4_batch, propagate_batch_numpy
from .conjunction import ConjunctionDetector, ConjunctionWarning
from .accelerator import (
    propagate,
    propagate_with_drag,
    propagate_steps,
    propagate_batch,
    propagate_batch_full_history,
    detect_conjunctions,
    backend_info,
)
from .ephemeris import sun_position_eci, moon_position_eci

__all__ = [
    "rk4_step",
    "rk4_batch",
    "propagate_batch_numpy",
    "ConjunctionDetector",
    "ConjunctionWarning",
    "propagate",
    "propagate_with_drag",
    "propagate_steps",
    "propagate_batch",
    "propagate_batch_full_history",
    "detect_conjunctions",
    "backend_info",
    "sun_position_eci",
    "moon_position_eci",
]
