# Astrosis: Orbital Analysis Engine

A high-performance orbital simulation and analysis engine for satellite situational awareness (SSA) and mission planning.

## Features

- **High-Fidelity Propagation**: RK4 numerical integration with J2 perturbation and US Standard Atmosphere 1976 drag model.
- **Full Python Parity**: Every physics component has a pure Python implementation for maximum portability, with an optional C++ accelerator for high-performance batch processing.
- **Conjunction Analysis**: Temporal sweep and spatial culling (KD-Tree) for detecting close approaches between satellites and debris.
- **Maneuver Planning**: Automated impulsive burn calculation (Radial-Normal strategy) for evasion and station-keeping, including fuel budgeting.
- **Coordinate Systems**: Support for ECI (pseudo-J2000), ECEF (WGS-84), Geodetic, and Topocentric (AER) frames.
- **Visibility & Eclipse**: Precise Earth shadow modeling (Conical Umbra/Penumbra) and ground station line-of-sight analysis.
- **Live Data**: Seamless ingestion and local caching of TLE data from CelesTrak.

## Architecture

The project is structured as a clean Python package with an optional C++ accelerator:

```
Astrosis/
├── engine/               # Core Engine Package
│   ├── physics/          # Physics & Mathematical logic
│   │   ├── propagator.py # Numerical integrators
│   │   ├── conjunction.py# Collision detection
│   │   ├── maneuver.py   # Burn planning
│   │   ├── fuel.py       # Propellant tracking
│   │   └── accelerator.py# C++ Bridge & Fallback routing
│   ├── frames.py         # Coordinate conversions
│   ├── visibility.py     # Optical visibility & eclipse
│   ├── data.py           # TLE ingestion & caching
│   ├── simulation.py     # State management
│   ├── analysis.py       # High-level reporting
│   └── cli.py            # Command-line interface
├── cpp/                  # Optional C++ High-Performance Source
├── main.py               # Package Entry Point
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.10+
- (Optional) CMake 3.15+ for C++ accelerator
- (Optional) C++ compiler with C++17 support

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Build the C++ accelerator:
   ```bash
   mkdir -p cpp/build && cd cpp/build
   cmake .. && make
   ```

## Usage

### Command Line Interface

Astrosis provides a comprehensive CLI for satellite analysis:

```bash
# Fetch TLE data from CelesTrak
python main.py fetch

# Fetch specific satellite TLE
python main.py fetch --id 25544

# Force refresh from remote
python main.py fetch --force

# Predict satellite passes for a ground station
python main.py passes --id 25544 --lat 51.5 --lon -0.1 --hours 12

# With physical parameters for drag modeling
python main.py passes --id 25544 --lat 28.5 --lon -80.6 --alt 0.05 \
  --hours 24 --area 15.0 --mass 420000 --cd 2.2 --output passes.json

# Run propagation simulation
python main.py run --steps 1000 --dt 60.0
```

### CLI Options

**`fetch` command:**
- `--id`: Specific NORAD ID to fetch
- `--force`: Force refresh from CelesTrak bypassing cache

**`passes` command:**
- `--id`: NORAD ID of satellite (required)
- `--lat`: Ground station latitude in degrees (required)
- `--lon`: Ground station longitude in degrees (required)
- `--alt`: Ground station altitude in km (default: 0)
- `--hours`: Hours to simulate (default: 24)
- `--area`: Satellite cross-section area in m² (default: 10)
- `--mass`: Satellite mass in kg (default: 1000)
- `--cd`: Drag coefficient (default: 2.2)
- `--output`: Output JSON file for results

## Python API

Use the engine as a library:

```python
from engine import SimulationContext
from engine.data import tle_ingestor
from engine.analysis import report_passes
from datetime import datetime, timezone

# Fetch TLE data
satellites = tle_ingestor.get_satellites()

# Predict passes
result = report_passes(
    norad_id=25544,
    lat=51.5074,  # London
    lon=-0.1278,
    alt=0.0,
    start_dt=datetime.now(timezone.utc).replace(tzinfo=None),
    hours=24
)

for p in result['passes']:
    print(f"Pass at {p['max_elevation_time']} - Max elevation: {p['elevation_max']:.1f}°")
```

## Performance Benchmarks

See `benchmark_results.md` for detailed performance comparisons:

| Operation | Python | C++ (speedup) |
|-----------|--------|---------------|
| Single propagation (5,000 iters) | 35.8 ms | 2.7 ms (×13.4) |
| Batch (200 sats × 100 steps) | 147.5 ms | 1.8 ms (×83.7) |
| Conjunction (100×100 pairs, 2h) | 518.1 ms | 37.4 ms (×13.9) |

## Architecture Details

- **RK4 Integration**: Fourth-order Runge-Kutta numerical propagation
- **J2 Perturbation**: Earth's oblateness modeling for accurate orbits
- **US Standard Atmosphere 1976**: Atmospheric density model for drag
- **Conical Shadow Model**: Precise Earth eclipse calculations

## License

Proprietary / Research Use Only.
