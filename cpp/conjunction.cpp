#include "conjunction.h"
#include "propagator.h"
#include <cmath>
#include <algorithm>

ConjunctionDetector::ConjunctionDetector() {}

std::vector<ConjunctionWarning> ConjunctionDetector::detect(
    const std::vector<std::array<double, 6>>& sat_states,
    const std::vector<std::array<double, 6>>& debris_states,
    double lookahead_s,
    double step_s) const {
    
    std::vector<ConjunctionWarning> warnings;
    Propagator prop;
    
    for (size_t i = 0; i < sat_states.size(); ++i) {
        for (size_t j = 0; j < debris_states.size(); ++j) {
            auto sat_state = sat_states[i];
            auto deb_state = debris_states[j];
            
            double min_distance = 1e9;
            double tca = 0.0;
            
            // Propagate forward to find closest approach
            for (double t = 0.0; t <= lookahead_s; t += step_s) {
                auto sat = prop.propagate(sat_state, t);
                auto deb = prop.propagate(deb_state, t);
                
                double dx = sat[0] - deb[0];
                double dy = sat[1] - deb[1];
                double dz = sat[2] - deb[2];
                double dist = std::sqrt(dx*dx + dy*dy + dz*dz);
                
                if (dist < min_distance) {
                    min_distance = dist;
                    tca = t;
                }
            }
            
            // Classify severity
            if (min_distance < CRITICAL_DISTANCE) {
                ConjunctionWarning w;
                w.sat_id = i;
                w.debris_id = j;
                w.current_distance = min_distance;
                w.time_to_closest_approach = tca;
                w.severity = "CRITICAL";
                
                // Calculate relative velocity
                auto sat = prop.propagate(sat_state, tca);
                auto deb = prop.propagate(deb_state, tca);
                w.relative_velocity = {
                    sat[3] - deb[3],
                    sat[4] - deb[4],
                    sat[5] - deb[5]
                };
                
                warnings.push_back(w);
            } else if (min_distance < WARNING_DISTANCE) {
                ConjunctionWarning w;
                w.sat_id = i;
                w.debris_id = j;
                w.current_distance = min_distance;
                w.time_to_closest_approach = tca;
                w.severity = "WARNING";
                
                auto sat = prop.propagate(sat_state, tca);
                auto deb = prop.propagate(deb_state, tca);
                w.relative_velocity = {
                    sat[3] - deb[3],
                    sat[4] - deb[4],
                    sat[5] - deb[5]
                };
                
                warnings.push_back(w);
            }
        }
    }
    
    return warnings;
}
