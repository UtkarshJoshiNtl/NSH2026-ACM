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
    cudaFree(ds);
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
#endif
