"""
backend/tle_scheduler.py — TLE Auto-Refresh Scheduler
======================================================
Periodically refreshes TLE data from Celestrak to keep satellite orbits current.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.tle_ingest import tle_ingestor
from backend.config import settings

logger = logging.getLogger("Astrosis-TLE-Scheduler")


class TLEScheduler:
    """Scheduler for automatic TLE data refresh."""

    def __init__(self, refresh_interval_hours: Optional[int] = None):
        self.refresh_interval = (
            refresh_interval_hours or settings.TLE_REFRESH_INTERVAL_HOURS
        ) * 3600
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def refresh_tle_data(self):
        """Refresh TLE data from Celestrak."""
        try:
            logger.info(f"Starting TLE refresh at {datetime.now(timezone.utc)}")
            count = await tle_ingestor.ingest()
            logger.info(f"TLE refresh completed: {count} entries updated")
            return count
        except Exception as e:
            logger.error(f"TLE refresh failed: {e}")
            return 0

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                await self.refresh_tle_data()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            # Wait for next refresh interval
            await asyncio.sleep(self.refresh_interval)

    async def start(self):
        """Start the TLE refresh scheduler."""
        if self.running:
            logger.warning("TLE scheduler already running")
            return

        logger.info(f"Starting TLE scheduler (interval: {self.refresh_interval}s)")
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """Stop the TLE refresh scheduler."""
        if not self.running:
            return

        logger.info("Stopping TLE scheduler")
        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        logger.info("TLE scheduler stopped")

    async def refresh_now(self):
        """Trigger an immediate TLE refresh."""
        logger.info("Triggering immediate TLE refresh")
        return await self.refresh_tle_data()


# Global scheduler instance
tle_scheduler = TLEScheduler()
