import sys
import os

# Use the same logic as engine_wrapper
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
core_path = os.path.join(root_dir, 'core')
sys.path.insert(0, core_path)

try:
    import autocm_engine
    print(f"DEBUG: autocm_engine loaded from {autocm_engine.__file__}")
    print(f"DEBUG: dir(autocm_engine) = {dir(autocm_engine)}")
except ImportError as e:
    print(f"DEBUG: FAILED to import autocm_engine: {e}")
