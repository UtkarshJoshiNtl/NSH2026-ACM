from __future__ import annotations
from importlib import import_module

from .frames import (
    gmst_from_datetime, eci_to_ecef, ecef_to_geodetic,
    geodetic_to_ecef, topocentric_aer,
)
from .visibility import (
    sun_position_eci, check_eclipse, is_optically_visible,
)

__all__ = [
    "gmst_from_datetime", "eci_to_ecef", "ecef_to_geodetic",
    "geodetic_to_ecef", "topocentric_aer",
    "sun_position_eci", "check_eclipse", "is_optically_visible",
    "report_passes",
]

_LAZY_GEO = {
    "report_passes": (".analysis", "report_passes"),
}


def __getattr__(name: str):
    if name not in _LAZY_GEO:
        raise AttributeError(f"module 'engine.geo' has no attribute {name!r}")
    module_name, attr_name = _LAZY_GEO[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
