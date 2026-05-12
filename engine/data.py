"""
astrosis/data.py — TLE Data Ingestion from Celestrak
==========================================================
Service for fetching and caching TLE (Two-Line Element) data locally.
"""

import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
import os
import json

logger = logging.getLogger("Astrosis-TLE")

# Cache dir is now .cache in the package root
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_CACHE_DIR = os.path.join(ROOT_DIR, ".cache", "tle")
CELESTRAK_API_URL = "https://celestrak.org/NORAD/elements/gp.php"

# TLE epoch year cutoff: years < 57 are 2000+, years >= 57 are 1900+
# This is a standard TLE convention for two-digit years
EPOCH_YEAR_CUTOFF = 57


class TLEIngestor:
    """Service for ingesting TLE data from Celestrak and caching locally."""

    def __init__(self, cache_dir: str = LOCAL_CACHE_DIR):
        self.api_url = CELESTRAK_API_URL
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, satellite_id: Optional[str] = None) -> str:
        if satellite_id:
            return os.path.join(self.cache_dir, f"{satellite_id}.txt")
        return os.path.join(self.cache_dir, "active.txt")

    def _is_cache_valid(self, cache_path: str, max_age_hours: int = 24) -> bool:
        if not os.path.exists(cache_path):
            return False
        mtime = os.path.getmtime(cache_path)
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age <= timedelta(hours=max_age_hours)

    def fetch_tle_data(self, satellite_id: Optional[str] = None, force_refresh: bool = False) -> List[str]:
        """
        Fetch TLE data from Celestrak synchronously.
        """
        cache_path = self._get_cache_path(satellite_id)
        if not force_refresh and self._is_cache_valid(cache_path):
            logger.info(f"Loaded TLEs from local cache: {cache_path}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read().strip().split("\n")

        try:
            logger.info("Fetching fresh TLEs from Celestrak...")
            with httpx.Client(timeout=30.0) as client:
                params = {"FORMAT": "TLE"}
                if satellite_id:
                    params["CATNR"] = satellite_id
                else:
                    params["GROUP"] = "active"

                response = client.get(self.api_url, params=params)
                response.raise_for_status()

                text_data = response.text.strip()
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(text_data)

                return text_data.split("\n")
        except Exception as e:
            logger.error(f"Failed to fetch TLE data: {e}")
            # Fallback to cache if available
            if os.path.exists(cache_path):
                logger.warning("Using stale cache due to fetch failure.")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return f.read().strip().split("\n")
            return []

    @staticmethod
    def _tle_checksum_valid(line: str) -> bool:
        """
        Validate the TLE line checksum (last character of each TLE data line).
        The checksum is the modulo-10 sum of all digits in the line (dashes count as 1).
        """
        if len(line) < 69:
            return False
        checksum = 0
        for ch in line[:68]:
            if ch.isdigit():
                checksum += int(ch)
            elif ch == '-':
                checksum += 1
        return checksum % 10 == int(line[68])

    def parse_tle_lines(self, lines: List[str]) -> List[dict]:
        """Parse TLE lines into structured data, skipping records with invalid checksums."""
        tle_entries = []
        i = 0
        while i < len(lines):
            if i + 2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()

                # --- Validate checksums before accepting the record ---
                if not (self._tle_checksum_valid(line1) and self._tle_checksum_valid(line2)):
                    logger.warning(f"Skipping TLE '{name}': invalid checksum on one or both element lines.")
                    i += 3
                    continue

                # --- Validate line identifiers ---
                if not (line1.startswith('1 ') and line2.startswith('2 ')):
                    logger.warning(f"Skipping TLE block at index {i}: lines do not begin with '1 '/'2 '.")
                    i += 1
                    continue

                norad_id = None
                if len(line1) > 6:
                    try:
                        norad_id = int(line1[2:7])
                    except ValueError:
                        pass

                epoch = None
                if len(line1) > 32:
                    try:
                        year_str = line1[18:20]
                        day_str = line1[20:32]
                        year = 2000 + int(year_str) if int(year_str) < EPOCH_YEAR_CUTOFF else 1900 + int(year_str)
                        day_of_year = float(day_str)
                        epoch = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
                    except (ValueError, IndexError):
                        pass

                tle_entries.append({
                    "norad_id": norad_id,
                    "satellite_name": name,
                    "line1": line1,
                    "line2": line2,
                    "epoch": epoch,
                })
                i += 3
            else:
                i += 1

        return tle_entries

    def get_satellites(self, satellite_id: Optional[str] = None, force_refresh: bool = False) -> List[dict]:
        """High-level function to get parsed satellite TLEs."""
        lines = self.fetch_tle_data(satellite_id, force_refresh)
        return self.parse_tle_lines(lines)


# Global default instance
tle_ingestor = TLEIngestor()
