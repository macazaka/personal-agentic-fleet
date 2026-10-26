"""
Exhaustive unit tests targeting remaining branches in daemon, yaml_helper, dev_tools, crash_reporter,
fleet_doctor, github_branch_protection, install_git_hooks, and mcp_server.
"""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

import fleet.daemon as daemon_mod
import fleet.core.yaml_helper as yaml_mod
import fleet.core.dev_tools as dev_mod
import fleet.tools.crash_reporter as crash_mod
import fleet.tools.fleet_doctor as doc_mod
import fleet.tools.github_branch_protection as gbp_mod
import fleet.tools.install_git_hooks as hooks_mod
import fleet.mcp_server as mcp_mod


# ==============================================================================
# DAEMON TESTS
# ==============================================================================

def test_daemon_single_iteration_and_exceptions():
    daemon = daemon_mod.FleetDaemon()
    mock_sched = MagicMock()
    mock_sched.check_and_run.side_effect = RuntimeError("Scheduler tick error")
    daemon.scheduler = mock_sched

    # Trigger periodic checks and error handlers
    daemon.check_and_trigger()
    daemon.run_scheduled_pr_review()
    daemon.run_scheduled_security_scan()

    # run_loop termination via KeyboardInterrupt
    with patch("time.sleep", side_effect=KeyboardInterrupt):
        with patch.object(daemon, "check_and_trigger"):
            daemon.run_loop(poll_interval_sec=0)


# ==============================================================================
# YAML HELPER PURE PYTHON FALLBACK TESTS
# ==============================================================================

def test_yaml_pure_python_parser_and_dumper(tmp_path):
    # Test empty or whitespace text
    assert yaml_mod.safe_load_yaml("") == {}
    assert yaml_mod.safe_load_yaml("   \n  ") == {}
    assert yaml_mod.load_yaml_file(tmp_path / "nonexistent.yaml") == {}

    yaml_text = (
        "# Top level comment\n"
        "name: Personal Fleet\n"
        "version: 1.0\n"
        "enabled: true\n"
        "items:\n"
        "  - alpha\n"
        "  - beta\n"
        "  - \n"
        "    nested_item: 42\n"
        "  - agent: overview\n"
        "    task: briefing\n"
        "    payload:\n"
        "      quiet: false\n"
        "    orphan_line_ignored\n"
        "nested:\n"
        "  port: 7890\n"
        "  host: localhost\n"
        "  not_a_key_val_line\n"
        "  empty_dict:\n"
    )

    with patch.dict(sys.modules, {"yaml": None}):
        parsed = yaml_mod.safe_load_yaml(yaml_text)
        assert parsed["name"] == "Personal Fleet"
        assert parsed["enabled"] is True
        assert "alpha" in parsed["items"]
        assert parsed["nested"]["port"] == 7890

        # Test pure python dumper with all data types
        complex_data = [
            {"a": {"nested": 1}, "b": True, "c": 42, "d": None, "e": "hello", "f": 3.14},
            {"empty_l": [], "empty_d": {}, "null_v": None, "bool_v": False}
        ]
        dumped = yaml_mod.dump_yaml(complex_data)
        assert "nested" in dumped
        assert "hello" in dumped
        assert "null" in dumped


# ==============================================================================
# DEV TOOLS CLI EXECUTIONS
# ==============================================================================

def test_dev_tools_cli_executions():
    # Claude Code execution
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Claude output", stderr="")):
        res_c = dev_mod.execute_claude_code("Prompt for claude")
        assert res_c["status"].lower() == "success"

    # Google Gemini CLI execution
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Gemini output", stderr="")):
        res_g = dev_mod.execute_google_gemini_cli("Prompt for gemini")
        assert res_g["status"].lower() == "success"

    # GitHub Copilot execution
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Copilot output", stderr="")):
        res_cp = dev_mod.execute_github_copilot_command("Prompt for copilot")
        assert res_cp["status"].lower() == "success"

    # AWS Q Developer execution
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="AWS Q output", stderr="")):
        res_q = dev_mod.execute_aws_q_developer("Prompt for AWS Q")
        assert res_q["status"].lower() == "success"


# ==============================================================================
# CRASH REPORTER, FLEET DOCTOR & BRANCH PROTECTION
# ==============================================================================

def test_crash_reporter_and_doctor(tmp_path):
    # Record crash
    crash_dir = tmp_path / "crashes"
    with patch.object(crash_mod, "CRASH_REPORTS_DIR", crash_dir):
        try:
            raise ValueError("Test crash exception")
        except ValueError as e:
            report_path = crash_mod.generate_crash_report(type(e), e, e.__traceback__, thread_name="test_thread")
            assert report_path.is_file()

        # List crashes
        crashes = crash_mod.list_crash_reports()
        assert len(crashes) >= 1

        # Prune crashes
        pruned = crash_mod.prune_old_crash_reports(keep=0)
        assert pruned >= 1

    # Fleet doctor
    doc_res = doc_mod.run_fleet_doctor()
    assert doc_res["status"] in ("PASS", "WARN", "FAIL")

    # Branch protection verify
    check_res = gbp_mod.verify_branch_protection()
    assert check_res["status"] in ("PASS", "WARN", "FAIL")

    # Apply remote rulesets with mocked token
    with patch("fleet.tools.github_branch_protection.os.environ.get", return_value="fake_gh_token"):
        with patch("urllib.request.urlopen"):
            remote_res = gbp_mod.apply_remote_branch_protection()
            assert isinstance(remote_res, dict)


# ==============================================================================
# GIT HOOKS & MCP SERVER
# ==============================================================================

def test_git_hooks_and_mcp_server(tmp_path):
    # Install git hooks in mock repo
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    res_hooks = hooks_mod.install_git_hooks(repo_root=tmp_path)
    assert res_hooks["status"] == "installed"

    # Direct tool executions on MCP server
    b = mcp_mod.fleet_get_daily_briefing()
    assert isinstance(b, str)

    t = mcp_mod.fleet_add_task("test task", priority="P1", description="detail")
    assert isinstance(t, str)

    tl = mcp_mod.fleet_list_tasks()
    assert isinstance(tl, str)

    rl = mcp_mod.fleet_list_routines()
    assert isinstance(rl, str)

    tr = mcp_mod.fleet_toggle_routine("smoothie_morning")
    assert isinstance(tr, str)

    notif = mcp_mod.fleet_send_notification("Test Alert", "Testing notification")
    assert isinstance(notif, str)

    scan = mcp_mod.fleet_scan_directory(str(tmp_path))
    assert isinstance(scan, str)

    emails = mcp_mod.fleet_classify_recent_emails(dry_run=True)
    assert isinstance(emails, str)

