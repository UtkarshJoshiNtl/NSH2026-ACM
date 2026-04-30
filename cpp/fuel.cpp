#include "fuel.h"
#include <cmath>

FuelTracker::FuelTracker(double initial_fuel, double dry_mass)
    : fuel_kg(initial_fuel), dry_mass(dry_mass) {}

double FuelTracker::current_mass() const {
    return dry_mass + fuel_kg;
}

double FuelTracker::fuel_percentage() const {
    return (fuel_kg / INITIAL_FUEL) * 100.0;
}

bool FuelTracker::is_critical() const {
    return fuel_percentage() < 10.0;
}

bool FuelTracker::is_empty() const {
    return fuel_kg <= 0.0;
}

double FuelTracker::calculate_fuel_cost(const std::array<double, 3>& delta_v) const {
    double dv_mag = std::sqrt(delta_v[0]*delta_v[0] + delta_v[1]*delta_v[1] + delta_v[2]*delta_v[2]);
    return current_mass() * (1.0 - std::exp(-dv_mag / (ISP * G0)));
}

void FuelTracker::apply_burn(const std::array<double, 3>& delta_v) {
    double cost = calculate_fuel_cost(delta_v);
    fuel_kg -= cost;
    if (fuel_kg < 0.0) fuel_kg = 0.0;
}
