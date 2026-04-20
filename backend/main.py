from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware import Middleware
from sqlalchemy import text
from backend.routers import (
    telemetry,
    simulate,
    visualization,
    tle,
    auth,
    simulations,
    propagation,
    export,
)
from backend.core.state_manager import state_mgr
from backend.loader import load_initial_state_from_disk
from backend.rate_limit import rate_limit_middleware
from backend.logging_config import setup_logging, get_correlation_id, set_correlation_id
from backend.database import engine
from backend.cache import RedisCache
from backend.tle_scheduler import tle_scheduler

# Configure structured logging
logger = setup_logging()

app = FastAPI(title="Astrosis — Satellite Physics Simulator")

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware)

# Routers
app.include_router(telemetry.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(visualization.router, prefix="/api")
app.include_router(tle.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(simulations.router, prefix="/api")
app.include_router(propagation.router, prefix="/api/propagation")
app.include_router(export.router, prefix="/api")

# Static files for frontend
import os

if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/api/health")
async def health_check():
    """Service health and state summary with dependency verification."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": {},
        "state": state_mgr.get_summary(),
    }

    # Check database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["dependencies"]["database"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["dependencies"]["database"] = f"disconnected: {str(e)}"

    # Check Redis connectivity
    try:
        redis_cache = RedisCache()
        if redis_cache.available:
            redis_cache.set("health_check", "ok", 1)
            redis_cache.get("health_check")
            health_status["dependencies"]["redis"] = "connected"
        else:
            health_status["dependencies"]["redis"] = "disabled (optional)"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["dependencies"]["redis"] = f"disconnected: {str(e)}"

    # Check physics engine
    try:
        from backend.core.physics.loader import physics as _physics

        if _physics:
            health_status["dependencies"]["physics_engine"] = "loaded"
        else:
            health_status["dependencies"]["physics_engine"] = "using_fallback"
    except Exception as e:
        health_status["dependencies"]["physics_engine"] = f"error: {str(e)}"

    return health_status


@app.post("/api/tle/refresh")
async def manual_tle_refresh():
    """Manually trigger TLE data refresh."""
    count = await tle_scheduler.refresh_now()
    return {
        "status": "success",
        "refreshed_count": count,
        "message": f"Manually refreshed {count} TLE entries",
    }


@app.on_event("startup")
async def startup_event():
    # Load initial state from disk (gracefully handles missing files)
    load_initial_state_from_disk(state_mgr)

    # Start TLE auto-refresh scheduler
    await tle_scheduler.start()
    logger.info("TLE scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    # Stop TLE scheduler
    await tle_scheduler.stop()
    logger.info("TLE scheduler stopped")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
