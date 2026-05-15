"""Core physics and analysis helpers.

The accelerator module probes native backends at import time, so keep exports
lazy to avoid loading C++/CUDA when callers only need lightweight symbols.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "rk4_step",
    "rk4_batch",
    "propagate_batch_numpy",
    "ConjunctionDetector",
    "ConjunctionWarning",
    "propagate",
    "propagate_batch",
    "detect_conjunctions",
    "backend_info",
    "sun_position_eci",
    "moon_position_eci",
]

_LAZY_EXPORTS = {
    "rk4_step": (".propagator", "rk4_step"),
    "rk4_batch": (".propagator", "rk4_batch"),
    "propagate_batch_numpy": (".propagator", "propagate_batch_numpy"),
    "ConjunctionDetector": (".conjunction", "ConjunctionDetector"),
    "ConjunctionWarning": (".conjunction", "ConjunctionWarning"),
    "propagate": (".accelerator", "propagate"),
    "propagate_batch": (".accelerator", "propagate_batch"),
    "detect_conjunctions": (".accelerator", "detect_conjunctions"),
    "backend_info": (".accelerator", "backend_info"),
    "sun_position_eci": (".ephemeris", "sun_position_eci"),
    "moon_position_eci": (".ephemeris", "moon_position_eci"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'engine.core' has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
