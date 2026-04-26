"""
═══════════════════════════════════════════════════════════════════════════
 ACM SERVICE — comms_service.py
 Ground Station Line-of-Sight (LOS)
 National Space Hackathon 2026
═══════════════════════════════════════════════════════════════════════════
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from ..core.physics import latlon_to_eci, RE

class CommsService:
    """
    Handles communication constraints between ground and fleet.
    """

    def __init__(self, ground_stations_path: str):
        self.stations = self._load_stations(ground_stations_path)

    def _load_stations(self, path: str) -> List[Dict]:
        try:
            df = pd.read_csv(path)
            stations = []
            for _, row in df.iterrows():
                # Use specification-compliant column names
                lat = row.get('Latitude', row.get('latitude_deg', 0.0))
                lon = row.get('Longitude', row.get('longitude_deg', 0.0))
                alt = row.get('Elevation_m', row.get('elevation_m', 0.0)) / 1000.0 # to km
                mask = row.get('Min_Elevation_Angle_deg', row.get('min_elevation_angle_deg', 5.0))
                
                stations.append({
                    "id": row.get('Station_ID', row.get('name', 'GS-UNKNOWN')),
                    "name": row.get('Station_Name', row.get('name', 'Unknown')),
                    "lat": float(lat),
                    "lon": float(lon),
                    "alt": float(alt),
                    "min_el": float(mask)
                })
            return stations
        except Exception as e:
            print(f"[CommsService] Warning: Failed to load stations from {path}: {e}")
            return []

    def has_los(self, sat_r_eci: np.ndarray, t: datetime) -> bool:
        """
        Check if the satellite has line-of-sight to ANY ground station at time t.
        Recalculates GS ECI position based on Earth rotation.
        """
        if not self.stations:
            return True # Fallback if no stations loaded

        sat_mag = np.linalg.norm(sat_r_eci)
        if sat_mag < RE: return False

        for gs in self.stations:
            # ── Dynamic GS ECI Position ─────────────────────────────────────
            # Transform from fixed Lat/Lon/Alt to simulation ECI frame
            gs_r_eci = latlon_to_eci(gs['lat'], gs['lon'], gs['alt'], t)
            
            # Vector from Ground Station to Satellite
            rho = sat_r_eci - gs_r_eci
            rho_mag = np.linalg.norm(rho)
            
            # Unit vectors
            u_gs = gs_r_eci / np.linalg.norm(gs_r_eci)
            u_rho = rho / rho_mag
            
            # Elevation Angle = 90 - angle between station zenith and rho
            # cos(theta) = u_gs . u_rho
            cos_zenith = np.dot(u_gs, u_rho)
            elev_angle = 90.0 - np.degrees(np.arccos(np.clip(cos_zenith, -1.0, 1.0)))
            
            if elev_angle >= gs['min_el']:
                return True
                
        return False

