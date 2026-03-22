from fastapi import APIRouter
from pydantic import BaseModel
from backend.core.state_manager import state_mgr
from backend.core.physics_bridge import propagate, compute_fuel_used
from backend.core.maneuver_planner import apply_burn
from backend.core.station_keeping import check_all_slots

router = APIRouter()

class StepRequest(BaseModel):
    step_seconds: float

@router.post("/simulate/step")
async def simulate_step(req: StepRequest):
    dt = req.step_seconds

    # 1. Execute maneuvers due within this step
    due_burns = state_mgr.pop_due_burns(state_mgr.simulation_time + dt)
    for burn in due_burns:
        sat = state_mgr.get(burn.satellite_id)
        if sat:
            fuel_used = apply_burn(sat, burn.delta_v, burn.burn_time)
            state_mgr.log_executed_burn(burn, fuel_used)

    # 2. Propagate ALL objects
    for obj in state_mgr.objects.values():
        state = obj.r + obj.v
        new_state = propagate(state, dt)
        obj.r = new_state[:3]
        obj.v = new_state[3:]

    # 3. Station keeping drift check
    check_all_slots(state_mgr.get_all_satellites())

    # 4. Advance simulation time
    state_mgr.advance_time(dt)

    return {
        "status": "STEP_COMPLETE",
        "simulation_time": state_mgr.simulation_time,
        "maneuvers_executed": len(due_burns),
        "history_count": len(state_mgr.maneuver_history),
    }
