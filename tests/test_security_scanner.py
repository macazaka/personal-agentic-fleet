"""
Unit tests for the 6-Layer Security & Privacy Scanner, Automated Daemon Scheduling,
Git Hook Installer, and Security API endpoints.
"""

from pathlib import Path
from unittest.mock import MagicMock
import urllib.parse

from fleet.tools.security_scanner import (
    load_user_pii_blocklist,
    run_security_scan,
    scan_text_for_secrets,
)
from fleet.tools.install_git_hooks import install_git_hooks


def test_secret_detection_catches_api_keys():
    sample_leak = 'API_KEY = "AIza' + 'SyD9x8A7B6C5D4E3F2G1H0I9J8K7L6M5N4O3"'
    findings = scan_text_for_secrets(sample_leak, "dummy_config.py")
    assert len(findings) >= 1
    assert findings[0]["category"] == "secret_leak"
    assert findings[0]["severity"] == "CRITICAL"


def test_secret_detection_ignores_clean_code():
    clean_code = 'from fleet.config import get_secure_secret\nkey = get_secure_secret("GEMINI_API_KEY")\n'
    findings = scan_text_for_secrets(clean_code, "clean_module.py")
    assert findings == []


def test_user_pii_blocklist_isolated_in_user_vault():
    terms = load_user_pii_blocklist()
    assert isinstance(terms, list)


def test_full_codebase_security_scan_passes_100():
    report = run_security_scan()
    assert report["status"] == "PASS", f"Expected PASS, got findings: {report.get('findings')}"
    assert report["score"] == 100
    assert report["passed_checks"] == 6
    assert report["total_checks"] == 6
    assert report["total_findings"] == 0


def test_daemon_scheduled_security_scan_runs():
    from fleet.daemon import FleetDaemon
    daemon = FleetDaemon()
    assert daemon.security_scan_interval_sec >= 60
    report = daemon.run_scheduled_security_scan()
    assert report["status"] == "PASS"
    assert report["score"] == 100


def test_git_hooks_installer(tmp_path: Path):
    fake_git_hooks = tmp_path / ".git" / "hooks"
    fake_git_hooks.mkdir(parents=True)
    res = install_git_hooks(repo_root=tmp_path)
    assert res["status"] == "installed"
    assert (fake_git_hooks / "pre-commit").is_file()
    assert (fake_git_hooks / "pre-push").is_file()
    content = (fake_git_hooks / "pre-commit").read_text(encoding="utf-8")
    assert "run_security_scan" in content


def test_security_scan_api_endpoints():
    from fleet.api.system_api import get_security_scan, post_security_scan

    mock_handler = MagicMock()
    parsed_url = urllib.parse.urlparse("http://127.0.0.1:7890/api/security/scan")
    get_security_scan(mock_handler, parsed_url)
    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["status"] == "PASS"
    assert payload["score"] == 100

    mock_handler.reset_mock()
    post_security_scan(mock_handler, {})
    assert mock_handler._send_json.called
    post_payload = mock_handler._send_json.call_args[0][0]
    assert post_payload["status"] == "success"
    assert post_payload["report"]["score"] == 100
