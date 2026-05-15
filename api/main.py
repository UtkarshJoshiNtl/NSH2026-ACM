"""Astrosis REST API — FastAPI application."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging

from engine.physics.accelerator import (
    propagate as acc_propagate,
    propagate_batch,
    detect_conjunctions,
    backend_info,
)
from api.models import (
    PropagateRequest, PropagateResponse,
    BatchPropagateRequest, BatchPropagateResponse,
    ConjunctionRequest, ConjunctionResponse, ConjunctionResult,
    PassRequest,
    HealthResponse, BackendResponse,
)

logger = logging.getLogger("astrosis.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Astrosis Orbital Engine API",
    description=(
        "High-performance satellite propagation and conjunction analysis. "
        "Backend selects CUDA → C++ → NumPy → Python automatically."
    ),
    version="gamma",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Liveness probe. Returns 200 if the engine is loaded."""
    return HealthResponse()


@app.get("/backend", response_model=BackendResponse, tags=["System"])
def backend():
    """
    Returns which compute backend is active and available.
    Priority: CUDA → C++ → NumPy → Pure Python.
    """
    info = backend_info()
    return BackendResponse(
        backend=info["backend"],
        cuda_available=info.get("cuda", False),
        cpp_available=info.get("cpp", False),
        description=info.get("description", ""),
    )


# ── Single Propagation ────────────────────────────────────────────────────────

@app.post("/propagate", response_model=PropagateResponse, tags=["Propagation"])
def propagate_single(req: PropagateRequest):
    """
    Propagate a single satellite state vector forward in time.

    Uses RK4 with J2/J3/J4 gravity perturbations (+ optional drag).
    The active backend is selected automatically at startup.
    """
    try:
        state = req.state
        for _ in range(req.steps):
            if req.with_drag:
                from engine.physics.accelerator import propagate_with_drag
                state = propagate_with_drag(state, req.dt_seconds,
                                            req.area_m2, req.mass_kg, req.cd)
            else:
                state = acc_propagate(state, req.dt_seconds)
        return PropagateResponse(
            state=state,
            backend=backend_info()["backend"],
            steps_taken=req.steps,
        )
    except Exception as e:
        logger.exception("propagate failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Batch Propagation ─────────────────────────────────────────────────────────

@app.post("/propagate/batch", response_model=BatchPropagateResponse, tags=["Propagation"])
def propagate_batch_endpoint(req: BatchPropagateRequest):
    """
    Propagate N satellites simultaneously using the fastest available backend.

    For N > ~300, CUDA backend provides 100–500x speedup over Python.
    Returns all final states in the same order as the input.
    """
    if len(req.states) == 0:
        raise HTTPException(status_code=422, detail="states must be non-empty")
    for i, s in enumerate(req.states):
        if len(s) != 6:
            raise HTTPException(status_code=422, detail=f"State {i} must have 6 elements")
    try:
        result = propagate_batch(
            req.states, req.dt_seconds, req.steps,
            area=req.area_m2, mass=req.mass_kg, cd=req.cd,
            with_drag=req.with_drag,
        )
        return BatchPropagateResponse(
            states=result,
            backend=backend_info()["backend"],
            n_satellites=len(req.states),
            steps_taken=req.steps,
        )
    except Exception as e:
        logger.exception("batch propagate failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Conjunction Detection ─────────────────────────────────────────────────────

@app.post("/conjunctions", response_model=ConjunctionResponse, tags=["Conjunction"])
def conjunctions(req: ConjunctionRequest):
    """
    All-pairs conjunction screening between a set of satellites and debris.

    Returns warnings with severity (ADVISORY / WARNING / CRITICAL), Brent-refined
    TCA, and Chan's method Probability of Collision.
    """
    n_sats = len(req.sat_states)
    n_debs = len(req.debris_states)
    if n_sats == 0 or n_debs == 0:
        raise HTTPException(status_code=422, detail="sat_states and debris_states must be non-empty")

    try:
        raw = detect_conjunctions(
            req.sat_states, req.debris_states,
            lookahead=req.lookahead_s, step_s=req.step_s,
        )
        warnings = []
        for w in raw:
            pc = getattr(w, "pc", None) or (
                w.pc_result.pc if hasattr(w, "pc_result") else None
            )
            warnings.append(ConjunctionResult(
                sat_id=w.sat_id,
                debris_id=w.debris_id,
                current_distance=w.current_distance,
                time_to_closest_approach=w.time_to_closest_approach,
                severity=w.severity,
                relative_velocity=list(w.relative_velocity),
                probability_of_collision=pc,
            ))
        return ConjunctionResponse(
            warnings=warnings,
            n_pairs_checked=n_sats * n_debs,
            backend=backend_info()["backend"],
        )
    except Exception as e:
        logger.exception("conjunction detection failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Pass Prediction ───────────────────────────────────────────────────────────

@app.post("/passes/{norad_id}", tags=["Analysis"])
def passes(norad_id: int, req: PassRequest):
    """
    Predict passes of a satellite (by NORAD ID) over a ground station.

    Fetches and caches the TLE from CelesTrak, then propagates and checks
    elevation above the horizon. Returns a list of rise/culmination/set events.
    """
    try:
        from engine.analysis import report_passes
        result = report_passes(
            norad_id=norad_id,
            lat=req.lat,
            lon=req.lon,
            alt=req.alt_km,
            start_dt=datetime.utcnow(),
            hours=req.hours,
            dt_step=req.dt_step_s,
        )
        return result
    except Exception as e:
        logger.exception("pass prediction failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
