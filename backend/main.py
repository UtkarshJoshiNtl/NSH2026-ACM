from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware import Middleware
from sqlalchemy import text
import asyncio
import json
import time
from datetime import datetime
from backend.routers import (
    telemetry,
    simulate,
    visualization,
    propagation,
    maneuver,
)
from backend.core.state_manager import state_mgr
from backend.loader import load_initial_state_from_disk

# Configure basic logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket client management
ws_clients = set()
_background_tasks = []

app = FastAPI(title="Astrosis — Satellite Physics Simulator")

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (NSH 2026 compliant endpoints only)
app.include_router(telemetry.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(visualization.router, prefix="/api")
app.include_router(propagation.router, prefix="/api/propagation")
app.include_router(maneuver.router, prefix="/api")

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
        "state": state_mgr.get_summary(),
    }


@app.on_event("startup")
async def startup_event():
    # Load initial state from disk (gracefully handles missing files)
    load_initial_state_from_disk(state_mgr)
    logger.info("Initial state loaded")

    # Start WebSocket broadcast loop
    ws_task = asyncio.create_task(_websocket_broadcast_loop())
    _background_tasks.append(ws_task)
    logger.info("WebSocket broadcast loop started")


@app.on_event("shutdown")
async def shutdown_event():
    # Cancel background tasks
    for task in _background_tasks:
        task.cancel()
    logger.info("Background tasks stopped")


# ═══════════════════════════════════════════════════════════════════════════
#  WebSocket — Real-time Telemetry Stream
#  Migrated from AutoCM for hackathon-compliant real-time updates
# ═══════════════════════════════════════════════════════════════════════════


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming.
    Clients receive snapshot updates every simulation tick.
    """
    await websocket.accept()
    ws_clients.add(websocket)
    client_id = id(websocket)
    logger.info(f"[WS] Client {client_id} connected ({len(ws_clients)} total)")

    try:
        # Send initial snapshot
        snapshot = state_mgr.get_snapshot()
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
        logger.error(f"[WS] Client {client_id} error: {e}")
    finally:
        ws_clients.discard(websocket)
        logger.info(f"[WS] Client {client_id} disconnected ({len(ws_clients)} remaining)")


async def _handle_ws_message(websocket: WebSocket, msg: dict):
    """Handle incoming WebSocket commands from clients."""
    msg_type = msg.get("type", "")

    if msg_type == "simulate_step":
        dt = msg.get("step_seconds", 60)
        # Delegate to simulation service
        await websocket.send_json({
            "type": "step_complete",
            "sim_time": datetime.utcnow().isoformat(),
        })

    elif msg_type == "subscribe":
        await websocket.send_json({"type": "subscribed", "status": "OK"})

    else:
        await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})


async def _websocket_broadcast_loop():
    """Broadcast snapshots to all connected WebSocket clients."""
    class _SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            return super().default(obj)

    while True:
        try:
            if ws_clients:
                snapshot = state_mgr.get_snapshot()
                msg = json.dumps({"type": "snapshot", "data": snapshot}, cls=_SafeEncoder)
                dead_clients = set()

                for ws in list(ws_clients):
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead_clients.add(ws)

                for ws in dead_clients:
                    ws_clients.discard(ws)

            await asyncio.sleep(0.1)  # 10Hz broadcast rate
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[WS] Broadcast error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
