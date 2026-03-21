"""
backend/core/station_keeping.py — ACM Station Keeping Monitor
==============================================================
Monitors satellite slot drift and flags satellites outside their
10 km nominal station-keeping box.
"""

import math
import logging
from typing import List, Tuple

from backend.core.state_manager import ObjectState

logger = logging.getLogger(__name__)

SLOT_BOX_KM = 10.0   # km — max allowed drift from nominal slot


def slot_drift(sat: ObjectState) -> float:
    """
    Returns the Euclidean distance (km) between the satellite's current
    position and its nominal slot. Returns 0 if no nominal slot is set.
    """
    if not sat.nominal_slot or len(sat.nominal_slot) < 3:
        return 0.0
    return math.sqrt(
        sum((sat.r[i] - sat.nominal_slot[i])**2 for i in range(3))
    )


def check_all_slots(satellites: List[ObjectState]) -> List[Tuple[ObjectState, float]]:
    """
    Returns list of (satellite, drift_km) for all satellites outside
    the SLOT_BOX_KM threshold.
    """
    violations = []
    for sat in satellites:
        if sat.obj_type != "SATELLITE":
            continue
        drift = slot_drift(sat)
        if drift > SLOT_BOX_KM:
            if sat.status == "NOMINAL":
                sat.status = "WARNING"
                logger.warning("Satellite %s drifted %.2f km outside slot box", sat.id, drift)
            violations.append((sat, drift))
        else:
            # Reset to NOMINAL if it drifted back and fuel is OK
            if sat.status == "WARNING" and drift <= SLOT_BOX_KM:
                sat.status = "NOMINAL"
    return violations


def nominal_slot_summary(satellites: List[ObjectState]) -> dict:
    """Summary statistics for telemetry / visualization."""
    drifts = [slot_drift(s) for s in satellites if s.obj_type == "SATELLITE"]
    if not drifts:
        return {"count": 0, "max_drift_km": 0.0, "violations": 0}
    return {
        "count":         len(drifts),
        "max_drift_km":  round(max(drifts), 3),
        "mean_drift_km": round(sum(drifts) / len(drifts), 3),
        "violations":    sum(1 for d in drifts if d > SLOT_BOX_KM),
    }
