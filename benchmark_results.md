
                                   Astrosis Three-Way Performance Benchmark                                   
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Backends: Python ✓ │ NumPy ✓ │ C++ ✓ │ CUDA ✓
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Benchmark                              │       Python │        NumPy │          C++ (speedup) │         CUDA (speedup)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Single propagation (5,000 iters)       │     35.8 ms │   1185.9 ms │      2.7 ms (× 13.4×) │        N/A (×   N/A)
  Batch propagation (200 sats × 100 steps) │    147.5 ms │     26.6 ms │      1.8 ms (× 83.7×) │    938.3 ms (×  0.2×)
  Batch propagation (1,000 sats × 100 steps) │    739.9 ms │     47.1 ms │      2.0 ms (×376.5×) │      7.2 ms (×102.1×)
  Conjunction detection (50×50 pairs, 1h) │    129.8 ms │        N/A │     28.1 ms (×  4.6×) │    294.4 ms (×  0.4×)
  Conjunction detection (100×100 pairs, 2h) │    518.1 ms │        N/A │    231.9 ms (×  2.2×) │     37.4 ms (× 13.9×)
  Fuel calculation (10,000 iters)        │      4.2 ms │        N/A │      2.4 ms (×  1.7×) │        N/A (×   N/A)
  Maneuver calculation (1,000 iters)     │     28.7 ms │        N/A │      0.5 ms (× 53.1×) │        N/A (×   N/A)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────

  Key metric — Batch Propagation:
    NumPy  vs Python:     5.5×
    C++    vs Python:    83.7×
    CUDA   vs Python:     0.2×
    CUDA   vs C++:        0.0×

GPU 0: NVIDIA GeForce RTX 2050 | SM 8.6 | 4294 MB | 16 SMs
