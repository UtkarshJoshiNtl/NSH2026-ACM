#pragma once
#include <array>
#include "conjunction.h"

struct ManeuverPlan {
    std::array<double, 3> evasion_dv_eci;
    std::array<double, 3> recovery_dv_eci;
    double fuel_cost_kg;
    double burn_timing_offset_s;
    
    ManeuverPlan() : evasion_dv_eci{0, 0, 0}, recovery_dv_eci{0, 0, 0},
                      fuel_cost_kg(0.0), burn_timing_offset_s(0.0) {}
};

class ManeuverCalculator {
public:
    ManeuverCalculator();
    
    ManeuverPlan calculate(
        const std::array<double, 6>& sat_state,
        const ConjunctionWarning& warning
    );
};
