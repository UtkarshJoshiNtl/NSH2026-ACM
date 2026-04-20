"""
Physical constants and thresholds for the Astrosis physics engine.
"""

from backend.config import settings

# Keep fundamental orbital constants
MU = 398600.4418  # km³/s²
RE = 6378.137  # km
J2 = 1.08263e-3

# Import configurable constants from settings
ISP = settings.ISP
G0 = settings.G0
DRY_MASS = settings.DRY_MASS_KG
INITIAL_FUEL = settings.INITIAL_FUEL_KG
MAX_DV = settings.MAX_DV_KMS
COOLDOWN_S = settings.COOLDOWN_S
