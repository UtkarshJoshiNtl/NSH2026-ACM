#pragma once
#include <array>
#include <vector>

using StateVector = std::array<double, 6>;

// ── Physics constants ────────────────────────────────────────────────────────
constexpr double MU         = 398600.4418;      // km³/s²
constexpr double RE         = 6378.137;         // km
constexpr double J2         = 1.08263e-3;       // EGM96
constexpr double J3         = -2.53266e-6;      // EGM96
constexpr double J4         = -1.61990e-6;      // EGM96
constexpr double OMEGA_EARTH = 7.2921150e-5;    // rad/s

// ── Satellite defaults ───────────────────────────────────────────────────────
constexpr double INITIAL_FUEL = 50.0;
constexpr double DRY_MASS     = 500.0;

class Propagator {
public:
    // ── Single-step propagation ──────────────────────────────────────────────
    StateVector propagate(const StateVector& state,
                          double dt_seconds) const;

    StateVector propagate_with_drag(const StateVector& state,
                                    double dt_seconds,
                                    double area,
                                    double mass,
                                    double cd) const;

    // ── Multi-step propagation (CPU serial) ──────────────────────────────────
    StateVector propagate_steps(const StateVector& state,
                                double total_seconds,
                                double step_size = 10.0) const;

    StateVector propagate_steps_drag(const StateVector& state,
                                     double total_seconds,
                                     double step_size,
                                     double area,
                                     double mass,
                                     double cd) const;

    // ── Batch propagation (N satellites × steps, CPU parallel loops) ─────────
    // states_inout: flat vector of N*6 doubles, modified in place.
    void propagate_batch(std::vector<double>& states_inout,
                         int n,
                         double dt_seconds,
                         int steps) const;

    void propagate_batch_drag(std::vector<double>& states_inout,
                              int n,
                              double dt_seconds,
                              int steps,
                              double area,
                              double mass,
                              double cd) const;

    // Python-friendly batch wrappers (accept list-of-lists, return same)
    std::vector<StateVector> batch_propagate_steps(
        const std::vector<StateVector>& states,
        double dt_seconds,
        int steps) const;

    std::vector<StateVector> batch_propagate_steps_drag(
        const std::vector<StateVector>& states,
        double dt_seconds,
        int steps,
        double area,
        double mass,
        double cd) const;

private:
    std::array<double, 3> acceleration(const std::array<double, 3>& r) const;

    std::array<double, 3> acceleration_with_drag(const std::array<double, 3>& r,
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
