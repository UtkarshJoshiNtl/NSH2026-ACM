#include "maneuver.h"
#include "physics_constants.h"
#include <cmath>

static double fuel_cost_kg(double dv_mag_km_s) {
    return INITIAL_FUEL * (1.0 - std::exp(-dv_mag_km_s / (ISP * G0_KM)));
}

ManeuverPlan ManeuverCalculator::calculate(
    const std::array<double, 6>& sat_state,
    const ConjunctionWarning& warning) {

    ManeuverPlan plan;
    auto rv = warning.relative_velocity;
    double rv_mag = std::sqrt(rv[0]*rv[0] + rv[1]*rv[1] + rv[2]*rv[2]);

    if (rv_mag < 1e-9) {
        return plan;
    }

    std::array<double, 3> r = {sat_state[0], sat_state[1], sat_state[2]};
    std::array<double, 3> dir = {
        rv[1]*r[2] - rv[2]*r[1],
        rv[2]*r[0] - rv[0]*r[2],
        rv[0]*r[1] - rv[1]*r[0]
    };

    double dir_mag = std::sqrt(dir[0]*dir[0] + dir[1]*dir[1] + dir[2]*dir[2]);
    if (dir_mag < 1e-9) {
        dir = {r[0], r[1], r[2]};
        dir_mag = std::sqrt(dir[0]*dir[0] + dir[1]*dir[1] + dir[2]*dir[2]);
    }

    double evasion_mag = std::min(MAX_DV, warning.current_distance / warning.time_to_closest_approach * 0.5);
    plan.evasion_dv_eci = {
        (dir[0] / dir_mag) * evasion_mag,
        (dir[1] / dir_mag) * evasion_mag,
        (dir[2] / dir_mag) * evasion_mag
    };
    plan.recovery_dv_eci = {
        -plan.evasion_dv_eci[0],
        -plan.evasion_dv_eci[1],
        -plan.evasion_dv_eci[2]
    };

    plan.fuel_cost_kg = fuel_cost_kg(evasion_mag) + fuel_cost_kg(evasion_mag);
    plan.burn_timing_offset_s = std::max(0.0, warning.time_to_closest_approach - COOLDOWN_S);

    return plan;
}
