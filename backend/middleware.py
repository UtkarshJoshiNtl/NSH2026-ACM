"""
backend/middleware.py — Authentication Middleware
=================================================
FastAPI middleware for API key authentication.
"""

from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db, APIKey, User
from backend.auth import verify_api_key, hash_api_key

# API key header extraction
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: Optional[str] = Security(api_key_header), db: Session = Depends(get_db)
) -> APIKey:
    """
    Verify API key and return the API key record.
    Raises 401 if authentication fails.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include X-API-Key header.",
        )

    # Hash the provided key and look it up in database
    key_hash = hash_api_key(api_key)

    # Look up API key in database
    api_key_record = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
        .first()
    )

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key.",
        )

    # Check if key is expired
    from datetime import datetime, timezone

    if api_key_record.expires_at and api_key_record.expires_at < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired.",
        )

    # Update last used timestamp
    api_key_record.last_used = datetime.now(timezone.utc)
    db.commit()

    return api_key_record


async def get_current_user(api_key: APIKey = Depends(get_api_key)) -> dict:
    """
    Get current user from API key.
    Returns user information for rate limiting and context.
    """
    from sqlalchemy.orm import Session
    from backend.database import get_db

    # Get user from database to get tier
    db: Session = next(get_db())
    try:
        user = db.query(User).filter(User.id == api_key.user_id).first()
        tier = user.tier if user else "free"
    finally:
        db.close()

    return {"user_id": api_key.user_id, "api_key_id": api_key.id, "tier": tier}


# Optional authentication - doesn't raise error if no key provided
async def optional_api_key(
    api_key: Optional[str] = Security(api_key_header), db: Session = Depends(get_db)
) -> Optional[APIKey]:
    """
    Optional API key authentication.
    Returns None if no key provided, raises 401 if key is invalid.
    """
    if not api_key:
        return None

    key_hash = hash_api_key(api_key)
    api_key_record = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
        .first()
    )

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key_record
