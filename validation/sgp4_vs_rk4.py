"""Compare SGP4 vs RK4 position divergence over 72 hours (gravity, drag, full)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from sgp4.api import Satrec, jday
from engine.core.propagator import rk4_step
from engine.geo.frames import teme_to_eci
from engine.constants import RE, ISS_LINE1, ISS_LINE2

# ISS TLE imported from engine.constants

def run_research():
    print("Running SGP4 vs RK4 Research Comparison...")
    satrec = Satrec.twoline2rv(ISS_LINE1, ISS_LINE2)
    
    # Epoch
    epoch_dt = datetime(2025, 5, 15, 13, 0, 0)
    jd, jdf = jday(epoch_dt.year, epoch_dt.month, epoch_dt.day,
                   epoch_dt.hour, epoch_dt.minute, epoch_dt.second)
    mjd0 = 60810.54166667
    
    # Initial State at Epoch (from SGP4)
    _, r0_teme, v0_teme = satrec.sgp4(jd, jdf)
    r0_eci, v0_eci = teme_to_eci(np.array(r0_teme), np.array(v0_teme), epoch_dt)
    state0 = tuple(list(r0_eci) + list(v0_eci))
    
    dt = 60.0  # 1 minute steps
    hours = 72
    steps = int(hours * 3600 / dt)
    
    times = []
    err_rk4_grav = []
    err_rk4_drag = []
    err_rk4_full = []
    
    curr_grav = state0
    curr_drag = state0
    curr_full = state0
    
    # Satellite params
    area = 20.0; mass = 450.0; cd = 2.2; cr = 1.5
    
    for i in range(1, steps + 1):
        t_s = i * dt
        
        # 1. SGP4 Reference
        step_dt = epoch_dt + timedelta(seconds=t_s)
        jd2, jdf2 = jday(step_dt.year, step_dt.month, step_dt.day,
                         step_dt.hour, step_dt.minute, step_dt.second)
        _, r_sgp4, v_sgp4 = satrec.sgp4(jd2, jdf2)
        r_ref, _ = teme_to_eci(np.array(r_sgp4), np.array(v_sgp4), step_dt)
        
        # 2. Astrosis RK4 - Gravity only
        curr_grav = rk4_step(curr_grav, dt, mjd0=0.0)
        
        # 3. Astrosis RK4 - Gravity + Drag
        curr_drag = rk4_step(curr_drag, dt, mjd0=0.0, area=area, mass=mass, cd=cd)
        
        # 4. Astrosis RK4 - Full (Drag + SRP + Lunisolar)
        curr_full = rk4_step(curr_full, dt, mjd0=mjd0, current_step=i-1, 
                             area=area, mass=mass, cd=cd, cr=cr)
        
        if i % 10 == 0:  # Sample every 10 mins
            times.append(t_s / 3600.0)
            err_rk4_grav.append(np.linalg.norm(np.array(curr_grav[:3]) - r_ref))
            err_rk4_drag.append(np.linalg.norm(np.array(curr_drag[:3]) - r_ref))
            err_rk4_full.append(np.linalg.norm(np.array(curr_full[:3]) - r_ref))
            
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(times, err_rk4_grav, label="RK4 (Gravity Only) vs SGP4", alpha=0.7)
    plt.plot(times, err_rk4_drag, label="RK4 (Gravity + Drag) vs SGP4", alpha=0.7)
    plt.plot(times, err_rk4_full, label="RK4 (Full High-Fi) vs SGP4", linewidth=2.5)
    
    plt.xlabel("Time from Epoch (hours)")
    plt.ylabel("Position Difference (km)")
    plt.title("Astrosis Numerical Propagator vs SGP4 Analytical Baseline (ISS)")
    plt.grid(True, which="both", ls="--", alpha=0.5)
    plt.legend()
    
    out_path = "validation/plots/sgp4_vs_rk4_research.png"
    plt.savefig(out_path, dpi=150)
    print(f"Research plot saved to: {out_path}")
    
    print(f"Final 72h Divergence (Full vs SGP4): {err_rk4_full[-1]:.2f} km")

if __name__ == "__main__":
    run_research()
