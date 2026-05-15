# Performance Analysis

> Benchmark methodology, roofline analysis, and scaling behaviour.

## Hardware

All measurements collected on:

| Component | Detail |
|-----------|--------|
| CPU | Intel i7-1260P (12 cores, 16 threads) |
| GPU | NVIDIA GeForce RTX 2050 (16 SMs, 4 GB VRAM, Turing) |
| RAM | 16 GB DDR4 |
| CUDA | 12.9 |
| Compiler | GCC 12, nvcc 12.9 |

## Methodology

| Parameter | Setting |
|-----------|---------|
| Precision | FP64 throughout (both CPU and GPU) |
| Timing | `time.perf_counter` (Python), `std::chrono` (C++) |
| Warmup | CUDA context warmup: one dummy kernel launch before timed runs |
| PCIe transfers | Included for CUDA benchmarks (realistic end-to-end) |
| OpenMP threads | `OMP_NUM_THREADS=12` (one per physical core) |
| Compiler flags | `-O3 -march=native -ffast-math` (C++), `-O3 --use_fast_math` (CUDA) |

## C++ Build Flags

```cmake
-O3 -march=native -ffast-math
-fno-omit-frame-pointer          # profiler-friendly
-fopt-info-vec                   # reports auto-vectorised loops
```

CUDA flags:

```cmake
-O3 --use_fast_math -lineinfo
```

## Propagation Benchmarks

### Single-Satellite Propagation (50 000 steps, dt = 10 s)

| Backend | Time | Speedup vs Python |
|---------|------|-------------------|
| Python | 395 ms | 1× |
| C++ | 21.9 ms | 18× |

CUDA is not beneficial for single-satellite workloads (kernel launch + PCIe
overhead dominates).

### Batch Propagation (1 000 sats × 864 steps = 24 h)

| Backend | Time | Speedup vs Python |
|---------|------|-------------------|
| Python | 7 034 ms | 1× |
| NumPy | ~900 ms | ~8× |
| C++ (OpenMP) | 13.9 ms | 507× |
| CUDA AoS | 46.9 ms | 150× |
| CUDA SoA | ~33 ms | ~213× |

The C++ OpenMP backend wins for batch propagation because the workload is
embarrassingly parallel with low transfer overhead. CUDA pays a PCIe transfer
penalty that dominates at moderate batch sizes.

## Conjunction Screening

### All-Pairs (400 satellites × 400 debris = 160 000 pairs, 1 h lookahead)

| Backend | Time | Speedup vs Python |
|---------|------|-------------------|
| Python | 46 718 ms | 1× |
| C++ | 5 159 ms | 9× |
| CUDA | 564 ms | 83× |

For all-pairs conjunction screening, the GPU advantage is decisive. The
computation is throughput-bound and the O(N²) scaling amortises the transfer
cost.

## Strong Scaling (OpenMP, N = 10 000 satellites)

| Threads | Time (ms) | Speedup | Efficiency |
|---------|-----------|---------|------------|
| 1 | 167 | 1.0× | 100 % |
| 2 | 86 | 1.9× | 97 % |
| 4 | 44 | 3.8× | 95 % |
| 8 | 24 | 7.0× | 87 % |
| 12 | 18 | 9.3× | 77 % |

Efficiency drops beyond 8 threads due to memory bandwidth saturation on the
shared L3 cache.

## Weak Scaling (OpenMP, 1 000 sats / thread)

| Threads | Total sats | Time (ms) | Efficiency |
|---------|------------|-----------|------------|
| 1 | 1 000 | 1.9 | 100 % |
| 2 | 2 000 | 3.9 | 97 % |
| 4 | 4 000 | 7.9 | 96 % |
| 8 | 8 000 | 16.0 | 95 % |
| 12 | 12 000 | 24.5 | 93 % |

Near-perfect weak scaling. Each thread works on independent cache lines
(64-byte aligned `StateVector`), so there is no false sharing.

## CUDA Crossover

CUDA batch propagation beats C++ only when N exceeds ~5 000 satellites
(for AoS layout). With SoA layout, the crossover shifts to ~200 satellites.

The crossover exists because:
- **Small N:** Kernel launch latency (≈ 10 µs) + PCIe transfer (≈ 50 µs)
  dominate. C++ processes the batch in-thread with no overhead.
- **Large N:** GPU compute throughput (200 GFLOPS FP64) exceeds CPU throughput
  (≈ 20 GFLOPS FP64). Memory coalescing with SoA layout gives CUDA a further
  1.4× advantage.

See `validation/plots/7_cuda_crossover.png` for the measured crossover curve.

## Roofline Model (RTX 2050, `k_prop_soa` kernel)

| Metric | Value |
|--------|-------|
| Arithmetic intensity (AI) | ~ 2.5 FLOP / byte |
| Peak FP64 compute | 0.2 TFLOP / s |
| Peak memory bandwidth | 192 GB / s |
| Ridge point | AI = 1.04 FLOP / byte |
| **Kernel regime** | **Compute-bound (AI = 2.5 > 1.04)** |

The kernel is compute-bound on FP64. Future optimisation directions:

- Reduce FP64 ops (atmospheric density lookup needs only 4 significant figures;
  could use FP32).
- Increase occupancy via register pressure reduction.
- Tensor core exploitation requires FP16 / TF32, which is inappropriate for
  orbital mechanics.

See `validation/plots/8_roofline.png` for the full roofline chart.

## Memory Layout: AoS vs SoA

**AoS (original):** Memory stride = 6 doubles = 48 bytes. Warp of 32 threads
reading component `vx` accesses offsets `{0, 6, 12, 18, …}` — every 6th
double. **Cache utilisation: 17 %.**

**SoA (current):** Memory stride = 1 double. Warp reads 32 consecutive doubles
from `VX[...]`. **Cache utilisation: 100 %.**

Measured throughput improvement: **1.4×** for N > 1 000 satellites.

## False Sharing Mitigation

`StateVector` is 64-byte aligned (8 doubles) to fit exactly one cache line.
Adjacent satellites in the batch array never share a cache line, eliminating
false sharing between OpenMP threads on write-back.

---

*See `validation/scaling_analysis.py` for the full reproducibility script.*
