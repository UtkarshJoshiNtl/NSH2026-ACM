"""
backend/core/ground_station.py — Ground Station Utilities
========================================================
ECI to geodetic coordinate conversion and ground station management.
"""

import math
import numpy as np
import csv
from typing import List, Tuple

# Earth parameters
MU = 398600.4418  # km³/s²
RE = 6378.137     # km
OMEGA_E = 7.2921159e-5  # Earth rotation rate (rad/s)


def eci_to_geodetic(r: List[float], time_s: float = 0.0) -> Tuple[float, float, float]:
    """
    Convert ECI position to geodetic coordinates (lat, lon, alt).
    
    Args:
        r: ECI position vector [x, y, z] in km
        time_s: Time in seconds (for Earth rotation)
    
    Returns:
        (latitude, longitude, altitude) in degrees and km
    """
    x, y, z = r
    
    # Account for Earth rotation
    theta = OMEGA_E * time_s
    x_rot = x * math.cos(theta) + y * math.sin(theta)
    y_rot = -x * math.sin(theta) + y * math.cos(theta)
    
    # Convert to geodetic
    r_mag = math.sqrt(x_rot**2 + y_rot**2 + z**2)
    
    # Longitude
    lon = math.atan2(y_rot, x_rot) * 180.0 / math.pi
    
    # Latitude (spherical approximation)
    lat = math.asin(z / r_mag) * 180.0 / math.pi
    
    # Altitude
    alt = r_mag - RE
    
    return lat, lon, alt


def vectorized_eci_to_geodetic(r_array: np.ndarray, time_s: float = 0.0) -> np.ndarray:
    """
    Vectorized ECI to geodetic conversion for numpy arrays.
    
    Args:
        r_array: Nx3 array of ECI positions
        time_s: Time in seconds
    
    Returns:
        Nx3 array of (lat, lon, alt) in degrees and km
    """
    theta = OMEGA_E * time_s
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    
    # Rotate for Earth rotation
    x_rot = r_array[:, 0] * cos_theta + r_array[:, 1] * sin_theta
    y_rot = -r_array[:, 0] * sin_theta + r_array[:, 1] * cos_theta
    z = r_array[:, 2]
    
    # Convert to geodetic
    r_mag = np.sqrt(x_rot**2 + y_rot**2 + z**2)
    lon = np.arctan2(y_rot, x_rot) * 180.0 / math.pi
    lat = np.arcsin(z / r_mag) * 180.0 / math.pi
    alt = r_mag - RE
    
    return np.column_stack([lat, lon, alt])


def get_all_stations() -> List[dict]:
    """
    Load ground stations from CSV file.
    
    Returns:
        List of ground station dictionaries
    """
    stations = []
    try:
        with open("data/ground_stations.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stations.append({
                    "id": row["Station_ID"],
                    "name": row["Station_Name"],
                    "lat": float(row["Latitude"]),
                    "lon": float(row["Longitude"]),
                    "elevation_m": float(row["Elevation_m"]),
                    "min_elevation_deg": float(row["Min_Elevation_Angle_deg"])
                })
    except FileNotFoundError:
        pass
    return stations
