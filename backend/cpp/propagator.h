#pragma once
#include <array>

using StateVector = std::array<double, 6>;

const double MU = 398600.4418;
const double RE = 6378.137;
const double J2 = 1.08263e-3;

class Propagator {
public:
    StateVector propagate(const StateVector& state, 
                          double dt_seconds) const;

    StateVector propagate_steps(const StateVector& state,
                                double total_seconds,
                                double step_size = 10.0) const;

private:
    std::array<double, 3> acceleration(
        const std::array<double, 3>& r) const;

    StateVector derivatives(const StateVector& state) const;

    StateVector rk4_step(const StateVector& state, 
                         double dt) const;
};
