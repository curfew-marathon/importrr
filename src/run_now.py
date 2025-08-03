#!/usr/bin/env python3
"""
Manual run script for importrr.
Use this to run the import process immediately without waiting for the scheduler.
"""

import sys
import os

# Add the current directory to Python path so we can import launch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launch import main_process

if __name__ == '__main__':
    print("Running importrr manually...")
    try:
        main_process()
        print("Manual run completed successfully!")
    except Exception as e:
        print(f"Manual run failed: {e}")
        sys.exit(1)
