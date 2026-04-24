"""
backend/core/decision_service.py — Autonomous Decision Engine
==============================================================
Autonomous collision avoidance and fleet management logic.
Migrated from AutoCM for hackathon-compliant autonomous operations.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import numpy as np

from .navigation import Navigator
from .models import Satellite, CDM, Maneuver


class DecisionService:
    """
    Analyzes CDMs and initiates autonomous evasion maneuvers.
    Implements autonomous decision logic for collision avoidance and station-keeping.
    """

    def __init__(
        self,
        fleet: Dict[str, Satellite],
        maneuver_callback: Optional[Callable] = None,
        alert_callback: Optional[Callable] = None,
        comms_service=None
    ):
        """
        Initialize decision service.

        Args:
            fleet: Dictionary of satellites
            maneuver_callback: Function to schedule maneuvers
            alert_callback: Function to generate alerts
            comms_service: Communication service for LOS checks
        """
        self.fleet = fleet
        self.maneuver_callback = maneuver_callback
        self.alert_callback = alert_callback
        self.comms_service = comms_service
        self.navigator = Navigator()

        # Risk Thresholds
        self.CRITICAL_DISTANCE_KM = 0.1  # 100m
        self.WARNING_DISTANCE_KM = 1.0   # 1km
        self.FUEL_CRITICAL_KG = 2.5       # 5% of 50kg initial fuel

    def process_cdms(self, cdms: List[CDM], sim_time: datetime) -> List[Dict]:
        """
        Processes a batch of CDMs and triggers evasions if thresholds are breached.

        Args:
            cdms: List of Conjunction Data Messages
            sim_time: Current simulation time

        Returns:
            List of actions taken
        """
        actions_taken = []

        # 1. End-of-Life (EOL) Management
        # If fuel drops to 5%, schedule a final maneuver to move to a graveyard orbit
        for sat_id, sat in self.fleet.items():
            if sat.status != "EOL" and sat.fuel_kg < self.FUEL_CRITICAL_KG:
                # Graveyard: Simple 15 m/s radial-out burn to raise orbit
                burn_time = sim_time + timedelta(seconds=11)
                dv_eci = self.navigator.plan_evasion(
                    sat.r.to_np(), sat.v.to_np(), strategy="R+"
                )

                burn = Maneuver(
                    burn_id=f"EOL-GRAVEYARD-{sat_id}",
                    satellite_id=sat_id,
                    burn_time=burn_time,
                    delta_v=dv_eci
                )

                if self.maneuver_callback:
                    self.maneuver_callback([burn], sat_id, sim_time)

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
        critical_cdms = [c for c in cdms if c.miss_distance < self.CRITICAL_DISTANCE_KM]

        sats_to_evade = {}
        for cdm in critical_cdms:
            if cdm.satellite_id not in sats_to_evade:
                sats_to_evade[cdm.satellite_id] = cdm
            elif cdm.miss_distance < sats_to_evade[cdm.satellite_id].miss_distance:
                sats_to_evade[cdm.satellite_id] = cdm

        # 3. Autonomous Evasion & Recovery
        for sat_id, cdm in sats_to_evade.items():
            sat = self.fleet.get(sat_id)
            if not sat or sat.status in ["EOL", "EVADING"]:
                continue

            # Evasion Strategy: 10 m/s Prograde
            # Recovery Strategy: 10 m/s Retrograde after 45 mins
            tca = cdm.tca

            # Schedule evasion burn ASAP (min 15s from now to satisfy latency rule)
            min_burn_time = sim_time + timedelta(seconds=15)
            preferred_eva = tca - timedelta(seconds=60)
            burn_time_eva = max(preferred_eva, min_burn_time)

            # Recovery burn: 30 minutes after evasion (safely past cooldown)
            burn_time_rec = burn_time_eva + timedelta(minutes=30)

            # Skip if even the minimum burn is past TCA
            if burn_time_eva >= tca and (tca - sim_time).total_seconds() < 0:
                continue

            # Evasion Burn (m/s)
            dv_eva_eci = self.navigator.plan_evasion(
                sat.r.to_np(), sat.v.to_np(), strategy="T+"
            )

            # Recovery Burn (Reverse)
            dv_rec_eci = -dv_eva_eci

            m_eva = Maneuver(
                burn_id=f"AUTO-EVA-{cdm.debris_id}",
                satellite_id=sat_id,
                burn_time=burn_time_eva,
                delta_v=dv_eva_eci
            )
            m_rec = Maneuver(
                burn_id=f"AUTO-REC-{cdm.debris_id}",
                satellite_id=sat_id,
                burn_time=burn_time_rec,
                delta_v=dv_rec_eci
            )

            # Schedule sequence immediately
            if self.maneuver_callback:
                self.maneuver_callback([m_eva, m_rec], sat_id, sim_time)

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
                    msg=f"Autonomous evasion scheduled for {sat_id} vs {cdm.debris_id}. TCA: {tca.strftime('%H:%M:%S')}",
                    sat_id=sat_id
                )

        return actions_taken

    def check_station_keeping(self, sim_time: datetime) -> List[Dict]:
        """
        Checks satellites for drift from nominal slot and schedules RTN-based proportional corrections.
        Triggers correction when drift exceeds 8km.

        Args:
            sim_time: Current simulation time

        Returns:
            List of actions taken
        """
        actions_taken = []

        for sat in self.fleet.values():
            if sat.status in ["EOL", "EVADING"]:
                continue

            # Calculate drift distance from nominal slot
            if not hasattr(sat, 'nominal_r') or sat.nominal_r is None:
                continue

            drift_km = np.linalg.norm(sat.r.to_np() - sat.nominal_r.to_np())

            # Trigger correction if drift exceeds 8km
            if drift_km > 8.0:
                # Calculate RTN-based proportional correction
                dv_eci = self.navigator.plan_station_keeping(
                    sat.r.to_np(),
                    sat.v.to_np(),
                    sat.nominal_r.to_np(),
                    sat.nominal_v.to_np() if hasattr(sat, 'nominal_v') else sat.v.to_np()
                )

                # Check if correction is non-zero
                dv_mag = np.linalg.norm(dv_eci) * 1000.0  # Convert km/s to m/s
                if dv_mag < 0.1:  # Negligible correction
                    continue

                # Schedule station-keeping burn for T+20s
                burn_time = sim_time + timedelta(seconds=20)

                burn = Maneuver(
                    burn_id=f"SK-CORRECT-{sat.id}",
                    satellite_id=sat.id,
                    burn_time=burn_time,
                    delta_v=dv_eci
                )

                if self.maneuver_callback:
                    self.maneuver_callback([burn], sat.id, sim_time)

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
                    })

        return actions_taken
