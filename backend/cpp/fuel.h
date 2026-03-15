#pragma once

// Physical constants
const double ISP = 300.0;
const double G0  = 0.00980665;  // km/s²
const double DRY_MASS          = 500.0;   // kg
const double INITIAL_FUEL      = 50.0;    // kg
const double INITIAL_WET_MASS  = 550.0;   // kg
const double MAX_DELTA_V       = 0.015;   // km/s
const double FUEL_CRITICAL_PCT = 0.05;    // 5%

// Fuel tracker class
class FuelTracker {
public:
    double fuel_kg;
    double dry_mass;

    // Constructor — sets up a fresh satellite
    FuelTracker(double initial_fuel = INITIAL_FUEL,
                double dry_mass    = DRY_MASS);

    // Returns current total mass (dry + fuel)
    double current_mass() const;

    // Returns fuel as percentage of initial
    double fuel_percentage() const;

    // Returns true if fuel is critically low
    bool is_critical() const;

    // Returns true if completely out of fuel
    bool is_empty() const;

    // Calculates fuel consumed for a given delta_v
    // Does NOT apply the burn yet
    double calculate_fuel_cost(double delta_v_magnitude) const;

    // Applies a burn — deducts fuel, returns actual fuel consumed
    // Returns -1 if burn is invalid
    double apply_burn(double delta_v_magnitude);
};
