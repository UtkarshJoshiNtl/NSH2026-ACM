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

    # Propagate ALL objects (snapshot IDs first to avoid mutation race)
    all_ids = list(state_mgr.objects.keys())
    for obj_id in all_ids:
        obj = state_mgr.objects.get(obj_id)
        if obj is None:
            continue
        state = obj.r + obj.v
        new_state = propagate(state, dt)
        obj.r = new_state[:3]
        obj.v = new_state[3:]

    # Advance simulation time
    state_mgr.advance_time(dt)

    return {
        "status": "STEP_COMPLETE",
        "simulation_time": state_mgr.simulation_time,
    }
