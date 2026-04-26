# Astrosis - Satellite Physics Simulator

**Production-ready satellite constellation management system with advanced features beyond NSH 2026 requirements.**

A high-fidelity orbital mechanics simulation platform for satellite constellation management, conjunction detection, and debris tracking. Features a C++ physics engine with RK4 integrator, J2/J3/J4 perturbations, third-body effects, atmospheric drag, solar radiation pressure, FastAPI backend, multi-tenancy, authentication, and real-time web visualization.

**Note**: For NSH 2026 IITD Hackathon compliance, use the `main` branch. This `v2` branch includes advanced production features.

## Features

- **High-Fidelity Physics Engine**: C++ implementation with RK4 integrator and J2 perturbation
- **Conjunction Detection**: Real-time collision warning system with configurable thresholds
- **Maneuver Planning**: Automated evasion and recovery maneuver calculation
- **Multi-Tenancy**: Support for multiple isolated simulation contexts
- **TLE Integration**: Import satellite data from Celestrak Two-Line Element sets
- **Real-Time Visualization**: Web-based ground track display with satellite and debris clouds
- **API Authentication**: Secure API key-based authentication with rate limiting
- **Structured Logging**: JSON logging with correlation IDs for distributed tracing

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │  C++ Physics    │
│   (HTML/JS)     │◄──►│   (FastAPI)     │◄──►│  Engine         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  PostgreSQL/    │
                       │  SQLite DB      │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │     Redis       │
                       │   (Cache/Rate)  │
                       └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ (or SQLite for development)
- Redis 6+ (optional, for caching and rate limiting)
- CMake 3.12+ (for building C++ physics engine)
- C++17 compatible compiler

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/UtkarshJoshiNtl/Astrosis.git
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

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/astrosis

# Redis (optional but recommended)
REDIS_URL=redis://localhost:6379/0

# Security (REQUIRED - generate strong secrets)
SECRET_KEY=your-secret-key-here

# Physics engine
PHYSICS_ENGINE_PATH=./backend/cpp/build/physics_engine.so
```

5. Build the C++ physics engine:
```bash
cd backend/cpp
mkdir build
cd build
cmake ..
make -j$(nproc)
cd ../../..
```

**Note**: If CMake cannot find pybind11, install it first:
```bash
pip install pybind11
# Or specify the path if using user installation:
cmake .. -Dpybind11_DIR=/path/to/pybind11/share/cmake/pybind11
```

6. Initialize the database:
```bash
python scripts/init_db.py
```

7. Generate initial simulation state:
```bash
python scripts/generate_initial_state.py
```

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

### Production Deployment

Use a production ASGI server like Gunicorn with Uvicorn workers:

```bash
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Documentation

### Authentication

All API endpoints require authentication via API key. Include the key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/health
```

### Key Endpoints

#### Simulation Control

- `POST /api/simulate/step` - Advance simulation by specified time
- `GET /api/visualization/snapshot` - Get current simulation state
- `POST /api/telemetry` - Ingest satellite/debris telemetry

#### TLE Management

- `GET /api/tle/groups` - List available satellite groups
- `POST /api/tle/fetch-group` - Fetch TLE data for a group
- `POST /api/tle/import-group` - Import satellites from TLE group

#### Propagation

- `POST /api/propagation/propagate` - Propagate state vector
- `POST /api/propagation/conjunction` - Detect conjunctions

#### Authentication

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `POST /api/auth/api-keys` - Create new API key

Full API documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Configuration

### Database Configuration

PostgreSQL is recommended for production. SQLite can be used for development:

```bash
# Development (SQLite)
DATABASE_URL=sqlite:///./astrosis.db

# Production (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/astrosis
```

### Rate Limiting

Configure rate limits per user tier in `.env`:

```bash
RATE_LIMIT_FREE=100      # requests per minute
RATE_LIMIT_PRO=1000
RATE_LIMIT_ENTERPRISE=10000
```

### Physics Constants

Configure propulsion and physics parameters:

```bash
ISP=300.0                # Specific impulse (s)
G0=0.00980665           # Standard gravity (km/s²)
DRY_MASS=500.0          # Satellite dry mass (kg)
INITIAL_FUEL=50.0       # Initial fuel (kg)
MAX_DV=0.015            # Maximum delta-v per maneuver (km/s)
COOLDOWN_S=600.0        # Maneuver cooldown (s)
```

## Testing

### Run Physics Engine Tests

```bash
python test_physics.py
```

### Run Backend Tests

```bash
pytest tests/
```

## Development Guidelines

### Code Style

- Python: Follow PEP 8
- C++: Follow Google C++ Style Guide
- JavaScript: Follow Airbnb Style Guide

### Adding New Features

1. Create feature branch: `git checkout -b feature/name`
2. Implement feature with tests
3. Update documentation
4. Submit pull request

### Physics Engine Extensions

To add new physics features:

1. Add function to C++ header (`backend/cpp/propagator.h`)
2. Implement in C++ (`backend/cpp/propagator.cpp`)
3. Add pybind11 bindings
4. Add Python wrapper in `backend/core/physics/engine.py`
5. Add fallback implementation in `backend/core/physics/fallback.py`

## Troubleshooting

### C++ Build Fails

Ensure you have CMake 3.12+ and a C++17 compiler:

```bash
cmake --version  # Should be 3.12+
g++ --version    # Should support C++17
```

### Database Connection Errors

Check that PostgreSQL is running and credentials in `.env` are correct:

```bash
psql -h localhost -U user -d astrosis
```

### Redis Connection Errors

Redis is optional. If not available, caching and rate limiting will be disabled with a warning. To run Redis:

```bash
redis-server
```

### Physics Engine Not Loading

If the C++ engine fails to load, the system will automatically fall back to the Python implementation. Check the build output:

```bash
cd backend/cpp/build
make VERBOSE=1
```

## Performance Tips

- Use PostgreSQL instead of SQLite for production
- Enable Redis for caching and rate limiting
- Use the C++ physics engine for large-scale simulations
- Configure appropriate rate limits for your use case
- Use connection pooling for database connections

## Security Considerations

- Never commit `.env` files or API keys
- Use strong, randomly generated SECRET_KEY
- Enable HTTPS in production
- Regularly rotate API keys
- Monitor rate limiting logs for abuse

## License

[Your License Here]

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## Support

For issues and questions:
- GitHub Issues: https://github.com/UtkarshJoshiNtl/Astrosis/issues
- Documentation: https://github.com/UtkarshJoshiNtl/Astrosis/wiki

## Acknowledgments

- Celestrak for TLE satellite data
- Skyfield library for orbital mechanics calculations
- pybind11 for Python-C++ integration
