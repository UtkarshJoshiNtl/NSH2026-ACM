"""
backend/core/conjunction.py — ACM Conjunction Assessment
==========================================================
Wraps the C++ ConjunctionDetector via physics_bridge.
Runs the check as an async-compatible function and updates the state_mgr.
"""

import asyncio
import logging
from typing import List

from backend.core.physics_bridge import detect_conjunctions
from backend.core.state_manager import state_mgr

logger = logging.getLogger(__name__)

# How many steps to use for the conjunction scan (trades speed vs. accuracy)
CDM_LOOKAHEAD_S   = 86400.0   # 24 hours
CDM_STEP_S        = 60.0      # 60-second propagation step


def _state_to_vec(obj) -> list:
    """Convert an ObjectState r+v into a flat [x,y,z,vx,vy,vz] list."""
    return obj.r + obj.v


def run_conjunction_check(
    lookahead_s: float = CDM_LOOKAHEAD_S,
    step_s: float = CDM_STEP_S,
) -> List[dict]:
    """
    Synchronous conjunction detection.
    Builds state vectors from the state manager, calls C++ detector,
    updates state_mgr.active_cdms, and returns the CDM list.
    """
    satellites = state_mgr.get_all_satellites()
    debris     = state_mgr.get_all_debris()

    if not satellites or not debris:
        return []

    sat_vecs = [_state_to_vec(s) for s in satellites]
    deb_vecs = [_state_to_vec(d) for d in debris]

    # Map integer indices back to string IDs
    sat_ids = [s.id for s in satellites]
    deb_ids = [d.id for d in debris]

    raw = detect_conjunctions(sat_vecs, deb_vecs, lookahead_s, step_s)

    # Replace integer indices with string IDs
    cdms = []
    for c in raw:
        try:
            sid = sat_ids[c["sat_id"]]
            did = deb_ids[c["debris_id"]]
        except IndexError:
            continue
        cdms.append({
            "sat_id":      sid,
            "debris_id":   did,
            "distance_km": c["distance_km"],
            "tca_s":       c["tca_s"],
            "severity":    c["severity"],
            "rel_vel_kms": c["rel_vel_kms"],
        })

    state_mgr.update_cdms(cdms)
    logger.info("Conjunction check complete: %d warnings (%d CRITICAL)",
                len(cdms),
                sum(1 for c in cdms if c["severity"] == "CRITICAL"))
    return cdms


async def check_conjunctions_async(
    lookahead_s: float = CDM_LOOKAHEAD_S,
    step_s: float = CDM_STEP_S,
) -> List[dict]:
    """
    Async version — runs the blocking detection in a thread pool so the
    FastAPI event loop is not blocked by the C++ computation.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: run_conjunction_check(lookahead_s, step_s)
    )
