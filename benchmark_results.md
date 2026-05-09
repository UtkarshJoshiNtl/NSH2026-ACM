
                                   Astrosis Three-Way Performance Benchmark                                   
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Backends: Python ✓ │ NumPy ✓ │ C++ ✓ │ CUDA ✗ (no nvcc)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Benchmark                              │       Python │        NumPy │          C++ (speedup) │         CUDA (speedup)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Single propagation (5,000 iters)       │     35.2 ms │   1116.2 ms │      2.6 ms (× 13.4×) │        N/A (×   N/A)
  Batch propagation (200 sats × 100 steps) │    144.8 ms │     27.5 ms │      2.6 ms (× 56.0×) │        N/A (×   N/A)
  Batch propagation (1,000 sats × 100 steps) │    735.6 ms │     45.9 ms │      1.7 ms (×423.0×) │        N/A (×   N/A)
  Conjunction detection (50×50 pairs, 1h) │     37.9 ms │        N/A │     27.6 ms (×  1.4×) │        N/A (×   N/A)
  Conjunction detection (100×100 pairs, 2h) │    307.2 ms │        N/A │    218.4 ms (×  1.4×) │        N/A (×   N/A)
  Fuel calculation (10,000 iters)        │      3.9 ms │        N/A │      2.3 ms (×  1.7×) │        N/A (×   N/A)
  Maneuver calculation (1,000 iters)     │     29.4 ms │        N/A │      0.5 ms (× 55.5×) │        N/A (×   N/A)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Key metric — Batch Propagation:
    NumPy  vs Python:     5.3×
    C++    vs Python:    56.0×
  ⚠  CUDA not available. Install CUDA Toolkit, then: cmake .. -DUSE_CUDA=ON && make

