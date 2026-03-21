from fastapi import APIRouter
from pydantic import BaseModel
from backend.core.state_manager import state_mgr
from backend.core.physics_bridge import propagate, compute_fuel_used
from backend.core.maneuver_planner import apply_burn
import math

router = APIRouter()

class StepRequest(BaseModel):
    step_seconds: float

@router.post("/simulate/step")
async def simulate_step(req: StepRequest):
    dt = req.step_seconds
    
    # 1. Execute maneuvers
    due_burns = state_mgr.pop_due_burns(state_mgr.simulation_time + dt)
    for burn in due_burns:
        sat = state_mgr.get(burn.satellite_id)
        if sat:
            apply_burn(sat, burn.delta_v, burn.burn_time)

    # 2. Propagate ALL objects
    for obj in state_mgr.objects.values():
        obj.r + obj.v # ensure we have state
        new_state = propagate(obj.r + obj.v, dt)
        obj.r = new_state[:3]
        obj.v = new_state[3:]

    # 3. Advance simulation time
    state_mgr.advance_time(dt)
    
    return {
        "status": "STEP_COMPLETE",
        "simulation_time": state_mgr.simulation_time,
        "maneuvers_executed": len(due_burns)
    }
