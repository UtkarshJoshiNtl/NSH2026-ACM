import sys
import os
import inspect

# Use the same logic as engine_wrapper
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
core_path = os.path.join(root_dir, 'core')
sys.path.insert(0, core_path)

try:
    import autocm_engine
    print(f"DEBUG: run_conjunction_assessment signature: {inspect.signature(autocm_engine.run_conjunction_assessment)}")
except Exception as e:
    print(f"DEBUG: Could not get signature: {e}")
    # Try calling it with help()
    import pydoc
    print(f"DEBUG: HELP output:\n{pydoc.render_doc(autocm_engine.run_conjunction_assessment)}")
