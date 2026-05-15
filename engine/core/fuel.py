"""
astrosis/physics/fuel.py — Propellant Consumption Tracker
=========================================================
Implements the Tsiolkovsky Rocket Equation for mass budgeting.
"""

import math
from ..constants import ISP, G0, G0_KM, DRY_MASS, INITIAL_FUEL


class FuelTracker:
    def __init__(self, initial_fuel: float = INITIAL_FUEL, dry_mass: float = DRY_MASS):
        self.fuel_kg = initial_fuel
        self.initial_fuel_kg = initial_fuel
        self.dry_mass = dry_mass

    def current_mass(self) -> float:
        """Returns total current mass [kg]."""
        return self.dry_mass + self.fuel_kg

    def fuel_percentage(self) -> float:
        """Returns percentage of fuel remaining."""
        return (self.fuel_kg / self.initial_fuel_kg) * 100.0 if self.initial_fuel_kg > 0 else 0.0

    def is_critical(self) -> bool:
        """True if fuel is below 10%."""
        return self.fuel_percentage() < 10.0

    def is_empty(self) -> bool:
        """True if fuel is depleted."""
        return self.fuel_kg <= 0.0

    def calculate_fuel_cost(self, delta_v: list) -> float:
        """
        Calculate propellant consumed [kg] for a given ΔV [km/s].
        Δm = m0 * (1 - exp(-dv / (Isp * g0)))
        """
        dv_mag = math.sqrt(sum(d * d for d in delta_v))
        if dv_mag == 0:
            return 0.0
        
        # Isp is in seconds, g0 is in m/s^2. We need dv in m/s.
        # Alternatively, use g0 in km/s^2.
        m0 = self.current_mass()
        fuel_used = m0 * (1.0 - math.exp(-dv_mag / (ISP * G0_KM)))
        return fuel_used

    def apply_burn(self, delta_v: list) -> None:
        """Consume propellant and update internal state."""
        cost = self.calculate_fuel_cost(delta_v)
        self.fuel_kg = max(0.0, self.fuel_kg - cost)
