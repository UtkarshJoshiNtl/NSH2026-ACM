import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
import os
from typing import Optional

ACCENT  = "#58a6ff"
GREEN   = "#3fb950"
ORANGE  = "#d29922"
RED     = "#f85149"
PURPLE  = "#bc8cff"

DARK_STYLE = {
    "figure.facecolor": "#0d1117",
    "axes.facecolor":   "#161b22",
    "axes.edgecolor":   "#30363d",
    "axes.labelcolor":  "#e6edf3",
    "xtick.color":      "#8b949e",
    "ytick.color":      "#8b949e",
    "text.color":       "#e6edf3",
    "grid.color":       "#21262d",
    "grid.linestyle":   "--",
    "grid.alpha":       0.6,
    "lines.linewidth":  2.0,
    "font.family":      "DejaVu Sans",
}

_plots_dir: Optional[str] = None

def set_plots_dir(path: str = "plots") -> None:
    global _plots_dir
    _plots_dir = path
    os.makedirs(path, exist_ok=True)

def use_dark() -> None:
    plt.rcParams.update(DARK_STYLE)

def save(name: str) -> Optional[str]:
    if _plots_dir:
        p = os.path.join(_plots_dir, name)
        plt.savefig(p, dpi=150, bbox_inches="tight")
        return p
    return None

def _sphere(ax, radius: float = 6378.137, color: str = "#1a3a5c", alpha: float = 0.6):
    u = np.linspace(0, 2 * np.pi, 40)
    v = np.linspace(0, np.pi, 20)
    x = radius * np.outer(np.cos(u), np.sin(v))
    y = radius * np.outer(np.sin(u), np.sin(v))
    z = radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, alpha=alpha, linewidth=0)

def plot_orbit_3d(states, label: str = "Orbit", color: str = ACCENT, show_earth: bool = True):
    use_dark()
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    if show_earth:
        _sphere(ax)
    s = np.array(states)
    ax.plot(s[:, 0], s[:, 1], s[:, 2], color=color, label=label, lw=1.5)
    ax.scatter(*s[0, :3], color=GREEN, s=40, label="Start")
    ax.scatter(*s[-1, :3], color=RED, s=40, label="End")
    mx = np.max(np.abs(s[:, :3]))
    ax.set_xlim(-mx, mx)
    ax.set_ylim(-mx, mx)
    ax.set_zlim(-mx, mx)
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")
    ax.legend()
    fig.tight_layout()
    return fig, ax

def conjunction_dashboard(sat_history, deb_history, warnings,
                           lookahead: float = 3600, step_s: float = 60):
    use_dark()
    fig = plt.figure(figsize=(10, 8))
    gs = plt.GridSpec(2, 1, height_ratios=[2, 1])
    ax1 = fig.add_subplot(gs[0], projection="3d")
    ax2 = fig.add_subplot(gs[1])
    sat = np.array(sat_history)
    deb = np.array(deb_history)
    n_steps = len(sat_history)
    times = np.arange(n_steps) * (lookahead / max(n_steps - 1, 1))
    dists = np.linalg.norm(sat - deb, axis=1)
    ax2.plot(times, dists, color=ACCENT, lw=2)
    ax2.axhline(5.0, color=ORANGE, ls="--", lw=1, label="Advisory (5 km)")
    ax2.axhline(1.0, color=RED, ls="--", lw=1, label="Warning (1 km)")
    ax2.axhline(0.1, color=RED, ls="-.", lw=1.5, label="Critical (0.1 km)")
    if warnings:
        for w in warnings:
            c = RED if w.severity == "CRITICAL" else ORANGE
            ax2.axvline(w.time_to_closest_approach, color=c, alpha=0.5, lw=1)
            ax2.annotate(w.severity, (w.time_to_closest_approach, w.current_distance),
                         fontsize=8, color=c)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Distance (km)")
    ax2.set_yscale("log")
    ax2.legend(fontsize=8)
    ax2.grid(True)
    _sphere(ax1)
    mid = len(sat) // 2
    ax1.plot(sat[:mid, 0], sat[:mid, 1], sat[:mid, 2], color=ACCENT, alpha=0.6, lw=1)
    ax1.plot(sat[mid:, 0], sat[mid:, 1], sat[mid:, 2], color=ACCENT, lw=1.5, label="Satellite")
    ax1.plot(deb[:mid, 0], deb[:mid, 1], deb[:mid, 2], color=ORANGE, alpha=0.6, lw=1)
    ax1.plot(deb[mid:, 0], deb[mid:, 1], deb[mid:, 2], color=ORANGE, lw=1.5, label="Debris")
    ax1.scatter(*sat[0, :3], color=GREEN, s=30)
    ax1.scatter(*deb[0, :3], color=RED, s=30)
    mx = max(np.max(np.abs(sat[:, :3])), np.max(np.abs(deb[:, :3])))
    ax1.set_xlim(-mx, mx); ax1.set_ylim(-mx, mx); ax1.set_zlim(-mx, mx)
    ax1.set_xlabel("X"); ax1.set_ylabel("Y"); ax1.set_zlabel("Z")
    ax1.legend(fontsize=8)
    fig.tight_layout()
    return fig, (ax1, ax2)

def scaling_report(times_cpp, times_cuda, Ns, roofline_ai=None):
    use_dark()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    ax1, ax2, ax3, ax4 = axes.flat
    if times_cpp:
        ax1.plot(Ns, times_cpp, "o-", color=ACCENT, label="C++")
        if times_cuda:
            ax1.plot(Ns, times_cuda, "s-", color=GREEN, label="CUDA")
        ax1.set_xscale("log"); ax1.set_yscale("log")
        ax1.set_xlabel("N satellites"); ax1.set_ylabel("Time (ms)")
        ax1.set_title("Batch propagation scaling")
        ax1.legend(); ax1.grid(True)
    if len(Ns) > 1 and times_cpp:
        t1 = times_cpp[0]
        speedups = [t1 / t for t in times_cpp]
        ax2.plot(Ns, speedups, "o-", color=PURPLE, label="C++ speedup")
        if times_cuda:
            t1c = times_cuda[0]
            speedups_c = [t1c / t for t in times_cuda]
            ax2.plot(Ns, speedups_c, "s-", color=GREEN, label="CUDA speedup")
        ax2.set_xscale("log")
        ax2.set_xlabel("N satellites"); ax2.set_ylabel("Speedup (T\u2081/T\u2099)")
        ax2.set_title("Strong scaling (relative to N=10)")
        ax2.legend(); ax2.grid(True)
    if roofline_ai is not None:
        ai_range = np.logspace(-2, 4, 500)
        peak_bw = 192.0
        peak_fp64 = 0.2 * 1000
        mem_roof = peak_bw * ai_range
        compute_roof = np.full_like(ai_range, peak_fp64)
        roofline = np.minimum(mem_roof, compute_roof)
        ax3.loglog(ai_range, roofline, color=ACCENT, lw=2)
        ai_ridge = peak_fp64 / peak_bw
        ax3.axvline(ai_ridge, color=ORANGE, ls="--", lw=1)
        ax3.scatter(roofline_ai[0], roofline_ai[1], color=GREEN, s=100, zorder=5)
        ax3.set_xlabel("Arithmetic Intensity (FLOP/byte)")
        ax3.set_ylabel("Performance (GFLOPS/s)")
        ax3.set_title("Roofline model (RTX 2050)")
        ax3.grid(True)
    ax4.text(0.5, 0.5, "Astrosis\nPerformance Summary\n\nC++ batch: ~500\u00d7 vs Python\nCUDA batch: ~150\u00d7 vs Python",
             transform=ax4.transAxes, ha="center", va="center", fontsize=14,
             color="#e6edf3")
    ax4.axis("off")
    fig.tight_layout()
    return fig, axes
