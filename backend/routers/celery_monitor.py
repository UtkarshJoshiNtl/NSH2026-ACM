"""
API router for Celery task monitoring.
"""

from fastapi import APIRouter
from celery import current_app
from backend.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tasks/stats")
async def get_celery_stats():
    """Get Celery worker statistics."""
    try:
        inspect = celery_app.control.inspect()
        
        # Get registered tasks
        registered = inspect.registered()
        
        # Get active tasks
        active = inspect.active()
        
        # Get scheduled tasks
        scheduled = inspect.scheduled()
        
        # Get worker stats
        stats = inspect.stats()
        
        return {
            "workers": {
                "registered": registered,
                "active": active,
                "scheduled": scheduled,
                "stats": stats,
            },
            "status": "connected" if registered else "no_workers"
        }
    except Exception as e:
        logger.error(f"Failed to get Celery stats: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/tasks/ping")
async def ping_celery_workers():
    """Ping all Celery workers."""
    try:
        inspect = celery_app.control.inspect()
        pong = inspect.ping()
        
        return {
            "workers": pong,
            "status": "connected" if pong else "no_workers"
        }
    except Exception as e:
        logger.error(f"Failed to ping Celery workers: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/queues")
async def get_queue_info():
    """Get queue information."""
    try:
        from backend.cache import RedisCache
        
        cache = RedisCache()
        if not cache.available:
            return {"status": "redis_unavailable"}
        
        # Get queue lengths (simplified - would need Redis queue library for full implementation)
        return {
            "status": "connected",
            "queues": {
                "propagation": "monitoring_enabled",
                "conjunction": "monitoring_enabled",
                "tle": "monitoring_enabled",
            }
        }
    except Exception as e:
        logger.error(f"Failed to get queue info: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
