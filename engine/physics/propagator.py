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

# Pre-compute NumPy arrays for fast vectorized density lookup
_ATMO_ALTS = np.array([e[0] for e in _ATMO_TABLE])
_ATMO_SCALES = np.array([e[1] for e in _ATMO_TABLE])
_ATMO_RHOS = np.array([e[2] for e in _ATMO_TABLE])


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


def _atmospheric_density_vec(altitude_km: np.ndarray) -> np.ndarray:
    """Vectorized atmospheric density lookup for NumPy arrays of altitudes."""
    rho = np.zeros_like(altitude_km)
    for i in range(len(_ATMO_TABLE) - 1):
        h0, H, rho0 = _ATMO_TABLE[i]
        h1 = _ATMO_TABLE[i + 1][0]
        mask = (altitude_km >= h0) & (altitude_km < h1)
        if np.any(mask):
            rho[mask] = rho0 * np.exp(-(altitude_km[mask] - h0) / H)
    # Above exosphere
    rho[altitude_km >= 1000] = 0.0
    return rho


# ---------------------------------------------------------------------------
# Scalar RK4 (single satellite, high accuracy: J2+J3+J4)
# ---------------------------------------------------------------------------

def rk4_py(state: tuple, dt: float) -> tuple:
    """
    RK4 integrator with J2+J3+J4 gravity perturbations.
    Operates on a single 6-element state vector (x,y,z,vx,vy,vz) [km, km/s].
    """

    def acceleration(r):
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
        z2 = z * z
        z2_r2 = z2 / r2
        j2f = 1.5 * J2 * MU * RE * RE / r5
        ax += j2f * x * (5.0 * z2_r2 - 1.0)
        ay += j2f * y * (5.0 * z2_r2 - 1.0)
        az += j2f * z * (5.0 * z2_r2 - 3.0)

        # J3
        j3f = 2.5 * J3 * MU * RE**3 / r7
        ax += j3f * x * (7.0 * z2_r2 * z / r_mag - 3.0 * z / r_mag)
        ay += j3f * y * (7.0 * z2_r2 * z / r_mag - 3.0 * z / r_mag)
        az += j3f * (7.0 * z2_r2 * z2 / r2 - 6.0 * z2_r2 + 3.0 / 5.0)

        # J4
        z4_r4 = z2_r2 * z2_r2
        j4f = (5.0 / 8.0) * J4 * MU * RE**4 / (r5 * r2)
        ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

        return ax, ay, az

    r = state[:3]
    v = state[3:6]

    k1_v = acceleration(r)
    k1_r = v

    r1 = tuple(r[i] + 0.5 * dt * k1_r[i] for i in range(3))
    k2_v = acceleration(r1)
    k2_r = tuple(v[i] + 0.5 * dt * k1_v[i] for i in range(3))

    r2 = tuple(r[i] + 0.5 * dt * k2_r[i] for i in range(3))
    k3_v = acceleration(r2)
    k3_r = tuple(v[i] + 0.5 * dt * k2_v[i] for i in range(3))

    r3 = tuple(r[i] + dt * k3_r[i] for i in range(3))
    k4_v = acceleration(r3)
    k4_r = tuple(v[i] + dt * k3_v[i] for i in range(3))

    r_new = [r[i] + (dt / 6.0) * (k1_r[i] + 2*k2_r[i] + 2*k3_r[i] + k4_r[i]) for i in range(3)]
    v_new = [v[i] + (dt / 6.0) * (k1_v[i] + 2*k2_v[i] + 2*k3_v[i] + k4_v[i]) for i in range(3)]

    return tuple(r_new + v_new)


def rk4_py_drag(
    state: tuple, dt: float, area: float = 10.0, mass: float = 1000.0, cd: float = 2.2
) -> tuple:
    """
    RK4 with J2+J3+J4 gravity + atmospheric drag with Earth-rotation correction.
    v_rel = v_satellite - omega_earth × r  (removes co-rotation of atmosphere).
    """

    def acceleration(r, v):
        x, y, z = r[0], r[1], r[2]
        r_mag = math.sqrt(x*x + y*y + z*z)
        r2 = r_mag * r_mag
        r3 = r2 * r_mag
        r5 = r3 * r2
        r7 = r5 * r2

        # Two-body
        ax = -MU * x / r3
        ay = -MU * y / r3
        az = -MU * z / r3

        # J2
        z2 = z * z
        z2_r2 = z2 / r2
        j2f = 1.5 * J2 * MU * RE * RE / r5
        ax += j2f * x * (5.0 * z2_r2 - 1.0)
        ay += j2f * y * (5.0 * z2_r2 - 1.0)
        az += j2f * z * (5.0 * z2_r2 - 3.0)

        # J3
        j3f = 2.5 * J3 * MU * RE**3 / r7
        ax += j3f * x * (7.0 * z2_r2 * z / r_mag - 3.0 * z / r_mag)
        ay += j3f * y * (7.0 * z2_r2 * z / r_mag - 3.0 * z / r_mag)
        az += j3f * (7.0 * z2_r2 * z2 / r2 - 6.0 * z2_r2 + 3.0 / 5.0)

        # J4
        z4_r4 = z2_r2 * z2_r2
        j4f = (5.0 / 8.0) * J4 * MU * RE**4 / (r5 * r2)
        ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
        az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

        # Atmospheric drag — Earth-rotation-corrected relative velocity
        altitude = r_mag - RE
        if 0.0 <= altitude < 1000.0:
            rho = _atmospheric_density(altitude)
            # v_rel = v - omega × r  (omega_earth around Z axis)
            vr_x = v[0] + OMEGA_EARTH * y
            vr_y = v[1] - OMEGA_EARTH * x
            vr_z = v[2]
            v_rel_mag = math.sqrt(vr_x*vr_x + vr_y*vr_y + vr_z*vr_z)
            if v_rel_mag > 0:
                # Drag: a = -0.5 * Cd * (A/m) * rho * v_rel * |v_rel|
                # Units: rho [kg/m³], A [m²], m [kg], v [km/s]
                # Factor 1000 converts m/s² → km/s²: drag_factor in km/s²
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
    k2_v = acceleration(r1, tuple(v[i] + 0.5 * dt * k1_v[i] for i in range(3)))
    k2_r = tuple(v[i] + 0.5 * dt * k1_v[i] for i in range(3))

    r2 = tuple(r[i] + 0.5 * dt * k2_r[i] for i in range(3))
    k3_v = acceleration(r2, tuple(v[i] + 0.5 * dt * k2_v[i] for i in range(3)))
    k3_r = tuple(v[i] + 0.5 * dt * k2_v[i] for i in range(3))

    r3 = tuple(r[i] + dt * k3_r[i] for i in range(3))
    k4_v = acceleration(r3, tuple(v[i] + dt * k3_v[i] for i in range(3)))
    k4_r = tuple(v[i] + dt * k3_v[i] for i in range(3))

    r_new = [r[i] + (dt / 6.0) * (k1_r[i] + 2*k2_r[i] + 2*k3_r[i] + k4_r[i]) for i in range(3)]
    v_new = [v[i] + (dt / 6.0) * (k1_v[i] + 2*k2_v[i] + 2*k3_v[i] + k4_v[i]) for i in range(3)]

    return tuple(r_new + v_new)


# ---------------------------------------------------------------------------
# Vectorized NumPy Batch Propagator (N satellites in parallel)
# ---------------------------------------------------------------------------

def _accel_batch(R: np.ndarray, V: np.ndarray,
                 area: float = 0.0, mass: float = 1.0, cd: float = 2.2,
                 with_drag: bool = False) -> np.ndarray:
    """
    Compute J2+J3+J4 acceleration (+drag) for N satellites simultaneously.

    Parameters
    ----------
    R : (N, 3) position array  [km]
    V : (N, 3) velocity array  [km/s]
    Returns (N, 3) acceleration array [km/s²]
    """
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    r_mag = np.linalg.norm(R, axis=1)          # (N,)
    r2 = r_mag ** 2
    r3 = r2 * r_mag
    r5 = r3 * r2
    r7 = r5 * r2

    # Two-body
    A = np.zeros_like(R)
    inv_r3 = MU / r3
    A[:, 0] = -inv_r3 * x
    A[:, 1] = -inv_r3 * y
    A[:, 2] = -inv_r3 * z

    # J2
    z2_r2 = (z * z) / r2
    j2f = 1.5 * J2 * MU * RE * RE / r5
    A[:, 0] += j2f * x * (5.0 * z2_r2 - 1.0)
    A[:, 1] += j2f * y * (5.0 * z2_r2 - 1.0)
    A[:, 2] += j2f * z * (5.0 * z2_r2 - 3.0)

    # J3
    j3f = 2.5 * J3 * MU * RE**3 / r7
    z_over_r = z / r_mag
    A[:, 0] += j3f * x * (7.0 * z2_r2 * z_over_r - 3.0 * z_over_r)
    A[:, 1] += j3f * y * (7.0 * z2_r2 * z_over_r - 3.0 * z_over_r)
    A[:, 2] += j3f * (7.0 * z2_r2 * z_over_r * z - 6.0 * z2_r2 + 0.6)

    # J4
    z4_r4 = z2_r2 * z2_r2
    j4f = (5.0 / 8.0) * J4 * MU * RE**4 / r7
    A[:, 0] += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    A[:, 1] += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    A[:, 2] += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

    # Atmospheric drag (vectorized)
    if with_drag and mass > 0:
        altitude = r_mag - RE
        rho = _atmospheric_density_vec(altitude)
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
    """
    Vectorized RK4 step for N satellites simultaneously.

    Parameters
    ----------
    states : (N, 6) array  [x,y,z,vx,vy,vz] in km / km/s
    dt     : time step [seconds]

    Returns
    -------
    (N, 6) updated state array
    """
    R = states[:, :3].copy()
    V = states[:, 3:].copy()

    def deriv(r, v):
        return _accel_batch(r, v, area, mass, cd, with_drag)

    k1_a = deriv(R, V)
    k1_v = V

    R2 = R + 0.5 * dt * k1_v
    V2 = V + 0.5 * dt * k1_a
    k2_a = deriv(R2, V2)
    k2_v = V2

    R3 = R + 0.5 * dt * k2_v
    V3 = V + 0.5 * dt * k2_a
    k3_a = deriv(R3, V3)
    k3_v = V3

    R4 = R + dt * k3_v
    V4 = V + dt * k3_a
    k4_a = deriv(R4, V4)
    k4_v = V4

    R_new = R + (dt / 6.0) * (k1_v + 2*k2_v + 2*k3_v + k4_v)
    V_new = V + (dt / 6.0) * (k1_a + 2*k2_a + 2*k3_a + k4_a)

    return np.hstack([R_new, V_new])


def propagate_batch_numpy(states: list, dt_seconds: float, steps: int,
                          area: float = 0.0, mass: float = 1.0, cd: float = 2.2,
                          with_drag: bool = False) -> list:
    """
    Propagate N satellites for `steps` RK4 steps using NumPy vectorization.

    Parameters
    ----------
    states       : list of N 6-element state lists [km, km/s]
    dt_seconds   : RK4 step size in seconds
    steps        : number of integration steps

    Returns
    -------
    List of N final state lists (same shape as input)
    """
    arr = np.array(states, dtype=np.float64)
    for _ in range(steps):
        arr = rk4_batch(arr, dt_seconds, area, mass, cd, with_drag)
    return arr.tolist()
