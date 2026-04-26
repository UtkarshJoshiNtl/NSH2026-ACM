"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — decision_service.py
 Autonomous Decision Engine (Intelligence Layer)
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

from ..models import Satellite, CDM, Maneuver, Vector3
from .maneuver_service import ManeuverService
from .fleet_service import FleetService

class DecisionService:
    """
    Analyzes CDMs and initiates autonomous evasion maneuvers.
    Implementation of Sections 5.1, 5.2, and 6 rulebook requirements.
    """

    def __init__(self, fleet: FleetService, maneuver: ManeuverService, alert_callback: Optional[callable] = None,
                 comms_service=None):
        self.fleet = fleet
        self.maneuver = maneuver
        self.alert_callback = alert_callback
        self.comms_service = comms_service
        
        # Risk Thresholds (Section 3.3 / 5.2)
        self.CRITICAL_DISTANCE_KM = 0.1 # 100m
        self.WARNING_DISTANCE_KM = 1.0  # 1km

    def process_cdms(self, cdms: List[CDM], sim_time: datetime) -> List[Dict]:
        """
        Processes a batch of CDMs and triggers evasions if thresholds are breached.
        """
        actions_taken = []
        
        # 1. End-of-Life (EOL) Management (Section 5.1/2)
        # "If fuel drops to 5%, schedule a final maneuver to move to a graveyard orbit"
        for sat_id, sat in self.fleet.satellites.items():
            if sat.status != "EOL" and sat.fuel_kg < 2.5: # 5% of 50kg
                # Graveyard: Simple 15 m/s radial-out burn to raise orbit
                burn_time = sim_time + timedelta(seconds=11)
                from ..core.navigation import Navigator
                nav = Navigator()
                # 15 m/s Radial-Out
                dv_eci = nav.plan_evasion(sat.r.to_np(), sat.v.to_np(), strategy="R+")
                
                burn = Maneuver(
                    burn_id=f"EOL-GRAVEYARD-{sat_id}",
                    satelliteId=sat_id,
                    burnTime=burn_time,
                    deltaV_vector=Vector3.from_np(dv_eci)
                )
                self.maneuver.schedule_burns(sat_id, [burn], sat.fuel_kg, sim_time,
                                               comms_service=self.comms_service, sat_r_eci=sat.r.to_np())
                sat.status = "EOL"
                actions_taken.append({
                    "satellite_id": sat_id, 
                    "type": "EOL_GRAVEYARD_TRIGGERED",
                    "fuel_kg": round(sat.fuel_kg, 3)
                })
                
                if self.alert_callback:
                    self.alert_callback(
                        type="EOL_ALERT",
                        level="WARNING",
                        msg=f"Satellite {sat_id} fuel critical ({sat.fuel_kg:.2f}kg). Graveyard burn initiated.",
                        sat_id=sat_id
                    )

        # 2. Conjunction Audit
        critical_cdms = [c for c in cdms if c.missDistance < self.CRITICAL_DISTANCE_KM]
        
        sats_to_evade = {}
        for cdm in critical_cdms:
            if cdm.satelliteId not in sats_to_evade:
                sats_to_evade[cdm.satelliteId] = cdm
            elif cdm.missDistance < sats_to_evade[cdm.satelliteId].missDistance:
                sats_to_evade[cdm.satelliteId] = cdm

        # 3. Autonomous Evasion & Recovery (Section 5.2/5.3)
        for sat_id, cdm in sats_to_evade.items():
            sat = self.fleet.satellites.get(sat_id)
            if not sat or sat.status in ["EOL", "EVADING"]:
                continue
                
            # Evasion Strategy: 10 m/s Prograde (Section 5.1/5.3)
            # Recovery Strategy: 10 m/s Retrograde after 45 mins (half orbit avg)
            tca = cdm.tca
            # Schedule evasion burn ASAP (min 15s from now to satisfy latency rule)
            # If TCA is more than 75s away, burn 60s before TCA; otherwise burn immediately
            min_burn_time = sim_time + timedelta(seconds=15)
            preferred_eva  = tca - timedelta(seconds=60)
            burn_time_eva  = max(preferred_eva, min_burn_time)

            # Recovery burn: 30 minutes after evasion (safely past cooldown)
            burn_time_rec = burn_time_eva + timedelta(minutes=30)

            # Skip if even the minimum burn is past TCA (satellite already past the debris)
            if burn_time_eva >= tca and (tca - sim_time).total_seconds() < 0:
                continue

            from ..core.navigation import Navigator
            nav = Navigator()
            
            # Evasion Burn (m/s)
            dv_eva_eci = nav.plan_evasion(sat.r.to_np(), sat.v.to_np(), strategy="T+")
            
            # Recovery Burn (Reverse)
            dv_rec_eci = -dv_eva_eci
            
            m_eva = Maneuver(
                burn_id=f"AUTO-EVA-{cdm.debrisId}",
                satelliteId=sat_id,
                burnTime=burn_time_eva,
                deltaV_vector=Vector3.from_np(dv_eva_eci)
            )
            m_rec = Maneuver(
                burn_id=f"AUTO-REC-{cdm.debrisId}",
                satelliteId=sat_id,
                burnTime=burn_time_rec,
                deltaV_vector=Vector3.from_np(dv_rec_eci)
            )
            
            # Schedule sequence immediately (Section 5.2 comment: "yes. immediate.")
            res = self.maneuver.schedule_burns(sat_id, [m_eva, m_rec], sat.fuel_kg, sim_time,
                                               comms_service=self.comms_service, sat_r_eci=sat.r.to_np())
            if res["scheduled"] and m_eva.burn_id in res["scheduled"]:
                sat.status = "EVADING"
                actions_taken.append({
                    "satellite_id": sat_id,
                    "type": "EVASION_RECOVERY_SCHEDULED",
                    "tca": tca.isoformat()
                })
                
                if self.alert_callback:
                    self.alert_callback(
                        type="CONJUNCTION_EVASION",
                        level="CRITICAL",
                        msg=f"Autonomous evasion scheduled for {sat_id} vs {cdm.debrisId}. TCA: {tca.strftime('%H:%M:%S')}",
                        sat_id=sat_id
                    )
        
        return actions_taken

    def check_station_keeping(self, satellites: List[Satellite], sim_time: datetime) -> List[Dict]:
        """
        Checks satellites for drift from nominal slot and schedules RTN-based proportional corrections.
        Triggers correction when drift exceeds 5km (half of 10km tolerance).
        """
        actions_taken = []
        
        for sat in satellites:
            if sat.status in ["EOL", "EVADING"]:
                continue
            
            # Calculate drift distance from nominal slot
            drift_km = np.linalg.norm(sat.r.to_np() - sat.nominal_r.to_np())
            
            # Trigger correction if drift exceeds 8km (more reasonable than 5km)
            if drift_km > 8.0:
                from ..core.navigation import Navigator
                nav = Navigator()
                
                # Calculate RTN-based proportional correction
                dv_eci = nav.plan_station_keeping(
                    sat.r.to_np(), 
                    sat.v.to_np(), 
                    sat.nominal_r.to_np(), 
                    sat.nominal_v.to_np()
                )
                
                # Check if correction is non-zero
                dv_mag = np.linalg.norm(dv_eci) * 1000.0  # Convert km/s to m/s
                if dv_mag < 0.1:  # Negligible correction
                    continue
                
                # Schedule station-keeping burn for T+20s
                burn_time = sim_time + timedelta(seconds=20)
                
                burn = Maneuver(
                    burn_id=f"SK-CORRECT-{sat.id}",
                    satelliteId=sat.id,
                    burnTime=burn_time,
                    deltaV_vector=Vector3.from_np(dv_eci)
                )
                
                res = self.maneuver.schedule_burns(sat.id, [burn], sat.fuel_kg, sim_time,
                                                   comms_service=self.comms_service, sat_r_eci=sat.r.to_np())
                
                if res["scheduled"] and burn.burn_id in res["scheduled"]:
                    actions_taken.append({
                        "satellite_id": sat.id,
                        "type": "STATION_KEEPING_CORRECTION",
                        "drift_km": round(drift_km, 3),
                        "correction_m_s": round(dv_mag, 3)
                    })
                    
                    if self.alert_callback:
                        self.alert_callback(
                            type="STATION_KEEPING",
                            level="INFO",
                            msg=f"Station-keeping correction scheduled for {sat.id}. Drift: {drift_km:.2f}km",
                            sat_id=sat.id
                        )
        
        return actions_taken
