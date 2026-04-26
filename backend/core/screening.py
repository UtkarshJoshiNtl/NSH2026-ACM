"""
═══════════════════════════════════════════════════════════════════════════
 ACM CORE — screening.py
 Fast Proximity Detection using SciPy KD-Tree
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import numpy as np
from scipy.spatial import cKDTree
from typing import List, Dict, Tuple

class ConjunctionScreener:
    """
    Efficiently identifies close approaches between satellites and debris.
    Uses SciPy's cKDTree (backed by C++) to avoid O(N^2) bottlenecks.
    """

    def __init__(self, critical_threshold_km: float = 0.1):
        """
        Args:
            critical_threshold_km: Distance below which a conjunction is 'Critical'.
        """
        self.threshold = critical_threshold_km

    def find_conjunctions(
        self, 
        satellites: List[Dict], 
        debris: List[Dict], 
        radius_km: float = 5.0
    ) -> List[Dict]:
        """
        Screens for all debris within radius_km of any satellite.
        
        Args:
            satellites: List of dicts with 'id' and 'r' (numpy array).
            debris: List of dicts with 'id' and 'r' (numpy array).
            radius_km: Search radius (e.g., 5km for advisory alerts).
            
        Returns:
            List of conjunction records: [{"sat_id", "deb_id", "distance", "relative_v"}]
        """
        if not satellites or not debris:
            return []

        # 1. Build KD-Tree for debris (large set)
        debris_positions = np.array([d['r'] for d in debris])
        tree = cKDTree(debris_positions)

        # 2. Query tree for each satellite
        sat_positions = np.array([s['r'] for s in satellites])
        
        # indices is a list of lists: for each sat, which debris are within radius_km
        indices = tree.query_ball_point(sat_positions, radius_km)

        results = []
        for i, debris_matches in enumerate(indices):
            sat = satellites[i]
            for deb_idx in debris_matches:
                deb = debris[deb_idx]
                
                # Calculate precise distance and relative velocity
                diff_r = sat['r'] - deb['r']
                dist = np.linalg.norm(diff_r)
                
                # Relative velocity vector
                diff_v = sat['v'] - deb['v']
                
                results.append({
                    "satelliteId": sat['id'],
                    "debrisId": deb['id'],
                    "distance": float(dist),
                    "relative_v": diff_v.tolist(),
                    "miss_distance": float(dist) # Alias for spec
                })

        return results

    def estimate_tca(self, sat_state: Dict, deb_state: Dict) -> float:
        """
        Linear approximation of Time of Closest Approach (TCA) in seconds.
        TCA = - (r ⋅ v) / |v|^2
        """
        r = sat_state['r'] - deb_state['r']
        v = sat_state['v'] - deb_state['v']
        
        v_mag_sq = np.dot(v, v)
        if v_mag_sq < 1e-9:
            return 0.0
            
        tca_seconds = -np.dot(r, v) / v_mag_sq
        return max(0.0, float(tca_seconds))
