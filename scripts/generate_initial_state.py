#!/usr/bin/env python3
"""
generate_initial_state.py — Astrosis
Generate synthetic ECI state vectors for 55 satellites and 10,000 debris objects.

Orbital mechanics used:
  - Circular orbits (e = 0)
  - ECI frame (J2000), position in km, velocity in km/s
  - Standard orbital mechanics: v = sqrt(mu/r)

Output:
  data/initial_satellites.json
  data/initial_debris.json
"""

import json
import math
import random
import os

# ── Physical constants ────────────────────────────────────────────────────────
MU = 398600.4418   # km³/s²
RE = 6378.137      # km

random.seed(42)


def circular_orbit_eci(alt_km: float, inc_deg: float,
                        raan_deg: float, ta_deg: float) -> dict:
    """
    Compute ECI [x,y,z,vx,vy,vz] for a circular orbit.

    Parameters
    ----------
    alt_km   : altitude above spherical Earth (km)
    inc_deg  : inclination (deg)
    raan_deg : right ascension of ascending node (deg)
    ta_deg   : true anomaly / argument of latitude (deg)

    Returns
    -------
    dict with keys 'r' ([x,y,z] km) and 'v' ([vx,vy,vz] km/s)
    """
    r_mag = RE + alt_km
    v_mag = math.sqrt(MU / r_mag)

    inc  = math.radians(inc_deg)
    raan = math.radians(raan_deg)
    ta   = math.radians(ta_deg)

    # Position in perifocal frame (circular → r = r_mag everywhere)
    p_x =  r_mag * math.cos(ta)
    p_y =  r_mag * math.sin(ta)

    # Velocity in perifocal frame (circular → perpendicular to radius)
    pv_x = -v_mag * math.sin(ta)
    pv_y =  v_mag * math.cos(ta)

    # Rotation matrix: perifocal → ECI  (Rz(-Ω) Rx(-i) Rz(-ω), ω=0 for 0-RAAN frame)
    cos_raan, sin_raan = math.cos(raan), math.sin(raan)
    cos_inc,  sin_inc  = math.cos(inc),  math.sin(inc)

    # Row vectors of the rotation matrix
    m = [
        [ cos_raan, -sin_raan * cos_inc,  sin_raan * sin_inc],
        [ sin_raan,  cos_raan * cos_inc, -cos_raan * sin_inc],
        [       0,              sin_inc,             cos_inc],
    ]

    def rot(px_, py_):
        x = m[0][0]*px_ + m[0][1]*py_
        y = m[1][0]*px_ + m[1][1]*py_
        z = m[2][0]*px_ + m[2][1]*py_
        return [x, y, z]

    r_eci = rot(p_x, p_y)
    v_eci = rot(pv_x, pv_y)
    return {"r": [round(c, 4) for c in r_eci],
            "v": [round(c, 6) for c in v_eci]}


# ── Generate 55 satellites ────────────────────────────────────────────────────
print("Generating satellites …")
satellites = []

# Define orbital planes: 5 planes × 11 satellites each
planes_inc = [45.0, 55.0, 70.0, 87.0, 97.6]   # inclinations (deg)
sat_idx = 0

for plane_i, inc in enumerate(planes_inc):
    raan = plane_i * 36.0           # 36° between planes
    alt = 500.0 + plane_i * 10.0   # 500–540 km altitude
    n_sats = 11

    for j in range(n_sats):
        ta = j * (360.0 / n_sats)
        state = circular_orbit_eci(alt, inc, raan, ta)
        sat_id = f"SAT-{sat_idx:03d}"
        entry = {
            "id":              sat_id,
            "type":            "SATELLITE",
            "r":               {"x": state["r"][0], "y": state["r"][1], "z": state["r"][2]},
            "v":               {"x": state["v"][0], "y": state["v"][1], "z": state["v"][2]},
            "m_fuel":          50.0,
            "dry_mass":        500.0,
            "last_burn_time":  0.0,
            "nominal_slot":    {"x": state["r"][0], "y": state["r"][1], "z": state["r"][2]},
            "status":          "NOMINAL",
        }
        satellites.append(entry)
        sat_idx += 1

print(f"  → {len(satellites)} satellites")

# ── Generate 10,000 debris ────────────────────────────────────────────────────
print("Generating debris …")
debris_list = []

for i in range(10000):
    alt     = random.uniform(400, 600)
    inc     = random.uniform(0, 180)
    raan    = random.uniform(0, 360)
    ta      = random.uniform(0, 360)
    state   = circular_orbit_eci(alt, inc, raan, ta)
    deb_id  = f"DEB-{i:05d}"
    entry = {
        "id":   deb_id,
        "type": "DEBRIS",
        "r":    {"x": state["r"][0], "y": state["r"][1], "z": state["r"][2]},
        "v":    {"x": state["v"][0], "y": state["v"][1], "z": state["v"][2]},
    }
    debris_list.append(entry)

print(f"  → {len(debris_list)} debris objects")

# ── Write files ───────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)

sats_path   = "data/initial_satellites.json"
debris_path = "data/initial_debris.json"

with open(sats_path, "w") as f:
    json.dump(satellites, f, indent=2)

with open(debris_path, "w") as f:
    json.dump(debris_list, f, indent=2)

print(f"\nWrote → {sats_path}  ({os.path.getsize(sats_path)//1024} KB)")
print(f"Wrote → {debris_path}  ({os.path.getsize(debris_path)//1024} KB)")
print("Done. ✅")
