"""
validation/scaling_analysis.py — HPC Scaling & CUDA Crossover Analysis
========================================================================
Three scaling experiments:

1. Strong scaling:  N=10,000 sats, vary OMP_NUM_THREADS 1→16, plot speedup
2. Weak scaling:    N proportional to threads, plot parallel efficiency η
3. CUDA crossover:  N from 10 to 10,000, find where GPU beats CPU

Run:
    python validation/scaling_analysis.py

All plots saved to validation/plots/.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLOTS_DIR = os.path.join(os.path.dirname(__file__), "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

STYLE = {
    "figure.facecolor": "#0d1117", "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d", "axes.labelcolor": "#e6edf3",
    "xtick.color": "#8b949e", "ytick.color": "#8b949e",
    "text.color": "#e6edf3", "grid.color": "#21262d",
    "grid.linestyle": "--", "grid.alpha": 0.6,
    "lines.linewidth": 2.0,
}
plt.rcParams.update(STYLE)
ACCENT = "#58a6ff"; GREEN = "#3fb950"; ORANGE = "#d29922"; RED = "#f85149"

# ── Load backends ─────────────────────────────────────────────────────────────
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cpp", "build"))
    import physics_engine as _cpp
    HAS_CPP  = True
    HAS_CUDA = getattr(_cpp, "cuda_available", lambda: False)()
    HAS_BATCH = hasattr(_cpp.Propagator, "batch_propagate_steps")
except ImportError:
    _cpp = None; HAS_CPP = False; HAS_CUDA = False; HAS_BATCH = False

from engine.core.propagator import propagate_batch_numpy
from engine.constants import RE

DT    = 10.0   # step size [s]
STEPS = 100    # integration steps per measurement


def _gen_states(n: int) -> np.ndarray:
    arr = np.empty((n, 6), dtype=np.float64)
    for i in range(n):
        arr[i] = [RE + 400 + i * 0.01, i * 0.1, 0.0, 0.0, 7.66 + i * 1e-5, 0.0]
    return arr


def _time_cpp_batch(states: np.ndarray, threads: int) -> float:
    """Time the C++ batch propagator with a given thread count.

    The measurement is executed in a fresh subprocess so the OpenMP thread
    count is fixed before the C++ module is imported.
    """
    import tempfile
    import pickle

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pkl', delete=False) as f:
        states_file = f.name
        pickle.dump((states, DT, STEPS), f)

    script = f"""
import os
import pickle
import sys
import time

sys.path.insert(0, r"{os.path.join(ROOT_DIR, "cpp", "build")}")
import physics_engine as _cpp

with open(r"{states_file}", "rb") as f:
    states, dt, steps = pickle.load(f)

prop = _cpp.Propagator()
t0 = time.perf_counter()
prop.batch_propagate_steps(states, dt, steps)
elapsed = time.perf_counter() - t0
print(elapsed)
"""

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        script_file = f.name
        f.write(script)

    try:
        result = subprocess.run(
            [sys.executable, script_file],
            env=env,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "C++ timing subprocess failed")
        elapsed = float(result.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(states_file)
        os.unlink(script_file)
    
    return elapsed


def _time_cuda(states: np.ndarray) -> float:
    arr = states.copy()
    t0 = time.perf_counter()
    _cpp.cuda_propagate_batch(arr, DT, STEPS)
    return time.perf_counter() - t0


def _time_cuda_soa(states: np.ndarray) -> float:
    arr = states.copy()
    t0 = time.perf_counter()
    _cpp.cuda_propagate_batch_soa(arr, DT, STEPS)
    return time.perf_counter() - t0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Strong Scaling
# ─────────────────────────────────────────────────────────────────────────────

def strong_scaling():
    print("Strong Scaling (N=10,000, vary threads)...")
    if not HAS_BATCH:
        print("  SKIP — C++ not available"); return
    N = 10_000
    states = _gen_states(N)
    thread_counts = [1, 2, 4, 6, 8, 12, 16]
    times = []
    for t in thread_counts:
        elapsed = _time_cpp_batch(states, t)
        times.append(elapsed)
        print(f"  T={t:2d} → {elapsed*1000:.1f} ms")

    t1 = times[0]
    speedups  = [t1 / t for t in times]
    ideal     = thread_counts

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thread_counts, speedups, "o-", color=ACCENT, label="Measured speedup")
    ax.plot(thread_counts, ideal, "--", color=RED, lw=1.2, label="Ideal linear")
    ax.set_xlabel("OMP_NUM_THREADS")
    ax.set_ylabel("Speedup (T₁ / Tₙ)")
    ax.set_title(f"Strong Scaling — N={N:,} satellites × {STEPS} steps")
    ax.legend(); ax.grid(True)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, "5_strong_scaling.png")
    fig.savefig(path, dpi=150); plt.close(fig)
    print(f"  Saved: {path}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Weak Scaling
# ─────────────────────────────────────────────────────────────────────────────

def weak_scaling():
    print("Weak Scaling (N = 1000 × threads)...")
    if not HAS_BATCH:
        print("  SKIP — C++ not available"); return
    thread_counts = [1, 2, 4, 6, 8, 12, 16]
    N_per_thread  = 1000
    efficiencies  = []
    t1 = None

    for tc in thread_counts:
        N = N_per_thread * tc
        states = _gen_states(N)
        elapsed = _time_cpp_batch(states, tc)
        if tc == 1:
            t1 = elapsed
        eta = t1 / elapsed if t1 else 1.0
        efficiencies.append(eta)
        print(f"  T={tc:2d}  N={N:6,}  η={eta:.3f}")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thread_counts, efficiencies, "s-", color=GREEN)
    ax.axhline(1.0, color=RED, ls="--", lw=1.2, label="Perfect efficiency")
    ax.set_ylim(0, 1.2)
    ax.set_xlabel("OMP_NUM_THREADS")
    ax.set_ylabel("Parallel efficiency  eta = T1/Tn")
    ax.set_title(f"Weak Scaling — N = {N_per_thread:,} × threads")
    ax.legend(); ax.grid(True)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, "6_weak_scaling.png")
    fig.savefig(path, dpi=150); plt.close(fig)
    print(f"  Saved: {path}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 3. CUDA Crossover Curve + AoS vs SoA
# ─────────────────────────────────────────────────────────────────────────────

def cuda_crossover():
    print("CUDA Crossover + AoS vs SoA (N sweep)...")
    if not HAS_BATCH:
        print("  SKIP — C++ not available"); return

    Ns = [10, 50, 100, 250, 500, 750, 1000, 2000, 3000, 5000, 7500, 10000]
    cpp_times, cuda_aos_times, cuda_soa_times = [], [], []
    crossover_N = None

    for N in Ns:
        states = _gen_states(N)
        cpp_t = _time_cpp_batch(states, threads=max(1, os.cpu_count() or 1))
        cpp_times.append(cpp_t * 1000)

        cuda_t = _time_cuda(states) * 1000 if HAS_CUDA else None
        cuda_aos_times.append(cuda_t)

        soa_t = None
        if HAS_CUDA and hasattr(_cpp, "cuda_propagate_batch_soa"):
            soa_t = _time_cuda_soa(states) * 1000
        cuda_soa_times.append(soa_t)

        if HAS_CUDA and cuda_t is not None and crossover_N is None and cuda_t < cpp_t * 1000:
            crossover_N = N

        print(f"  N={N:6,}  C++={cpp_times[-1]:7.1f}ms"
              + (f"  CUDA-AoS={cuda_t:7.1f}ms" if cuda_t else "")
              + (f"  CUDA-SoA={soa_t:7.1f}ms" if soa_t else ""))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(Ns, cpp_times, "o-", color=ACCENT, label="C++ (OpenMP)")
    if any(t is not None for t in cuda_aos_times):
        valid = [(n, t) for n, t in zip(Ns, cuda_aos_times) if t is not None]
        ax.plot([v[0] for v in valid], [v[1] for v in valid], "s-",
                color=GREEN, label="CUDA AoS")
    if any(t is not None for t in cuda_soa_times):
        valid = [(n, t) for n, t in zip(Ns, cuda_soa_times) if t is not None]
        ax.plot([v[0] for v in valid], [v[1] for v in valid], "^-",
                color=ORANGE, label="CUDA SoA (coalesced)")
    if crossover_N:
        ax.axvline(crossover_N, color=RED, ls=":", lw=1.5,
                   label=f"CUDA breakeven ≈ N={crossover_N}")
    ax.set_xlabel("Number of satellites (N)")
    ax.set_ylabel("Propagation time (ms)")
    ax.set_title(f"CUDA vs C++ Crossover + AoS vs SoA  ({STEPS} steps × {DT}s)")
    ax.legend(); ax.grid(True)
    ax.set_xscale("log")
    ax.set_yscale("log")
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, "7_cuda_crossover.png")
    fig.savefig(path, dpi=150); plt.close(fig)
    print(f"\n  CUDA breakeven: N ≈ {crossover_N or 'N/A (CUDA always slower)'}")
    print(f"  Saved: {path}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Astrosis Scaling Analysis")
    print("=" * 60 + "\n")
    print(f"Backends: C++={'✓' if HAS_CPP else '✗'}  CUDA={'✓' if HAS_CUDA else '✗'}\n")

    if HAS_CUDA:
        _cpp.cuda_propagate_batch(_gen_states(1), DT, 1)  # warm up

    strong_scaling()
    weak_scaling()
    cuda_crossover()
    print("Done. All plots saved to:", PLOTS_DIR)
