# !/usr/bin/env python3
# start_engine.py
"""
India AQI Alert Engine - Start Script
Starts the engine with scheduler for continuous monitoring
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scheduler import main

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════╗
    ║   India AQI Alert Engine                     ║
    ║   Continuous Air Quality Monitoring          ║
    ╚══════════════════════════════════════════════╝

    Starting engine...
    Press Ctrl+C to stop
    """)

    try:
        option = input("Select the source of AQI Data:\n1. OpenWeather\nEnter the option number (e.g. 1,2):\n")
        main(int(option))
    except KeyboardInterrupt:
        print("\n\n Engine stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n Engine failed: {e}")
        sys.exit(1)
