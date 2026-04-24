"""
backend/core/ground_station.py — Ground Station Utilities
========================================================
ECI to geodetic coordinate conversion and ground station management.
Enhanced with dynamic Earth rotation for accurate LOS calculations.
Migrated from AutoCM for hackathon-compliant communication constraints.
"""

import math
import numpy as np
import csv
from typing import List, Tuple, Optional
from datetime import datetime

# Earth parameters
MU = 398600.4418  # km³/s²
RE = 6378.137  # km
OMEGA_E = 7.2921159e-5  # Earth rotation rate (rad/s)
EARTH_ROT_RATE = 7.292115e-5  # rad/s (Earth's Rotation Rate)


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
                stations.append(
                    {
                        "id": row["Station_ID"],
                        "name": row["Station_Name"],
                        "lat": float(row["Latitude"]),
                        "lon": float(row["Longitude"]),
                        "elevation_m": float(row["Elevation_m"]),
                        "min_elevation_deg": float(row["Min_Elevation_Angle_deg"]),
                    }
                )
    except FileNotFoundError:
        pass
    return stations


def calculate_visibility(
    sat_eci: List[float], station: dict, time_s: float = 0.0
) -> dict:
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
    cos_el = math.sin(stn_lat) * math.sin(sat_lat_rad) + math.cos(stn_lat) * math.cos(
        sat_lat_rad
    ) * math.cos(sat_lon_rad - stn_lon)

    # Clamp to [-1, 1] to avoid numerical errors
    cos_el = max(-1.0, min(1.0, cos_el))

    elevation_angle = (
        math.acos(cos_el) - math.pi / 2
    )  # Convert to elevation from horizon
    elevation_deg = math.degrees(elevation_angle)

    # Calculate azimuth
    y = math.sin(sat_lon_rad - stn_lon)
    x = math.cos(sat_lat_rad) * math.tan(stn_lat) - math.sin(sat_lat_rad) * math.cos(
        sat_lon_rad - stn_lon
    )
    azimuth_deg = math.degrees(math.atan2(y, x))

    # Check visibility
    is_visible = elevation_deg >= station["min_elevation_deg"]

    return {
        "visible": is_visible,
        "elevation_deg": elevation_deg,
        "azimuth_deg": azimuth_deg,
        "min_elevation_deg": station["min_elevation_deg"],
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
            visible.append({**station, "visibility": vis})

    return visible


def latlon_to_eci(lat: float, lon: float, alt: float, t: Optional[datetime] = None) -> np.ndarray:
    """
    Convert Lat (deg), Lon (deg), Alt (km) to ECI (km).
    If t is provided, accounts for Earth's rotation.

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        alt: Altitude in km
        t: Datetime object for Earth rotation correction

    Returns:
        ECI position vector [x, y, z] in km
    """
    r_mag = RE + alt
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    x_ecef = r_mag * math.cos(lat_rad) * math.cos(lon_rad)
    y_ecef = r_mag * math.cos(lat_rad) * math.sin(lon_rad)
    z_ecef = r_mag * math.sin(lat_rad)

    r_ecef = np.array([x_ecef, y_ecef, z_ecef])

    return ecef_to_eci(r_ecef, t) if t else r_ecef


def ecef_to_eci(r_ecef: np.ndarray, t: datetime) -> np.ndarray:
    """
    Rotates ECEF vector to ECI frame based on time.

    Args:
        r_ecef: ECEF position vector [x, y, z] in km
        t: Datetime object

    Returns:
        ECI position vector [x, y, z] in km
    """
    gmst = get_gmst(t)
    cos_g = math.cos(gmst)
    sin_g = math.sin(gmst)

    # Rotation matrix around Z-axis
    rot = np.array([
        [cos_g, -sin_g, 0],
        [sin_g,  cos_g, 0],
        [0,      0,     1]
    ])
    return rot @ r_ecef


def get_gmst(t: datetime) -> float:
    """
    Returns Greenwich Mean Sidereal Time (GMST) in radians.
    Simplified version using J2000 epoch.

    Args:
        t: Datetime object

    Returns:
        GMST angle in radians
    """
    # Seconds since J2000 epoch (2000-01-01 12:00:00 UTC)
    epoch = datetime(2000, 1, 1, 12, 0, 0)
    # Ensure t is naive or handle timezone
    if t.tzinfo is not None:
        t = t.replace(tzinfo=None)

    dt_sec = (t - epoch).total_seconds()

    # Rotation angle (rad) = theta0 + omega * dt
    # theta0 at J2000 is approx 4.894961 rad
    theta0 = 4.894961
    return (theta0 + EARTH_ROT_RATE * dt_sec) % (2 * math.pi)


class CommsService:
    """
    Enhanced communication service with dynamic Earth rotation for accurate LOS.
    Migrated from AutoCM for hackathon-compliant blackout zone handling.
    """

    def __init__(self, ground_stations_path: Optional[str] = None):
        """
        Initialize communication service.

        Args:
            ground_stations_path: Path to ground stations CSV file
        """
        self.stations = self._load_stations(ground_stations_path) if ground_stations_path else get_all_stations()

    def _load_stations(self, path: str) -> List[dict]:
        """
        Load ground stations from CSV file with flexible column naming.

        Args:
            path: Path to CSV file

        Returns:
            List of ground station dictionaries
        """
        try:
            import pandas as pd
            df = pd.read_csv(path)
            stations = []
            for _, row in df.iterrows():
                # Use specification-compliant column names
                lat = row.get('Latitude', row.get('latitude_deg', 0.0))
                lon = row.get('Longitude', row.get('longitude_deg', 0.0))
                alt = row.get('Elevation_m', row.get('elevation_m', 0.0)) / 1000.0  # to km
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

        Args:
            sat_r_eci: Satellite ECI position [x, y, z] in km
            t: Current simulation time

        Returns:
            True if satellite has LOS to at least one ground station
        """
        if not self.stations:
            return True  # Fallback if no stations loaded

        sat_mag = np.linalg.norm(sat_r_eci)
        if sat_mag < RE:
            return False

        for gs in self.stations:
            # Dynamic GS ECI Position
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
            elev_angle = 90.0 - math.degrees(math.acos(np.clip(cos_zenith, -1.0, 1.0)))

            if elev_angle >= gs['min_el']:
                return True

        return False
