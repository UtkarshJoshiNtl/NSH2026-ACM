"""
backend/core/auto_cola.py — ACM Autonomous Collision Avoidance Loop
=====================================================================
Background async task that periodically:
1. Runs conjunction assessment
2. Schedules evasion + recovery burns for CRITICAL CDMs
3. Triggers graveyard maneuvers for EOL satellites
"""

import asyncio
import logging
import uuid
import time

from backend.core.state_manager import state_mgr, ScheduledBurn
from backend.core.conjunction import check_conjunctions_async
from backend.core.maneuver_planner import (
    compute_evasion_burn, compute_recovery_burn, estimate_graveyard_burn,
    validate_burn, EOL_FUEL_PCT,
)
from backend.core.ground_station import check_los
from backend.core.physics_bridge import _vec_mag as vec_mag

logger = logging.getLogger(__name__)

EOL_INITIAL_FUEL = 50.0   # kg


async def autonomous_cola_loop(
    lookahead_s: float = 86400.0,
    step_s: float = 60.0,
) -> int:
    """
    Single pass of the autonomous COLA loop.
    Returns the number of maneuvers scheduled.
    """
    cdms = await check_conjunctions_async(lookahead_s, step_s)

    scheduled_count = 0
    # Track which satellites already have an evasion queued this pass
    already_queued: set = set()

    for cdm in cdms:
        if cdm["severity"] != "CRITICAL":
            continue

        sat = state_mgr.get(cdm["sat_id"])
        if sat is None or sat.obj_type != "SATELLITE":
            continue
        if sat.id in already_queued:
            continue

        sim_now = state_mgr.simulation_time

        # Check LOS before scheduling
        if not check_los(sat.r):
            logger.info("Sat %s: CRITICAL CDM but no LOS — cannot schedule evasion", sat.id)
            continue

        # ── Evasion burn ───────────────────────────────────────────────────────
        burn_time_evasion = sim_now + 10.0   # 10 s latency

        dv_evasion = compute_evasion_burn(sat, cdm)
        dv_mag = vec_mag(dv_evasion)
        if dv_mag < 1e-12:
            continue

        val = validate_burn(sat, dv_mag, burn_time_evasion)
        if not val["ok"]:
            logger.warning("Sat %s: evasion rejected — %s", sat.id, val["reason"])
            continue

        evasion_burn = ScheduledBurn(
            burn_id=f"EVADE_{cdm['debris_id']}_{uuid.uuid4().hex[:6]}",
            satellite_id=sat.id,
            burn_time=burn_time_evasion,
            delta_v=dv_evasion,
            burn_type="EVASION",
        )
        state_mgr.queue_burn(evasion_burn)

        # ── Recovery burn (90 min / half-period later) ─────────────────────────
        burn_time_recovery = burn_time_evasion + 5400.0   # ~90 min

        dv_recovery = compute_recovery_burn(sat)
        rec_mag = vec_mag(dv_recovery)

        if rec_mag > 1e-12:
            recovery_burn = ScheduledBurn(
                burn_id=f"RECOVER_{cdm['debris_id']}_{uuid.uuid4().hex[:6]}",
                satellite_id=sat.id,
                burn_time=burn_time_recovery,
                delta_v=dv_recovery,
                burn_type="RECOVERY",
            )
            state_mgr.queue_burn(recovery_burn)

        already_queued.add(sat.id)
        scheduled_count += 1
        logger.info("Sat %s: scheduled EVADE+RECOVER for debris %s (dist=%.4f km)",
                    sat.id, cdm["debris_id"], cdm["distance_km"])

    # ── EOL check — schedule graveyard maneuvers ───────────────────────────────
    for sat in state_mgr.get_all_satellites():
        if sat.m_fuel / EOL_INITIAL_FUEL < EOL_FUEL_PCT and sat.status != "EOL":
            sat.status = "EOL"
            logger.warning("Satellite %s is EOL (fuel=%.2f kg). Scheduling graveyard.", sat.id, sat.m_fuel)
            if check_los(sat.r):
                dv_gy = estimate_graveyard_burn(sat)
                gy_burn = ScheduledBurn(
                    burn_id=f"GRAVE_{sat.id}_{uuid.uuid4().hex[:6]}",
                    satellite_id=sat.id,
                    burn_time=state_mgr.simulation_time + 60.0,
                    delta_v=dv_gy,
                    burn_type="GRAVEYARD",
                )
                state_mgr.queue_burn(gy_burn)

    return scheduled_count
