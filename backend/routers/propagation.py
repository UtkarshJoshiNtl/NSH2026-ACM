"""
backend/routers/propagation.py — Orbital Propagation API
======================================================
API endpoints for satellite orbital propagation using the C++ physics engine.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from backend.core.physics import propagate, propagate_steps
from backend.core.physics_bridge import detect_conjunctions
from backend.middleware import get_current_user

router = APIRouter()


# Request/Response Models
class StateVector(BaseModel):
    r: List[float]  # Position vector [x, y, z] in km
    v: List[float]  # Velocity vector [vx, vy, vz] in km/s


class PropagateRequest(BaseModel):
    state: StateVector
    dt: float  # Time step in seconds


class PropagateResponse(BaseModel):
    r: List[float]
    v: List[float]
    propagated_time: float


class BatchPropagateRequest(BaseModel):
    states: List[StateVector]
    dt: float  # Time step in seconds


class ConjunctionRequest(BaseModel):
    states: List[StateVector]
    threshold_km: float = 10.0  # Distance threshold for conjunction detection


class ConjunctionResponse(BaseModel):
    pairs: List[dict]
    count: int


@router.post("/propagate", response_model=PropagateResponse)
async def propagate_single(
    req: PropagateRequest, user: dict = Depends(get_current_user)
):
    """
    Propagate a single satellite state by time delta using the C++ physics engine.
    Returns the new state vector after propagation.
    """
    try:
        # Combine r and v into single array for C++ engine
        state = req.state.r + req.state.v
        new_state = propagate(state, req.dt)

        return PropagateResponse(
            r=new_state[:3], v=new_state[3:], propagated_time=req.dt
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Propagation failed: {str(e)}",
        )


@router.post("/propagate/batch", response_model=List[PropagateResponse])
async def propagate_batch(
    req: BatchPropagateRequest, user: dict = Depends(get_current_user)
):
    """
    Propagate multiple satellite states by time delta using the C++ physics engine.
    Returns the new state vectors for all satellites.
    """
    try:
        results = []
        for state in req.states:
            state_array = state.r + state.v
            new_state = propagate(state_array, req.dt)

            results.append(
                PropagateResponse(
                    r=new_state[:3], v=new_state[3:], propagated_time=req.dt
                )
            )

        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch propagation failed: {str(e)}",
        )


@router.post("/propagate/steps")
async def propagate_with_steps(
    req: PropagateRequest, steps: int = 10, user: dict = Depends(get_current_user)
):
    """
    Propagate a satellite state by time delta in multiple steps.
    Returns intermediate states at each step.
    """
    try:
        state = req.state.r + req.state.v
        dt_per_step = req.dt / steps

        states = propagate_steps(state, dt_per_step, steps)

        return {
            "steps": steps,
            "dt_per_step": dt_per_step,
            "total_time": req.dt,
            "states": [
                {"step": i, "r": s[:3], "v": s[3:], "time": i * dt_per_step}
                for i, s in enumerate(states)
            ],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step propagation failed: {str(e)}",
        )


@router.post("/conjunctions", response_model=ConjunctionResponse)
async def detect_conjunctions_api(
    req: ConjunctionRequest, user: dict = Depends(get_current_user)
):
    """
    Detect conjunctions (close approaches) between satellites.
    Returns pairs of satellites that are within the threshold distance.
    """
    try:
        # Convert state vectors to format expected by C++ engine
        states = [s.r + s.v for s in req.states]

        # Detect conjunctions
        conjunctions = detect_conjunctions(states, req.threshold_km)

        return ConjunctionResponse(pairs=conjunctions, count=len(conjunctions))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conjunction detection failed: {str(e)}",
        )


@router.get("/health")
async def propagation_health():
    """Check if the C++ physics engine is available."""
    try:
        # Test propagation with a simple state
        test_state = [7000.0, 0.0, 0.0, 0.0, 7.5, 0.0]
        result = propagate(test_state, 60.0)

        return {"status": "healthy", "engine": "C++", "test_passed": True}
    except Exception as e:
        return {"status": "unhealthy", "engine": "C++", "error": str(e)}
