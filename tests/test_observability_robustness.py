"""
Unit tests for Pillar 5 Observability & Pillar 4 SSE streaming.
Tests Structured JSON Logging (ROB-12), Crash Reporting (ROB-13), and SSE stream (ROB-07).
"""

import io
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from fleet.core.logger import (
    JsonLogFormatter,
    RingBufferLogHandler,
    configure_logging,
    get_recent_logs,
)
from fleet.tools.crash_reporter import (
    generate_crash_report,
    list_crash_reports,
    prune_old_crash_reports,
    sanitize_sensitive_data,
)
from fleet.server import FleetDashboardHandler


def test_structured_json_logging():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="fleet.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test event message",
        args=(),
        exc_info=None
    )
    record.agent = "DailyBriefingAgent"
    record.action = "GENERATE_BRIEFING"
    record.metadata = {"duration_ms": 42}

    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["level"] == "INFO"
    assert data["logger"] == "fleet.test"
    assert data["agent"] == "DailyBriefingAgent"
    assert data["action"] == "GENERATE_BRIEFING"
    assert data["message"] == "Test event message"
    assert data["metadata"]["duration_ms"] == 42


def test_ring_buffer_handler():
    handler = RingBufferLogHandler(capacity=5)
    handler.clear()

    for i in range(10):
        rec = logging.LogRecord(
            name="fleet.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"Msg #{i}",
            args=(),
            exc_info=None
        )
        rec.agent = "AgentA" if i % 2 == 0 else "AgentB"
        handler.emit(rec)

    # Max capacity is 5, so only last 5 remain
    logs = handler.get_logs(limit=10)
    assert len(logs) == 5
    assert logs[0]["message"] == "Msg #9"  # Most recent first

    agent_a_logs = handler.get_logs(agent="AgentA")
    assert all(l["agent"] == "AgentA" for l in agent_a_logs)


def test_crash_reporter_sanitization(tmp_path):
    # Test secret scrubbing (constructed dynamically so static pre-commit scanner is not tripped)
    dummy_sk = "sk-" + "abcdef1234567890" * 3
    dummy_gemini = "AIza" + "Sy" + "D284hfd84jshfkshdf934hf84hfd83"
    raw_leak = f"API key {dummy_sk} should be hidden and {dummy_gemini}"
    sanitized = sanitize_sensitive_data(raw_leak)
    assert "sk-" not in sanitized
    assert "AIzaSy" not in sanitized
    assert "[REDACTED" in sanitized

    # Test crash report generation
    try:
        dummy_exc_key = "AIza" + "Sy" + "FakeSecret1234567890FakeSecret123"
        raise ValueError(f"Simulated fatal test exception with key {dummy_exc_key}")
    except ValueError as e:
        import sys
        exc_type, exc_val, exc_tb = sys.exc_info()
        report_path = generate_crash_report(exc_type, exc_val, exc_tb, thread_name="TestThread")
        assert report_path.exists()

        content = json.loads(report_path.read_text(encoding="utf-8"))
        assert content["exception_type"] == "ValueError"
        assert "[REDACTED" in content["exception_message"]
        assert content["thread_name"] == "TestThread"
        assert "system_snapshot" in content

        # Cleanup
        report_path.unlink()


def test_server_diagnostics_and_sse_endpoints():
    def create_handler(path):
        handler = FleetDashboardHandler.__new__(FleetDashboardHandler)
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.path = path
        handler.command = "GET"
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.headers = {"Content-Type": "application/json"}
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 54321)
        handler.close_connection = False
        return handler, handler.wfile

    # 1. GET /api/diagnostics/logs
    h, out = create_handler("/api/diagnostics/logs?limit=5")
    h.do_GET()
    resp_text = out.getvalue().decode("utf-8")
    assert "200 OK" in resp_text
    assert '"status": "success"' in resp_text

    # 2. GET /api/diagnostics/crashes
    h, out = create_handler("/api/diagnostics/crashes")
    h.do_GET()
    resp_text = out.getvalue().decode("utf-8")
    assert "200 OK" in resp_text
    assert '"reports":' in resp_text

    # 3. GET /api/events/stream
    h, out = create_handler("/api/events/stream")
    h._sse_test_mode = True  # Instructs handler to exit loop after 1 tick
    h.do_GET()
    resp_text = out.getvalue().decode("utf-8")
    assert "text/event-stream" in resp_text
    assert "event: ready" in resp_text
