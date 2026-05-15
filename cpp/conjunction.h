#pragma once
#include <string>
#include <vector>
#include <array>

#include "physics_constants.h"

struct ConjunctionWarning {
    int sat_id;
    int debris_id;
    double current_distance;
    double time_to_closest_approach;
    std::string severity;
    std::array<double, 3> relative_velocity;
    
    ConjunctionWarning() : sat_id(0), debris_id(0), current_distance(0.0),
                          time_to_closest_approach(0.0), severity("NONE"),
                          relative_velocity{0, 0, 0} {}
};

class ConjunctionDetector {
public:
    ConjunctionDetector();
    
    std::vector<ConjunctionWarning> detect(
        const std::vector<std::array<double, 6>>& sat_states,
        const std::vector<std::array<double, 6>>& debris_states,
        double lookahead_s = 86400.0,
        double step_s = 60.0
    ) const;
};
