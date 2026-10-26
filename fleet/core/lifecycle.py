"""
Unified Lifecycle, Signal Trap & Clean Shutdown Coordinator for Personal Agentic Fleet.
Gracefully handles SIGINT, SIGTERM, and Win32 SetConsoleCtrlHandler events.
"""

import atexit
import ctypes
import logging
import os
import signal
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fleet.config import DATA_DIR, DB_PATH

logger = logging.getLogger("fleet.lifecycle")

PID_FILE = DATA_DIR / "fleet.pid"
SHUTDOWN_EVENT = threading.Event()

_SHUTDOWN_CALLBACKS: List[Tuple] = []  # (priority, name, callable)
_LOCK = threading.Lock()
_SHUTDOWN_TRIGGERED = False

def _safe_log(msg: str, level: str = "info") -> None:
    try:
        import sys
        if getattr(sys, "stderr", None) is None or getattr(sys.stderr, "closed", False):
            return
        import logging as _l
        for h in list(_l.root.handlers) + list(logger.handlers):
            stream = getattr(h, "stream", None)
            if stream and getattr(stream, "closed", False):
                return
        getattr(logger, level)(msg)
    except Exception:
        pass


def register_shutdown_callback(name: str, fn: Callable[[], None], priority: int = 50) -> None:
    """Registers a clean-shutdown hook with priority (lower executes first)."""
    with _LOCK:
        _SHUTDOWN_CALLBACKS.append((priority, name, fn))
        _SHUTDOWN_CALLBACKS.sort(key=lambda x: x[0])


def write_pid_file() -> None:
    """Writes the current process PID to fleet/data/fleet.pid."""
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to write PID file: {e}")


def remove_pid_file() -> None:
    """Safely removes fleet/data/fleet.pid on shutdown."""
    try:
        if PID_FILE.is_file():
            PID_FILE.unlink()
    except Exception:
        pass


def checkpoint_sqlite_wal(db_path: Path = DB_PATH) -> bool:
    """Executes PRAGMA wal_checkpoint(TRUNCATE) to cleanly flush WAL to disk."""
    if not db_path.is_file():
        return True
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"SQLite WAL checkpoint on shutdown encountered: {e}")
        return False


def execute_clean_shutdown(exit_code: int = 0) -> None:
    """Coordinates the 3-second structured clean shutdown sequence."""
    global _SHUTDOWN_TRIGGERED
    with _LOCK:
        if _SHUTDOWN_TRIGGERED:
            return
        _SHUTDOWN_TRIGGERED = True

    try:
        _safe_log("Initiating Fleet clean shutdown protocol...")
    except Exception:
        pass
    SHUTDOWN_EVENT.set()

    # 1. Execute registered shutdown callbacks
    for priority, name, fn in _SHUTDOWN_CALLBACKS:
        try:
            fn()
        except Exception as e:
            try:
                logger.error(f"Error in shutdown callback '{name}': {e}", exc_info=True)
            except Exception:
                pass

    # 2. Close all pooled SQLite connections
    try:
        from fleet.core.db.pool import close_all_pooled_connections
        close_all_pooled_connections()
    except Exception:
        pass

    # 3. Checkpoint SQLite WAL
    checkpoint_sqlite_wal()

    # 4. Remove PID lock
    remove_pid_file()

    try:
        _safe_log("Fleet shutdown complete.")
    except Exception:
        pass


# Signal Handlers
def _posix_signal_handler(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    logger.info(f"Received OS signal {sig_name}. Triggering clean shutdown.")
    execute_clean_shutdown(exit_code=0)
    sys.exit(0)


def _setup_win32_console_ctrl():
    """Hooks Win32 SetConsoleCtrlHandler for Windows NT consoles and background services."""
    if os.name != "nt":
        return

    try:
        win_func = getattr(ctypes, "WINFUNCTYPE", getattr(ctypes, "CFUNCTYPE", None))
        if not win_func:
            return
        HandlerRoutine = win_func(ctypes.c_bool, ctypes.c_ulong)

        def _win_handler(ctrl_type: int) -> bool:
            # 0=CTRL_C_EVENT, 1=CTRL_BREAK_EVENT, 2=CTRL_CLOSE_EVENT, 5=CTRL_LOGOFF_EVENT, 6=CTRL_SHUTDOWN_EVENT
            execute_clean_shutdown(exit_code=0)
            return True

        # Keep global reference to avoid garbage collection
        global _win32_handler_ref
        _win32_handler_ref = HandlerRoutine(_win_handler)
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCtrlHandler(_win32_handler_ref, True)
    except Exception as e:
        logger.debug(f"Win32 SetConsoleCtrlHandler setup skipped: {e}")


def install_lifecycle_guards() -> None:
    """Installs POSIX signal traps, Win32 console traps, and atexit handlers."""
    write_pid_file()

    # Always register atexit as fallback
    atexit.register(execute_clean_shutdown)

    # POSIX signals
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, _posix_signal_handler)
            except Exception:
                pass

    # Windows console handler
    if os.name == "nt":
        _setup_win32_console_ctrl()
