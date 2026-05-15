#pragma once
#include <cuda_runtime.h>
#include <cmath>

// ── Shared Device Constants ──────────────────────────────────────────────────
// These are defined in one .cu file and accessed in others via extern if needed,
// but for simplicity and performance in small kernels, we define them here.
// Note: __constant__ must be defined in the .cu file, so we use a macro or inline.
// However, to avoid duplicate definition errors during linking, we use a single source.

static __constant__ double C_MU=398600.4418, C_RE=6378.137;
static __constant__ double C_J2=1.08263e-3, C_J3=-2.53266e-6, C_J4=-1.61990e-6;
static __constant__ double C_OMEGA=7.2921150e-5;
static __constant__ double C_MU_SUN=132712440018.0, C_MU_MOON=4902.800066;
static __constant__ double C_AU=149597870.7, C_P_SR=4.56e-6;

struct CA { double alt, H, rho0; };
static __constant__ CA C_ATM[28]={
    {0,8.44,1.225},{25,6.49,3.899e-2},{30,6.75,1.774e-2},{40,7.58,3.972e-3},
    {50,8.55,1.057e-3},{60,7.71,3.206e-4},{70,6.55,8.770e-5},{80,5.79,1.905e-5},
    {90,5.57,3.396e-6},{100,5.90,5.297e-7},{110,7.17,9.661e-8},{120,9.59,2.438e-8},
    {130,12.2,8.484e-9},{140,15.5,3.845e-9},{150,19.3,2.070e-9},{180,26.0,5.464e-10},
    {200,26.0,2.789e-10},{250,38.5,7.248e-11},{300,51.0,2.418e-11},{350,59.5,9.518e-12},
    {400,67.6,3.725e-12},{450,76.0,1.585e-12},{500,84.0,6.967e-13},{600,105.0,1.454e-13},
    {700,130.0,3.614e-14},{800,180.0,1.170e-14},{900,268.0,5.245e-15},{1000,1e9,3.019e-15}
};

// ── Shared Device Functions ──────────────────────────────────────────────────

__device__ __forceinline__ double drho(double alt) {
    if (alt < 0 || alt >= 1000) return 0.0;
    for(int i=0; i<27; i++) {
        if(C_ATM[i].alt <= alt && alt < C_ATM[i+1].alt)
            return C_ATM[i].rho0 * exp(-(alt - C_ATM[i].alt) / C_ATM[i].H);
    }
    return 0.0;
}

__device__ __forceinline__ void d_sun_position(double mjd, double& sx, double& sy, double& sz) {
    double d = mjd - 51544.5;
    double g_rad = (357.529 + 0.98560028 * d) * (M_PI / 180.0);
    double q = 280.459 + 0.98564736 * d;
    double L_rad = (q + 1.915 * sin(g_rad) + 0.020 * sin(2 * g_rad)) * (M_PI / 180.0);
    double R_au = 1.00014 - 0.01671 * cos(g_rad) - 0.00014 * cos(2 * g_rad);
    double R_km = R_au * C_AU;
    double e_rad = (23.439 - 0.00000036 * d) * (M_PI / 180.0);
    
    sx = R_km * cos(L_rad);
    sy = R_km * cos(e_rad) * sin(L_rad);
    sz = R_km * sin(e_rad) * sin(L_rad);
}

__device__ __forceinline__ void d_moon_position(double mjd, double& mx, double& my, double& mz) {
    double d = mjd - 51544.5;
    double L_rad = (218.316 + 13.176396 * d) * (M_PI / 180.0);
    double M_rad = (134.963 + 13.064993 * d) * (M_PI / 180.0);
    double F_rad = (93.272 + 13.229350 * d) * (M_PI / 180.0);
    double l_ecl = L_rad + (6.289 * sin(M_rad)) * (M_PI / 180.0);
    double b_ecl = (5.128 * sin(F_rad)) * (M_PI / 180.0);
    double dist = 385001.0 - 20905.0 * cos(M_rad);
    double e_rad = (23.439 - 0.00000036 * d) * (M_PI / 180.0);
    
    double x_ecl = dist * cos(b_ecl) * cos(l_ecl);
    double y_ecl = dist * cos(b_ecl) * sin(l_ecl);
    double z_ecl = dist * sin(b_ecl);
    
    mx = x_ecl;
    my = y_ecl * cos(e_rad) - z_ecl * sin(e_rad);
    mz = y_ecl * sin(e_rad) + z_ecl * cos(e_rad);
}

__device__ __forceinline__ void d_third_body(double x, double y, double z, double bx, double by, double bz, double mu, double& ax, double& ay, double& az) {
    double dx = bx - x, dy = by - y, dz = bz - z;
    double d_mag = sqrt(dx*dx + dy*dy + dz*dz);
    double d3 = d_mag * d_mag * d_mag;
    double b_mag = sqrt(bx*bx + by*by + bz*bz);
    double b3 = b_mag * b_mag * b_mag;
    ax += mu * (dx/d3 - bx/b3);
    ay += mu * (dy/d3 - by/b3);
    az += mu * (dz/d3 - bz/b3);
}

__device__ __forceinline__ void accel(
    double x, double y, double z, double mjd, double& ax, double& ay, double& az) {
    double r2 = x*x + y*y + z*z, rm = sqrt(r2);
    double r3 = r2 * rm, r5 = r3 * r2, r7 = r5 * r2;
    ax = -C_MU * x / r3; ay = -C_MU * y / r3; az = -C_MU * z / r3;
    
    double z2r2 = z*z / r2;
    double j2f = 1.5 * C_J2 * C_MU * C_RE * C_RE / r5;
    ax += j2f * x * (5.0 * z2r2 - 1.0);
    ay += j2f * y * (5.0 * z2r2 - 1.0);
    az += j2f * z * (5.0 * z2r2 - 3.0);
    
    double zr = z / rm;
    double j3f = 2.5 * C_J3 * C_MU * C_RE * C_RE * C_RE / r7;
    ax += j3f * x * (7.0 * z2r2 * zr - 3.0 * zr);
    ay += j3f * y * (7.0 * z2r2 * zr - 3.0 * zr);
    az += j3f * (7.0 * z2r2 * zr * z - 6.0 * z2r2 + (3.0 / 5.0));
    
    double z4r4 = z2r2 * z2r2;
    double j4f = (5.0 / 8.0) * C_J4 * C_MU * C_RE * C_RE * C_RE * C_RE / r7;
    ax += j4f * x * (3.0 - 42.0 * z2r2 + 63.0 * z4r4);
    ay += j4f * y * (3.0 - 42.0 * z2r2 + 63.0 * z4r4);
    az += j4f * z * (15.0 - 70.0 * z2r2 + 63.0 * z4r4);

    if (mjd > 0.0) {
        double sx, sy, sz; d_sun_position(mjd, sx, sy, sz);
        d_third_body(x, y, z, sx, sy, sz, C_MU_SUN, ax, ay, az);
        
        double mx, my, mz; d_moon_position(mjd, mx, my, mz);
        d_third_body(x, y, z, mx, my, mz, C_MU_MOON, ax, ay, az);
    }
}

__device__ __forceinline__ void accel_drag(
    double x, double y, double z, double vx, double vy, double vz,
    double A, double m, double cd, double cr, double mjd, double& ax, double& ay, double& az) {
    accel(x, y, z, mjd, ax, ay, az);
    double r_mag = sqrt(x*x + y*y + z*z), alt = r_mag - C_RE;
    if(alt >= 0 && alt < 1000) {
        double rho = drho(alt);
        double vrx = vx + C_OMEGA * y;
        double vry = vy - C_OMEGA * x;
        double vrz = vz;
        double vm = sqrt(vrx*vrx + vry*vry + vrz*vrz);
        if(vm > 0) {
            double df = -0.5 * cd * (A / m) * rho * vm * 1000.0;
            ax += df * vrx; ay += df * vry; az += df * vrz;
        }
    }
    
    if (mjd > 0.0 && A > 0.0 && m > 0.0) {
        double sx, sy, sz; d_sun_position(mjd, sx, sy, sz);
        double rs_mag = sqrt(sx*sx + sy*sy + sz*sz);
        double dot_prod = x*sx + y*sy + z*sz;
        double shadow = 1.0;
        
        if (dot_prod < 0) {
            double proj = dot_prod / rs_mag;
            double d_perp2 = max(0.0, r_mag*r_mag - proj*proj);
            if (sqrt(d_perp2) < C_RE) shadow = 0.0;
        }
        
        if (shadow > 0.0) {
            double dx = x - sx, dy = y - sy, dz = z - sz;
            double d_mag = sqrt(dx*dx + dy*dy + dz*dz);
            double au_scale = C_AU / rs_mag;
            au_scale *= au_scale;
            double coeff = -C_P_SR * cr * (A / m) * shadow * au_scale * 1e-3 / d_mag;
            ax += coeff * dx; ay += coeff * dy; az += coeff * dz;
        }
    }
}

__device__ __forceinline__ void rk4_step_device(
    double& x, double& y, double& z, double& vx, double& vy, double& vz,
    double dt, bool with_drag, double A, double m, double cd, double cr, double mjd0, int step_idx) {
    
    double mjd_start = (mjd0 > 0.0) ? mjd0 + (step_idx * dt) / 86400.0 : 0.0;
    double mjd_mid   = (mjd0 > 0.0) ? mjd_start + (dt / 2.0) / 86400.0 : 0.0;
    double mjd_end   = (mjd0 > 0.0) ? mjd_start + dt / 86400.0 : 0.0;

    auto compute_accel = [&](double _x, double _y, double _z, double _vx, double _vy, double _vz, 
                             double local_mjd, double& _ax, double& _ay, double& _az) {
        if (with_drag) accel_drag(_x, _y, _z, _vx, _vy, _vz, A, m, cd, cr, local_mjd, _ax, _ay, _az);
        else accel(_x, _y, _z, local_mjd, _ax, _ay, _az);
    };

    double a1x, a1y, a1z; compute_accel(x, y, z, vx, vy, vz, mjd_start, a1x, a1y, a1z);
    
    double x2 = x + 0.5 * dt * vx, y2 = y + 0.5 * dt * vy, z2 = z + 0.5 * dt * vz;
    double vx2 = vx + 0.5 * dt * a1x, vy2 = vy + 0.5 * dt * a1y, vz2 = vz + 0.5 * dt * a1z;
    double a2x, a2y, a2z; compute_accel(x2, y2, z2, vx2, vy2, vz2, mjd_mid, a2x, a2y, a2z);
    
    double x3 = x + 0.5 * dt * vx2, y3 = y + 0.5 * dt * vy2, z3 = z + 0.5 * dt * vz2;
    double vx3 = vx + 0.5 * dt * a2x, vy3 = vy + 0.5 * dt * a2y, vz3 = vz + 0.5 * dt * a2z;
    double a3x, a3y, a3z; compute_accel(x3, y3, z3, vx3, vy3, vz3, mjd_mid, a3x, a3y, a3z);
    
    double x4 = x + dt * vx3, y4 = y + dt * vy3, z4 = z + dt * vz3;
    double vx4 = vx + dt * a3x, vy4 = vy + dt * a3y, vz4 = vz + dt * a3z;
    double a4x, a4y, a4z; compute_accel(x4, y4, z4, vx4, vy4, vz4, mjd_end, a4x, a4y, a4z);
    
    double k = (dt / 6.0);
    x  += k * (vx + 2*vx2 + 2*vx3 + vx4);
    y  += k * (vy + 2*vy2 + 2*vy3 + vy4);
    z  += k * (vz + 2*vz2 + 2*vz3 + vz4);
    vx += k * (a1x + 2*a2x + 2*a3x + a4x);
    vy += k * (a1y + 2*a2y + 2*a3y + a4y);
    vz += k * (a1z + 2*a2z + 2*a3z + a4z);
}
