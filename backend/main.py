"""
═══════════════════════════════════════════════════════════════════════════
 ACM API — main.py
 FastAPI entry point with WebSocket support for real-time telemetry.
 National Space Hackathon 2026

 Run with:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
═══════════════════════════════════════════════════════════════════════════
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .state_manager import state
from .routers.telemetry import router as telemetry_router
from .routers.maneuvers import router as maneuvers_router
from .routers.rulebook_api import router as rulebook_router
from .routers.auth import router as auth_router


# ═══════════════════════════════════════════════════════════════════════════
#  Application Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load catalog and begin simulation loop."""
    print("=" * 70)
    print("  AUTONOMOUS CONSTELLATION MANAGER - FastAPI Backend")
    print("  National Space Hackathon 2026")
    print("=" * 70)

    # Load satellite & debris catalog
    catalog_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "catalog.json"
    )
    state.load_catalog(catalog_path)

    # Start simulation by default for demo
    if not state.sim_running:
        state.sim_running = True
        state.step_seconds = 1
        state.real_interval_ms = 1000
        print("[API] Simulation started by default for demo")

    print(f"[API] Server ready - {len(state.satellites)} satellites, "
          f"{len(state.debris)} debris tracked")
    print(f"[API] Dashboard: http://localhost:8000")
    print(f"[API] API Docs:  http://localhost:8000/docs")

    # Start background simulation loop
    sim_task = asyncio.create_task(_simulation_loop())
    ws_task = asyncio.create_task(_websocket_broadcast_loop())
    
    # Add to global list to prevent garbage collection
    _background_tasks.append(sim_task)
    _background_tasks.append(ws_task)

    yield

    # Shutdown
    sim_task.cancel()
    ws_task.cancel()
    print("[API] Shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════
#  FastAPI Application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ACM — Autonomous Constellation Manager",
    description="Real-time satellite constellation management with autonomous "
                "collision avoidance. National Space Hackathon 2026.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard on any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Include Routers ───────────────────────────────────────────────────────

app.include_router(telemetry_router, prefix="/api")
app.include_router(maneuvers_router, prefix="/api")
app.include_router(rulebook_router)  # Rulebook compliant endpoints
# Alias: grader also calls /api/satellites/telemetry per problem statement Section 4.1
from fastapi import Request
from fastapi.responses import JSONResponse

@app.post("/api/satellites/telemetry")
async def satellites_telemetry_alias(request: Request):
    """Alias for /api/telemetry to match problem statement Section 4.1 exactly."""
    from .routers.rulebook_api import post_telemetry
    from .routers.rulebook_api import TelemetryPayload
    body = await request.json()
    payload = TelemetryPayload(**body)
    return await post_telemetry(payload)

app.include_router(auth_router)


# ═══════════════════════════════════════════════════════════════════════════
#  Core API Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "sim_time": state.sim_time.isoformat(),
        "satellites": len(state.satellites),
        "debris": len(state.debris),
        "ws_clients": len(state.ws_clients),
    }


@app.get("/api/visualization/snapshot")
async def get_snapshot():
    """Rulebook compliant snapshot (Section 6.3) - optimized for telemetry."""
    # Ensure consistent formatting for debris cloud [ID, lat, lon, alt]
    snapshot = state.get_snapshot()
    return snapshot


@app.get("/api/constellation/stats")
async def get_constellation_stats():
    """Constellation statistics including ΔV totals."""
    return state.get_stats()


@app.get("/api/alerts")
async def get_alerts(after: int = 0):
    """Get mission alerts (since-based polling)."""
    alerts = state.get_alerts_since(after)
    latest_id = alerts[0]["id"] if alerts else after
    return {"alerts": alerts, "latest_id": latest_id}


# ── Simulation Control ────────────────────────────────────────────────────

@app.post("/api/simulate/step")
async def simulation_step(body: dict = None):
    """Advance simulation by one step."""
    step_seconds = 60
    if body and "step_seconds" in body:
        try:
            step_seconds = float(body["step_seconds"])
        except (TypeError, ValueError):
            step_seconds = 60
    result = state.simulate_step(step_seconds)
    if not isinstance(result, dict):
        result = {
            "status": "STEP_COMPLETE",
            "new_timestamp": state.sim_time.isoformat(),
            "collisions_detected": 0,
            "maneuvers_executed": 0,
        }
    return result


@app.post("/api/simulate/run")
async def simulation_run(body: dict = None):
    """Start continuous simulation (Section 4 endpoint)."""
    if body:
        state.step_seconds = body.get("step_seconds", 60)
        state.real_interval_ms = body.get("real_interval_ms", 1000)
    state.sim_running = True
    return {"status": "OK", "running": True}


@app.post("/api/simulate/stop")
async def simulation_stop():
    """Stop continuous simulation (Section 4 endpoint)."""
    state.sim_running = False
    return {"status": "OK", "running": False}


@app.get("/api/simulate/status")
async def simulation_get_status():
    """Get simulation status (Section 4 endpoint)."""
    return {
        "running": state.sim_running,
        "sim_time": state.sim_time.isoformat(),
        "step_seconds": state.step_seconds,
        "real_interval_ms": state.real_interval_ms,
    }


# Legacy endpoint aliases for backward compatibility (Deprecated)
@app.post("/api/simulation/run")
async def start_simulation_sim_alias(body: dict = None):
    return await simulation_run(body)

@app.post("/api/simulation/stop")
async def stop_simulation_sim_alias():
    return await simulation_stop()

@app.get("/api/simulation/status")
async def simulation_status_sim_alias():
    return await simulation_get_status()

@app.post("/api/threat/inject")
async def inject_threat(request: Request):
    """Inject a threat for a satellite via REST API - creates debris at threatening position."""
    try:
        body = await request.json()
        sat_id = body.get("satellite_id")
        if sat_id and sat_id in state.satellites:
            from datetime import datetime, timedelta
            import numpy as np
            from api.models import Debris, Vector3
            from api.core.physics import eci_to_latlon
            
            sat = state.satellites[sat_id]
            
            # Create debris at threatening position (10 minutes away for demo)
            sat_r = sat.r.to_np()
            sat_v = sat.v.to_np()
            
            # Calculate where satellite will be in 10 minutes (600 seconds) for demo
            from api.core.physics import J2RK4Propagator
            prop = J2RK4Propagator()
            future_r, future_v = prop.propagate(sat_r, sat_v, 600.0)
            
            # Place debris at future position (10 minutes ahead for demo)
            threat_r = future_r
            # Debris velocity similar to satellite to maintain near-miss
            threat_v = future_v
            
            # Add small offset to create 0.1 km miss distance at TCA
            # Offset in normal direction (perpendicular to velocity)
            v_norm = future_v / np.linalg.norm(future_v)
            if abs(v_norm[0]) < 0.9:
                perp = np.cross(v_norm, np.array([1, 0, 0]))
            else:
                perp = np.cross(v_norm, np.array([0, 1, 0]))
            perp = perp / np.linalg.norm(perp)
            threat_r = threat_r + perp * 0.1
            
            # Calculate threat distance for alert
            threat_distance_km = 0.1
            
            # Create debris object
            debris_id = f"THREAT-{sat_id}-{datetime.now().strftime('%H%M%S')}"
            deb = Debris(
                id=debris_id,
                lat=0, lon=0, alt_km=0,  # Will be calculated
                r=Vector3.from_np(threat_r),
                v=Vector3.from_np(threat_v)
            )
            
            # Calculate lat/lon
            deb.lat, deb.lon, deb.alt_km = eci_to_latlon(threat_r, t=state.sim.sim_time)
            
            # Add debris to fleet
            state.fleet.add_debris(deb)
            
            # Trigger conjunction detection
            sats = list(state.fleet.satellites.values())
            debs = list(state.fleet.debris.values())
            print(f"[THREAT] Before screen_fleet: {len(debs)} debris, checking for conjunctions")
            state.conj.screen_fleet(sats, debs, state.sim.sim_time)
            print(f"[THREAT] After screen_fleet: {len(state.conj.active_cdms)} CDMs created")
            
            state._add_alert("THREAT_INJECTION", "CRITICAL",
                           f"Threat debris {debris_id} injected at {threat_distance_km}km from {sat_id}", sat_id)
            
            return {
                "status": "success", 
                "satellite_id": sat_id, 
                "debris_id": debris_id,
                "distance_km": threat_distance_km,
                "message": f"Debris {debris_id} created at threatening position"
            }
        return {"status": "error", "message": "Invalid satellite_id"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
#  WebSocket — Real-time Telemetry Stream
# ═══════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming.
    Clients receive snapshot updates every simulation tick.
    Clients can also send commands via the WebSocket.
    """
    await websocket.accept()
    state.register_ws(websocket)
    client_id = id(websocket)
    print(f"[WS] Client {client_id} connected ({len(state.ws_clients)} total)")

    try:
        # Send initial snapshot
        snapshot = state.get_snapshot()
        await websocket.send_json({
            "type": "snapshot",
            "data": snapshot,
        })

        # Listen for client commands while connected
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                msg = json.loads(data)
                await _handle_ws_message(websocket, msg)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "ts": time.time()})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Client {client_id} error: {e}")
    finally:
        state.unregister_ws(websocket)
        print(f"[WS] Client {client_id} disconnected ({len(state.ws_clients)} remaining)")


async def _handle_ws_message(websocket: WebSocket, msg: dict):
    """Handle incoming WebSocket commands from clients with 10s signal delay."""
    msg_type = msg.get("type", "")
    command_timestamp = msg.get("timestamp")
    
    # Enforce 10-second signal delay (Section 4.2)
    current_time = time.time()
    if command_timestamp:
        time_diff = current_time - command_timestamp
        if time_diff < 10.0:
            await websocket.send_json({
                "type": "error",
                "message": f"Command violates 10s signal delay. Received after {time_diff:.2f}s, need 10s minimum."
            })
            return
    
    if msg_type == "simulate_step":
        dt = msg.get("step_seconds", 60)
        state.simulate_step(dt)
        await websocket.send_json({
            "type": "step_complete",
            "sim_time": state.sim_time.isoformat(),
        })

    elif msg_type == "subscribe":
        # Client subscribes to specific satellite updates
        await websocket.send_json({"type": "subscribed", "status": "OK"})

    elif msg_type == "command_maneuver":
        sat_id = msg.get("satellite_id")
        delta_v = msg.get("delta_v", {"x": 0, "y": 0, "z": 0})
        result = state.execute_maneuver(sat_id, delta_v)
        await websocket.send_json({"type": "maneuver_result", "data": result})

    elif msg_type == "inject_threat":
        # Allow injecting a threat for demonstration
        sat_id = msg.get("satellite_id")
        if sat_id and sat_id in state.satellites:
            state.satellites[sat_id].status = "EVADING"
            state._add_alert("THREAT_INJECTION", "CRITICAL",
                           f"Manual threat injected for {sat_id}", sat_id)
            await websocket.send_json({"type": "threat_injected", "satellite_id": sat_id})

    else:
        await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})


# ═══════════════════════════════════════════════════════════════════════════
#  Background Loops
# ═══════════════════════════════════════════════════════════════════════════

# Store task references to prevent garbage collection
_background_tasks = []

async def _simulation_loop():
    """Background simulation loop — advances state when sim_running=True."""
    while True:
        try:
            if state.sim_running:
                state.simulate_step(state.step_seconds)
            await asyncio.sleep(state.real_interval_ms / 1000.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[SIM] Error in simulation loop: {e}")
            await asyncio.sleep(1)


async def _websocket_broadcast_loop():
    """Broadcast snapshots to all connected WebSocket clients."""
    import datetime as _dt

    class _SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (_dt.datetime, _dt.date)):
                return obj.isoformat()
            try:
                from pydantic import BaseModel
                if isinstance(obj, BaseModel):
                    return obj.model_dump()
            except ImportError:
                pass
            return super().default(obj)

    while True:
        try:
            if state.ws_clients:
                snapshot = state.get_snapshot()
                msg = json.dumps({"type": "snapshot", "data": snapshot}, cls=_SafeEncoder)
                dead_clients = set()

                for ws in list(state.ws_clients):
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead_clients.add(ws)

                for ws in dead_clients:
                    state.unregister_ws(ws)

            # Synchronize broadcast rate closely with the simulation tick, down to ~10ms hardware limit
            await asyncio.sleep(max(state.real_interval_ms / 1000.0, 0.01))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WS] Broadcast error: {e}")
            await asyncio.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════
#  Static Files — Serve Dashboard
# ═══════════════════════════════════════════════════════════════════════════

# Serve the frontend dashboard
_frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(_frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(_frontend_dir, "js")), name="js")

    @app.get("/")
    async def serve_dashboard():
        """Serve the main dashboard HTML."""
        return FileResponse(os.path.join(_frontend_dir, "index.html"))
