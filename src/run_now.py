#!/usr/bin/env python3
"""
Manual run script for importrr.
This is just a convenience script that calls launch.py directly.
"""

import subprocess
import sys
import os

if __name__ == '__main__':
    print("Running importrr manually via launch.py...")
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    launch_script = os.path.join(script_dir, 'launch.py')
    
    try:
        # Run launch.py directly (without SCHEDULER_MODE, so it runs once)
        result = subprocess.run([sys.executable, launch_script], 
                              env={**os.environ, 'SCHEDULER_MODE': 'false'})
        if result.returncode == 0:
            print("Manual run completed successfully!")
        else:
            print(f"Manual run failed with exit code: {result.returncode}")
            sys.exit(result.returncode)
    except Exception as e:
        print(f"Failed to run launch.py: {e}")
        sys.exit(1)
