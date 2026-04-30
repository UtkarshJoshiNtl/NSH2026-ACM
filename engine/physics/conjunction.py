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

from .propagator import rk4_py
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
        Uses a KDTree to cull distant pairs efficiently.
        """
        warnings = []
        
        if not sat_states or not debris_states:
            return []

        # 1. Broad Phase: Initial distance check (t=0)
        # Combine into KDTree for spatial query
        sat_pos = [s[:3] for s in sat_states]
        debris_pos = [d[:3] for d in debris_states]
        
        tree = KDTree(debris_pos)
        
        # Find all pairs within ADVISORY_DISTANCE * 10 (coarse sweep)
        # We assume orbits don't drift by more than ~50km relative to each other in 24h for LEO.
        candidates = tree.query_ball_point(sat_pos, r=50.0) 
        
        # 2. Narrow Phase: Temporal sweep for each candidate pair
        for sat_idx, candidate_list in enumerate(candidates):
            for deb_idx in candidate_list:
                s_state = tuple(sat_states[sat_idx])
                d_state = tuple(debris_states[deb_idx])
                
                min_dist = float('inf')
                tca_time = 0.0
                rel_v_at_tca = [0.0, 0.0, 0.0]
                
                # Simple temporal search
                # In production, we'd use Brent's method for TCA refinement
                for t in np.arange(0, lookahead_s, step_s):
                    # Compute distance from current propagated states
                    r_sat = np.array(s_state[:3])
                    r_deb = np.array(d_state[:3])
                    
                    dist = np.linalg.norm(r_sat - r_deb)
                    
                    if dist < min_dist:
                        min_dist = dist
                        tca_time = t
                        rel_v_at_tca = list(np.array(s_state[3:]) - np.array(d_state[3:]))
                        
                    # Advance states for next iteration
                    if t + step_s < lookahead_s:
                        s_state = rk4_py(s_state, step_s)
                        d_state = rk4_py(d_state, step_s)
                        
                if min_dist < ADVISORY_DISTANCE:
                    severity = "NONE"
                    if min_dist < CRITICAL_DISTANCE:
                        severity = "CRITICAL"
                    elif min_dist < WARNING_DISTANCE:
                        severity = "WARNING"
                    else:
                        severity = "ADVISORY"
                        
                    warnings.append(ConjunctionWarning(
                        sat_id=sat_idx,
                        debris_id=deb_idx,
                        current_distance=float(min_dist),
                        time_to_closest_approach=float(tca_time),
                        severity=severity,
                        relative_velocity=rel_v_at_tca
                    ))
                    
        return warnings
