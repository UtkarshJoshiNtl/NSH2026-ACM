#!/usr/bin/env python3
"""
test_physics.py  —  Astrosis Physics Engine Test Suite
==========================================================
Tests conjunction detection and maneuver planning via the physics_engine
pybind11 module.  Run from the project root after building:

    cd backend/cpp/build && make -j$(nproc)
    cd ../../.. && python3 test_physics.py
"""

import sys
import os
import math
import pytest

# ── Locate the built .so ─────────────────────────────────────────────────────
BUILD_DIR = os.path.join(os.path.dirname(__file__), "backend", "cpp", "build")
sys.path.insert(0, BUILD_DIR)

try:
    import physics_engine as pe
except ImportError as e:
    print(f"FATAL: Could not import physics_engine from {BUILD_DIR}: {e}")
    # Don't exit if running under pytest
    if "pytest" in sys.modules:
        pytest.skip("physics_engine not built", allow_module_level=True)
    else:
        sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
PASS = "✅ PASS"
FAIL = "❌ FAIL"

def check(name: str, condition: bool) -> bool:
    tag = PASS if condition else FAIL
    print(f"  {tag}  {name}")
    return condition

def vec_mag(v) -> float:
    return math.sqrt(sum(x*x for x in v))

# ─────────────────────────────────────────────────────────────────────────────
# Scenario Setup
# ─────────────────────────────────────────────────────────────────────────────
# Three satellites in circular-ish LEO (400 km altitude)
# StateVector: [x, y, z, vx, vy, vz]  (km, km/s)
RE     = 6378.137
ALT    = 400.0
R_LEO  = RE + ALT                   # ~6778 km
V_LEO  = math.sqrt(398600.4418 / R_LEO)   # ~7.669 km/s

# Satellites placed at 0°, 90°, 180° in the equatorial plane
sat_states = [
    [R_LEO,   0.0,  0.0,  0.0,  V_LEO,  0.0],   # Sat 0 — along +X
    [0.0,   R_LEO,  0.0, -V_LEO, 0.0,   0.0],   # Sat 1 — along +Y
    [-R_LEO,  0.0,  0.0,  0.0, -V_LEO,  0.0],   # Sat 2 — along -X
]

# ── 100 debris objects ───────────────────────────────────────────────────────
import random
random.seed(42)

CRITICAL_DIST  = 0.05    # 50 m in km  — CRITICAL threshold is 0.1 km
WARNING_DIST   = 0.8     # 800 m in km — WARNING threshold is 1.0 km

debris_states = []

# Debris #0 — direct collision course with Sat 0 (50 m offset along Y)
sat0 = sat_states[0]
debris_states.append([
    sat0[0] + CRITICAL_DIST, sat0[1],             sat0[2],
    sat0[3],                 sat0[4] - 1.0,        sat0[5],   # slightly closing velocity
])

# Debris #1 — 800 m from Sat 1 (WARNING)
sat1 = sat_states[1]
debris_states.append([
    sat1[0] + WARNING_DIST,  sat1[1],              sat1[2],
    sat1[3],                 sat1[4] - 0.5,        sat1[5],
])

# Debris #2..#99 — random positions away from all satellites (> 20 km)
for _ in range(98):
    angle = random.uniform(0, 2 * math.pi)
    inc   = random.uniform(-0.3, 0.3)
    r     = R_LEO + random.uniform(-50, 50)
    x = r * math.cos(angle)
    y = r * math.sin(angle) * math.cos(inc)
    z = r * math.sin(angle) * math.sin(inc)
    speed = math.sqrt(398600.4418 / r)
    # Velocity perpendicular to position
    vx = -speed * math.sin(angle)
    vy =  speed * math.cos(angle) * math.cos(inc)
    vz =  speed * math.cos(angle) * math.sin(inc)
    debris_states.append([x, y, z, vx, vy, vz])

assert len(debris_states) == 100, "Expected 100 debris objects"

# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Conjunction Detection
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 58)
print("  TEST SUITE: Astrosis PHYSICS ENGINE")
print("═" * 58)
print("\n[1] Conjunction Detection")

detector  = pe.ConjunctionDetector()
# Use a short lookahead (300 s, 30 s steps) so the test runs in < 1 s
warnings  = detector.detect(sat_states, debris_states, lookahead_s=300.0, step_s=30.0)

# Index warnings by (sat_id, debris_id)
warn_map = {(w.sat_id, w.debris_id): w for w in warnings}

all_passed = True

# Check 1a — CRITICAL conjunction on Sat 0, Debris 0
crit_found = (0, 0) in warn_map
all_passed &= check("CRITICAL conjunction detected (Sat 0, Debris 0)", crit_found)

if crit_found:
    cw = warn_map[(0, 0)]
    all_passed &= check(
        f"  severity == 'CRITICAL' (got '{cw.severity}')",
        cw.severity == "CRITICAL"
    )
    all_passed &= check(
        f"  distance < 0.1 km (got {cw.current_distance:.6f} km)",
        cw.current_distance < 0.1
    )

# Check 1b — WARNING conjunction on Sat 1, Debris 1
warn_found = (1, 1) in warn_map
all_passed &= check("WARNING conjunction detected (Sat 1, Debris 1)", warn_found)

if warn_found:
    ww = warn_map[(1, 1)]
    all_passed &= check(
        f"  severity == 'WARNING' (got '{ww.severity}')",
        ww.severity == "WARNING"
    )
    all_passed &= check(
        f"  distance < 1.0 km (got {ww.current_distance:.6f} km)",
        ww.current_distance < 1.0
    )

# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Maneuver Planning on the CRITICAL conjunction
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] Maneuver Calculator (CRITICAL conjunction)")

if not crit_found:
    print("  ⚠  Skipped — CRITICAL conjunction not found in detection step.")
    plan = None
else:
    calc = pe.ManeuverCalculator()
    plan = calc.calculate(sat_states[0], warn_map[(0, 0)])

    ev_mag = vec_mag(plan.evasion_dv_eci)
    rc_mag = vec_mag(plan.recovery_dv_eci)
    MAX_DV = 0.015  # km/s as specified

    all_passed &= check(
        f"  Evasion ΔV ≤ 0.015 km/s (got {ev_mag:.6f} km/s)",
        ev_mag <= MAX_DV + 1e-9
    )
    all_passed &= check(
        f"  Recovery ΔV ≤ 0.015 km/s (got {rc_mag:.6f} km/s)",
        rc_mag <= MAX_DV + 1e-9
    )
    all_passed &= check(
        f"  Evasion burn returned (|ΔV| > 0)",
        ev_mag > 1e-9
    )
    all_passed &= check(
        f"  Recovery burn returned (|ΔV| > 0)",
        rc_mag > 1e-9
    )
    all_passed &= check(
        f"  Evasion + Recovery are paired (both non-zero)",
        ev_mag > 1e-9 and rc_mag > 1e-9
    )
    all_passed &= check(
        f"  Fuel cost > 0 kg (got {plan.fuel_cost_kg:.4f} kg)",
        plan.fuel_cost_kg > 0.0
    )
    all_passed &= check(
        f"  Burn timing offset > 0 s (got {plan.burn_timing_offset_s:.1f} s)",
        plan.burn_timing_offset_s > 0.0
    )

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═" * 58)
if plan is not None:
    print(f"  Evasion  ΔV : {list(round(x,6) for x in plan.evasion_dv_eci)} km/s")
    print(f"  Recovery ΔV : {list(round(x,6) for x in plan.recovery_dv_eci)} km/s")
    print(f"  Fuel cost   : {plan.fuel_cost_kg:.4f} kg")
    print(f"  Burn offset : {plan.burn_timing_offset_s:.1f} s")
    print(f"  # Warnings  : {len(warnings)}")
    print("═" * 58)

result = "ALL CHECKS PASSED ✅" if all_passed else "SOME CHECKS FAILED ❌"
print(f"\n  {result}\n")

# Only exit if not running under pytest
if "pytest" not in sys.modules:
    sys.exit(0 if all_passed else 1)
