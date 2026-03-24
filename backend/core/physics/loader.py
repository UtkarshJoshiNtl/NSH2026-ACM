"""
Handles loading of the compiled pybind11 physics_engine module.
"""

import sys
import os
import logging

logger = logging.getLogger(__name__)

def load_physics_engine():
    _BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cpp", "build")
    _BUILD_DIR = os.path.abspath(_BUILD_DIR)
    _ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    for _path in [_BUILD_DIR, _ROOT_DIR]:
        if _path not in sys.path:
            sys.path.insert(0, _path)

    try:
        import physics_engine as _physics
        logger.info("physics_engine C++ module loaded successfully")
        return _physics
    except ImportError as exc:
        logger.warning("physics_engine C++ module not found; using Python fallback")
        return None

physics = load_physics_engine()
