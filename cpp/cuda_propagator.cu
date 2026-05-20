/*
 * cpp/cuda_propagator.cu — CUDA Batch RK4 Propagator
 * ===================================================
 * Uses SoA (Structure-of-Arrays) layout for coalesced memory access:
 *      [x0,x1,...,xN], [y0,y1,...,yN], [z0,z1,...,zN], [vx0,...,vxN], ...
 *
 * Pinned host memory eliminates the page-fault overhead of cudaMemcpy from
 * pageable memory. On RTX 2050 (PCIe 3 x8): pinned H2D throughput ≈ 8 GB/s
 * vs ≈ 6 GB/s for pageable — ~33% PCIe transfer speedup.
 */
#include "cuda_bridge.h"
#include "cuda_physics.cuh"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>
#include <cstring>

#define CUDA_CHECK(call) \
    do { cudaError_t _e=(call); if(_e!=cudaSuccess) \
        throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(_e) \
            +" at " __FILE__ ":"+std::to_string(__LINE__)); } while(0)

// ─────────────────────────────────────────────────────────────────────────────
// SoA kernel — coalesced memory accesses for all 6 components
// ─────────────────────────────────────────────────────────────────────────────
// Layout: X[0..n-1], Y[n..2n-1], Z[2n..3n-1], VX[3n..4n-1], VY[4n..5n-1], VZ[5n..6n-1]
__global__ void k_prop_soa(double* __restrict__ X,  double* __restrict__ Y,
                             double* __restrict__ Z,  double* __restrict__ VX,
                             double* __restrict__ VY, double* __restrict__ VZ,
                             int n, double dt, int steps, 
                             bool drag, double A, double m, double cd, double cr, double mjd0){
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if(i >= n) return;

    double x = X[i], y = Y[i], z = Z[i];
    double vx = VX[i], vy = VY[i], vz = VZ[i];

    for(int s=0; s<steps; s++){
        rk4_step_device(x, y, z, vx, vy, vz, dt, drag, A, m, cd, cr, mjd0, s);
    }

    X[i] = x; Y[i] = y; Z[i] = z;
    VX[i] = vx; VY[i] = vy; VZ[i] = vz;
}

// ─────────────────────────────────────────────────────────────────────────────
// Full History Kernel
// ─────────────────────────────────────────────────────────────────────────────
__global__ void k_history(const double* __restrict__ S0, int n, double dt, int steps, 
                           bool drag, double A, double m, double cd, double cr, double mjd0, 
                           double* __restrict__ H){
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if(i >= n) return;

    double x  = S0[i*6],   y  = S0[i*6+1], z  = S0[i*6+2];
    double vx = S0[i*6+3], vy = S0[i*6+4], vz = S0[i*6+5];

    // step 0
    H[0*(n*6) + i*6+0]=x; H[0*(n*6) + i*6+1]=y; H[0*(n*6) + i*6+2]=z;
    H[0*(n*6) + i*6+3]=vx; H[0*(n*6) + i*6+4]=vy; H[0*(n*6) + i*6+5]=vz;

    for(int s=1; s<=steps; s++){
        rk4_step_device(x, y, z, vx, vy, vz, dt, drag, A, m, cd, cr, mjd0, s-1);
        int out_idx = s*(n*6) + i*6;
        H[out_idx+0]=x; H[out_idx+1]=y; H[out_idx+2]=z;
        H[out_idx+3]=vx; H[out_idx+4]=vy; H[out_idx+5]=vz;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SoA host launcher with pinned memory for H2D/D2H transfers
// ─────────────────────────────────────────────────────────────────────────────
static void run(double* s, int n, double dt, int steps,
                    bool drag, double A, double m, double cd, double cr, double mjd0){
    size_t bytes_per_comp = (size_t)n * sizeof(double);
    size_t total_gpu_bytes = bytes_per_comp * 6;
    double *d_all;
    CUDA_CHECK(cudaMalloc(&d_all, total_gpu_bytes));
    
    double *dX = d_all, *dY = d_all + n, *dZ = d_all + 2*n;
    double *dVX = d_all + 3*n, *dVY = d_all + 4*n, *dVZ = d_all + 5*n;

    // Use pinned memory for faster scatter/gather transfers
    double *h_pinned;
    CUDA_CHECK(cudaHostAlloc(&h_pinned, total_gpu_bytes, cudaHostAllocDefault));
    
    double *hx = h_pinned, *hy = h_pinned + n, *hz = h_pinned + 2*n;
    double *hvx = h_pinned + 3*n, *hvy = h_pinned + 4*n, *hvz = h_pinned + 5*n;

    // Scatter AoS -> SoA
    #pragma omp parallel for
    for(int i=0; i<n; i++){
        hx[i]=s[i*6]; hy[i]=s[i*6+1]; hz[i]=s[i*6+2];
        hvx[i]=s[i*6+3]; hvy[i]=s[i*6+4]; hvz[i]=s[i*6+5];
    }

    CUDA_CHECK(cudaMemcpy(dX, hx, total_gpu_bytes, cudaMemcpyHostToDevice));

    int blk = 256, grd = (n+blk-1)/blk;
    k_prop_soa<<<grd, blk>>>(dX, dY, dZ, dVX, dVY, dVZ, n, dt, steps, drag, A, m, cd, cr, mjd0);

    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // Gather SoA -> AoS
    CUDA_CHECK(cudaMemcpy(h_pinned, d_all, total_gpu_bytes, cudaMemcpyDeviceToHost));

    #pragma omp parallel for
    for(int i=0; i<n; i++){
        s[i*6]=hx[i]; s[i*6+1]=hy[i]; s[i*6+2]=hz[i];
        s[i*6+3]=hvx[i]; s[i*6+4]=hvy[i]; s[i*6+5]=hvz[i];
    }

    cudaFreeHost(h_pinned);
    cudaFree(d_all);
}

// ── Monte Carlo Conjunction Kernel ───────────────────────────────────────────
__global__ void k_monte_carlo(
    const double* __restrict__ sat_samples,
    const double* __restrict__ deb_samples,
    int n, double dt, int steps, double threshold_km,
    int* __restrict__ collision_count, double mjd0)
{
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;

    double sx = sat_samples[i*6+0], sy = sat_samples[i*6+1], sz = sat_samples[i*6+2];
    double svx = sat_samples[i*6+3], svy = sat_samples[i*6+4], svz = sat_samples[i*6+5];
    
    double dx = deb_samples[i*6+0], dy = deb_samples[i*6+1], dz = deb_samples[i*6+2];
    double dvx = deb_samples[i*6+3], dvy = deb_samples[i*6+4], dvz = deb_samples[i*6+5];

    double min_dist = 1e15;

    for (int st = 0; st < steps; ++st) {
        double rx = sx - dx, ry = sy - dy, rz = sz - dz;
        double d2 = rx*rx + ry*ry + rz*rz;
        if (d2 < min_dist) min_dist = d2;

        // Propagate both
        rk4_step_device(sx, sy, sz, svx, svy, svz, dt, false, 0, 1, 0, 1.5, mjd0, st);
        rk4_step_device(dx, dy, dz, dvx, dvy, dvz, dt, false, 0, 1, 0, 1.5, mjd0, st);
    }

    if (sqrt(min_dist) < threshold_km) {
        atomicAdd(collision_count, 1);
    }
}

double cuda_monte_carlo_pc(
    const double* sat_samples, 
    const double* deb_samples,
    int n, double dt, int steps, double threshold_km, double mjd0) 
{
    double *d_sat, *d_deb;
    int *d_count;
    int h_count = 0;

    CUDA_CHECK(cudaMalloc(&d_sat, n * 6 * sizeof(double)));
    CUDA_CHECK(cudaMalloc(&d_deb, n * 6 * sizeof(double)));
    CUDA_CHECK(cudaMalloc(&d_count, sizeof(int)));

    CUDA_CHECK(cudaMemcpy(d_sat, sat_samples, n * 6 * sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_deb, deb_samples, n * 6 * sizeof(double), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(d_count, 0, sizeof(int)));

    int blk = 256;
    k_monte_carlo<<<(n + blk - 1) / blk, blk>>>(d_sat, d_deb, n, dt, steps, threshold_km, d_count, mjd0);
    
    CUDA_CHECK(cudaMemcpy(&h_count, d_count, sizeof(int), cudaMemcpyDeviceToHost));

    cudaFree(d_sat); cudaFree(d_deb); cudaFree(d_count);

    return (double)h_count / n;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API (USE_CUDA guard)
// ─────────────────────────────────────────────────────────────────────────────
#ifdef USE_CUDA
bool cuda_available(){
    int c=0; return cudaGetDeviceCount(&c)==cudaSuccess && c>0;
}
int cuda_device_count(){
    int c=0; cudaGetDeviceCount(&c); return c;
}
void cuda_print_device_info(){
    int c=0; cudaGetDeviceCount(&c);
    for(int i=0;i<c;i++){
        cudaDeviceProp p; cudaGetDeviceProperties(&p,i);
        printf("GPU %d: %s | SM %d.%d | %.0f MB | %d SMs\n",
               i,p.name,p.major,p.minor,p.totalGlobalMem/1e6,p.multiProcessorCount);
    }
}
void cuda_propagate_batch(double* s, int n, double dt, int steps, double mjd0){
    run(s,n,dt,steps,false,0,1,0,1.5,mjd0);
}
void cuda_propagate_batch_drag(double* s, int n, double dt, int steps,
                                double A, double m, double cd, double cr, double mjd0){
    run(s,n,dt,steps,true,A,m,cd,cr,mjd0);
}
void cuda_propagate_full_history(const double* initial_states, int n,
                                  double dt, int steps, 
                                  double area, double mass, double cd, double cr, bool with_drag,
                                  double mjd0, double* output_history){
    size_t in_bytes  = (size_t)n*6*sizeof(double);
    size_t out_bytes = (size_t)(steps+1)*n*6*sizeof(double);
    double *din, *dout;
    CUDA_CHECK(cudaMalloc(&din,  in_bytes));
    CUDA_CHECK(cudaMalloc(&dout, out_bytes));
    CUDA_CHECK(cudaMemcpy(din, initial_states, in_bytes, cudaMemcpyHostToDevice));
    int blk=256, grd=(n+blk-1)/blk;
    k_history<<<grd,blk>>>(din,n,dt,steps,with_drag,area,mass,cd,cr,mjd0,dout);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(output_history, dout, out_bytes, cudaMemcpyDeviceToHost));
    cudaFree(din); cudaFree(dout);
}
#endif
