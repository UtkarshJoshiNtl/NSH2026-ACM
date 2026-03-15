#include "fuel.h"
#include <cmath>
#include <stdexcept>
#include <pybind11/pybind11.h>

namespace py = pybind11;

// ─── Constructor ────────────────────────────────────────────────
FuelTracker::FuelTracker(double initial_fuel, double dry_mass)
    : fuel_kg(initial_fuel), dry_mass(dry_mass) {}

// ─── Current total mass ─────────────────────────────────────────
double FuelTracker::current_mass() const {
    return dry_mass + fuel_kg;
}

// ─── Fuel as percentage ─────────────────────────────────────────
double FuelTracker::fuel_percentage() const {
    return fuel_kg / INITIAL_FUEL;
}

// ─── Is fuel critically low ─────────────────────────────────────
bool FuelTracker::is_critical() const {
    return fuel_percentage() <= FUEL_CRITICAL_PCT;
}

// ─── Is completely empty ────────────────────────────────────────
bool FuelTracker::is_empty() const {
    return fuel_kg <= 0.0;
}

// ─── Calculate fuel cost without applying ───────────────────────
double FuelTracker::calculate_fuel_cost(double delta_v) const {
    if (delta_v <= 0.0) return 0.0;
    double mass = current_mass();
    double exponent = -delta_v / (ISP * G0);
    double fuel_consumed = mass * (1.0 - std::exp(exponent));
    return fuel_consumed;
}

// ─── Apply burn and deduct fuel ─────────────────────────────────
double FuelTracker::apply_burn(double delta_v) {
    // Reject invalid burns
    if (delta_v <= 0.0)        return -1.0;
    if (delta_v > MAX_DELTA_V) return -1.0;
    if (is_empty())            return -1.0;

    double fuel_consumed = calculate_fuel_cost(delta_v);

    // Prevent going below zero
    if (fuel_consumed > fuel_kg) {
        fuel_consumed = fuel_kg;
        fuel_kg = 0.0;
    } else {
        fuel_kg -= fuel_consumed;
    }

    return fuel_consumed;
}

// ─── pybind11 — expose to Python ────────────────────────────────
PYBIND11_MODULE(physics_engine, m) {
    m.doc() = "ACM Physics Engine";

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
}
