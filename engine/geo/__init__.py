"""Geometry and visibility helpers for Astrosis."""

from __future__ import annotations

from importlib import import_module

from .frames import (
    gmst_from_datetime,
    eci_to_ecef,
    ecef_to_geodetic,
    geodetic_to_ecef,
    topocentric_aer,
)
from .visibility import (
    sun_position_eci,
    check_eclipse,
    is_optically_visible,
)

__all__ = [
    "gmst_from_datetime",
    "eci_to_ecef",
    "ecef_to_geodetic",
    "geodetic_to_ecef",
    "topocentric_aer",
    "sun_position_eci",
    "check_eclipse",
    "is_optically_visible",
    "report_passes",
]


def __getattr__(name: str):
    if name != "report_passes":
        raise AttributeError(f"module 'engine.geo' has no attribute {name!r}")
    module = import_module(".analysis", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value

