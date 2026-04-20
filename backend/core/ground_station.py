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


def calculate_visibility(sat_eci: List[float], station: dict, time_s: float = 0.0) -> dict:
    """
    Calculate visibility of a satellite from a ground station.
    
    Args:
        sat_eci: Satellite ECI position [x, y, z] in km
        station: Ground station dictionary with lat, lon, elevation_m, min_elevation_deg
        time_s: Time in seconds (for Earth rotation)
    
    Returns:
        Dictionary with visibility status, elevation angle, and azimuth
    """
    # Convert satellite ECI to geodetic
    sat_lat, sat_lon, sat_alt = eci_to_geodetic(sat_eci, time_s)
    
    # Station coordinates
    stn_lat = math.radians(station["lat"])
    stn_lon = math.radians(station["lon"])
    sat_lat_rad = math.radians(sat_lat)
    sat_lon_rad = math.radians(sat_lon)
    
    # Calculate elevation angle using spherical geometry
    # Elevation angle from station to satellite
    cos_el = (math.sin(stn_lat) * math.sin(sat_lat_rad) + 
              math.cos(stn_lat) * math.cos(sat_lat_rad) * math.cos(sat_lon_rad - stn_lon))
    
    # Clamp to [-1, 1] to avoid numerical errors
    cos_el = max(-1.0, min(1.0, cos_el))
    
    elevation_angle = math.acos(cos_el) - math.pi / 2  # Convert to elevation from horizon
    elevation_deg = math.degrees(elevation_angle)
    
    # Calculate azimuth
    y = math.sin(sat_lon_rad - stn_lon)
    x = math.cos(sat_lat_rad) * math.tan(stn_lat) - math.sin(sat_lat_rad) * math.cos(sat_lon_rad - stn_lon)
    azimuth_deg = math.degrees(math.atan2(y, x))
    
    # Check visibility
    is_visible = elevation_deg >= station["min_elevation_deg"]
    
    return {
        "visible": is_visible,
        "elevation_deg": elevation_deg,
        "azimuth_deg": azimuth_deg,
        "min_elevation_deg": station["min_elevation_deg"]
    }


def get_visible_stations(sat_eci: List[float], time_s: float = 0.0) -> List[dict]:
    """
    Get all ground stations that currently have visibility of a satellite.
    
    Args:
        sat_eci: Satellite ECI position [x, y, z] in km
        time_s: Time in seconds
    
    Returns:
        List of visible ground stations with visibility details
    """
    stations = get_all_stations()
    visible = []
    
    for station in stations:
        vis = calculate_visibility(sat_eci, station, time_s)
        if vis["visible"]:
            visible.append({
                **station,
                "visibility": vis
            })
    
    return visible
