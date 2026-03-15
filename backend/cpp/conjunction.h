#pragma once
#include "propagator.h"   // StateVector, MU, RE, J2
#include <string>
#include <vector>

// ─── Conjunction Warning ─────────────────────────────────────────────────────
struct ConjunctionWarning {
    int    sat_id;
    int    debris_id;
    double current_distance;          // km — distance at closest approach found
    double time_to_closest_approach;  // seconds from epoch (0 = now)
    std::string severity;             // "CRITICAL" | "WARNING" | "WATCH"
    double relative_velocity;         // km/s — relative speed at closest approach
};

// ─── Conjunction Detector ─────────────────────────────────────────────────────
// Uses a 3-D KD-Tree built over debris positions so that satellite neighbourhood
// queries run in O(log N) instead of O(N) per satellite, making the total
// complexity O(S * T * log N) rather than O(S * T * N).
//
// Parameters
// ----------
//   sat_states    : list of satellite state vectors [x,y,z,vx,vy,vz] (km, km/s)
//   debris_states : list of debris  state vectors [x,y,z,vx,vy,vz] (km, km/s)
//   lookahead_s   : how far ahead to check, default 86400 s (24 h)
//   step_s        : propagation time step, default 60 s
//
// Returns
// -------
//   A list of ConjunctionWarning, one per (sat, debris) pair that breaches the
//   WATCH threshold (5 km) at any time in [0, lookahead_s].

class ConjunctionDetector {
public:
    // Severity thresholds (km)
    static constexpr double THRESHOLD_CRITICAL = 0.1;   // 100 m
    static constexpr double THRESHOLD_WARNING  = 1.0;   // 1 km
    static constexpr double THRESHOLD_WATCH    = 5.0;   // 5 km

    std::vector<ConjunctionWarning> detect(
        const std::vector<StateVector>& sat_states,
        const std::vector<StateVector>& debris_states,
        double lookahead_s = 86400.0,
        double step_s      = 60.0) const;

private:
    // ── Internal lightweight 3-D KD-Tree ────────────────────────────────────
    struct KDNode {
        double  pos[3];    // x, y, z
        int     idx;       // index into the debris array
        int     left  = -1;
        int     right = -1;
    };

    using KDTree = std::vector<KDNode>;

    // Build a KD-tree from a snapshot of 3-D positions.
    KDTree build_kdtree(
        const std::vector<StateVector>& states,
        std::vector<int>& indices,
        int start, int end, int depth) const;

    KDTree make_tree(const std::vector<StateVector>& states) const;

    // Query: collect all debris indices within `radius` km of `query[3]`.
    void radius_search(
        const KDTree& tree,
        int           node_idx,
        const double  query[3],
        double        radius,
        int           depth,
        std::vector<int>& results) const;

    // Single RK4 step (self-contained, no dependency on Propagator object)
    StateVector rk4(const StateVector& s, double dt) const;
    std::array<double,3> accel(const std::array<double,3>& r) const;
};
