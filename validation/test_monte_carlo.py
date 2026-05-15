import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cpp", "build"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
import time

try:
    import physics_engine as _cpp
except ImportError:
    pytest.skip("physics_engine extension is not built", allow_module_level=True)

def test_mc():
    print("Testing GPU Monte Carlo Pc Calculation...")
    if not getattr(_cpp, "cuda_available", lambda: False)():
        pytest.skip("CUDA backend is not available")
    
    # 1. Setup a near-miss scenario
    # Satellite A (circular)
    sat_mean = np.array([7000.0, 0.0, 0.0, 0.0, 7.5, 0.0])
    # Satellite B (crossing, 100m separation)
    deb_mean = np.array([7000.1, 0.0, 0.0, 0.0, -7.5, 0.0])
    
    n_samples = 100000
    sigma_pos = 0.1  # 100m uncertainty
    sigma_vel = 0.001 # 1m/s uncertainty
    
    # Generate samples
    sat_samples = np.tile(sat_mean, (n_samples, 1))
    sat_samples[:, :3] += np.random.normal(0, sigma_pos, (n_samples, 3))
    sat_samples[:, 3:] += np.random.normal(0, sigma_vel, (n_samples, 3))
    
    deb_samples = np.tile(deb_mean, (n_samples, 1))
    deb_samples[:, :3] += np.random.normal(0, sigma_pos, (n_samples, 3))
    deb_samples[:, 3:] += np.random.normal(0, sigma_vel, (n_samples, 3))
    
    dt = 1.0
    steps = 10  # 10 seconds sweep
    threshold = 0.2 # 200m collision sphere
    mjd0 = 60810.0
    
    start = time.perf_counter()
    try:
        pc = _cpp.cuda_monte_carlo_pc(sat_samples, deb_samples, dt, steps, threshold, mjd0)
    except RuntimeError as exc:
        if "CUDA" in str(exc):
            pytest.skip(f"CUDA Monte Carlo unavailable: {exc}")
        raise
    elapsed = time.perf_counter() - start
    
    print(f"  Samples:    {n_samples:,}")
    print(f"  Threshold:  {threshold*1000:.0f} m")
    print(f"  Result Pc:  {pc:.6f}")
    print(f"  GPU Time:   {elapsed*1000:.2f} ms")
    
    if pc > 0:
        print("  ✓ PASS: Found collisions in the sample cloud.")
    else:
        print("  ! NOTE: No collisions found (increase threshold or decrease distance).")

if __name__ == "__main__":
    test_mc()
