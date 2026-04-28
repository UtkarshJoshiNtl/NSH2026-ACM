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
            return ManeuverPlan([0,0,0], [0,0,0], 0.0, 0.0)

        # Strategy: Burn in the "Normal" direction (h = r x v)
        # This changes the orbit inclination slightly, which is very effective for evasion
        # without changing orbital energy (semi-major axis).
        h = np.cross(r, v)
        h_hat = h / np.linalg.norm(h)
        
        # Evasion Delta-V
        evasion_dv_eci = h_hat * MAX_DV
        
        # Recovery Delta-V (equal and opposite to return to original orbit)
        recovery_dv_eci = -evasion_dv_eci
        
        # Calculate fuel cost
        tracker = FuelTracker()
        cost_evasion = tracker.calculate_fuel_cost(list(evasion_dv_eci))
        tracker.apply_burn(list(evasion_dv_eci))
        cost_recovery = tracker.calculate_fuel_cost(list(recovery_dv_eci))
        
        return ManeuverPlan(
            evasion_dv_eci=list(evasion_dv_eci),
            recovery_dv_eci=list(recovery_dv_eci),
            fuel_cost_kg=cost_evasion + cost_recovery,
            burn_timing_offset_s=COOLDOWN_S
        )
