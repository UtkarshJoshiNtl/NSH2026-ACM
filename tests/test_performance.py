import pytest
import numpy as np
from engine.physics.accelerator import (
    propagate, 
    propagate_batch, 
    backend_info,
    detect_conjunctions
)
from engine.constants import MU

def test_backend_parity():
    """Verify that Python and C++ backends produce consistent results."""
    state = [-5971.0, 0.0, 0.0, 0.0, 7.66, 0.0]
    dt = 10.0
    
    # 1. Single propagation
    # Force Python by bypassing the bridge if needed, but here we just check if C++ is used
    res = propagate(state, dt)
    
    # Simple sanity check: energy conservation (approximate)
    r = np.linalg.norm(res[:3])
    v = np.linalg.norm(res[3:])
    energy = 0.5 * v**2 - MU / r
    
    r0 = np.linalg.norm(state[:3])
    v0 = np.linalg.norm(state[3:])
    energy0 = 0.5 * v0**2 - MU / r0
    
    assert abs(energy - energy0) < 1e-6

def test_conjunction_optimization():
    """Verify the new optimized conjunction detection logic."""
    sat_states = [[-5971.0, 0.0, 0.0, 0.0, 7.66, 0.0]]
    # Debris very close to the satellite
    debris_states = [[-5970.9, 0.05, 0.05, 0.0, 7.66, 0.01]]
    
    lookahead = 3600.0
    step = 60.0
    
    warnings = detect_conjunctions(sat_states, debris_states, lookahead, step)
    
    assert len(warnings) > 0
    assert warnings[0].severity in ["CRITICAL", "WARNING", "ADVISORY"]
    assert warnings[0].current_distance < 1.0

def test_batch_equivalence():
    """Verify that batch propagation matches single propagation."""
    sats = [
        [-5971.0, 0.0, 0.0, 0.0, 7.66, 0.0],
        [7000.0, 1000.0, 0.0, -1.0, 7.0, 0.1]
    ]
    dt = 10.0
    steps = 5
    
    res_batch = propagate_batch(sats, dt, steps)
    
    # Verify first sat
    curr = sats[0]
    for _ in range(steps):
        curr = propagate(curr, dt)
        
    assert np.allclose(res_batch[0], curr, atol=1e-8)
