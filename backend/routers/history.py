"""
backend/routers/history.py — ACM Maneuver History & Queue API
=============================================================
Provides endpoints to inspect the executed burn log and the
currently scheduled maneuver queue.
"""

from fastapi import APIRouter, Query
from backend.core.state_manager import state_mgr

router = APIRouter()


@router.get("/history/maneuvers")
async def get_maneuver_history(
    satellite_id: str | None = Query(None, description="Filter by satellite ID"),
    limit: int = Query(100, description="Max records to return (newest first)")
):
    """Return executed burn history, newest first."""
    history = list(reversed(state_mgr.maneuver_history))
    if satellite_id:
        history = [h for h in history if h["satellite_id"] == satellite_id]
    return {
        "total": len(state_mgr.maneuver_history),
        "records": history[:limit]
    }


@router.get("/history/queue")
async def get_maneuver_queue(
    satellite_id: str | None = Query(None, description="Filter by satellite ID")
):
    """Return pending scheduled burns (not yet executed)."""
    queue = [
        {
            "burn_id":      b.burn_id,
            "satellite_id": b.satellite_id,
            "burn_type":    b.burn_type,
            "burn_time":    b.burn_time,
            "delta_v":      b.delta_v,
        }
        for b in state_mgr.scheduled_maneuvers
        if not b.executed
    ]
    if satellite_id:
        queue = [q for q in queue if q["satellite_id"] == satellite_id]
    return {"pending": len(queue), "burns": queue}
