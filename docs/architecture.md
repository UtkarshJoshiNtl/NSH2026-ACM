# Architecture & Design

## System Overview

Astrosis uses a **modular, multi-backend architecture** that automatically selects the fastest available hardware for your workload.

```
┌─────────────────────────────────────────────┐
│              User Interfaces                │
├──────────────────┬──────────────────────────┤
│   CLI Tools      │   Python API             │
│   (main.py)      │   (engine.*)             │
└──────────────────┴──────────────────────────┘
                      │
                 ┌──────────▼──────────┐
                 │ Simulation Context  │
                 │ (simulation.py)     │
                 └──────────┬──────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌───────▼─────────┐
│  Physics Core  │ │  Transformations│ │  I/O & Catalog  │
│  (core/*)      │ │  (geo/*)        │ │  (io/*)         │
├────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • Propagator   │ │ • ECI/ECEF      │ │ • TLE parsing   │
│ • Maneuver     │ │ • LLA/Topocen.  │ │ • Ephemeris     │
│ • Conjunction  │ │ • Time systems  │ │ • Data formats  │
│ • Fuel         │ │ • Frame rotations│ │ • CelesTrak API │
└────────────────┘ └─────────────────┘ └─────────────────┘
        │
        │ (auto-detects optimal backend)
        │
        ├──────────────────┬──────────────────┬──────────────┐
        │                  │                  │              │
    ┌───▼──┐          ┌────▼────┐      ┌─────▼────┐   ┌────▼────┐
    │CUDA  │          │  C++    │      │ NumPy    │   │  Pure   │
    │GPU   │          │ OpenMP  │      │ Vectorized   │ Python  │
    └───┬──┘          └────┬────┘      └─────┬────┘   └────┬────┘
        │                  │                  │             │
        └──────────────────┼──────────────────┴─────────────┘
                           │
                ┌──────────▼──────────┐
                │   Numpy Backend     │
                │ (Portable array ops)│
                └─────────────────────┘
```

---

## Backend Selection Strategy

Astrosis automatically chooses the best backend based on hardware availability and problem size:

### Decision Tree

```
┌─ CUDA available?
│  ├─ Yes ──┬─ Problem size > 500 satellites?
│  │        ├─ Yes → Use CUDA (82x speedup)
│  │        └─ No  → Use C++ (lower latency)
│  │
│  └─ No ──┬─ C++ compiled?
│           ├─ Yes → Use C++/OpenMP (18x speedup)
│           │
│           └─ No ──┬─ NumPy available?
│                    ├─ Yes → Use NumPy (3–5x speedup)
│                    └─ No  → Fall back to pure Python
```

### Heuristics & Thresholds

| Factor | Threshold | Decision |
|--------|-----------|----------|
| **Satellites** | < 500 | Prefer C++ (lower launch overhead) |
| **Satellites** | 500–2,000 | CUDA competitive; use available |
| **Satellites** | > 2,000 | Strongly prefer CUDA |
| **Propagation steps** | < 10,000 | CPU typically adequate |
| **Propagation steps** | > 100,000 | CUDA essential for real-time |
| **Integration dt** | > 60 seconds | CPU competitive (fewer steps) |
| **Integration dt** | 1–10 seconds | CUDA advantage grows |

### Manual Backend Override

Users can explicitly specify a backend:

```python
from engine.simulation import SimulationContext, Backend

# Force CUDA (fails gracefully if unavailable)
sim = SimulationContext(backend=Backend.CUDA)

# Force CPU (useful for testing/reproducibility)
sim = SimulationContext(backend=Backend.CPP)

# Force NumPy (for debugging)
sim = SimulationContext(backend=Backend.NUMPY)
```

---

## Module Descriptions

### `engine/core/` — Physics Kernels

**Propagator** (`propagator.py`):
- RK4 numerical integration
- Force computation: J2–J4, drag, SRP, third-body
- State vector: [x, y, z, vx, vy, vz]
- Available in: CUDA, C++/OpenMP, NumPy, Python

**Maneuver** (`maneuver.py`):
- ΔV calculations (impulsive burns)
- Fuel consumption modeling (Tsiolkovsky equation)
- Hohmann transfer design
- Low-thrust spiral optimization (future)

**Conjunction** (`conjunction.py`):
- Pairwise distance computation
- Time-of-Closest-Approach (TCA) refinement
- Collision probability (Chan approximation)
- Spatial partitioning for O(N log N) screening

**Fuel** (`fuel.py`):
- Propellant budget tracking
- Specific impulse (Isp) calculations
- Thruster efficiency models

**Ephemeris** (`ephemeris.py`):
- Solar/lunar position (low-precision analytical)
- Julian Date handling
- Epoch conversions

---

### `engine/geo/` — Coordinate Transformations

**Frames** (`frames.py`):
- ECI ↔ ECEF conversions (with proper pole wandering)
- ECEF → LLA (latitude/longitude/altitude)
- Topocentric coordinates (local horizon system)
- Time system conversions: UTC ↔ TAI ↔ TT

**Analysis** (`analysis.py`):
- Ground visibility calculations
- Elevation/azimuth/range computation
- Rise/set time predictions
- Groundtrack analysis

**Visibility** (`visibility.py`):
- Line-of-sight checks
- Antenna pointing solutions
- Coverage area computation

---

### `engine/io/` — Data I/O

**Data** (`data.py`):
- TLE parsing (Two-Line Element Set format)
- OEM file handling (Orbit Ephemeris Message)
- CSV import/export
- Database interface (future)

**Catalog Integration:**
- CelesTrak API (real-time TLE updates)
- Space-Track.org (historical TLE archive)
- Local file caching

---

### `cpp/` — High-Performance Backends

**Structure:**
```
cpp/
├── CMakeLists.txt          # Build configuration
├── physics_constants.h     # J2, GM, R_E, etc.
├── propagator.cpp/.h       # RK4 implementation
├── conjunction.cpp/.h      # Pairwise screening
├── maneuver.cpp/.h         # Maneuver calculations
├── fuel.cpp/.h             # Fuel modeling
├── cuda_propagator.cu      # CUDA kernel: k_prop_soa
├── cuda_conjunction.cu     # CUDA kernel: k_conjunction
└── cuda_physics.cuh        # CUDA force computation
```

**Build:**
```bash
cd cpp && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_CUDA=ON
make -j$(nproc)
```

---



### `frontend/` — Visualization

**Technology:** Three.js + WebSocket + Plotly

- **3D globe** with satellite orbits
- **Real-time tracking** of constellation
- **Conjunction visualization** (risk heatmap)
- **Ground station footprints**
- **Maneuver planner** interactive tool

---

## Data Flow: Constellation Propagation

**Example:** Propagate 1,000 satellites for 24 hours

```
┌─ User code
│  sim.propagate(satellites, hours=24, dt=10)
│
├─ SimulationContext
│  Detects: 1,000 satellites → CUDA beneficial
│  Selects backend: CUDA (assuming GPU available)
│
├─ Python ↔ C++ FFI (ctypes / pybind11)
│  Pack state vectors into GPU memory
│  SoA layout: [x₁..x₁₀₀₀, y₁..y₁₀₀₀, z₁..z₁₀₀₀, ...]
│  (~48 KB for 1,000 6-element state vectors)
│
├─ GPU Memory Setup
│  Device memory allocation: 100 MB (satellite data + temporaries)
│  Transfer: 48 KB upload (negligible)
│
├─ CUDA Kernel Execution (86,400 steps)
│  Launch grid: 4 blocks × 256 threads (1,024 total threads)
│  Each thread: 1 satellite across all 4 RK4 stages
│  Loop: for each 10-second timestep
│    - k_prop_soa (GPU kernel) evaluates all 1,000 satellites
│    - 4 kernel launches per step (RK4 k1, k2, k3, k4)
│  Total kernel calls: 4 × 86,400 = 345,600
│
├─ GPU Memory Transfer (download results)
│  Final state: 48 KB download
│  Overhead: ~14 ms (negligible vs. 47 ms compute)
│
└─ Return to Python
   Trajectory array: [86,400 timesteps × 1,000 sats × 6 components]
   Time: 46.9 ± 2.1 ms (measured)
```

---

## Precision & Arithmetic

### Default Precision: FP64 (IEEE 754 Double)

**Rationale:**
- Orbital state spans 13 orders of magnitude (position to velocity)
- FP32 mantissa (24 bits) insufficient for differentiation
- Energy conservation requires FP64 for 24-hour stability

**Force Computation:** FP64 throughout

**Storage:** FP64 (future: compression/streaming for large catalogs)

### Mixed-Precision Roadmap (Future)

```python
# Potential future optimization (not current)
# Compute forces in FP32, integrate state in FP64
state = FP64(...)           # Canonical orbital elements
f_accel = ComputeForces(state, precision='FP32')  # 4 KB faster cache
state_new = Integrate(state, f_accel, 'FP64')     # Preserve precision
```

Estimated benefit: 20–30% speedup with < 0.01% accuracy loss (TBD by validation)

---

## Extensibility Points

### Adding a New Force Model

1. Implement acceleration function (e.g., `AccelThirdBodyPluto()`)
2. Register in `ComputeAccel()` dispatcher
3. Add unit tests in `validation/`
4. Benchmark impact on throughput

### Adding a New Coordinate System

1. Implement transformation matrices in `engine/geo/frames.py`
2. Update rotation/velocity chain rule
3. Add round-trip conversion tests

### Adding a New Backend

1. Implement `Backend` interface in `engine/simulation.py`
2. Port physics kernels to target architecture (e.g., OpenCL, HIP)
3. Update backend selection heuristics
4. Benchmark vs. CUDA baseline

---

## API Stability & Versioning

### Current Status: EXPERIMENTAL

The Astrosis API is subject to change before v1.0. Key interfaces may be reorganized:

- **Core API** (propagation, conjunction): Stable
- **Maneuver planning**: Subject to extension (adding constraints, optimization methods)
- **Coordinate transforms**: Stable
- **REST endpoints**: May change paths/parameter names
- **Data formats**: May add compression, streaming support

### Semantic Versioning (post-v1.0)

- **v1.0.0**: First stable release
- **v1.x.0**: Backward-compatible bug fixes & features
- **v2.0.0**: Breaking API changes (major refactor)

### Deprecated Features

None currently; all features pre-v1.0.

---

## Testing & Validation Strategy

- **Unit tests:** `tests/test_*.py`
- **Integration tests:** End-to-end propagation + analysis
- **Physics validation:** `validation/*.py` with analytical/real-world baselines
- **Performance regression:** Automated benchmarking on CI
- **Reproducibility:** Deterministic seeding for all random operations
