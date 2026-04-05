from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from backend.routers import telemetry, maneuver, simulate, visualization, history
from backend.core.state_manager import state_mgr
import json
import os
import asyncio
import logging
from backend.core.auto_cola import autonomous_cola_loop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Astrosis-Backend")

app = FastAPI(title="Astrosis — Orbital Intelligence API")

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers
app.include_router(telemetry.router, prefix="/api")
app.include_router(maneuver.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(visualization.router, prefix="/api")
app.include_router(history.router, prefix="/api")

# Static files for frontend
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/api/health")
async def health_check():
    """Service health and state summary."""
    return {
        "status": "healthy",
        "version": "2.0.1",
        "state": state_mgr.get_summary()
    }

@app.on_event("startup")
async def startup_event():
    # Load initial state
    sats_path = "data/initial_satellites.json"
    debris_path = "data/initial_debris.json"
    
    if os.path.exists(sats_path) and os.path.exists(debris_path):
        with open(sats_path, 'r') as f:
            sats = json.load(f)
        with open(debris_path, 'r') as f:
            debris = json.load(f)
        state_mgr.load_initial_state(sats, debris)
        logger.info(f"Loaded initial state: {len(sats)} sats, {len(debris)} debris")
    
    # Start background COLA loop
    async def cola_task():
        logger.info("Starting background COLA service...")
        while True:
            try:
                await autonomous_cola_loop()
            except Exception as e:
                logger.error(f"Error in COLA loop: {e}", exc_info=True)
            await asyncio.sleep(60) # Run every minute
            
    asyncio.create_task(cola_task())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
