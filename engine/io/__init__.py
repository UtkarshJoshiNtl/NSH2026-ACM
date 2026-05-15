"""I/O helpers for Astrosis.

Keep this package lightweight so code that only needs geometry or physics does
not pay for the HTTP/TLE client on import.
"""

from __future__ import annotations

from importlib import import_module

__all__ = ["tle_ingestor", "TLEIngestor"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module 'engine.io' has no attribute {name!r}")
    module = import_module(".data", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value

