# Astrosis — GPU-Accelerated Orbital Propagation and Conjunction Analysis Engine

[![Backend: CUDA](https://img.shields.io/badge/Backend-CUDA_12.9-76b900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)
[![Backend: C++](https://img.shields.io/badge/Backend-C++17-00599C?logo=c%2B%2B)](https://isocpp.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

High-throughput orbital propagation and all-pairs conjunction screening
using RK4 integration with J2/J3/J4 gravity harmonics, atmospheric drag,
and GPU/CPU architecture-aware optimisation.

## Core Features

- **RK4 propagation** with J2/J3/J4 perturbations, US Standard Atmosphere 1976
  drag, SRP with cylindrical shadow, and lunisolar third-body effects
- **OpenMP + CUDA** multi-backend architecture with automatic backend selection
- **SoA memory layout** achieving 100 % cache utilisation vs 17 % for AoS
- **Brent-method TCA refinement** converging to < 0.1 s accuracy
- **All-pairs conjunction screening** with Chan's probability of collision
- **Validation suite** (energy conservation, convergence order, SGP4 comparison)

## Performance

| Operation | Python | C++ (speedup) | CUDA (speedup) |
|-----------|--------|---------------|----------------|
| Single propagation (50 k steps) | 395 ms | 21.9 ms (18×) | N/A |
| Batch propagation (1 k sats × 24 h) | 7 034 ms | 13.9 ms (507×) | 46.9 ms (150×) |
| Conjunction screening (400 × 400 pairs) | 46 718 ms | 5 159 ms (9×) | 564 ms (83×) |

Hardware: Intel i7-1260P, RTX 2050 (16 SMs). See [docs/performance.md](docs/performance.md)
for full methodology.

## Project Scope

**Astrosis is:**
- A high-performance orbital propagation engine (RK4, J2/J3/J4, drag, SRP)
- A GPU-accelerated conjunction screening system (all-pairs, Brent TCA, Chan Pc)
- A validated, benchmarked HPC / scientific computing project

**Astrosis is not:**
- An operational SSA platform
- A flight-certified system
- A complete mission-planning suite
- A replacement for NASA GMAT or AGI STK

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Build C++ and CUDA backends (optional but recommended)
scripts/build.sh

# Run the test suite
python -m pytest tests/test_correctness.py -v

# Run physics validation
python validation/validate_physics.py

# Run performance benchmark
python benchmarks/benchmark.py --quick
```

### CLI Demo

```bash
# Propagate the ISS for 24 hours
python main.py propagate

[INFO] Propagated ISS for 8640 steps (dt=10s, total=86400s)
[INFO]   Final state: x=3775.99 y=5537.37 z=-1128.68 km
[INFO]   Final velocity: vx=-4.5358 vy=1.9028 vz=-5.8737 km/s
[INFO]   Max energy drift: 8.35e-06 (target < 1e-5)

# Demo conjunction screening
python main.py conjunction

[INFO] Conjunction: sat=0 debris=0 distance=0.0500 km TCA=0.0s severity=CRITICAL
```

## Project Structure

```
engine/       → Python orchestration + physics kernels
├── core/     →   propagator, conjunction, ephemeris, accelerator
├── geo/      →   coordinate frames, visibility
├── io/       →   TLE ingestion
└── simulation.py  orchestration wrapper

cpp/          → C++17 + CUDA backends (pybind11)
├── propagator.cpp/h
├── conjunction.cpp/h
├── cuda_propagator.cu
├── cuda_conjunction.cu
└── ...

validation/   → Numerical verification suite + plots
benchmarks/   → Reproducible performance benchmarks
docs/         → Design, performance, validation, limitations
tests/        → Physics correctness tests
```

## Validation

| Test | Result |
|------|--------|
| Energy conservation | < 1 × 10⁻⁷ relative drift over 24 h |
| RK4 convergence | 4th-order verified (16× error reduction per dt halving) |
| SGP4 comparison | < 10 km position error at 24 h |
| J2 nodal regression | < 0.03 °/day accuracy |

All validation code is in `validation/` and is fully reproducible. See
[docs/validation.md](docs/validation.md) for methodology.

## Technical Deep Dives

- [Design Decisions](docs/design.md) — RK4 vs adaptive, J2–J4 selection,
  GPU memory layouts, false sharing, TCA refinement
- [Performance Analysis](docs/performance.md) — Roofline, occupancy, strong/weak
  scaling, CUDA crossover, AoS vs SoA
- [Validation Methodology](docs/validation.md) — Numerical verification approach
- [Known Limitations](docs/limitations.md) — Where and why the model breaks down

## References

- Vallado, D. *Fundamentals of Astrodynamics and Applications* (4th ed.)
- Montenbruck, O. & Gill, E. *Satellite Orbits* (1st ed.)
- Brent, R. P. *Algorithms for Minimization without Derivatives* (1973)
- Chan, K. *Improved Analytical Expressions for Computing Satellite Collision
  Probabilities* (AAS 03-184)
