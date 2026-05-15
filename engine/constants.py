"""
astrosis/constants.py — All physics and operational constants
=============================================================
Single source of truth for every numerical constant used across the engine.
"""

# ── Orbital Mechanics ────────────────────────────────────────────────────────
MU = 398600.4418        # Earth gravitational parameter  [km³/s²]
RE = 6378.137           # Earth equatorial radius         [km]
J2 = 1.08263e-3         # Earth oblateness J2 (EGM96)   [dimensionless]
J3 = -2.53266e-6        # Earth pear-shape J3 (EGM96)   [dimensionless]
J4 = -1.61990e-6        # J4 (EGM96)                    [dimensionless]
OMEGA_EARTH = 7.2921150e-5  # Earth rotation rate         [rad/s]
MU_SUN = 132712440018.0 # Sun gravitational parameter    [km³/s²]
MU_MOON = 4902.800066   # Moon gravitational parameter   [km³/s²]


# ── WGS-84 Ellipsoid ─────────────────────────────────────────────────────────
F_WGS84  = 1.0 / 298.257223563
E2_WGS84 = 2 * F_WGS84 - F_WGS84 ** 2

# ── Conjunction Thresholds ───────────────────────────────────────────────────
CRITICAL_DISTANCE = 0.1   # CRITICAL warning threshold  [km]
WARNING_DISTANCE  = 1.0   # WARNING threshold            [km]
ADVISORY_DISTANCE = 5.0   # ADVISORY threshold           [km]

# ── Sun / Visibility / SRP ───────────────────────────────────────────────────
RS_SUN = 696340.0    # Solar radius                     [km]
AU     = 149597870.7 # Astronomical unit                [km]
P_SR   = 4.56e-6     # Solar radiation pressure @ 1 AU  [N/m²]
