"""
TLE handler for fetching and parsing Two-Line Element satellite data from Celestrak.
"""

import httpx
from skyfield.api import load, EarthSatellite
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("TLE-Handler")

CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"

# Popular satellite groups for space nerds
SATELLITE_GROUPS = {
    "space-stations": "Space Stations",
    "starlink": "Starlink",
    "gps": "GPS Operational",
    "glonass": "GLONASS Operational",
    "galileo": "Galileo",
    "iridium": "Iridium",
    "noaa": "NOAA",
    "goes": "GOES",
    "resource": "Earth Resources",
    "scientific": "Scientific",
}

async def fetch_tle_group(group: str) -> List[str]:
    """
    Fetch TLE data for a satellite group from Celestrak.
    
    Args:
        group: Group identifier (e.g., 'space-stations', 'starlink')
    
    Returns:
        List of TLE lines (3 lines per satellite: name, line1, line2)
    """
    if group not in SATELLITE_GROUPS:
        raise ValueError(f"Unknown satellite group: {group}")
    
    params = {"GROUP": group, "FORMAT": "tle"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(CELESTRAK_BASE_URL, params=params)
            response.raise_for_status()
            tle_data = response.text
            
            # Parse into 3-line groups (name, line1, line2)
            lines = tle_data.strip().split('\n')
            tles = []
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    tles.append('\n'.join(lines[i:i+3]))
            
            logger.info(f"Fetched {len(tles)} TLEs from group '{group}'")
            return tles
            
    except Exception as e:
        logger.error(f"Failed to fetch TLEs for group '{group}': {e}")
        raise

async def fetch_tle_by_norad_id(norad_id: str) -> Optional[str]:
    """
    Fetch TLE data for a specific satellite by NORAD ID.
    
    Args:
        norad_id: NORAD catalog ID (e.g., '25544' for ISS)
    
    Returns:
        TLE data (3 lines: name, line1, line2) or None if not found
    """
    params = {"CATNR": norad_id, "FORMAT": "tle"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(CELESTRAK_BASE_URL, params=params)
            response.raise_for_status()
            tle_data = response.text.strip()
            
            if not tle_data or len(tle_data.split('\n')) < 3:
                return None
                
            logger.info(f"Fetched TLE for NORAD ID {norad_id}")
            return tle_data
            
    except Exception as e:
        logger.error(f"Failed to fetch TLE for NORAD ID {norad_id}: {e}")
        return None

def tle_to_state_vector(tle: str, timestamp: float) -> Dict:
    """
    Convert TLE to state vector (position, velocity) using skyfield.
    
    Args:
        tle: TLE data (3 lines: name, line1, line2)
        timestamp: Unix timestamp
    
    Returns:
        Dictionary with position (km), velocity (km/s), and orbital elements
    """
    lines = tle.strip().split('\n')
    if len(lines) < 2:
        raise ValueError("Invalid TLE format")
    
    # skyfield expects line1 and line2 (no name line)
    line1 = lines[0] if len(lines) == 2 else lines[1]
    line2 = lines[1] if len(lines) == 2 else lines[2]
    
    satellite = EarthSatellite(line1, line2)
    
    from skyfield.api import load
    ts = load.timescale()
    t = ts.utc(timestamp)
    
    # Get position and velocity in ICRF (inertial)
    position = satellite.at(t)
    
    # Convert to km and km/s
    r_km = position.position.km
    v_km_per_s = position.velocity.km_per_s
    
    # Calculate orbital elements
    # Semi-major axis from mean motion
    mean_motion = float(line1[50:63])  # rev/day
    a_km = (398600.4418 / (mean_motion * 2 * 3.14159265359 / 86400)**2)**(1/3)
    
    # Eccentricity
    e = float("0." + line1[26:33])
    
    # Inclination (degrees)
    i_deg = float(line2[8:16])
    
    # RAAN (degrees)
    raan_deg = float(line2[17:25])
    
    # Argument of perigee (degrees)
    aop_deg = float(line2[34:42])
    
    # Mean anomaly (degrees)
    ma_deg = float(line2[43:51])
    
    return {
        "r": [float(r_km[0]), float(r_km[1]), float(r_km[2])],
        "v": [float(v_km_per_s[0]), float(v_km_per_s[1]), float(v_km_per_s[2])],
        "orbital_elements": {
            "semi_major_axis_km": a_km,
            "eccentricity": e,
            "inclination_deg": i_deg,
            "raan_deg": raan_deg,
            "argument_of_perigee_deg": aop_deg,
            "mean_anomaly_deg": ma_deg,
            "mean_motion_rev_per_day": mean_motion,
            "period_minutes": (2 * 3.14159265359 / (mean_motion * 2 * 3.14159265359 / 86400)) / 60,
        }
    }

def get_satellite_name(tle: str) -> str:
    """Extract satellite name from TLE."""
    lines = tle.strip().split('\n')
    if len(lines) >= 3:
        return lines[0].strip()
    elif len(lines) == 2:
        # Try to extract from line1
        return lines[0][0:24].strip()
    return "Unknown"

def get_satellite_groups() -> Dict[str, str]:
    """Get available satellite groups."""
    return SATELLITE_GROUPS
