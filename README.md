# Astrosis - Autonomous Constellation Manager

**NSH 2026 IITD Hackathon - Orbital Debris Avoidance & Constellation Management System**

A high-performance autonomous constellation management system designed for the National Space Hackathon 2026. Features J2-aware RK4 propagation, real-time conjunction detection, autonomous collision avoidance, and mission control visualization.

## Features (NSH 2026 Compliant)

- **J2-Aware Propagation**: RK4 integrator with Earth's J2 zonal harmonic perturbation
- **Conjunction Detection**: Real-time collision warning with <100m critical threshold
- **Autonomous Collision Avoidance**: Evasion and recovery maneuver calculation
- **RTN Navigation**: Maneuver planning in Radial-Transverse-Normal frame
- **Ground Station LOS**: Line-of-sight communication with Earth rotation
- **Fuel Management**: Tsiolkovsky rocket equation with EOL graveyard orbit
- **Real-Time Visualization**: Ground track map, bullseye plot, fuel gauges, Gantt timeline
- **WebSocket Streaming**: 2-second telemetry update intervals

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │  Physics Engine │
│   (D3.js/HTML)  │◄──►│   (FastAPI)     │◄──►│  (Python/C++)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.10+
- Docker (for deployment)
- CMake 3.12+ (optional, for C++ physics engine)
- C++17 compatible compiler (optional)

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/UtkarshJoshiNtl/NSH2026-ACM.git
cd Astrosis
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Build the C++ physics engine:
```bash
cd backend/cpp
mkdir build
cd build
cmake ..
make -j$(nproc)
cd ../../..
```

**Note**: The system will automatically fall back to pure Python if C++ engine is not built.

### Frontend Setup

The frontend is served statically by the backend. No additional setup required.

## Running the Application

### Development Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- Frontend: http://localhost:8000
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/api/health

### Docker Deployment (NSH 2026 Requirement)

```bash
docker build -t astrosis .
docker run -p 8000:8000 astrosis
```

## API Documentation (NSH 2026 Compliant)

### Required Endpoints

#### Telemetry Ingestion (Section 4.1)
```http
POST /api/telemetry
```
Accepts high-frequency state vector updates for satellites and debris.

#### Maneuver Scheduling (Section 4.2)
```http
POST /api/maneuver/schedule
```
Submit evasion and recovery burn sequences with validation.

#### Simulation Fast-Forward (Section 4.3)
```http
POST /api/simulate/step
```
Advance simulation by specified time step.

#### Visualization Snapshot (Section 6.3)
```http
GET /api/visualization/snapshot
```
Get current simulation state for frontend rendering.

#### Propagation
```http
POST /api/propagation/propagate
POST /api/propagation/conjunction
```
Propagate state vectors and detect conjunctions.

Full API documentation available at `/docs` (Swagger UI).

## Physics Constants (NSH 2026 Compliant)

The following constants are configured in `backend/config.py`:

- **Dry Mass (mdry)**: 500.0 kg
- **Initial Propellant Mass (mfuel)**: 50.0 kg
- **Specific Impulse (Isp)**: 300.0 s
- **Maximum Thrust Limit**: |∆⃗v| ≤ 15.0 m/s per burn
- **Thermal Cooldown**: 600 seconds between burns
- **Station-Keeping Box**: ±10 km spherical radius
- **Critical Conjunction Threshold**: < 100 meters
- **EOL Fuel Threshold**: < 5% fuel

## Testing

### Run Physics Engine Tests

```bash
python test_physics.py
```

## Deployment Requirements (NSH 2026)

- **Dockerfile**: Must use `ubuntu:22.04` base image
- **Port Binding**: Must expose port 8000 on 0.0.0.0
- **API Endpoints**: Must implement all required NSH 2026 endpoints

## Project Structure

```
Astrosis/
├── backend/                # FastAPI backend
│   ├── main.py            # API entry point
│   ├── config.py          # Configuration
│   ├── core/              # Core logic
│   │   ├── physics/       # Physics engine (J2+RK4)
│   │   ├── navigation.py  # RTN frame navigation
│   │   ├── ground_station.py # LOS calculations
│   │   ├── decision_service.py # Autonomous logic
│   │   └── state_manager.py # Simulation state
│   └── routers/           # API endpoints
│       ├── telemetry.py   # Telemetry ingestion
│       ├── simulate.py    # Simulation control
│       ├── visualization.py # Snapshot endpoint
│       └── propagation.py # Propagation & conjunction
├── frontend/              # D3.js visualization
├── data/                  # Ground stations, catalog
├── Dockerfile             # Ubuntu 22.04 base
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

Developed for the **National Space Hackathon 2026** at Indian Institute of Technology, Delhi.
