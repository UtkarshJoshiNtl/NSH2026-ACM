/*
 * cpp/propagator.cpp — C++ Orbital Propagator
 * ============================================
 * RK4 integrator with J2+J3+J4 gravity harmonics and US Standard
 * Atmosphere 1976 drag (Earth-rotation-corrected relative velocity).
 * Includes batch propagation over N satellites using OpenMP (if available).
 */

#include "propagator.h"
#include "fuel.h"
#include "conjunction.h"
#include "maneuver.h"
#include "cuda_bridge.h"
#include <cmath>
#include <algorithm>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

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
    return ATMO_TABLE[0].rho_base * std::exp(-alt_km / ATMO_TABLE[0].scale_height_km);
}

// ── Gravity: J2 + J3 + J4 ────────────────────────────────────────────────────
std::array<double,3> Propagator::acceleration(const std::array<double,3>& r) const {
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
    double z_r   = z / rm;
    double j3f   = 2.5 * J3 * MU * RE * RE * RE / r7;
    ax += j3f * x * (7.0 * z2_r2 * z_r - 3.0 * z_r);
    ay += j3f * y * (7.0 * z2_r2 * z_r - 3.0 * z_r);
    az += j3f * (7.0 * z2_r2 * z_r * z - 6.0 * z2_r2 + (3.0 / 5.0));

    // J4
    double z4_r4 = z2_r2 * z2_r2;
    double j4f   = (5.0/8.0) * J4 * MU * RE * RE * RE * RE / r7;
    ax += j4f * x * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4);
    ay += j4f * y * (3.0 - 42.0 * z2_r2 + 63.0 * z4_r4);
    az += j4f * z * (15.0 - 70.0 * z2_r2 + 63.0 * z4_r4);

    return {ax, ay, az};
}

// ── Gravity + Drag ────────────────────────────────────────────────────────────
std::array<double,3> Propagator::acceleration_with_drag(
        const std::array<double,3>& r, const std::array<double,3>& v,
        double area, double mass, double cd) const {

    auto a = acceleration(r);
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
    return a;
}

// ── Derivatives ───────────────────────────────────────────────────────────────
StateVector Propagator::derivatives(const StateVector& s) const {
    auto a = acceleration({s[0], s[1], s[2]});
    return {s[3], s[4], s[5], a[0], a[1], a[2]};
}
StateVector Propagator::derivatives_drag(const StateVector& s,
                                          double area, double mass, double cd) const {
    auto a = acceleration_with_drag({s[0],s[1],s[2]}, {s[3],s[4],s[5]}, area, mass, cd);
    return {s[3], s[4], s[5], a[0], a[1], a[2]};
}

// ── RK4 step ──────────────────────────────────────────────────────────────────
StateVector Propagator::rk4_step(const StateVector& s, double dt) const {
    auto k1 = derivatives(s);
    StateVector s2; for (int i=0;i<6;i++) s2[i] = s[i] + 0.5*dt*k1[i];
    auto k2 = derivatives(s2);
    StateVector s3; for (int i=0;i<6;i++) s3[i] = s[i] + 0.5*dt*k2[i];
    auto k3 = derivatives(s3);
    StateVector s4; for (int i=0;i<6;i++) s4[i] = s[i] + dt*k3[i];
    auto k4 = derivatives(s4);
    StateVector res;
    for (int i=0;i<6;i++) res[i] = s[i] + (dt/6.0)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]);
    return res;
}
StateVector Propagator::rk4_step_drag(const StateVector& s, double dt,
                                       double area, double mass, double cd) const {
    auto k1 = derivatives_drag(s, area, mass, cd);
    StateVector s2; for (int i=0;i<6;i++) s2[i] = s[i] + 0.5*dt*k1[i];
    auto k2 = derivatives_drag(s2, area, mass, cd);
    StateVector s3; for (int i=0;i<6;i++) s3[i] = s[i] + 0.5*dt*k2[i];
    auto k3 = derivatives_drag(s3, area, mass, cd);
    StateVector s4; for (int i=0;i<6;i++) s4[i] = s[i] + dt*k3[i];
    auto k4 = derivatives_drag(s4, area, mass, cd);
    StateVector res;
    for (int i=0;i<6;i++) res[i] = s[i] + (dt/6.0)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]);
    return res;
}

// ── Single-step public API ────────────────────────────────────────────────────
StateVector Propagator::propagate(const StateVector& s, double dt) const {
    return rk4_step(s, dt);
}
StateVector Propagator::propagate_with_drag(const StateVector& s, double dt,
                                             double area, double mass, double cd) const {
    return rk4_step_drag(s, dt, area, mass, cd);
}

// ── Multi-step public API ─────────────────────────────────────────────────────
StateVector Propagator::propagate_steps(const StateVector& s,
                                         double total, double step) const {
    StateVector cur = s;
    for (double rem = total; rem > 0.0; rem -= step)
        cur = rk4_step(cur, std::min(step, rem));
    return cur;
}
StateVector Propagator::propagate_steps_drag(const StateVector& s,
                                              double total, double step,
                                              double area, double mass, double cd) const {
    StateVector cur = s;
    for (double rem = total; rem > 0.0; rem -= step)
        cur = rk4_step_drag(cur, std::min(step, rem), area, mass, cd);
    return cur;
}

// ── Batch propagation (flat double array, modified in-place) ─────────────────
void Propagator::propagate_batch(std::vector<double>& states, int n,
                                  double dt, int steps) const {
#ifdef _OPENMP
    #pragma omp parallel for schedule(dynamic, 16)
#endif
    for (int i = 0; i < n; ++i) {
        StateVector s;
        for (int k = 0; k < 6; ++k) s[k] = states[i*6 + k];
        for (int step = 0; step < steps; ++step)
            s = rk4_step(s, dt);
        for (int k = 0; k < 6; ++k) states[i*6 + k] = s[k];
    }
}

void Propagator::propagate_batch_drag(std::vector<double>& states, int n,
                                       double dt, int steps,
                                       double area, double mass, double cd) const {
#ifdef _OPENMP
    #pragma omp parallel for schedule(dynamic, 16)
#endif
    for (int i = 0; i < n; ++i) {
        StateVector s;
        for (int k = 0; k < 6; ++k) s[k] = states[i*6 + k];
        for (int step = 0; step < steps; ++step)
            s = rk4_step_drag(s, dt, area, mass, cd);
        for (int k = 0; k < 6; ++k) states[i*6 + k] = s[k];
    }
}

// ── Python-friendly batch wrappers ────────────────────────────────────────────
std::vector<StateVector> Propagator::batch_propagate_steps(
        const std::vector<StateVector>& states, double dt, int steps) const {
    std::vector<StateVector> out = states;
    int n = (int)out.size();
    std::vector<double> flat(n * 6);
    for (int i = 0; i < n; ++i)
        for (int k = 0; k < 6; ++k) flat[i*6+k] = out[i][k];
    propagate_batch(flat, n, dt, steps);
    for (int i = 0; i < n; ++i)
        for (int k = 0; k < 6; ++k) out[i][k] = flat[i*6+k];
    return out;
}

std::vector<StateVector> Propagator::batch_propagate_steps_drag(
        const std::vector<StateVector>& states, double dt, int steps,
        double area, double mass, double cd) const {
    std::vector<StateVector> out = states;
    int n = (int)out.size();
    std::vector<double> flat(n * 6);
    for (int i = 0; i < n; ++i)
        for (int k = 0; k < 6; ++k) flat[i*6+k] = out[i][k];
    propagate_batch_drag(flat, n, dt, steps, area, mass, cd);
    for (int i = 0; i < n; ++i)
        for (int k = 0; k < 6; ++k) out[i][k] = flat[i*6+k];
    return out;
}

// ── pybind11 bindings ─────────────────────────────────────────────────────────
PYBIND11_MODULE(physics_engine, m) {
    m.doc() = "Astrosis Physics Engine — J2/J3/J4 propagator, fuel, conjunction, maneuver";

    // FuelTracker
    py::class_<FuelTracker>(m, "FuelTracker")
        .def(py::init<double, double>(),
             py::arg("initial_fuel") = INITIAL_FUEL,
             py::arg("dry_mass")     = DRY_MASS)
        .def("current_mass",        &FuelTracker::current_mass)
        .def("fuel_percentage",     &FuelTracker::fuel_percentage)
        .def("is_critical",         &FuelTracker::is_critical)
        .def("is_empty",            &FuelTracker::is_empty)
        .def("calculate_fuel_cost", &FuelTracker::calculate_fuel_cost)
        .def("apply_burn",          &FuelTracker::apply_burn)
        .def_readwrite("fuel_kg",   &FuelTracker::fuel_kg)
        .def_readwrite("dry_mass",  &FuelTracker::dry_mass);

    // Propagator
    py::class_<Propagator>(m, "Propagator")
        .def(py::init<>())
        // Single-step
        .def("propagate",       &Propagator::propagate)
        .def("propagate_with_drag", &Propagator::propagate_with_drag,
             py::arg("state"), py::arg("dt_seconds"),
             py::arg("area"), py::arg("mass"), py::arg("cd"))
        // Multi-step (returns final state)
        .def("propagate_steps", &Propagator::propagate_steps,
             py::arg("state"), py::arg("total_seconds"), py::arg("step_size") = 10.0)
        .def("propagate_steps_drag", &Propagator::propagate_steps_drag,
             py::arg("state"), py::arg("total_seconds"), py::arg("step_size"),
             py::arg("area"), py::arg("mass"), py::arg("cd"))
        // Batch propagation (N satellites × steps) — CPU parallel
        .def("batch_propagate_steps", &Propagator::batch_propagate_steps,
             py::arg("states"), py::arg("dt_seconds"), py::arg("steps"),
             py::call_guard<py::gil_scoped_release>(),
             "Propagate N satellites for `steps` RK4 steps. Releases GIL for parallelism.")
        .def("batch_propagate_steps_drag", &Propagator::batch_propagate_steps_drag,
             py::arg("states"), py::arg("dt_seconds"), py::arg("steps"),
             py::arg("area"), py::arg("mass"), py::arg("cd"),
             py::call_guard<py::gil_scoped_release>());

    // ConjunctionWarning
    py::class_<ConjunctionWarning>(m, "ConjunctionWarning")
        .def(py::init<>())
        .def_readwrite("sat_id",                   &ConjunctionWarning::sat_id)
        .def_readwrite("debris_id",                &ConjunctionWarning::debris_id)
        .def_readwrite("current_distance",         &ConjunctionWarning::current_distance)
        .def_readwrite("time_to_closest_approach", &ConjunctionWarning::time_to_closest_approach)
        .def_readwrite("severity",                 &ConjunctionWarning::severity)
        .def_readwrite("relative_velocity",        &ConjunctionWarning::relative_velocity)
        .def("__repr__", [](const ConjunctionWarning& w) {
            return "<ConjunctionWarning sat=" + std::to_string(w.sat_id)
                 + " debris=" + std::to_string(w.debris_id)
                 + " dist=" + std::to_string(w.current_distance)
                 + " km sev=" + w.severity + ">";
        });

    // ConjunctionDetector
    py::class_<ConjunctionDetector>(m, "ConjunctionDetector")
        .def(py::init<>())
        .def("detect", &ConjunctionDetector::detect,
             py::arg("sat_states"), py::arg("debris_states"),
             py::arg("lookahead_s") = 86400.0, py::arg("step_s") = 60.0,
             py::call_guard<py::gil_scoped_release>());

    // ManeuverPlan
    py::class_<ManeuverPlan>(m, "ManeuverPlan")
        .def(py::init<>())
        .def_readwrite("evasion_dv_eci",       &ManeuverPlan::evasion_dv_eci)
        .def_readwrite("recovery_dv_eci",      &ManeuverPlan::recovery_dv_eci)
        .def_readwrite("fuel_cost_kg",         &ManeuverPlan::fuel_cost_kg)
        .def_readwrite("burn_timing_offset_s", &ManeuverPlan::burn_timing_offset_s)
        .def("__repr__", [](const ManeuverPlan& p) {
            auto& e = p.evasion_dv_eci; auto& r = p.recovery_dv_eci;
            double em = std::sqrt(e[0]*e[0]+e[1]*e[1]+e[2]*e[2]);
            double rm = std::sqrt(r[0]*r[0]+r[1]*r[1]+r[2]*r[2]);
            return "<ManeuverPlan evasion=" + std::to_string(em)
                 + " km/s recovery=" + std::to_string(rm)
                 + " km/s fuel=" + std::to_string(p.fuel_cost_kg) + " kg>";
        });

    // ManeuverCalculator
    py::class_<ManeuverCalculator>(m, "ManeuverCalculator")
        .def(py::init<>())
        .def("calculate", &ManeuverCalculator::calculate,
             py::arg("sat_state"), py::arg("warning"));

    // ── CUDA GPU Acceleration (Optional) ─────────────────────────────────────
    m.def("cuda_available", &cuda_available, "Returns true if an NVIDIA GPU is found.");
    
#ifdef USE_CUDA
    m.def("cuda_device_count", &cuda_device_count);
    m.def("cuda_print_device_info", &cuda_print_device_info);

    m.def("cuda_propagate_batch", [](py::list states, double dt, int steps) {
        int n = (int)states.size();
        std::vector<double> flat(n * 6);
        for(int i=0; i<n; i++) {
            py::list s = states[i];
            for(int k=0; k<6; k++) flat[i*6+k] = s[k].cast<double>();
        }
        
        {
            py::gil_scoped_release release;
            cuda_propagate_batch(flat.data(), n, dt, steps);
        }

        py::list out;
        for(int i=0; i<n; i++) {
            py::list s;
            for(int k=0; k<6; k++) s.append(flat[i*6+k]);
            out.append(s);
        }
        return out;
    }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"));

    m.def("cuda_propagate_batch_drag", [](py::list states, double dt, int steps, 
                                          double area, double mass, double cd) {
        int n = (int)states.size();
        std::vector<double> flat(n * 6);
        for(int i=0; i<n; i++) {
            py::list s = states[i];
            for(int k=0; k<6; k++) flat[i*6+k] = s[k].cast<double>();
        }

        {
            py::gil_scoped_release release;
            cuda_propagate_batch_drag(flat.data(), n, dt, steps, area, mass, cd);
        }

        py::list out;
        for(int i=0; i<n; i++) {
            py::list s;
            for(int k=0; k<6; k++) s.append(flat[i*6+k]);
            out.append(s);
        }
        return out;
    }, py::arg("states"), py::arg("dt_seconds"), py::arg("steps"),
       py::arg("area"), py::arg("mass"), py::arg("cd"));

    m.def("cuda_detect_conjunctions", &cuda_detect_conjunctions,
          py::arg("sat_states"), py::arg("debris_states"),
          py::arg("lookahead_s") = 86400.0, py::arg("step_s") = 60.0,
          py::call_guard<py::gil_scoped_release>());
#endif
}
