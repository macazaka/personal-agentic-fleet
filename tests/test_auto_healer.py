"""
Comprehensive Unit Tests for Proactive Log Scanner & Autonomous Self-Healing Engine.
Tests log ingestion, diagnostic pattern recognition, autonomous remediation routines,
persistence to SQLite and JSON ledger, daemon integration, and REST API endpoints.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from fleet.core.auto_healer import (
    AutonomousAutoHealer,
    ImprovementAction,
    IssueFinding,
    ProactiveLogScanner,
    calculate_system_health_index,
    get_auto_improvements_history,
    persist_improvements_to_ledger,
    run_proactive_log_scan_and_heal,
)
from fleet.core.database import FleetDatabase


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated FleetDatabase instance."""
    db_file = tmp_path / "test_autoheal.db"
    db = FleetDatabase(db_path=db_file)
    return db


def test_calculate_system_health_index():
    """Verifies objective deduction scoring based on issue severity."""
    # Clean system
    assert calculate_system_health_index([]) == 100.0

    # Low severity finding
    f_low = IssueFinding(
        id="1", category="WARNINGS", severity="LOW",
        title="Warnings", description="Sample"
    )
    assert calculate_system_health_index([f_low]) == 97.0

    # High severity finding
    f_high = IssueFinding(
        id="2", category="DATABASE", severity="HIGH",
        title="DB Lock", description="Sample"
    )
    assert calculate_system_health_index([f_high]) == 80.0

    # Multiple issues compounding
    f_crit = IssueFinding(
        id="3", category="MEMORY", severity="CRITICAL",
        title="OOM", description="Sample"
    )
    score = calculate_system_health_index([f_low, f_high, f_crit])
    assert score == 42.0  # 100 - (3 + 20 + 35)


def test_scanner_database_contention_detection(tmp_path):
    """Tests detection of database locked patterns and large WAL files."""
    db_path = tmp_path / "contention_test.db"
    scanner = ProactiveLogScanner(db_path=db_path)

    # Clean logs
    logs_clean = [{"message": "System starting up", "level": "INFO"}]
    assert scanner._check_database_contention(logs_clean) is None

    # Contention logs
    logs_error = [
        {"message": "sqlite3.OperationalError: database is locked", "level": "ERROR"},
        {"message": "Retrying transaction after lock contention", "level": "WARNING"},
    ]
    finding = scanner._check_database_contention(logs_error)
    assert finding is not None
    assert finding.category == "DATABASE"
    assert finding.severity in ("MEDIUM", "HIGH")
    assert finding.remediation_action == "checkpoint_wal_and_optimize_db"
    assert finding.evidence["lock_count"] >= 1


def test_scanner_rate_limiting_detection():
    """Tests detection of HTTP 429 and rate-limiting patterns."""
    scanner = ProactiveLogScanner()

    # Normal logs
    assert scanner._check_rate_limiting([{"message": "GET /api/status HTTP 200"}]) is None

    # 429 logs
    logs = [
        {"message": "HTTP response: 429 Too Many Requests from external API", "level": "WARNING"},
        {"message": "RateLimitError: quota exceeded for model", "level": "ERROR"},
    ]
    finding = scanner._check_rate_limiting(logs)
    assert finding is not None
    assert finding.category == "RATE_LIMIT"
    assert finding.remediation_action == "apply_adaptive_rate_limit_backoff"
    assert finding.evidence["rate_limit_count"] == 2


def test_scanner_task_failure_detection(temp_db):
    """Tests detection of failed tasks in database."""
    scanner = ProactiveLogScanner(db_path=temp_db.db_path)

    # Insert a failed task into the database
    with temp_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (title, description, source, priority, status, created_at, updated_at)
            VALUES ('Failing Job', 'Network sync failed', 'Scheduler', 'P1', 'failed', datetime('now'), datetime('now'))
        """)
        conn.commit()

    finding = scanner._check_task_failure_loops([], db_conn=temp_db._get_connection())
    assert finding is not None
    assert finding.category == "TASK_FAILURES"
    assert finding.remediation_action == "auto_backoff_and_quarantine_failed_tasks"
    assert finding.evidence["failed_tasks_count"] >= 1


def test_autonomous_healer_wal_checkpoint(tmp_path):
    """Tests execution of WAL checkpoint and DB optimization remediation."""
    db_path = tmp_path / "wal_heal.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO t1 (val) VALUES ('test')")
    conn.commit()
    conn.close()

    healer = AutonomousAutoHealer(db_path=db_path)
    finding = IssueFinding(
        id="ISSUE-DB-TEST", category="DATABASE", severity="MEDIUM",
        title="WAL Checkpoint Needed", description="Test",
        remediation_action="checkpoint_wal_and_optimize_db"
    )

    action = healer._heal_checkpoint_wal_and_optimize_db("SCAN-TEST", finding)
    assert action.status == "VERIFIED"
    assert action.issue_type == "DATABASE"
    assert "PRAGMA wal_checkpoint" in action.action_taken


def test_autonomous_healer_task_quarantine(temp_db):
    """Tests automatic quarantining and backoff application for repeated failed tasks."""
    with temp_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO tasks (title, description, source, priority, status, created_at, updated_at)
            VALUES ('Stuck Task', 'API connection error', 'Scheduler', 'P1', 'failed', datetime('now'), datetime('now'))
        """)
        conn.commit()

    healer = AutonomousAutoHealer(db_path=temp_db.db_path)
    finding = IssueFinding(
        id="ISSUE-TASK-TEST", category="TASK_FAILURES", severity="MEDIUM",
        title="Stuck Task Loop", description="Test",
        evidence={"failed_tasks_count": 1},
        remediation_action="auto_backoff_and_quarantine_failed_tasks"
    )

    action = healer._heal_auto_backoff_and_quarantine_failed_tasks(
        "SCAN-TEST", finding, db_conn=temp_db._get_connection()
    )
    assert action.status == "VERIFIED"
    assert action.metrics_after["quarantined_tasks"] >= 1

    # Verify task status was updated to 'quarantined'
    with temp_db._get_connection() as conn:
        row = conn.execute("SELECT status, description FROM tasks WHERE title = 'Stuck Task'").fetchone()
        assert row["status"] == "quarantined"
        assert "Auto-Quarantined" in row["description"]


def test_autonomous_healer_crash_pruning(tmp_path):
    """Tests pruning of aged or excess crash dumps."""
    crash_dir = tmp_path / "crash_reports"
    crash_dir.mkdir(parents=True, exist_ok=True)

    # Create 14 mock crash reports
    for i in range(14):
        p = crash_dir / f"crash_test_{i:02d}.json"
        p.write_text(json.dumps({"error": f"crash {i}"}), encoding="utf-8")

    with patch("fleet.core.auto_healer.CRASH_REPORTS_DIR", crash_dir), \
         patch("fleet.core.auto_healer.MAX_RETAINED_CRASH_DUMPS", 10):
        scanner = ProactiveLogScanner()
        finding = scanner._check_crash_dumps()
        assert finding is not None
        assert finding.category == "CRASH_DUMPS"

        healer = AutonomousAutoHealer()
        action = healer._heal_prune_aged_crash_dumps("SCAN-TEST", finding)
        assert action.status == "VERIFIED"
        assert len(list(crash_dir.glob("crash_*.json"))) == 10


def test_auto_improvements_persistence(temp_db, tmp_path):
    """Tests recording and querying auto-improvements in SQLite and JSON ledger."""
    json_path = tmp_path / "test_auto_imp.json"
    with patch("fleet.core.auto_healer.AUTO_IMPROVEMENTS_JSON", json_path), \
         patch("fleet.core.auto_healer.DB_PATH", temp_db.db_path):

        imp = ImprovementAction(
            scan_id="SCAN-TEST-001",
            issue_type="DATABASE",
            severity="MEDIUM",
            description="High WAL size",
            action_taken="Executed WAL checkpoint. Reclaimed 4.2 MB.",
            status="VERIFIED",
            metrics_before={"wal_size_mb": 4.2},
            metrics_after={"reclaimed_mb": 4.2},
        )

        persist_improvements_to_ledger([imp], db_inst=temp_db)

        # Query from DB mixin
        history = temp_db.list_auto_improvements(limit=10)
        assert len(history) >= 1
        assert history[0]["issue_type"] == "DATABASE"
        assert history[0]["status"] == "VERIFIED"

        stats = temp_db.get_auto_improvements_stats()
        assert stats["total_improvements"] >= 1
        assert "DATABASE" in stats["by_type"]

        # Verify fallback JSON file was created
        assert json_path.exists()
        json_data = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(json_data) >= 1
        assert json_data[0]["scan_id"] == "SCAN-TEST-001"


def test_optimizer_agent_task_execution(temp_db):
    """Verifies that the OptimizerAgent correctly executes the scan_logs_and_heal task."""
    from fleet.agents.optimizer.agent import OptimizerAgent
    agent = OptimizerAgent()

    with patch("fleet.core.auto_healer.run_proactive_log_scan_and_heal") as mock_scan:
        mock_scan.return_value = {
            "scan_id": "SCAN-TEST",
            "logs_analyzed_count": 100,
            "improvements_applied_count": 2,
            "system_health_index": 98.0,
        }

        res = agent.execute_task("scan_logs_and_heal")
        assert res["status"] == "success"
        assert "Proactive Log Scan & Self-Healing Complete" in res["title"]
        assert mock_scan.called


def test_daemon_proactive_log_scan_pulse(temp_db):
    """Tests the FleetDaemon periodic log scan method."""
    from fleet.daemon import FleetDaemon
    daemon = FleetDaemon()
    daemon.bus.db = temp_db

    with patch("fleet.core.auto_healer.run_proactive_log_scan_and_heal") as mock_run:
        mock_run.return_value = {
            "improvements_applied_count": 1,
            "system_health_index": 95.0,
            "scan_id": "SCAN-DAEMON-TEST",
        }

        report = daemon.run_scheduled_log_scan_and_heal()
        assert report["improvements_applied_count"] == 1
        assert mock_run.called


def test_diagnostics_auto_healer_rest_api(temp_db):
    """Tests GET and POST API endpoints for log analysis and auto improvements."""
    from fleet.server import FleetDashboardHandler
    import urllib.parse

    mock_db = temp_db
    handler = FleetDashboardHandler.__new__(FleetDashboardHandler)
    handler.headers = {}
    handler.requestline = "GET /api/diagnostics/auto-improvements HTTP/1.1"
    handler.request_version = "HTTP/1.1"

    captured_json = []
    def mock_send_json(data, status=200):
        captured_json.append((status, data))
    handler._send_json = mock_send_json

    # Test GET /api/diagnostics/auto-improvements
    handler.path = "/api/diagnostics/auto-improvements?limit=10"
    parsed = urllib.parse.urlparse(handler.path)

    with patch("fleet.server.db", mock_db):
        FleetDashboardHandler.do_GET(handler)
        assert len(captured_json) == 1
        status, data = captured_json[0]
        assert status == 200
        assert data["status"] == "success"
        assert "improvements" in data

    # Test POST /api/diagnostics/log-analysis/run
    captured_json.clear()
    handler.path = "/api/diagnostics/log-analysis/run"
    handler.headers = {"Content-Length": "2"}
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = b"{}"

    with patch("fleet.server.db", mock_db), \
         patch("fleet.core.auto_healer.run_proactive_log_scan_and_heal") as mock_scan:
        mock_scan.return_value = {
            "scan_id": "SCAN-POST-TEST",
            "improvements_applied_count": 0,
            "system_health_index": 100.0,
        }
        FleetDashboardHandler.do_POST(handler)
        assert len(captured_json) == 1
        status, data = captured_json[0]
        assert status == 200
        assert data["status"] == "success"
        assert data["report"]["scan_id"] == "SCAN-POST-TEST"
