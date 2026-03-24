"""
backend/core/state_manager.py — ACM In-Memory State Store
==========================================================
Thread-safe singleton that owns all object states, simulation clock,
scheduled maneuvers, and active CDM warnings.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


from .models import ObjectState, ScheduledBurn


# ── State Manager (Singleton) ─────────────────────────────────────────────────

class StateManager:
    """
    Thread-safe in-memory store for all constellation state.
    Use the module-level `state_mgr` singleton.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.objects: Dict[str, ObjectState] = {}
        self.simulation_time: float = time.time()       # current sim Unix timestamp
        self.scheduled_maneuvers: List[ScheduledBurn] = []
        self.active_cdms: List[dict] = []               # conjunction data messages
        self.maneuver_history: List[dict] = []          # executed burn log

    # ── Object management ──────────────────────────────────────────────────────

    def upsert(self, obj: ObjectState) -> None:
        """Insert or update an object by ID."""
        with self._lock:
            # Preserve fuel/status/nominal_slot if already tracked
            existing = self.objects.get(obj.id)
            if existing and obj.obj_type == "SATELLITE":
                if obj.m_fuel == 50.0:          # default value: don't overwrite
                    obj.m_fuel = existing.m_fuel
                if not obj.nominal_slot:
                    obj.nominal_slot = existing.nominal_slot
                obj.last_burn_time = existing.last_burn_time
                obj.status = existing.status
            self.objects[obj.id] = obj

    def get(self, obj_id: str) -> Optional[ObjectState]:
        with self._lock:
            return self.objects.get(obj_id)

    def get_all_satellites(self) -> List[ObjectState]:
        with self._lock:
            return [o for o in self.objects.values() if o.obj_type == "SATELLITE"]

    def get_all_debris(self) -> List[ObjectState]:
        with self._lock:
            return [o for o in self.objects.values() if o.obj_type == "DEBRIS"]

    def object_count(self) -> dict:
        with self._lock:
            sats  = sum(1 for o in self.objects.values() if o.obj_type == "SATELLITE")
            debs  = len(self.objects) - sats
            return {"satellites": sats, "debris": debs, "total": len(self.objects)}

    # ── Maneuver queue ──────────────────────────────────────────────────────────

    def queue_burn(self, burn: ScheduledBurn) -> None:
        with self._lock:
            self.scheduled_maneuvers.append(burn)

    def pop_due_burns(self, until_time: float) -> List[ScheduledBurn]:
        """
        Remove and return all burns scheduled at or before `until_time`
        that have not yet been executed.
        """
        with self._lock:
            due, remaining = [], []
            for b in self.scheduled_maneuvers:
                if not b.executed and b.burn_time <= until_time:
                    due.append(b)
                else:
                    remaining.append(b)
            self.scheduled_maneuvers = remaining
            return due

    def log_executed_burn(self, burn: ScheduledBurn, fuel_used: float) -> None:
        """Record an executed burn to the history log."""
        with self._lock:
            self.maneuver_history.append({
                "burn_id":      burn.burn_id,
                "satellite_id": burn.satellite_id,
                "burn_type":    burn.burn_type,
                "burn_time":    burn.burn_time,
                "delta_v":      burn.delta_v,
                "fuel_used_kg": round(fuel_used, 4),
            })

    # ── CDM store ──────────────────────────────────────────────────────────────

    def update_cdms(self, cdms: List[dict]) -> None:
        with self._lock:
            self.active_cdms = sorted(
                cdms,
                key=lambda c: (c.get("severity") != "CRITICAL",
                                c.get("severity") != "WARNING",
                                c.get("distance_km", 9e9))
            )

    # ── Simulation clock ───────────────────────────────────────────────────────

    def advance_time(self, dt_seconds: float) -> None:
        with self._lock:
            self.simulation_time += dt_seconds

    def load_initial_state(self, satellites_data: list, debris_data: list) -> None:
        """Bulk-load the initial constellation from JSON data."""
        for s in satellites_data:
            r = [s["r"]["x"], s["r"]["y"], s["r"]["z"]]
            v = [s["v"]["x"], s["v"]["y"], s["v"]["z"]]
            obj = ObjectState(
                id=s["id"],
                obj_type="SATELLITE",
                r=r, v=v,
                m_fuel=s.get("m_fuel", 50.0),
                dry_mass=s.get("dry_mass", 500.0),
                nominal_slot=r.copy(),
                status="NOMINAL",
            )
            self.objects[obj.id] = obj

        for d in debris_data:
            r = [d["r"]["x"], d["r"]["y"], d["r"]["z"]]
            v = [d["v"]["x"], d["v"]["y"], d["v"]["z"]]
            obj = ObjectState(
                id=d["id"],
                obj_type="DEBRIS",
                r=r, v=v,
            )
            self.objects[obj.id] = obj


# Module-level singleton
state_mgr = StateManager()
