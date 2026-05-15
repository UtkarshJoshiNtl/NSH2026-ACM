#pragma once
#include <array>

#include "physics_constants.h"

class FuelTracker {
public:
    FuelTracker(double initial_fuel = INITIAL_FUEL, double dry_mass = DRY_MASS);
    
    double current_mass() const;
    double fuel_percentage() const;
    bool is_critical() const;
    bool is_empty() const;
    double calculate_fuel_cost(const std::array<double, 3>& delta_v) const;
    void apply_burn(const std::array<double, 3>& delta_v);
    
    double fuel_kg;
    double dry_mass;
    double initial_fuel_kg;
};
