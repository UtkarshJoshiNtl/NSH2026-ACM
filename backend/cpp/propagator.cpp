#include "propagator.h"
#include "fuel.h"
#include "conjunction.h"
#include "maneuver.h"
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

// ─── Gravity + J2 acceleration ──────────────────────────────────
std::array<double, 3> Propagator::acceleration(
    const std::array<double, 3>& r) const {

    double x = r[0], y = r[1], z = r[2];
    double r_norm = std::sqrt(x*x + y*y + z*z);
    double r2 = r_norm * r_norm;
    double r3 = r2 * r_norm;
    double r5 = r3 * r2;

    // Two body gravity
    double grav = -MU / r3;
    double ax = grav * x;
    double ay = grav * y;
    double az = grav * z;

    // J2 perturbation
    double j2_factor = (3.0/2.0) * J2 * MU * RE*RE / r5;
    double z2_r2 = (z * z) / r2;

    ax += j2_factor * x * (5.0 * z2_r2 - 1.0);
    ay += j2_factor * y * (5.0 * z2_r2 - 1.0);
    az += j2_factor * z * (5.0 * z2_r2 - 3.0);

    return {ax, ay, az};
}

// ─── Full state derivatives ──────────────────────────────────────
StateVector Propagator::derivatives(const StateVector& s) const {
    std::array<double, 3> r = {s[0], s[1], s[2]};
    std::array<double, 3> a = acceleration(r);

    // Derivative of position is velocity
    // Derivative of velocity is acceleration
    return {s[3], s[4], s[5],
            a[0], a[1], a[2]};
}

// ─── Single RK4 step ────────────────────────────────────────────
StateVector Propagator::rk4_step(
    const StateVector& s, double dt) const {

    StateVector k1 = derivatives(s);

    StateVector s2;
    for(int i = 0; i < 6; i++)
        s2[i] = s[i] + 0.5 * dt * k1[i];
    StateVector k2 = derivatives(s2);

    StateVector s3;
    for(int i = 0; i < 6; i++)
        s3[i] = s[i] + 0.5 * dt * k2[i];
    StateVector k3 = derivatives(s3);

    StateVector s4;
    for(int i = 0; i < 6; i++)
        s4[i] = s[i] + dt * k3[i];
    StateVector k4 = derivatives(s4);

    StateVector result;
    for(int i = 0; i < 6; i++)
        result[i] = s[i] + (dt/6.0) * 
                    (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]);

    return result;
}

// ─── Single propagation step ────────────────────────────────────
StateVector Propagator::propagate(
    const StateVector& state, double dt_seconds) const {
    return rk4_step(state, dt_seconds);
}

// ─── Multi step propagation ─────────────────────────────────────
StateVector Propagator::propagate_steps(
    const StateVector& state,
    double total_seconds,
    double step_size) const {

    StateVector current = state;
    double remaining = total_seconds;

    while(remaining > 0.0) {
        double dt = std::min(step_size, remaining);
        current = rk4_step(current, dt);
        remaining -= dt;
    }

    return current;
}

// ─── pybind11 bindings ───────────────────────────────────────────
PYBIND11_MODULE(physics_engine, m) {
    m.doc() = "ACM Physics Engine — Propagator, FuelTracker, ConjunctionDetector, ManeuverCalculator";

    // ── FuelTracker ─────────────────────────────────────────────
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

    // ── Propagator ──────────────────────────────────────────────
    py::class_<Propagator>(m, "Propagator")
        .def(py::init<>())
        .def("propagate",       &Propagator::propagate)
        .def("propagate_steps", &Propagator::propagate_steps,
             py::arg("state"),
             py::arg("total_seconds"),
             py::arg("step_size") = 10.0);

    // ── ConjunctionWarning ──────────────────────────────────────
    py::class_<ConjunctionWarning>(m, "ConjunctionWarning")
        .def(py::init<>())
        .def_readwrite("sat_id",                   &ConjunctionWarning::sat_id)
        .def_readwrite("debris_id",                &ConjunctionWarning::debris_id)
        .def_readwrite("current_distance",         &ConjunctionWarning::current_distance)
        .def_readwrite("time_to_closest_approach", &ConjunctionWarning::time_to_closest_approach)
        .def_readwrite("severity",                 &ConjunctionWarning::severity)
        .def_readwrite("relative_velocity",        &ConjunctionWarning::relative_velocity)
        .def("__repr__", [](const ConjunctionWarning& w){
            return "<ConjunctionWarning sat=" + std::to_string(w.sat_id)
                 + " debris=" + std::to_string(w.debris_id)
                 + " dist=" + std::to_string(w.current_distance)
                 + " km sev=" + w.severity + ">";
        });

    // ── ConjunctionDetector ─────────────────────────────────────
    py::class_<ConjunctionDetector>(m, "ConjunctionDetector")
        .def(py::init<>())
        .def("detect",
             &ConjunctionDetector::detect,
             py::arg("sat_states"),
             py::arg("debris_states"),
             py::arg("lookahead_s") = 86400.0,
             py::arg("step_s")      = 60.0,
             "Find all conjunction warnings within lookahead window.\n"
             "Returns list of ConjunctionWarning objects.");

    // ── ManeuverPlan ────────────────────────────────────────────
    py::class_<ManeuverPlan>(m, "ManeuverPlan")
        .def(py::init<>())
        .def_readwrite("evasion_dv_eci",       &ManeuverPlan::evasion_dv_eci)
        .def_readwrite("recovery_dv_eci",      &ManeuverPlan::recovery_dv_eci)
        .def_readwrite("fuel_cost_kg",         &ManeuverPlan::fuel_cost_kg)
        .def_readwrite("burn_timing_offset_s", &ManeuverPlan::burn_timing_offset_s)
        .def("__repr__", [](const ManeuverPlan& p){
            auto& e = p.evasion_dv_eci;
            auto& r = p.recovery_dv_eci;
            double e_mag = std::sqrt(e[0]*e[0]+e[1]*e[1]+e[2]*e[2]);
            double r_mag = std::sqrt(r[0]*r[0]+r[1]*r[1]+r[2]*r[2]);
            return "<ManeuverPlan evasion_dv=" + std::to_string(e_mag)
                 + " km/s recovery_dv=" + std::to_string(r_mag)
                 + " km/s fuel=" + std::to_string(p.fuel_cost_kg) + " kg>";
        });

    // ── ManeuverCalculator ──────────────────────────────────────
    py::class_<ManeuverCalculator>(m, "ManeuverCalculator")
        .def(py::init<>())
        .def("calculate",
             &ManeuverCalculator::calculate,
             py::arg("sat_state"),
             py::arg("warning"),
             "Calculate optimal paired evasion+recovery burns.\n"
             "Returns a ManeuverPlan with both burns in ECI frame.");
}

