"""
Derf PQ Messenger Main Entrypoint (PyQt6 High-End Premium UI on Desktop, Toga on Android/Mobile).
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Derf import _single, _load_pq
import Derf

def is_android_device():
    """Fail-proof detection for Android platform (Chaquopy / BeeWare / Kivy)."""
    if 'ANDROID_DATA' in os.environ or 'ANDROID_ROOT' in os.environ or 'ANDROID_ARGUMENT' in os.environ or 'PYTHON_SERVICE_ARGUMENT' in os.environ:
        return True
    if hasattr(sys, 'getandroidapilevel') or sys.platform == 'android':
        return True
    if 'CHAQUOPY' in os.environ or 'org.beeware' in os.environ.get('PYTHONHOME', ''):
        return True
    try:
        import java.lang
        return True
    except ImportError:
        pass
    return False

def main():
    profile_name = "default"
    for arg in sys.argv[1:]:
        if arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]

    if not _single(profile_name):
        print(f"⚠️ Another instance of Derf ({profile_name}) is already running.")
        sys.exit(1)

    try:
        Derf.PQ_KEM = _load_pq()
    except Exception as e:
        print(f"FATAL: Post-Quantum backend failed to initialize: {e}")
        sys.exit(1)

    # Check platform
    if not is_android_device():
        try:
            from derf_qt_ui import launch_pyqt_app
            launch_pyqt_app(profile_name)
            return
        except (ImportError, ModuleNotFoundError) as e:
            print(f"PyQt6 not available ({e}), falling back to Mobile UI...")

    # Native Android / Mobile UI
    from derf_mobile_ui import launch_mobile_app
    launch_mobile_app(profile_name)

if __name__ == '__main__':
    main()
