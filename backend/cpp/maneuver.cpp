#include "maneuver.h"
#include "fuel.h"       // MAX_DELTA_V, ISP, G0, DRY_MASS, INITIAL_FUEL
#include <cmath>
#include <algorithm>

// ─── Vector helpers ───────────────────────────────────────────────────────────
std::array<double,3> ManeuverCalculator::cross(
        const std::array<double,3>& a,
        const std::array<double,3>& b) const {
    return {
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    };
}

std::array<double,3> ManeuverCalculator::normalise(
        const std::array<double,3>& v) const {
    double mag = std::sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
    if(mag < 1e-12) return {0.0, 0.0, 0.0};
    return {v[0]/mag, v[1]/mag, v[2]/mag};
}

std::array<double,3> ManeuverCalculator::scale(
        const std::array<double,3>& unit, double mag) const {
    return {unit[0]*mag, unit[1]*mag, unit[2]*mag};
}

// ─── Tsiolkovsky fuel cost ────────────────────────────────────────────────────
// m_prop = m_wet * (1 - exp(-|ΔV| / (Isp * g0)))
// We use DRY_MASS + INITIAL_FUEL as wet mass (full tank assumption).
double ManeuverCalculator::fuel_mass(double dv) const {
    double wet = DRY_MASS + INITIAL_FUEL;
    return wet * (1.0 - std::exp(-dv / (ISP * G0)));
}

// ─── RTN frame construction ───────────────────────────────────────────────────
// R̂ = r / |r|              (radial, outward)
// N̂ = (r × v) / |r × v|   (normal, orbit-plane north)
// T̂ = N̂ × R̂              (transverse, along-track)
void ManeuverCalculator::build_rtn(
        const std::array<double,3>& r_vec,
        const std::array<double,3>& v_vec,
        std::array<double,3>& r_hat,
        std::array<double,3>& t_hat,
        std::array<double,3>& n_hat) const {

    r_hat = normalise(r_vec);
    n_hat = normalise(cross(r_vec, v_vec));
    t_hat = cross(n_hat, r_hat);   // already unit if r̂ and n̂ are unit
    t_hat = normalise(t_hat);      // guard against floating-point drift
}

// ─────────────────────────────────────────────────────────────────────────────
// ManeuverCalculator::calculate
//
// Strategy
// --------
// 1. Extract position and velocity from sat_state.
// 2. Build RTN frame.
// 3. Determine required evasion ΔV:
//    - Prefer T̂ (transverse / along-track) burns because they create
//      a phase difference that moves the conjunction into the future or past.
//    - The minimum T̂ burn to achieve > THRESHOLD_WARNING clearance is
//      estimated from the current miss distance and relative velocity.
//    - If the conjunction is CRITICAL (< 0.1 km), we apply a maximum
//      urgency burn (MAX_DELTA_V) in the prograde (positive T̂) direction.
//    - If WARNING, a proportionally reduced T̂ burn is used.
//    - If nothing else, a normal (N̂) burn is used as last resort.
// 4. Cap at MAX_DELTA_V.
// 5. Recovery burn = same magnitude, opposite T̂ component, after debris
//    has passed (timing = TCA + half orbital period as a conservative estimate).
// ─────────────────────────────────────────────────────────────────────────────
ManeuverPlan ManeuverCalculator::calculate(
        const StateVector&        sat_state,
        const ConjunctionWarning& warning) const {

    std::array<double,3> r_vec = {sat_state[0], sat_state[1], sat_state[2]};
    std::array<double,3> v_vec = {sat_state[3], sat_state[4], sat_state[5]};

    std::array<double,3> r_hat, t_hat, n_hat;
    build_rtn(r_vec, v_vec, r_hat, t_hat, n_hat);

    // ── Step 1: determine required evasion delta-v magnitude ─────────────────
    double miss = warning.current_distance;   // km
    double tca  = warning.time_to_closest_approach; // seconds
    double rel_v = warning.relative_velocity;       // km/s

    // Desired clearance after manoeuvre: 2× WARNING threshold (2 km)
    // For a transverse burn of magnitude δv applied at time t_burn before TCA:
    //   drift ≈ δv * t_burn  (first-order linear approximation)
    // Minimum δv to achieve 2.0 km clearance:
    double desired_clearance = 2.0 * ConjunctionDetector::THRESHOLD_WARNING; // 2 km
    double need_clearance    = desired_clearance - miss;                      // km

    // Estimate burn-to-TCA time: apply burn now (offset = 0), so t_burn = TCA.
    double t_burn = std::max(tca, 30.0);  // at least 30 s ahead

    // Required delta-v (transverse) to move satellite out of the collision cone
    double dv_transverse = 0.0;
    if(need_clearance > 0.0 && t_burn > 0.0){
        dv_transverse = need_clearance / t_burn;
    }

    // For a CRITICAL threat, ensure we use enough delta-v regardless of TCA
    if(warning.severity == "CRITICAL"){
        dv_transverse = std::max(dv_transverse, MAX_DELTA_V * 0.5);
    }

    // Determine burn direction preference.
    // If the relative velocity has a component along velocity (closing),
    // a retrograde burn is preferred; otherwise prograde.
    // We keep it simple: positive T̂ = prograde.
    // For head-on approaches (rel_v >> orbital, debris closing from front),
    // retrograde shortens the orbit slightly, making us arrive earlier.
    // Use relative velocity sign as heuristic.
    // Here we always use a prograde (positive T̂) evasion since it's
    // conservative and always increases altitude on the opposite side.
    double dv_evasion_mag = std::min(dv_transverse, MAX_DELTA_V);

    // Last resort: if we couldn't compute a sensible transverse burn
    // (e.g. rel_v == 0, or TCA == 0), fall back to MAX_DELTA_V / 2 normal burn.
    bool use_normal = (dv_evasion_mag < 1e-9);
    if(use_normal){
        dv_evasion_mag = std::min(MAX_DELTA_V * 0.5, MAX_DELTA_V);
    }

    // ── Step 2: build evasion ΔV vector in ECI ────────────────────────────────
    std::array<double,3> evasion_dv;
    if(!use_normal){
        // Prograde transverse burn
        evasion_dv = scale(t_hat, dv_evasion_mag);
    } else {
        // Normal burn as last resort
        evasion_dv = scale(n_hat, dv_evasion_mag);
    }

    // ── Step 3: recovery burn (returns satellite toward nominal slot) ─────────
    // After the debris has passed (at TCA + some margin), apply an equal
    // retrograde burn to begin drifting back.  The recovery magnitude matches
    // the evasion so fuel cost is symmetric and the satellite returns to
    // roughly the same orbital element set (within 10 km drift).
    double dv_recovery_mag = dv_evasion_mag;

    std::array<double,3> recovery_dv;
    if(!use_normal){
        // Retrograde (negative T̂) recovery
        recovery_dv = scale(t_hat, -dv_recovery_mag);
    } else {
        recovery_dv = scale(n_hat, -dv_recovery_mag);
    }

    // Recommended burn timing: apply evasion `burn_offset` seconds before TCA.
    // Use TCA as reference; earlier burns need smaller delta-v.
    // If TCA == 0 (immediate threat), use 60 s as emergency burn offset.
    double burn_offset;
    if(tca < 60.0){
        burn_offset = 60.0;  // emergency — burn immediately with 60 s margin
    } else {
        burn_offset = std::min(tca, std::max(60.0, tca * 0.8));
    }

    // ── Step 4: fuel cost (Tsiolkovsky, both burns combined) ──────────────────
    double total_dv   = dv_evasion_mag + dv_recovery_mag;
    double fc         = fuel_mass(total_dv);

    ManeuverPlan plan;
    plan.evasion_dv_eci       = evasion_dv;
    plan.recovery_dv_eci      = recovery_dv;
    plan.fuel_cost_kg         = fc;
    plan.burn_timing_offset_s = burn_offset;

    return plan;
}
