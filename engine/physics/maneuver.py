"""
astrosis/physics/maneuver.py — Burn Planning Logic
==================================================
Calculates optimal impulsive burns for evasion and station-keeping.
"""

from dataclasses import dataclass
from typing import List
import numpy as np

from .fuel import FuelTracker
from .conjunction import ConjunctionWarning
from ..constants import MAX_DV, COOLDOWN_S


@dataclass
class ManeuverPlan:
    evasion_dv_eci: List[float]
    recovery_dv_eci: List[float]
    fuel_cost_kg: float
    burn_timing_offset_s: float


class ManeuverCalculator:
    def __init__(self):
        pass

    def _create_plan(self, sat_state: List[float], dv_eci: np.ndarray) -> ManeuverPlan:
        """Helper to calculate fuel cost and create a ManeuverPlan."""
        evasion_dv = list(dv_eci)
        recovery_dv = list(-dv_eci)
        
        tracker = FuelTracker()
        cost_evasion = tracker.calculate_fuel_cost(evasion_dv)
        tracker.apply_burn(evasion_dv)
        cost_recovery = tracker.calculate_fuel_cost(recovery_dv)
        
        return ManeuverPlan(
            evasion_dv_eci=evasion_dv,
            recovery_dv_eci=recovery_dv,
            fuel_cost_kg=cost_evasion + cost_recovery,
            burn_timing_offset_s=COOLDOWN_S
        )

    def calculate(
        self,
        sat_state: List[float],
        warning: ConjunctionWarning
    ) -> ManeuverPlan:
        """
        Calculate an evasion maneuver perpendicular to relative velocity (best miss).
        """
        r = np.array(sat_state[:3])
        v = np.array(sat_state[3:])
        rv = np.array(warning.relative_velocity)
        
        rv_mag = np.linalg.norm(rv)
        if rv_mag < 1e-9:
            # Fallback: when relative velocity is zero, burn radially outward
            r_hat = r / np.linalg.norm(r)
            return self._create_plan(sat_state, r_hat * MAX_DV)

        # Strategy: Burn in the "Normal" direction (h = r x v)
        h = np.cross(r, v)
        h_hat = h / np.linalg.norm(h)
        return self._create_plan(sat_state, h_hat * MAX_DV)
