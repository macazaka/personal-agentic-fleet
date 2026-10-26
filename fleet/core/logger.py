"""
Structured JSON Logging Engine & In-Memory Ring Buffer for Personal Agentic Fleet.
Zero pip dependencies. Thread-safe log rotation and live diagnostics streaming buffer.
"""

import collections
import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from fleet.config import DATA_DIR

DEFAULT_LOG_FILE = DATA_DIR / "fleet_app.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 3
RING_BUFFER_CAPACITY = 1000


class JsonLogFormatter(logging.Formatter):
    """Formats log records as uniform, machine-readable JSON objects."""

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
            "metadata": metadata,
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class RingBufferLogHandler(logging.Handler):
    """Thread-safe logging handler that buffers the N most recent log records in memory."""

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
                "metadata": metadata,
            }
            if record.exc_info:
                entry["exception"] = self.formatException(record.exc_info)

            with self._lock:
                self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
        agent: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns buffered log entries with optional filtering, most recent first."""
        with self._lock:
            logs = list(self._buffer)

        if level:
            level_upper = level.upper()
            logs = [e for e in logs if e["level"] == level_upper]

        if agent:
            logs = [e for e in logs if e["agent"].lower() == agent.lower()]

        # Return latest first up to limit
        return logs[-limit:][::-1]

    def clear(self) -> None:
        """Clears all buffered entries."""
        with self._lock:
            self._buffer.clear()


# Global ring buffer instance
ring_buffer_handler = RingBufferLogHandler(RING_BUFFER_CAPACITY)


def configure_logging(
    log_file: Optional[Path] = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    level: int = logging.INFO,
    enable_console: bool = True
) -> logging.Logger:
    """Configures structured JSON logging with rotating file handler and in-memory ring buffer."""
    root_logger = logging.getLogger("fleet")
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if any(isinstance(h, RingBufferLogHandler) for h in root_logger.handlers):
        return root_logger

    formatter = JsonLogFormatter()

    # 1. In-memory Ring Buffer Handler
    ring_buffer_handler.setFormatter(formatter)
    ring_buffer_handler.setLevel(level)
    root_logger.addHandler(ring_buffer_handler)

    # 2. Rotating File Handler
    target_log_file = log_file or DEFAULT_LOG_FILE
    target_log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        str(target_log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # 3. Optional Console Handler (Plain text or JSON depending on context)
    if enable_console and not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    return root_logger


def get_recent_logs(
    limit: int = 100,
    level: Optional[str] = None,
    agent: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Helper to query the global ring buffer."""
    return ring_buffer_handler.get_logs(limit=limit, level=level, agent=agent)
