import sys
import os

print(f"DEBUG: __file__ = {__file__}")
print(f"DEBUG: dirname(__file__) = {os.path.dirname(__file__)}")

mock_path = os.path.join(
    os.path.dirname(__file__),
    'core'
)
print(f"DEBUG: mock_path = {mock_path}")
print(f"DEBUG: mock_path exists: {os.path.exists(mock_path)}")
if os.path.exists(mock_path):
    print(f"DEBUG: contents of mock_path: {os.listdir(mock_path)}")

sys.path.insert(0, mock_path)
try:
    import mock_physics_engine
    print("DEBUG: SUCCESS: import mock_physics_engine")
except ImportError as e:
    print(f"DEBUG: FAILED: import mock_physics_engine: {e}")
