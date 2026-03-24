"""
backend/core/physics_bridge.py — ACM Physics Bridge (Proxy)
=====================================================
Legacy entry point. Now proxies to the .physics package.
"""

from .physics import (
    propagate,
    propagate_steps,
    compute_fuel_used,
    detect_conjunctions,
    calculate_maneuver
)

from .physics.constants import (
    MU, RE, J2, ISP, G0, DRY_MASS, INITIAL_FUEL, MAX_DV, COOLDOWN_S
)
