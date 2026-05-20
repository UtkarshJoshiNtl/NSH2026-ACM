/*
 * cpp/propagator.cpp — C++ Orbital Propagator
 * ============================================
 * RK4 integrator with J2+J3+J4 gravity harmonics and US Standard
 * Atmosphere 1976 drag (Earth-rotation-corrected relative velocity).
 * Includes batch propagation over N satellites using OpenMP (if available).
 */

#include "propagator.h"
#include "conjunction.h"
#include "cuda_bridge.h"
#include <cmath>
#include <algorithm>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

// ── US Standard Atmosphere 1976 table ────────────────────────────────────────
struct AtmoEntry { double alt_base_km, scale_height_km, rho_base; };

static constexpr AtmoEntry ATMO_TABLE[] = {
    {0,    8.44,  1.225e+0}, {25,   6.49,  3.899e-2}, {30,   6.75,  1.774e-2},
    {40,   7.58,  3.972e-3}, {50,   8.55,  1.057e-3}, {60,   7.71,  3.206e-4},
    {70,   6.55,  8.770e-5}, {80,   5.79,  1.905e-5}, {90,   5.57,  3.396e-6},
    {100,  5.90,  5.297e-7}, {110,  7.17,  9.661e-8}, {120,  9.59,  2.438e-8},
    {130, 12.20,  8.484e-9}, {140, 15.50,  3.845e-9}, {150, 19.30,  2.070e-9},
    {180, 26.00,  5.464e-10},{200, 26.00,  2.789e-10},{250, 38.50,  7.248e-11},
    {300, 51.00,  2.418e-11},{350, 59.50,  9.518e-12},{400, 67.60,  3.725e-12},
    {450, 76.00,  1.585e-12},{500, 84.00,  6.967e-13},{600, 105.0,  1.454e-13},
    {700, 130.0,  3.614e-14},{800, 180.0,  1.170e-14},{900, 268.0,  5.245e-15},
    {1000, 1e9,   3.019e-15}
};
static constexpr int ATMO_N = sizeof(ATMO_TABLE) / sizeof(AtmoEntry);

static double atmospheric_density(double alt_km) {
    if (alt_km >= 1000.0) return 0.0;
    if (alt_km < 0.0)     alt_km = 0.0;
    for (int i = 0; i < ATMO_N - 1; ++i) {
        if (ATMO_TABLE[i].alt_base_km <= alt_km && alt_km < ATMO_TABLE[i+1].alt_base_km)
            return ATMO_TABLE[i].rho_base * std::exp(-(alt_km - ATMO_TABLE[i].alt_base_km)
                                                        / ATMO_TABLE[i].scale_height_km);
    }
    return 0.0;
}

// ── Ephemeris ────────────────────────────────────────────────────────────────
static constexpr double DEG2RAD = M_PI / 180.0;

static std::array<double, 3> sun_position_eci(double mjd) {
    double d = mjd - 51544.5;
    double g_rad = (357.529 + 0.98560028 * d) * DEG2RAD;
    double q = 280.459 + 0.98564736 * d;
    double L_rad = (q + 1.915 * std::sin(g_rad) + 0.020 * std::sin(2 * g_rad)) * DEG2RAD;
    double R_au = 1.00014 - 0.01671 * std::cos(g_rad) - 0.00014 * std::cos(2 * g_rad);
    double R_km = R_au * AU_CONST; // Note: Need to make sure AU_CONST is defined
    double e_rad = (23.439 - 0.00000036 * d) * DEG2RAD;
    return {
        R_km * std::cos(L_rad),
        R_km * std::cos(e_rad) * std::sin(L_rad),
        R_km * std::sin(e_rad) * std::sin(L_rad)
    };
}

static std::array<double, 3> moon_position_eci(double mjd) {
    double d = mjd - 51544.5;
    double L_rad = (218.316 + 13.176396 * d) * DEG2RAD;
    double M_rad = (134.963 + 13.064993 * d) * DEG2RAD;
    double F_rad = (93.272 + 13.229350 * d) * DEG2RAD;
    double l_ecl = L_rad + (6.289 * std::sin(M_rad)) * DEG2RAD;
    double b_ecl = (5.128 * std::sin(F_rad)) * DEG2RAD;
    double dist = 385001.0 - 20905.0 * std::cos(M_rad);
    double e_rad = (23.439 - 0.00000036 * d) * DEG2RAD;
    
    double x_ecl = dist * std::cos(b_ecl) * std::cos(l_ecl);
    double y_ecl = dist * std::cos(b_ecl) * std::sin(l_ecl);
    double z_ecl = dist * std::sin(b_ecl);
    
    return {
        x_ecl,
        y_ecl * std::cos(e_rad) - z_ecl * std::sin(e_rad),
        y_ecl * std::sin(e_rad) + z_ecl * std::cos(e_rad)
    };
}

static void add_third_body(double& ax, double& ay, double& az, const std::array<double,3>& r, const std::array<double,3>& rb, double mu_body) {
    double dx = rb[0] - r[0], dy = rb[1] - r[1], dz = rb[2] - r[2];
    double d3 = std::pow(dx*dx + dy*dy + dz*dz, 1.5);
    double rb3 = std::pow(rb[0]*rb[0] + rb[1]*rb[1] + rb[2]*rb[2], 1.5);
    ax += mu_body * (dx/d3 - rb[0]/rb3);
    ay += mu_body * (dy/d3 - rb[1]/rb3);
    az += mu_body * (dz/d3 - rb[2]/rb3);
}

// ── Gravity: J2 + J3 + J4 + Lunisolar ────────────────────────────────────────
std::array<double,3> Propagator::acceleration(const std::array<double,3>& r, double mjd) const {
    double x = r[0], y = r[1], z = r[2];
    double r2  = x*x + y*y + z*z;
    double rm  = std::sqrt(r2);
    double r3  = r2 * rm;
    double r5  = r3 * r2;
    double r7  = r5 * r2;

    double ax = -MU * x / r3;
    double ay = -MU * y / r3;
    double az = -MU * z / r3;

    // J2
    double z2_r2 = z * z / r2;
    double j2f   = 1.5 * J2 * MU * RE * RE / r5;
    ax += j2f * x * (5.0 * z2_r2 - 1.0);
    ay += j2f * y * (5.0 * z2_r2 - 1.0);
    az += j2f * z * (5.0 * z2_r2 - 3.0);

    // J3
    double j3f   = -2.5 * J3 * MU * RE * RE * RE / r7;
    ax += j3f * x * (7.0 * z2_r2 * z - 3.0 * z);
    ay += j3f * y * (7.0 * z2_r2 * z - 3.0 * z);
    az += j3f * (7.0 * z2_r2 * z * z - 6.0 * z * z + 0.6 * r2);

    // J4
    double z4_r4 = z2_r2 * z2_r2;
    double j4f   = (5.0/8.0) * J4 * MU * RE * RE * RE * RE / r7;
    ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4);
    ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4);
    az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4);

    if (mjd > 0.0) {
        add_third_body(ax, ay, az, r, sun_position_eci(mjd), MU_SUN);
        add_third_body(ax, ay, az, r, moon_position_eci(mjd), MU_MOON);
    }

    return {ax, ay, az};
}

// ── Gravity + Drag + SRP ──────────────────────────────────────────────────────
std::array<double,3> Propagator::acceleration_with_drag(
        const std::array<double,3>& r, const std::array<double,3>& v,
        double area, double mass, double cd, double cr, double mjd) const {

    auto a = acceleration(r, mjd);
    double x = r[0], y = r[1];
    double rm = std::sqrt(x*x + y*y + r[2]*r[2]);
    double alt = rm - RE;

    if (alt >= 0.0 && alt < 1000.0) {
        double rho = atmospheric_density(alt);
        // Earth-rotation-corrected relative velocity
        double vr_x = v[0] + OMEGA_EARTH * y;
        double vr_y = v[1] - OMEGA_EARTH * x;
        double vr_z = v[2];
        double vr_mag = std::sqrt(vr_x*vr_x + vr_y*vr_y + vr_z*vr_z);
        if (vr_mag > 0.0) {
            // a_drag = -0.5 * Cd * (A/m) * rho * |v_rel| * v_rel  [km/s²]
            double df = -0.5 * cd * (area / mass) * rho * vr_mag * 1000.0;
            a[0] += df * vr_x;
            a[1] += df * vr_y;
            a[2] += df * vr_z;
        }
    }

    if (mjd > 0.0 && area > 0.0 && mass > 0.0) {
        auto r_sun = sun_position_eci(mjd);
        double rs_mag = std::sqrt(r_sun[0]*r_sun[0] + r_sun[1]*r_sun[1] + r_sun[2]*r_sun[2]);
        double dot_prod = r[0]*r_sun[0] + r[1]*r_sun[1] + r[2]*r_sun[2];
        
        double shadow = 1.0;
        if (dot_prod < 0) {
            double proj = dot_prod / rs_mag;
            double r_mag = std::sqrt(r[0]*r[0] + r[1]*r[1] + r[2]*r[2]);
            double d_perp2 = std::max(0.0, r_mag*r_mag - proj*proj);
            if (std::sqrt(d_perp2) < RE) shadow = 0.0;
        }

        if (shadow > 0.0) {
            double dx = r[0] - r_sun[0];
            double dy = r[1] - r_sun[1];
            double dz = r[2] - r_sun[2];
            double au_scale = (AU_CONST / rs_mag);
            au_scale *= au_scale;
            double coeff = P_SR * cr * (area / mass) * shadow * au_scale * 1e-3;
            a[0] += coeff * dx;
            a[1] += coeff * dy;
            a[2] += coeff * dz;
        }
    }

    return a;
}

// ── Derivatives ───────────────────────────────────────────────────────────────
StateVector Propagator::derivatives(const StateVector& s, double mjd) const {
    std::array<double, 3> r = {s[0], s[1], s[2]};
    std::array<double, 3> a = acceleration(r, mjd);
    StateVector ret;
    ret[0] = s[3]; ret[1] = s[4]; ret[2] = s[5];
    ret[3] = a[0]; ret[4] = a[1]; ret[5] = a[2];
    return ret;
}
StateVector Propagator::derivatives_drag(const StateVector& s,
                                         double area, double mass, double cd, double cr, double mjd) const {
    std::array<double, 3> r = {s[0], s[1], s[2]};
    std::array<double, 3> v = {s[3], s[4], s[5]};
    std::array<double, 3> a = acceleration_with_drag(r, v, area, mass, cd, cr, mjd);
    StateVector ret;
    ret[0] = s[3]; ret[1] = s[4]; ret[2] = s[5];
    ret[3] = a[0]; ret[4] = a[1]; ret[5] = a[2];
    return ret;
}

// ── RK4 step ──────────────────────────────────────────────────────────────────
StateVector Propagator::rk4_step(const StateVector& s, double dt, double mjd0, int current_step) const {
    double mjd_start = (mjd0 > 0.0) ? mjd0 + (current_step * dt) / 86400.0 : 0.0;
    double mjd_mid   = (mjd0 > 0.0) ? mjd_start + (dt / 2.0) / 86400.0 : 0.0;
    double mjd_end   = (mjd0 > 0.0) ? mjd_start + dt / 86400.0 : 0.0;

    auto k1 = derivatives(s, mjd_start);
    StateVector s2; for (int i=0;i<6;i++) s2[i] = s[i] + 0.5*dt*k1[i];
    auto k2 = derivatives(s2, mjd_mid);
    StateVector s3; for (int i=0;i<6;i++) s3[i] = s[i] + 0.5*dt*k2[i];
    auto k3 = derivatives(s3, mjd_mid);
    StateVector s4; for (int i=0;i<6;i++) s4[i] = s[i] + dt*k3[i];
    auto k4 = derivatives(s4, mjd_end);
    StateVector res;
    for (int i=0;i<6;i++) res[i] = s[i] + (dt/6.0)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]);
    return res;
}
StateVector Propagator::rk4_step_drag(const StateVector& s, double dt,
                                       double area, double mass, double cd, double cr, double mjd0, int current_step) const {
    double mjd_start = (mjd0 > 0.0) ? mjd0 + (current_step * dt) / 86400.0 : 0.0;
    double mjd_mid   = (mjd0 > 0.0) ? mjd_start + (dt / 2.0) / 86400.0 : 0.0;
    double mjd_end   = (mjd0 > 0.0) ? mjd_start + dt / 86400.0 : 0.0;

    auto k1 = derivatives_drag(s, area, mass, cd, cr, mjd_start);
    StateVector s2; for (int i=0;i<6;i++) s2[i] = s[i] + 0.5*dt*k1[i];
    auto k2 = derivatives_drag(s2, area, mass, cd, cr, mjd_mid);
    StateVector s3; for (int i=0;i<6;i++) s3[i] = s[i] + 0.5*dt*k2[i];
    auto k3 = derivatives_drag(s3, area, mass, cd, cr, mjd_mid);
    StateVector s4; for (int i=0;i<6;i++) s4[i] = s[i] + dt*k3[i];
    auto k4 = derivatives_drag(s4, area, mass, cd, cr, mjd_end);
    StateVector res;
    for (int i=0;i<6;i++) res[i] = s[i] + (dt/6.0)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]);
    return res;
}

// ── Single-step public API ────────────────────────────────────────────────────
StateVector Propagator::propagate(const StateVector& s, double dt, double mjd0) const {
    return rk4_step(s, dt, mjd0, 0);
}
StateVector Propagator::propagate_with_drag(const StateVector& s, double dt,
                                             double area, double mass, double cd, double cr, double mjd0) const {
    return rk4_step_drag(s, dt, area, mass, cd, cr, mjd0, 0);
}

// ── Multi-step public API ─────────────────────────────────────────────────────
StateVector Propagator::propagate_steps(const StateVector& s,
                                        double total_seconds,
                                        double step_size,
                                        double area, double mass, double cd, double cr,
                                        bool with_drag, double mjd0) const {
    StateVector curr = s;
    double rem = total_seconds;
    int steps_taken = 0;
    while (rem > 0) {
        double dt = std::min(step_size, rem);
        if (with_drag) {
            curr = rk4_step_drag(curr, dt, area, mass, cd, cr, mjd0, steps_taken);
        } else {
            curr = rk4_step(curr, dt, mjd0, steps_taken);
        }
        rem -= dt;
        steps_taken++;
    }
    return curr;
}

// ── Batch API (Raw Pointers + OpenMP) ───────────────────────────────────────
void Propagator::propagate_batch(double* states_inout, int n,
                                 double dt_seconds, int steps, double mjd0) const {
    #pragma omp parallel for
    for (int i = 0; i < n; ++i) {
        StateVector s;
        std::memcpy(s.raw(), &states_inout[i * 6], 6 * sizeof(double));
        for (int step = 0; step < steps; ++step) {
            s = rk4_step(s, dt_seconds, mjd0, step);
        }
        std::memcpy(&states_inout[i * 6], s.raw(), 6 * sizeof(double));
    }
}

void Propagator::propagate_batch_drag(double* states_inout, int n,
                                      double dt_seconds, int steps,
                                      double area, double mass, double cd, double cr, double mjd0) const {
    #pragma omp parallel for
    for (int i = 0; i < n; ++i) {
        StateVector s;
        std::memcpy(s.raw(), &states_inout[i * 6], 6 * sizeof(double));
        for (int step = 0; step < steps; ++step) {
            s = rk4_step_drag(s, dt_seconds, area, mass, cd, cr, mjd0, step);
        }
        std::memcpy(&states_inout[i * 6], s.raw(), 6 * sizeof(double));
    }
}

// ── Python-Friendly Batch API (std::vector) ─────────────────────────────────
std::vector<StateVector> Propagator::batch_propagate_steps(
        const std::vector<StateVector>& states,
        double dt_seconds, int steps, double mjd0) const {
    std::vector<StateVector> res = states;
    #pragma omp parallel for
    for (size_t i = 0; i < res.size(); ++i) {
        for (int step = 0; step < steps; ++step) {
            res[i] = rk4_step(res[i], dt_seconds, mjd0, step);
        }
    }
    return res;
}

std::vector<StateVector> Propagator::batch_propagate_steps_drag(
        const std::vector<StateVector>& states,
        double dt_seconds, int steps,
        double area, double mass, double cd, double cr, double mjd0) const {
    std::vector<StateVector> res = states;
    #pragma omp parallel for
    for (size_t i = 0; i < res.size(); ++i) {
        for (int step = 0; step < steps; ++step) {
            res[i] = rk4_step_drag(res[i], dt_seconds, area, mass, cd, cr, mjd0, step);
        }
    }
    return res;
}

void Propagator::batch_propagate_full_history(
        const double* initial_states, int n,
        double dt_seconds, int steps, 
        double area, double mass, double cd, double cr, bool with_drag,
        double mjd0,
        double* output_history) const {
    #pragma omp parallel for
    for (int i = 0; i < n; ++i) {
        StateVector s;
        std::memcpy(s.raw(), &initial_states[i * 6], 6 * sizeof(double));
        std::memcpy(&output_history[0 * (n * 6) + i * 6], s.raw(), 6 * sizeof(double));

        for (int step = 0; step < steps; ++step) {
            if (with_drag) {
                s = rk4_step_drag(s, dt_seconds, area, mass, cd, cr, mjd0, step);
            } else {
                s = rk4_step(s, dt_seconds, mjd0, step);
            }
            std::memcpy(&output_history[(step + 1) * (n * 6) + i * 6], s.raw(), 6 * sizeof(double));
        }
    }
}

// ── pybind11 bindings ─────────────────────────────────────────────────────────
PYBIND11_MODULE(physics_engine, m) {
    m.doc() = "Astrosis Physics Engine — J2/J3/J4 propagator, conjunction analysis";

    // Propagator
    py::class_<Propagator>(m, "Propagator")
        .def(py::init<>())
        .def("propagate",
            [](const Propagator& p, const std::array<double,6>& s, double dt, double mjd0) {
                StateVector sv; for (int i=0;i<6;i++) sv[i]=s[i];
                auto res = p.propagate(sv, dt, mjd0);
                std::array<double,6> out; for (int i=0;i<6;i++) out[i]=res[i];
                return out;
            }, py::arg("state"), py::arg("dt_seconds"), py::arg("mjd0") = 0.0)
        .def("propagate_with_drag",
            [](const Propagator& p, const std::array<double,6>& s, double dt, double area, double mass, double cd, double cr, double mjd0) {
                StateVector sv; for (int i=0;i<6;i++) sv[i]=s[i];
                auto res = p.propagate_with_drag(sv, dt, area, mass, cd, cr, mjd0);
                std::array<double,6> out; for (int i=0;i<6;i++) out[i]=res[i];
                return out;
            }, py::arg("state"), py::arg("dt_seconds"), py::arg("area"), py::arg("mass"), py::arg("cd"), py::arg("cr") = 1.5, py::arg("mjd0") = 0.0)
        .def("propagate_steps",
            [](const Propagator& p, const std::array<double,6>& s, double total, double step, double area, double mass, double cd, double cr, bool with_drag, double mjd0) {
                StateVector sv; for (int i=0;i<6;i++) sv[i]=s[i];
                auto res = p.propagate_steps(sv, total, step, area, mass, cd, cr, with_drag, mjd0);
                std::array<double,6> out; for (int i=0;i<6;i++) out[i]=res[i];
                return out;
            }, py::arg("state"), py::arg("total_seconds"), py::arg("step_size"), py::arg("area") = 0.0, py::arg("mass") = 1.0, py::arg("cd") = 2.2, py::arg("cr") = 1.5, py::arg("with_drag") = false, py::arg("mjd0") = 0.0)
        .def("batch_propagate_steps", [](const Propagator& self, py::array_t<double> states, double dt, int steps, double mjd0) {
            auto buf = states.request();
            if (buf.ndim != 2 || buf.shape[1] != 6) throw std::runtime_error("States must be (N, 6)");
            int n = (int)buf.shape[0];
            double* ptr = (double*)buf.ptr;
            {
                py::gil_scoped_release release;
                self.propagate_batch(ptr, n, dt, steps, mjd0);
            }
            return states;
        }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"), py::arg("mjd0") = 0.0)
        .def("batch_propagate_steps_drag",
            [](const Propagator& p, py::array_t<double> states, double dt, int steps, double area, double mass, double cd, double cr, double mjd0) {
                py::buffer_info buf = states.request();
                int n = buf.shape[0];
                py::array_t<double> out({n, 6});
                std::memcpy(out.mutable_data(), buf.ptr, n * 6 * sizeof(double));
                
                py::gil_scoped_release release;
                p.propagate_batch_drag(static_cast<double*>(out.mutable_data()), n, dt, steps, area, mass, cd, cr, mjd0);
                return out;
            }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"), py::arg("area"), py::arg("mass"), py::arg("cd"), py::arg("cr") = 1.5, py::arg("mjd0") = 0.0)
        .def("batch_propagate_full_history", [](const Propagator& self, py::array_t<double> states, double dt, int steps, double area, double mass, double cd, double cr, bool with_drag, double mjd0) {
            auto buf = states.request();
            int n = (int)buf.shape[0];
            double* in_ptr = (double*)buf.ptr;
            
            py::array_t<double> history({steps + 1, n, 6});
            auto h_buf = history.request();
            double* out_ptr = (double*)h_buf.ptr;

            {
                py::gil_scoped_release release;
                self.batch_propagate_full_history(in_ptr, n, dt, steps, area, mass, cd, cr, with_drag, mjd0, out_ptr);
            }
            return history;
        }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"), 
           py::arg("area") = 0.0, py::arg("mass") = 1.0, py::arg("cd") = 2.2, py::arg("cr") = 1.5, py::arg("with_drag") = false, py::arg("mjd0") = 0.0);

    // ConjunctionWarning
    py::class_<ConjunctionWarning>(m, "ConjunctionWarning")
        .def(py::init<>())
        .def_readwrite("sat_id",                   &ConjunctionWarning::sat_id)
        .def_readwrite("debris_id",                &ConjunctionWarning::debris_id)
        .def_readwrite("current_distance",         &ConjunctionWarning::current_distance)
        .def_readwrite("time_to_closest_approach", &ConjunctionWarning::time_to_closest_approach)
        .def_readwrite("severity",                 &ConjunctionWarning::severity)
        .def_readwrite("relative_velocity",        &ConjunctionWarning::relative_velocity)
        .def_property_readonly("pc", [](const ConjunctionWarning& w){ return w.pc_result.pc; })
        .def_property_readonly("pc_sigma_km", [](const ConjunctionWarning& w){ return w.pc_result.sigma_pos_km; })
        .def("__repr__", [](const ConjunctionWarning& w) {
            return "<ConjunctionWarning sat=" + std::to_string(w.sat_id)
                 + " debris=" + std::to_string(w.debris_id)
                 + " dist=" + std::to_string(w.current_distance)
                 + " km sev=" + w.severity
                 + " Pc=" + std::to_string(w.pc_result.pc) + ">";
        });

    // ConjunctionDetector
    py::class_<ConjunctionDetector>(m, "ConjunctionDetector")
        .def(py::init<>())
        .def("detect", [](const ConjunctionDetector& self, py::array_t<double> sats, py::array_t<double> debs,
                          double lookahead, double step, double tle_age) {
            auto b_sat = sats.request(); auto b_deb = debs.request();
            int ns = (int)b_sat.shape[0], nd = (int)b_deb.shape[0];
            std::vector<StateVector> vs(ns), vd(nd);
            for(int i=0; i<ns; i++) std::memcpy(vs[i].raw(), (double*)b_sat.ptr + i*6, 6*sizeof(double));
            for(int i=0; i<nd; i++) std::memcpy(vd[i].raw(), (double*)b_deb.ptr + i*6, 6*sizeof(double));
            {
                py::gil_scoped_release release;
                return self.detect(vs, vd, lookahead, step, tle_age);
            }
        }, py::arg("sat_states"), py::arg("debris_states"),
           py::arg("lookahead_s") = 86400.0, py::arg("step_s") = 60.0,
            py::arg("tle_age_days") = 1.0);

    // ── CUDA GPU Acceleration (Optional) ─────────────────────────────────────
    m.def("cuda_available", &cuda_available, "Returns true if an NVIDIA GPU is found.");
    
#ifdef USE_CUDA
    m.def("cuda_device_count", &cuda_device_count);
    m.def("cuda_print_device_info", &cuda_print_device_info);

    m.def("cuda_propagate_batch", [](py::array_t<double> states, double dt, int steps, double mjd0) {
        auto buf = states.request();
        if (buf.ndim != 2 || buf.shape[1] != 6) throw std::runtime_error("States must be (N, 6)");
        int n = (int)buf.shape[0];
        // If the array is contiguous, we can pass the pointer directly
        double* ptr = (double*)buf.ptr;
        {
            py::gil_scoped_release release;
            cuda_propagate_batch(ptr, n, dt, steps, mjd0);
        }
        return states; // Return the same array since it was modified in-place
    }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"), py::arg("mjd0") = 0.0);

    m.def("cuda_propagate_batch_drag", [](py::array_t<double> states, double dt, int steps, 
                                          double area, double mass, double cd, double cr, double mjd0) {
        auto buf = states.request();
        int n = (int)buf.shape[0];
        double* ptr = (double*)buf.ptr;
        {
            py::gil_scoped_release release;
            cuda_propagate_batch_drag(ptr, n, dt, steps, area, mass, cd, cr, mjd0);
        }
        return states;
    }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"),
       py::arg("area"), py::arg("mass"), py::arg("cd"), py::arg("cr") = 1.5, py::arg("mjd0") = 0.0);

    m.def("cuda_propagate_full_history", [](py::array_t<double> states, double dt, int steps, double area, double mass, double cd, double cr, bool with_drag, double mjd0) {
        auto buf = states.request();
        int n = (int)buf.shape[0];
        double* in_ptr = (double*)buf.ptr;
        
        // We must allocate a new array for history
        py::array_t<double> history({steps + 1, n, 6});
        auto h_buf = history.request();
        double* out_ptr = (double*)h_buf.ptr;

        {
            py::gil_scoped_release release;
            cuda_propagate_full_history(in_ptr, n, dt, steps, area, mass, cd, cr, with_drag, mjd0, out_ptr);
        }
        return history;
    }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"), py::arg("area") = 0.0, py::arg("mass") = 1.0, py::arg("cd") = 2.2, py::arg("cr") = 1.5, py::arg("with_drag") = false, py::arg("mjd0") = 0.0);

    m.def("cuda_detect_conjunctions", [](py::array_t<double> sats, py::array_t<double> debs, 
                                        double lookahead, double step, double mjd0) {
        auto b_sat = sats.request(); auto b_deb = debs.request();
        int ns = (int)b_sat.shape[0], nd = (int)b_deb.shape[0];
        {
            py::gil_scoped_release release;
            return cuda_detect_conjunctions((double*)b_sat.ptr, ns, (double*)b_deb.ptr, nd, lookahead, step, mjd0);
        }
    }, py::arg("sat_states"), py::arg("debris_states"),
       py::arg("lookahead_s") = 86400.0, py::arg("step_s") = 60.0, py::arg("mjd0") = 0.0);

    m.def("cuda_monte_carlo_pc", [](py::array_t<double> sat_samples, py::array_t<double> deb_samples,
                                    double dt, int steps, double threshold, double mjd0) {
        auto b_sat = sat_samples.request(); auto b_deb = deb_samples.request();
        int n = (int)b_sat.shape[0];
        {
            py::gil_scoped_release release;
            return cuda_monte_carlo_pc((double*)b_sat.ptr, (double*)b_deb.ptr, n, dt, steps, threshold, mjd0);
        }
    }, py::arg("sat_samples"), py::arg("deb_samples"), 
       py::arg("dt"), py::arg("steps"), py::arg("threshold_km"), py::arg("mjd0") = 0.0);
#endif
}
