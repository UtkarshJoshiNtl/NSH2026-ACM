"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — simulation_service.py
 Main Orchestration and Physics Loop
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np

from ..core.physics import J2RK4Propagator
from .fleet_service import FleetService
from .conjunction_service import ConjunctionService
from .maneuver_service import ManeuverService
from .comms_service import CommsService

class SimulationService:
    """
    Heartbeat of the ACM. Orchestrates physics, logic, and maneuvers.
    """

    def __init__(self, fleet: FleetService, conj: ConjunctionService, 
                 maneuver: ManeuverService, comms: CommsService, decision: Any):
        self.fleet = fleet
        self.conj = conj
        self.maneuver = maneuver
        self.comms = comms
        self.decision = decision
        self.propagator = J2RK4Propagator()
        
        self.sim_time = datetime(2026, 3, 12, 8, 0, 0)
        self.running = False
        self.step_seconds = 10.0   # 10s steps: screener catches short TCA windows

    def step(self, dt: float) -> Dict[str, Any]:
        """
        Advances the entire constellation state by dt seconds.
        Sub-steps large windows to maintain RK4 stability (max 60s per step).
        """
        MAX_STEP = 60.0
        remaining_dt = dt
        collisions_detected = 0
        maneuvers_executed = 0
        
        while remaining_dt > 0:
            step_dt = min(remaining_dt, MAX_STEP)
            res = self._internal_step(step_dt)
            collisions_detected += res["collisions_detected"]
            maneuvers_executed += res["maneuvers_executed"]
            remaining_dt -= step_dt
            
        return {
            "status": "STEP_COMPLETE",
            "new_timestamp": self.sim_time.isoformat(),
            "collisions_detected": collisions_detected,
            "maneuvers_executed": maneuvers_executed
        }

    def _internal_step(self, dt: float) -> Dict[str, Any]:
        """Single physics iteration for dt seconds."""
        initial_time = self.sim_time
        target_time = initial_time + timedelta(seconds=dt)
        
        print(f"[SIM] Step: {dt}s from {initial_time} to {target_time}")
        
        maneuvers_executed = 0
        collisions_detected = 0

        # ── 1. Propagate Satellites ──────────────────────────────────────────
        for sat_id, sat in self.fleet.satellites.items():
            if sat.status == "EOL": continue
            print(f"[SIM] Propagating {sat_id} from lat={sat.lat:.2f}")
            
            # Check for scheduled burns in this window
            pending = self.maneuver.get_pending_burns(sat_id, initial_time, target_time)
            
            # For simplicity in this 'step', we propagate to the burn time, 
            # apply burn, then propagate the rest of the window.
            # (In a real high-fidelity sim, we'd handle multiple burns per step).
            
            curr_r = sat.r.to_np()
            curr_v = sat.v.to_np()
            
            if pending:
                for burn in pending:
                    # Time from step start to burn
                    dt_to_burn = (burn.burnTime - initial_time).total_seconds()
                    
                    # Propagate to burn point
                    if dt_to_burn > 0:
                        curr_r, curr_v = self.propagator.propagate(curr_r, curr_v, dt_to_burn)
                    
                    # Apply IMPULSIVE burn (Section 5.1)
                    # Convert m/s (API unit) to km/s (Physics unit)
                    dv_m_s = burn.deltaV_vector.to_np()
                    dv_km_s = dv_m_s / 1000.0
                    curr_v += dv_km_s
                    
                    # Deduct fuel
                    self.fleet.deduct_fuel(sat_id, burn.fuel_cost_kg)
                    self.maneuver.mark_executed(sat_id, burn.burn_id)
                    maneuvers_executed += 1
                    
                    # Reset 'initial' for the remaining part of the window
                    window_rem = dt - dt_to_burn
                    if window_rem > 0:
                        curr_r, curr_v = self.propagator.propagate(curr_r, curr_v, window_rem)
            else:
                # Standard propagation for full window
                curr_r, curr_v = self.propagator.propagate(curr_r, curr_v, dt)

            # Update Registry with dt for nominal slot propagation
            self.fleet.update_satellite_state(sat_id, curr_r, curr_v, dt=dt, sim_time=target_time)

        # ── 2. Propagate Debris ──────────────────────────────────────────────
        for deb_id, deb in self.fleet.debris.items():
            curr_r = deb.r.to_np()
            curr_v = deb.v.to_np()
            
            # Use same J2 propagator for consistency (v2 Goal)
            new_r, new_v = self.propagator.propagate(curr_r, curr_v, dt)
            
            # Update debris registry (flat update) - only position/velocity
            # lat/lon/alt calculated on-demand for snapshot to save CPU
            deb.r.x, deb.r.y, deb.r.z = new_r
            deb.v.x, deb.v.y, deb.v.z = new_v

        # ── 3. Screen for Conjunctions ───────────────────────────────────────
        # Run at current propagated positions
        sats = list(self.fleet.satellites.values())
        debs = list(self.fleet.debris.values())
        self.conj.screen_fleet(sats, debs, target_time)

        # Check for immediate collisions (Section 3.3)
        for cdm in self.conj.active_cdms:
            if cdm.missDistance < 0.1: # 100m
                collisions_detected += 1
        
        self.sim_time = target_time

        # ── 3.5. Station-Keeping Check ───────────────────────────────────────
        # IMPORTANT: run AFTER sim_time is updated so burn times land in next tick
        if self.decision:
            sk_actions = self.decision.check_station_keeping(sats, self.sim_time)
            for action in sk_actions:
                print(f"[STATION_KEEPING] {action['type']} for {action['satellite_id']} | Drift: {action.get('drift_km', 0):.2f}km")
        
        # ── 4. Autonomous Intelligence ───────────────────────────────────────
        if self.decision:
            actions = self.decision.process_cdms(self.conj.active_cdms, self.sim_time)
            # Log any significant actions as alerts
            for action in actions:
                msg = f"Autonomous Action: {action['type']} for {action['satellite_id']}"
                if 'tca' in action:
                    msg += f" | TCA: {action['tca']}"
                # We need a way to add alerts to the state manager. 
                # Since DecisionService was injected with Fleet/Maneuver, 
                # maybe we can add a callback or just log to stdout for now, 
                # or better, modify DecisionService to take an alert_callback.
                print(f"[DECISION] {msg}")
        
        # ── 5. Process Blackout Upload Queue ────────────────────────────────────
        # Check queued burns for each satellite and upload if LOS is available
        for sat_id, sat in self.fleet.satellites.items():
            if sat.status == "EOL": continue
            queue_results = self.maneuver.process_upload_queue(
                sat_id, self.sim_time, self.comms, sat.r.to_np(), sat.fuel_kg
            )
            if queue_results["uploaded"]:
                print(f"[QUEUE] Uploaded {len(queue_results['uploaded'])} burns for {sat_id}")
            if queue_results["expired"]:
                print(f"[QUEUE] Expired {len(queue_results['expired'])} burns for {sat_id}")
        
        return {
            "status": "STEP_COMPLETE",
            "new_timestamp": self.sim_time.isoformat(),
            "collisions_detected": collisions_detected,
            "maneuvers_executed": maneuvers_executed
        }
