"""
astrosis/physics/propagator.py — Pure Python & NumPy Orbital Propagator
========================================================================
Numerical integration using RK4 with:
  - J2 + J3 + J4 gravity harmonics (EGM96)
  - US Standard Atmosphere 1976 drag with Earth-rotation velocity correction
  - Vectorized NumPy batch propagation for high-throughput scenarios
"""

import math
import numpy as np
from ..constants import MU, RE, J2, J3, J4, OMEGA_EARTH


# ---------------------------------------------------------------------------
# US Standard Atmosphere 1976 — piecewise exponential density table (kg/m³)
# Each tuple: (alt_base_km, scale_height_km, rho_base)
# Source: Vallado "Fundamentals of Astrodynamics", Table 8-4
# ---------------------------------------------------------------------------
_ATMO_TABLE = [
    (0,    8.44,  1.225e+0), (25,   6.49,  3.899e-2), (30,   6.75,  1.774e-2),
    (40,   7.58,  3.972e-3), (50,   8.55,  1.057e-3), (60,   7.71,  3.206e-4),
    (70,   6.55,  8.770e-5), (80,   5.79,  1.905e-5), (90,   5.57,  3.396e-6),
    (100,  5.90,  5.297e-7), (110,  7.17,  9.661e-8), (120,  9.59,  2.438e-8),
    (130, 12.20,  8.484e-9), (140, 15.50,  3.845e-9), (150, 19.30,  2.070e-9),
    (180, 26.00,  5.464e-10),(200, 26.00,  2.789e-10),(250, 38.50,  7.248e-11),
    (300, 51.00,  2.418e-11),(350, 59.50,  9.518e-12),(400, 67.60,  3.725e-12),
    (450, 76.00,  1.585e-12),(500, 84.00,  6.967e-13),(600, 105.0,  1.454e-13),
    (700, 130.0,  3.614e-14),(800, 180.0,  1.170e-14),(900, 268.0,  5.245e-15),
    (1000, 1e9,   3.019e-15),  # exosphere sentinel
]


def get_atmospheric_density(altitude_km):
    """
    Unified atmospheric density lookup (US Standard Atmosphere 1976).
    Supports both scalar (float) and vectorized (NumPy array) inputs.
    """
    # Scalar path
    if isinstance(altitude_km, (float, int)):
        if altitude_km >= 1000: return 0.0
        if altitude_km < 0: altitude_km = 0.0
        for i in range(len(_ATMO_TABLE) - 1):
            h0, H, rho0 = _ATMO_TABLE[i]
            if h0 <= altitude_km < _ATMO_TABLE[i+1][0]:
                return rho0 * math.exp(-(altitude_km - h0) / H)
        return _ATMO_TABLE[0][2] * math.exp(-altitude_km / _ATMO_TABLE[0][1])

    # Vectorized path
    alt = np.atleast_1d(altitude_km)
    rho = np.zeros_like(alt)
    for i in range(len(_ATMO_TABLE) - 1):
        h0, H, rho0 = _ATMO_TABLE[i]
        mask = (alt >= h0) & (alt < _ATMO_TABLE[i+1][0])
        if np.any(mask):
            rho[mask] = rho0 * np.exp(-(alt[mask] - h0) / H)
    rho[alt >= 1000] = 0.0
    return rho


# ---------------------------------------------------------------------------
# Scalar RK4 (single satellite)
# ---------------------------------------------------------------------------

def rk4_step(state: tuple, dt: float,
             area: float = 0.0, mass: float = 1.0, cd: float = 2.2) -> tuple:
    """
    Consolidated RK4 integrator with J2+J3+J4 gravity (+ optional drag).
    Operates on a single 6-element state vector (x,y,z,vx,vy,vz) [km, km/s].
    If area > 0 and mass > 0, drag is included.
    """

    def acceleration(r, v):
        x, y, z = r[0], r[1], r[2]
        r_mag = math.sqrt(x*x + y*y + z*z)
        r2 = r_mag * r_mag
        r3 = r2 * r_mag
        r5 = r3 * r2
        r7 = r5 * r2

        # Two-body gravity
        ax = -MU * x / r3
        ay = -MU * y / r3
        az = -MU * z / r3

        # J2
        z2_r2 = (z * z) / r2
        j2f = 1.5 * J2 * MU * RE * RE / r5
        ax += j2f * x * (5.0 * z2_r2 - 1.0)
        ay += j2f * y * (5.0 * z2_r2 - 1.0)
        az += j2f * z * (5.0 * z2_r2 - 3.0)

        # J3
        zr = z / r_mag
        j3f = 2.5 * J3 * MU * RE**3 / r7
        ax += j3f * x * (7.0 * z2_r2 * zr - 3.0 * zr)
        ay += j3f * y * (7.0 * z2_r2 * zr - 3.0 * zr)
        az += j3f * (7.0 * z2_r2 * zr * z - 6.0 * z2_r2 + (3.0 / 5.0))

        # J4
        z4_r4 = z2_r2 * z2_r2
        j4f = 0.625 * J4 * MU * RE**4 / r7
        ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

        # Atmospheric drag
        if area > 0 and mass > 0:
            altitude = r_mag - RE
            if 0.0 <= altitude < 1000.0:
                rho = get_atmospheric_density(altitude)
                vr_x = v[0] + OMEGA_EARTH * y
                vr_y = v[1] - OMEGA_EARTH * x
                vr_z = v[2]
                v_rel_mag = math.sqrt(vr_x*vr_x + vr_y*vr_y + vr_z*vr_z)
                if v_rel_mag > 0:
                    drag_coeff = -0.5 * cd * (area / mass) * rho * v_rel_mag * 1000.0
                    ax += drag_coeff * vr_x
                    ay += drag_coeff * vr_y
                    az += drag_coeff * vr_z

        return ax, ay, az

    r = state[:3]
    v = state[3:6]

    k1_v = acceleration(r, v)
    k1_r = v

    r1 = tuple(r[i] + 0.5 * dt * k1_r[i] for i in range(3))
    v1 = tuple(v[i] + 0.5 * dt * k1_v[i] for i in range(3))
    k2_v = acceleration(r1, v1)
    k2_r = v1

    r2 = tuple(r[i] + 0.5 * dt * k2_r[i] for i in range(3))
    v2 = tuple(v[i] + 0.5 * dt * k2_v[i] for i in range(3))
    k3_v = acceleration(r2, v2)
    k3_r = v2

    r3 = tuple(r[i] + dt * k3_r[i] for i in range(3))
    v3 = tuple(v[i] + dt * k3_v[i] for i in range(3))
    k4_v = acceleration(r3, v3)
    k4_r = v3

    r_new = [r[i] + (dt / 6.0) * (k1_r[i] + 2*k2_r[i] + 2*k3_r[i] + k4_r[i]) for i in range(3)]
    v_new = [v[i] + (dt / 6.0) * (k1_v[i] + 2*k2_v[i] + 2*k3_v[i] + k4_v[i]) for i in range(3)]

    return tuple(r_new + v_new)


# ---------------------------------------------------------------------------
# Vectorized NumPy Batch Propagator (N satellites in parallel)
# ---------------------------------------------------------------------------

def _accel_batch(R: np.ndarray, V: np.ndarray,
                 area: float = 0.0, mass: float = 1.0, cd: float = 2.2,
                 with_drag: bool = False) -> np.ndarray:
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    r_mag = np.linalg.norm(R, axis=1)
    r2 = r_mag ** 2
    r3 = r2 * r_mag
    r5 = r3 * r2
    r7 = r5 * r2

    A = np.zeros_like(R)
    inv_r3 = MU / r3
    A[:, 0] = -inv_r3 * x
    A[:, 1] = -inv_r3 * y
    A[:, 2] = -inv_r3 * z

    z2_r2 = (z * z) / r2
    j2f = 1.5 * J2 * MU * RE * RE / r5
    A[:, 0] += j2f * x * (5.0 * z2_r2 - 1.0)
    A[:, 1] += j2f * y * (5.0 * z2_r2 - 1.0)
    A[:, 2] += j2f * z * (5.0 * z2_r2 - 3.0)

    j3f = 2.5 * J3 * MU * RE**3 / r7
    zr = z / r_mag
    A[:, 0] += j3f * x * (7.0 * z2_r2 * zr - 3.0 * zr)
    A[:, 1] += j3f * y * (7.0 * z2_r2 * zr - 3.0 * zr)
    A[:, 2] += j3f * (7.0 * z2_r2 * zr * z - 6.0 * z2_r2 + (3.0 / 5.0))

    j4f = 0.625 * J4 * MU * RE**4 / r7
    z4_r4 = z2_r2 * z2_r2
    A[:, 0] += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    A[:, 1] += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    A[:, 2] += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

    if with_drag and mass > 0:
        altitude = r_mag - RE
        rho = get_atmospheric_density(altitude)
        drag_mask = (altitude >= 0.0) & (altitude < 1000.0) & (rho > 0)
        if np.any(drag_mask):
            Vr = V.copy()
            Vr[drag_mask, 0] += OMEGA_EARTH * y[drag_mask]
            Vr[drag_mask, 1] -= OMEGA_EARTH * x[drag_mask]
            v_rel_mag = np.linalg.norm(Vr, axis=1)
            coeff = np.zeros(len(R))
            m = drag_mask & (v_rel_mag > 0)
            coeff[m] = -0.5 * cd * (area / mass) * rho[m] * v_rel_mag[m] * 1000.0
            A[m] += coeff[m, np.newaxis] * Vr[m]

    return A


def rk4_batch(states: np.ndarray, dt: float,
              area: float = 0.0, mass: float = 1.0, cd: float = 2.2,
              with_drag: bool = False) -> np.ndarray:
    R = states[:, :3].copy()
    V = states[:, 3:].copy()

    k1_a = _accel_batch(R, V, area, mass, cd, with_drag)
    k1_v = V

    R2 = R + 0.5 * dt * k1_v
    V2 = V + 0.5 * dt * k1_a
    k2_a = _accel_batch(R2, V2, area, mass, cd, with_drag)
    k2_v = V2

    R3 = R + 0.5 * dt * k2_v
    V3 = V + 0.5 * dt * k2_a
    k3_a = _accel_batch(R3, V3, area, mass, cd, with_drag)
    k3_v = V3

    R4 = R + dt * k3_v
    V4 = V + dt * k3_a
    k4_a = _accel_batch(R4, V4, area, mass, cd, with_drag)
    k4_v = V4

    R_new = R + (dt / 6.0) * (k1_v + 2*k2_v + 2*k3_v + k4_v)
    V_new = V + (dt / 6.0) * (k1_a + 2*k2_a + 2*k3_a + k4_a)

    return np.hstack([R_new, V_new])


def propagate_batch_numpy(states: list, dt_seconds: float, steps: int,
                          area: float = 0.0, mass: float = 1.0, cd: float = 2.2,
                          with_drag: bool = False) -> list:
    arr = np.array(states, dtype=np.float64)
    for _ in range(steps):
        arr = rk4_batch(arr, dt_seconds, area, mass, cd, with_drag)
    return arr.tolist()
