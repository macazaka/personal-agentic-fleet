"""
Structured JSON Logging Engine, Error Forensics & Ring Buffer for Personal Agentic Fleet.
Zero pip dependencies. Thread-safe log rotation, dedicated error isolation,
Python warnings interception, and deep diagnostic forensics streaming.
"""

import collections
import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
import sys
import threading
import traceback
from typing import Any, Dict, List, Optional

from fleet.config import DATA_DIR

DEFAULT_LOG_FILE = DATA_DIR / "fleet_app.log"
DEFAULT_ERROR_LOG_FILE = DATA_DIR / "fleet_error.log"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5
RING_BUFFER_CAPACITY = 2000

# Level numeric hierarchy for min_level filtering
LEVEL_HIERARCHY = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JsonLogFormatter(logging.Formatter):
    """Formats log records as uniform, machine-readable JSON objects with full diagnostic fidelity."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        
        # Extract structured metadata if provided via extra={...}
        agent = getattr(record, "agent", getattr(record, "agent_name", "Microkernel"))
        action = getattr(record, "action", getattr(record, "event_action", ""))
        metadata = getattr(record, "metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"raw": str(metadata)}

        log_obj: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "agent": agent,
            "action": action,
            "message": record.getMessage(),
            "file": record.pathname,
            "filename": record.filename,
            "line": record.lineno,
            "func": record.funcName,
            "module": record.module,
            "process": record.process,
            "thread_name": record.threadName,
            "thread_id": record.thread,
            "metadata": metadata,
        }

        if record.exc_info:
            exc_type, exc_val, exc_tb = record.exc_info
            log_obj["exception"] = self.formatException(record.exc_info)
            log_obj["exception_type"] = exc_type.__name__ if exc_type else "Exception"
            log_obj["exception_message"] = str(exc_val)
            if exc_tb:
                try:
                    log_obj["stack_frames"] = [line.strip() for line in traceback.format_tb(exc_tb)]
                except Exception:
                    pass
        elif record.levelno >= logging.WARNING:
            log_obj["caller"] = f"{record.filename}:{record.lineno} in {record.funcName}()"
            if record.stack_info:
                log_obj["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_obj, ensure_ascii=False)


class DetailedTextLogFormatter(logging.Formatter):
    """Human-readable console and text log formatter with file, line, and caller details."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname.ljust(7)
        agent = getattr(record, "agent", getattr(record, "agent_name", ""))
        agent_tag = f" [{agent}]" if agent else ""
        location = f"{record.filename}:{record.lineno}"
        msg = record.getMessage()

        base = f"[{timestamp}] [{level}] [{record.name}] [{location}{agent_tag}] {msg}"
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            base = f"{base}\n{exc_text}"
        return base


class RingBufferLogHandler(logging.Handler):
    """Thread-safe logging handler that buffers the N most recent log records in memory with diagnostic fields."""

    def __init__(self, capacity: int = RING_BUFFER_CAPACITY):
        super().__init__()
        self.capacity = capacity
        self._buffer: collections.deque = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            timestamp = datetime.fromtimestamp(record.created).isoformat()
            agent = getattr(record, "agent", getattr(record, "agent_name", "Microkernel"))
            action = getattr(record, "action", getattr(record, "event_action", ""))
            metadata = getattr(record, "metadata", {})
            if not isinstance(metadata, dict):
                metadata = {"raw": str(metadata)}

            entry: Dict[str, Any] = {
                "timestamp": timestamp,
                "level": record.levelname,
                "logger": record.name,
                "agent": agent,
                "action": action,
                "message": record.getMessage(),
                "file": record.filename,
                "line": record.lineno,
                "func": record.funcName,
                "module": record.module,
                "thread_name": record.threadName,
                "metadata": metadata,
            }

            if record.exc_info:
                exc_type, exc_val, _ = record.exc_info
                if self.formatter:
                    entry["exception"] = self.formatter.formatException(record.exc_info)
                else:
                    entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
                entry["exception_type"] = exc_type.__name__ if exc_type else "Exception"
                entry["exception_message"] = str(exc_val)
            elif record.levelno >= logging.WARNING:
                entry["caller"] = f"{record.filename}:{record.lineno} in {record.funcName}()"

            with self._lock:
                self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
        min_level: Optional[str] = None,
        agent: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns buffered log entries with optional filtering, most recent first."""
        with self._lock:
            logs = list(self._buffer)

        if level:
            level_upper = level.upper()
            logs = [e for e in logs if e.get("level") == level_upper]

        if min_level:
            min_thresh = LEVEL_HIERARCHY.get(min_level.upper(), logging.DEBUG)
            logs = [e for e in logs if LEVEL_HIERARCHY.get(e.get("level", "DEBUG"), 0) >= min_thresh]

        if agent:
            agent_lower = agent.lower()
            logs = [e for e in logs if str(e.get("agent", "")).lower() == agent_lower]

        if search:
            search_lower = search.lower()
            logs = [
                e for e in logs
                if search_lower in str(e.get("message", "")).lower()
                or search_lower in str(e.get("exception", "")).lower()
                or search_lower in str(e.get("caller", "")).lower()
            ]

        # Return latest first up to limit
        return logs[-limit:][::-1]

    def clear(self) -> None:
        """Clears all buffered entries."""
        with self._lock:
            self._buffer.clear()


# Global ring buffer instance
ring_buffer_handler = RingBufferLogHandler(RING_BUFFER_CAPACITY)

# Guard against duplicate excepthook registration
_EXCEPTHOOKS_INSTALLED = False


def install_logging_excepthooks() -> None:
    """Installs sys.excepthook and threading.excepthook to log uncaught exceptions with full detail."""
    global _EXCEPTHOOKS_INSTALLED
    if _EXCEPTHOOKS_INSTALLED:
        return

    orig_sys_hook = sys.excepthook

    def handle_sys_exception(exc_type, exc_val, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            orig_sys_hook(exc_type, exc_val, exc_tb)
            return
        uncaught_logger = logging.getLogger("fleet.uncaught")
        uncaught_logger.critical(
            "Uncaught sys exception: %s: %s",
            exc_type.__name__,
            exc_val,
            exc_info=(exc_type, exc_val, exc_tb),
            extra={"agent": "SystemKernel", "action": "uncaught_sys_exception"}
        )
        orig_sys_hook(exc_type, exc_val, exc_tb)

    def handle_thread_exception(args: threading.ExceptHookArgs):
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        uncaught_logger = logging.getLogger("fleet.uncaught")
        thread_name = args.thread.name if args.thread else "UnknownThread"
        uncaught_logger.critical(
            "Uncaught thread exception in thread '%s': %s: %s",
            thread_name,
            args.exc_type.__name__ if args.exc_type else "Exception",
            args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback) if (args.exc_type and args.exc_value) else True,
            extra={"agent": "SystemKernel", "action": "uncaught_thread_exception"}
        )

    sys.excepthook = handle_sys_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception

    _EXCEPTHOOKS_INSTALLED = True


def configure_logging(
    log_file: Optional[Path] = None,
    error_log_file: Optional[Path] = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    level: Optional[int] = None,
    enable_console: bool = True,
    enable_warnings: bool = True,
) -> logging.Logger:
    """
    Configures full-fledged structured JSON logging with:
    - Primary rotating file handler (fleet_app.log)
    - Dedicated failure & error isolation handler (fleet_error.log)
    - In-memory ring buffer for live web telemetry
    - Python runtime warnings routing (py.warnings)
    - Global uncaught exception diagnostics
    """
    # Determine effective log level
    if level is None:
        env_level_str = os.environ.get("FLEET_LOG_LEVEL", "DEBUG").strip().upper()
        effective_level = LEVEL_HIERARCHY.get(env_level_str, logging.DEBUG)
    else:
        effective_level = level

    root_logger = logging.getLogger("fleet")
    root_logger.setLevel(effective_level)

    # Avoid adding duplicate handlers if already configured
    if any(isinstance(h, RingBufferLogHandler) for h in root_logger.handlers):
        return root_logger

    formatter = JsonLogFormatter()

    # 1. In-memory Ring Buffer Handler
    ring_buffer_handler.setFormatter(formatter)
    ring_buffer_handler.setLevel(effective_level)
    root_logger.addHandler(ring_buffer_handler)

    # 2. Primary Rotating File Handler (All diagnostic telemetry)
    target_log_file = log_file or DEFAULT_LOG_FILE
    target_log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        str(target_log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(effective_level)
    root_logger.addHandler(file_handler)

    # 3. Dedicated Error & Failure Isolation Handler (fleet_error.log)
    # Strictly captures WARNING, ERROR, and CRITICAL events for post-mortem forensics
    target_error_file = error_log_file or DEFAULT_ERROR_LOG_FILE
    target_error_file.parent.mkdir(parents=True, exist_ok=True)
    error_handler = logging.handlers.RotatingFileHandler(
        str(target_error_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)
    root_logger.addHandler(error_handler)

    # 4. Optional Console Handler with readable detailed text format
    if enable_console and not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(DetailedTextLogFormatter())
        console_handler.setLevel(effective_level)
        root_logger.addHandler(console_handler)

    # 5. Capture Python Runtime Warnings into Fleet Logging
    if enable_warnings:
        try:
            logging.captureWarnings(True)
            warnings_logger = logging.getLogger("py.warnings")
            warnings_logger.setLevel(logging.WARNING)
            if not any(isinstance(h, RingBufferLogHandler) for h in warnings_logger.handlers):
                warnings_logger.addHandler(ring_buffer_handler)
                warnings_logger.addHandler(file_handler)
                warnings_logger.addHandler(error_handler)
        except Exception:
            pass

    # 6. Global Unhandled Exception Hooks
    try:
        install_logging_excepthooks()
    except Exception:
        pass

    return root_logger


def get_recent_logs(
    limit: int = 100,
    level: Optional[str] = None,
    min_level: Optional[str] = None,
    agent: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Helper to query the global ring buffer."""
    return ring_buffer_handler.get_logs(
        limit=limit,
        level=level,
        min_level=min_level,
        agent=agent,
        search=search,
    )


def get_recent_errors(limit: int = 100) -> List[Dict[str, Any]]:
    """Helper to retrieve all recent warnings, errors, and critical failures from the ring buffer."""
    return ring_buffer_handler.get_logs(limit=limit, min_level="WARNING")


def read_error_log_tail(max_lines: int = 100, log_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Reads the most recent entries from the dedicated fleet_error.log file on disk."""
    path = log_path or DEFAULT_ERROR_LOG_FILE
    if not path.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in reversed(lines[-max_lines:]):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entries.append(json.loads(line_str))
                except Exception:
                    entries.append({"raw": line_str, "level": "UNKNOWN"})
    except Exception as e:
        entries.append({"error": f"Failed to read error log: {e}", "level": "ERROR"})

    return entries
