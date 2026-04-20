"""
backend/core/state_manager.py — ACM In-Memory State Store
==========================================================
Thread-safe multi-context state manager that supports multiple simulation
contexts for multi-tenancy while maintaining backward compatibility.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from contextlib import contextmanager


from .models import ObjectState, ScheduledBurn


# ── Simulation Context ────────────────────────────────────────────────────────

@dataclass
class SimulationContext:
    """Container for a single simulation's state."""
    objects: Dict[str, ObjectState] = field(default_factory=dict)
    simulation_time: float = time.time()
    scheduled_maneuvers: List[ScheduledBurn] = field(default_factory=list)
    active_cdms: List[dict] = field(default_factory=list)
    maneuver_history: List[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)


# ── State Manager (Multi-Context) ─────────────────────────────────────────────

class StateManager:
    """
    Thread-safe in-memory store for multiple simulation contexts.
    Supports multi-tenancy while maintaining backward compatibility.
    """

    def __init__(self):
        self._contexts: Dict[str, SimulationContext] = {}
        self._global_lock = threading.Lock()
        # Default context for backward compatibility
        self._default_context_id = "default"
        self._contexts[self._default_context_id] = SimulationContext()

    def _get_context(self, simulation_id: Optional[str] = None) -> SimulationContext:
        """Get or create a simulation context."""
        if simulation_id is None:
            simulation_id = self._default_context_id
        
        with self._global_lock:
            if simulation_id not in self._contexts:
                self._contexts[simulation_id] = SimulationContext()
            return self._contexts[simulation_id]

    def create_context(self, simulation_id: str) -> SimulationContext:
        """Create a new simulation context."""
        with self._global_lock:
            if simulation_id in self._contexts:
                raise ValueError(f"Simulation context {simulation_id} already exists")
            self._contexts[simulation_id] = SimulationContext()
            return self._contexts[simulation_id]

    def delete_context(self, simulation_id: str) -> None:
        """Delete a simulation context."""
        with self._global_lock:
            if simulation_id == self._default_context_id:
                raise ValueError("Cannot delete default context")
            if simulation_id in self._contexts:
                del self._contexts[simulation_id]

    # ── Object management ──────────────────────────────────────────────────────

    def upsert(self, obj: ObjectState, simulation_id: Optional[str] = None) -> None:
        """Insert or update an object by ID in the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            # Preserve fuel/status/nominal_slot if already tracked
            existing = ctx.objects.get(obj.id)
            if existing and obj.obj_type == "SATELLITE":
                if obj.m_fuel == 50.0:          # default value: don't overwrite
                    obj.m_fuel = existing.m_fuel
                if not obj.nominal_slot:
                    obj.nominal_slot = existing.nominal_slot
                obj.last_burn_time = existing.last_burn_time
                obj.status = existing.status
            ctx.objects[obj.id] = obj

    def get(self, obj_id: str, simulation_id: Optional[str] = None) -> Optional[ObjectState]:
        """Get an object by ID from the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            return ctx.objects.get(obj_id)

    def get_all_satellites(self, simulation_id: Optional[str] = None) -> List[ObjectState]:
        """Get all satellites from the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            return [o for o in ctx.objects.values() if o.obj_type == "SATELLITE"]

    def get_all_debris(self, simulation_id: Optional[str] = None) -> List[ObjectState]:
        """Get all debris from the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            return [o for o in ctx.objects.values() if o.obj_type == "DEBRIS"]

    def check_fuel_depletion(self, simulation_id: Optional[str] = None, threshold_pct: float = 5.0) -> List[dict]:
        """Check for satellites with critically low fuel.
        
        Args:
            threshold_pct: Fuel percentage threshold (default 5%)
        
        Returns:
            List of satellites with fuel below threshold
        """
        from backend.core.physics.constants import INITIAL_FUEL
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            depleted = []
            
            for obj in ctx.objects.values():
                if obj.obj_type == "SATELLITE":
                    fuel_pct = (obj.m_fuel / INITIAL_FUEL) * 100.0 if INITIAL_FUEL > 0 else 0.0
                    if fuel_pct < threshold_pct:
                        depleted.append({
                            "id": obj.id,
                            "fuel_kg": obj.m_fuel,
                            "fuel_percentage": fuel_pct,
                            "status": "CRITICAL" if fuel_pct < 1.0 else "WARNING"
                        })
            
            return depleted

    def object_count(self, simulation_id: Optional[str] = None) -> dict:
        """Get object counts from the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            sats  = sum(1 for o in ctx.objects.values() if o.obj_type == "SATELLITE")
            debs  = len(ctx.objects) - sats
            return {"satellites": sats, "debris": debs, "total": len(ctx.objects)}

    def get_summary(self, simulation_id: Optional[str] = None) -> dict:
        """Return a high-level summary of the specified context's state."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            sats = [o for o in ctx.objects.values() if o.obj_type == "SATELLITE"]
            return {
                "simulation_id": simulation_id or self._default_context_id,
                "simulation_time": ctx.simulation_time,
                "satellite_count": len(sats),
                "debris_count": len(ctx.objects) - len(sats),
                "active_cdms": len(ctx.active_cdms),
                "scheduled_maneuvers": len(ctx.scheduled_maneuvers),
                "executed_maneuvers": len(ctx.maneuver_history)
            }

    # ── Maneuver queue ──────────────────────────────────────────────────────────

    def queue_burn(self, burn: ScheduledBurn, simulation_id: Optional[str] = None) -> None:
        """Queue a burn in the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            ctx.scheduled_maneuvers.append(burn)

    def pop_due_burns(self, until_time: float, simulation_id: Optional[str] = None) -> List[ScheduledBurn]:
        """
        Remove and return all burns scheduled at or before `until_time`
        that have not yet been executed in the specified context.
        """
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            due, remaining = [], []
            for b in ctx.scheduled_maneuvers:
                if not b.executed and b.burn_time <= until_time:
                    due.append(b)
                else:
                    remaining.append(b)
            ctx.scheduled_maneuvers = remaining
            return due

    def log_executed_burn(self, burn: ScheduledBurn, fuel_used: float, simulation_id: Optional[str] = None) -> None:
        """Record an executed burn to the history log in the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            ctx.maneuver_history.append({
                "burn_id":      burn.burn_id,
                "satellite_id": burn.satellite_id,
                "burn_type":    burn.burn_type,
                "burn_time":    burn.burn_time,
                "delta_v":      burn.delta_v,
                "fuel_used_kg": round(fuel_used, 4),
            })

    # ── CDM store ──────────────────────────────────────────────────────────────

    def update_cdms(self, cdms: List[dict], simulation_id: Optional[str] = None) -> None:
        """Update CDMs in the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            ctx.active_cdms = sorted(
                cdms,
                key=lambda c: (c.get("severity") != "CRITICAL",
                                c.get("severity") != "WARNING",
                                c.get("distance_km", 9e9))
            )

    # ── Simulation clock ───────────────────────────────────────────────────────

    def advance_time(self, dt_seconds: float, simulation_id: Optional[str] = None) -> None:
        """Advance simulation time in the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
            ctx.simulation_time += dt_seconds

    def load_initial_state(self, satellites_data: list, debris_data: list, simulation_id: Optional[str] = None) -> None:
        """Bulk-load the initial constellation into the specified context."""
        ctx = self._get_context(simulation_id)
        with ctx._lock:
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
                ctx.objects[obj.id] = obj

            for d in debris_data:
                r = [d["r"]["x"], d["r"]["y"], d["r"]["z"]]
                v = [d["v"]["x"], d["v"]["y"], d["v"]["z"]]
                obj = ObjectState(
                    id=d["id"],
                    obj_type="DEBRIS",
                    r=r, v=v,
                )
                ctx.objects[obj.id] = obj

    # ── Context management ───────────────────────────────────────────────────────

    def list_contexts(self) -> List[str]:
        """List all simulation context IDs."""
        with self._global_lock:
            return list(self._contexts.keys())

    def context_exists(self, simulation_id: str) -> bool:
        """Check if a simulation context exists."""
        with self._global_lock:
            return simulation_id in self._contexts


# Module-level singleton (backward compatible)
state_mgr = StateManager()
