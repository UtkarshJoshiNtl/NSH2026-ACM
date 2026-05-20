from dataclasses import dataclass
from typing import Dict, List
from .constants import INITIAL_FUEL, DRY_MASS

@dataclass
class ObjectState:
    id: str
    obj_type: str
    r: List[float]
    v: List[float]
    m_fuel: float = INITIAL_FUEL
    dry_mass: float = DRY_MASS
    status: str = "NOMINAL"


class SimulationContext:
    def __init__(self, start_time: float = 0.0):
        self.objects: Dict[str, ObjectState] = {}
        self.simulation_time: float = start_time

    def get_all_satellites(self) -> List[ObjectState]:
        return [o for o in self.objects.values() if o.obj_type == "SATELLITE"]

    def load_initial_state(self, satellites_data: list, debris_data: list) -> None:
        for s in satellites_data:
            r = [s["r"]["x"], s["r"]["y"], s["r"]["z"]]
            v = [s["v"]["x"], s["v"]["y"], s["v"]["z"]]
            obj = ObjectState(
                id=s["id"],
                obj_type="SATELLITE",
                r=r,
                v=v,
                m_fuel=s.get("m_fuel", INITIAL_FUEL),
                dry_mass=s.get("dry_mass", DRY_MASS)
            )
            self.objects[obj.id] = obj

        for d in debris_data:
            r = [d["r"]["x"], d["r"]["y"], d["r"]["z"]]
            v = [d["v"]["x"], d["v"]["y"], d["v"]["z"]]
            obj = ObjectState(
                id=d["id"],
                obj_type="DEBRIS",
                r=r,
                v=v
            )
            self.objects[obj.id] = obj

    def advance_time(self, dt_seconds: float) -> None:
        from .core.accelerator import propagate_batch
        
        sats = self.get_all_satellites()
        if not sats:
            self.simulation_time += dt_seconds
            return
            
        sat_states = [s.r + s.v for s in sats]
        new_states = propagate_batch(sat_states, dt_seconds, 1)
        
        for i, s in enumerate(sats):
            s.r = new_states[i][:3]
            s.v = new_states[i][3:]
            
        self.simulation_time += dt_seconds
