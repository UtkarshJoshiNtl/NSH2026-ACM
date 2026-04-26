"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — maneuver_service.py
 Burn Scheduling and Validation
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from ..models import Maneuver, Satellite, Vector3
from ..core.navigation import Navigator
import numpy as np

class ManeuverService:
    """
    Manages the lifecycle of satellite maneuvers (Evasion and Recovery).
    """

    def __init__(self):
        self.navigator = Navigator()
        self.scheduled_burns: Dict[str, List[Maneuver]] = {} # sat_id -> sorted list of burns
        self.executed_burns: List[Maneuver] = []
        self.cooldown_tracker: Dict[str, datetime] = {} # sat_id -> last burn time
        self.pending_upload_queue: Dict[str, List[Maneuver]] = {} # sat_id -> burns waiting for LOS

    def schedule_burns(self, sat_id: str, burns: List[Maneuver], current_fuel_kg: float, sim_time: datetime, 
                       comms_service=None, sat_r_eci=None) -> Dict:
        """
        Validates and schedules a sequence of burns.
        Checks: Signal latency (10s), Fuel budget, Thruster cooldown (600s), LOS (if comms_service provided).
        If no LOS, burns are queued for upload when satellite enters coverage.
        """
        if sat_id not in self.scheduled_burns:
            self.scheduled_burns[sat_id] = []
        if sat_id not in self.pending_upload_queue:
            self.pending_upload_queue[sat_id] = []
        
        results = {"scheduled": [], "failed": []}
        temp_fuel = current_fuel_kg
        
        # Sort incoming burns by time
        sorted_burns = sorted(burns, key=lambda b: b.burnTime)
        
        for burn in sorted_burns:
            # 0a. Dedup: skip if this exact burn_id is already scheduled
            if any(b.burn_id == burn.burn_id for b in self.scheduled_burns[sat_id]):
                continue

            # 0b. LOS Check (Section 5.4)
            has_los = True
            if comms_service is not None and sat_r_eci is not None:
                has_los = comms_service.has_los(sat_r_eci, sim_time)
            
            # 1. 10s Signal Latency Check (Section 5.4)
            time_to_burn = (burn.burnTime - sim_time).total_seconds()
            if time_to_burn < 10.0:
                results["failed"].append({
                    "id": burn.burn_id, 
                    "reason": f"Signal latency violation: T+{time_to_burn:.2f}s, need 10s minimum"
                })
                continue
            
            # If no LOS, queue the burn instead of failing
            if not has_los:
                self.pending_upload_queue[sat_id].append(burn)
                results["scheduled"].append(burn.burn_id)  # Mark as scheduled (queued)
                continue

            # 2. Cooldown Check (600s = 10 mins)
            # Must check against the last executed burn AND other scheduled burns
            all_relevant_times = [self.cooldown_tracker.get(sat_id)] + [b.burnTime for b in self.scheduled_burns[sat_id]]
            all_relevant_times = [t for t in all_relevant_times if t is not None]
            
            # Check if this burn is too close to any existing burn (+/- 600s)
            cooldown_violation = False
            for t in all_relevant_times:
                if abs((burn.burnTime - t).total_seconds()) < 600:
                    cooldown_violation = True
                    break
            
            if cooldown_violation:
                results["failed"].append({"id": burn.burn_id, "reason": "Thruster cooldown violation (600s)"})
                continue
            
            # 3. Thrust Limit Check (Section 5.1)
            # deltaV_vector is stored in km/s (physics units) — convert to m/s for checks
            dv_mag_kms = np.linalg.norm(burn.deltaV_vector.to_np())
            dv_mag_ms  = dv_mag_kms * 1000.0  # km/s → m/s
            if dv_mag_ms > 15.0:
                results["failed"].append({"id": burn.burn_id, "reason": f"Thrust limit violation (15.0 m/s): {dv_mag_ms:.2f} m/s"})
                continue

            # 4. Fuel Check (Tsiolkovsky expects m/s)
            fuel_cost = self.navigator.compute_fuel_cost(500.0 + temp_fuel, dv_mag_ms)
            
            if fuel_cost > temp_fuel:
                results["failed"].append({"id": burn.burn_id, "reason": "Insufficient propellant"})
                continue
            
            # 4. ACK
            burn.fuel_cost_kg = fuel_cost
            self.scheduled_burns[sat_id].append(burn)
            # Update cooldown tracker with most recent burn time (if it's later)
            if sat_id not in self.cooldown_tracker or burn.burnTime > self.cooldown_tracker[sat_id]:
                self.cooldown_tracker[sat_id] = burn.burnTime
            
            temp_fuel -= fuel_cost
            results["scheduled"].append(burn.burn_id)

        # Re-sort schedule
        self.scheduled_burns[sat_id].sort(key=lambda b: b.burnTime)
        
        return results

    def get_pending_burns(self, sat_id: str, start_time: datetime, end_time: datetime) -> List[Maneuver]:
        """Returns burns occurring within a specific window."""
        if sat_id not in self.scheduled_burns:
            return []
            
        pending = [b for b in self.scheduled_burns[sat_id] if start_time <= b.burnTime < end_time]
        return pending

    def mark_executed(self, sat_id: str, burn_id: str):
        """Clean up schedule after execution and track in executed list."""
        if sat_id in self.scheduled_burns:
            for burn in self.scheduled_burns[sat_id]:
                if burn.burn_id == burn_id:
                    burn.status = "EXECUTED"
                    self.executed_burns.append(burn)
                    break
            self.scheduled_burns[sat_id] = [b for b in self.scheduled_burns[sat_id] if b.burn_id != burn_id]

    def process_upload_queue(self, sat_id: str, sim_time: datetime, comms_service, sat_r_eci, current_fuel_kg: float) -> Dict:
        """
        Process queued burns for a satellite, attempting to upload them when LOS is available.
        Returns dict with uploaded and failed burn IDs.
        """
        if sat_id not in self.pending_upload_queue or not self.pending_upload_queue[sat_id]:
            return {"uploaded": [], "failed": [], "expired": []}
        
        results = {"uploaded": [], "failed": [], "expired": []}
        remaining_queue = []
        
        for burn in self.pending_upload_queue[sat_id]:
            # Check if burn has expired (burn time < sim_time + 10s latency)
            time_to_burn = (burn.burnTime - sim_time).total_seconds()
            if time_to_burn < 10.0:
                results["expired"].append(burn.burn_id)
                continue
            
            # Check if LOS is now available
            has_los = comms_service.has_los(sat_r_eci, sim_time)
            if not has_los:
                remaining_queue.append(burn)
                continue
            
            # LOS available - attempt to schedule the burn
            # Call schedule_burns with LOS=True to bypass queueing
            temp_results = self.schedule_burns(sat_id, [burn], current_fuel_kg, sim_time, 
                                              comms_service=comms_service, sat_r_eci=sat_r_eci)
            
            if burn.burn_id in temp_results["scheduled"]:
                results["uploaded"].append(burn.burn_id)
            else:
                # Failed validation (fuel, cooldown, etc.) - keep in queue for retry
                remaining_queue.append(burn)
        
        # Update queue with remaining burns
        self.pending_upload_queue[sat_id] = remaining_queue
        
        return results
