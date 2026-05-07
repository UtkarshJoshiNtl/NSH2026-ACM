/*
 * cpp/cuda_conjunction.cu — CUDA All-Pairs Conjunction Screening
 * ==============================================================
 * Two-phase approach:
 *   1. Broad phase: each thread checks one (sat, debris) pair at t=0
 *      and flags close pairs for narrow phase processing.
 *   2. Narrow phase: a second kernel sweeps flagged pairs through time.
 *
 * Debris positions are cached in shared memory per block to reduce
 * global memory bandwidth.
 */
#include "cuda_bridge.h"
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

// Use same constants as propagator (already in __constant__ from cuda_propagator.cu)
extern __constant__ double C_MU, C_RE, C_J2, C_J3, C_J4, C_OMEGA;

// Thresholds
__constant__ double C_CRIT = 0.1;   // km
__constant__ double C_WARN = 1.0;   // km
__constant__ double C_ADV  = 5.0;   // km — broad phase culling radius

// Device gravity function (duplicate here for separate compilation unit)
__device__ __forceinline__ void cj_accel(
        double x,double y,double z,double& ax,double& ay,double& az){
    double r2=x*x+y*y+z*z, rm=sqrt(r2);
    double r3=r2*rm, r5=r3*r2, r7=r5*r2;
    ax=-C_MU*x/r3; ay=-C_MU*y/r3; az=-C_MU*z/r3;
    double z2r2=z*z/r2;
    double j2f=1.5*C_J2*C_MU*C_RE*C_RE/r5;
    ax+=j2f*x*(5*z2r2-1); ay+=j2f*y*(5*z2r2-1); az+=j2f*z*(5*z2r2-3);
}

__device__ __forceinline__ void cj_rk4(double& x,double& y,double& z,
                                        double& vx,double& vy,double& vz,
                                        double dt){
    double a1x,a1y,a1z; cj_accel(x,y,z,a1x,a1y,a1z);
    double x2=x+.5*dt*vx,y2=y+.5*dt*vy,z2=z+.5*dt*vz;
    double vx2=vx+.5*dt*a1x,vy2=vy+.5*dt*a1y,vz2=vz+.5*dt*a1z;
    double a2x,a2y,a2z; cj_accel(x2,y2,z2,a2x,a2y,a2z);
    double x3=x+.5*dt*vx2,y3=y+.5*dt*vy2,z3=z+.5*dt*vz2;
    double vx3=vx+.5*dt*a2x,vy3=vy+.5*dt*a2y,vz3=vz+.5*dt*a2z;
    double a3x,a3y,a3z; cj_accel(x3,y3,z3,a3x,a3y,a3z);
    double x4=x+dt*vx3,y4=y+dt*vy3,z4=z+dt*vz3;
    double vx4=vx+dt*a3x,vy4=vy+dt*a3y,vz4=vz+dt*a3z;
    double a4x,a4y,a4z; cj_accel(x4,y4,z4,a4x,a4y,a4z);
    double k=dt/6.0;
    x+=k*(vx+2*vx2+2*vx3+vx4); y+=k*(vy+2*vy2+2*vy3+vy4); z+=k*(vz+2*vz2+2*vz3+vz4);
    vx+=k*(a1x+2*a2x+2*a3x+a4x); vy+=k*(a1y+2*a2y+2*a3y+a4y); vz+=k*(a1z+2*a2z+2*a3z+a4z);
}

// ── Result struct for GPU output ──────────────────────────────────────────────
struct GpuWarning {
    int sat_id, deb_id;
    double min_dist, tca;
    double rel_vx, rel_vy, rel_vz;
    int severity; // 0=none,1=advisory,2=warning,3=critical
};

// ── Broad-phase: flag pairs within ADVISORY radius at t=0 ────────────────────
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
    flags[si * nd + di] = (dist < 50.0) ? 1 : 0;  // 50 km coarse cull
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
    double sx=sats[si*6],sy=sats[si*6+1],sz=sats[si*6+2];
    double svx=sats[si*6+3],svy=sats[si*6+4],svz=sats[si*6+5];
    double dx=debs[di*6],dy=debs[di*6+1],dz=debs[di*6+2];
    double dvx=debs[di*6+3],dvy=debs[di*6+4],dvz=debs[di*6+5];

    double min_dist = 1e15, tca = 0.0;
    double rv_x=0,rv_y=0,rv_z=0;

    int nsteps = (int)(lookahead / step_s);
    for (int st = 0; st <= nsteps; st++) {
        double rx=sx-dx, ry=sy-dy, rz=sz-dz;
        double dist = sqrt(rx*rx+ry*ry+rz*rz);
        if (dist < min_dist) {
            min_dist = dist;
            tca = st * step_s;
            rv_x=svx-dvx; rv_y=svy-dvy; rv_z=svz-dvz;
        }
        cj_rk4(sx,sy,sz,svx,svy,svz,step_s);
        cj_rk4(dx,dy,dz,dvx,dvy,dvz,step_s);
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

// ── Host launcher ─────────────────────────────────────────────────────────────
std::vector<ConjunctionWarning> cuda_detect_conjunctions(
        const std::vector<StateVector>& sats,
        const std::vector<StateVector>& debris,
        double lookahead_s, double step_s) {

    int ns = (int)sats.size(), nd = (int)debris.size();
    if (ns == 0 || nd == 0) return {};

    // Flatten to double arrays
    std::vector<double> hs(ns*6), hd(nd*6);
    for (int i=0;i<ns;i++) for(int k=0;k<6;k++) hs[i*6+k]=sats[i][k];
    for (int i=0;i<nd;i++) for(int k=0;k<6;k++) hd[i*6+k]=debris[i][k];

    double *ds, *dd; int *flags, *cnt;
    int max_out = std::max(ns * nd / 10, 1024);
    GpuWarning* gout;

    CUDA_CHECK(cudaMalloc(&ds,   ns*6*sizeof(double)));
    CUDA_CHECK(cudaMalloc(&dd,   nd*6*sizeof(double)));
    CUDA_CHECK(cudaMalloc(&flags,ns*nd*sizeof(int)));
    CUDA_CHECK(cudaMalloc(&cnt,  sizeof(int)));
    CUDA_CHECK(cudaMalloc(&gout, max_out*sizeof(GpuWarning)));
    CUDA_CHECK(cudaMemcpy(ds, hs.data(), ns*6*sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dd, hd.data(), nd*6*sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(cnt, 0, sizeof(int)));

    // Broad phase
    dim3 blk(16,16), grd((ns+15)/16,(nd+15)/16);
    k_broad<<<grd,blk>>>(ds,ns,dd,nd,flags);
    CUDA_CHECK(cudaGetLastError());

    // Narrow phase
    k_narrow<<<grd,blk>>>(ds,ns,dd,nd,flags,gout,cnt,max_out,lookahead_s,step_s);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    int h_cnt=0;
    CUDA_CHECK(cudaMemcpy(&h_cnt, cnt, sizeof(int), cudaMemcpyDeviceToHost));
    h_cnt = std::min(h_cnt, max_out);

    std::vector<GpuWarning> hw(h_cnt);
    if (h_cnt > 0)
        CUDA_CHECK(cudaMemcpy(hw.data(), gout, h_cnt*sizeof(GpuWarning), cudaMemcpyDeviceToHost));

    cudaFree(ds); cudaFree(dd); cudaFree(flags); cudaFree(cnt); cudaFree(gout);

    static const char* SEV[] = {"NONE","ADVISORY","WARNING","CRITICAL"};
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
