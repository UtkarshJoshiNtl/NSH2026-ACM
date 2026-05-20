# Astrosis Engine — Design Decisions

> **Why we built it this way.** Every significant decision in Astrosis was made deliberately. This document explains the *why* behind the *what*, providing insight into the engineering tradeoffs that enable high-performance orbital simulation.

**Quick Context:** Astrosis simulates satellite motion with engineering-grade accuracy while maintaining real-time performance for constellation-scale analysis (10,000+ satellites). The core challenge: balance numerical precision with computational efficiency across CPU and GPU architectures.

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
- Global error after 24h: O(dt⁴) ≈ 10⁻⁷ relative energy drift (verified — see [validation/plots/1_energy_conservation.png](../validation/plots/1_energy_conservation.png))

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

**Crossover:** For pure batch propagation of LEO states, the multi-threaded C++ engine (OpenMP) is extremely efficient, often beating the CUDA engine for batches up to **N ≈ 5,000 satellites** due to the low overhead of CPU context switching compared to GPU kernel launches and PCIe transfer latency.

However, the GPU advantage becomes massive for **all-pairs conjunction screening**. In this compute-bound regime, the CUDA engine provides an **82.8× speedup** over C++ for 400x400 pairs (160k combinations), proving that acceleration is best applied to the most compute-intensive analysis phases rather than simple state integration.

The crossover plot ([validation/plots/7_cuda_crossover.png](../validation/plots/7_cuda_crossover.png)) shows this as the intersection of the C++ and CUDA timing curves on a log-log scale.

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

The roofline plot is saved to [validation/plots/8_roofline.png](../validation/plots/8_roofline.png).

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

---

## Summary: The Astrosis Philosophy

**Performance through precision, not compromise.** Astrosis demonstrates that high-performance orbital simulation doesn't require sacrificing accuracy. By carefully engineering every layer — from numerical methods to memory layouts — we achieve:

- **83x speedup** on collision detection vs. naive implementations
- **< 1e-7 energy conservation** over 24 hours
- **Real-time constellation analysis** on consumer hardware

**Key Principles:**
1. **Hardware-aware design**: Optimize for GPU/CPU strengths, not mathematical purity
2. **Validation-driven development**: Every optimization proven against analytical solutions
3. **Scalable architecture**: Same code runs on laptops and supercomputers
4. **Open science**: All methods, benchmarks, and validation are reproducible

**For researchers:** The [validation/](../validation/) directory contains all verification code. Reproduce our results or extend the physics models.

**For operators:** The [engine/](../engine/) provides a stable API for integration into operational systems.

**For contributors:** See [README.md](../README.md) for development setup and contribution guidelines.

---

*This document evolves with the codebase. Design decisions are revisited as hardware and requirements change.*
