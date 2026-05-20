from dataclasses import dataclass
from typing import List
import numpy as np

from .conjunction import ConjunctionWarning
from ..constants import MAX_DV, COOLDOWN_S, ISP, G0_KM

__all__ = ["ManeuverPlan", "ManeuverCalculator"]


@dataclass
class ManeuverPlan:
    evasion_dv_eci: List[float]
    recovery_dv_eci: List[float]
    fuel_cost_kg: float
    burn_timing_offset_s: float


def _fuel_cost(dv_mag: float, initial_fuel: float = 1000.0) -> float:
    return initial_fuel * (1.0 - np.exp(-dv_mag / (ISP * G0_KM)))


class ManeuverCalculator:
    def calculate(
        self, sat_state: List[float], warning: ConjunctionWarning
    ) -> ManeuverPlan:
        r = np.array(sat_state[:3])
        rv = np.array(warning.relative_velocity)
        rv_mag = np.linalg.norm(rv)

        if rv_mag < 1e-9:
            direction = r / np.linalg.norm(r)
        else:
            direction = np.cross(rv, r)
            d_mag = np.linalg.norm(direction)
            if d_mag < 1e-9:
                direction = r
            else:
                direction /= d_mag

        evasion_mag = min(MAX_DV, warning.current_distance / warning.time_to_closest_approach * 0.5)
        evasion_dv = list(direction * evasion_mag)
        recovery_dv = list(-direction * evasion_mag)

        fuel_cost = _fuel_cost(evasion_mag) + _fuel_cost(evasion_mag)

        return ManeuverPlan(
            evasion_dv_eci=evasion_dv,
            recovery_dv_eci=recovery_dv,
            fuel_cost_kg=fuel_cost,
            burn_timing_offset_s=max(0.0, warning.time_to_closest_approach - COOLDOWN_S),
        )
