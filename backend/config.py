from pydantic import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for Astrosis orbital mechanics engine."""
    
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
