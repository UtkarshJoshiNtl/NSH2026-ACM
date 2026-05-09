"""
astrosis/physics/conjunction.py — Space Traffic Management Logic
================================================================
Identifies close approaches between objects using temporal sweep.
"""

import math
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from scipy.spatial import KDTree

from .propagator import rk4_step
from ..constants import CRITICAL_DISTANCE, WARNING_DISTANCE, ADVISORY_DISTANCE


@dataclass
class ConjunctionWarning:
    sat_id: int
    debris_id: int
    current_distance: float  # km at TCA
    time_to_closest_approach: float  # s
    severity: str
    relative_velocity: List[float]  # [vx, vy, vz] at TCA


class ConjunctionDetector:
    def __init__(self):
        pass

    def detect(
        self,
        sat_states: List[List[float]],
        debris_states: List[List[float]],
        lookahead_s: float = 86400.0,
        step_s: float = 60.0
    ) -> List[ConjunctionWarning]:
        """
        Detect potential collisions within a lookahead window.
        Uses a KDTree to cull distant pairs, then performs a temporal sweep
        using pre-propagated states to avoid redundant calculations.
        """
        if not sat_states or not debris_states:
            return []

        # 1. Broad Phase: Initial distance check (t=0)
        sat_pos = [s[:3] for s in sat_states]
        debris_pos = [d[:3] for d in debris_states]
        tree = KDTree(debris_pos)
        candidates = tree.query_ball_point(sat_pos, r=50.0) 

        # 2. Narrow Phase: Temporal sweep
        # To avoid redundant propagation, we propagate all involved objects once.
        # For simplicity in this implementation, we propagate ALL objects.
        from .accelerator import propagate_batch
        
        n_steps = int(lookahead_s / step_s)
        dt = step_s
        
        # Pre-propagate all satellites and debris
        # Shape: (steps+1, N, 6)
        all_sats = [sat_states]
        all_debs = [debris_states]
        
        curr_sats = sat_states
        curr_debs = debris_states
        
        for _ in range(n_steps):
            # We use steps=1 to get the state at each step
            curr_sats = propagate_batch(curr_sats, dt, 1)
            curr_debs = propagate_batch(curr_debs, dt, 1)
            all_sats.append(curr_sats)
            all_debs.append(curr_debs)

        warnings = []
        for sat_idx, candidate_list in enumerate(candidates):
            for deb_idx in candidate_list:
                min_dist = float('inf')
                tca_time = 0.0
                rel_v_at_tca = [0.0, 0.0, 0.0]
                
                for step in range(n_steps + 1):
                    s = all_sats[step][sat_idx]
                    d = all_debs[step][deb_idx]
                    
                    dx = s[0] - d[0]
                    dy = s[1] - d[1]
                    dz = s[2] - d[2]
                    dist_sq = dx*dx + dy*dy + dz*dz
                    
                    if dist_sq < min_dist * min_dist:
                        min_dist = math.sqrt(dist_sq)
                        tca_time = step * step_s
                        rel_v_at_tca = [s[3]-d[3], s[4]-d[4], s[5]-d[5]]
                
                if min_dist < ADVISORY_DISTANCE:
                    severity = "NONE"
                    if min_dist < CRITICAL_DISTANCE: severity = "CRITICAL"
                    elif min_dist < WARNING_DISTANCE: severity = "WARNING"
                    else: severity = "ADVISORY"
                        
                    warnings.append(ConjunctionWarning(
                        sat_id=sat_idx, debris_id=deb_idx,
                        current_distance=min_dist,
                        time_to_closest_approach=tca_time,
                        severity=severity, relative_velocity=rel_v_at_tca
                    ))
                    
        return warnings
