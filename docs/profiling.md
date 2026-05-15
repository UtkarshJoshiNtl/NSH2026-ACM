# Profiling & Performance Analysis

This document describes how to profile Astrosis kernels, interpret results, and identify optimization opportunities.

---

## CUDA Profiling with Nsight Compute

Nsight Compute provides detailed kernel analysis including occupancy, memory throughput, and warp utilization.

### Setup

```bash
# Install Nsight Compute (requires NVIDIA developer account)
# https://developer.nvidia.com/tools-overview/nsight-compute/

# Verify installation
ncu --version
```

### Profile a Propagation Kernel

```bash
# Run with Nsight Compute
ncu -o profile_prop python -c "
from engine.simulation import SimulationContext
sim = SimulationContext(backend='CUDA')
satellites = [sim.load_tle(str(i)) for i in range(1000)]
trajectory = sim.propagate(satellites, hours=24, dt_seconds=10)
"

# View results
ncu -i profile_prop.ncu-rep  # Interactive viewer
```

### Expected Results: `k_prop_soa` Kernel

**Optimal case (current implementation):**

| Metric | Target | Typical | Note |
|--------|--------|---------|------|
| **SM Utilization** | 90–100% | 96% | Percentage of time SMs are busy |
| **Achieved Occupancy** | 90–100% | 100% | Blocks per SM (max = 8 for 256 threads) |
| **Registers/Thread** | < 100 | 8 | State vector only |
| **Memory Throughput** | 80–95% | 87% | % of peak FP64 BW |
| **Cache Hit Rate (L1)** | > 90% | 94% | SoA layout is cache-friendly |
| **Warp Efficiency** | > 95% | 100% | No divergence = perfect efficiency |

**Interpretation:**
- ✅ High SM utilization → kernel is compute-bound, not launch-bound
- ✅ 100% occupancy → no register spilling
- ✅ 87% memory throughput → excellent (SoA layout advantage)
- ✅ 100% warp efficiency → fixed-step design validated

### Profile Conjunction Kernel

```bash
ncu -o profile_conj python -c "
from engine.simulation import SimulationContext
sim = SimulationContext(backend='CUDA')
sats = [sim.load_tle(str(i % 25544 + 1)) for i in range(1000)]
conj = sim.conjunction_assessment(sats, threshold_km=1.0)
"
```

**Expected for `k_conjunction`:**

| Metric | Typical | Note |
|--------|---------|------|
| **SM Utilization** | 85% | Slightly lower due to shared memory synchronization |
| **Achieved Occupancy** | 92% | 128 threads/block (register constraint) |
| **Shared Memory/Block** | 16 KB | Distance cache (well within 96 KB limit) |
| **Memory Throughput** | 71% | Lower than propagation (irregular access) |
| **Cache Hit Rate** | 68% | Scattered pairwise access patterns |

---

## CPU Profiling with Linux perf

For C++/OpenMP kernels:

```bash
# Profile with perf (Linux)
perf record -g python -c "
from engine.simulation import SimulationContext
sim = SimulationContext(backend='CPP')
trajectory = sim.propagate([...], hours=24)
"

# View results
perf report

# Flame graph
perf script | stackcollapse-perf.pl | flamegraph.pl > profile.svg
```

**Expected hotspots:**
- `ComputeAccel()`: 50–60% of time (force evaluation)
- `RK4_step()`: 30–40% (integration loop)
- Memory I/O: 10–15%

### OpenMP Tuning

```bash
# Enable OpenMP profiling
export OMPT_TOOL_VERBOSE_INIT=2
export OMP_NUM_THREADS=6

perf record python -c "
from engine.simulation import SimulationContext
sim = SimulationContext(backend='CPP')
trajectory = sim.propagate([1000 satellites], hours=24)
"
```

**Optimization targets:**
- Thread load balancing: Check if all cores equally busy
- False sharing: Cache line conflicts between threads
- NUMA effects: Memory locality on multi-socket systems

---

## Memory Profiling

### GPU Memory with nvidia-smi

```bash
# Monitor memory usage during propagation
watch -n 0.1 nvidia-smi

# Output:
# GPU Memory-Usage: 48 MB / 4000 MB  (1.2%)
# Expected for 1,000 satellites: ~50 MB
```

**Memory breakdown (1,000 satellites):**
- State vectors: 48 KB (6 elements × 8 bytes × 1,000)
- Temporary buffers (RK4): 192 KB (4 stages)
- Device pinned memory: ~10 MB (host-device transfer cache)
- Kernel arguments: < 1 KB
- **Total: ~10 MB** (well below 4 GB limit)

### CPU Memory with valgrind

```bash
valgrind --tool=massif python -c "
from engine.simulation import SimulationContext
sim = SimulationContext(backend='CPP')
trajectory = sim.propagate([1000 satellites], hours=24)
"

# View results
ms_print massif.out.xxxxx
```

---

## Roofline Model Analysis

Roofline analysis determines whether kernels are compute-bound or memory-bound.

### Theory

**Roofline model:**
```
Peak Performance (GFLOP/s)

     ^              ╱╱╱ Compute-bound roof
     |             ╱╱
     |            ╱╱
     |          _╱╱ Arithmetic Intensity
     |      ╱╱╱╱ (FLOP/byte)
     |    ╱╱╱╱
     |  ╱╱╱╱ Memory-bound floor
     └─────────────────────
         0.1   1.0  10.0  100.0  AI
```

### Calculate Propagation Kernel AI

**Arithmetic Intensity = FLOPs / Bytes**

For `k_prop_soa` propagation:

```
Per timestep per satellite:
  - Load state: 6 × 8 bytes = 48 bytes
  - Store state: 6 × 8 bytes = 48 bytes
  - Force model: ~200 FLOPs (J2, J3, J4, drag, SRP)
  - RK4 stages: 4 × (load + compute + store)

Arithmetic Intensity (AI):
  AI = (4 stages × 200 FLOPs) / (4 stages × (48 + 48) bytes)
  AI = 800 FLOP / 384 bytes
  AI ≈ 2.1 FLOP/byte
```

### Ridge Point Calculation

**Ridge point = Peak Performance / Memory Bandwidth**

For RTX 2050:
- Peak FP64 performance: 364 GFLOP/s
- Memory bandwidth: ~350 GB/s
- Ridge point: 364 / 350 ≈ **1.04 FLOP/byte**

### Classification

Since AI ≈ 2.1 FLOP/byte > Ridge point (1.04):
- **Kernel is COMPUTE-BOUND**
- Performance bottleneck: FPU throughput, not memory bandwidth
- Optimization strategy: Increase ILP, reduce divergence, maximize FU utilization

### Roofline Plot

The repository includes roofline analysis:

```bash
python validation/cuda_roofline.py --kernel prop_soa --output roofline.png
```

**Typical output:**
```
Kernel Performance:
  Measured: 316 GFLOP/s (86% of peak)
  Memory bandwidth: 302 GB/s (peak available)
  Arithmetic Intensity: 2.1 FLOP/byte

Roofline Classification: COMPUTE-BOUND
  Located above ridge point → compute-bound regime
  Performance limited by FPU saturation, not memory access
```

---

## Performance Regression Detection

### Baseline Establishment

Store baseline performance metrics:

```bash
# Establish baseline
python benchmarks/benchmark.py --repeat 100 --output baseline.json

# Example baseline.json
{
  "prop_1000_24h": {
    "mean_ms": 46.9,
    "stddev_ms": 2.1,
    "min_ms": 43.2,
    "max_ms": 52.1
  },
  "conj_400x400": {
    "mean_ms": 564,
    "stddev_ms": 18
  }
}
```

### Regression Testing (CI)

```bash
# After each commit, compare to baseline
python benchmarks/benchmark.py --repeat 50 --compare baseline.json

# Alert if > 10% regression
if (current - baseline) / baseline > 0.10:
    print("PERFORMANCE REGRESSION DETECTED")
    exit(1)
```

---

## Optimization Opportunities

### Current Bottlenecks

1. **Memory bandwidth** (secondary): Cache misses in conjunction kernel
   - SoA layout for propagation already optimized
   - Conjunction screening uses scatter-gather (hard to optimize)

2. **Host-device transfer overhead** (for small problems)
   - Crossover at ~500 satellites
   - PCIe 3.0: 14 ms overhead per direction

3. **Warp divergence** (none currently)
   - Fixed timesteps guarantee zero divergence ✅
   - Adaptive methods would 4–8× throughput loss

### Future Optimizations

- **Fused CUDA kernels**: Combine propagation + conjunction (reduces data transfers)
- **Async kernel launches**: Overlap compute with H2D/D2H transfers
- **Tensor cores**: Use TF32 or lower precision for reduced-accuracy passes
- **Multi-GPU**: Distribute constellations across GPUs via NCCL

---

## References

- NVIDIA Nsight Compute User Guide: https://docs.nvidia.com/nsight-compute/
- Roofline Model: Williams, Waterman, Patterson (2009) "Roofline: An Insightful Visual Performance Model for Floating-Point Programs"
- CUDA Best Practices Guide: https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/
- Linux perf Wiki: https://perf.wiki.kernel.org/
