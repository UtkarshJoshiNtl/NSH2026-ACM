"""
═══════════════════════════════════════════════════════════════════════════
 ACM API — state_manager.py
 Central Facade for v2 Services
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import os
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from .models import Satellite, Debris, Vector3, Maneuver, CDM
from .services.fleet_service import FleetService
from .services.conjunction_service import ConjunctionService
from .services.maneuver_service import ManeuverService
from .services.comms_service import CommsService
from .services.simulation_service import SimulationService
from .services.decision_service import DecisionService

class StateManager:
    """
    Lightweight facade for AutoCM v2.
    Coordinates specialized services while maintaining backward compatibility
    with existing FastAPI routers.
    """

    def __init__(self):
        # 1. Initialize Services
        self.fleet = FleetService()
        self.conj = ConjunctionService()
        self.maneuver = ManeuverService()
        
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.comms = CommsService(os.path.join(data_dir, "ground_stations.csv"))
        
        # Inject alert callback to decision service for automated mission logs
        self.decision = DecisionService(self.fleet, self.maneuver, alert_callback=self._add_alert, comms_service=self.comms)
        
        self.sim = SimulationService(self.fleet, self.conj, self.maneuver, self.comms, self.decision)
        
        # 2. Local State for UI and WebSockets
        self._ws_clients = set()
        self.alerts = []
        self._alert_counter = 0
        self.real_interval_ms = 1000  # ms between sim ticks

    def reset(self):
        """Reset the system state for testing (re-initializes services)."""
        self.fleet = FleetService()
        self.conj = ConjunctionService()
        self.maneuver = ManeuverService()
        self.decision = DecisionService(self.fleet, self.maneuver, alert_callback=self._add_alert, comms_service=self.comms)
        self.sim = SimulationService(self.fleet, self.conj, self.maneuver, self.comms, self.decision)
        self.alerts = []
        self._alert_counter = 0
        self._ws_clients = set()
        self.real_interval_ms = 1000

    def _rtn_to_eci(self, r: Any, v: Any, dr_rtn: Any) -> Dict[str, float]:
        """
        Facade for coordinate conversion logic. 
        Transforms a relative vector in RTN to the absolute ECI frame.
        Handles dict, Vector3, or np.ndarray inputs for robustness.
        Returns: dict {x, y, z}
        """
        def _to_np(val):
            if isinstance(val, dict):
                # Handle both {x,y,z} and {radial,transverse,normal}
                return np.array([val.get('x', val.get('radial', 0)), 
                                val.get('y', val.get('transverse', 0)), 
                                val.get('z', val.get('normal', 0))])
            if hasattr(val, 'to_np'):
                return val.to_np()
            if isinstance(val, (list, tuple)):
                return np.array(val)
            return val

        r_np = _to_np(r)
        v_np = _to_np(v)
        dr_np = _to_np(dr_rtn)

        from .core.navigation import Navigator
        nav = Navigator()
        res_np = nav.rtn_to_eci(dr_np, r_np, v_np)
        
        return {"x": float(res_np[0]), "y": float(res_np[1]), "z": float(res_np[2])}

    # ── Backward Compatible Properties ─────────────────────────────────────
    
    @property
    def satellites(self): return self.fleet.satellites
    
    @property
    def debris(self): return self.fleet.debris
    
    @property
    def sim_time(self): return self.sim.sim_time
    
    @property
    def cdms(self): return self.conj.active_cdms
    
    @property
    def maneuvers(self):
        """Return maneuvers serialized for the frontend with consistent field names.
        Includes both scheduled (PENDING) and recently executed burns.
        """
        def _serialize(burn, override_status=None):
            dv = burn.deltaV_vector
            bid = burn.burn_id
            if 'RECOVERY' in bid or 'REC' in bid:
                burn_type = 'RECOVERY BURN'
            elif 'GRAVEYARD' in bid or 'EOL' in bid:
                burn_type = 'GRAVEYARD BURN'
            elif 'SK-CORRECT' in bid:
                burn_type = 'COOLDOWN'
            else:
                burn_type = 'EVASION BURN'
            return {
                "burnId":       bid,
                "burn_id":      bid,
                "satelliteId":  burn.satelliteId,
                "burnTime":     burn.burnTime.isoformat(),
                "type":         burn_type,
                "status":       override_status or burn.status,
                "duration":     180,
                "deltaV":       {"x": dv.x, "y": dv.y, "z": dv.z},
                "deltaV_vector":{"x": dv.x, "y": dv.y, "z": dv.z},
                "fuelCost":     round(burn.fuel_cost_kg, 4),
                "fuel_cost_kg": round(burn.fuel_cost_kg, 4),
            }

        result = []
        # Scheduled (PENDING) burns
        for sat_burns in self.maneuver.scheduled_burns.values():
            for burn in sat_burns:
                result.append(_serialize(burn))
        # Recently executed burns (last 20) — needed for scatter chart
        for burn in self.maneuver.executed_burns[-20:]:
            result.append(_serialize(burn, override_status="EXECUTED"))
        return result

    @property
    def ws_clients(self): return self._ws_clients

    @property
    def sim_running(self): return self.sim.running
    @sim_running.setter
    def sim_running(self, val): self.sim.running = val

    @property
    def step_seconds(self): return self.sim.step_seconds
    @step_seconds.setter
    def step_seconds(self, val): self.sim.step_seconds = val

    # ── Data Loading ──────────────────────────────────────────────────────

    def load_catalog(self, catalog_path: str):
        """Loads satellites and debris from catalog.json."""
        if not os.path.exists(catalog_path):
            print(f"[StateManager] Catalog not found: {catalog_path}")
            return

        with open(catalog_path, "r") as f:
            data = json.load(f)

        for s in data.get("satellites", []):
            # Convert dict to Satellite model
            sat = Satellite(
                id=s['id'],
                r=Vector3(**s['state']['r']),
                v=Vector3(**s['state']['v']),
                fuel_kg=s.get('mass_fuel', 50.0),
                status=s.get('status', 'NOMINAL')
            )
            # Pre-calculate lat/lon/alt
            from .core.physics import eci_to_latlon
            sat.lat, sat.lon, sat.alt_km = eci_to_latlon(sat.r.to_np())
            self.fleet.add_satellite(sat)

        for d in data.get("debris", []):
            deb = Debris(
                id=d['id'],
                r=Vector3(**d['state']['r']),
                v=Vector3(**d['state']['v']),
                lat=0, lon=0, alt_km=0 # Placeholder till calculated
            )
            from .core.physics import eci_to_latlon
            new_r = deb.r.to_np()
            deb.lat, deb.lon, deb.alt_km = eci_to_latlon(new_r)
            self.fleet.add_debris(deb)

    # ── Simulation Facade ─────────────────────────────────────────────────

    def simulate_step(self, dt: float):
        return self.sim.step(dt)

    # ── Validation & Execution ────────────────────────────────────────────

    def validate_maneuver(self, sat_id: str, burn_time: datetime, delta_v: dict, **kwargs) -> dict:
        """
        Validates maneuver against Section 4.2 & 5 constraints.
        """
        sat = self.fleet.satellites.get(sat_id)
        if not sat:
            return {"valid": False, "errors": ["Satellite not found"]}

        errors = []
        
        # Note: LOS check is handled in ManeuverService.schedule_burns for queueing
        # We don't reject here to allow blackout queueing (Section 5.4)
        has_los = True  # Default to True since queueing handles blackout scenarios

        # 1. Thrust Limit Check (Section 5.1)
        # delta_v is in m/s
        dv_mag = np.linalg.norm(np.array([delta_v['x'], delta_v['y'], delta_v['z']]))
        if dv_mag > 15.0:
            errors.append(f"Thrust limit violation (15.0 m/s): {dv_mag:.2f} m/s")

        # 2. Fuel Check
        from .core.navigation import Navigator
        nav = Navigator()
        fuel_cost = nav.compute_fuel_cost(sat.mass_kg, dv_mag)
        
        sufficient_fuel = sat.fuel_kg >= fuel_cost
        if not sufficient_fuel:
            errors.append(f"Insufficient propellant (need {fuel_cost:.2f}kg)")

        # 3. Cooldown Check
        last_burn = self.maneuver.cooldown_tracker.get(sat_id)
        cooldown_ok = True
        if last_burn and (burn_time - last_burn).total_seconds() < 600:
            cooldown_ok = False
            errors.append("Thruster cooldown violation (600s)")

        return {
            "valid": bool(len(errors) == 0),
            "ground_station_los": bool(has_los),
            "sufficient_fuel": bool(sufficient_fuel),
            "thruster_cooldown_ok": bool(cooldown_ok),
            "fuel_cost_kg": float(round(fuel_cost, 4)),
            "projected_mass_remaining_kg": float(round(sat.mass_kg - fuel_cost, 2)),
            "errors": errors
        }

    def get_stats(self) -> dict:
        """Get constellation statistics."""
        sats = list(self.fleet.satellites.values())
        active = [s for s in sats if s.status != "EOL"]
        critical_cdms = [c for c in self.conj.active_cdms if c.missDistance < 0.1]

        return {
            "satellites": {
                "total": len(sats),
                "active": len(active),
                "eol": len(sats) - len(active),
            },
            "fuel": {
                "total_kg": round(sum(s.fuel_kg for s in sats), 2),
                "avg_kg": round(sum(s.fuel_kg for s in sats) / len(sats) if sats else 0, 2),
            },
            "conjunctions": {
                "total_active": len(self.conj.active_cdms),
                "critical": len(critical_cdms),
            },
            "uptime": {
                "fleet_avg_score": round(sum(s.uptime_score for s in sats) / len(sats) if sats else 1.0, 4),
                "total_outages": sum(len(s.outage_events) for s in sats),
            },
            "sim_time": self.sim.sim_time.isoformat(),
        }

    def get_alerts_since(self, after_id: int) -> List[dict]:
        """Get alerts with id > after_id."""
        return [a for a in self.alerts if a["id"] > after_id]

    def _add_alert(self, type: str, level: str, msg: str, sat_id: Optional[str] = None):
        self._alert_counter += 1
        self.alerts.append({
            "id": self._alert_counter,
            "type": type,
            "level": level,
            "message": msg,
            "satellite_id": sat_id,
            "timestamp": self.sim.sim_time.isoformat()
        })
        # Keep buffer small
        if len(self.alerts) > 100:
            self.alerts.pop(0)

    def execute_maneuver(self, sat_id: str, delta_v: dict, burn_time_iso: Optional[str] = None):
        """Direct execution (manual override)."""
        sat = self.fleet.satellites.get(sat_id)
        if not sat: return {"status": "ERROR", "message": "Not found"}
        
        # In v2, we prefer scheduling. Manual override just schedules for T+10s.
        burn_dt = self.sim.sim_time + timedelta(seconds=11)
        from .models import Maneuver, Vector3
        m = Maneuver(
            burn_id=f"MANUAL_{self._alert_counter}",
            satelliteId=sat_id,
            burnTime=burn_dt,
            deltaV_vector=Vector3(**delta_v)
        )
        res = self.maneuver.schedule_burns(sat_id, [m], sat.fuel_kg, self.sim.sim_time, 
                                           comms_service=self.comms, sat_r_eci=sat.r.to_np())
        return res

    # ── Snapshot for Dashboard ────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Rulebook compliant snapshot (Section 6.3)."""
        return {
            "timestamp": self.sim.sim_time.isoformat(),
            "satellites": [s.model_dump() for s in self.fleet.satellites.values()],
            "debris_cloud": self.fleet.get_debris_snapshot(), # Flattened [ID, lat, lon, alt]
            "cdms": [c.model_dump() for c in self.conj.active_cdms],
            "maneuvers": self.maneuvers
        }

    def register_ws(self, ws): self._ws_clients.add(ws)
    def unregister_ws(self, ws): self._ws_clients.discard(ws)

state = StateManager()
