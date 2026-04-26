"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — conjunction_service.py
 Conjunction Detection Coordination
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

from typing import List, Dict
from ..models import Satellite, Debris, CDM
from ..core.screening import ConjunctionScreener
from datetime import datetime, timedelta

class ConjunctionService:
    """
    Orchestrates collision screening between fleet and space junk.
    """

    def __init__(self):
        self.screener = ConjunctionScreener(critical_threshold_km=0.1)
        self.active_cdms: List[CDM] = []

    def screen_fleet(self, satellites: List[Satellite], debris: List[Debris], current_time: datetime):
        """
        Runs the KD-Tree screener and updates the active CDM list.
        """
        # Prepare data for screener
        sat_data = [{"id": s.id, "r": s.r.to_np(), "v": s.v.to_np()} for s in satellites]
        deb_data = [{"id": d.id, "r": d.r.to_np(), "v": d.v.to_np()} for d in debris]

        # Find proximity matches within 5km (advisory limit)
        matches = self.screener.find_conjunctions(sat_data, deb_data, radius_km=5.0)

        new_cdms = []
        for m in matches:
            # Simple TCA estimate (tca_seconds_from_now)
            sat_match = next(s for s in sat_data if s['id'] == m['satelliteId'])
            deb_match = next(d for d in deb_data if d['id'] == m['debrisId'])
            tca_offset = self.screener.estimate_tca(sat_match, deb_match)
            
            tca_dt = current_time + timedelta(seconds=tca_offset)
            
            # Probability heuristic (higher risk as distance shrinks)
            dist = m['distance']
            prob = 0.000001
            if dist < 0.1: prob = 0.05
            elif dist < 1.0: prob = 0.001

            new_cdms.append(CDM(
                satelliteId=m['satelliteId'],
                debrisId=m['debrisId'],
                tca=tca_dt,
                missDistance=dist,
                probability=prob
            ))

        self.active_cdms = new_cdms
        return self.active_cdms

    def get_critical_cdms(self) -> List[CDM]:
        """Returns CDMs with miss distance < 100m."""
        return [c for c in self.active_cdms if c.missDistance < 0.1]
