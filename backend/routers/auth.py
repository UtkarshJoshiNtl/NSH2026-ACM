"""
backend/routers/auth.py — Authentication Endpoints
==================================================
User registration, login, and API key management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.database import get_db, User, APIKey
from backend.auth import hash_password, verify_password, generate_api_key, hash_api_key
from backend.config import settings

router = APIRouter()


# Request/Response Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class APIKeyCreate(BaseModel):
    name: str


class UserResponse(BaseModel):
    id: str
    email: str
    tier: str
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        tier="free",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=dict)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login and return user info (JWT can be added later)."""
    # Find user
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive"
        )

    return {"user_id": user.id, "email": user.email, "tier": user.tier}


@router.post(
    "/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    key_data: APIKeyCreate,
    user_id: str,  # In real implementation, get from JWT
    db: Session = Depends(get_db),
):
    """Create a new API key for the user."""
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    # Create API key record
    new_api_key = APIKey(
        key_hash=key_hash,
        user_id=user.id,
        name=key_data.name,
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),  # 1 year expiry
    )
    db.add(new_api_key)
    db.commit()
    db.refresh(new_api_key)

    # Return the actual key (only shown once)
    return APIKeyResponse(
        id=new_api_key.id,
        name=new_api_key.name,
        key=api_key,  # Return raw key (only on creation)
        created_at=new_api_key.created_at,
        expires_at=new_api_key.expires_at,
    )


@router.get("/api-keys", response_model=list)
async def list_api_keys(user_id: str, db: Session = Depends(get_db)):
    """List all API keys for the user."""
    api_keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
    return [
        {
            "id": key.id,
            "name": key.name,
            "created_at": key.created_at,
            "expires_at": key.expires_at,
            "last_used": key.last_used,
            "is_active": key.is_active,
        }
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(key_id: str, user_id: str, db: Session = Depends(get_db)):
    """Delete an API key."""
    api_key = (
        db.query(APIKey).filter(APIKey.id == key_id, APIKey.user_id == user_id).first()
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    db.delete(api_key)
    db.commit()

    return None
