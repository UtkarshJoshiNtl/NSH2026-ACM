"""
engine/simulation.py — Thin orchestration wrapper.
==================================================
Exposes a clean high-level API backed by the accelerator tier.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ObjectState:
    id: str
    obj_type: str
    r: List[float]
    v: List[float]
    status: str = "NOMINAL"


class SimulationContext:
    def __init__(self, start_time: float = 0.0):
        self.objects: Dict[str, ObjectState] = {}
        self.simulation_time: float = start_time

    def get_all_satellites(self) -> List[ObjectState]:
        return [o for o in self.objects.values() if o.obj_type == "SATELLITE"]

    def propagate_batch(self, states: list, dt_seconds: float, steps: int,
                        area: float = 0.0, mass: float = 1.0,
                        cd: float = 2.2, cr: float = 1.5, with_drag: bool = False,
                        mjd0: float = 0.0) -> list:
        from .core.accelerator import propagate_batch
        return propagate_batch(states, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0)

    def conjunction_assessment(self, sat_states: list, debris_states: list,
                                lookahead: float = 86400.0,
                                step_s: float = 60.0,
                                mjd0: float = 0.0) -> list:
        from .core.accelerator import detect_conjunctions
        return detect_conjunctions(sat_states, debris_states, lookahead, step_s, mjd0)

    def advance_time(self, dt_seconds: float) -> None:
        sats = self.get_all_satellites()
        if not sats:
            self.simulation_time += dt_seconds
            return
        sat_states = [s.r + s.v for s in sats]
        new_states = self.propagate_batch(sat_states, dt_seconds, 1)
        for i, s in enumerate(sats):
            s.r = new_states[i][:3]
            s.v = new_states[i][3:]
        self.simulation_time += dt_seconds
