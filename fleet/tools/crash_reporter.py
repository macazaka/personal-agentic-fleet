"""
Global Crash Reporter & Sanitized Diagnostic Dump Engine for Personal Agentic Fleet.
Captures uncaught sys & threading exceptions, scrubs PII/secrets, and saves JSON forensics.
Zero pip dependencies.
"""

import json
import logging
import os
import platform
import re
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fleet.config import DATA_DIR

CRASH_REPORTS_DIR = DATA_DIR / "crash_reports"
MAX_CRASH_REPORTS = 20

logger = logging.getLogger("fleet.crash_reporter")

# Sanitization regexes to redact sensitive tokens/passwords
SENSITIVE_PATTERNS = [
    (re.compile(r"(AIzaSy[A-Za-z0-9_\-]{30,45})"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"(sk-[A-Za-z0-9_\-]{30,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(ghp_[A-Za-z0-9]{30,})"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE), r"\1[REDACTED_BEARER]"),
    (re.compile(r'(["\']?(?:password|token|secret|api_key|access_token)["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r"\1[REDACTED]\3"),
]


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively redacts API keys, tokens, and secrets from strings, dicts, and lists."""
    if isinstance(val, str):
        result = val
        for pat, replacement in SENSITIVE_PATTERNS:
            result = pat.sub(replacement, result)
        return result
    elif isinstance(val, dict):
        return {k: ("[REDACTED]" if any(s in k.lower() for s in ("token", "secret", "password", "key")) else sanitize_sensitive_data(v)) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_sensitive_data(item) for item in val]
    return val


def get_system_snapshot() -> Dict[str, Any]:
    """Captures non-sensitive workstation execution context."""
    active_threads = [t.name for t in threading.enumerate()]
    snapshot: Dict[str, Any] = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "pid": os.getpid(),
        "active_threads_count": len(active_threads),
        "active_threads": active_threads,
    }

    # Memory estimate if available
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                snapshot["working_set_bytes"] = counters.WorkingSetSize
                snapshot["working_set_mb"] = round(counters.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass

    return snapshot


def generate_crash_report(
    exc_type: Any,
    exc_val: Any,
    exc_tb: Any,
    thread_name: Optional[str] = None
) -> Path:
    """Generates and writes a sanitized crash forensic dump file."""
    CRASH_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"crash_{timestamp_str}_{os.getpid()}.json"
    report_path = CRASH_REPORTS_DIR / report_filename

    raw_tb = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    sanitized_tb = sanitize_sensitive_data(raw_tb)

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "thread_name": thread_name or threading.current_thread().name,
        "exception_type": getattr(exc_type, "__name__", str(exc_type)),
        "exception_message": sanitize_sensitive_data(str(exc_val)),
        "traceback": sanitized_tb,
        "system_snapshot": get_system_snapshot(),
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    logger.critical(f"[CrashReporter] Fatal uncaught exception captured. Diagnostic report saved to: {report_path}")
    prune_old_crash_reports()
    return report_path


def prune_old_crash_reports(keep: int = MAX_CRASH_REPORTS) -> int:
    """Maintains a bounded collection of crash reports, removing oldest first."""
    if not CRASH_REPORTS_DIR.exists():
        return 0

    reports = sorted(CRASH_REPORTS_DIR.glob("crash_*.json"), key=lambda p: p.stat().st_mtime)
    pruned = 0
    if len(reports) > keep:
        to_delete = reports if keep == 0 else reports[:-keep]
        for p in to_delete:
            try:
                p.unlink()
                pruned += 1
            except Exception:
                pass
    return pruned


def list_crash_reports() -> List[Dict[str, Any]]:
    """Returns metadata for all available crash reports."""
    if not CRASH_REPORTS_DIR.exists():
        return []

    reports = []
    for p in sorted(CRASH_REPORTS_DIR.glob("crash_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            reports.append({
                "filename": p.name,
                "timestamp": data.get("timestamp"),
                "exception_type": data.get("exception_type"),
                "exception_message": data.get("exception_message"),
                "thread_name": data.get("thread_name"),
            })
        except Exception:
            continue
    return reports


def install_crash_reporter() -> None:
    """Installs sys.excepthook and threading.excepthook handlers for universal fatal capture."""
    orig_sys_hook = sys.excepthook

    def fleet_sys_excepthook(exc_type, exc_val, exc_tb):
        try:
            generate_crash_report(exc_type, exc_val, exc_tb, thread_name="MainThread")
        except Exception:
            pass
        if orig_sys_hook:
            orig_sys_hook(exc_type, exc_val, exc_tb)

    sys.excepthook = fleet_sys_excepthook

    if hasattr(threading, "excepthook"):
        orig_thread_hook = threading.excepthook

        def fleet_thread_excepthook(args):
            try:
                generate_crash_report(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                    thread_name=args.thread.name if args.thread else "BackgroundThread"
                )
            except Exception:
                pass
            if orig_thread_hook:
                orig_thread_hook(args)

        threading.excepthook = fleet_thread_excepthook

    logger.info("[CrashReporter] Universal sys and threading excepthooks installed.")
