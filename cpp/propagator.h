#pragma once
#include <array>
#include <vector>
#include <cstring>

#include "physics_constants.h"

// ── StateVector: 64-byte cache-line aligned ───────────────────────────────────
// std::array<double,6> is 48 bytes — two adjacent satellites straddle a single
// 64-byte cache line, causing false sharing between OpenMP threads on write-back.
// Padding to 8 doubles (64 bytes) eliminates this: each satellite owns exactly
// one cache line and no two threads ever contend for the same line.
struct alignas(64) StateVector {
    double data[8];   // [0..5] = x,y,z,vx,vy,vz  |  [6..7] = padding

    StateVector() { std::memset(data, 0, sizeof(data)); }

    double&       operator[](int i)       { return data[i]; }
    const double& operator[](int i) const { return data[i]; }

    double*       begin()       { return data; }
    double*       end()         { return data + 6; }
    const double* begin() const { return data; }
    const double* end()   const { return data + 6; }

    double* raw()       { return data; }
    const double* raw() const { return data; }
};

class Propagator {
public:
    // ── Single-step propagation ──────────────────────────────────────────────
    StateVector propagate(const StateVector& state,
                          double dt_seconds, double mjd0 = 0.0) const;

    StateVector propagate_with_drag(const StateVector& state,
                                    double dt_seconds,
                                    double area,
                                    double mass,
                                    double cd, double cr = 1.5, double mjd0 = 0.0) const;

    // ── Multi-step propagation (CPU serial) ──────────────────────────────────
    StateVector propagate_steps(const StateVector& state,
                                double total_seconds,
                                double step_size = 10.0,
                                double area = 0.0, double mass = 1.0, double cd = 2.2, double cr = 1.5,
                                bool with_drag = false, double mjd0 = 0.0) const;

    // ── Batch propagation (N satellites × steps, CPU parallel loops) ─────────
    // states_inout: flat array of N*6 doubles (stride-6), modified in place.
    // The flat-array interface keeps the Python/NumPy ABI simple; false sharing
    // is mitigated by using aligned local StateVectors during per-thread work.
    void propagate_batch(double* states_inout,
                         int n,
                         double dt_seconds,
                         int steps, double mjd0) const;

    void propagate_batch_drag(double* states_inout,
                              int n,
                              double dt_seconds,
                              int steps,
                              double area,
                              double mass,
                              double cd, double cr, double mjd0) const;

    // Python-friendly batch wrappers (accept list-of-lists, return same)
    std::vector<StateVector> batch_propagate_steps(
        const std::vector<StateVector>& states,
        double dt_seconds,
        int steps, double mjd0 = 0.0) const;

    std::vector<StateVector> batch_propagate_steps_drag(
        const std::vector<StateVector>& states,
        double dt_seconds,
        int steps,
        double area,
        double mass,
        double cd, double cr = 1.5, double mjd0 = 0.0) const;

    // Returns full history: (steps+1) frames × n satellites × 6 doubles
    void batch_propagate_full_history(
        const double* initial_states,
        int n,
        double dt_seconds,
        int steps, double mjd0,
        double* output_history) const;

private:
    std::array<double, 3> acceleration(const std::array<double, 3>& r, double mjd) const;

    std::array<double, 3> acceleration_with_drag(const std::array<double, 3>& r,
                                                  const std::array<double, 3>& v,
                                                  double area,
                                                  double mass,
                                                  double cd, double cr, double mjd) const;

    StateVector derivatives(const StateVector& state, double mjd) const;
    StateVector derivatives_drag(const StateVector& state,
                                 double area, double mass, double cd, double cr, double mjd) const;

    StateVector rk4_step(const StateVector& state, double dt, double mjd0 = 0.0, int current_step = 0) const;
    StateVector rk4_step_drag(const StateVector& state, double dt,
                               double area, double mass, double cd, double cr = 1.5, double mjd0 = 0.0, int current_step = 0) const;
};
