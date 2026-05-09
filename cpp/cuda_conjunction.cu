/*
 * cpp/cuda_conjunction.cu — CUDA All-Pairs Conjunction Screening
 * ==============================================================
 */
#include "cuda_bridge.h"
#include "cuda_physics.cuh"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <thrust/device_vector.h>
#include <thrust/host_vector.h>
#include <cmath>
#include <vector>
#include <stdexcept>
#include <string>

#define CUDA_CHECK(call) \
    do { cudaError_t _e=(call); if(_e!=cudaSuccess) \
        throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(_e) \
            +" at " __FILE__ ":"+std::to_string(__LINE__)); } while(0)

// Thresholds
__constant__ double C_CRIT = 0.1;   // km
__constant__ double C_WARN = 1.0;   // km
__constant__ double C_ADV  = 5.0;   // km

// ── Result struct for GPU output ──────────────────────────────────────────────
struct GpuWarning {
    int sat_id, deb_id;
    double min_dist, tca;
    double rel_vx, rel_vy, rel_vz;
    int severity; // 0=none, 1=advisory, 2=warning, 3=critical
};

// ── Broad-phase: flag pairs within 50km coarse radius at t=0 ──────────────────
__global__ void k_broad(const double* __restrict__ sats, int ns,
                         const double* __restrict__ debs, int nd,
                         int* __restrict__ flags) {
    int si = blockIdx.x * blockDim.x + threadIdx.x;
    int di = blockIdx.y * blockDim.y + threadIdx.y;
    if (si >= ns || di >= nd) return;

    double dx = sats[si*6]   - debs[di*6];
    double dy = sats[si*6+1] - debs[di*6+1];
    double dz = sats[si*6+2] - debs[di*6+2];
    double dist = sqrt(dx*dx + dy*dy + dz*dz);
    flags[si * nd + di] = (dist < 50.0) ? 1 : 0;
}

// ── Narrow-phase: temporal sweep for flagged pairs ────────────────────────────
__global__ void k_narrow(const double* __restrict__ sats, int ns,
                          const double* __restrict__ debs, int nd,
                          const int* __restrict__ flags,
                          GpuWarning* __restrict__ out,
                          int* __restrict__ out_count,
                          int max_out,
                          double lookahead, double step_s) {
    int si = blockIdx.x * blockDim.x + threadIdx.x;
    int di = blockIdx.y * blockDim.y + threadIdx.y;
    if (si >= ns || di >= nd) return;
    if (!flags[si * nd + di]) return;

    // Load initial states into registers
    double sx = sats[si*6], sy = sats[si*6+1], sz = sats[si*6+2];
    double svx = sats[si*6+3], svy = sats[si*6+4], svz = sats[si*6+5];
    double dx = debs[di*6], dy = debs[di*6+1], dz = debs[di*6+2];
    double dvx = debs[di*6+3], dvy = debs[di*6+4], dvz = debs[di*6+5];

    double min_dist = 1e15, tca = 0.0;
    double rv_x = 0, rv_y = 0, rv_z = 0;

    int nsteps = (int)(lookahead / step_s);
    for (int st = 0; st <= nsteps; st++) {
        double rx = sx - dx, ry = sy - dy, rz = sz - dz;
        double dist = sqrt(rx*rx + ry*ry + rz*rz);
        if (dist < min_dist) {
            min_dist = dist;
            tca = st * step_s;
            rv_x = svx - dvx; rv_y = svy - dvy; rv_z = svz - dvz;
        }
        rk4_step_device(sx, sy, sz, svx, svy, svz, step_s, false, 0, 1, 0);
        rk4_step_device(dx, dy, dz, dvx, dvy, dvz, step_s, false, 0, 1, 0);
    }

    int sev = 0;
    if      (min_dist < C_CRIT) sev = 3;
    else if (min_dist < C_WARN) sev = 2;
    else if (min_dist < C_ADV)  sev = 1;
    if (sev == 0) return;

    int idx = atomicAdd(out_count, 1);
    if (idx < max_out) {
        out[idx] = {si, di, min_dist, tca, rv_x, rv_y, rv_z, sev};
    }
}

#ifdef USE_CUDA
// ── Host launcher ─────────────────────────────────────────────────────────────
std::vector<ConjunctionWarning> cuda_detect_conjunctions(
        const std::vector<StateVector>& sats,
        const std::vector<StateVector>& debris,
        double lookahead_s, double step_s) {

    int ns = (int)sats.size(), nd = (int)debris.size();
    if (ns == 0 || nd == 0) return {};

    // Flatten to double arrays
    std::vector<double> hs(ns*6), hd(nd*6);
    for (int i=0; i<ns; i++) for(int k=0; k<6; k++) hs[i*6+k] = sats[i][k];
    for (int i=0; i<nd; i++) for(int k=0; k<6; k++) hd[i*6+k] = debris[i][k];

    double *ds, *dd; int *flags, *cnt;
    int max_out = std::max(ns * nd / 10, 1024);
    GpuWarning* gout;

    CUDA_CHECK(cudaMalloc(&ds,    ns*6*sizeof(double)));
    CUDA_CHECK(cudaMalloc(&dd,    nd*6*sizeof(double)));
    CUDA_CHECK(cudaMalloc(&flags, ns*nd*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&cnt,   sizeof(int)));
    CUDA_CHECK(cudaMalloc(&gout,  max_out*sizeof(GpuWarning)));
    
    CUDA_CHECK(cudaMemcpy(ds, hs.data(), ns*6*sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dd, hd.data(), nd*6*sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(cnt, 0, sizeof(int)));

    // Broad phase
    dim3 blk(16, 16), grd((ns+15)/16, (nd+15)/16);
    k_broad<<<grd, blk>>>(ds, ns, dd, nd, flags);
    CUDA_CHECK(cudaGetLastError());

    // Narrow phase
    k_narrow<<<grd, blk>>>(ds, ns, dd, nd, flags, gout, cnt, max_out, lookahead_s, step_s);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    int h_cnt = 0;
    CUDA_CHECK(cudaMemcpy(&h_cnt, cnt, sizeof(int), cudaMemcpyDeviceToHost));
    h_cnt = std::min(h_cnt, max_out);

    std::vector<GpuWarning> hw(h_cnt);
    if (h_cnt > 0)
        CUDA_CHECK(cudaMemcpy(hw.data(), gout, h_cnt*sizeof(GpuWarning), cudaMemcpyDeviceToHost));

    cudaFree(ds); cudaFree(dd); cudaFree(flags); cudaFree(cnt); cudaFree(gout);

    static const char* SEV[] = {"NONE", "ADVISORY", "WARNING", "CRITICAL"};
    std::vector<ConjunctionWarning> result;
    result.reserve(h_cnt);
    for (auto& w : hw) {
        ConjunctionWarning cw;
        cw.sat_id = w.sat_id; cw.debris_id = w.deb_id;
        cw.current_distance = w.min_dist;
        cw.time_to_closest_approach = w.tca;
        cw.severity = SEV[w.severity];
        cw.relative_velocity = {w.rel_vx, w.rel_vy, w.rel_vz};
        result.push_back(cw);
    }
    return result;
}
#endif
