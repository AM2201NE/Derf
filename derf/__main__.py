"""
Derf PQ Messenger Package Main Entrypoint for BeeWare Briefcase.
"""
import sys
import os

# Adjust path to find core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

if __name__ == "__main__":
    main()
