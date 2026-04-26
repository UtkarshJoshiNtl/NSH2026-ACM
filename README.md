# Astrosis - Autonomous Constellation Manager

**National Space Hackathon 2026 IITD Hackathon Submission**

This is the official hackathon submission for the National Space Hackathon 2026 at Indian Institute of Technology, Delhi. The system implements autonomous constellation management with real-time collision avoidance, J2-aware orbital propagation, and comprehensive mission control visualization.

**Note**: This branch contains the hackathon submission code. Active development continues in the `v2` branch.

## Features

- **J2-Aware Propagation**: RK4 integrator with Earth's J2 zonal harmonic perturbation
- **Conjunction Detection**: Real-time collision warning with KD-Tree optimization (O(N log N))
- **Autonomous Collision Avoidance**: Evasion and recovery maneuver calculation
- **RTN Navigation**: Maneuver planning in Radial-Transverse-Normal frame
- **Ground Station LOS**: Line-of-sight communication with Earth rotation
- **Fuel Management**: Tsiolkovsky rocket equation with EOL graveyard orbit
- **Real-Time Visualization**: Ground track map, bullseye plot, fuel gauges, Gantt timeline
- **WebSocket Streaming**: Real-time telemetry updates

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │
│   (D3.js/HTML)  │◄──►│   (FastAPI)     │
└─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Physics Engine │
                       │  (Pure Python)  │
                       └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Docker (for deployment)

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/UtkarshJoshiNtl/NSH2026-ACM.git
cd Astrosis
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Frontend Setup

The frontend is served statically by the backend. No additional setup required.

## Running the Application

### Development Server

```bash
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- Frontend: http://localhost:8000
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/api/health

### Docker Deployment

```bash
docker build -t astrosis .
docker run -p 8000:8000 astrosis
```

## API Documentation

### Required Endpoints (NSH 2026 Compliant)

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

Full API documentation available at `/docs` (Swagger UI).

## Physics Constants (NSH 2026 Compliant)

- **Dry Mass (mdry)**: 500.0 kg
- **Initial Propellant Mass (mfuel)**: 50.0 kg
- **Specific Impulse (Isp)**: 300.0 s
- **Maximum Thrust Limit**: |∆⃗v| ≤ 15.0 m/s per burn
- **Thermal Cooldown**: 600 seconds between burns
- **Station-Keeping Box**: ±10 km spherical radius
- **Critical Conjunction Threshold**: < 100 meters
- **EOL Fuel Threshold**: < 5% fuel

## Project Structure

```
Astrosis/
├── backend/                # FastAPI backend
│   ├── main.py            # API entry point
│   ├── core/              # Core logic
│   │   ├── physics.py     # J2+RK4 physics engine
│   │   ├── navigation.py  # RTN frame navigation
│   │   ├── screening.py   # KD-Tree conjunction detection
│   │   ├── autonomy_logic.py # Autonomous decision logic
│   │   └── state_manager.py # Simulation state
│   ├── routers/           # API endpoints
│   │   ├── rulebook_api.py # NSH 2026 compliant endpoints
│   │   ├── telemetry.py   # Telemetry ingestion
│   │   ├── maneuvers.py   # Maneuver scheduling
│   │   └── auth.py        # Authentication
│   └── services/          # Background services
├── frontend/              # D3.js visualization
├── data/                  # Ground stations, catalog
├── Dockerfile             # Ubuntu 22.04 base
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

Developed for the **National Space Hackathon 2026** at Indian Institute of Technology, Delhi.
