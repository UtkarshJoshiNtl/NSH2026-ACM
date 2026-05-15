"""
validation/cuda_roofline.py — Roofline Model for the CUDA Propagation Kernel
=============================================================================
Parses Nsight Compute (ncu) metrics to compute arithmetic intensity and
plots the kernel's location on the roofline model for the RTX 2050.

Usage (requires ncu — may need sudo):
    sudo ncu --metrics sm__sass_thread_inst_executed_op_dfma_pred_on.sum,\
dram__bytes_read.sum,dram__bytes_write.sum \
        --csv python validation/cuda_roofline.py --ncu-mode \
        > validation/ncu_output.csv

    python validation/cuda_roofline.py

If ncu is not run, the script uses hardcoded RTX 2050 roofline limits and
plots a representative marker based on theoretical kernel analysis.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLOTS_DIR = os.path.join(os.path.dirname(__file__), "plots")
NCU_CSV   = os.path.join(os.path.dirname(__file__), "ncu_output.csv")
os.makedirs(PLOTS_DIR, exist_ok=True)

STYLE = {
    "figure.facecolor": "#0d1117", "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d", "axes.labelcolor": "#e6edf3",
    "xtick.color": "#8b949e", "ytick.color": "#8b949e",
    "text.color": "#e6edf3", "grid.color": "#21262d",
    "grid.linestyle": "--", "grid.alpha": 0.6,
}
plt.rcParams.update(STYLE)

# RTX 2050 (SM 8.6) hardware limits — from NVIDIA Ampere Architecture Whitepaper
RTX2050_BW_GBS    = 192.0    # GB/s peak memory bandwidth (RTX 2050 mobile)
RTX2050_FP64_TFLOPS = 0.2    # TFLOPs FP64  (RTX 2050 is 1/32 FP64 rate)
RTX2050_FP32_TFLOPS = 6.4    # TFLOPs FP32

# Roofline limits in GFLOPS/s and GB/s
PEAK_BW   = RTX2050_BW_GBS        # GB/s
PEAK_FP64 = RTX2050_FP64_TFLOPS * 1000  # GFLOPS/s


def run_ncu_and_collect(n: int = 2000):
    """
    Run the main cuda_propagate_batch kernel under Nsight Compute CLI and
    collect FLOP and memory byte counts. Writes ncu_output.csv.
    Requires 'ncu' binary on PATH and appropriate permissions.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cpp", "build"))
    # Build a tiny driver script
    driver = os.path.join(os.path.dirname(__file__), "_ncu_driver.py")
    with open(driver, "w") as f:
        f.write(f"""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cpp', 'build'))
import physics_engine as pe
states = np.random.randn({n}, 6).astype(np.float64)
states[:, 0] += 6778.0; states[:, 4] += 7.66
pe.cuda_propagate_batch(states, 10.0, 100)
""")
    cmd = [
        "ncu", "--metrics",
        "sm__sass_thread_inst_executed_op_dfma_pred_on.sum,"
        "sm__sass_thread_inst_executed_op_dadd_pred_on.sum,"
        "sm__sass_thread_inst_executed_op_dmul_pred_on.sum,"
        "dram__bytes_read.sum,dram__bytes_write.sum",
        "--csv", sys.executable, driver,
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ncu error: {result.stderr[:500]}")
        return None
    with open(NCU_CSV, "w") as f:
        f.write(result.stdout)
    os.remove(driver)
    return result.stdout


def parse_ncu_csv(csv_text: str):
    """Extract FLOPs and bytes from ncu --csv output."""
    dfma = dadd = dmul = bytes_read = bytes_write = 0
    for line in csv_text.splitlines():
        parts = line.split(",")
        if len(parts) < 8:
            continue
        metric = parts[7].strip().strip('"')
        try:
            value = float(parts[-1].strip().strip('"').replace(",", ""))
        except ValueError:
            continue
        if "dfma" in metric:   dfma  += value
        if "dadd" in metric:   dadd  += value
        if "dmul" in metric:   dmul  += value
        if "bytes_read" in metric:  bytes_read  += value
        if "bytes_write" in metric: bytes_write += value
    # Each DFMA counts as 2 FP64 ops
    flops = 2 * dfma + dadd + dmul
    total_bytes = bytes_read + bytes_write
    return flops, total_bytes


def plot_roofline(ai: float, achieved_gflops: float | None, label: str,
                  has_ncu_data: bool = False, estimated_ceiling_gflops: float | None = None):
    """
    Plot the Roofline model for RTX 2050.
    ai = arithmetic intensity [FLOP/byte]
    achieved_gflops = measured performance [GFLOPS/s], or None if unavailable
    """
    ai_range = np.logspace(-2, 4, 500)

    # Memory-bound roof: Performance = BW × AI
    mem_roof = PEAK_BW * ai_range  # GFLOPS/s

    # Compute-bound roof: flat line at PEAK_FP64
    compute_roof = np.full_like(ai_range, PEAK_FP64)

    # Actual roofline = min(mem_roof, compute_roof)
    roofline = np.minimum(mem_roof, compute_roof)

    # Ridge point (transition from memory-bound to compute-bound)
    ai_ridge = PEAK_FP64 / PEAK_BW

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.loglog(ai_range, roofline, color="#58a6ff", lw=2.5, label="RTX 2050 Roofline (FP64)")
    ax.loglog(ai_range, mem_roof, color="#8b949e", lw=1, ls="--", label=f"Memory BW limit ({PEAK_BW} GB/s)")
    ax.axhline(PEAK_FP64, color="#8b949e", lw=1, ls=":", label=f"FP64 compute limit ({PEAK_FP64:.0f} GFLOPS/s)")
    ax.axvline(ai_ridge, color="#d29922", lw=1.2, ls="-.",
               label=f"Ridge point  AI={ai_ridge:.1f} FLOP/byte")

    if estimated_ceiling_gflops is None:
        estimated_ceiling_gflops = float(min(PEAK_BW * ai, PEAK_FP64))

    # Plot measured point if we have one, otherwise show the theoretical ceiling.
    if achieved_gflops is not None:
        ax.scatter([ai], [achieved_gflops], s=200, color="#3fb950", zorder=5,
                   label=f"{label} measured  (AI={ai:.2f}, {achieved_gflops:.1f} GFLOPS/s)")
        ax.scatter([ai], [estimated_ceiling_gflops], s=90, facecolors="none",
                   edgecolors="#f85149", linewidths=2.0, zorder=6,
                   label=f"Roofline ceiling at AI={ai:.2f}: {estimated_ceiling_gflops:.1f} GFLOPS/s")
        ax.annotate(
            "measured",
            xy=(ai, achieved_gflops),
            xytext=(ai * 1.15, achieved_gflops * 0.75),
            color="#3fb950",
            fontsize=9,
        )
    else:
        ax.scatter([ai], [estimated_ceiling_gflops], s=200, color="#f85149", zorder=5,
                   label=f"{label} theoretical ceiling  (AI={ai:.2f}, {estimated_ceiling_gflops:.1f} GFLOPS/s)")
        region = "memory-bound" if ai < ai_ridge else "compute-bound"
        ax.text(ai * 1.2, estimated_ceiling_gflops * 0.7, region, color="#f85149", fontsize=9)

    ax.set_xlabel("Arithmetic Intensity (FLOP / byte)")
    ax.set_ylabel("Performance (GFLOPS/s)")
    ax.set_title("Roofline Model — RTX 2050 (SM 8.6)  |  FP64 RK4 Propagation Kernel")
    ax.set_xlim(0.01, 1000)
    ax.set_ylim(0.01, PEAK_FP64 * 3)
    ax.legend(fontsize=8)
    ax.grid(True, which="both")
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, "8_roofline.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ncu-mode", action="store_true",
                        help="Run ncu to collect actual metrics (requires ncu on PATH)")
    args = parser.parse_args()

    has_ncu_data = False
    ai = 0.0
    achieved_gflops = None

    # Theoretical analysis of the RK4 kernel:
    # Per satellite per step: ~120 FP64 multiplies/adds in 4 derivative evaluations
    # Memory reads per satellite: 6 doubles (state) = 48 bytes
    # Memory writes: 6 doubles = 48 bytes
    # AI_theoretical ≈ 120 * 2 / 96 ≈ 2.5 FLOP/byte
    THEORETICAL_AI = 2.5

    if args.ncu_mode:
        csv_text = run_ncu_and_collect(n=5000)
        if csv_text:
            flops, total_bytes = parse_ncu_csv(csv_text)
            if total_bytes > 0 and flops > 0:
                ai = flops / total_bytes
                # Estimated time: ~5ms for 5000 sats × 100 steps
                try:
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cpp", "build"))
                    import physics_engine as pe
                    import time
                    states = np.random.randn(5000, 6).astype(np.float64)
                    states[:, 0] += 6778.0; states[:, 4] += 7.66
                    t0 = time.perf_counter()
                    pe.cuda_propagate_batch(states, 10.0, 100)
                    elapsed = time.perf_counter() - t0
                    achieved_gflops = (flops / elapsed) / 1e9
                    has_ncu_data = True
                    print(f"  AI = {ai:.2f} FLOP/byte")
                    print(f"  Performance = {achieved_gflops:.1f} GFLOPS/s")
                except Exception as e:
                    print(f"  Could not measure time: {e}")

    if not has_ncu_data:
        # Theoretical ceiling point: AI ≈ 2.5.
        ai = THEORETICAL_AI
        achieved_gflops = None
        print(f"  Using theoretical values: AI={ai:.2f}, roofline ceiling≈{min(PEAK_BW * ai, PEAK_FP64):.1f} GFLOPS/s")
        print("  To get measured values: sudo ncu ... python validation/cuda_roofline.py --ncu-mode")

    path = plot_roofline(
        ai,
        achieved_gflops,
        "RK4 k_prop_aos",
        has_ncu_data,
        estimated_ceiling_gflops=min(PEAK_BW * ai, PEAK_FP64),
    )
    print(f"  Saved: {path}")
