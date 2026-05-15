/*
 * cpp/cuda_propagator.cu — CUDA Batch RK4 Propagator
 * ===================================================
 * Refactored to use shared device functions in cuda_physics.cuh.
 */
#include "cuda_bridge.h"
#include "cuda_physics.cuh"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cstdio>
#include <stdexcept>
#include <string>

#define CUDA_CHECK(call) \
    do { cudaError_t _e=(call); if(_e!=cudaSuccess) \
        throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(_e) \
            +" at " __FILE__ ":"+std::to_string(__LINE__)); } while(0)

// One thread = one satellite; all steps in register
__global__ void k_prop(double* __restrict__ S, int n, double dt, int steps){
    int i = blockIdx.x * blockDim.x + threadIdx.x; 
    if(i >= n) return;
    
    double x = S[i*6],   y = S[i*6+1], z = S[i*6+2];
    double vx = S[i*6+3], vy = S[i*6+4], vz = S[i*6+5];
    
    for(int s=0; s<steps; s++){
        rk4_step_device(x, y, z, vx, vy, vz, dt, false, 0, 1, 0);
    }
    
    S[i*6] = x;   S[i*6+1] = y; S[i*6+2] = z;
    S[i*6+3] = vx; S[i*6+4] = vy; S[i*6+5] = vz;
}

__global__ void k_prop_drag(double* __restrict__ S, int n, double dt, int steps,
                             double A, double m, double cd){
    int i = blockIdx.x * blockDim.x + threadIdx.x; 
    if(i >= n) return;
    
    double x = S[i*6],   y = S[i*6+1], z = S[i*6+2];
    double vx = S[i*6+3], vy = S[i*6+4], vz = S[i*6+5];
    
    for(int s=0; s<steps; s++){
        rk4_step_device(x, y, z, vx, vy, vz, dt, true, A, m, cd);
    }
    
    S[i*6] = x;   S[i*6+1] = y; S[i*6+2] = z;
    S[i*6+3] = vx; S[i*6+4] = vy; S[i*6+5] = vz;
}

// ── Direct Allocation ───────────────────────────────────────────────

static void run(double* s, int n, double dt, int steps,
                bool drag, double A, double m, double cd){
    size_t bytes = (size_t)n * 6 * sizeof(double);
    double* ds;
    CUDA_CHECK(cudaMalloc(&ds, bytes));
    CUDA_CHECK(cudaMemcpy(ds, s, bytes, cudaMemcpyHostToDevice));
    
    int blk = 256;
    int grd = (n + blk - 1) / blk;
    
    if(drag) k_prop_drag<<<grd, blk>>>(ds, n, dt, steps, A, m, cd);
    else     k_prop<<<grd, blk>>>(ds, n, dt, steps);
    
    CUDA_CHECK(cudaGetLastError()); 
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(s, ds, bytes, cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaFree(ds));
}

// ── Full History Kernel ──────────────────────────────────────────────────────
__global__ void k_history(const double* __restrict__ S0, int n, double dt, int steps, double* __restrict__ H){
    int i = blockIdx.x * blockDim.x + threadIdx.x; 
    if(i >= n) return;
    
    double x = S0[i*6],   y = S0[i*6+1], z = S0[i*6+2];
    double vx = S0[i*6+3], vy = S0[i*6+4], vz = S0[i*6+5];
    
    // Step 0 is already at H[0*n*6 + i*6] if we copy S0 to H first, but it's safer to write it.
    H[0 * n * 6 + i * 6 + 0] = x;  H[0 * n * 6 + i * 6 + 1] = y;  H[0 * n * 6 + i * 6 + 2] = z;
    H[0 * n * 6 + i * 6 + 3] = vx; H[0 * n * 6 + i * 6 + 4] = vy; H[0 * n * 6 + i * 6 + 5] = vz;

    for(int s=1; s<=steps; s++){
        rk4_step_device(x, y, z, vx, vy, vz, dt, false, 0, 1, 0);
        size_t offset = (size_t)s * n * 6 + i * 6;
        H[offset + 0] = x;  H[offset + 1] = y;  H[offset + 2] = z;
        H[offset + 3] = vx; H[offset + 4] = vy; H[offset + 5] = vz;
    }
}

#ifdef USE_CUDA
bool cuda_available(){ 
    int c = 0; 
    return cudaGetDeviceCount(&c) == cudaSuccess && c > 0; 
}
int  cuda_device_count(){ 
    int c = 0; 
    cudaGetDeviceCount(&c); 
    return c; 
}
void cuda_print_device_info(){
    int c = 0; 
    cudaGetDeviceCount(&c);
    for(int i=0; i<c; i++){
        cudaDeviceProp p; 
        cudaGetDeviceProperties(&p, i);
        printf("GPU %d: %s | SM %d.%d | %.0f MB | %d SMs\n",
               i, p.name, p.major, p.minor, p.totalGlobalMem/1e6, p.multiProcessorCount);
    }
}
void cuda_propagate_batch(double* s, int n, double dt, int steps){
    run(s, n, dt, steps, false, 0, 1, 0);
}
void cuda_propagate_batch_drag(double* s, int n, double dt, int steps,
                                double A, double m, double cd){
    run(s, n, dt, steps, true, A, m, cd);
}
void cuda_propagate_full_history(const double* initial_states, int n, double dt, int steps, double* output_history){
    size_t in_bytes = (size_t)n * 6 * sizeof(double);
    size_t out_bytes = (size_t)(steps + 1) * n * 6 * sizeof(double);
    
    double *din, *dout;
    CUDA_CHECK(cudaMalloc(&din, in_bytes));
    CUDA_CHECK(cudaMalloc(&dout, out_bytes));
    
    CUDA_CHECK(cudaMemcpy(din, initial_states, in_bytes, cudaMemcpyHostToDevice));
    
    int blk = 256;
    int grd = (n + blk - 1) / blk;
    k_history<<<grd, blk>>>(din, n, dt, steps, dout);
    
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(output_history, dout, out_bytes, cudaMemcpyDeviceToHost));
    
    cudaFree(din);
    cudaFree(dout);
}
#endif
