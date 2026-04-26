"""
backend/core/physics/fallback.py — Pure Python Physics Engine
=============================================================
Fallback implementation when C++ engine is unavailable.
NSH 2026 compliant: J2 perturbation only, no atmospheric drag.
"""

import math
from .constants import MU, RE, J2


def rk4_py(state: tuple, dt: float) -> tuple:
    """RK4 integrator for orbital propagation with J2 perturbation."""

    def acceleration(r):
        r_mag = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        
        # Two-body gravity
        a_grav = [-MU / r_mag**3 * r[i] for i in range(3)]
        
        # J2 perturbation (NSH 2026 requirement)
        z2 = r[2] ** 2
        r2 = r_mag ** 2
        factor = 1.5 * J2 * MU * (RE ** 2) / (r_mag ** 5)
        
        a_j2 = [
            factor * r[0] * (5 * z2 / r2 - 1),
            factor * r[1] * (5 * z2 / r2 - 1),
            factor * r[2] * (5 * z2 / r2 - 3)
        ]
        
        return [a_grav[i] + a_j2[i] for i in range(3)]

    r = state[:3]
    v = state[3:6]

    k1_v = acceleration(r)
    k1_r = v

    r1 = [r[i] + 0.5 * dt * k1_r[i] for i in range(3)]
    k2_v = acceleration(r1)
    k2_r = [v[i] + 0.5 * dt * k1_v[i] for i in range(3)]

    r2 = [r[i] + 0.5 * dt * k2_r[i] for i in range(3)]
    k3_v = acceleration(r2)
    k3_r = [v[i] + 0.5 * dt * k2_v[i] for i in range(3)]

    r3 = [r[i] + dt * k3_r[i] for i in range(3)]
    k4_v = acceleration(r3)
    k4_r = [v[i] + dt * k3_v[i] for i in range(3)]

    r_new = [
        r[i] + (dt / 6.0) * (k1_r[i] + 2 * k2_r[i] + 2 * k3_r[i] + k4_r[i])
        for i in range(3)
    ]
    v_new = [
        v[i] + (dt / 6.0) * (k1_v[i] + 2 * k2_v[i] + 2 * k3_v[i] + k4_v[i])
        for i in range(3)
    ]

    return tuple(r_new + v_new)
