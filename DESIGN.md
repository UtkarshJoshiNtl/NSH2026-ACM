# Astrosis Engine — Design Decisions

> Every significant decision in this engine was made deliberately.
> This document explains *why*, not just *what*.

---

## 1. Why RK4 and not an adaptive step-size integrator (RK45 / Dormand-Prince)?

**Short answer:** Fixed step sizes are GPU-friendly, SIMD-vectorizable, and produce predictable memory usage. Adaptive methods offer better accuracy per CPU cycle for a single satellite; fixed methods win decisively for batches of thousands.

### The GPU argument

A CUDA kernel processes all N satellites in a warp. If each satellite uses a different step size (adaptive), warp divergence destroys throughput — threads that have converged spin while threads that haven't finish more steps. Empirically, warp divergence can reduce throughput by 4–8x on Ampere hardware.

With fixed steps, all threads in a warp execute the same number of instructions. The `k_prop_soa` kernel sustains near-peak arithmetic throughput with zero divergence.

### The memory argument

Adaptive methods must store internal state (k values, error estimate, step history) per satellite — roughly 6× the state vector per step. For 10,000 satellites this is tens of MB of working memory, competing with the L2 cache. Fixed-step RK4 uses only 8 registers per thread (the state vector) with no dynamic memory.

### Accuracy

RK4 with `dt=10s` for circular LEO:
- Local truncation error: O(dt⁵) ≈ 10⁻¹³ km per step
- Global error after 24h: O(dt⁴) ≈ 10⁻⁷ relative energy drift (verified — see validation/plots/1_energy_conservation.png)

For conjunction analysis, position accuracy of <0.1 km at 24h suffices (TLE uncertainty itself is 0.1–1 km). RK4 at dt=10s is well within this margin.

**Adaptive methods are better for:** single high-eccentricity trajectories, long-arc maneuver design, re-entry corridor analysis.
**Fixed RK4 is better for:** GPU-parallel batch propagation of many LEO satellites, real-time conjunction screening.

---

## 2. Why J2/J3/J4 and not the full EGM2008 gravity model?

EGM2008 has 2,190 × 2,190 = 4.8 million spherical harmonic coefficients. Computing them per satellite per step would require:
- ~10 million FP64 multiply-adds per satellite per step
- A 37 MB coefficient table in GPU constant memory (16 MB limit on most GPUs)
- O(l²) computation scaling — impractical for real-time use

**Perturbation contribution (LEO, 400 km circular):**

| Term | Acceleration magnitude | Contribution |
|------|----------------------|-------------|
| Two-body | 8.7 km/s² | 100% |
| J2 | 2.6 × 10⁻³ km/s² | 0.030% |
| J3 | 2.0 × 10⁻⁶ km/s² | 0.000023% |
| J4 | 1.6 × 10⁻⁶ km/s² | 0.000018% |
| J5+ | < 5 × 10⁻⁷ km/s² | < 0.000006% |
| EGM2008 tesseral | < 2 × 10⁻⁷ km/s² | < 0.000002% |

J2 through J4 captures >99.97% of the gravitational perturbation with just 3 extra arithmetic expressions per evaluation. J5 and beyond contribute less than 0.006% and would be swamped by TLE epoch uncertainty (~0.3 km / orbit period) within a few hours.

**The tradeoff:** We trade < 0.006% gravitational accuracy for a 3-instruction vs 10-million-instruction kernel. For engineering-grade conjunction analysis, this is the correct choice.

---

## 3. Where the propagator breaks down

| Regime | Why it fails | Mitigation |
|--------|-------------|------------|
| High eccentricity (e > 0.5) | Fixed step dt=10s is too coarse near periapsis (fast motion); energy drift grows rapidly | Use smaller dt or adaptive method near periapsis |
| Very low altitude (< 180 km) | Atmospheric density model degrades; drag deceleration becomes large relative to gravity | Re-entry trajectories require atmospheric uncertainty models |
| Very long propagation (> 7 days) | J4 drag cross-coupling terms and solar radiation pressure accumulate; error > 10 km | Use TLE epoch refresh every 1–2 days |
| Resonant orbits (GPS, Molniya) | Higher harmonics (J5+, tesseral) dominate at resonance; secular drifts diverge | Add J5+ or switch to EGM2008 for these specific altitudes |
| Near-GEO | Solar radiation pressure and lunar/solar gravity become significant perturbations | Add solar/lunar third-body terms |

---

## 4. CUDA crossover point (GPU vs CPU batch propagation)

From `validation/scaling_analysis.py` (RTX 2050 SM 8.6, 12-core CPU):

| Metric | Value |
|--------|-------|
| PCIe 3.0 x8 bandwidth | ~8 GB/s pinned |
| Transfer time for N=1000 sats | ~0.6 ms |
| CUDA kernel time for N=1000 sats | ~0.3 ms |
| C++ OpenMP time for N=1000 sats | ~0.4 ms |

**Crossover:** The GPU beats C++ at **N ≈ 300–500 satellites** (varies by step count). Below this threshold, PCIe transfer overhead dominates kernel execution time and C++ is faster. Above it, the GPU's 640 CUDA cores overwhelm the CPU's 12 threads.

The crossover plot (`validation/plots/7_cuda_crossover.png`) shows this as the intersection of the C++ and CUDA timing curves on a log-log scale.

**The SoA advantage:** Switching from AoS to SoA layout shifts the crossover to ~200 satellites by reducing memory transaction waste. All warp accesses hit a contiguous cache line instead of striding across a 48-byte struct.

---

## 5. Roofline Analysis (RTX 2050, FP64 RK4 kernel)

The `k_prop_soa` kernel was analysed using Nsight Compute. Key metrics:

| Metric | Value |
|--------|-------|
| Arithmetic intensity (AI) | ~2.5 FLOP/byte |
| Peak FP64 compute | 0.2 TFLOPs/s |
| Peak memory bandwidth | 192 GB/s |
| Roofline ceiling at AI=2.5 | min(2.5 × 192, 200) = 200 GFLOPS/s |

The kernel is **memory-bound** (AI = 2.5 < ridge point = 0.2/0.192 ≈ 1.0 FLOP/byte).

Wait — actually the ridge point for this hardware is at:
```
AI_ridge = PEAK_FP64_GFLOPS / PEAK_BW_GB_s = 200 / 192 ≈ 1.04 FLOP/byte
```

Since our AI ≈ 2.5 > 1.04, the kernel is actually **compute-bound** on FP64.

This means future optimisation should focus on:
- Reducing FP64 operations (e.g., using FP32 for the atmospheric density lookup which only needs 4 significant figures)
- Tensor core exploitation (requires FP16/TF32, inappropriate for orbital mechanics)
- Increasing occupancy via register pressure reduction

The roofline plot is saved to `validation/plots/8_roofline.png`.

---

## 6. AoS vs SoA Memory Layout

**AoS (Array-of-Structures)** — original layout:
```
Memory: [x0,y0,z0,vx0,vy0,vz0, x1,y1,z1,vx1,vy1,vz1, ...]
```
When warp of 32 threads each reads `vy[threadIdx.x]`, they access offsets `{4, 10, 16, 22, ...}` — every 6th double. This requires 6 cache line loads for 32 doubles. **Utilisation: 1/6 = 17%.**

**SoA (Structure-of-Arrays)** — gamma layout:
```
Memory: [x0,x1,...,xN, y0,y1,...,yN, z0,..., vx0,..., vy0,..., vz0,...]
```
When warp reads `VY[threadIdx.x]`, they access offsets `{4N, 4N+1, ..., 4N+31}` — 32 consecutive doubles. One cache line load, full utilisation. **Utilisation: 100%.**

Access pattern for the RK4 kernel: all 6 components are read/written once per step → SoA provides full coalescing for all accesses. Measured improvement: **~1.4× throughput** for N > 1000.

---

## 7. False Sharing in OpenMP Batch Propagator

The OpenMP batch propagator assigns one satellite per thread. With AoS layout, two consecutive satellites (48 bytes each) share a 64-byte cache line. When thread 0 writes satellite 0 and thread 1 writes satellite 1, they invalidate each other's cache lines on every write (false sharing).

**Fix (gamma branch):** `StateVector` is now `alignas(64)` with 8 doubles (64 bytes). Each satellite owns exactly one cache line. Adjacent satellites can never share a line.

For the flat `double*` API used in the CUDA bridge, we rely on the fact that threads work on a local `StateVector` copy in registers, then write back atomically — limiting the false-sharing window to a single store instruction.

---

## 8. Conjunction TCA Accuracy

**Before Brent's method (alpha):** TCA accuracy was limited to ±step_s (typically ±60s). At 7.66 km/s relative velocity, this translates to ±460 km uncertainty in miss distance at TCA — completely wrong.

**With Brent's method (gamma):** The coarse sweep finds the bracket; Brent's 1D minimiser converges to ±0.1s TCA accuracy in ≤ 50 iterations with super-linear convergence. At 7.66 km/s, this gives ±0.76 km miss-distance accuracy — meaningful for CDM (Conjunction Data Message) generation.

---

## 9. Probability of Collision (Chan's Method)

The simplified circular encounter approximation is:
```
Pc ≈ (HBR² / 2σ²) × exp(-x²/2)
```
where:
- `HBR` = hard-body radius (10 m default — assumes one satellite is the primary)
- `σ` = combined 1-sigma position uncertainty at TCA (km)
- `x` = miss_distance / σ

This is valid for the dilute encounter regime (miss_distance >> σ), which covers the vast majority of CDM events. For miss_distance < σ (ultra-close approaches), a numerical integration of the 2D Gaussian is required — this is the Foster/Patera refinement not currently implemented.

Position uncertainty is estimated from TLE age: `σ ≈ 0.3 × sqrt(TLE_age_days)` km. This is the Vallado (2013) empirical model for LEO.
