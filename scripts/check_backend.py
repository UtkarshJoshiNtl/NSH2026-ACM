
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.core.accelerator import backend_info

def check():
    info = backend_info()
    print("Backend Info:")
    for k, v in info.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    check()
