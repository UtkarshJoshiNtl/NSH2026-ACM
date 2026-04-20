from fastapi import APIRouter
from pydantic import BaseModel
from backend.core.state_manager import state_mgr
from backend.core.physics_bridge import propagate

router = APIRouter()


class StepRequest(BaseModel):
    step_seconds: float


@router.post("/simulate/step")
async def simulate_step(req: StepRequest):
    dt = req.step_seconds

    # Get all satellites and debris using thread-safe methods
    satellites = state_mgr.get_all_satellites()
    debris = state_mgr.get_all_debris()

    # Propagate satellites
    for obj in satellites:
        state = obj.r + obj.v
        new_state = propagate(state, dt)
        obj.r = new_state[:3]
        obj.v = new_state[3:]
        state_mgr.upsert(obj)

    # Propagate debris
    for obj in debris:
        state = obj.r + obj.v
        new_state = propagate(state, dt)
        obj.r = new_state[:3]
        obj.v = new_state[3:]
        state_mgr.upsert(obj)

    # Advance simulation time
    state_mgr.advance_time(dt)

    return {
        "status": "STEP_COMPLETE",
        "simulation_time": state_mgr.simulation_time,
    }
