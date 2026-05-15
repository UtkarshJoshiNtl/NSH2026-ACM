"""
benchmark.py — Three-Way Performance Benchmark: Python vs C++ vs CUDA
======================================================================
Compares every available backend across multiple workload sizes:
  - Single-satellite propagation (scalability baseline)
  - Batch propagation: N satellites × steps
  - Conjunction detection: N sats × N debris
  - Fuel calculation
  - Maneuver planning

Run with:
    python benchmark.py           # auto-selects available backends
    python benchmark.py --quick   # smaller workloads for fast iteration
"""

import argparse
import time
import sys
import os
import logging
import tracemalloc
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cpp', 'build')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ── Import backends directly so we can force each one ────────────────────────
from engine.core.propagator import rk4_step, rk4_batch, propagate_batch_numpy
from engine.core.conjunction import ConjunctionDetector as PyDetector
from engine.core.fuel import FuelTracker as PyFuelTracker
from engine.core.maneuver import ManeuverCalculator as PyManeuverCalc, ManeuverPlan
from engine.core.conjunction import ConjunctionWarning
from engine.constants import MU, RE, INITIAL_FUEL, DRY_MASS
import numpy as np

# Try loading C++ / CUDA module
try:
    import physics_engine as _cpp
    _HAS_CPP = True
    _HAS_CUDA = getattr(_cpp, 'cuda_available', lambda: False)()
    _HAS_BATCH = hasattr(_cpp.Propagator, 'batch_propagate_steps')
except ImportError:
    _cpp = None
    _HAS_CPP = False
    _HAS_CUDA = False
    _HAS_BATCH = False

# ── Test data ─────────────────────────────────────────────────────────────────
ISS_STATE = [-6371.0 + 400.0, 0.0, 0.0, 0.0, 7.66, 0.0]

def gen_states(n: int) -> Tuple[list, list]:
    sats, debs = [], []
    for i in range(n):
        sats.append([-6371+400+i*0.1, i*0.5, 0.0, 0.0, 7.66+i*0.001, 0.0])
        debs.append([-6371+405+i*0.1, i*0.5+1.0, 0.5, 0.1, 7.65+i*0.001, 0.1])
    return sats, debs


# ── Timing helper ─────────────────────────────────────────────────────────────
@dataclass
class BenchResult:
    name: str
    py_s:   Optional[float] = None
    np_s:   Optional[float] = None
    cpp_s:  Optional[float] = None
    cuda_s: Optional[float] = None
    note:   str = ""

    def speedup(self, ref, val) -> str:
        if ref is None or val is None or val == 0:
            return "N/A"
        return f"{ref/val:.1f}×"

    def row(self) -> str:
        sp_cpp  = self.speedup(self.py_s, self.cpp_s)
        sp_np   = self.speedup(self.py_s, self.np_s)
        sp_cuda = self.speedup(self.py_s, self.cuda_s)

        def fmt(v): return f"{v*1000:8.1f} ms" if v is not None else "       N/A"

        return (f"  {self.name:<38} │ {fmt(self.py_s)} │ {fmt(self.np_s)} │"
                f" {fmt(self.cpp_s)} (×{sp_cpp:>6}) │"
                f" {fmt(self.cuda_s)} (×{sp_cuda:>6})")


def _t(fn) -> float:
    """Time a callable, return seconds."""
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


# ── Benchmarks ────────────────────────────────────────────────────────────────

def bench_single_propagation(iters: int) -> BenchResult:
    r = BenchResult(f"Single propagation ({iters:,} iters)")

    # Python
    def py():
        s = tuple(ISS_STATE)
        for _ in range(iters): s = rk4_step(s, 10.0)
    r.py_s = _t(py)

    # NumPy (batch of 1)
    arr = np.array([ISS_STATE])
    def np_fn():
        rk4_batch(arr, 10.0, iters)
    r.np_s = _t(np_fn)

    # C++
    if _HAS_CPP:
        prop = _cpp.Propagator()
        def cpp():
            s = list(ISS_STATE)
            for _ in range(iters): s = list(prop.propagate(s, 10.0))
        r.cpp_s = _t(cpp)

    return r


def bench_batch_propagation(n: int, steps: int) -> BenchResult:
    r = BenchResult(f"Batch propagation ({n:,} sats × {steps:,} steps)")
    sats, _ = gen_states(n)
    dt = 10.0

    # Python loop
    def py():
        ss = [tuple(s) for s in sats]
        for _ in range(steps):
            ss = [rk4_step(s, dt) for s in ss]
    r.py_s = _t(py)

    # NumPy vectorized
    def np_fn():
        propagate_batch_numpy(sats, dt, steps)
    r.np_s = _t(np_fn)

    # C++ batch (GIL-released)
    if _HAS_BATCH:
        prop = _cpp.Propagator()
        def cpp():
            arr = np.array(sats, dtype=np.float64)
            prop.batch_propagate_steps(arr, dt, steps)
        r.cpp_s = _t(cpp)

    # CUDA
    if _HAS_CUDA:
        arr_cuda = np.array(sats, dtype=np.float64)
        
        # 1. AoS
        def cuda_aos():
            _cpp.cuda_propagate_batch(arr_cuda, dt, steps)
        r.cuda_s = _t(cuda_aos)
        
        # 2. SoA (for note)
        def cuda_soa():
            _cpp.cuda_propagate_batch_soa(arr_cuda, dt, steps)
        t_soa = _t(cuda_soa)
        
        # 3. Streamed
        def cuda_stream():
            _cpp.cuda_propagate_batch_streamed(arr_cuda, dt, steps)
        t_stream = _t(cuda_stream)
        
        r.note = f"AoS: {r.cuda_s*1000:.1f}ms | SoA: {t_soa*1000:.1f}ms | Stream: {t_stream*1000:.1f}ms"
    return r


def bench_conjunction(n: int, lookahead: float = 3600.0, step: float = 60.0) -> BenchResult:
    r = BenchResult(f"Conjunction detection ({n}×{n} pairs, {int(lookahead/3600)}h)")
    sats, debs = gen_states(n)

    # Python
    def py():
        PyDetector().detect(sats, debs, lookahead_s=lookahead, step_s=step)
    r.py_s = _t(py)

    # C++ (no NumPy path for conjunction)
    r.np_s = None

    # C++
    if _HAS_CPP:
        def cpp():
            _cpp.ConjunctionDetector().detect(sats, debs, lookahead, step)
        r.cpp_s = _t(cpp)

    # CUDA
    if _HAS_CUDA and hasattr(_cpp, 'cuda_detect_conjunctions'):
        def cuda():
            _cpp.cuda_detect_conjunctions(sats, debs, lookahead, step)
        r.cuda_s = _t(cuda)

    return r


def bench_fuel(iters: int) -> BenchResult:
    r = BenchResult(f"Fuel calculation ({iters:,} iters)")
    dv = [0.1, 0.2, 0.3]

    def py():
        t = PyFuelTracker(INITIAL_FUEL)
        for _ in range(iters): t.calculate_fuel_cost(dv)
    r.py_s = _t(py)
    r.np_s = None  # no numpy path

    if _HAS_CPP:
        def cpp():
            t = _cpp.FuelTracker(INITIAL_FUEL, DRY_MASS)
            for _ in range(iters): t.calculate_fuel_cost(dv)
        r.cpp_s = _t(cpp)

    return r


def bench_maneuver(iters: int) -> BenchResult:
    r = BenchResult(f"Maneuver calculation ({iters:,} iters)")
    if _HAS_CPP:
        w = _cpp.ConjunctionWarning()
        w.sat_id = 0
        w.debris_id = 1
        w.current_distance = 5.0
        w.time_to_closest_approach = 3600.0
        w.severity = "WARNING"
        w.relative_velocity = [0.1, 0.2, 0.3]
    else:
        w = ConjunctionWarning(
            sat_id=0, debris_id=1, current_distance=5.0,
            time_to_closest_approach=3600.0, severity="WARNING",
            relative_velocity=[0.1, 0.2, 0.3])

    def py():
        calc = PyManeuverCalc()
        # If we have C++ warning, we might need a Python one for the Python calculator
        py_w = w
        if _HAS_CPP:
             py_w = ConjunctionWarning(
                sat_id=w.sat_id, debris_id=w.debris_id, current_distance=w.current_distance,
                time_to_closest_approach=w.time_to_closest_approach, severity=w.severity,
                relative_velocity=list(w.relative_velocity))
        for _ in range(iters): calc.calculate(ISS_STATE, py_w)
    r.py_s = _t(py)
    if _HAS_CPP:
        calc = _cpp.ManeuverCalculator()
        def cpp():
            for _ in range(iters): calc.calculate(ISS_STATE, w)
        r.cpp_s = _t(cpp)
    return r


# ── Report ────────────────────────────────────────────────────────────────────

def print_header():
    sep = "─" * 110
    print(f"\n{'Astrosis Three-Way Performance Benchmark':^110}")
    print(sep)
    backends = []
    backends.append("Python ✓")
    backends.append("NumPy ✓")
    backends.append(f"C++ {'✓' if _HAS_CPP else '✗'}")
    backends.append(f"CUDA {'✓' if _HAS_CUDA else '✗ (no nvcc)'}")
    print(f"  Backends: {' │ '.join(backends)}")
    if _HAS_CUDA:
        _cpp.cuda_print_device_info()
    print(sep)
    print(f"  {'Benchmark':<38} │ {'Python':>12} │ {'NumPy':>12} │ "
          f"{'C++ (speedup)':>22} │ {'CUDA (speedup)':>22}")
    print(sep)


def print_footer(results: List[BenchResult]):
    sep = "─" * 110
    print(sep)
    # Summary speedups (batch propagation is the key metric)
    batch = next((r for r in results if "Batch" in r.name), None)
    if batch:
        print(f"\n  Key metric — Batch Propagation:")
        if batch.np_s:
            print(f"    NumPy  vs Python: {batch.speedup(batch.py_s, batch.np_s):>8}")
        if batch.cpp_s:
            print(f"    C++    vs Python: {batch.speedup(batch.py_s, batch.cpp_s):>8}")
        if batch.cuda_s:
            print(f"    CUDA   vs Python: {batch.speedup(batch.py_s, batch.cuda_s):>8}")
            if batch.cpp_s:
                print(f"    CUDA   vs C++:    {batch.speedup(batch.cpp_s, batch.cuda_s):>8}")

    if not _HAS_CPP:
        print("\n  ⚠  C++ module not built. Run: cd cpp && mkdir build && cd build && cmake .. && make")
    if not _HAS_CUDA:
        print("  ⚠  CUDA not available. Install CUDA Toolkit, then: cmake .. -DUSE_CUDA=ON && make")
    print()


def main(quick: bool = False):
    if _HAS_CUDA:
        # Warmup CUDA context
        _cpp.cuda_propagate_batch([[RE+400, 0, 0, 0, 7.6, 0]], 10.0, 1)

    print_header()
    results = []

    if quick:
        configs = dict(single_iters=5_000, batch_n=200, batch_steps=100,
                       conj_n=50, fuel_iters=10_000, man_iters=1_000)
    else:
        configs = dict(single_iters=50_000, batch_n=1_000, batch_steps=864,
                       conj_n=200, fuel_iters=100_000, man_iters=10_000)

    for fn, args in [
        (bench_single_propagation, (configs['single_iters'],)),
        (bench_batch_propagation,  (configs['batch_n'], configs['batch_steps'])),
        (bench_batch_propagation,  (configs['batch_n']*5, configs['batch_steps'])),
        (bench_conjunction,        (configs['conj_n'],)),
        (bench_conjunction,        (configs['conj_n']*2, 7200.0, 60.0)),
        (bench_fuel,               (configs['fuel_iters'],)),
        (bench_maneuver,           (configs['man_iters'],)),
    ]:
        r = fn(*args)
        results.append(r)
        print(r.row() + (f"  [{r.note}]" if r.note else ""))

    print_footer(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Astrosis backend benchmark")
    parser.add_argument("--quick", action="store_true",
                        help="Run smaller workloads for fast iteration")
    args = parser.parse_args()
    main(quick=args.quick)
