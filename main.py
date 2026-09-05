"""
Derf PQ Messenger Main Entrypoint (PyQt6 High-End Premium UI).
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Derf import _single, _load_pq
import Derf
from derf_qt_ui import launch_pyqt_app

def main():
    profile_name = "default"
    for arg in sys.argv[1:]:
        if arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]

    if not _single():
        print("⚠️ Another instance of Derf is already running.")
        sys.exit(1)

    try:
        Derf.PQ_KEM = _load_pq()
    except Exception as e:
        print(f"FATAL: Post-Quantum backend failed to initialize: {e}")
        sys.exit(1)

    launch_pyqt_app(profile_name)

if __name__ == '__main__':
    main()
