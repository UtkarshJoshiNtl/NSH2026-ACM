"""
astrosis/physics/propagator.py — Pure Python Orbital Propagator
=============================================================
Numerical integration using RK4 with J2 and US Standard Atmosphere 1976 drag.
"""

import math
from ..constants import MU, RE, J2


# ---------------------------------------------------------------------------
# US Standard Atmosphere 1976 — piecewise exponential density table (kg/m³)
# Each tuple: (alt_base_km, scale_height_km, rho_base)
# Source: Vallado "Fundamentals of Astrodynamics", Table 8-4
# ---------------------------------------------------------------------------
_ATMO_TABLE = [
    (0,    8.44,  1.225e+0),
    (25,   6.49,  3.899e-2),
    (30,   6.75,  1.774e-2),
    (40,   7.58,  3.972e-3),
    (50,   8.55,  1.057e-3),
    (60,   7.71,  3.206e-4),
    (70,   6.55,  8.770e-5),
    (80,   5.79,  1.905e-5),
    (90,   5.57,  3.396e-6),
    (100,  5.90,  5.297e-7),
    (110,  7.17,  9.661e-8),
    (120,  9.59,  2.438e-8),
    (130, 12.20,  8.484e-9),
    (140, 15.50,  3.845e-9),
    (150, 19.30,  2.070e-9),
    (180, 26.00,  5.464e-10),
    (200, 26.00,  2.789e-10),
    (250, 38.50,  7.248e-11),
    (300, 51.00,  2.418e-11),
    (350, 59.50,  9.518e-12),
    (400, 67.60,  3.725e-12),
    (450, 76.00,  1.585e-12),
    (500, 84.00,  6.967e-13),
    (600, 105.0,  1.454e-13),
    (700, 130.0,  3.614e-14),
    (800, 180.0,  1.170e-14),
    (900, 268.0,  5.245e-15),
    (1000, 1e9,   3.019e-15),  # exosphere sentinel
]


def _atmospheric_density(altitude_km: float) -> float:
    """Return atmospheric density [kg/m³] via US Standard Atmosphere 1976 lookup table."""
    if altitude_km >= 1000:
        return 0.0
    if altitude_km < 0:
        altitude_km = 0.0
    for i in range(len(_ATMO_TABLE) - 1):
        h0, H, rho0 = _ATMO_TABLE[i]
        h1 = _ATMO_TABLE[i + 1][0]
        if h0 <= altitude_km < h1:
            return rho0 * math.exp(-(altitude_km - h0) / H)
    h0, H, rho0 = _ATMO_TABLE[0]
    return rho0 * math.exp(-(altitude_km - h0) / H)


def rk4_py(state: tuple, dt: float) -> tuple:
    """RK4 integrator for orbital propagation."""

    def acceleration(r):
        r_mag = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        # 2-body gravity
        a_grav = -MU / r_mag**3 * r[0], -MU / r_mag**3 * r[1], -MU / r_mag**3 * r[2]
        
        # J2 perturbation
        z2_r2 = (r[2] * r[2]) / (r_mag * r_mag)
        j2_factor = (1.5) * J2 * MU * (RE**2) / (r_mag**5)
        
        ax_j2 = j2_factor * r[0] * (5.0 * z2_r2 - 1.0)
        ay_j2 = j2_factor * r[1] * (5.0 * z2_r2 - 1.0)
        az_j2 = j2_factor * r[2] * (5.0 * z2_r2 - 3.0)
        
        return (a_grav[0] + ax_j2, a_grav[1] + ay_j2, a_grav[2] + az_j2)

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
    state: tuple, dt: float, area: float = 10.0, mass: float = 1000.0, cd: float = 2.2
) -> tuple:
    """RK4 integrator with atmospheric drag."""

    def acceleration(r, v):
        r_mag = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        v_mag = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)

        # Gravitational acceleration + J2
        z2_r2 = (r[2] * r[2]) / (r_mag * r_mag)
        j2_factor = (1.5) * J2 * MU * (RE**2) / (r_mag**5)
        
        a_grav = [-MU / r_mag**3 * r[i] for i in range(3)]
        a_j2 = [
            j2_factor * r[0] * (5.0 * z2_r2 - 1.0),
            j2_factor * r[1] * (5.0 * z2_r2 - 1.0),
            j2_factor * r[2] * (5.0 * z2_r2 - 3.0)
        ]

        # Atmospheric drag using US Standard Atmosphere 1976 table.
        altitude = r_mag - RE
        if 0 <= altitude < 1000:
            rho = _atmospheric_density(altitude)  # kg/m³
            v_m_s2 = v_mag**2 * 1e6                # (km/s)^2 -> (m/s)^2
            drag_force = 0.5 * rho * v_m_s2 * cd * area  # N
            drag_accel = drag_force / mass / 1000  # km/s²
            a_drag = (
                [-drag_accel * v[i] / v_mag for i in range(3)]
                if v_mag > 0
                else [0, 0, 0]
            )
        else:
            a_drag = [0, 0, 0]

        return [a_grav[i] + a_j2[i] + a_drag[i] for i in range(3)]

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
