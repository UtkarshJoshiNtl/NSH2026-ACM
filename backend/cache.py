"""
backend/cache.py — Redis Caching and Rate Limiting
===================================================
Redis client for caching propagation results and rate limiting API requests.
"""

import json
import redis
from typing import Optional, Any
from datetime import timedelta

from backend.config import settings


class RedisCache:
    """Redis client wrapper for caching and rate limiting."""
    
    def __init__(self):
        try:
            self.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
            self.available = True
        except Exception as e:
            print(f"Warning: Redis not available - {e}")
            self.client = None
            self.available = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self.available:
            return None
        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception:
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with optional TTL."""
        if not self.available:
            return False
        try:
            ttl = ttl or settings.REDIS_CACHE_TTL
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.available:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False
    
    def increment(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment a counter (for rate limiting)."""
        if not self.available:
            return 0
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            if ttl:
                pipe.expire(key, ttl)
            result = pipe.execute()
            return result[0]
        except Exception:
            return 0
    
    def check_rate_limit(self, identifier: str, limit: int, window: int = 60) -> tuple[bool, int]:
        """
        Check if identifier is within rate limit.
        Returns (allowed, remaining_requests).
        """
        if not self.available:
            return True, limit  # Allow all if Redis unavailable
        
        key = f"rate_limit:{identifier}"
        current = self.increment(key, window)
        remaining = max(0, limit - current)
        return current <= limit, remaining


# Global Redis client instance
cache = RedisCache()
