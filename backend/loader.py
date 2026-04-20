import json
import os
import logging

logger = logging.getLogger("Astrosis-Backend")


def load_initial_state_from_disk(state_mgr):
    """
    Load initial satellite and debris state from JSON files if they exist.
    If files are missing, log a warning and continue with empty state.

    Parameters
    ----------
    state_mgr : StateManager
        The state manager instance to load data into
    """
    sats_path = "data/initial_satellites.json"
    debris_path = "data/initial_debris.json"

    sats_loaded = False
    debris_loaded = False

    if os.path.exists(sats_path):
        try:
            with open(sats_path, "r") as f:
                sats = json.load(f)
            state_mgr.load_initial_state(sats, [])
            sats_loaded = True
            logger.info(f"Loaded {len(sats)} satellites from {sats_path}")
        except Exception as e:
            logger.error(f"Failed to load satellites from {sats_path}: {e}")
    else:
        logger.warning(
            f"Satellites file not found: {sats_path} - starting with empty satellite state"
        )

    if os.path.exists(debris_path):
        try:
            with open(debris_path, "r") as f:
                debris = json.load(f)
            if sats_loaded:
                # If satellites were already loaded, we need to load debris separately
                state_mgr.load_initial_state([], debris)
            else:
                # If no satellites were loaded, load debris with empty satellite list
                state_mgr.load_initial_state([], debris)
            debris_loaded = True
            logger.info(f"Loaded {len(debris)} debris objects from {debris_path}")
        except Exception as e:
            logger.error(f"Failed to load debris from {debris_path}: {e}")
    else:
        logger.warning(
            f"Debris file not found: {debris_path} - starting with empty debris state"
        )

    if not sats_loaded and not debris_loaded:
        logger.info("Starting with empty state - no initial data files found")
