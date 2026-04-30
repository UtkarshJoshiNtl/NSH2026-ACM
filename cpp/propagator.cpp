#include "propagator.h"
#include "fuel.h"
#include "conjunction.h"
#include "maneuver.h"
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// US Standard Atmosphere 1976 — piecewise exponential density table (kg/m³)
// Each entry: {alt_base_km, scale_height_km, rho_base}
// Source: Vallado "Fundamentals of Astrodynamics", Table 8-4
// ---------------------------------------------------------------------------
struct AtmoEntry {
    double alt_base_km;
    double scale_height_km;
    double rho_base;
};

const AtmoEntry ATMO_TABLE[] = {
    {0,    8.44,  1.225e+0},
    {25,   6.49,  3.899e-2},
    {30,   6.75,  1.774e-2},
    {40,   7.58,  3.972e-3},
    {50,   8.55,  1.057e-3},
    {60,   7.71,  3.206e-4},
    {70,   6.55,  8.770e-5},
    {80,   5.79,  1.905e-5},
    {90,   5.57,  3.396e-6},
    {100,  5.90,  5.297e-7},
    {110,  7.17,  9.661e-8},
    {120,  9.59,  2.438e-8},
    {130, 12.20,  8.484e-9},
    {140, 15.50,  3.845e-9},
    {150, 19.30,  2.070e-9},
    {180, 26.00,  5.464e-10},
    {200, 26.00,  2.789e-10},
    {250, 38.50,  7.248e-11},
    {300, 51.00,  2.418e-11},
    {350, 59.50,  9.518e-12},
    {400, 67.60,  3.725e-12},
    {450, 76.00,  1.585e-12},
    {500, 84.00,  6.967e-13},
    {600, 105.0,  1.454e-13},
    {700, 130.0,  3.614e-14},
    {800, 180.0,  1.170e-14},
    {900, 268.0,  5.245e-15},
    {1000, 1e9,   3.019e-15}  // exosphere sentinel
};

const int ATMO_TABLE_SIZE = sizeof(ATMO_TABLE) / sizeof(AtmoEntry);

double atmospheric_density(double altitude_km) {
    if (altitude_km >= 1000.0) return 0.0;
    if (altitude_km < 0.0) altitude_km = 0.0;
    
    for (int i = 0; i < ATMO_TABLE_SIZE - 1; i++) {
        double h0 = ATMO_TABLE[i].alt_base_km;
        double H = ATMO_TABLE[i].scale_height_km;
        double rho0 = ATMO_TABLE[i].rho_base;
        double h1 = ATMO_TABLE[i + 1].alt_base_km;
        
        if (h0 <= altitude_km && altitude_km < h1) {
            return rho0 * std::exp(-(altitude_km - h0) / H);
        }
    }
    
    // Fallback to first entry
    double h0 = ATMO_TABLE[0].alt_base_km;
    double H = ATMO_TABLE[0].scale_height_km;
    double rho0 = ATMO_TABLE[0].rho_base;
    return rho0 * std::exp(-(altitude_km - h0) / H);
}

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

// ─── Acceleration with Drag ─────────────────────────────────────
std::array<double, 3> Propagator::acceleration_with_drag(
    const std::array<double, 3>& r,
    const std::array<double, 3>& v,
    double area,
    double mass,
    double cd) const {

    auto a_grav_j2 = acceleration(r);

    double x = r[0], y = r[1], z = r[2];
    double r_norm = std::sqrt(x*x + y*y + z*z);
    double h_km = r_norm - RE;

    if (h_km > 1000.0 || h_km < 0.0) {
        return a_grav_j2; // Exosphere, drag negligible
    }

    // Use US Standard Atmosphere 1976 table lookup
    double rho = atmospheric_density(h_km);

    // v_rel = v - omega_earth x r (in km/s)
    double v_rel_x = v[0] + OMEGA_EARTH * y;
    double v_rel_y = v[1] - OMEGA_EARTH * x;
    double v_rel_z = v[2];

    double v_rel_mag = std::sqrt(v_rel_x*v_rel_x + v_rel_y*v_rel_y + v_rel_z*v_rel_z);

    // a_drag = -0.5 * Cd * (A/m) * rho * v_rel_mag * v_rel
    // Note: A is m^2, m is kg, rho is kg/m^3, v is km/s.
    // Result drag acceleration needs to be in km/s^2.
    // v_rel_mag * v_rel is in (km/s)^2. 
    // rho * A / m has units (kg/m^3) * m^2 / kg = 1/m = 1000/km.
    // So 1/m * (km/s)^2 = (1000/km) * (km^2/s^2) = 1000 * km/s^2.
    double drag_factor = -0.5 * cd * (area / mass) * rho * v_rel_mag * 1000.0; 

    double a_drag_x = drag_factor * v_rel_x;
    double a_drag_y = drag_factor * v_rel_y;
    double a_drag_z = drag_factor * v_rel_z;

    return {a_grav_j2[0] + a_drag_x, a_grav_j2[1] + a_drag_y, a_grav_j2[2] + a_drag_z};
}

// ─── Full state derivatives ──────────────────────────────────────
StateVector Propagator::derivatives(const StateVector& s) const {
    std::array<double, 3> r = {s[0], s[1], s[2]};
    std::array<double, 3> a = acceleration(r);
    return {s[3], s[4], s[5], a[0], a[1], a[2]};
}

StateVector Propagator::derivatives_drag(const StateVector& s, double area, double mass, double cd) const {
    std::array<double, 3> r = {s[0], s[1], s[2]};
    std::array<double, 3> v = {s[3], s[4], s[5]};
    std::array<double, 3> a = acceleration_with_drag(r, v, area, mass, cd);
    return {s[3], s[4], s[5], a[0], a[1], a[2]};
}

// ─── Single RK4 step ────────────────────────────────────────────
StateVector Propagator::rk4_step(const StateVector& s, double dt) const {
    StateVector k1 = derivatives(s);
    StateVector s2; for(int i=0; i<6; i++) s2[i] = s[i] + 0.5 * dt * k1[i];
    StateVector k2 = derivatives(s2);
    StateVector s3; for(int i=0; i<6; i++) s3[i] = s[i] + 0.5 * dt * k2[i];
    StateVector k3 = derivatives(s3);
    StateVector s4; for(int i=0; i<6; i++) s4[i] = s[i] + dt * k3[i];
    StateVector k4 = derivatives(s4);
    StateVector result;
    for(int i=0; i<6; i++) result[i] = s[i] + (dt/6.0) * (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]);
    return result;
}

StateVector Propagator::rk4_step_drag(const StateVector& s, double dt, double area, double mass, double cd) const {
    StateVector k1 = derivatives_drag(s, area, mass, cd);
    StateVector s2; for(int i=0; i<6; i++) s2[i] = s[i] + 0.5 * dt * k1[i];
    StateVector k2 = derivatives_drag(s2, area, mass, cd);
    StateVector s3; for(int i=0; i<6; i++) s3[i] = s[i] + 0.5 * dt * k2[i];
    StateVector k3 = derivatives_drag(s3, area, mass, cd);
    StateVector s4; for(int i=0; i<6; i++) s4[i] = s[i] + dt * k3[i];
    StateVector k4 = derivatives_drag(s4, area, mass, cd);
    StateVector result;
    for(int i=0; i<6; i++) result[i] = s[i] + (dt/6.0) * (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]);
    return result;
}

// ─── Single propagation step ────────────────────────────────────
StateVector Propagator::propagate(const StateVector& state, double dt_seconds) const {
    return rk4_step(state, dt_seconds);
}

StateVector Propagator::propagate_with_drag(const StateVector& state, double dt_seconds, double area, double mass, double cd) const {
    return rk4_step_drag(state, dt_seconds, area, mass, cd);
}

// ─── Multi step propagation ─────────────────────────────────────
StateVector Propagator::propagate_steps(const StateVector& state, double total_seconds, double step_size) const {
    StateVector current = state;
    double remaining = total_seconds;
    while(remaining > 0.0) {
        double dt = std::min(step_size, remaining);
        current = rk4_step(current, dt);
        remaining -= dt;
    }
    return current;
}

StateVector Propagator::propagate_steps_drag(const StateVector& state, double total_seconds, double step_size, double area, double mass, double cd) const {
    StateVector current = state;
    double remaining = total_seconds;
    while(remaining > 0.0) {
        double dt = std::min(step_size, remaining);
        current = rk4_step_drag(current, dt, area, mass, cd);
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
             py::arg("step_size") = 10.0)
        .def("propagate_with_drag", &Propagator::propagate_with_drag,
             py::arg("state"), py::arg("dt_seconds"), py::arg("area"), py::arg("mass"), py::arg("cd"))
        .def("propagate_steps_drag", &Propagator::propagate_steps_drag,
             py::arg("state"), py::arg("total_seconds"), py::arg("step_size"), py::arg("area"), py::arg("mass"), py::arg("cd"));

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

