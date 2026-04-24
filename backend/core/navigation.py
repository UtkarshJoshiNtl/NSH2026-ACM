"""
backend/core/navigation.py — RTN Frame Navigation
====================================================
Radial-Transverse-Normal coordinate frame transformations and maneuver planning.
Migrated from AutoCM for optimal fuel-efficient station-keeping and evasion.
"""

import numpy as np
from typing import Tuple

# Propulsion Constants
ISP_S = 300.0       # Specific Impulse (s)
G0_MS2 = 9.80665    # Standard Gravity (m/s^2)
M_DRY_KG = 500.0    # Dry Mass (kg)


class Navigator:
    """
    Handles orbital coordinate transforms (ECI <-> RTN) and maneuver math.
    RTN frame is the local orbital frame:
    - R (Radial): Points from Earth center through satellite
    - T (Transverse): Direction of velocity (in orbital plane)
    - N (Normal): Perpendicular to orbital plane (angular momentum direction)
    """

    @staticmethod
    def get_rtn_matrix(r_eci: np.ndarray, v_eci: np.ndarray) -> np.ndarray:
        """
        Computes the rotation matrix R from ECI to RTN frame.

        Args:
            r_eci: Position vector in ECI [x, y, z] km
            v_eci: Velocity vector in ECI [vx, vy, vz] km/s

        Returns:
            3x3 rotation matrix to transform ECI -> RTN
        """
        r_mag = np.linalg.norm(r_eci)
        if r_mag < 1e-9:
            return np.eye(3)

        # 1. Radial Unit Vector
        u_r = r_eci / r_mag

        # 2. Normal Unit Vector (Angular Momentum direction)
        h = np.cross(r_eci, v_eci)
        h_mag = np.linalg.norm(h)
        u_n = h / h_mag if h_mag > 1e-9 else np.array([0, 0, 1])

        # 3. Transverse Unit Vector (completes right-handed system)
        u_t = np.cross(u_n, u_r)

        # Matrix to transform ECI -> RTN is [u_r, u_t, u_n]^T
        return np.vstack([u_r, u_t, u_n])

    def eci_to_rtn(self, vec_eci: np.ndarray, r_eci: np.ndarray, v_eci: np.ndarray) -> np.ndarray:
        """
        Transforms a vector (like delta-v) from ECI to RTN.

        Args:
            vec_eci: Vector in ECI frame [x, y, z]
            r_eci: Satellite position in ECI [x, y, z] km
            v_eci: Satellite velocity in ECI [vx, vy, vz] km/s

        Returns:
            Vector in RTN frame [r, t, n]
        """
        m = self.get_rtn_matrix(r_eci, v_eci)
        return m @ vec_eci

    def rtn_to_eci(self, vec_rtn: np.ndarray, r_eci: np.ndarray, v_eci: np.ndarray) -> np.ndarray:
        """
        Transforms a vector (like delta-v) from RTN to ECI.

        Args:
            vec_rtn: Vector in RTN frame [r, t, n]
            r_eci: Satellite position in ECI [x, y, z] km
            v_eci: Satellite velocity in ECI [vx, vy, vz] km/s

        Returns:
            Vector in ECI frame [x, y, z]
        """
        m = self.get_rtn_matrix(r_eci, v_eci)
        # Transformation from RTN -> ECI is just the transpose (inverse)
        return m.T @ vec_rtn

    @staticmethod
    def compute_fuel_cost(m_current_kg: float, dv_mag_ms: float) -> float:
        """
        Tsiolkovsky Rocket Equation.

        Args:
            m_current_kg: Current wet mass (kg)
            dv_mag_ms: Delta-v magnitude (m/s)

        Returns:
            Fuel mass consumed (kg)
        """
        return m_current_kg * (1.0 - np.exp(-abs(dv_mag_ms) / (ISP_S * G0_MS2)))

    def plan_evasion(self, r_eci: np.ndarray, v_eci: np.ndarray, strategy: str = "T+") -> np.ndarray:
        """
        Calculates a standard evasion burn in RTN frame.

        Args:
            r_eci: Satellite position in ECI [x, y, z] km
            v_eci: Satellite velocity in ECI [vx, vy, vz] km/s
            strategy: Evasion strategy:
                'T+': Prograde (most efficient for altitude change)
                'T-': Retrograde
                'R+': Radial-out
                'N+': Normal (cross-track)

        Returns:
            Delta-v vector in ECI frame [x, y, z] km/s
        """
        dv_rtn = np.zeros(3)
        dv_mag_kms = 0.010  # 10 m/s as required for standoff

        if strategy == "T+":
            dv_rtn[1] = dv_mag_kms
        elif strategy == "T-":
            dv_rtn[1] = -dv_mag_kms
        elif strategy == "R+":
            dv_rtn[0] = dv_mag_kms
        elif strategy == "N+":
            dv_rtn[2] = dv_mag_kms

        return self.rtn_to_eci(dv_rtn, r_eci, v_eci)

    def plan_station_keeping(
        self,
        r_eci: np.ndarray,
        v_eci: np.ndarray,
        nominal_r_eci: np.ndarray,
        nominal_v_eci: np.ndarray
    ) -> np.ndarray:
        """
        Calculates a proportional RTN correction to return satellite to its nominal slot.

        Uses proportional control: correction magnitude = proportional_gain * drift_distance
        Clamped to 15.0 m/s maximum thrust limit.

        Args:
            r_eci: Current position in ECI [x, y, z] km
            v_eci: Current velocity in ECI [vx, vy, vz] km/s
            nominal_r_eci: Nominal position in ECI [x, y, z] km
            nominal_v_eci: Nominal velocity in ECI [vx, vy, vz] km/s

        Returns:
            Delta-v correction vector in ECI frame [x, y, z] km/s
        """
        # Calculate drift vector in ECI
        drift_eci = nominal_r_eci - r_eci
        drift_km = np.linalg.norm(drift_eci)

        if drift_km < 0.1:  # Negligible drift, no correction needed
            return np.zeros(3)

        # Convert drift to RTN frame for proportional control
        drift_rtn = self.eci_to_rtn(drift_eci, r_eci, v_eci)

        # Proportional gain: moderate correction (0.3) to avoid overshoot
        proportional_gain = 0.3
        dv_rtn = drift_rtn * proportional_gain

        # Convert to m/s for thrust limit check
        dv_m_s = dv_rtn * 1000.0  # RTN is in km/s, convert to m/s
        dv_mag = np.linalg.norm(dv_m_s)

        # Clamp to 15.0 m/s thrust limit
        max_thrust = 15.0
        if dv_mag > max_thrust:
            dv_m_s = dv_m_s / dv_mag * max_thrust

        # Convert back to km/s for physics engine
        dv_km_s = dv_m_s / 1000.0

        # Convert RTN correction back to ECI
        return self.rtn_to_eci(dv_km_s, r_eci, v_eci)
