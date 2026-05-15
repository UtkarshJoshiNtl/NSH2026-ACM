import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cpp", "build"))
import physics_engine as _cpp
import numpy as np

def profile():
    n = 10000
    steps = 100
    dt = 10.0
    states = np.random.rand(n, 6).astype(np.float64)
    # Warmup
    _cpp.cuda_propagate_batch_soa(states, dt, steps)
    # Profile this call
    _cpp.cuda_propagate_batch_soa(states, dt, steps)

if __name__ == "__main__":
    profile()
