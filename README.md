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

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Build the C++ accelerator (requires CMake + pybind11):
   ```bash
   mkdir -p cpp/build && cd cpp/build
   cmake .. && make
   ```

## Usage

### Command Line Interface

**Predict satellite passes for a location:**
```bash
python main.py passes --id 25544 --lat 51.5 --lon -0.1 --hours 12
```

**Fetch and cache latest TLEs:**
```bash
python main.py fetch --id 25544
```

## Python API

You can use the engine as a library in your own projects:

```python
from engine import FuelTracker, ConjunctionDetector, ObjectState

# Initialize simulation...
detector = ConjunctionDetector()
# ... logic ...
```

## License
Proprietary / Research Use Only.
