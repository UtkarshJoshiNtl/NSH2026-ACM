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


# ── WGS-84 Ellipsoid ─────────────────────────────────────────────────────────
F_WGS84  = 1.0 / 298.257223563
E2_WGS84 = 2 * F_WGS84 - F_WGS84 ** 2

# ── Propulsion ───────────────────────────────────────────────────────────────
ISP          = 300.0    # Specific impulse              [s]
G0           = 9.80665  # Standard gravity              [m/s²]
G0_KM        = G0 / 1000.0  # Standard gravity         [km/s²]
DRY_MASS     = 500.0    # Default satellite dry mass    [kg]
INITIAL_FUEL = 50.0     # Default propellant load       [kg]
MAX_DV       = 0.015    # Maximum single-burn ΔV        [km/s]
COOLDOWN_S   = 600.0    # Thermal cooldown between burns [s]

# ── Conjunction Thresholds ───────────────────────────────────────────────────
CRITICAL_DISTANCE = 0.1   # CRITICAL warning threshold  [km]
WARNING_DISTANCE  = 1.0   # WARNING threshold            [km]
ADVISORY_DISTANCE = 5.0   # ADVISORY threshold           [km]

# ── Sun / Visibility ─────────────────────────────────────────────────────────
RS_SUN = 696340.0    # Solar radius                     [km]
AU     = 149597870.7 # Astronomical unit                [km]
