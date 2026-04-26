"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — fleet_service.py
 Registry for Satellites and Debris
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from ..models import Satellite, Debris, Vector3
from ..core.physics import eci_to_latlon, latlon_to_eci
import numpy as np

class FleetService:
    def __init__(self):
        self.satellites: Dict[str, Satellite] = {}
        self.debris: Dict[str, Debris] = {}

    def add_satellite(self, sat: Satellite):
        # Initialize nominal slot to starting state (Section 5.2)
        sat.nominal_r = sat.r.model_copy()
        sat.nominal_v = sat.v.model_copy()
        sat.is_nominal = True
        sat.uptime_seconds = 0.0
        self.satellites[sat.id] = sat

    def add_debris(self, deb: Debris):
        self.debris[deb.id] = deb

    def update_satellite_state(self, sat_id: str, r: np.ndarray, v: np.ndarray, dt: float = 0.0, sim_time: Optional[datetime] = None):
        """Updates internal state and converts back to Geodetic for UI."""
        if sat_id in self.satellites:
            sat = self.satellites[sat_id]
            sat.r = Vector3.from_np(r)
            sat.v = Vector3.from_np(v)
            
            # 1. Update Geodetic with Earth Rotation awareness
            lat, lon, alt = eci_to_latlon(r, t=sim_time)
            sat.lat = float(lat)
            sat.lon = float(lon)
            sat.alt_km = float(alt)

            # 2. Propagate Nominal Slot (Unperturbed Keplerian)
            # Reference Section 5.2: "dynamic reference point propagating along ideal unperturbed orbit"
            # Upgrade from Euler to RK4 for high-fidelity unperturbed tracking
            if dt > 0:
                from ..core.physics import J2RK4Propagator
                prop = J2RK4Propagator()
                r_nom_np = sat.nominal_r.to_np()
                v_nom_np = sat.nominal_v.to_np()
                
                # Propagate without J2 (ideal unperturbed orbit)
                r_nom_next, v_nom_next = prop.propagate(r_nom_np, v_nom_np, dt, including_j2=False)
                
                sat.nominal_r = Vector3.from_np(r_nom_next)
                sat.nominal_v = Vector3.from_np(v_nom_next)

            # 3. Station-Keeping Drift Check (10km Sphere)
            dist_km = np.linalg.norm(r - sat.nominal_r.to_np())
            was_nominal = sat.is_nominal
            sat.is_nominal = bool(dist_km <= 10.0)
            
            # 4. Exponential Uptime Score (Section 5.2 Requirement)
            # Degradation formula: Score = Score * e^(-lambda * dt)
            # lambda = 0.0001925 per second (~50% decay per hour)
            LAMBDA_DECAY = 0.0001925 
            
            if sat.is_nominal:
                sat.uptime_seconds += dt
                # Recovery: Score slowly returns when nominal (e.g. 1% per minute)
                sat.uptime_score = min(1.0, sat.uptime_score + (0.00016 * dt))
            else:
                # Active Decay
                decay_factor = np.exp(-LAMBDA_DECAY * dt)
                sat.uptime_score *= decay_factor
                
                # Log Outage Event
                if was_nominal:
                    from datetime import datetime, timezone
                    sat.outage_events.append({
                        "id": f"OUTAGE-{len(sat.outage_events) + 1}",
                        "start_dist_km": round(float(dist_km), 3),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    sat.status = "OFF_STATION"
            
            if not was_nominal and sat.is_nominal:
                if sat.status == "OFF_STATION":
                    sat.status = "NOMINAL"

    def get_satellites_list(self) -> List[Dict]:
        return [s.model_dump() for s in self.satellites.values()]

    def get_debris_snapshot(self) -> List[List]:
        """Returns flattened [ID, lat, lon, alt] as required by Section 6.3."""
        return [
            [d.id, d.lat, d.lon, d.alt_km] 
            for d in self.debris.values()
        ]

    def deduct_fuel(self, sat_id: str, amount_kg: float):
        if sat_id in self.satellites:
            self.satellites[sat_id].fuel_kg = max(0.0, self.satellites[sat_id].fuel_kg - amount_kg)
            if self.satellites[sat_id].fuel_kg < 2.5: # 5% EOL threshold
                self.satellites[sat_id].status = "EOL"
