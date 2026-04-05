# Astrosis — Orbital Intelligence API

A high-performance orbital mechanics engine written in C++ with a Python API, for real-time conjunction assessment and collision avoidance.

## Architecture

```
C++ physics engine → pybind11 → Python FastAPI backend → REST API → HTML/Canvas frontend
```

## Physics engine

| Module | Description |
|---|---|
| `propagator.cpp` | RK4 orbital propagation with J2 perturbation |
| `fuel.cpp` | Tsiolkovsky fuel depletion (Isp=300s, g₀=9.80665 m/s²) |
| `conjunction.cpp` | KD-Tree CDM detection (O(S·T·log N)) |
| `maneuver.cpp` | RTN-frame evasion + recovery burn planning |

**Constants**: μ = 398600.4418 km³/s², Rₑ = 6378.137 km, J₂ = 1.08263×10⁻³

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

## Docker

```bash
docker build -t astrosis .
docker run -p 8000:8000 astrosis
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/telemetry` | Ingest batch object states |
| `POST` | `/api/maneuver/schedule` | Schedule evasion + recovery burns |
| `POST` | `/api/simulate/step` | Advance simulation by N seconds |
| `GET` | `/api/visualization/snapshot` | Get current constellation state |

## Roadmap

- Live TLE ingestion from Celestrak
- Atmospheric drag model (NRLMSISE-00)
- Public hosted API
