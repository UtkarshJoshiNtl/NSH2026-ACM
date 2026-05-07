/*
 * cpp/cuda_propagator.cu — CUDA Batch RK4 Propagator (sm_75 / RTX 2050)
 * Physics: J2+J3+J4 gravity + US Std Atmo 1976 drag w/ Earth-rotation correction
 */
#include "cuda_bridge.h"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <string>

#define CUDA_CHECK(call) \
    do { cudaError_t _e=(call); if(_e!=cudaSuccess) \
        throw std::runtime_error(std::string("CUDA: ")+cudaGetErrorString(_e) \
            +" at " __FILE__ ":"+std::to_string(__LINE__)); } while(0)

// Constants in L1 cache
__constant__ double C_MU=398600.4418, C_RE=6378.137;
__constant__ double C_J2=1.08263e-3, C_J3=-2.53266e-6, C_J4=-1.61990e-6;
__constant__ double C_OMEGA=7.2921150e-5;

struct CA { double alt, H, rho0; };
__constant__ CA C_ATM[28]={
    {0,8.44,1.225},{25,6.49,3.899e-2},{30,6.75,1.774e-2},{40,7.58,3.972e-3},
    {50,8.55,1.057e-3},{60,7.71,3.206e-4},{70,6.55,8.770e-5},{80,5.79,1.905e-5},
    {90,5.57,3.396e-6},{100,5.90,5.297e-7},{110,7.17,9.661e-8},{120,9.59,2.438e-8},
    {130,12.2,8.484e-9},{140,15.5,3.845e-9},{150,19.3,2.070e-9},{180,26.0,5.464e-10},
    {200,26.0,2.789e-10},{250,38.5,7.248e-11},{300,51.0,2.418e-11},{350,59.5,9.518e-12},
    {400,67.6,3.725e-12},{450,76.0,1.585e-12},{500,84.0,6.967e-13},{600,105.0,1.454e-13},
    {700,130.0,3.614e-14},{800,180.0,1.170e-14},{900,268.0,5.245e-15},{1000,1e9,3.019e-15}
};

__device__ __forceinline__ double drho(double alt) {
    if (alt<0||alt>=1000) return 0.0;
    for(int i=0;i<27;i++) if(C_ATM[i].alt<=alt&&alt<C_ATM[i+1].alt)
        return C_ATM[i].rho0*exp(-(alt-C_ATM[i].alt)/C_ATM[i].H);
    return 0.0;
}

__device__ __forceinline__ void accel(
        double x,double y,double z, double& ax,double& ay,double& az) {
    double r2=x*x+y*y+z*z, rm=sqrt(r2);
    double r3=r2*rm, r5=r3*r2, r7=r5*r2;
    ax=-C_MU*x/r3; ay=-C_MU*y/r3; az=-C_MU*z/r3;
    double z2r2=z*z/r2;
    double j2f=1.5*C_J2*C_MU*C_RE*C_RE/r5;
    ax+=j2f*x*(5*z2r2-1); ay+=j2f*y*(5*z2r2-1); az+=j2f*z*(5*z2r2-3);
    double zr=z/rm, j3f=2.5*C_J3*C_MU*C_RE*C_RE*C_RE/r7;
    ax+=j3f*x*(7*z2r2*zr-3*zr); ay+=j3f*y*(7*z2r2*zr-3*zr);
    az+=j3f*(7*z2r2*zr*z-6*z2r2+0.6);
    double z4r4=z2r2*z2r2, j4f=0.625*C_J4*C_MU*C_RE*C_RE*C_RE*C_RE/r7;
    ax+=j4f*x*(3-42*z2r2+63*z4r4); ay+=j4f*y*(3-42*z2r2+63*z4r4);
    az+=j4f*z*(15-70*z2r2+63*z4r4);
}

__device__ __forceinline__ void accel_drag(
        double x,double y,double z,double vx,double vy,double vz,
        double A,double m,double cd, double& ax,double& ay,double& az) {
    accel(x,y,z,ax,ay,az);
    double rm=sqrt(x*x+y*y+z*z), alt=rm-C_RE;
    if(alt>=0&&alt<1000){
        double rho=drho(alt);
        double vrx=vx+C_OMEGA*y, vry=vy-C_OMEGA*x, vrz=vz;
        double vm=sqrt(vrx*vrx+vry*vry+vrz*vrz);
        if(vm>0){double df=-0.5*cd*(A/m)*rho*vm*1000;
            ax+=df*vrx; ay+=df*vry; az+=df*vrz;}
    }
}

// One thread = one satellite; all steps in register
__global__ void k_prop(double* __restrict__ S, int n, double dt, int steps){
    int i=blockIdx.x*blockDim.x+threadIdx.x; if(i>=n) return;
    double x=S[i*6],y=S[i*6+1],z=S[i*6+2];
    double vx=S[i*6+3],vy=S[i*6+4],vz=S[i*6+5];
    for(int s=0;s<steps;s++){
        double a1x,a1y,a1z; accel(x,y,z,a1x,a1y,a1z);
        double x2=x+.5*dt*vx, y2=y+.5*dt*vy, z2=z+.5*dt*vz;
        double vx2=vx+.5*dt*a1x,vy2=vy+.5*dt*a1y,vz2=vz+.5*dt*a1z;
        double a2x,a2y,a2z; accel(x2,y2,z2,a2x,a2y,a2z);
        double x3=x+.5*dt*vx2,y3=y+.5*dt*vy2,z3=z+.5*dt*vz2;
        double vx3=vx+.5*dt*a2x,vy3=vy+.5*dt*a2y,vz3=vz+.5*dt*a2z;
        double a3x,a3y,a3z; accel(x3,y3,z3,a3x,a3y,a3z);
        double x4=x+dt*vx3,y4=y+dt*vy3,z4=z+dt*vz3;
        double vx4=vx+dt*a3x,vy4=vy+dt*a3y,vz4=vz+dt*a3z;
        double a4x,a4y,a4z; accel(x4,y4,z4,a4x,a4y,a4z);
        double k=(dt/6.0);
        x+=k*(vx+2*vx2+2*vx3+vx4); y+=k*(vy+2*vy2+2*vy3+vy4);
        z+=k*(vz+2*vz2+2*vz3+vz4);
        vx+=k*(a1x+2*a2x+2*a3x+a4x); vy+=k*(a1y+2*a2y+2*a3y+a4y);
        vz+=k*(a1z+2*a2z+2*a3z+a4z);
    }
    S[i*6]=x;S[i*6+1]=y;S[i*6+2]=z;
    S[i*6+3]=vx;S[i*6+4]=vy;S[i*6+5]=vz;
}

__global__ void k_prop_drag(double* __restrict__ S,int n,double dt,int steps,
                             double A,double m,double cd){
    int i=blockIdx.x*blockDim.x+threadIdx.x; if(i>=n) return;
    double x=S[i*6],y=S[i*6+1],z=S[i*6+2];
    double vx=S[i*6+3],vy=S[i*6+4],vz=S[i*6+5];
    for(int s=0;s<steps;s++){
        double a1x,a1y,a1z; accel_drag(x,y,z,vx,vy,vz,A,m,cd,a1x,a1y,a1z);
        double x2=x+.5*dt*vx,y2=y+.5*dt*vy,z2=z+.5*dt*vz;
        double vx2=vx+.5*dt*a1x,vy2=vy+.5*dt*a1y,vz2=vz+.5*dt*a1z;
        double a2x,a2y,a2z; accel_drag(x2,y2,z2,vx2,vy2,vz2,A,m,cd,a2x,a2y,a2z);
        double x3=x+.5*dt*vx2,y3=y+.5*dt*vy2,z3=z+.5*dt*vz2;
        double vx3=vx+.5*dt*a2x,vy3=vy+.5*dt*a2y,vz3=vz+.5*dt*a2z;
        double a3x,a3y,a3z; accel_drag(x3,y3,z3,vx3,vy3,vz3,A,m,cd,a3x,a3y,a3z);
        double x4=x+dt*vx3,y4=y+dt*vy3,z4=z+dt*vz3;
        double vx4=vx+dt*a3x,vy4=vy+dt*a3y,vz4=vz+dt*a3z;
        double a4x,a4y,a4z; accel_drag(x4,y4,z4,vx4,vy4,vz4,A,m,cd,a4x,a4y,a4z);
        double k=(dt/6.0);
        x+=k*(vx+2*vx2+2*vx3+vx4); y+=k*(vy+2*vy2+2*vy3+vy4);
        z+=k*(vz+2*vz2+2*vz3+vz4);
        vx+=k*(a1x+2*a2x+2*a3x+a4x); vy+=k*(a1y+2*a2y+2*a3y+a4y);
        vz+=k*(a1z+2*a2z+2*a3z+a4z);
    }
    S[i*6]=x;S[i*6+1]=y;S[i*6+2]=z;
    S[i*6+3]=vx;S[i*6+4]=vy;S[i*6+5]=vz;
}

static void run(double* s,int n,double dt,int steps,
                bool drag,double A,double m,double cd){
    size_t bytes=(size_t)n*6*sizeof(double);
    double* ds; CUDA_CHECK(cudaMalloc(&ds,bytes));
    CUDA_CHECK(cudaMemcpy(ds,s,bytes,cudaMemcpyHostToDevice));
    int blk=256, grd=(n+blk-1)/blk;
    if(drag) k_prop_drag<<<grd,blk>>>(ds,n,dt,steps,A,m,cd);
    else     k_prop<<<grd,blk>>>(ds,n,dt,steps);
    CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(s,ds,bytes,cudaMemcpyDeviceToHost));
    cudaFree(ds);
}

bool cuda_available(){ int c=0; return cudaGetDeviceCount(&c)==cudaSuccess&&c>0; }
int  cuda_device_count(){ int c=0; cudaGetDeviceCount(&c); return c; }
void cuda_print_device_info(){
    int c=0; cudaGetDeviceCount(&c);
    for(int i=0;i<c;i++){
        cudaDeviceProp p; cudaGetDeviceProperties(&p,i);
        printf("GPU %d: %s | SM %d.%d | %.0f MB | %d SMs\n",
               i,p.name,p.major,p.minor,p.totalGlobalMem/1e6,p.multiProcessorCount);
    }
}
void cuda_propagate_batch(double* s,int n,double dt,int steps){
    run(s,n,dt,steps,false,0,1,0);
}
void cuda_propagate_batch_drag(double* s,int n,double dt,int steps,
                                double A,double m,double cd){
    run(s,n,dt,steps,true,A,m,cd);
}
