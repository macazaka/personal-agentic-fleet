"""
Unified App Launcher for Personal Agentic Fleet.
Starts the Local Web Dashboard and opens it in your default web browser.
Can run in console or completely in the background via pythonw.exe.
"""

import atexit
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path(__file__).resolve().parent / "data"
LOG_FILE = DATA_DIR / "fleet_app.log"
PID_FILE = DATA_DIR / "fleet.pid"

def setup_streams():
    """Configure stdout/stderr for console or headless pythonw background execution."""
    if sys.stdout is None or sys.stderr is None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _log_fp = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
            sys.stdout = _log_fp
            sys.stderr = _log_fp

            def _log_excepthook(exc_type, exc_val, exc_tb):
                import traceback
                traceback.print_exception(exc_type, exc_val, exc_tb, file=_log_fp)
                _log_fp.flush()

            sys.excepthook = _log_excepthook
            return _log_fp
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


setup_streams()

from fleet.config import VERSION
from fleet.core.lifecycle import install_lifecycle_guards, register_shutdown_callback
from fleet.core.logger import configure_logging
from fleet.core.power import power_manager
from fleet.daemon import FleetDaemon
from fleet.server import PORT, start_server
from fleet.tools.crash_reporter import install_crash_reporter


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def open_browser_delayed(url: str, delay: float = 1.0):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    no_browser = "--no-browser" in sys.argv

    # If already running, simply focus/open browser and exit
    if is_port_in_use(PORT):
        print(f"Personal Agentic Fleet is already active at http://127.0.0.1:{PORT}")
        if not no_browser:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        return

    # Write PID file for process management
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        atexit.register(lambda: PID_FILE.unlink(missing_ok=True))
    except Exception:
        pass

    # Initialize Native Robustness Subsystems (Logging, Crash Reporter, Lifecycle & Power)
    try:
        configure_logging()
        install_crash_reporter()
        install_lifecycle_guards()
        power_manager.start_monitoring()
        register_shutdown_callback(power_manager.stop_monitoring)
    except Exception as e:
        print(f"Warning: Failed to initialize all robustness lifecycle guards: {e}")

    print("=" * 65)
    print(f"     ⚡ PERSONAL AGENTIC FLEET v{VERSION} — CONTROL CENTER ⚡")
    print("=" * 65)
    print(f"Launching Local Web Dashboard at: http://127.0.0.1:{PORT}")
    print("Starting background proactive routine monitor...")
    if not no_browser:
        print("Opening your browser...")
    else:
        print("Running in background headless mode (--no-browser).")
    print("=" * 65)

    # Start browser opener if not disabled
    if not no_browser:
        threading.Thread(target=open_browser_delayed, args=(f"http://127.0.0.1:{PORT}",), daemon=True).start()

    # Start background proactive daemon in thread
    daemon = FleetDaemon()
    daemon_thread = threading.Thread(target=daemon.run_loop, kwargs={"poll_interval_sec": 30}, daemon=True)
    daemon_thread.start()

    # Check for new version on GitHub and dispatch notification if available
    try:
        from fleet.core.updater import start_startup_update_check
        start_startup_update_check(db=getattr(daemon, "db", None))
    except Exception as e:
        pass

    # Start HTTP Server on main thread
    try:
        start_server(PORT)
    except Exception as e:
        import traceback
        print(f"Server exception: {e}")
        traceback.print_exc()
        if sys.stdout:
            sys.stdout.flush()
        if sys.stderr:
            sys.stderr.flush()


if __name__ == "__main__":
    main()

