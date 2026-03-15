#include "fuel.h"
#include <cmath>

FuelTracker::FuelTracker(double initial_fuel, double dry_mass)
    : fuel_kg(initial_fuel), dry_mass(dry_mass) {}

double FuelTracker::current_mass() const {
    return dry_mass + fuel_kg;
}

double FuelTracker::fuel_percentage() const {
    return fuel_kg / INITIAL_FUEL;
}

bool FuelTracker::is_critical() const {
    return fuel_percentage() <= FUEL_CRITICAL_PCT;
}

bool FuelTracker::is_empty() const {
    return fuel_kg <= 0.0;
}

double FuelTracker::calculate_fuel_cost(double delta_v) const {
    if (delta_v <= 0.0) return 0.0;
    double mass = current_mass();
    double exponent = -delta_v / (ISP * G0);
    return mass * (1.0 - std::exp(exponent));
}

double FuelTracker::apply_burn(double delta_v) {
    if (delta_v <= 0.0)        return -1.0;
    if (delta_v > MAX_DELTA_V) return -1.0;
    if (is_empty())            return -1.0;

    double fuel_consumed = calculate_fuel_cost(delta_v);

    if (fuel_consumed > fuel_kg) {
        fuel_consumed = fuel_kg;
        fuel_kg = 0.0;
    } else {
        fuel_kg -= fuel_consumed;
    }

    return fuel_consumed;
}
