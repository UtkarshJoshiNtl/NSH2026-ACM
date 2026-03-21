from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from backend.routers import telemetry, maneuver, simulate, visualization
from backend.core.state_manager import state_mgr
import json
import os
import asyncio
from backend.core.auto_cola import autonomous_cola_loop

app = FastAPI(title="ACM — Autonomous Constellation Manager")

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Routers
app.include_router(telemetry.router, prefix="/api")
app.include_router(maneuver.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(visualization.router, prefix="/api")

# Static files for frontend
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

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
        print(f"Loaded initial state: {len(sats)} sats, {len(debris)} debris")
    
    # Start background COLA loop
    async def cola_task():
        while True:
            try:
                await autonomous_cola_loop()
            except Exception as e:
                print(f"Error in COLA loop: {e}")
            await asyncio.sleep(60) # Run every minute
            
    asyncio.create_task(cola_task())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
