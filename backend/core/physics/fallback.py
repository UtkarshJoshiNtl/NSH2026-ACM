"""
backend/core/physics/fallback.py — Pure Python Physics Engine
=============================================================
Fallback implementation when C++ engine is unavailable.
"""

import math
from .constants import MU, RE, J2


def rk4_py(state: tuple, dt: float) -> tuple:
    """RK4 integrator for orbital propagation."""

    def acceleration(r):
        r_mag = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        a_grav = -MU / r_mag**3 * r[0], -MU / r_mag**3 * r[1], -MU / r_mag**3 * r[2]
        return a_grav

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


def rk4_py_drag(
    state: tuple, dt: float, area: float = 0.1, mass: float = 100.0, cd: float = 2.2
) -> tuple:
    """RK4 integrator with atmospheric drag for LEO objects.

    Args:
        state: Position and velocity [x, y, z, vx, vy, vz] in km and km/s
        dt: Time step in seconds
        area: Cross-sectional area in m²
        mass: Object mass in kg
        cd: Drag coefficient (dimensionless)

    Returns:
        Updated state tuple
    """

    def acceleration(r, v):
        r_mag = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        v_mag = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)

        # Gravitational acceleration
        a_grav = [-MU / r_mag**3 * r[i] for i in range(3)]

        # Atmospheric drag (simplified exponential atmosphere model)
        # Scale height ~8.5 km, sea level density ~1.225 kg/m³
        altitude = r_mag - RE
        if altitude < 1000:  # Only apply drag below 1000 km
            rho = 1.225 * math.exp(-altitude / 8.5)  # kg/m³
            drag_force = 0.5 * rho * v_mag**2 * cd * area  # N
            drag_accel = drag_force / mass / 1000  # km/s² (convert N to kg·km/s²)

            # Drag acts opposite to velocity direction
            a_drag = (
                [-drag_accel * v[i] / v_mag for i in range(3)]
                if v_mag > 0
                else [0, 0, 0]
            )
        else:
            a_drag = [0, 0, 0]

        return [a_grav[i] + a_drag[i] for i in range(3)]

    r = state[:3]
    v = state[3:6]

    k1_v = acceleration(r, v)
    k1_r = v

    r1 = [r[i] + 0.5 * dt * k1_r[i] for i in range(3)]
    k2_v = acceleration(r1, [v[i] + 0.5 * dt * k1_v[i] for i in range(3)])
    k2_r = [v[i] + 0.5 * dt * k1_v[i] for i in range(3)]

    r2 = [r[i] + 0.5 * dt * k2_r[i] for i in range(3)]
    k3_v = acceleration(r2, [v[i] + 0.5 * dt * k2_v[i] for i in range(3)])
    k3_r = [v[i] + 0.5 * dt * k2_v[i] for i in range(3)]

    r3 = [r[i] + dt * k3_r[i] for i in range(3)]
    k4_v = acceleration(r3, [v[i] + dt * k3_v[i] for i in range(3)])
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
