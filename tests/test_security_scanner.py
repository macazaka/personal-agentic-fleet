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
    assert report["tokens_used"] == 0
    assert report["cost_usd"] == "$0.00"
    assert report["passed_checks"] == 11
    assert report["total_checks"] == 11
    assert report["total_findings"] == 0


def test_zero_token_deterministic_router_and_prompt_compressor():
    from fleet.core.token_optimizer import (
        cache_prompt_response,
        compress_prompt,
        get_cached_prompt_response,
        get_token_optimization_stats,
        try_deterministic_intent_route,
    )

    db = FleetDatabase()

    # 1. Deterministic Security Scan Route (0 tokens)
    sec_res = try_deterministic_intent_route("scan security", db=db)
    assert sec_res is not None
    assert sec_res["tokens_used"] == 0
    assert sec_res["cost_usd"] == "$0.00"

    # 2. Deterministic Hydration Route (0 tokens)
    water_res = try_deterministic_intent_route("log water 2", db=db)
    assert water_res is not None
    assert water_res["tokens_used"] == 0
    assert "+500 ml" in water_res["message"]

    # 3. Normalized Prompt Cache (0 tokens on repeat query)
    cache_prompt_response("What is the FFD breakfast ratio?", "25% sprouts, 25% raw salad, 50% cooked dal.")
    cached = get_cached_prompt_response("  what is the   ffd breakfast ratio? ")
    assert cached == "25% sprouts, 25% raw salad, 50% cooked dal."

    # 4. Prompt Compressor strips comments & excess whitespace
    bloated = "Hello   world<!-- comment -->\n\n\n\nNext paragraph"
    comp = compress_prompt(bloated)
    assert comp["text"] == "Hello world\n\nNext paragraph"
    assert comp["chars_saved"] > 0

    stats = get_token_optimization_stats()
    assert stats["security_scan_token_cost"] == 0
    assert stats["tier0_deterministic_hits"] >= 2


def test_advanced_8_layer_token_reduction_methods():
    from fleet.core.token_optimizer import (
        cache_prompt_response,
        check_mcp_delta_response,
        coalesce_queued_prompts,
        compress_prompt,
        deduplicate_uploaded_image,
        get_cached_prompt_response,
        query_local_knowledge_base,
        select_optimal_model_tier,
    )

    # 1. Local Offline BM25 Knowledge RAG answers FFD & Workout questions at 0 tokens
    smoothie_rag = query_local_knowledge_base("What is the FFD green smoothie recipe and timing?")
    assert smoothie_rag is not None
    assert smoothie_rag["tokens_used"] == 0
    assert "Major Green" in smoothie_rag["message"]

    workout_rag = query_local_knowledge_base("What is my Mudgal and Samtola workout schedule?")
    assert workout_rag is not None
    assert workout_rag["tokens_used"] == 0
    assert "Monday" in workout_rag["message"] and "Wednesday" in workout_rag["message"]

    hypo_rag = query_local_knowledge_base("How to handle hypoglycemia when BSL is below 70?")
    assert hypo_rag is not None
    assert "3 tsp sugar" in hypo_rag["message"]

    # 2. Fuzzy Semantic Cache catches paraphrased repeat questions (0 tokens)
    cache_prompt_response(
        "Explain the lunch and dinner 25% quad plate formula",
        "25% raw salad, 25% cooked veg, 25% dal, 25% single low-GI grain.",
    )
    fuzzy_hit = get_cached_prompt_response("Please tell me the lunch & dinner 25% quad plate formula!")
    assert fuzzy_hit == "25% raw salad, 25% cooked veg, 25% dal, 25% single low-GI grain."

    # 3. Code-Block AST/Tokenize Minifier strips Python comments inside prompts
    code_prompt = "Fix this:\n```python\n# This is a noisy comment that wastes tokens\ndef add(a, b):\n    # Another comment\n    return a + b\n```"
    minified = compress_prompt(code_prompt)
    assert "noisy comment" not in minified["text"]
    assert "def add(a, b):" in minified["text"]

    # 4. Queued Prompt Coalescer merges multiple prompts to save ~8,000+ system context tokens per item
    queued_items = [
        {"id": 101, "prompt": "Summarize today's P1 tasks", "images": [], "model": "gemini-3.8-flash-high"},
        {"id": 102, "prompt": "Check pending backlog items", "images": [], "model": "gemini-3.8-flash-high"},
        {"id": 103, "prompt": "List hydration goal status", "images": [], "model": "gemini-3.8-flash-high"},
    ]
    coalesced = coalesce_queued_prompts(queued_items)
    assert len(coalesced) == 1
    assert coalesced[0]["merged_ids"] == [101, 102, 103]
    assert "### Task 1:" in coalesced[0]["prompt"] and "### Task 3:" in coalesced[0]["prompt"]

    # 5. Budget-Aware Model Tier Downgrade (>70% usage forces Flash tier)
    downgraded = select_optimal_model_tier(
        "Perform deep architectural analysis",
        requested_model="claude-opus-5-5-medium",
        token_usage_pct=75.0,
    )
    assert downgraded == "gemini-3.8-flash-high"

    # 6. SHA-256 Image Deduplication prevents duplicate vision token billing
    sample_img = b"\x89PNG\r\n\x1a\n_dummy_image_payload_bytes"
    first_upload = deduplicate_uploaded_image(sample_img, lambda: {"filename": "img1.png", "size": len(sample_img)})
    assert first_upload["deduplicated"] is False
    second_upload = deduplicate_uploaded_image(sample_img, lambda: {"filename": "img2.png", "size": len(sample_img)})
    assert second_upload["deduplicated"] is True
    assert second_upload["filename"] == "img1.png"

    # 7. Delta-Only MCP State-Hash Cache skips redundant context dumps
    full_briefing = "Daily Briefing: 3 P1 tasks, 5 habits."
    first_mcp = check_mcp_delta_response("briefing_test_tool", full_briefing)
    assert first_mcp == full_briefing
    second_mcp = check_mcp_delta_response("briefing_test_tool", full_briefing)
    assert "State unchanged since last" in second_mcp


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
    assert payload["passed_checks"] == 11

    mock_handler.reset_mock()
    post_security_scan(mock_handler, {})
    assert mock_handler._send_json.called
    post_payload = mock_handler._send_json.call_args[0][0]
    assert post_payload["status"] == "success"
    assert post_payload["report"]["score"] == 100


def test_minimum_python_version_guard():
    from fleet.config import MIN_PYTHON_VERSION, check_minimum_python_version
    assert MIN_PYTHON_VERSION == (3, 10)
    assert check_minimum_python_version((3, 10, 0)) is True
    assert check_minimum_python_version((3, 14, 7)) is True
    with pytest.raises(RuntimeError, match="Python 3.10 or higher is required"):
        check_minimum_python_version((3, 9, 18))
