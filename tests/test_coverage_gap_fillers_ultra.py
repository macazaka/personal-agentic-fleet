"""
Ultra gap-filler tests for server, db.health, health_api, base_agent, system_tools, network_spool, and logger.
"""

import base64
import io
import json
import logging
from pathlib import Path
import sqlite3
import sys
import threading
import time
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.server import FleetDashboardHandler
from fleet.core.database import FleetDatabase
import fleet.api.health_api as health_api
from fleet.core.base_agent import FleetAgent
import fleet.tools.system_tools as sys_tools
import fleet.core.network_spool as spool_mod
import fleet.core.logger as log_mod
from fleet.core.event_bus import FleetEvent


# ==============================================================================
# SERVER EDGE CASES
# ==============================================================================

def test_server_options_and_security_blocks():
    handler = MagicMock()
    handler.client_address = ("127.0.0.1", 12345)
    handler.path = "/api/fleet/health"
    handler.headers = {"Host": "attacker.com"} # Untrusted host
    handler.wfile = io.BytesIO()

    # do_OPTIONS
    FleetDashboardHandler.do_OPTIONS(handler)
    assert handler.send_response.called

    # do_GET blocked by security
    handler.send_response.reset_mock()
    FleetDashboardHandler.do_GET(handler)
    assert handler._send_json.called

    # do_GET rate limited (429)
    handler._send_json.reset_mock()
    handler.headers = {"Host": "127.0.0.1:7890"}
    with patch("fleet.core.rate_limiter.rate_limiter.check_rate_limit", return_value=(False, 5.0)):
        FleetDashboardHandler.do_GET(handler)
        handler.send_response.assert_called_with(429)

    # do_POST rate limited and security blocked
    with patch("fleet.core.rate_limiter.rate_limiter.check_rate_limit", return_value=(False, 5.0)):
        FleetDashboardHandler.do_POST(handler)
        handler.send_response.assert_called_with(429)

    handler.headers = {"Host": "attacker.com"}
    with patch("fleet.core.rate_limiter.rate_limiter.check_rate_limit", return_value=(True, 0.0)):
        FleetDashboardHandler.do_POST(handler)
        assert handler._send_json.called


def test_server_sse_stream_and_upload():
    # SSE stream in test mode
    handler = MagicMock()
    handler.client_address = ("127.0.0.1", 12345)
    handler.path = "/api/events/stream"
    handler.headers = {"Host": "127.0.0.1:7890"}
    handler._sse_test_mode = True
    handler.wfile = io.BytesIO()

    with patch("fleet.core.rate_limiter.rate_limiter.check_rate_limit", return_value=(True, 0.0)):
        with patch("fleet.core.event_bus.bus.subscribe"):
            with patch("fleet.core.event_bus.bus.unsubscribe"):
                FleetDashboardHandler.do_GET(handler)
                assert len(handler.wfile.getvalue()) > 0

    # do_POST upload with "base64" key
    handler.path = "/api/antigravity/upload"
    b64_content = base64.b64encode(b"fake image bytes").decode("utf-8")
    handler._read_json.return_value = {"filename": "pic.png", "base64": b64_content}
    with patch("fleet.core.rate_limiter.rate_limiter.check_rate_limit", return_value=(True, 0.0)):
        with patch("fleet.server.save_uploaded_image", return_value={"status": "success"}):
            FleetDashboardHandler.do_POST(handler)
            assert handler._send_json.called


# ==============================================================================
# DB HEALTH & HEALTH API
# ==============================================================================

def test_db_health_metabolic_profile(tmp_path):
    test_db = tmp_path / "health_test.db"
    db = FleetDatabase(db_path=test_db)

    # Ensure metabolic_profile table exists
    with db._get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metabolic_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_weight_kg REAL DEFAULT 75.0,
                target_hba1c REAL DEFAULT 6.4,
                target_date TEXT DEFAULT '2027-01-07',
                baseline_json TEXT,
                updated_at TEXT
            );
        """)
        conn.execute("""
            INSERT OR REPLACE INTO metabolic_profile (id, target_weight_kg, target_hba1c, target_date, baseline_json)
            VALUES (1, 75.0, 6.4, '2027-01-07', '{"start_weight": 85}');
        """)
        conn.commit()

    prof = db.get_metabolic_profile()
    assert prof["target_weight_kg"] == 75.0
    assert "days_remaining" in prof

    # Update profile
    updated = db.update_metabolic_profile(target_weight_kg=73.5, target_hba1c=6.1)
    assert updated["target_weight_kg"] == 73.5
    assert updated["target_hba1c"] == 6.1


def test_health_api_full_video_stream(tmp_path):
    vid_file = tmp_path / "exercise.mp4"
    vid_file.write_bytes(b"dummy mp4 video bytes" * 100)

    handler = MagicMock()
    handler.headers = {} # No Range header -> triggers 200 full stream
    handler.wfile = io.BytesIO()

    parsed = urllib.parse.urlparse("/api/health/video/stream?file=exercise.mp4")

    with patch.object(health_api, "FFD_VIDEOS_DIR", tmp_path):
        health_api.stream_video(handler, parsed)
        handler.send_response.assert_called_with(200)
        assert len(handler.wfile.getvalue()) > 0


# ==============================================================================
# BASE AGENT EXTENSIONS
# ==============================================================================

def test_base_agent_custom_panel_and_tasks(tmp_path):
    class ConcreteAgent(FleetAgent):
        @property
        def id(self) -> str:
            return "test_concrete"

        @property
        def name(self) -> str:
            return "Concrete Test"

        @property
        def icon(self) -> str:
            return "🧪"

    agent_dir = tmp_path / "concrete_agent"
    agent_dir.mkdir()
    (agent_dir / "ui").mkdir()
    
    agent = ConcreteAgent(agent_dir=agent_dir)
    assert agent.execute_task("unknown")["status"] == "NOT_IMPLEMENTED"
    assert agent.register_tasks() == []
    agent.register_events(MagicMock())

    # Custom panel in config with reading exception
    bad_panel = tmp_path / "bad_panel.html"
    agent.config["custom_panel_path"] = str(bad_panel)
    with patch.object(Path, "is_file", return_value=True):
        with patch.object(Path, "read_text", side_effect=OSError("Read fail")):
            manifest = agent.get_ui_manifest()
            assert "Error loading custom panel" in manifest["html"]


# ==============================================================================
# SYSTEM TOOLS, NETWORK SPOOL & LOGGER
# ==============================================================================

def test_system_tools_kdialog():
    # kdialog fallback success and failure
    with patch("sys.platform", "linux"):
        def side_effect(cmd, **kwargs):
            if cmd[0] == "kdialog":
                return MagicMock(returncode=0)
            return MagicMock(returncode=1)

        with patch("subprocess.run", side_effect=side_effect):
            assert sys_tools.send_linux_notification("Title", "Message") is True

        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            assert sys_tools.send_linux_notification("Title", "Message") is False


def test_network_spool_flush_error(tmp_path):
    test_db = tmp_path / "spool_test.db"
    with patch("fleet.core.network_spool.DB_PATH", test_db):
        with patch("fleet.core.network_spool.is_network_available", return_value=True):
            spool_mod.spool_offline_event("target_agent", "ACTION", {"data": 123})

            mock_bus = MagicMock()
            mock_bus.dispatch.side_effect = RuntimeError("Dispatch error")
            
            res = spool_mod.flush_offline_spool(event_bus=mock_bus)
            assert res["failed_count"] == 1


def test_logger_buffer_filtering_and_emit_error():
    buf_handler = log_mod.RingBufferLogHandler(capacity=50)
    
    # Record with exc_info and no formatter
    buf_handler.formatter = None
    try:
        raise ValueError("Log error")
    except ValueError:
        rec = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=sys.exc_info()
        )
        buf_handler.emit(rec)

    # get_logs with level and agent filtering
    logs = buf_handler.get_logs(limit=10, level="ERROR")
    assert len(logs) >= 1
    assert logs[0]["level"] == "ERROR"

    # Emit exception handling
    mock_deque = MagicMock()
    mock_deque.append.side_effect = RuntimeError("Buffer full")
    buf_handler._buffer = mock_deque
    with patch.object(buf_handler, "handleError") as mock_err:
        buf_handler.emit(rec)
        assert mock_err.called

