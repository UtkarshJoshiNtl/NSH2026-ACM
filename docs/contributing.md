# Contributing to Astrosis

Thank you for your interest in contributing! This document outlines how to get involved with development, testing, and improvement.

---

## Development Setup

### Clone & Install

```bash
git clone https://github.com/your-org/astrosis.git
cd astrosis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pytest black flake8 mypy
```

### Build C++/CUDA Backends (Optional)

```bash
cd cpp && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_CUDA=ON
make -j$(nproc)
cd ../..
```

---

## Testing Strategy

### Unit Tests

All physics, coordinate transforms, and utility functions have unit tests:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_propagator.py -v

# Run with coverage
python -m pytest tests/ --cov=engine --cov-report=html
```

**Test categories:**
- `tests/test_core.py` — Physics kernels (RK4, forces, energy conservation)
- `tests/test_geo.py` — Coordinate transformations, time systems
- `tests/test_conjunction.py` — Collision detection, TCA refinement
- `tests/test_maneuver.py` — Orbital maneuvers, Hohmann transfers

### Physics Validation

Reproducible validation against analytical solutions and real satellite data:

```bash
# Energy conservation test (24h LEO propagation)
python validation/validate_physics.py --test energy --hours 24

# ISS validation (vs. SGP4 baseline)
python validation/sgp4_vs_rk4.py --id 25544 --hours 24

# RK4 convergence study
python validation/validate_physics.py --test convergence

# J2 precession (analytical comparison)
python validation/validate_physics.py --test j2_precession --days 7

# Atmospheric drag validation
python validation/validate_physics.py --test atmospheric_drag

# Solar radiation pressure validation
python validation/validate_physics.py --test srp_divergence

# Monte Carlo ensemble (100 random orbits, 72h)
python validation/test_monte_carlo.py --cases 100 --hours 72
```

**Expected outputs:**
- Energy conservation: < 1e-7 relative drift
- J2 precession: < 0.03°/day error vs. analytical
- Convergence: Exactly 4th-order (error ratio ≈ 16)
- SRP: Correct mass-dependent acceleration ratios

### Performance Regression Testing

Track performance across code changes:

```bash
# Benchmark key operations
python benchmarks/benchmark.py --repeat 100 --output results.json

# Scaling analysis (1k, 5k, 10k satellites)
python validation/scaling_analysis.py

# CUDA kernel profiling (Nsight Compute)
python scripts/profile_cuda.py --kernel prop_soa --satellites 1000
```

**Performance budgets (approximate):**
- 1,000 satellite, 24h propagation (CUDA): 46.9 ± 2.1 ms
- 400×400 conjunction screening (CUDA): 564 ± 18 ms
- Deviations > 10% warrant investigation

---

## Code Style & Standards

### Python

- **Formatter:** Black (`black engine/`)
- **Linter:** Flake8 (`flake8 engine/ tests/`)
- **Type hints:** MyPy (`mypy engine/`)
- **Docstrings:** Google-style for all public functions

Example:

```python
def propagate(initial_state: np.ndarray, timestep: float, hours: int) -> np.ndarray:
    """Propagate orbital state using RK4 integration.
    
    Args:
        initial_state: 6D state vector [x, y, z, vx, vy, vz] in ECI, meters/sec
        timestep: Integration step in seconds
        hours: Propagation duration in hours
        
    Returns:
        Trajectory: [steps × 6] array of state vectors
        
    Raises:
        ValueError: If timestep or hours invalid
    """
```

### C++/CUDA

- **Standard:** C++20 with CUDA 12.x
- **Style:** Google C++ Guide + NVIDIA CUDA best practices
- **Comments:** Explain non-obvious optimizations (e.g., SoA vs. AoS)
- **Register limits:** Keep per-thread register count < 100

---

## Areas for Contribution

### Physics Models (Medium Difficulty)

- [ ] Higher-order gravity harmonics (J5, J6)
- [ ] Improved atmospheric drag model (NRLMSISE-00)
- [ ] Solid Earth tides
- [ ] Relativistic effects (for GEO/HEO)
- [ ] Albedo and infrared radiation pressure

**How to add:**
1. Implement acceleration function
2. Register in `ComputeAccel()` dispatcher
3. Add unit test in `tests/test_core.py`
4. Validate against analytical formula
5. Benchmark impact on throughput

### Numerical Methods (Hard)

- [ ] Adaptive Runge-Kutta (RK45) for CPU
- [ ] Symplectic integrators (Störmer-Verlet)
- [ ] Bulirsch-Stoer for ultra-high precision
- [ ] Split-step methods (preserving energy)

**Consideration:** GPU requires fixed timesteps; CPU can use adaptive.

### Backends & Acceleration (Medium-Hard)

- [ ] Vulkan compute shaders (cross-platform GPU)
- [ ] ARM GPU support (Mali, Adreno)
- [ ] Apple Metal acceleration
- [ ] Intel OneAPI/SYCL for CPUs
- [ ] Distributed computing (multi-GPU, MPI)

### Applications (Easy-Medium)

- [ ] Launch window optimizer
- [ ] Re-entry prediction tool
- [ ] Debris propagation module
- [ ] Mega-constellation analyzer
- [ ] Live tracking dashboard improvements

### Documentation (Easy)

- [ ] Jupyter notebooks with examples
- [ ] Performance tuning guide
- [ ] Physics model documentation
- [ ] API reference expansion
- [ ] Tutorial videos (orbital mechanics basics)

### Testing & Validation (Easy-Medium)

- [ ] Additional test cases (highly eccentric orbits, GEO, etc.)
- [ ] Comparison with published benchmarks
- [ ] CI/CD pipeline improvements
- [ ] Code coverage analysis
- [ ] Profiling & optimization reports

---

## Pull Request Workflow

1. **Fork & branch**
   ```bash
   git checkout -b feature/my-contribution
   ```

2. **Develop & test**
   ```bash
   # Make changes, add tests
   pytest tests/  # Run full suite
   black engine/
   flake8 engine/
   ```

3. **Commit with clear messages**
   ```bash
   git commit -m "Add [feature]: description

   - Specific implementation detail
   - Test coverage added
   - Performance impact (if any)
   ```

4. **Push & create PR**
   ```bash
   git push origin feature/my-contribution
   # Open PR on GitHub with description
   ```

5. **Address review feedback**
   - Respond to code review comments
   - Re-run full test suite
   - Update documentation as needed

---

## Reporting Issues

### Bug Reports

Include:
- **Minimal reproduction case** (code snippet)
- **Expected vs. actual behavior**
- **Environment** (OS, Python version, CUDA version if applicable)
- **Error message** (full traceback)

Example:
```markdown
### Energy Conservation Test Failing on RTX 3060

**Actual:** Energy drift = 1e-5 (too high)
**Expected:** < 1e-7

**Reproduction:**
```python
sat = load_tle("25544")
traj = propagate(sat, hours=24, dt=10)
energy_error = check_energy_conservation(traj)
assert energy_error < 1e-7  # Fails with 1.2e-5
```

**Environment:** RTX 3060, CUDA 12.4, Python 3.11
```

### Feature Requests

Describe:
- **Problem it solves**
- **Example use case**
- **Proposed implementation** (if known)
- **Estimated complexity** (easy/medium/hard)

---

## Design Discussions

For major changes, open a Discussion or Issue first:
- Is a new force model worth the complexity?
- Should we support a new integration method?
- How should we handle uncertainty propagation?

This helps align on direction before significant implementation effort.

---

## Recognition

Contributors are recognized in release notes for each version and the GitHub contributor graph.

---

## Questions?

- **Technical questions:** Open a GitHub Issue with `[question]` tag
- **Design discussions:** Use GitHub Discussions
- **Quick clarifications:** Tag @maintainers in comments

---

**Thank you for improving Astrosis!**
