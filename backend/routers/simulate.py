from fastapi import APIRouter
from pydantic import BaseModel
from backend.core.state_manager import state_mgr
from backend.core.physics_bridge import propagate
from datetime import datetime

router = APIRouter()


class StepRequest(BaseModel):
    step_seconds: float


@router.post("/simulate/step")
async def simulate_step(req: StepRequest):
    """
    Advance simulation by specified time step.
    NSH 2026 Section 4.3 compliant response format.
    """
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

    # Execute scheduled maneuvers within this time window
    maneuvers_executed = 0
    current_time = state_mgr.simulation_time
    if isinstance(current_time, str):
        current_time = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
    
    end_time = current_time + datetime.timedelta(seconds=dt)
    
    # Get and execute pending burns
    pending_burns = state_mgr.get_scheduled_burns()
    for burn in pending_burns:
        burn_time = burn.burn_time if hasattr(burn, 'burn_time') else burn.get('burn_time')
        if isinstance(burn_time, str):
            burn_time = datetime.fromisoformat(burn_time.replace('Z', '+00:00'))
        
        if current_time <= burn_time <= end_time:
            # Execute the burn
            sat_id = burn.satellite_id if hasattr(burn, 'satellite_id') else burn.get('satellite_id')
            delta_v = burn.delta_v if hasattr(burn, 'delta_v') else burn.get('delta_v')
            
            sat = state_mgr.get_satellite(sat_id)
            if sat:
                # Apply delta-v
                sat.v[0] += delta_v[0]
                sat.v[1] += delta_v[1]
                sat.v[2] += delta_v[2]
                state_mgr.upsert(sat)
                maneuvers_executed += 1

    # Check for collisions (conjunctions < 100m)
    collisions_detected = 0
    for cdm in state_mgr.active_cdms:
        if cdm.get('distance_km', 999) < 0.1:  # 100m threshold
            collisions_detected += 1

    # Advance simulation time
    state_mgr.advance_time(dt)

    return {
        "status": "STEP_COMPLETE",
        "new_timestamp": state_mgr.simulation_time.isoformat() if hasattr(state_mgr.simulation_time, 'isoformat') else state_mgr.simulation_time,
        "collisions_detected": collisions_detected,
        "maneuvers_executed": maneuvers_executed,
    }
