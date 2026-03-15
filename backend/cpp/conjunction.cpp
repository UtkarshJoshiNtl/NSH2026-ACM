#include "conjunction.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>

// ─────────────────────────────────────────────────────────────────────────────
// Self-contained RK4 propagator (mirrors Propagator but has no object
// dependency, so conjunction.cpp remains decoupled from propagator.cpp).
// ─────────────────────────────────────────────────────────────────────────────
std::array<double,3> ConjunctionDetector::accel(
        const std::array<double,3>& r) const {
    double x = r[0], y = r[1], z = r[2];
    double r2    = x*x + y*y + z*z;
    double r_mag = std::sqrt(r2);
    double r3    = r2 * r_mag;
    double r5    = r3 * r2;

    double grav = -MU / r3;
    double ax = grav * x;
    double ay = grav * y;
    double az = grav * z;

    // J2 perturbation
    double j2f  = (1.5) * J2 * MU * RE * RE / r5;
    double z2r2 = (z * z) / r2;
    ax += j2f * x * (5.0 * z2r2 - 1.0);
    ay += j2f * y * (5.0 * z2r2 - 1.0);
    az += j2f * z * (5.0 * z2r2 - 3.0);
    return {ax, ay, az};
}

StateVector ConjunctionDetector::rk4(const StateVector& s, double dt) const {
    auto deriv = [&](const StateVector& st) -> StateVector {
        std::array<double,3> r = {st[0], st[1], st[2]};
        auto a = accel(r);
        return {st[3], st[4], st[5], a[0], a[1], a[2]};
    };

    StateVector k1 = deriv(s);
    StateVector s2; for(int i=0;i<6;i++) s2[i]=s[i]+0.5*dt*k1[i];
    StateVector k2 = deriv(s2);
    StateVector s3; for(int i=0;i<6;i++) s3[i]=s[i]+0.5*dt*k2[i];
    StateVector k3 = deriv(s3);
    StateVector s4; for(int i=0;i<6;i++) s4[i]=s[i]+    dt*k3[i];
    StateVector k4 = deriv(s4);

    StateVector out;
    for(int i=0;i<6;i++)
        out[i] = s[i] + (dt/6.0)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]);
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// KD-Tree construction
// Builds the tree in place using a flat vector of KDNode.
// The `indices` vector is a working array of debris indices sorted by position.
// ─────────────────────────────────────────────────────────────────────────────
ConjunctionDetector::KDTree ConjunctionDetector::make_tree(
        const std::vector<StateVector>& states) const {

    int n = static_cast<int>(states.size());
    if(n == 0) return {};

    // Build nodes
    KDTree nodes(n);
    std::vector<int> indices(n);
    std::iota(indices.begin(), indices.end(), 0);

    for(int i=0; i<n; i++){
        nodes[i].idx    = i;
        nodes[i].pos[0] = states[i][0];
        nodes[i].pos[1] = states[i][1];
        nodes[i].pos[2] = states[i][2];
    }

    // Recursive lambda to partition and store in tree order.
    // Returns the node index in `nodes` that is the root of this sub-tree.
    std::vector<int> order; order.reserve(n);
    std::function<int(int,int,int)> build = [&](int lo, int hi, int depth) -> int {
        if(lo >= hi) return -1;
        int axis = depth % 3;
        int mid  = (lo + hi) / 2;

        // Partial sort: median goes to position `mid`
        std::nth_element(indices.begin()+lo,
                         indices.begin()+mid,
                         indices.begin()+hi,
                         [&](int a, int b){
                             return nodes[a].pos[axis] < nodes[b].pos[axis];
                         });

        int node = indices[mid];
        int left_child  = build(lo,    mid,  depth+1);
        int right_child = build(mid+1, hi,   depth+1);
        nodes[node].left  = left_child;
        nodes[node].right = right_child;
        return node;
    };

    // root index (returned but we embed it as nodes[root_idx])
    int root = build(0, n, 0);
    // Reorder vector so node 0 is always the root for callers.
    // Simpler approach: store root index separately — expose via a tiny wrapper.
    // We do it the easy way: return the vector as-is and root is 'root'.
    // radius_search receives the root index explicitly.
    // Tag root into position 0 by swapping.
    if(root != 0){
        std::swap(nodes[0], nodes[root]);
        // Fix children pointers that reference 0 or root.
        for(auto& nd : nodes){
            if(nd.left  == root) nd.left  = 0;
            else if(nd.left  == 0) nd.left  = root;
            if(nd.right == root) nd.right = 0;
            else if(nd.right == 0) nd.right = root;
        }
    }
    return nodes;
}

// ─────────────────────────────────────────────────────────────────────────────
// KD-Tree radius search
// Recursively finds all debris indices within `radius` km of `query`.
// ─────────────────────────────────────────────────────────────────────────────
void ConjunctionDetector::radius_search(
        const KDTree& tree,
        int           node_idx,
        const double  query[3],
        double        radius,
        int           depth,
        std::vector<int>& results) const {

    if(node_idx < 0 || node_idx >= static_cast<int>(tree.size())) return;

    const KDNode& node = tree[node_idx];

    // Euclidean distance check
    double dx = query[0]-node.pos[0];
    double dy = query[1]-node.pos[1];
    double dz = query[2]-node.pos[2];
    double dist = std::sqrt(dx*dx + dy*dy + dz*dz);
    if(dist <= radius) results.push_back(node.idx);

    // Splitting plane distance
    int axis = depth % 3;
    double plane_dist = query[axis] - node.pos[axis];

    // Visit nearer child first
    int near  = (plane_dist <= 0) ? node.left  : node.right;
    int far   = (plane_dist <= 0) ? node.right : node.left;

    radius_search(tree, near, query, radius, depth+1, results);

    // Only visit far child if the splitting plane is within radius
    if(std::abs(plane_dist) <= radius)
        radius_search(tree, far, query, radius, depth+1, results);
}

// ─────────────────────────────────────────────────────────────────────────────
// Main detection function
// ─────────────────────────────────────────────────────────────────────────────
std::vector<ConjunctionWarning> ConjunctionDetector::detect(
        const std::vector<StateVector>& sat_states,
        const std::vector<StateVector>& debris_states,
        double lookahead_s,
        double step_s) const {

    int num_sats   = static_cast<int>(sat_states.size());
    int num_debris = static_cast<int>(debris_states.size());
    if(num_sats == 0 || num_debris == 0) return {};

    // ── Propagate debris forward at each time step, build KD-tree snapshots ──
    // For each time step we need debris positions; build KD-tree per step.
    // Satellite propagation is independent and cheap.

    double clamp_step = std::max(step_s, 1.0);  // sanity: minimum 1 s
    int num_steps = static_cast<int>(std::ceil(lookahead_s / clamp_step)) + 1;

    // Track per-(sat,debris) minimum distance and time of closest approach.
    // Use a flat array: best_dist[sat][debris].
    // To avoid O(S*D) allocation for 50*10000 = 500k entries we use a map
    // approach: only allocate when a pair is found to be within WATCH range.

    // Structure to accumulate best encounter per pair
    struct Encounter {
        double min_dist    = std::numeric_limits<double>::max();
        double tca         = 0.0;  // time of min distance (seconds)
        double rel_vel     = 0.0;  // relative speed at TCA
    };

    // Use a map keyed by (sat_id * max_debris + debris_id)
    // For 50 * 10000 = 500k, a flat vector is fine.
    std::vector<Encounter> best(static_cast<size_t>(num_sats) * num_debris);

    // Propagate states step-by-step
    std::vector<StateVector> sat_cur   = sat_states;
    std::vector<StateVector> deb_cur   = debris_states;

    for(int step = 0; step < num_steps; step++){
        double t = step * clamp_step;

        // Build KD-tree over current debris positions
        KDTree tree = make_tree(deb_cur);
        if(tree.empty()) break;

        // For each satellite, query tree within WATCH radius
        for(int s = 0; s < num_sats; s++){
            double q[3] = { sat_cur[s][0], sat_cur[s][1], sat_cur[s][2] };

            std::vector<int> candidates;
            candidates.reserve(32);
            radius_search(tree, 0, q, THRESHOLD_WATCH, 0, candidates);

            for(int d : candidates){
                double dx = sat_cur[s][0] - deb_cur[d][0];
                double dy = sat_cur[s][1] - deb_cur[d][1];
                double dz = sat_cur[s][2] - deb_cur[d][2];
                double dist = std::sqrt(dx*dx + dy*dy + dz*dz);

                // Relative velocity
                double dvx = sat_cur[s][3] - deb_cur[d][3];
                double dvy = sat_cur[s][4] - deb_cur[d][4];
                double dvz = sat_cur[s][5] - deb_cur[d][5];
                double rel_v = std::sqrt(dvx*dvx + dvy*dvy + dvz*dvz);

                size_t key = static_cast<size_t>(s) * num_debris + d;
                if(dist < best[key].min_dist){
                    best[key].min_dist = dist;
                    best[key].tca      = t;
                    best[key].rel_vel  = rel_v;
                }
            }
        }

        // Propagate one step forward (skip last iteration)
        if(step < num_steps - 1){
            double dt = std::min(clamp_step, lookahead_s - t);
            if(dt <= 0) break;
            for(int s=0; s<num_sats;   s++) sat_cur[s] = rk4(sat_cur[s], dt);
            for(int d=0; d<num_debris; d++) deb_cur[d] = rk4(deb_cur[d], dt);
        }
    }

    // ── Collect results ──────────────────────────────────────────────────────
    std::vector<ConjunctionWarning> warnings;

    for(int s=0; s<num_sats; s++){
        for(int d=0; d<num_debris; d++){
            size_t key = static_cast<size_t>(s) * num_debris + d;
            double md = best[key].min_dist;
            if(md >= THRESHOLD_WATCH) continue;  // never got close enough

            ConjunctionWarning w;
            w.sat_id                  = s;
            w.debris_id               = d;
            w.current_distance        = md;
            w.time_to_closest_approach= best[key].tca;
            w.relative_velocity       = best[key].rel_vel;

            if(md < THRESHOLD_CRITICAL)      w.severity = "CRITICAL";
            else if(md < THRESHOLD_WARNING)  w.severity = "WARNING";
            else                             w.severity = "WATCH";

            warnings.push_back(w);
        }
    }

    return warnings;
}
