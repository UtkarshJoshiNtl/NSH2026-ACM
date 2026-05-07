/*
 * cpp/cuda_bridge.h — Public API for CUDA GPU acceleration
 * =========================================================
 * Declared here; implemented in cuda_propagator.cu and cuda_conjunction.cu.
 * All functions degrade gracefully to CPU if CUDA is unavailable at compile time.
 */
#pragma once

#include "propagator.h"
#include "conjunction.h"
#include <vector>

// ── Runtime probe ─────────────────────────────────────────────────────────────
#ifdef USE_CUDA
bool cuda_available();
int  cuda_device_count();
void cuda_print_device_info();
#else
inline bool cuda_available()    { return false; }
inline int  cuda_device_count() { return 0; }
inline void cuda_print_device_info() {}
#endif

// ── Batch Propagation ─────────────────────────────────────────────────────────
// Propagates N satellites for `steps` RK4 steps of size `dt_s` seconds.
// `states_inout` is a flat array of N*6 doubles [x,y,z,vx,vy,vz] per satellite,
// modified in-place.
#ifdef USE_CUDA
void cuda_propagate_batch(
    double* states_inout, int n,
    double dt_s, int steps);

void cuda_propagate_batch_drag(
    double* states_inout, int n,
    double dt_s, int steps,
    double area, double mass, double cd);
#endif

// ── Conjunction Detection ─────────────────────────────────────────────────────
// All-pairs conjunction screening on the GPU.
// Returns the same ConjunctionWarning objects as the CPU detector.
#ifdef USE_CUDA
std::vector<ConjunctionWarning> cuda_detect_conjunctions(
    const std::vector<StateVector>& sat_states,
    const std::vector<StateVector>& debris_states,
    double lookahead_s,
    double step_s);
#endif
