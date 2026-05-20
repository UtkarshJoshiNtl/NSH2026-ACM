import math
import numpy as np
from ..constants import MU, RE, J2, J3, J4, OMEGA_EARTH, P_SR, MU_SUN, MU_MOON, AU, RS_SUN
from .ephemeris import sun_position_eci, moon_position_eci

__all__ = [
    "rk4_step", "rk4_batch", "propagate_batch_numpy",
]


def _gravity_accel(x, y, z, r_mag, r2, r3, r5, r7):
    ax = -MU * x / r3
    ay = -MU * y / r3
    az = -MU * z / r3

    z2_r2 = (z * z) / r2
    j2f = 1.5 * J2 * MU * RE * RE / r5
    ax += j2f * x * (5.0 * z2_r2 - 1.0)
    ay += j2f * y * (5.0 * z2_r2 - 1.0)
    az += j2f * z * (5.0 * z2_r2 - 3.0)

    j3f = -2.5 * J3 * MU * RE**3 / r7
    ax += j3f * x * (7.0 * z2_r2 * z - 3.0 * z)
    ay += j3f * y * (7.0 * z2_r2 * z - 3.0 * z)
    az += j3f * (7.0 * z2_r2 * z * z - 6.0 * z * z + 0.6 * r2)

    z4_r4 = z2_r2 * z2_r2
    j4f = 0.625 * J4 * MU * RE**4 / r7
    ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4)
    az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4)

    return ax, ay, az


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
    (1000, 1e9,   3.019e-15),
]


def get_atmospheric_density(altitude_km):
    if isinstance(altitude_km, (float, int)):
        if altitude_km >= 1000: return 0.0
        if altitude_km < 0: altitude_km = 0.0
        for i in range(len(_ATMO_TABLE) - 1):
            h0, H, rho0 = _ATMO_TABLE[i]
            if h0 <= altitude_km < _ATMO_TABLE[i+1][0]:
                return rho0 * math.exp(-(altitude_km - h0) / H)
        return 0.0

    alt = np.atleast_1d(altitude_km)
    rho = np.zeros_like(alt)
    for i in range(len(_ATMO_TABLE) - 1):
        h0, H, rho0 = _ATMO_TABLE[i]
        mask = (alt >= h0) & (alt < _ATMO_TABLE[i+1][0])
        if np.any(mask):
            rho[mask] = rho0 * np.exp(-(alt[mask] - h0) / H)
    rho[alt >= 1000] = 0.0
    return rho


def _third_body_accel(r, r_body, mu_body):
    dx = r_body[0] - r[0]
    dy = r_body[1] - r[1]
    dz = r_body[2] - r[2]
    d_mag = math.sqrt(dx*dx + dy*dy + dz*dz)
    d3 = d_mag * d_mag * d_mag
    rb_mag = math.sqrt(r_body[0]*r_body[0] + r_body[1]*r_body[1] + r_body[2]*r_body[2])
    rb3 = rb_mag * rb_mag * rb_mag
    return (
        mu_body * (dx / d3 - r_body[0] / rb3),
        mu_body * (dy / d3 - r_body[1] / rb3),
        mu_body * (dz / d3 - r_body[2] / rb3),
    )


def _srp_accel(r, r_sun, area, mass, cr):
    if area <= 0 or mass <= 0:
        return 0.0, 0.0, 0.0

    rs_mag = math.sqrt(r_sun[0]*r_sun[0] + r_sun[1]*r_sun[1] + r_sun[2]*r_sun[2])
    dot_prod = r[0]*r_sun[0] + r[1]*r_sun[1] + r[2]*r_sun[2]
    r_mag = math.sqrt(r[0]*r[0] + r[1]*r[1] + r[2]*r[2])

    shadow = 1.0
    if dot_prod < 0:
        proj = dot_prod / rs_mag
        d_perp = math.sqrt(max(0.0, r_mag*r_mag - proj*proj))
        if d_perp < RE:
            shadow = 0.0

    if shadow == 0.0:
        return 0.0, 0.0, 0.0

    au_scale = (AU / rs_mag)**2
    coeff = P_SR * cr * (area / mass) * shadow * au_scale * 1e-3
    return coeff * (r[0] - r_sun[0]), coeff * (r[1] - r_sun[1]), coeff * (r[2] - r_sun[2])


def rk4_step(state: tuple, dt: float, mjd0: float = 0.0, current_step: int = 0,
             area: float = 0.0, mass: float = 1.0, cd: float = 2.2, cr: float = 1.5) -> tuple:
    def accel(r, v, local_mjd):
        x, y, z = r[0], r[1], r[2]
        r_mag = math.sqrt(x*x + y*y + z*z)
        r2 = r_mag * r_mag
        r3 = r2 * r_mag
        r5 = r3 * r2
        r7 = r5 * r2

        ax, ay, az = _gravity_accel(x, y, z, r_mag, r2, r3, r5, r7)

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

        if mjd0 > 0.0:
            r_sun = sun_position_eci(local_mjd)
            r_moon = moon_position_eci(local_mjd)

            sax, say, saz = _third_body_accel(r, r_sun, MU_SUN)
            ax += sax; ay += say; az += saz
            max_a, may, maz = _third_body_accel(r, r_moon, MU_MOON)
            ax += max_a; ay += may; az += maz

            if area > 0 and mass > 0:
                srp_ax, srp_ay, srp_az = _srp_accel(r, r_sun, area, mass, cr)
                ax += srp_ax; ay += srp_ay; az += srp_az

        return ax, ay, az

    r = state[:3]
    v = state[3:]

    mjd_start = mjd0 + (current_step * dt) / 86400.0 if mjd0 > 0 else 0.0
    mjd_mid   = mjd_start + (dt / 2.0) / 86400.0 if mjd0 > 0 else 0.0
    mjd_end   = mjd_start + dt / 86400.0 if mjd0 > 0 else 0.0

    k1_v = accel(r, v, mjd_start)
    k1_r = v

    r1 = tuple(r[i] + 0.5 * dt * k1_r[i] for i in range(3))
    v1 = tuple(v[i] + 0.5 * dt * k1_v[i] for i in range(3))
    k2_v = accel(r1, v1, mjd_mid)
    k2_r = v1

    r2 = tuple(r[i] + 0.5 * dt * k2_r[i] for i in range(3))
    v2 = tuple(v[i] + 0.5 * dt * k2_v[i] for i in range(3))
    k3_v = accel(r2, v2, mjd_mid)
    k3_r = v2

    r3_tmp = tuple(r[i] + dt * k3_r[i] for i in range(3))
    v3_tmp = tuple(v[i] + dt * k3_v[i] for i in range(3))
    k4_v = accel(r3_tmp, v3_tmp, mjd_end)
    k4_r = v3_tmp

    res = tuple(state[i] + (dt / 6.0) * (k1_r[i] + 2*k2_r[i] + 2*k3_r[i] + k4_r[i]) if i < 3 else
                state[i] + (dt / 6.0) * (k1_v[i-3] + 2*k2_v[i-3] + 2*k3_v[i-3] + k4_v[i-3]) for i in range(6))
    return res


def _accel_batch(R: np.ndarray, V: np.ndarray,
                 area: float = 0.0, mass: float = 1.0, cd: float = 2.2, cr: float = 1.5,
                 with_drag: bool = False, mjd: float = 0.0) -> np.ndarray:
    X, Y, Z = R[:, 0], R[:, 1], R[:, 2]
    R_mag = np.linalg.norm(R, axis=1)
    R2 = R_mag**2
    R3 = R2 * R_mag
    R5 = R3 * R2
    R7 = R5 * R2

    ax = -MU * X / R3
    ay = -MU * Y / R3
    az = -MU * Z / R3

    Z2_R2 = (Z**2) / R2
    J2F = 1.5 * J2 * MU * RE**2 / R5
    ax += J2F * X * (5.0 * Z2_R2 - 1.0)
    ay += J2F * Y * (5.0 * Z2_R2 - 1.0)
    az += J2F * Z * (5.0 * Z2_R2 - 3.0)

    J3F = -2.5 * J3 * MU * RE**3 / R7
    ax += J3F * X * (7.0 * Z2_R2 * Z - 3.0 * Z)
    ay += J3F * Y * (7.0 * Z2_R2 * Z - 3.0 * Z)
    az += J3F * (7.0 * Z2_R2 * Z * Z - 6.0 * Z * Z + 0.6 * R2)

    Z4_R4 = Z2_R2**2
    J4F = 0.625 * J4 * MU * RE**4 / R7
    ax += J4F * X * (3.0 - 42.0 * Z2_R2 + 63.0 * Z4_R4)
    ay += J4F * Y * (3.0 - 42.0 * Z2_R2 + 63.0 * Z4_R4)
    az += J4F * Z * (15.0 - 70.0 * Z2_R2 + 63.0 * Z4_R4)

    if with_drag and mass > 0:
        alt = R_mag - RE
        rho = get_atmospheric_density(alt)
        mask = (rho > 0) & (alt >= 0) & (alt < 1000)
        if np.any(mask):
            vr_x = V[mask, 0] + OMEGA_EARTH * Y[mask]
            vr_y = V[mask, 1] - OMEGA_EARTH * X[mask]
            vr_z = V[mask, 2]
            v_rel_mag = np.sqrt(vr_x**2 + vr_y**2 + vr_z**2)

            drag_coeff = -0.5 * cd * (area / mass) * rho[mask] * v_rel_mag * 1000.0
            ax[mask] += drag_coeff * vr_x
            ay[mask] += drag_coeff * vr_y
            az[mask] += drag_coeff * vr_z

    if mjd > 0.0:
        r_sun = sun_position_eci(mjd)
        r_moon = moon_position_eci(mjd)

        dx = r_sun[0] - X
        dy = r_sun[1] - Y
        dz = r_sun[2] - Z
        d_mag = np.sqrt(dx*dx + dy*dy + dz*dz)
        d3 = d_mag**3
        rb_mag = np.linalg.norm(r_sun)
        rb3 = rb_mag**3
        ax += MU_SUN * (dx / d3 - r_sun[0] / rb3)
        ay += MU_SUN * (dy / d3 - r_sun[1] / rb3)
        az += MU_SUN * (dz / d3 - r_sun[2] / rb3)

        mdx = r_moon[0] - X
        mdy = r_moon[1] - Y
        mdz = r_moon[2] - Z
        md_mag = np.sqrt(mdx*mdx + mdy*mdy + mdz*mdz)
        md3 = md_mag**3
        mrb_mag = np.linalg.norm(r_moon)
        mrb3 = mrb_mag**3
        ax += MU_MOON * (mdx / md3 - r_moon[0] / mrb3)
        ay += MU_MOON * (mdy / md3 - r_moon[1] / mrb3)
        az += MU_MOON * (mdz / md3 - r_moon[2] / mrb3)

        if area > 0 and mass > 0:
            dot_prod = X*r_sun[0] + Y*r_sun[1] + Z*r_sun[2]
            proj = dot_prod / rb_mag
            d_perp = np.sqrt(np.maximum(0.0, R2 - proj**2))
            shadow = np.ones_like(X)
            shadow[(dot_prod < 0) & (d_perp < RE)] = 0.0
            au_scale = (AU / rb_mag)**2
            coeff = -P_SR * cr * (area / mass) * shadow * au_scale * 1e-3
            ax += coeff * dx
            ay += coeff * dy
            az += coeff * dz

    return np.column_stack((ax, ay, az))


def rk4_batch(state_arr: np.ndarray, dt_seconds: float, steps: int,
              area: float = 0.0, mass: float = 1.0, cd: float = 2.2, cr: float = 1.5,
              with_drag: bool = False, mjd0: float = 0.0) -> np.ndarray:
    R = state_arr[:, :3].copy()
    V = state_arr[:, 3:].copy()

    for step in range(steps):
        mjd_start = mjd0 + (step * dt_seconds) / 86400.0 if mjd0 > 0 else 0.0
        mjd_mid   = mjd_start + (dt_seconds / 2.0) / 86400.0 if mjd0 > 0 else 0.0
        mjd_end   = mjd_start + dt_seconds / 86400.0 if mjd0 > 0 else 0.0

        k1_v = _accel_batch(R, V, area, mass, cd, cr, with_drag, mjd_start)
        k1_r = V

        R1 = R + 0.5 * dt_seconds * k1_r
        V1 = V + 0.5 * dt_seconds * k1_v
        k2_v = _accel_batch(R1, V1, area, mass, cd, cr, with_drag, mjd_mid)
        k2_r = V1

        R2 = R + 0.5 * dt_seconds * k2_r
        V2 = V + 0.5 * dt_seconds * k2_v
        k3_v = _accel_batch(R2, V2, area, mass, cd, cr, with_drag, mjd_mid)
        k3_r = V2

        R3 = R + dt_seconds * k3_r
        V3 = V + dt_seconds * k3_v
        k4_v = _accel_batch(R3, V3, area, mass, cd, cr, with_drag, mjd_end)
        k4_r = V3

        R += (dt_seconds / 6.0) * (k1_r + 2 * k2_r + 2 * k3_r + k4_r)
        V += (dt_seconds / 6.0) * (k1_v + 2 * k2_v + 2 * k3_v + k4_v)

    return np.hstack((R, V))


def propagate_batch_numpy(states: list, dt_seconds: float, steps: int,
                          area: float = 0.0, mass: float = 1.0, cd: float = 2.2, cr: float = 1.5,
                          with_drag: bool = False, mjd0: float = 0.0) -> list:
    arr = np.array(states, dtype=np.float64)
    arr = rk4_batch(arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0)
    return arr.tolist()
