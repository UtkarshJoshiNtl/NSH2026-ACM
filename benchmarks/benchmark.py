"""Benchmark Python vs C++ vs CUDA across workload sizes."""

import argparse
import time
import sys
import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.core.propagator import rk4_step, rk4_batch, propagate_batch_numpy
from engine.core.conjunction import ConjunctionDetector as PyDetector
from engine.core.accelerator import backend_info
from engine.constants import MU, RE
import numpy as np

# Backend info
_info = backend_info()
_HAS_CPP = _info["cpp"]
_HAS_CUDA = _info["cuda"]
_HAS_BATCH = _info["cpp"]

# Import C++ module directly for benchmarking individual tiers
try:
    import physics_engine as _cpp
except ImportError:
    _cpp = None

# ── Test data ─────────────────────────────────────────────────────────────────
ISS_STATE = [-RE + 400.0, 0.0, 0.0, 0.0, 7.66, 0.0]


def gen_states(n: int) -> Tuple[list, list]:
    sats, debs = [], []
    for i in range(n):
        sats.append([-RE+400+i*0.1, i*0.5, 0.0, 0.0, 7.66+i*0.001, 0.0])
        debs.append([-RE+405+i*0.1, i*0.5+1.0, 0.5, 0.1, 7.65+i*0.001, 0.1])
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
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


# ── Benchmarks ────────────────────────────────────────────────────────────────

def bench_single_propagation(iters: int) -> BenchResult:
    r = BenchResult(f"Single propagation ({iters:,} iters)")

    def py():
        s = tuple(ISS_STATE)
        for _ in range(iters): s = rk4_step(s, 10.0)
    r.py_s = _t(py)

    arr = np.array([ISS_STATE])
    def np_fn():
        rk4_batch(arr, 10.0, iters)
    r.np_s = _t(np_fn)

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

    def py():
        ss = [tuple(s) for s in sats]
        for _ in range(steps):
            ss = [rk4_step(s, dt) for s in ss]
    r.py_s = _t(py)

    def np_fn():
        propagate_batch_numpy(sats, dt, steps)
    r.np_s = _t(np_fn)

    if _HAS_BATCH:
        prop = _cpp.Propagator()
        def cpp():
            arr = np.array(sats, dtype=np.float64)
            prop.batch_propagate_steps(arr, dt, steps)
        r.cpp_s = _t(cpp)

    if _HAS_CUDA:
        arr_cuda = np.array(sats, dtype=np.float64)

        def cuda_bench():
            fn = getattr(_cpp, "cuda_propagate_batch_soa", _cpp.cuda_propagate_batch)
            fn(arr_cuda, dt, steps)
        r.cuda_s = _t(cuda_bench)

    return r


def bench_conjunction(n: int, lookahead: float = 3600.0, step: float = 60.0) -> BenchResult:
    r = BenchResult(f"Conjunction detection ({n}×{n} pairs, {int(lookahead/3600)}h)")
    sats, debs = gen_states(n)

    def py():
        PyDetector().detect(sats, debs, lookahead_s=lookahead, step_s=step)
    r.py_s = _t(py)

    r.np_s = None

    if _HAS_CPP:
        def cpp():
            _cpp.ConjunctionDetector().detect(sats, debs, lookahead, step)
        r.cpp_s = _t(cpp)

    if _HAS_CUDA and hasattr(_cpp, 'cuda_detect_conjunctions'):
        def cuda():
            _cpp.cuda_detect_conjunctions(sats, debs, lookahead, step)
        r.cuda_s = _t(cuda)

    return r


# ── Report ────────────────────────────────────────────────────────────────────

def print_header():
    sep = "─" * 110
    print(f"\n{'Astrosis Performance Benchmark':^110}")
    print(sep)
    print(f"  Backends: Python ✓ │ NumPy ✓ │ C++ {'✓' if _HAS_CPP else '✗'} │ "
          f"CUDA {'✓' if _HAS_CUDA else '✗'}")
    print(sep)
    print(f"  {'Benchmark':<38} │ {'Python':>12} │ {'NumPy':>12} │ "
          f"{'C++ (speedup)':>22} │ {'CUDA (speedup)':>22}")
    print(sep)


def print_footer(results: List[BenchResult]):
    sep = "─" * 110
    print(sep)
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
        print("\n  C++ module not built. Run: cd cpp && mkdir build && cd build && cmake .. && make")
    if not _HAS_CUDA:
        print("  CUDA not available. Install CUDA Toolkit, then: cmake .. -DUSE_CUDA=ON && make")
    print()


def main(quick: bool = False):
    if _HAS_CUDA and _cpp is not None:
        _cpp.cuda_propagate_batch([[RE+400, 0, 0, 0, 7.6, 0]], 10.0, 1)

    print_header()
    results = []

    if quick:
        configs = dict(single_iters=5_000, batch_n=200, batch_steps=100, conj_n=50)
    else:
        configs = dict(single_iters=50_000, batch_n=1_000, batch_steps=864, conj_n=200)

    for fn, args in [
        (bench_single_propagation, (configs['single_iters'],)),
        (bench_batch_propagation,  (configs['batch_n'], configs['batch_steps'])),
        (bench_batch_propagation,  (configs['batch_n']*5, configs['batch_steps'])),
        (bench_conjunction,        (configs['conj_n'],)),
        (bench_conjunction,        (configs['conj_n']*2, 7200.0, 60.0)),
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
