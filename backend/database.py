"""
backend/database.py — Database Models and Session Management
===========================================================
SQLAlchemy models for users, API keys, simulations, and TLE data.
"""

from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Float,
    Integer,
    Text,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import uuid

from backend.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.ENVIRONMENT == "development",
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class User(Base):
    """User account for API access."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    tier = Column(String, default="free")  # free, pro, enterprise
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    # Relationships
    api_keys = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    simulations = relationship(
        "Simulation", back_populates="user", cascade="all, delete-orphan"
    )


class APIKey(Base):
    """API key for authentication."""

    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # User-friendly name for the key
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")


class Simulation(Base):
    """Simulation context for multi-tenancy."""

    __tablename__ = "simulations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    simulation_time = Column(Float, default=0.0)
    state_data = Column(Text, nullable=True)  # JSON-serialized state
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="simulations")


class TLEData(Base):
    """TLE (Two-Line Element) satellite data."""

    __tablename__ = "tle_data"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    norad_id = Column(Integer, nullable=False, index=True)
    satellite_name = Column(String, nullable=True)
    line1 = Column(String, nullable=False)
    line2 = Column(String, nullable=False)
    epoch = Column(DateTime, nullable=True, index=True)
    source = Column(String, default="celestrak")  # celestrak, manual, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Composite index for efficient queries
    __table_args__ = (Index("idx_norad_epoch", "norad_id", "epoch"),)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
