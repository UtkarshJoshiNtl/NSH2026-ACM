#include "maneuver.h"
#include "fuel.h"
#include <cmath>

ManeuverCalculator::ManeuverCalculator() {}

ManeuverPlan ManeuverCalculator::calculate(
    const std::array<double, 6>& sat_state,
    const ConjunctionWarning& warning) {
    
    ManeuverPlan plan;
    
    // Simple evasion: burn perpendicular to relative velocity in the orbital plane
    auto rv = warning.relative_velocity;
    double rv_mag = std::sqrt(rv[0]*rv[0] + rv[1]*rv[1] + rv[2]*rv[2]);
    
    if (rv_mag < 1e-9) {
        return plan; // No relative velocity, no maneuver needed
    }
    
    // Calculate evasion direction (cross product with position vector)
    std::array<double, 3> r = {sat_state[0], sat_state[1], sat_state[2]};
    std::array<double, 3> cross = {
        rv[1]*r[2] - rv[2]*r[1],
        rv[2]*r[0] - rv[0]*r[2],
        rv[0]*r[1] - rv[1]*r[0]
    };
    
    double cross_mag = std::sqrt(cross[0]*cross[0] + cross[1]*cross[1] + cross[2]*cross[2]);
    
    if (cross_mag < 1e-9) {
        // Fallback: use radial direction
        cross = {r[0], r[1], r[2]};
        cross_mag = std::sqrt(cross[0]*cross[0] + cross[1]*cross[1] + cross[2]*cross[2]);
    }
    
    // Normalize and scale to max delta-v
    double evasion_mag = std::min(MAX_DV, warning.current_distance / warning.time_to_closest_approach * 0.5);
    plan.evasion_dv_eci = {
        (cross[0] / cross_mag) * evasion_mag,
        (cross[1] / cross_mag) * evasion_mag,
        (cross[2] / cross_mag) * evasion_mag
    };
    
    // Recovery burn is opposite of evasion
    plan.recovery_dv_eci = {
        -plan.evasion_dv_eci[0],
        -plan.evasion_dv_eci[1],
        -plan.evasion_dv_eci[2]
    };
    
    // Calculate fuel cost
    FuelTracker tracker;
    plan.fuel_cost_kg = tracker.calculate_fuel_cost(plan.evasion_dv_eci) +
                        tracker.calculate_fuel_cost(plan.recovery_dv_eci);
    
    // Schedule burn before TCA
    plan.burn_timing_offset_s = std::max(0.0, warning.time_to_closest_approach - COOLDOWN_S);
    
    return plan;
}
