/*
 * cpp/conjunction.cpp — C++ Conjunction Detector
 * ===============================================
 * All-pairs screening with:
 *   - Incremental RK4 propagation (fixed in alpha branch)
 *   - Brent's method for sub-step TCA refinement
 *   - ADVISORY / WARNING / CRITICAL severity tiers
 *   - Chan's method Probability of Collision (Pc)
 */
#include "conjunction.h"
#include "propagator.h"
#include <cmath>
#include <algorithm>
#include <functional>

ConjunctionDetector::ConjunctionDetector() {}

// ── Brent's Method for 1D minimisation ───────────────────────────────────────
// Finds the x in [a,b] minimising f(x) to tolerance tol using Brent's method.
// See: Brent (1973) "Algorithms for Minimization without Derivatives"
static double brent_minimise(std::function<double(double)> f,
                              double a, double b, double tol = 0.01) {
    constexpr double GOLDEN = 0.3819660;
    double x = a + GOLDEN * (b - a);
    double w = x, v = x;
    double fx = f(x), fw = fx, fv = fx;
    double d = 0.0, e = 0.0;

    for (int iter = 0; iter < 50; ++iter) {
        double m = 0.5 * (a + b);
        double tol1 = tol * std::abs(x) + 1e-10;
        double tol2 = 2.0 * tol1;
        if (std::abs(x - m) <= tol2 - 0.5 * (b - a)) break;

        bool do_golden = true;
        if (std::abs(e) > tol1) {
            double r = (x - w) * (fx - fv);
            double q = (x - v) * (fx - fw);
            double p = (x - v) * q - (x - w) * r;
            q = 2.0 * (q - r);
            if (q > 0) p = -p; else q = -q;
            r = e; e = d;
            if (std::abs(p) < std::abs(0.5 * q * r) &&
                p > q * (a - x) && p < q * (b - x)) {
                d = p / q;
                double u = x + d;
                if ((u - a) < tol2 || (b - u) < tol2)
                    d = (x < m) ? tol1 : -tol1;
                do_golden = false;
            }
        }
        if (do_golden) {
            e = (x < m) ? b - x : a - x;
            d = GOLDEN * e;
        }
        double u = x + ((std::abs(d) >= tol1) ? d : (d > 0 ? tol1 : -tol1));
        double fu = f(u);
        if (fu <= fx) {
            if (u < x) b = x; else a = x;
            v = w; fv = fw; w = x; fw = fx; x = u; fx = fu;
        } else {
            if (u < x) a = u; else b = u;
            if (fu <= fw || w == x) { v = w; fv = fw; w = u; fw = fu; }
            else if (fu <= fv || v == x || v == w) { v = u; fv = fu; }
        }
    }
    return x;
}

// ── Chan's Pc: 2D Gaussian integral (Foster 1992 / Chan 1997 formulation) ────
// Uses the combined covariance at TCA modelled as a diagonal 2D ellipse in the
// miss-distance plane. sigma_r is the combined 1-sigma position uncertainty [km].
// Returns Pc using the series expansion for the circular encounter approximation.
static PcResult chan_pc(double miss_dist_km, double sigma_r_km,
                        double rel_speed_km_s, double hard_body_radius_km = 0.01) {
    PcResult r;
    r.sigma_pos_km = sigma_r_km;
    r.computed = false;
    if (sigma_r_km <= 0 || rel_speed_km_s <= 0) return r;

    // Encounter duration ~ hard-body passage time
    double x = miss_dist_km / sigma_r_km;
    // 2D Gaussian probability that relative position < HBR within the combined covariance
    // Simplified: Pc ≈ (HBR²/(2σ²)) * exp(-x²/2)  for x >> 1
    double sigma2 = sigma_r_km * sigma_r_km;
    double hbr2 = hard_body_radius_km * hard_body_radius_km;
    double pc = (hbr2 / (2.0 * sigma2)) * std::exp(-0.5 * x * x);
    r.pc = std::min(pc, 1.0);
    r.computed = true;
    return r;
}

std::vector<ConjunctionWarning> ConjunctionDetector::detect(
    const std::vector<StateVector>& sat_states,
    const std::vector<StateVector>& debris_states,
    double lookahead_s,
    double step_s,
    double tle_age_days) const {

    std::vector<ConjunctionWarning> warnings;
    Propagator prop;

    // Position uncertainty grows ~ sqrt(TLE age). Empirical 1-sigma at 1 day: 0.3 km
    double sigma_pos = 0.3 * std::sqrt(std::max(tle_age_days, 0.1));

    for (size_t i = 0; i < sat_states.size(); ++i) {
        for (size_t j = 0; j < debris_states.size(); ++j) {
            StateVector sat = sat_states[i];
            StateVector deb = debris_states[j];

            double min_distance = std::numeric_limits<double>::max();
            double tca_coarse   = 0.0;
            StateVector sat_tca = sat;
            StateVector deb_tca = deb;

            // ── Coarse sweep (incremental propagation) ────────────────────────
            for (double t = 0.0; t <= lookahead_s; t += step_s) {
                double dx = sat[0] - deb[0];
                double dy = sat[1] - deb[1];
                double dz = sat[2] - deb[2];
                double dist = std::sqrt(dx*dx + dy*dy + dz*dz);

                if (dist < min_distance) {
                    min_distance = dist;
                    tca_coarse   = t;
                    sat_tca      = sat;
                    deb_tca      = deb;
                }

                sat = prop.propagate(sat, step_s);
                deb = prop.propagate(deb, step_s);
            }

            // Quick cull — only Brent-refine if under ADVISORY threshold
            if (min_distance >= ADVISORY_DISTANCE) continue;

            // ── Brent refinement in [tca_coarse - step_s, tca_coarse + step_s] ──
            // We propagate fresh from sat_states[i] for the Brent objective function.
            StateVector s0 = sat_states[i];
            StateVector d0 = debris_states[j];

            double t_lo = std::max(0.0, tca_coarse - step_s);
            double t_hi = std::min(lookahead_s, tca_coarse + step_s);

            auto distance_at_t = [&](double t) -> double {
                // Propagate from the coarse bracket start to avoid full re-integration
                auto s = prop.propagate_steps(s0, t, step_s);
                auto d = prop.propagate_steps(d0, t, step_s);
                double dx = s[0]-d[0], dy = s[1]-d[1], dz = s[2]-d[2];
                return std::sqrt(dx*dx + dy*dy + dz*dz);
            };

            double tca_refined = brent_minimise(distance_at_t, t_lo, t_hi, 0.1);
            auto s_tca = prop.propagate_steps(s0, tca_refined, step_s);
            auto d_tca = prop.propagate_steps(d0, tca_refined, step_s);

            double dx_f = s_tca[0]-d_tca[0];
            double dy_f = s_tca[1]-d_tca[1];
            double dz_f = s_tca[2]-d_tca[2];
            double min_dist_refined = std::sqrt(dx_f*dx_f + dy_f*dy_f + dz_f*dz_f);

            // Use the better of coarse and Brent estimates
            double final_dist = std::min(min_distance, min_dist_refined);
            double final_tca  = (min_dist_refined < min_distance) ? tca_refined : tca_coarse;
            const auto& final_s = (min_dist_refined < min_distance) ? s_tca : sat_tca;
            const auto& final_d = (min_dist_refined < min_distance) ? d_tca : deb_tca;

            // ── Classify severity ─────────────────────────────────────────────
            std::string severity = "NONE";
            if      (final_dist < CRITICAL_DISTANCE)  severity = "CRITICAL";
            else if (final_dist < WARNING_DISTANCE)   severity = "WARNING";
            else if (final_dist < ADVISORY_DISTANCE)  severity = "ADVISORY";
            else continue;

            // ── Relative velocity at TCA ──────────────────────────────────────
            std::array<double, 3> rel_v = {
                final_s[3] - final_d[3],
                final_s[4] - final_d[4],
                final_s[5] - final_d[5]
            };
            double rel_speed = std::sqrt(rel_v[0]*rel_v[0] + rel_v[1]*rel_v[1] + rel_v[2]*rel_v[2]);

            ConjunctionWarning w;
            w.sat_id                   = static_cast<int>(i);
            w.debris_id                = static_cast<int>(j);
            w.current_distance         = final_dist;
            w.time_to_closest_approach = final_tca;
            w.severity                 = severity;
            w.relative_velocity        = rel_v;
            w.pc_result                = chan_pc(final_dist, sigma_pos, rel_speed);

            warnings.push_back(w);
        }
    }

    return warnings;
}
