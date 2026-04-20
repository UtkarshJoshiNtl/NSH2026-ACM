# Astrosis — Satellite Physics Simulator

A web-based orbital mechanics simulator with a high-performance C++ physics engine and Python API.

## Architecture

```
C++ physics engine → pybind11 → Python FastAPI backend → REST API → HTML/Canvas frontend
```

## Physics engine

| Module | Description |
|---|---|
| `propagator.cpp` | RK4 orbital propagation with J2 perturbation |

**Constants**: μ = 398600.4418 km³/s², Rₑ = 6378.137 km, J₂ = 1.08263×10⁻³

## Features

- **Orbital Propagation**: RK4 integration with J2 Earth oblateness perturbation
- **Real-time Visualization**: Ground track map showing satellite and debris positions
- **Interactive Simulation**: Step forward in time to observe orbital evolution
- **Multi-object Support**: Simulate satellites and debris clouds simultaneously

## Local setup

```bash
# Build C++ engine
cd backend/cpp && mkdir -p build && cd build
cmake -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir) -DPython3_EXECUTABLE=$(which python3) ..
make -j4
cd ../../..

# Install Python dependencies
pip install -r requirements.txt

# Generate initial state data
python3 scripts/generate_initial_state.py

# Run server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Service health and state summary |
| `POST` | `/api/simulate/step` | Advance simulation by N seconds |
| `GET` | `/api/visualization/snapshot` | Get current constellation state |
| `POST` | `/api/telemetry` | Ingest batch object states |

## Roadmap

- Live TLE ingestion from Celestrak
- Atmospheric drag model (NRLMSISE-00)
- 3D orbit visualization
- Public hosted API
