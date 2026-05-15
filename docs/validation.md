# Validation Methodology

> Every numerical claim in Astrosis is backed by a reproducible test. This
> document describes the validation approach, the specific tests, and how to
> reproduce the results.

## Principles

1. **Test against analytical solutions** where available (two-body energy,
   J2 nodal regression).
2. **Test against established models** (SGP4 for position comparison).
3. **Test convergence order** (RK4 must show exactly 4th-order error reduction).
4. **All tests produce plots.** Each run generates a timestamped PNG for
   visual inspection.

## Running the Suite

```bash
# Physics validation (5 tests, produces 5 plots)
python validation/validate_physics.py

# SGP4 comparison (72 h propagation)
python validation/sgp4_vs_rk4.py

# Scaling analysis (strong, weak, CUDA crossover)
python validation/scaling_analysis.py

# Roofline model
python validation/cuda_roofline.py

# Monte Carlo Pc test (GPU)
python validation/test_monte_carlo.py
```

All plots are written to `validation/plots/`.

## Test Descriptions

### 1. Energy Conservation

**File:** `validate_physics.py` — Test 1

Propagate a circular LEO orbit (400 km altitude) for one orbital period
(≈ 5 550 s) with `dt = 10 s`. Measure relative drift in specific orbital
energy:

```
ε = v²/2 − μ/r

|ε_final − ε_initial| / |ε_initial| < 1 × 10⁻⁷
```

RK4 with `dt = 10 s` has a local truncation error of O(dt⁵) ≈ 10⁻¹³ km²/s²,
giving a 24 h accumulated drift of ≈ 7 × 10⁻⁶ relative. The stricter single-orbit
bound (1 × 10⁻⁷) catches first-order integration mistakes and wrong gravity
sign/magnitude.

**Plot:** `validation/plots/1_energy_conservation.png`

### 2. SGP4 Comparison

**File:** `validate_physics.py` — Test 2

Initialise the ISS from its real TLE (epoch baked into the test for
reproducibility). Propagate 24 h using:

- SGP4 (analytical, standard reference)
- Astrosis RK4 (gravity only)
- Astrosis RK4 (gravity + drag)

Report RMS position difference between SGP4 and RK4 over 24 h.

Expected: `< 10 km` position error at 24 h, dominated by the different force
models (SGP4 uses simplified drag and no J3/J4).

**Plot:** `validation/plots/2_sgp4_comparison.png`

### 3. J2 Nodal Regression Rate

**File:** `validate_physics.py` — Test 3

Verify that the RAAN drift rate matches the J2 analytical formula:

```
Ω_dot = −1.5 × J2 × √μ × R_E² / (a⁷/² × (1 − e²)²)
```

Propagate a 500 km circular orbit for 48 h, extract Ω from each state vector,
fit a linear slope, and compare to the predicted rate.

Expected: `< 0.03 °/day` error.

**Plot:** `validation/plots/3_raan_precession.png`

### 4. RK4 Convergence Order

**File:** `validate_physics.py` — Test 4

Propagate a reference orbit for 2 h with a very fine step (`dt = 2 s`).
Then propagate for the same time window at `dt = 60 s` and `dt = 30 s`.
Measure the position error vs the reference at each step. Halving dt should
reduce error by exactly 16× (4th order):

```
ratio = error(dt) / error(dt/2) ≈ 16
```

Acceptance threshold: `ratio ≥ 14` (accounts for rounding and non-asymptotic
effects at moderate step sizes).

**Plot:** `validation/plots/4_rk4_convergence.png`

### 5. Solar Radiation Pressure (SRP) Divergence

**File:** `validate_physics.py` — Test 5

Propagate two identical orbits for 48 h, one with SRP enabled and one without.
The trajectory separation demonstrates the physical effect of solar radiation
pressure.

**Plot:** `validation/plots/5_srp_divergence.png`

### 6. Strong Scaling (OpenMP)

**File:** `scaling_analysis.py`

Measure batch propagation time for N = 10 000 satellites with 1, 2, 4, 8, and
12 threads. Efficiency computed as `T(1) / (p × T(p))`.

**Plot:** `validation/plots/5_strong_scaling.png`

### 7. Weak Scaling (OpenMP)

**File:** `scaling_analysis.py`

Measure batch propagation time with fixed work per thread (1 000 sats / thread).
Ideal weak scaling shows constant runtime.

**Plot:** `validation/plots/6_weak_scaling.png`

### 8. CUDA Crossover

**File:** `scaling_analysis.py`

Vary batch size from N = 100 to N = 10 000. Measure C++ (OpenMP) and CUDA
batch propagation time. The crossover is the N at which CUDA becomes faster.

**Plot:** `validation/plots/7_cuda_crossover.png`

### 9. Roofline Model

**File:** `cuda_roofline.py`

Uses Nsight Compute metrics (FP64 FLOPs, DRAM bytes) to place the
`k_prop_soa` kernel on the roofline chart for the RTX 2050.

**Plot:** `validation/plots/8_roofline.png`

### 10. Monte Carlo Pc (GPU)

**File:** `test_monte_carlo.py`

Draw 10 000 Monte Carlo samples from position covariance, propagate each
sample pair with the CUDA kernel, count collisions. Compare the empirical Pc
to Chan's analytical Pc.
