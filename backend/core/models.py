from dataclasses import dataclass, field
from typing import List

@dataclass
class ObjectState:
    id: str
    obj_type: str                    # "SATELLITE" | "DEBRIS"
    r: List[float]                   # [x, y, z] km ECI
    v: List[float]                   # [vx, vy, vz] km/s ECI
    m_fuel: float = 50.0             # kg (satellites only)
    dry_mass: float = 500.0          # kg
    last_burn_time: float = 0.0      # Unix timestamp of last burn
    nominal_slot: List[float] = field(default_factory=list)  # [x,y,z] km ECI
    status: str = "NOMINAL"          # NOMINAL | WARNING | CRITICAL | EOL


@dataclass
class Satellite(ObjectState):
    """Satellite-specific state with additional properties."""
    def __init__(self, id: str, r: List[float], v: List[float], mass: float = 1000.0):
        super().__init__(
            id=id,
            obj_type="SATELLITE",
            r=r,
            v=v,
            dry_mass=mass,
            m_fuel=50.0
        )


@dataclass
class ScheduledBurn:
    burn_id: str
    satellite_id: str
    burn_time: float                 # Unix timestamp when to execute
    delta_v: List[float]             # [dvx, dvy, dvz] km/s ECI
    burn_type: str = "EVASION"       # EVASION | RECOVERY | STATION_KEEP | GRAVEYARD
    executed: bool = False
