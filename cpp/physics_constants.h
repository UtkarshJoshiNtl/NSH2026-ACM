#pragma once

// ── Orbital Mechanics ────────────────────────────────────────────────────────
constexpr double MU           = 398600.4418;      // Earth gravitational parameter [km³/s²]
constexpr double RE           = 6378.137;         // Earth equatorial radius [km]
constexpr double J2           = 1.08263e-3;       // J2 oblateness (EGM96)
constexpr double J3           = -2.53266e-6;      // J3 pear-shape (EGM96)
constexpr double J4           = -1.61990e-6;      // J4 (EGM96)
constexpr double OMEGA_EARTH  = 7.2921150e-5;    // Earth rotation rate [rad/s]

// ── Propulsion & Satellite Defaults ──────────────────────────────────────────
constexpr double ISP          = 300.0;            // Specific impulse [s]
constexpr double G0           = 9.80665;          // Standard gravity [m/s²]
constexpr double G0_KM        = G0 / 1000.0;      // Standard gravity [km/s²]
constexpr double DRY_MASS     = 500.0;            // Default satellite dry mass [kg]
constexpr double INITIAL_FUEL = 50.0;             // Default propellant load [kg]
constexpr double MAX_DV       = 0.015;            // Maximum single-burn ΔV [km/s]
constexpr double COOLDOWN_S   = 600.0;            // Thermal cooldown [s]

// ── Conjunction Thresholds ───────────────────────────────────────────────────
constexpr double CRITICAL_DISTANCE = 0.1;         // CRITICAL warning [km]
constexpr double WARNING_DISTANCE  = 1.0;         // WARNING [km]
constexpr double ADVISORY_DISTANCE = 5.0;         // ADVISORY [km]
