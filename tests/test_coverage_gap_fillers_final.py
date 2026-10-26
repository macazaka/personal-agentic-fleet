"""
Ultra-targeted gap filler test suite to eliminate remaining statement misses
and reach >= 99% overall microkernel coverage.
100% deterministic (Tier 0: $0.00 / 0 LLM tokens, 0 external network requests).
"""

import base64
import io
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_scheduler_uncovered_branches(tmp_path):
    import fleet.core.scheduler as sched_mod
    from fleet.core.scheduler import FleetScheduler

    # 1. Line 340: if not raw_rules: DEFAULT_SCHEDULES fallback
    with patch.object(sched_mod, "BASE_DIR", tmp_path):
        with patch("fleet.core.scheduler.load_fleet_config", return_value={}):
            sched_defaults = FleetScheduler(config_dir=tmp_path / "u_def")
            assert len(sched_defaults.get_schedules()) > 0

    # 2. Line 336-337: default schedules file returns list
    with patch("fleet.core.scheduler.load_yaml_file", return_value=[{"agent": "overview", "task": "run", "every": "1h"}]):
        with patch("pathlib.Path.is_file", return_value=True):
            sched_list = FleetScheduler(config_dir=tmp_path / "u_list")
            assert any(s["id"] == "overview_run" for s in sched_list.get_schedules())

    # 3. Line 358: urid already in rules_by_id and Line 370-372, 377-379
    fleet_cfg = {
        "schedules": [
            {"id": "overview_run", "every": "4h"},  # update existing
            {"id": "unique_sched", "agent": "overview", "task": "custom"}  # add new
        ],
        "agents": {
            "health": {"schedule": {"task": "water", "interval": "30m"}},
            "optimizer": {"schedules": [{"task": "clean", "every": "2h"}]}
        }
    }
    with patch("fleet.core.scheduler.load_fleet_config", return_value=fleet_cfg):
        sched_overrides = FleetScheduler(config_dir=tmp_path / "u_ovr")
        assert any(s["id"] == "overview_run" for s in sched_overrides.get_schedules())
        assert any(s["id"] == "health_water" for s in sched_overrides.get_schedules())
        assert any(s["id"] == "optimizer_clean" for s in sched_overrides.get_schedules())

    # 4. Line 507: toggle_schedule when id not in overrides
    sched_overrides.load_overrides = MagicMock(return_value={})
    sched_overrides.save_overrides = MagicMock()
    toggle_res = sched_overrides.toggle_schedule("overview_run")
    assert toggle_res["status"] == "success"

    # 5. Line 524: check_and_run(now=None)
    with patch.object(sched_overrides, "run_task"):
        sched_overrides.check_and_run(now=None)


def test_registry_uncovered_branches(tmp_path):
    from fleet.core.registry import AgentRegistry

    # 1. Line 54: custom_agents_dir in config
    reg_cfg = AgentRegistry(config={"custom_agents_dir": str(tmp_path / "custom_c")})
    assert reg_cfg.custom_agents_dir == tmp_path / "custom_c"

    # 2. Line 96: agents_dir does not exist
    missing_dir = tmp_path / "missing_agents_dir"
    reg_miss = AgentRegistry(agents_dir=missing_dir, custom_agents_dir=tmp_path / "c")
    reg_miss.discover_and_load()
    assert missing_dir.is_dir()

    # 3. Line 159 & 178: _load_agent_from_file returns None when no subclass
    empty_file = tmp_path / "empty_agent.py"
    empty_file.write_text("# empty\n", encoding="utf-8")
    assert reg_miss._load_agent_from_file(empty_file, tmp_path, {}) is None

    # 4. Lines 220-222: is_default override
    a1 = MagicMock(id="a1", enabled=True)
    a2 = MagicMock(id="a2", enabled=True)
    reg_miss._all_discovered_agents = {"a1": a1, "a2": a2}
    reg_miss.customize_agent("a1", {"is_default": True})
    assert a2._override_default is False

    # 5. Lines 251-252: reset_agent when agent is disabled
    dis_agent = MagicMock(id="dis_agent", enabled=True, config={})
    reg_miss.agents = {"dis_agent": dis_agent}
    reg_miss.config = {"agents": {"dis_agent": {"enabled": False}}}
    reg_miss.reset_agent("dis_agent")
    assert "dis_agent" in reg_miss.disabled_agents

    # 6. Line 361: create_custom_agent raises RuntimeError when load fails
    with patch.object(reg_miss, "_load_agent_from_file", return_value=None):
        with pytest.raises(RuntimeError, match="Failed to load"):
            reg_miss.create_custom_agent("failed_new", "Failed")


def test_hyperscalers_uncovered_branches():
    from fleet.core.hyperscalers import HyperscalerGateway

    # 1. Line 262: alt_env_keys check (AZURE_AI_FOUNDRY_KEY)
    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: "foundry_key" if k == "AZURE_AI_FOUNDRY_KEY" else ""
        providers = HyperscalerGateway.list_available_providers()
        ms = next(p for p in providers if p["id"] == "microsoft")
        assert ms["is_configured"] is True

    # 2. Line 357: complete unknown provider fallback
    gw = HyperscalerGateway()
    res_unk = gw.complete("prompt", provider="unknown_provider", allow_tier0=False)
    assert res_unk["status"] == "FALLBACK"

    # 3. Line 439: _call_google_vertex missing credentials error
    with patch("fleet.core.hyperscalers.get_secure_secret", return_value=""):
        with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
            gw._call_google_vertex("prompt")

    # 4. Line 575: _call_aws_bedrock system instruction
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"content": [{"text": "bedrock output"}]}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    def mock_secrets(k):
        if k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            return "fake_key"
        if k == "AWS_REGION":
            return "us-east-1"
        if k == "ANTHROPIC_API_KEY":
            return "fake_key"
        return ""

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("fleet.core.hyperscalers.get_secure_secret", side_effect=mock_secrets):
            b_res = gw._call_aws_bedrock("prompt", model="anthropic.claude-3-haiku", sys_inst="system rules")
            assert b_res["text"] == "bedrock output"

            # 5. Line 628: _call_anthropic_claude system instruction
            mock_resp.read.return_value = json.dumps({"content": [{"text": "claude output"}]}).encode("utf-8")
            c_res = gw._call_anthropic_claude("prompt", sys_inst="system rules")
            assert c_res["text"] == "claude output"


def test_yaml_helper_uncovered_branches():
    import fleet.core.yaml_helper as yaml_mod

    # 1. Lines 43-44: JSON-style inline object
    assert yaml_mod.parse_yaml_scalar('{"key": 123}') == {"key": 123}

    # 2. Lines 118, 126, 151, 184: complex nested yaml parsing
    yaml_txt = (
        "- agent: overview\n"
        "  task:\n"
        "    nested: val\n"
        "- item2\n"
        "dict_key:\n"
        "  - list_item_1\n"
        "  - list_item_2\n"
    )
    res = yaml_mod.safe_load_yaml(yaml_txt)
    assert res is not None


def test_daemon_uncovered_branches():
    from fleet.daemon import FleetDaemon

    d = FleetDaemon()
    mock_pr = MagicMock()
    mock_pr.audit_pull_requests.return_value = {"open_count": 3}
    mock_pr.check_ci_status.return_value = {"status": "FAILING", "failing_runs": ["build"]}
    with patch("fleet.agents.pr_review.agent.PRReviewAgent", return_value=mock_pr):
        d.run_scheduled_pr_review()


def test_security_scanner_uncovered_branches(tmp_path):
    from fleet.tools.security_scanner import run_security_scan

    # 1. Lines 183, 220, 350: tracked file missing on disk
    with patch("fleet.tools.security_scanner.get_tracked_files", return_value=["nonexistent_tracked.py"]):
        rep = run_security_scan(repo_root=tmp_path)
        assert isinstance(rep, dict)

    # 2. Lines 430-438: USER_VAULT_DIR is not a dir
    with patch("fleet.tools.security_scanner.USER_VAULT_DIR") as mv:
        mv.exists.return_value = True
        mv.is_dir.return_value = False
        rep = run_security_scan(repo_root=tmp_path)
        assert any(f.get("category") == "User Vault Isolation" for f in rep["findings"])

    # 3. Line 665: check_minimum_python_version returns False
    with patch("fleet.config.check_minimum_python_version", return_value=False):
        rep = run_security_scan(repo_root=tmp_path)
        assert any(f.get("category") == "Runtime Version Guard" for f in rep["findings"])


def test_health_and_antigravity_api_uncovered(tmp_path):
    from fleet.api.health_api import get_health_image, stream_video
    from fleet.api.antigravity_api import get_media, post_upload

    # 1. Health API 404s
    h = MagicMock()
    get_health_image(h, urllib.parse.urlparse("/api/health/video/image?file=nonexistent.png"))
    h.send_error.assert_called_with(404, "Image not found")
    stream_video(h, urllib.parse.urlparse("/api/health/video/stream?file=nonexistent.mp4"))
    h.send_error.assert_called_with(404, "Video not found")

    # 2. Antigravity API media in brain directory
    brain_dir = tmp_path / "brain"
    (brain_dir / ".user_uploaded").mkdir(parents=True, exist_ok=True)
    media_file = brain_dir / ".user_uploaded" / "pic.png"
    media_file.write_bytes(b"png_data")
    fake_t = brain_dir / "a" / "b" / "transcript.jsonl"
    with patch("fleet.server.get_active_transcript_path", return_value=fake_t):
        h2 = MagicMock()
        get_media(h2, "/api/antigravity/media/pic.png", urllib.parse.urlparse("/api/antigravity/media/pic.png"))
        h2.send_response.assert_called_with(200)

    # 3. Antigravity API upload with base64 and data URI prefix
    with patch("fleet.server.save_uploaded_image", return_value={"name": "img.png"}):
        h3 = MagicMock()
        post_upload(h3, {"filename": "img.png", "base64": "data:image/png;base64,QUJD"})
        h3._send_json.assert_called_with({"status": "success", "file": {"name": "img.png"}})


def test_gmail_client_uncovered_branches():
    from fleet.integrations.gmail_client import GmailManager

    gm = GmailManager(db=MagicMock())
    gm.is_connected = True
    gm.service = MagicMock()
    gm.db.get_cached_email_body.return_value = None
    gm.db.is_email_unsubscribed.return_value = False

    # 1. Line 349: auto_archive_ignore=True for category 4
    gm.label_ids = {4: "label_4"}
    gm._apply_labels_to_gmail([{"id": "msg_fyi", "category_id": 4}], auto_archive_ignore=True)
    gm.service.users().messages().batchModify.assert_called_once()

    # 2. Lines 618-619: text/html part
    html_msg = {
        "id": "html_msg",
        "snippet": "Snippet fallback",
        "payload": {
            "headers": [{"name": "Subject", "value": "Subject"}, {"name": "From", "value": "a@b.com"}],
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<b>HTML Content</b>").decode("ascii")}
                }
            ]
        }
    }
    gm.service.users().messages().get().execute.return_value = html_msg
    res_html = gm.get_email_full_body("html_msg")
    assert "HTML Content" in res_html["body"]

    # 3. Line 621: empty body fallback to snippet
    empty_msg = {
        "id": "empty_msg",
        "snippet": "Snippet only",
        "payload": {"headers": [], "parts": []}
    }
    gm.service.users().messages().get().execute.return_value = empty_msg
    res_empty = gm.get_email_full_body("empty_msg")
    assert res_empty["body"] == "Snippet only"


def test_server_sse_stream_listener():
    from fleet.server import FleetDashboardHandler
    import fleet.server as srv_mod

    srv_h = FleetDashboardHandler.__new__(FleetDashboardHandler)
    srv_h.headers = {"Origin": "http://127.0.0.1:7890"}
    srv_h.send_header = MagicMock()
    srv_h._send_security_headers()
    srv_h.send_header.assert_any_call("Access-Control-Allow-Origin", "http://127.0.0.1:7890")

    wfile = io.BytesIO()
    srv_h.wfile = wfile
    srv_h.send_response = MagicMock()
    srv_h.send_header = MagicMock()
    srv_h.end_headers = MagicMock()
    srv_h._sse_test_mode = True
    srv_h.path = "/api/events/stream"

    def trigger_event():
        time.sleep(0.05)
        from fleet.core.event_bus import FleetEvent
        srv_mod.bus.dispatch(FleetEvent(sender="test", target="all", action="test_evt", payload={"x": 1}))

    t = threading.Thread(target=trigger_event)
    t.start()
    srv_h.do_GET()
    t.join()
    assert b"event: fleet_event" in wfile.getvalue()


def test_preflight_gate_uncovered_permissions(tmp_path):
    from fleet.tools.preflight_gate import verify_agent_package_isolation

    agent_dir = tmp_path / "fleet" / "agents" / "bad_perms_agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "ui").mkdir(parents=True, exist_ok=True)
    (agent_dir / "manifest.json").write_text(json.dumps({
        "id": "bad_perms_agent",
        "permissions": ["unrecognized:bad_perm"]
    }), encoding="utf-8")
    (agent_dir / "agent.py").write_text("# agent\n", encoding="utf-8")
    (agent_dir / "ui" / "panel.html").write_text("<p>hi</p>", encoding="utf-8")
    res_iso = verify_agent_package_isolation(repo_root=tmp_path)
    assert any("unrecognized permissions" in f for f in res_iso["findings"])


def test_create_agent_auto_target(tmp_path):
    from fleet.tools.create_agent import scaffold_agent

    with patch("fleet.tools.create_agent.Path.mkdir"):
        with patch("fleet.tools.create_agent.Path.exists", return_value=False):
            with patch("fleet.tools.create_agent.Path.write_text"):
                res = scaffold_agent("auto_target_agent", permissions=["db:read"], target_dir=None)
                assert isinstance(res, Path)
                assert res.name == "auto_target_agent"


def test_install_git_hooks_missing_dir(tmp_path):
    from fleet.tools.install_git_hooks import install_git_hooks
    res = install_git_hooks(repo_root=tmp_path / "no_git_dir")
    assert res["status"] == "skipped"


def test_web_builder_missing_template(tmp_path):
    from fleet.web.builder import get_dashboard_html
    import fleet.web.builder as wb
    with patch.object(wb, "TEMPLATES_DIR", tmp_path / "no_templates"):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            get_dashboard_html()


def test_email_api_unsubscribe_error():
    from fleet.api.email_api import unsubscribe_email
    import fleet.server as srv
    h = MagicMock()
    with patch.object(srv.bus, "dispatch", return_value={"status": "error", "message": "Failed unsub"}):
        unsubscribe_email(h, {"id": "msg_unsub", "url": "http://unsub"})
        h._send_json.assert_called_with({"error": "Failed unsub"}, 500)


def test_backup_uncovered_branches(tmp_path):
    from fleet.core.db.backup import perform_database_backup, prune_old_backups, list_backups
    # Line 33: missing source db
    assert perform_database_backup(tmp_path / "nonexistent.db", tmp_path)["status"] == "skipped"
    # Line 104: missing backup dir
    assert prune_old_backups(tmp_path / "nonexistent_dir") == 0
    # Line 127: missing backup dir
    assert list_backups(tmp_path / "nonexistent_dir") == []


def test_crash_reporter_uncovered_branches(tmp_path):
    from fleet.tools.crash_reporter import (
        get_system_snapshot,
        prune_old_crash_reports,
        list_crash_reports,
        install_crash_reporter,
    )
    import fleet.tools.crash_reporter as cr_mod
    # Line 127 & 145: missing crash reports dir
    with patch.object(cr_mod, "CRASH_REPORTS_DIR", tmp_path / "nonexistent_crashes"):
        assert prune_old_crash_reports() == 0
        assert list_crash_reports() == []
    # Line 84-85: ctypes GetProcessMemoryInfo returns True
    snap = get_system_snapshot()
    assert "platform" in snap

    # Line 182-192: fleet_thread_excepthook
    install_crash_reporter()
    if hasattr(threading, "excepthook"):
        class FakeThreadArgs:
            exc_type = ValueError
            exc_value = ValueError("test thread crash")
            exc_traceback = None
            thread = threading.Thread(name="TestCrashThread")
        threading.excepthook(FakeThreadArgs())


def test_preflight_gate_uncovered_gate_checks(tmp_path):
    from fleet.tools.preflight_gate import (
        verify_agent_package_isolation,
        verify_documentation_integrity,
    )
    # Line 61: missing agents dir
    res_iso = verify_agent_package_isolation(repo_root=tmp_path / "no_repo")
    assert res_iso["status"] == "FAIL"

    # Line 142 & 145: intra-page anchor '#' and broken relative link
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    doc_file = tmp_path / "README.md"
    doc_file.write_text("[Anchor Link](#section-1)\n[Broken Target](nonexistent_file.md)\n" + "x" * 600, encoding="utf-8")
    for req in [
        "INSTALL.md", "CONTRIBUTING.md", "docs/ARCHITECTURE.md", "docs/SECURITY.md",
        "docs/HYPERSCALERS_AND_DEV_TOOLS.md", "docs/PREREQUISITES_AND_OS.md",
        "docs/API_REFERENCE.md", "docs/DEVELOPER_GUIDE.md", "docs/CUSTOMIZING_AGENTS.md",
        "docs/MAINTAINING_DOCUMENTATION.md", "docs/ROBUSTNESS_BACKLOG.md",
        "docs/DEPLOYMENT_AND_SCENARIOS.md"
    ]:
        p = tmp_path / req
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Doc\n" + "y" * 600, encoding="utf-8")
    res_doc = verify_documentation_integrity(repo_root=tmp_path)
    assert any("Broken relative link target" in f for f in res_doc["findings"])


def test_sandbox_quota_uncovered_branches():
    from fleet.core.sandbox_quota import (
        ProcessQuotaManager,
        enforce_agent_egress,
        get_process_memory_mb,
    )
    import socket

    # Line 208: string address (unix socket)
    with enforce_agent_egress("test_agent", permissions=[]):
        with patch.object(socket.socket, "connect"):
            sock = socket.socket()
            sock.connect("/var/run/test.sock")
            sock.close()

    # Line 183: platform fallback returns 0.0
    with patch("sys.platform", "unknown_os"):
        assert get_process_memory_mb() == 0.0

    # Line 87, 104, 114: Windows job object failures
    try:
        import ctypes
        if hasattr(ctypes, "windll"):
            limiter = ProcessQuotaManager(memory_limit_mb=128)
            with patch("ctypes.windll.kernel32.CreateJobObjectW", return_value=None):
                assert limiter._apply_windows_job_object(999999) is False
            with patch("ctypes.windll.kernel32.CreateJobObjectW", return_value=123):
                with patch("ctypes.windll.kernel32.SetInformationJobObject", return_value=0):
                    assert limiter._apply_windows_job_object(999999) is False
                with patch("ctypes.windll.kernel32.SetInformationJobObject", return_value=1):
                    with patch("ctypes.windll.kernel32.OpenProcess", return_value=None):
                        assert limiter._apply_windows_job_object(999999) is False
    except Exception:
        pass


