"""
AutoCM Core Physics & Analytics Engine
"""

try:
    from .engine_wrapper import *
except Exception:
    pass

try:
    from .autonomy_logic import AutonomyManager
except Exception:
    pass

__version__ = "0.1.0"
