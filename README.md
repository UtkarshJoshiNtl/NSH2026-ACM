# Astrosis — Satellite Physics Simulator API

A high-performance satellite propagation API service with a C++ physics engine, PostgreSQL database, Redis caching, and multi-tenant simulation contexts.

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

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register a new user account |
| `POST` | `/api/auth/login` | Login with email/password |
| `POST` | `/api/auth/api-keys` | Create a new API key |
| `GET` | `/api/auth/api-keys` | List user's API keys |
| `DELETE` | `/api/auth/api-keys/{key_id}` | Delete an API key |

### Simulation Contexts

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/simulations` | Create a new simulation context |
| `GET` | `/api/simulations` | List user's simulations |
| `GET` | `/api/simulations/{id}` | Get simulation details |
| `DELETE` | `/api/simulations/{id}` | Delete a simulation |
| `GET` | `/api/simulations/{id}/state` | Get simulation state summary |

### TLE Data

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/tle/groups` | Get available satellite groups |
| `POST` | `/api/tle/ingest` | Ingest TLE data from Celestrak |
| `POST` | `/api/tle/import` | Import a satellite from TLE |
| `POST` | `/api/tle/import-group` | Import a satellite group |

## Roadmap

- ✅ Live TLE ingestion from Celestrak
- ✅ Multi-tenant simulation contexts
- ✅ API key authentication and rate limiting
- ✅ PostgreSQL database persistence
- ✅ Redis caching layer
- Atmospheric drag model (NRLMSISE-00)
- 3D orbit visualization
- Public hosted API deployment
