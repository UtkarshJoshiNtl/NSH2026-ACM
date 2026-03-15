#pragma once
#include <array>

// State vector is always 6 doubles
// [x, y, z, vx, vy, vz]
// position in km, velocity in km/s
using StateVector = std::array<double, 6>;

// Physical constants
const double MU = 398600.4418;   // km³/s²
const double RE = 6378.137;      // km
const double J2 = 1.08263e-3;

class Propagator {
public:
    // Move state forward by dt seconds
    // Uses RK4 with J2 perturbation
    StateVector propagate(const StateVector& state, 
                          double dt_seconds) const;

    // Propagate forward by total_seconds
    // Uses multiple small steps for accuracy
    StateVector propagate_steps(const StateVector& state,
                                double total_seconds,
                                double step_size = 10.0) const;

private:
    // Compute acceleration from gravity + J2
    std::array<double, 3> acceleration(
        const std::array<double, 3>& r) const;

    // Compute full derivatives of state vector
    StateVector derivatives(const StateVector& state) const;

    // Single RK4 step
    StateVector rk4_step(const StateVector& state, 
                         double dt) const;
};
