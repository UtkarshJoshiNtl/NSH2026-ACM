import math
from ..constants import ISP, G0, G0_KM, DRY_MASS, INITIAL_FUEL

__all__ = ["FuelTracker"]


class FuelTracker:
    def __init__(self, initial_fuel: float = INITIAL_FUEL, dry_mass: float = DRY_MASS):
        self.fuel_kg = initial_fuel
        self.initial_fuel_kg = initial_fuel
        self.dry_mass = dry_mass

    def current_mass(self) -> float:
        return self.dry_mass + self.fuel_kg

    def fuel_percentage(self) -> float:
        return (self.fuel_kg / self.initial_fuel_kg) * 100.0 if self.initial_fuel_kg > 0 else 0.0

    def is_critical(self) -> bool:
        return self.fuel_percentage() < 10.0

    def is_empty(self) -> bool:
        return self.fuel_kg <= 0.0

    def calculate_fuel_cost(self, delta_v: list) -> float:
        dv_mag = math.sqrt(sum(d * d for d in delta_v))
        if dv_mag < 1e-15:
            return 0.0
        m0 = self.current_mass()
        fuel_used = m0 * (1.0 - math.exp(-dv_mag / (ISP * G0_KM)))
        return fuel_used

    def apply_burn(self, delta_v: list) -> None:
        cost = self.calculate_fuel_cost(delta_v)
        self.fuel_kg = max(0.0, self.fuel_kg - cost)
