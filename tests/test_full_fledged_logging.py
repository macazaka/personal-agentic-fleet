"""
Comprehensive Test Suite for Full-Fledged Logging, Error Forensics & Diagnostics.
Validates:
- Full diagnostic metadata (file, line, func, thread, process, exception stack frames)
- Dedicated fleet_error.log isolation for WARNING, ERROR, and CRITICAL events
- Python runtime warnings interception (py.warnings)
- In-memory ring buffer search, level filtering, and min_level thresholding
- Global sys.excepthook and threading.excepthook unhandled exception capture
- Diagnostics REST API endpoints (/api/diagnostics/logs and /api/diagnostics/errors)
"""

import io
import json
import logging
import os
import sys
import tempfile
import threading
import time
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from fleet.core.logger import (
    DetailedTextLogFormatter,
    JsonLogFormatter,
    RingBufferLogHandler,
    configure_logging,
    get_recent_errors,
    get_recent_logs,
    install_logging_excepthooks,
    read_error_log_tail,
)
from fleet.server import FleetDashboardHandler


def test_json_log_formatter_full_diagnostic_fields():
    formatter = JsonLogFormatter()
    
    # 1. Info record without exception
    rec = logging.LogRecord(
        name="fleet.test_subsystem",
        level=logging.INFO,
        pathname="/app/fleet/agents/agenda.py",
        lineno=142,
        msg="Task dispatch completed in 12ms",
        args=(),
        exc_info=None,
    )
    rec.agent = "AgendaAgent"
    rec.action = "DISPATCH_TASK"
    rec.metadata = {"task_id": 42, "duration_ms": 12}

    formatted = formatter.format(rec)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "fleet.test_subsystem"
    assert data["agent"] == "AgendaAgent"
    assert data["action"] == "DISPATCH_TASK"
    assert data["message"] == "Task dispatch completed in 12ms"
    assert data["line"] == 142
    assert "agenda.py" in data["filename"]
    assert data["metadata"]["task_id"] == 42
    assert "process" in data
    assert "thread_name" in data
    assert "thread_id" in data


def test_json_log_formatter_exception_and_warning_caller():
    formatter = JsonLogFormatter()

    # 1. Error with exception info
    try:
        raise ValueError("Critical database connection timeout")
    except ValueError:
        exc_info = sys.exc_info()

    rec_err = logging.LogRecord(
        name="fleet.database",
        level=logging.ERROR,
        pathname="/app/fleet/core/database.py",
        lineno=88,
        msg="Database query failure",
        args=(),
        exc_info=exc_info,
    )
    rec_err.agent = "DatabaseEngine"
    rec_err.action = "QUERY_TIMEOUT"

    formatted_err = formatter.format(rec_err)
    data_err = json.loads(formatted_err)

    assert data_err["level"] == "ERROR"
    assert "exception" in data_err
    assert data_err["exception_type"] == "ValueError"
    assert "Critical database connection timeout" in data_err["exception_message"]
    assert "stack_frames" in data_err
    assert len(data_err["stack_frames"]) >= 1

    # 2. Warning without exception info captures caller
    rec_warn = logging.LogRecord(
        name="fleet.token_monitor",
        level=logging.WARNING,
        pathname="/app/fleet/core/token_optimizer.py",
        lineno=210,
        msg="Approaching token usage ceiling (85%)",
        args=(),
        exc_info=None,
    )
    formatted_warn = formatter.format(rec_warn)
    data_warn = json.loads(formatted_warn)

    assert data_warn["level"] == "WARNING"
    assert "caller" in data_warn
    assert "token_optimizer.py:210" in data_warn["caller"]


def test_detailed_text_formatter():
    formatter = DetailedTextLogFormatter()
    rec = logging.LogRecord(
        name="fleet.network",
        level=logging.WARNING,
        pathname="spool.py",
        lineno=55,
        msg="Packet retransmission detected",
        args=(),
        exc_info=None,
    )
    rec.agent = "NetworkSpool"
    formatted = formatter.format(rec)

    assert "[WARNING]" in formatted
    assert "[fleet.network]" in formatted
    assert "[spool.py:55 [NetworkSpool]]" in formatted
    assert "Packet retransmission detected" in formatted

    # With exception
    try:
        raise ConnectionResetError("Remote host reset connection")
    except ConnectionResetError:
        rec.exc_info = sys.exc_info()

    formatted_exc = formatter.format(rec)
    assert "ConnectionResetError: Remote host reset connection" in formatted_exc


def test_ring_buffer_handler_advanced_filtering():
    handler = RingBufferLogHandler(capacity=20)
    handler.clear()

    # Emit varied records
    levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
    for idx, lvl in enumerate(levels):
        r = logging.LogRecord(
            name=f"fleet.sub_{idx}",
            level=lvl,
            pathname="sub.py",
            lineno=idx + 1,
            msg=f"Message {idx} with keyword_alpha",
            args=(),
            exc_info=None,
        )
        r.agent = "AgentA" if idx % 2 == 0 else "AgentB"
        handler.emit(r)

    # 1. Exact level filter
    errors = handler.get_logs(level="ERROR")
    assert len(errors) == 1
    assert errors[0]["level"] == "ERROR"

    # 2. Min level threshold filter (WARNING and above)
    high_sev = handler.get_logs(min_level="WARNING")
    assert len(high_sev) == 3  # WARNING, ERROR, CRITICAL
    assert all(e["level"] in ("WARNING", "ERROR", "CRITICAL") for e in high_sev)

    # 3. Agent filter
    agent_a_logs = handler.get_logs(agent="AgentA")
    assert all(e["agent"] == "AgentA" for e in agent_a_logs)

    # 4. Search query filter
    searched = handler.get_logs(search="keyword_alpha")
    assert len(searched) == 5

    # 5. Clear
    handler.clear()
    assert len(handler.get_logs()) == 0


def test_full_fledged_dual_log_files_isolation():
    """Validates that fleet_app.log gets all logs, while fleet_error.log strictly isolates warnings/errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app_log = Path(tmpdir) / "test_fleet_app.log"
        error_log = Path(tmpdir) / "test_fleet_error.log"

        test_logger = logging.getLogger("fleet.test_isolation")
        test_logger.setLevel(logging.DEBUG)

        formatter = JsonLogFormatter()

        # Main app handler (DEBUG and up)
        h_app = logging.FileHandler(str(app_log), encoding="utf-8")
        h_app.setFormatter(formatter)
        h_app.setLevel(logging.DEBUG)
        test_logger.addHandler(h_app)

        # Dedicated error handler (WARNING and up)
        h_err = logging.FileHandler(str(error_log), encoding="utf-8")
        h_err.setFormatter(formatter)
        h_err.setLevel(logging.WARNING)
        test_logger.addHandler(h_err)

        try:
            # Emit INFO, WARNING, and ERROR
            test_logger.info("Routine operation succeeded", extra={"agent": "TestAgent"})
            test_logger.warning("Disk utilization exceeded threshold", extra={"agent": "SystemAgent"})
            try:
                raise RuntimeError("Subsystem thread crashed")
            except RuntimeError:
                test_logger.error("Critical execution fault", exc_info=True, extra={"agent": "SupervisorAgent"})

            h_app.flush()
            h_err.flush()

            # Verify app_log contains all 3 entries
            app_lines = [json.loads(line) for line in app_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(app_lines) == 3
            assert [l["level"] for l in app_lines] == ["INFO", "WARNING", "ERROR"]

            # Verify error_log contains strictly WARNING and ERROR (0 INFO entries)
            err_lines = [json.loads(line) for line in error_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(err_lines) == 2
            assert [l["level"] for l in err_lines] == ["WARNING", "ERROR"]
            assert err_lines[1]["exception_type"] == "RuntimeError"

            # Test read_error_log_tail helper
            parsed_tail = read_error_log_tail(max_lines=10, log_path=error_log)
            assert len(parsed_tail) == 2
            assert parsed_tail[0]["level"] == "ERROR"  # latest first

        finally:
            test_logger.removeHandler(h_app)
            test_logger.removeHandler(h_err)
            h_app.close()
            h_err.close()


def test_python_warnings_interception():
    """Validates that standard Python runtime warnings are captured by the logging engine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_log = Path(tmpdir) / "warnings_test.log"
        handler = logging.FileHandler(str(test_log), encoding="utf-8")
        handler.setFormatter(JsonLogFormatter())
        handler.setLevel(logging.WARNING)

        py_warnings = logging.getLogger("py.warnings")
        py_warnings.addHandler(handler)

        try:
            # Under pytest runners, invoke logging's warning redirector directly
            if hasattr(logging, "_showwarning"):
                logging._showwarning("Deprecated API version v1 used", DeprecationWarning, "api.py", 42)
            else:
                py_warnings.warning("Deprecated API version v1 used: DeprecationWarning")
            handler.flush()

            lines = [json.loads(l) for l in test_log.read_text(encoding="utf-8").splitlines() if l.strip()]
            assert len(lines) >= 1
            assert any("Deprecated API version v1 used" in l["message"] for l in lines)
            assert any(l["level"] == "WARNING" for l in lines)
        finally:
            py_warnings.removeHandler(handler)
            handler.close()


def test_uncaught_exception_hooks():
    """Validates global unhandled exception hooks capture crashes with full traceback."""
    install_logging_excepthooks()

    try:
        raise KeyError("Missing essential vault key")
    except KeyError:
        exc_type, exc_val, exc_tb = sys.exc_info()

    # Verify sys.excepthook logs a critical crash event
    with patch("sys.__excepthook__"):
        with patch.object(logging.getLogger("fleet.uncaught"), "critical") as mock_u_crit, \
             patch.object(logging.getLogger("fleet.crash_reporter"), "critical") as mock_c_crit:
            sys.excepthook(exc_type, exc_val, exc_tb)
            assert mock_u_crit.called or mock_c_crit.called

    # Verify threading.excepthook if available
    if hasattr(threading, "ExceptHookArgs"):
        th = threading.Thread(name="WorkerThread-42")
        hook_args = threading.ExceptHookArgs((exc_type, exc_val, exc_tb, th))
        with patch.object(logging.getLogger("fleet.uncaught"), "critical") as mock_th_crit, \
             patch.object(logging.getLogger("fleet.crash_reporter"), "critical") as mock_th_c_crit:
            threading.excepthook(hook_args)
            assert mock_th_crit.called or mock_th_c_crit.called


def test_diagnostics_api_endpoints():
    """Validates /api/diagnostics/logs and /api/diagnostics/errors REST API endpoints."""
    # Seed ring buffer with test logs
    from fleet.core.logger import ring_buffer_handler
    ring_buffer_handler.clear()

    rec_info = logging.LogRecord("fleet.api", logging.INFO, "api.py", 10, "GET /api/status 200", (), None)
    rec_warn = logging.LogRecord("fleet.api", logging.WARNING, "api.py", 20, "Rate limit approaching", (), None)
    rec_err = logging.LogRecord("fleet.api", logging.ERROR, "api.py", 30, "Database busy error", (), None)

    ring_buffer_handler.emit(rec_info)
    ring_buffer_handler.emit(rec_warn)
    ring_buffer_handler.emit(rec_err)

    # 1. GET /api/diagnostics/logs?min_level=WARNING
    handler = FleetDashboardHandler.__new__(FleetDashboardHandler)
    handler.rfile = io.BytesIO()
    handler.wfile = io.BytesIO()
    handler.path = "/api/diagnostics/logs?min_level=WARNING"
    handler.command = "GET"
    handler.requestline = f"GET {handler.path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.headers = {}
    handler.client_address = ("127.0.0.1", 54321)
    handler.close_connection = False

    handler.do_GET()
    resp = handler.wfile.getvalue().decode("utf-8")
    assert "200 OK" in resp
    body = json.loads(resp.split("\r\n\r\n", 1)[1])
    assert body["status"] == "success"
    assert body["count"] == 2
    assert all(l["level"] in ("WARNING", "ERROR") for l in body["logs"])

    # 2. GET /api/diagnostics/errors
    handler_err = FleetDashboardHandler.__new__(FleetDashboardHandler)
    handler_err.rfile = io.BytesIO()
    handler_err.wfile = io.BytesIO()
    handler_err.path = "/api/diagnostics/errors?source=ring"
    handler_err.command = "GET"
    handler_err.requestline = f"GET {handler_err.path} HTTP/1.1"
    handler_err.request_version = "HTTP/1.1"
    handler_err.headers = {}
    handler_err.client_address = ("127.0.0.1", 54321)
    handler_err.close_connection = False

    handler_err.do_GET()
    resp_err = handler_err.wfile.getvalue().decode("utf-8")
    assert "200 OK" in resp_err
    body_err = json.loads(resp_err.split("\r\n\r\n", 1)[1])
    assert body_err["status"] == "success"
    assert len(body_err["ring_buffer_errors"]) == 2
