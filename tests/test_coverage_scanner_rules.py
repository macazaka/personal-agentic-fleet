"""
Unit tests specifically targeting uncovered branches and edge cases in fleet/tools/security_scanner.py
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
import fleet.tools.security_scanner as sec_mod


def test_get_git_executable_fallbacks(tmp_path):
    with patch("shutil.which", return_value=None):
        with patch.object(sec_mod.Path, "is_file", lambda s: str(s).endswith("git.exe")):
            exe = sec_mod._get_git_executable()
            assert "git" in exe.lower()

    with patch("shutil.which", return_value=None):
        with patch.object(sec_mod.Path, "is_file", return_value=False):
            exe = sec_mod._get_git_executable()
            assert exe == "git"


def test_get_tracked_files_git_exception(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    with patch("subprocess.run", side_effect=OSError("Git not found")):
        (tmp_path / "test.py").touch()
        (tmp_path / "test.pyc").touch()
        (tmp_path / "test.db").touch()
        tracked = sec_mod.get_tracked_files(repo_root=tmp_path)
        assert "test.py" in tracked
        assert "test.pyc" not in tracked
        assert "test.db" not in tracked


def test_load_pii_blocklist_edge_cases(tmp_path):
    fake_vault = tmp_path / "uncreatable"
    with patch.object(sec_mod, "USER_VAULT_DIR", fake_vault):
        with patch.object(Path, "mkdir", side_effect=PermissionError("read-only")):
            terms = sec_mod._load_pii_blocklist()
            assert isinstance(terms, list)

    vault_dir = tmp_path / "user_vault"
    vault_dir.mkdir()
    with patch.object(sec_mod, "USER_VAULT_DIR", vault_dir):
        with patch("os.getlogin", return_value="customuser"):
            terms = sec_mod._load_pii_blocklist()
            assert "customuser" in terms

    bad_file = vault_dir / "pii_blocklist.json"
    bad_file.write_text("invalid json{{", encoding="utf-8")
    with patch.object(sec_mod, "USER_VAULT_DIR", vault_dir):
        terms = sec_mod._load_pii_blocklist()
        assert terms == []


def test_security_scanner_hits_and_exceptions(tmp_path):
    (tmp_path / ".gitignore").write_text("*.db\n*.key\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('requires-python = ">=3.10"', encoding="utf-8")
    (tmp_path / ".python-version").touch()
    (tmp_path / "bootstrap.ps1").touch()
    (tmp_path / "bootstrap.sh").touch()

    gh_dir = tmp_path / ".github"
    gh_dir.mkdir()
    (gh_dir / "dependabot.yml").touch()

    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir()
    tools_dir = fleet_dir / "tools"
    tools_dir.mkdir()
    (tools_dir / "sbom_generator.py").touch()
    (tools_dir / "fleet_doctor.py").touch()

    # Secret hit file
    secret_file = tmp_path / "leaked.py"
    prefix = "AIza"
    suffix = "SyD9x8A7B6C5D4E3F2G1H0I9J8K7L6M5N4O3"
    secret_file.write_text(f'KEY = "{prefix}{suffix}"\n', encoding="utf-8")

    # PII hit file
    pii_file = tmp_path / "pii_leak.py"
    pii_file.write_text('user_name = "testuser"\n', encoding="utf-8")

    # Forbidden tracked file
    forbidden_file = tmp_path / "vault.key"
    forbidden_file.write_text("supersecretkey\n", encoding="utf-8")

    # SAST hits and CORS hit
    sast_file = fleet_dir / "sub_test.py"
    sast_file.write_text(
        'subprocess.run(["ls"], shell=True)\n'
        'headers["Access-Control-Allow-Origin"] = "*"\n',
        encoding="utf-8",
    )

    # Deterministic module with paid LLM invocation
    det_file = fleet_dir / "daemon.py"
    det_file.write_text('client = openai.ChatCompletion.create()\n', encoding="utf-8")

    # Server path missing headers
    (fleet_dir / "server.py").write_text("# Incomplete server\n", encoding="utf-8")

    # Agents root with various issues
    agents_dir = fleet_dir / "agents"
    agents_dir.mkdir()

    a1 = agents_dir / "agent1"
    a1.mkdir()

    a2 = agents_dir / "agent2"
    a2.mkdir()
    (a2 / "agent.py").touch()

    a3 = agents_dir / "agent3"
    a3.mkdir()
    (a3 / "agent.py").touch()
    (a3 / "manifest.json").write_text(json.dumps({"permissions": []}), encoding="utf-8")

    a4 = agents_dir / "agent4"
    a4.mkdir()
    (a4 / "agent.py").touch()
    (a4 / "manifest.json").write_text(json.dumps({"permissions": ["unauthorized:perm"]}), encoding="utf-8")

    a5 = agents_dir / "agent5"
    a5.mkdir()
    (a5 / "agent.py").touch()
    (a5 / "manifest.json").write_text("invalid json{{", encoding="utf-8")

    tracked_list = [
        "leaked.py",
        "pii_leak.py",
        "vault.key",
        "fleet/sub_test.py",
        "fleet/daemon.py",
        "fleet/server.py",
    ]

    with patch.object(sec_mod, "get_tracked_files", return_value=tracked_list):
        with patch.object(sec_mod, "_load_pii_blocklist", return_value=["testuser"]):
            fake_log = (
                "commit 1234567890abcdef\n"
                "+++ b/fleet/some_file.py\n"
                "+ leaked testuser pii line\n"
            )
            fake_proc = MagicMock(returncode=0, stdout=fake_log)
            with patch("subprocess.run", return_value=fake_proc):
                with patch("fleet.core.crypto_vault.encrypt_sensitive_text", side_effect=RuntimeError("DPAPI error")):
                    with patch("fleet.config.PREFER_ZERO_TOKEN_CODE", False):
                        with patch("fleet.config.check_minimum_python_version", side_effect=ValueError("version check crashed")):
                            with patch.object(sec_mod, "USER_VAULT_DIR", tmp_path / "missing_vault"):
                                report = sec_mod.run_security_scan(repo_root=tmp_path, save_report=False)
                                assert report["status"] == "FAIL"
                                assert report["score"] == 0
                                assert report["findings_count"] > 0


def test_security_scanner_file_read_exceptions(tmp_path):
    test_f = tmp_path / "fleet" / "test.py"
    test_f.parent.mkdir(parents=True)
    test_f.touch()

    with patch.object(sec_mod, "get_tracked_files", return_value=["fleet/test.py"]):
        with patch.object(Path, "read_text", side_effect=OSError("Read error")):
            with patch.object(sec_mod, "_load_pii_blocklist", return_value=["target"]):
                report = sec_mod.run_security_scan(repo_root=tmp_path, save_report=False)
                assert isinstance(report, dict)


def test_security_scanner_save_report_exception(tmp_path):
    with patch.object(sec_mod, "SECURITY_REPORT_FILE", tmp_path / "nonexistent_dir" / "report.json"):
        with patch.object(Path, "mkdir", side_effect=PermissionError("Denied")):
            report = sec_mod.run_security_scan(repo_root=tmp_path, save_report=True)
            assert isinstance(report, dict)


def test_security_scanner_main_cli():
    fake_report = {
        "status": "FAIL",
        "security_score": 50,
        "files_scanned": 10,
        "checks": [
            {"name": "Check A", "status": "FAIL", "findings_count": 1},
            {"name": "Check B", "status": "PASS", "findings_count": 0},
        ],
        "findings": [
            {"severity": "HIGH", "file": "foo.py", "line": 10, "detail": "Test issue"}
        ],
        "passed_checks": 1,
        "total_checks": 2,
        "findings_count": 1,
    }

    with patch("fleet.tools.security_scanner.run_security_scan", return_value=fake_report):
        with patch("sys.argv", ["security_scanner.py", "--json"]):
            with patch("builtins.print") as mock_print:
                sec_mod.main()
                assert mock_print.called

        with patch("sys.argv", ["security_scanner.py", "--strict"]):
            with patch("sys.exit") as mock_exit:
                sec_mod.main()
                mock_exit.assert_called_with(1)

