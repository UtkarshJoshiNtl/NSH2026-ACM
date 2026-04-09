from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from backend.routers import telemetry, simulate, visualization, tle
from backend.core.state_manager import state_mgr
from backend.loader import load_initial_state_from_disk
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Astrosis-Backend")

app = FastAPI(title="Astrosis — Satellite Physics Simulator")

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers
app.include_router(telemetry.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(visualization.router, prefix="/api")
app.include_router(tle.router, prefix="/api")

# Static files for frontend
import os
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/api/health")
async def health_check():
    """Service health and state summary."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "state": state_mgr.get_summary()
    }

@app.on_event("startup")
async def startup_event():
    # Load initial state from disk (gracefully handles missing files)
    load_initial_state_from_disk(state_mgr)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
