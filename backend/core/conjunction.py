"""
backend/core/conjunction.py — Conjunction Detection
==================================================
Detect conjunctions between satellites and debris using the physics engine.
"""

import asyncio
from typing import List
from backend.core.state_manager import state_mgr
from backend.core.physics import detect_conjunctions

CRITICAL_DISTANCE = 0.1  # km
WARNING_DISTANCE = 1.0   # km


async def check_conjunctions_async():
    """
    Asynchronously check for conjunctions and update CDMs in state manager.
    This is designed to run as a background task.
    """
    try:
        satellites = state_mgr.get_all_satellites()
        debris = state_mgr.get_all_debris()
        
        if not satellites or not debris:
            return
        
        # Convert to state vectors
        sat_states = [[s.r[0], s.r[1], s.r[2], s.v[0], s.v[1], s.v[2]] for s in satellites]
        deb_states = [[d.r[0], d.r[1], d.r[2], d.v[0], d.v[1], d.v[2]] for d in debris]
        
        # Detect conjunctions
        conjunctions = detect_conjunctions(sat_states + deb_states, WARNING_DISTANCE)
        
        # Convert to CDM format
        cdms = []
        for c in conjunctions:
            sat_id = satellites[c[0]].id if c[0] < len(satellites) else debris[c[0] - len(satellites)].id
            deb_id = debris[c[1]].id if c[1] < len(debris) else satellites[c[1] - len(debris)].id
            distance = c[2]
            
            severity = "CRITICAL" if distance < CRITICAL_DISTANCE else "WARNING"
            
            cdms.append({
                "satellite_id": sat_id,
                "debris_id": deb_id,
                "distance_km": distance,
                "severity": severity,
                "time_to_closest_approach": c[3] if len(c) > 3 else 0.0
            })
        
        # Update state manager
        state_mgr.update_cdms(cdms)
        
    except Exception as e:
        print(f"Error in conjunction check: {e}")
