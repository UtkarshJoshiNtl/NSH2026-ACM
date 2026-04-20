#pragma once
#include <array>

const double ISP = 300.0;
const double G0 = 0.00980665;
const double DRY_MASS = 500.0;
const double INITIAL_FUEL = 50.0;
const double MAX_DV = 0.015;
const double COOLDOWN_S = 600.0;

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
};
