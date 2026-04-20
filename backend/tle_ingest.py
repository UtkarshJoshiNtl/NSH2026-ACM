"""
backend/tle_ingest.py — TLE Data Ingestion from Celestrak
==========================================================
Service for fetching and storing TLE (Two-Line Element) data from Celestrak.
"""

import httpx
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from backend.database import SessionLocal, TLEData
from backend.config import settings

logger = logging.getLogger("Astrosis-TLE")


class TLEIngestor:
    """Service for ingesting TLE data from Celestrak."""
    
    def __init__(self):
        self.api_url = settings.CELESTRAK_API_URL
    
    async def fetch_tle_data(self, satellite_id: Optional[str] = None) -> List[str]:
        """
        Fetch TLE data from Celestrak.
        If satellite_id is provided, fetch specific satellite data.
        Otherwise, fetch all active satellites.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if satellite_id:
                    params = {"FORMAT": "TLE", "ID": satellite_id}
                else:
                    params = {"FORMAT": "TLE"}
                
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                
                # Parse TLE data (3 lines per satellite: name, line1, line2)
                lines = response.text.strip().split('\n')
                return lines
        except Exception as e:
            logger.error(f"Failed to fetch TLE data: {e}")
            return []
    
    def parse_tle_lines(self, lines: List[str]) -> List[dict]:
        """Parse TLE lines into structured data."""
        tle_entries = []
        
        i = 0
        while i < len(lines):
            # TLE format: name (line 0), line1, line2
            if i + 2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()
                
                # Extract NORAD ID from line 1 (columns 2-6)
                norad_id = None
                if len(line1) > 6:
                    try:
                        norad_id = int(line1[2:7])
                    except ValueError:
                        pass
                
                # Extract epoch from line 1 (columns 18-32)
                epoch = None
                if len(line1) > 32:
                    try:
                        year_str = line1[18:20]
                        day_str = line1[20:32]
                        year = 2000 + int(year_str) if int(year_str) < 57 else 1900 + int(year_str)
                        day_of_year = float(day_str)
                        epoch = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
                    except (ValueError, IndexError):
                        pass
                
                tle_entries.append({
                    "norad_id": norad_id,
                    "satellite_name": name,
                    "line1": line1,
                    "line2": line2,
                    "epoch": epoch
                })
                
                i += 3
            else:
                i += 1
        
        return tle_entries
    
    def store_tle_data(self, tle_entries: List[dict]) -> int:
        """Store TLE data in database."""
        db = SessionLocal()
        stored_count = 0
        
        try:
            for entry in tle_entries:
                if not entry["norad_id"]:
                    continue
                
                # Check if TLE already exists for this satellite with same epoch
                existing = db.query(TLEData).filter(
                    TLEData.norad_id == entry["norad_id"],
                    TLEData.epoch == entry["epoch"]
                ).first()
                
                if existing:
                    continue
                
                # Create new TLE record
                tle_data = TLEData(
                    norad_id=entry["norad_id"],
                    satellite_name=entry.get("satellite_name"),
                    line1=entry["line1"],
                    line2=entry["line2"],
                    epoch=entry["epoch"],
                    source="celestrak"
                )
                db.add(tle_data)
                stored_count += 1
            
            db.commit()
            logger.info(f"Stored {stored_count} new TLE entries")
            return stored_count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store TLE data: {e}")
            return 0
        finally:
            db.close()
    
    async def ingest(self, satellite_id: Optional[str] = None) -> int:
        """Fetch and store TLE data."""
        lines = await self.fetch_tle_data(satellite_id)
        if not lines:
            return 0
        
        tle_entries = self.parse_tle_lines(lines)
        if not tle_entries:
            return 0
        
        return self.store_tle_data(tle_entries)


# Global TLE ingestor instance
tle_ingestor = TLEIngestor()
