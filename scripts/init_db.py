#!/usr/bin/env python3
"""
scripts/init_db.py — Database Initialization Script
=====================================================
Initialize the PostgreSQL database with all required tables.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.database import init_db, engine
from backend.config import settings

if __name__ == "__main__":
    print(f"Initializing database with URL: {settings.DATABASE_URL}")
    print("Creating tables...")
    
    try:
        init_db()
        print("✓ Database tables created successfully")
        print("\nTables created:")
        print("  - users")
        print("  - api_keys")
        print("  - simulations")
        print("  - tle_data")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        sys.exit(1)
