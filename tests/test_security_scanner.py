"""
Unit tests for the 10-Layer Security & Privacy Scanner, DPAPI At-Rest Crypto Vault,
Localhost DNS-Rebinding/CSRF Session Guard, Plugin Capability Sandbox, CycloneDX SBOM,
Automated Daemon Scheduling, Git Hook Installer, and Security API endpoints.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock
import urllib.parse
import pytest

from fleet.core.crypto_vault import decrypt_sensitive_text, encrypt_sensitive_text
from fleet.core.database import FleetDatabase
from fleet.core.plugin_sandbox import (
    ScopedDatabaseProxy,
    get_sanitized_plugin_env,
    validate_manifest_permissions,
)
from fleet.core.session_auth import get_session_cookie_header, validate_request_security
from fleet.tools.install_git_hooks import install_git_hooks
from fleet.tools.sbom_generator import generate_sbom
from fleet.tools.security_scanner import (
    load_user_pii_blocklist,
    run_security_scan,
    scan_text_for_secrets,
)


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
    assert report["passed_checks"] == 10
    assert report["total_checks"] == 10
    assert report["total_findings"] == 0


def test_dpapi_crypto_vault_roundtrip_and_tamper_detection():
    secret_val = "super_confidential_oauth_refresh_token_2026"
    encrypted = encrypt_sensitive_text(secret_val)
    assert encrypted.startswith("ENC:v1:")
    assert secret_val not in encrypted

    decrypted = decrypt_sensitive_text(encrypted)
    assert decrypted == secret_val

    # Verify HMAC tamper detection
    tampered = encrypted[:-4] + ("AAAA" if not encrypted.endswith("AAAA") else "BBBB")
    with pytest.raises( Exception ):
        decrypt_sensitive_text(tampered)

    # Verify SQLite encrypted settings integration
    db = FleetDatabase()
    db.set_encrypted_setting("test_vault_secret", "my_encrypted_db_value")
    assert db.get_encrypted_setting("test_vault_secret") == "my_encrypted_db_value"


def test_session_auth_dns_rebinding_and_csrf_guard():
    allowed_origins = {"http://127.0.0.1:7890", "http://localhost:7890"}
    cookie_hdr = get_session_cookie_header()
    assert "HttpOnly" in cookie_hdr
    assert "SameSite=Strict" in cookie_hdr

    # Legitimate localhost request passes
    ok, _ = validate_request_security(
        {"Host": "127.0.0.1:7890", "Origin": "http://127.0.0.1:7890"},
        "POST",
        allowed_origins,
    )
    assert ok is True

    # DNS Rebinding attack via evil Host header is blocked
    ok, reason = validate_request_security(
        {"Host": "evil-rebind.attacker.com:7890"},
        "GET",
        allowed_origins,
    )
    assert ok is False
    assert "DNS Rebinding blocked" in reason

    # Cross-Origin POST from external website is blocked
    ok, reason = validate_request_security(
        {"Host": "127.0.0.1:7890", "Origin": "https://malicious-site.com"},
        "POST",
        allowed_origins,
    )
    assert ok is False
    assert "Cross-Origin POST blocked" in reason

    # Fetch Metadata cross-site request is blocked
    ok, reason = validate_request_security(
        {"Host": "127.0.0.1:7890", "Sec-Fetch-Site": "cross-site"},
        "POST",
        allowed_origins,
    )
    assert ok is False
    assert "Sec-Fetch-Site" in reason


def test_plugin_capability_sandbox_enforcement():
    assert validate_manifest_permissions("test_agent", ["db:read", "ui:render"]) == []
    assert validate_manifest_permissions("test_agent", ["root:shell_exec"]) == ["root:shell_exec"]

    db = FleetDatabase()
    read_only_proxy = ScopedDatabaseProxy(db, "untrusted_plugin", permissions=["db:read", "ui:render"])

    # Read operation succeeds
    tasks = read_only_proxy.list_tasks()
    assert isinstance(tasks, list)

    # Write operation raises PermissionError
    with pytest.raises(PermissionError, match="without 'db:write' permission"):
        read_only_proxy.add_task("Unauthorized task", "Should be blocked")

    # Environment variable sanitizer strips secret keys
    os.environ["TEMP_TEST_API_SECRET_KEY"] = "secret123"
    clean_env = get_sanitized_plugin_env()
    assert "TEMP_TEST_API_SECRET_KEY" not in clean_env
    os.environ.pop("TEMP_TEST_API_SECRET_KEY", None)


def test_cyclonedx_sbom_generator_and_api():
    sbom = generate_sbom(save_to_disk=True)
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["component_count"] >= 50

    from fleet.api.system_api import get_security_sbom
    mock_handler = MagicMock()
    parsed_url = urllib.parse.urlparse("http://127.0.0.1:7890/api/security/sbom")
    get_security_sbom(mock_handler, parsed_url)
    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["bomFormat"] == "CycloneDX"


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
    parsed_url = urllib.parse.urlparse("http://127.0.0.1:7890/api/security/scan?refresh=true")
    get_security_scan(mock_handler, parsed_url)
    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["status"] == "PASS"
    assert payload["score"] == 100
    assert payload["passed_checks"] == 10

    mock_handler.reset_mock()
    post_security_scan(mock_handler, {})
    assert mock_handler._send_json.called
    post_payload = mock_handler._send_json.call_args[0][0]
    assert post_payload["status"] == "success"
    assert post_payload["report"]["score"] == 100
