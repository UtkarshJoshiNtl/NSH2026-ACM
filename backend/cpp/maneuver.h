#pragma once
#include "propagator.h"      // StateVector
#include "conjunction.h"     // ConjunctionWarning
#include <array>

// ─── Maneuver Plan ────────────────────────────────────────────────────────────
// Evasion and recovery burns are ALWAYS returned as a paired unit.
// All delta-v vectors are in ECI frame (km/s).
struct ManeuverPlan {
    std::array<double,3> evasion_dv_eci;    // delta-v for evasion burn (km/s)
    std::array<double,3> recovery_dv_eci;   // delta-v for recovery burn (km/s)
    double fuel_cost_kg;                    // total propellant consumed (kg)
    double burn_timing_offset_s;            // recommended seconds before TCA to execute evasion
};

// ─── Maneuver Calculator ──────────────────────────────────────────────────────
// Computes minimum-delta-v evasion burns in the RTN frame and converts to ECI.
//
// Strategy
// --------
//  1. Build the RTN frame from the satellite's current position and velocity.
//  2. Prefer a Transverse (T̂) burn — prograde for early approach, retrograde
//     for late approach — since phase-change manoeuvres are fuel-optimal.
//  3. Cap the evasion delta-v at MAX_DELTA_V (from fuel.h).
//  4. Compute a paired recovery burn (equal magnitude, opposite T̂ component)
//     to return the satellite to within 10 km of its nominal slot.
//  5. Fuel cost is derived from the Tsiolkovsky equation using ISP, G0, and
//     the satellite's current wet mass (DRY_MASS + INITIAL_FUEL from fuel.h).

class ManeuverCalculator {
public:
    ManeuverPlan calculate(
        const StateVector&       sat_state,
        const ConjunctionWarning& warning) const;

private:
    // Build orthonormal RTN unit vectors from position and velocity.
    void build_rtn(
        const std::array<double,3>& r_vec,
        const std::array<double,3>& v_vec,
        std::array<double,3>& r_hat,
        std::array<double,3>& t_hat,
        std::array<double,3>& n_hat) const;

    // Scale a unit vector by a scalar and return an ECI delta-v vector.
    std::array<double,3> scale(const std::array<double,3>& unit, double mag) const;

    // Tsiolkovsky: mass of propellant consumed for given |ΔV| (km/s).
    double fuel_mass(double dv_magnitude) const;

    // Cross product of two 3-vectors.
    std::array<double,3> cross(
        const std::array<double,3>& a,
        const std::array<double,3>& b) const;

    // Normalise a 3-vector (returns zero vector if near-zero magnitude).
    std::array<double,3> normalise(const std::array<double,3>& v) const;
};
