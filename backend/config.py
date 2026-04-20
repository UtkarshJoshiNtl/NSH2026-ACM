from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for Astrosis orbital mechanics engine."""
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # Database Configuration (PostgreSQL)
    DATABASE_URL: str = "sqlite:///./astrosis.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis Configuration (Caching & Rate Limiting)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600
    
    # API Rate Limiting (requests per minute)
    RATE_LIMIT_FREE: int = 100
    RATE_LIMIT_PRO: int = 1000
    RATE_LIMIT_ENTERPRISE: int = 10000
    
    # TLE Data Source
    CELESTRAK_API_URL: str = "https://celestrak.org/NORAD/elements/gp.php"
    TLE_REFRESH_INTERVAL_HOURS: int = 6
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY_LENGTH: int = 32
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Physics Engine
    PHYSICS_ENGINE_PATH: str = "./backend/cpp/build/physics_engine.so"
    
    # Propulsion and physics constants
    ISP: float = 300.0
    G0: float = 0.00980665
    DRY_MASS_KG: float = 500.0
    INITIAL_FUEL_KG: float = 50.0
    
    # Operational constraints
    COOLDOWN_S: float = 600.0
    MAX_DV_KMS: float = 0.015
    EOL_FUEL_PCT: float = 0.05
    SLOT_BOX_KM: float = 10.0
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()
