#pragma once
#include <array>

using StateVector = std::array<double, 6>;

const double MU = 398600.4418;
const double RE = 6378.137;
const double J2 = 1.08263e-3;
const double OMEGA_EARTH = 7.2921159e-5; // rad/s

class Propagator {
public:
    StateVector propagate(const StateVector& state, 
                          double dt_seconds) const;

    StateVector propagate_steps(const StateVector& state,
                                double total_seconds,
                                double step_size = 10.0) const;

    StateVector propagate_with_drag(const StateVector& state, 
                                    double dt_seconds,
                                    double area,
                                    double mass,
                                    double cd) const;

    StateVector propagate_steps_drag(const StateVector& state,
                                     double total_seconds,
                                     double step_size,
                                     double area,
                                     double mass,
                                     double cd) const;

private:
    std::array<double, 3> acceleration(
        const std::array<double, 3>& r) const;

    std::array<double, 3> acceleration_with_drag(
        const std::array<double, 3>& r,
        const std::array<double, 3>& v,
        double area,
        double mass,
        double cd) const;

    StateVector derivatives(const StateVector& state) const;
    StateVector derivatives_drag(const StateVector& state, 
                                 double area, double mass, double cd) const;

    StateVector rk4_step(const StateVector& state, double dt) const;
    StateVector rk4_step_drag(const StateVector& state, double dt, 
                              double area, double mass, double cd) const;
};
