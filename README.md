# Astrosis

**GPU-accelerated orbital propagation and conjunction analysis with RK4 numerical integration.**

Astrosis propagates satellite orbits using a fourth-order Runge-Kutta integrator with J₂/J₃/J₄ geopotential harmonics, atmospheric drag (US Standard Atmosphere 1976), solar radiation pressure, and lunisolar third-body perturbations. It supports Python, C++ (OpenMP), and CUDA backends with automatic selection at import time.

## Features

- **Numerical propagation** — RK4 integrator with configurable perturbations (J₂–J₄, drag, SRP, Sun, Moon)
- **Conjunction screening** — KDTree broad-phase culling, temporal sweep, Brent's method for sub-second TCA refinement, Chan probability of collision
- **Three backends** — Pure Python / NumPy, C++ OpenMP (pybind11), CUDA GPU — auto-selected by priority
- **Coordinate transforms** — ECI ↔ ECEF ↔ geodetic ↔ topocentric (az/el/range), TEME-to-ECI for SGP4 validation
- **TLE ingestion** — Fetches and caches from Celestrak, validates checksums
- **Visualization** — Dark-theme plots: 3D orbits, conjunction dashboards, scaling reports (matplotlib)

## Quick start

```bash
pip install -r requirements.txt
scripts/build.sh              # build C++/CUDA backends (optional)
python main.py propagate      # propagate ISS for 24 hours
python main.py conjunction    # demo conjunction screening
python -m pytest tests/ -v    # run tests
```

## Project layout

```
engine/              # Python package
  core/              #   propagator, conjunction, accelerator, ephemeris
  geo/               #   coordinate frames (ECI, ECEF, geodetic, topocentric)
  io/                #   TLE download + cache (via Celestrak)
  viz.py             #   plotting (3D orbits, conjunctions, scaling)
  cli.py             #   CLI subcommands
  constants.py       #   physical constants
cpp/                 # C++ / CUDA source (pybind11)
  propagator.cpp     #   Python bindings
  cuda_propagator.cu #   CUDA propagation kernels
  cuda_conjunction.cu#   CUDA conjunction kernels
  cuda_physics.cuh   #   shared device functions
  cuda_bridge.h      #   C API declarations
validation/          # research scripts + plots
tests/               # pytest suite
benchmarks/          # performance benchmarks
```

## Backends

| Backend | Detection | Status |
|---------|-----------|--------|
| CUDA GPU | `cuda_available()` at runtime | Fastest for N ≥ 500 |
| C++ OpenMP | pybind11 module loaded | ~50–500× vs Python |
| NumPy batch | always available | Good for N ≤ 100 |
| Pure Python | always available | Fallback |

The engine selects the best available backend at import time. Call `backend_info()` to see which is active.

## Physical model

- **Gravity:** J₂, J₃, J₄ zonal harmonics (EGM96 coefficients)
- **Atmosphere:** US Standard Atmosphere 1976, piecewise exponential density (0–1000 km)
- **Drag:** Earth-rotation velocity correction, adjustable C<sub>D</sub>
- **SRP:** Cylindrical shadow model, adjustable C<sub>R</sub>
- **Third-body:** Point-mass Sun and Moon (Meeus analytical ephemeris)

## Validation

Energy conservation is better than 1×10⁻⁷ relative over one orbit and 1×10⁻⁵ over 24 hours. RK4 convergence order is verified as O(Δt⁴). Position divergence versus SGP4 is under 10 km at 24 hours including drag and lunisolar perturbations. See `validation/` for scripts and plots.

## Dependencies

- numpy, scipy, matplotlib
- pybind11 (C++ backend)
- httpx (TLE fetching)
- sgp4 (validation reference)
- CUDA Toolkit ≥ 11 (optional, GPU backend)

## License

MIT
