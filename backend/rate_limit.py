"""
backend/rate_limit.py — Rate Limiting Middleware
================================================
FastAPI middleware for API rate limiting using Redis.
"""

from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Callable
from backend.cache import cache
from backend.config import settings


async def rate_limit_middleware(request: Request, call_next: Callable):
    """
    Rate limiting middleware using Redis.
    Checks rate limits based on user tier from authentication context.
    """
    # Skip rate limiting for health endpoint
    if request.url.path == "/api/health":
        return await call_next(request)
    
    # Skip rate limiting for auth endpoints
    if request.url.path.startswith("/api/auth"):
        return await call_next(request)
    
    # Get user info from request state (set by auth middleware)
    user_info = getattr(request.state, "user", None)
    
    if user_info:
        user_tier = user_info.get("tier", "free")
        user_id = user_info.get("user_id", "unknown")
    else:
        # For unauthenticated requests, use IP as identifier
        user_tier = "free"
        user_id = request.client.host if request.client else "unknown"
    
    # Get rate limit based on tier
    tier_limits = {
        "free": settings.RATE_LIMIT_FREE,
        "pro": settings.RATE_LIMIT_PRO,
        "enterprise": settings.RATE_LIMIT_ENTERPRISE
    }
    limit = tier_limits.get(user_tier, settings.RATE_LIMIT_FREE)
    
    # Check rate limit
    allowed, remaining = cache.check_rate_limit(user_id, limit, window=60)
    
    # Add rate limit headers to response
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    if not allowed:
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window": "60 seconds"
            }
        )
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["Retry-After"] = "60"
    
    return response
