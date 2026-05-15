"""Astrosis engine package.

Keep this module light: importing `engine` should not eagerly pull in the core
physics backend, TLE ingestion, or validation helpers.
"""

from __future__ import annotations

from importlib import import_module

from .constants import (
    MU, RE, J2, J3, J4, OMEGA_EARTH, MU_SUN, MU_MOON,
    F_WGS84, E2_WGS84, CRITICAL_DISTANCE, WARNING_DISTANCE, ADVISORY_DISTANCE,
    RS_SUN, AU, P_SR,
)
from .simulation import SimulationContext

__all__ = [
    "SimulationContext",
    "MU", "RE", "J2", "J3", "J4", "OMEGA_EARTH", "MU_SUN", "MU_MOON",
    "F_WGS84", "E2_WGS84", "CRITICAL_DISTANCE", "WARNING_DISTANCE",
    "ADVISORY_DISTANCE", "RS_SUN", "AU", "P_SR",
]

_LAZY_EXPORTS = {
    "rk4_step": (".core", "rk4_step"),
    "rk4_batch": (".core", "rk4_batch"),
    "propagate_batch_numpy": (".core", "propagate_batch_numpy"),
    "ConjunctionDetector": (".core", "ConjunctionDetector"),
    "ConjunctionWarning": (".core", "ConjunctionWarning"),
    "propagate": (".core", "propagate"),
    "propagate_batch": (".core", "propagate_batch"),
    "detect_conjunctions": (".core", "detect_conjunctions"),
    "backend_info": (".core", "backend_info"),
    "core_sun_position_eci": (".core", "sun_position_eci"),
    "core_moon_position_eci": (".core", "moon_position_eci"),
    "gmst_from_datetime": (".geo", "gmst_from_datetime"),
    "eci_to_ecef": (".geo", "eci_to_ecef"),
    "ecef_to_geodetic": (".geo", "ecef_to_geodetic"),
    "geodetic_to_ecef": (".geo", "geodetic_to_ecef"),
    "topocentric_aer": (".geo", "topocentric_aer"),
    # NOTE: geo/visibility exports sun_position_eci, check_eclipse, is_optically_visible
    # but they are unused since analysis.py was removed. Core ephemeris module provides
    # the sun/moon positions used by the propagator (via core_sun_position_eci).
    "tle_ingestor": (".io", "tle_ingestor"),
    "TLEIngestor": (".io", "TLEIngestor"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'engine' has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

