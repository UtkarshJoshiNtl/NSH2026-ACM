# NSH 2026 — Autonomous Constellation Manager (ACM)

![Python](https://img.shields.io/badge/python-3.10-blue) ![C++](https://img.shields.io/badge/C%2B%2B-17-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green) ![Docker](https://img.shields.io/badge/Docker-ubuntu%3A22.04-orange)

Autonomous satellite constellation manager with real-time conjunction assessment and collision avoidance, built for the **National Space Hackathon 2026** at IIT Delhi.

## Architecture

```
ACM/
├── backend/
│   ├── cpp/            # C++ physics engine (RK4 + J2, KD-Tree CDM, RTN maneuvers)
│   ├── core/           # Python logic layer
│   ├── routers/        # FastAPI route handlers
│   └── main.py         # App entry point (port 8000)
├── data/
│   ├── ground_stations.csv
│   ├── initial_satellites.json  (55 satellites)
│   └── initial_debris.json      (10,000 debris)
├── frontend/           # HTML/Canvas dashboard
├── scripts/
│   └── generate_initial_state.py
├── Dockerfile
└── requirements.txt
```

## Physics Engine (C++)

| Module | Description |
|---|---|
| `propagator.cpp` | RK4 orbital propagation with J2 perturbation |
| `fuel.cpp` | Tsiolkovsky fuel depletion (Isp=300s, g₀=9.80665 m/s²) |
| `conjunction.cpp` | KD-Tree CDM detection (O(S·T·log N)) |
| `maneuver.cpp` | RTN-frame evasion + recovery burn planning |

**Constants**: μ = 398600.4418 km³/s², Rₑ = 6378.137 km, J₂ = 1.08263×10⁻³

## 🐳 Docker Deployment (NSH 2026 Phase 6 Compliance)

The application is containerized for consistent deployment across environments.

### 1. Build the Image
```bash
docker build -t acm-nsh2026 .
```

### 2. Run the Container
```bash
docker run -p 8000:8000 acm-nsh2026
```

### 3. Verification
Once the container is running, access the dashboard at:
**[http://localhost:8000](http://localhost:8000)**

---

## 🛠 Features (Alpha v2.0)
- **Autonomous COLA Loop**: Real-time C++ physics-driven conjunction detection and evasion.
- **Multi-Panel Dashboard**: 
  - **Ground Track**: Real-time map with 10k+ debris objects.
  - **Risk Bullseye**: Polar plot for immediate conjunction assessment.
  - **Fuel Heatmap**: Critical fuel status tracking for all satellites.
  - **Gantt Timeline**: Maneuver schedule and execution windows.
- **Maneuver History**: Complete log of executed burns via `/api/history/maneuvers`.

## Quick Start

### Local (with venv)
```bash
# Build C++ engine
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd backend/cpp && mkdir -p build && cd build
cmake -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir) -DPython3_EXECUTABLE=$(which python3) ..
make -j4
cd ../../..

# Generate initial state data
python3 scripts/generate_initial_state.py

# Run server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker
```bash
docker build -t acm-nsh2026 .
docker run -p 8000:8000 acm-nsh2026
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/telemetry` | Ingest batch object states |
| `POST` | `/api/maneuver/schedule` | Schedule evasion + recovery burns |
| `POST` | `/api/simulate/step` | Advance simulation by N seconds |
| `GET` | `/api/visualization/snapshot` | Get current constellation state |

## Test
```bash
# Run physics test suite
python3 test_physics.py

# Test API
curl -X POST http://localhost:8000/api/simulate/step \
     -H "Content-Type: application/json" \
     -d '{"step_seconds": 3600}'
```

## Physics Constraints
- Max |Δv| per burn: **15.0 m/s**
- Thruster cooldown: **600 s**
- EOL fuel threshold: **< 5% of initial** → graveyard maneuver
- Dry mass: **500 kg** | Initial fuel: **50 kg** | Wet mass: **550 kg**
- Conjunction thresholds: CRITICAL < 100 m | WARNING < 1 km | WATCH < 5 km
