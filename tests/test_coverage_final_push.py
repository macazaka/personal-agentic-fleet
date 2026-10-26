"""
Final push test suite designed to elevate total microkernel test coverage to >= 99%.
All tests are 100% deterministic (Tier 0: $0.00 / 0 LLM tokens, 0 network egress).
"""

import base64
import collections
import io
import json
import logging
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==============================================================================
# 1. FLEET CORE SCHEDULER
# ==============================================================================

def test_scheduler_deep_branches(tmp_path):
    import fleet.core.scheduler as sched_mod
    from fleet.core.scheduler import FleetScheduler

    # 1. Test base defaults loaded as list
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "schedules.yaml").write_text("- agent: overview\n  task: run\n  every: 1h\n", encoding="utf-8")

    with patch.object(sched_mod, "BASE_DIR", tmp_path):
        fleet_cfg = {
            "schedules": [{"agent": "overview", "task": "run", "every": "2h"}],
            "agents": {
                "health": {
                    "schedule": {"task": "water_reminder", "interval": "45m"}
                },
                "optimizer": {
                    "schedules": [
                        {"id": "opt_clean", "task": "clean_temp", "every": "4h"}
                    ]
                }
            }
        }
        with patch("fleet.core.scheduler.load_fleet_config", return_value=fleet_cfg):
            sched = FleetScheduler(config_dir=tmp_path / "user_cfg")
            rules = sched.get_schedules()
            assert any(r["id"] == "health_water_reminder" for r in rules)
            assert any(r["id"] == "opt_clean" for r in rules)

    # 2. Test times as list of strings
    sched = FleetScheduler(config_dir=tmp_path / "user_cfg")
    parsed_rule = sched._normalize_rule({
        "agent": "test",
        "task": "daily",
        "times": ["08:00", "12:00", "18:00"],
    })
    assert parsed_rule["times"] == ["08:00", "12:00", "18:00"]

    # 3. Test cron schedule in check_and_run
    cron_rule = sched._normalize_rule({
        "id": "cron_test_task",
        "agent": "overview",
        "task": "pulse",
        "schedule_type": "cron",
        "cron": "* * * * *",
        "enabled": True,
    })
    sched.schedules = [cron_rule]
    now_dt = datetime(2026, 10, 26, 14, 30)
    with patch.object(sched, "run_task", return_value={"status": "SUCCESS"}):
        results = sched.check_and_run(now=now_dt)
        assert len(results) == 1
        # Second run in same minute should be deduplicated
        results2 = sched.check_and_run(now=now_dt)
        assert len(results2) == 0

    # 4. Test run_task dispatch via AgentRegistry agent instance having execute_task
    mock_reg = MagicMock()
    mock_agent = MagicMock()
    mock_agent.execute_task.return_value = {"status": "SUCCESS", "data": "agent_executed"}
    mock_reg.agents = {"custom_agent": mock_agent}
    sched.registry = mock_reg

    task_res = sched.run_task({
        "id": "custom_agent_task",
        "agent": "custom_agent",
        "task": "audit",
        "payload": {"depth": "full"}
    })
    assert task_res["status"] == "SUCCESS"
    assert task_res["result"] == {"status": "SUCCESS", "data": "agent_executed"}


# ==============================================================================
# 2. FLEET CORE HYPERSCALERS
# ==============================================================================

def test_hyperscalers_deep_branches():
    from fleet.core.hyperscalers import (
        HyperscalerGateway,
        _sign_aws_sigv4_headers,
    )

    # 1. Test aws_sigv4_headers with session token
    headers = _sign_aws_sigv4_headers(
        method="POST",
        url="https://bedrock-runtime.us-east-1.amazonaws.com/model/anthropic.claude-3-haiku-20240307-v1:0/invoke",
        payload_bytes=b'{"prompt": "hello"}',
        access_key="AKIA1234567890",
        secret_key="secret1234567890",
        region="us-east-1",
        service="bedrock",
        session_token="session_token_xyz"
    )
    assert headers.get("X-Amz-Security-Token") == "session_token_xyz"

    # 2. Test list_available_providers with env_key and alt_env_keys
    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: "mock_val" if k in ("GEMINI_API_KEY", "AZURE_OPENAI_API_KEY") else ""
        providers = HyperscalerGateway.list_available_providers()
        gemini_p = next(p for p in providers if p["id"] == "google")
        azure_p = next(p for p in providers if p["id"] == "microsoft")
        assert gemini_p["is_configured"] is True
        assert azure_p["is_configured"] is True

    # 3. Test HyperscalerGateway complete with Tier 0 RAG & Semantic Cache
    gw = HyperscalerGateway()
    with patch("fleet.core.hyperscalers.query_local_knowledge_base", return_value={"message": "RAG Response"}):
        res_rag = gw.complete("What is HbA1c?", allow_tier0=True)
        assert res_rag["tier"] == "TIER_0_RAG"
        assert res_rag["text"] == "RAG Response"

    with patch("fleet.core.hyperscalers.get_cached_prompt_response", return_value="Cached answer"):
        res_cache = gw.complete("How to optimize memory?", allow_tier0=True)
        assert res_cache["tier"] == "TIER_0_CACHE"
        assert res_cache["text"] == "Cached answer"

    # 4. Test provider 'auto' detection
    with patch.object(gw, "list_available_providers", return_value=[{"id": "ollama", "is_configured": True}]):
        with patch.object(gw, "_call_ollama", return_value={"status": "SUCCESS", "text": "ollama output"}):
            res_auto = gw.complete("test prompt", provider="auto", allow_tier0=False)
            assert res_auto["text"] == "ollama output"

    # 5. Test _call_google with google-vertex- prefix and system instruction
    with patch.object(gw, "_call_google_vertex", return_value={"status": "SUCCESS", "text": "vertex output"}) as mock_v:
        res = gw._call_google("test", model="google-vertex-gemini-2.5-flash", sys_inst="Be helpful")
        assert res["text"] == "vertex output"
        mock_v.assert_called_once()

    # 6. Test _call_google_vertex gcloud auth token fallback & missing credentials error
    with patch.dict(os.environ, {"FLEET_TEST_MODE": "0"}, clear=False):
        with patch("fleet.core.hyperscalers.get_secure_secret", return_value=""):
            with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="gcloud_token_123\n")):
                with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
                    gw._call_google_vertex("test prompt")

    # 7. Test AWS Bedrock shapes: content, message, results, generation, and Anthropic Claude
    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: "secret" if "KEY" in k or "PROJECT" in k else ""

        # Test Bedrock with generation format
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"generation": "bedrock generation output"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            b_res = gw._call_aws_bedrock("prompt", model="amazon.titan-text-express-v1", sys_inst="sys prompt")
            assert b_res["text"] == "bedrock generation output"

        # Test Bedrock with Claude sys_inst
        mock_resp.read.return_value = json.dumps({"content": [{"text": "bedrock claude output"}]}).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            b_claude = gw._call_aws_bedrock("prompt", model="anthropic.claude-3-5-sonnet", sys_inst="be concise")
            assert b_claude["text"] == "bedrock claude output"

        # Test direct Claude API with sys_inst
        mock_resp.read.return_value = json.dumps({"content": [{"text": "direct claude output"}]}).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            c_res = gw._call_anthropic_claude("prompt", sys_inst="system rules")
            assert c_res["text"] == "direct claude output"


# ==============================================================================
# 3. YAML HELPER
# ==============================================================================

def test_yaml_helper_deep_coverage():
    import fleet.core.yaml_helper as yaml_mod

    # 1. Test dump_yaml with PyYAML mocked in sys.modules
    mock_yaml = MagicMock()
    mock_yaml.dump.return_value = "yaml_dump_output: true\n"
    with patch.dict(sys.modules, {"yaml": mock_yaml}):
        res = yaml_mod.dump_yaml({"key": "val"})
        assert res == "yaml_dump_output: true\n"

    # 2. Test dump_yaml pure-Python fallback with dict containing [], {}, None, bool, float
    with patch.dict(sys.modules, {"yaml": None}):
        d = {
            "empty_list": [],
            "empty_dict": {},
            "null_val": None,
            "bool_val": True,
            "float_val": 42.5,
            "items": [
                {"name": "sub1", "empty_nested": {}, "null_sub": None, "sub_list": [1, 2]},
                "scalar_item"
            ]
        }
        res_pure = yaml_mod.dump_yaml(d)
        assert "empty_list: []" in res_pure
        assert "empty_dict: {}" in res_pure
        assert "null_val: null" in res_pure
        assert "bool_val: true" in res_pure
        assert "float_val: 42.5" in res_pure
        assert "scalar_item" in res_pure


# ==============================================================================
# 4. DEV TOOLS CLI
# ==============================================================================

def test_dev_tools_deep_coverage(tmp_path):
    from fleet.core.dev_tools import (
        detect_developer_tools,
        execute_aws_q_developer,
        execute_claude_code,
    )

    # 1. Test detect_developer_tools candidate file paths
    with patch("shutil.which", return_value=None):
        with patch("pathlib.Path.is_file", return_value=True):
            tools = detect_developer_tools()
            assert tools["gemini_cli"]["installed"] is True
            assert tools["claude_code"]["installed"] is True
            assert tools["github_copilot"]["installed"] is True
            assert tools["aws_q"]["installed"] is True
            assert tools["cursor"]["installed"] is True
            assert tools["ollama"]["installed"] is True

    # 2. Test execute_claude_code timeout branch
    with patch("fleet.core.dev_tools.detect_developer_tools", return_value={"claude_code": {"installed": True, "path": "claude"}}):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120)):
            res = execute_claude_code("test prompt")
            assert res["status"] == "error"
            assert "timed out" in res["message"]

    # 3. Test execute_aws_q_developer with binary path ending in 'q'
    with patch("fleet.core.dev_tools.detect_developer_tools", return_value={"aws_q": {"installed": True, "path": "/usr/bin/q"}}):
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="AWS Q Output", stderr="")):
            res = execute_aws_q_developer("explain S3")
            assert res["status"] == "success"
            assert res["output"] == "AWS Q Output"


# ==============================================================================
# 5. CRYPTO VAULT
# ==============================================================================

def test_crypto_vault_deep_coverage(tmp_path):
    import fleet.core.crypto_vault as cv

    # 1. Test set_secure_secret with keyring
    mock_kr = MagicMock()
    with patch.dict(sys.modules, {"keyring": mock_kr}):
        assert cv.set_secure_secret("TEST_KEY", "secret_val") is True
        mock_kr.set_password.assert_called_once_with("fleet_os", "TEST_KEY", "secret_val")

    # 2. Test _dpapi_encrypt_bytes and _dpapi_decrypt_bytes on non-win32
    with patch.object(cv.sys, "platform", "linux"):
        assert cv._dpapi_encrypt_bytes(b"data") is None
        assert cv._dpapi_decrypt_bytes(b"data") is None

    # 3. Test get_or_create_master_key with 64-hex env key and 32-byte raw file
    with patch("fleet.core.crypto_vault.get_secure_secret", return_value="a" * 64):
        key = cv.get_or_create_master_key()
        assert len(key) == 32
        assert key == bytes.fromhex("a" * 64)

    with patch("fleet.core.crypto_vault.get_secure_secret", return_value=""):
        fake_key_file = tmp_path / "master.dpapi"
        fake_key_file.write_bytes(b"B" * 32)
        with patch.object(cv, "MASTER_KEY_FILE", fake_key_file):
            with patch.object(cv, "_dpapi_decrypt_bytes", return_value=None):
                key2 = cv.get_or_create_master_key()
                assert key2 == b"B" * 32

    # 4. Test decrypt_sensitive_text with DPAPI prefix and corrupted length
    with patch.object(cv, "_dpapi_decrypt_bytes", return_value=b"decrypted_dpapi_text"):
        b64_dpapi = base64.urlsafe_b64encode(b"ciphertext").decode("ascii")
        dec = cv.decrypt_sensitive_text(f"{cv.DPAPI_PREFIX}{b64_dpapi}")
        assert dec == "decrypted_dpapi_text"

    # Corrupted payload (<48 bytes)
    short_b64 = base64.urlsafe_b64encode(b"short").decode("ascii")
    with pytest.raises(ValueError, match="Corrupted encrypted payload"):
        cv.decrypt_sensitive_text(f"{cv.ENCRYPTION_PREFIX}{short_b64}")


# ==============================================================================
# 6. SECURITY SCANNER & PREFLIGHT GATE
# ==============================================================================

def test_security_scanner_and_preflight_deep_coverage(tmp_path):
    from fleet.tools.security_scanner import run_security_scan
    from fleet.tools.preflight_gate import (
        run_preflight_gate,
        verify_agent_package_isolation,
        verify_documentation_integrity,
    )

    # 1. Security scan: test Git History PII exposure hit
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    git_log_output = (
        "commit 12345678\n"
        "+++ b/some_file.py\n"
        "+ user_secret_token_12345 = 'leak'\n"
    )
    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=git_log_output)):
        with patch("fleet.tools.security_scanner._load_pii_blocklist", return_value=["user_secret_token"]):
            report = run_security_scan(repo_root=tmp_path)
            assert any(f.get("category") == "Git History PII Exposure" for f in report["findings"])

    # 2. Security scan: missing user vault dir hit & failed crypto check
    with patch("fleet.tools.security_scanner.USER_VAULT_DIR") as mock_vault:
        mock_vault.exists.return_value = False
        mock_vault.is_dir.return_value = False
        with patch("fleet.core.crypto_vault.decrypt_sensitive_text", return_value="wrong"):
            report = run_security_scan(repo_root=tmp_path)
            assert any(f.get("category") == "User Vault Isolation" for f in report["findings"])
            assert any(f.get("category") == "At-Rest Encryption" for f in report["findings"])

    # 3. Preflight gate: verify_agent_package_isolation error branches
    (tmp_path / "fleet" / "agents" / "bad_agent" / "ui").mkdir(parents=True, exist_ok=True)
    (tmp_path / "fleet" / "agents" / "bad_agent" / "manifest.json").write_text(
        json.dumps({"id": "wrong_id", "permissions": "not_a_list"}), encoding="utf-8"
    )
    iso_res = verify_agent_package_isolation(repo_root=tmp_path)
    assert iso_res["status"] == "FAIL"
    assert any("does not match directory name" in f for f in iso_res["findings"])
    assert any("permissions must be a list" in f for f in iso_res["findings"])

    # 4. Preflight gate: verify_documentation_integrity stub file & broken link
    doc_file = tmp_path / "README.md"
    doc_file.write_text("Short content.\n[Broken](nonexistent.md)", encoding="utf-8")
    with patch("fleet.tools.preflight_gate.REQUIRED_DOCUMENTS", ["README.md"]):
        doc_res = verify_documentation_integrity(repo_root=tmp_path)
        assert doc_res["status"] == "FAIL"
        assert any("incomplete or stub" in f for f in doc_res["findings"])

    # 5. Preflight gate: run_preflight_gate failures
    with patch("fleet.tools.preflight_gate.run_fleet_doctor", return_value={"status": "FAIL", "security_score": 50}):
        assert run_preflight_gate(repo_root=tmp_path) == 1

    with patch("fleet.tools.preflight_gate.run_fleet_doctor", return_value={"status": "PASS", "security_score": 100, "python_version": "3.11"}):
        with patch("fleet.tools.preflight_gate.run_security_scan", return_value={"status": "FAIL", "total_findings": 1}):
            assert run_preflight_gate(repo_root=tmp_path) == 1


# ==============================================================================
# 7. GITHUB BRANCH PROTECTION & CRASH REPORTER
# ==============================================================================

def test_github_branch_protection_and_crash_reporter(tmp_path):
    import urllib.error
    from fleet.tools.github_branch_protection import (
        apply_remote_branch_protection,
        main as bp_main,
        verify_branch_protection,
    )
    import fleet.tools.crash_reporter as cr

    # 1. Branch protection: missing pre-push hook and invalid ruleset
    (tmp_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    bp_json = tmp_path / ".github" / "branch-protection.json"
    bp_json.parent.mkdir(parents=True, exist_ok=True)
    bp_json.write_text(json.dumps({"target": "tag", "enforcement": "disabled"}), encoding="utf-8")

    res = verify_branch_protection(repo_root=tmp_path)
    assert res["status"] == "FAIL"
    assert any("must have target='branch'" in i for i in res["issues"])
    assert any("Missing .git/hooks/pre-push hook" in i for i in res["issues"])

    # 2. Remote apply branch protection: HTTPError branch
    fake_ruleset = tmp_path / ".github" / "rulesets" / "main-branch.json"
    fake_ruleset.parent.mkdir(parents=True, exist_ok=True)
    fake_ruleset.write_text("{}", encoding="utf-8")
    
    mock_err = urllib.error.HTTPError(
        url="http://test", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"Requires admin")
    )
    with patch("fleet.tools.github_branch_protection.EXPECTED_RULESET_FILES", ["main-branch.json"]):
        with patch("urllib.request.urlopen", side_effect=mock_err):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token"}):
                apply_res = apply_remote_branch_protection(repo_root=tmp_path)
                assert apply_res["status"] == "PARTIAL_OR_ERROR"
                assert len(apply_res["errors"]) == 1

    # 3. Main CLI with --strict
    with patch("sys.argv", ["bp", "--strict"]):
        with patch("fleet.tools.github_branch_protection.verify_branch_protection", return_value={"status": "FAIL", "protected_branch": "main", "policy_file": "p", "rulesets_verified": [], "codeowners_file": "c", "local_pre_push_guard": False, "issues": ["error"]}):
            assert bp_main() == 1

    # 4. Crash reporter: hooks and process snapshot
    snap = cr.get_system_snapshot()
    assert isinstance(snap, dict)
    assert "pid" in snap

    cr.install_crash_reporter()
    try:
        raise ValueError("test crash")
    except ValueError as e:
        sys.excepthook(type(e), e, e.__traceback__)


# ==============================================================================
# 8. FLEET DOCTOR, POWER & SANDBOX QUOTA
# ==============================================================================

def test_doctor_power_sandbox(tmp_path):
    from fleet.core.power import PowerLifecycleManager
    from fleet.core.sandbox_quota import (
        ProcessQuotaManager,
        enforce_agent_egress,
        get_process_memory_mb,
    )
    from fleet.tools.fleet_doctor import harden_user_vault_permissions, run_fleet_doctor

    # 1. Fleet doctor: empty username fallback & missing directory
    vault_dir = tmp_path / "vault_test"
    with patch.dict(os.environ, {"USERNAME": ""}, clear=False):
        with patch("os.getlogin", side_effect=Exception("no login")):
            h_res = harden_user_vault_permissions(vault_dir)
            assert h_res["status"] == "PASS"

    with patch("fleet.tools.fleet_doctor.check_minimum_python_version", side_effect=RuntimeError("Python too old")):
        doc_res = run_fleet_doctor(repo_root=tmp_path)
        assert doc_res["status"] == "FAIL"

    # 2. Power manager: _monitoring_loop with sleep gap
    pm = PowerLifecycleManager(gap_threshold_sec=5.0)
    stop_called = False

    def fake_resume(sleep_duration):
        nonlocal stop_called
        stop_called = True

    pm._handle_system_resume = fake_resume

    times = [100.0, 150.0]  # 50 second gap > 5.0
    with patch("time.time", side_effect=lambda: times.pop(0) if times else 200.0):
        with patch("time.sleep"):
            # Run loop for 1 iteration
            pm._stop_event = MagicMock()
            pm._stop_event.is_set.side_effect = [False, True]
            pm._monitoring_loop()
            assert stop_called is True

    # 3. Sandbox quota: POSIX setrlimit & egress str address
    pq = ProcessQuotaManager(memory_limit_mb=256)
    mock_res = MagicMock()
    with patch.dict(sys.modules, {"resource": mock_res}):
        assert pq._apply_posix_rlimit() is True
        mock_res.setrlimit.assert_called_once()

    # Address as string (Unix socket path)
    with enforce_agent_egress("overview", ["network:none"]):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with patch("socket.socket.connect", return_value=None) as mock_conn:
            s.connect("some_unix_socket_path")
            mock_conn.assert_called_once()
        s.close()


# ==============================================================================
# 9. TOKEN OPTIMIZER & FLEET DAEMON
# ==============================================================================

def test_token_optimizer_and_daemon(tmp_path):
    import fleet.core.token_optimizer as to_mod
    from fleet.core.token_optimizer import (
        coalesce_queued_prompts,
        get_cached_prompt_response,
        select_optimal_model_tier,
        try_deterministic_intent_route,
    )
    from fleet.daemon import FleetDaemon

    # 1. Token optimizer: expired cache hit
    to_mod._PROMPT_CACHE["test_expired_key"] = {
        "ts": time.time() - 99999,
        "response": "old",
        "prompt": "test prompt",
    }
    assert get_cached_prompt_response("test prompt") is None

    # 2. coalesce_queued_prompts with single item
    assert len(coalesce_queued_prompts([{"id": "1", "prompt": "hi"}])) == 1

    # 3. select_optimal_model_tier routine short prompt
    tier = select_optimal_model_tier("What is the time?", requested_model=None)
    assert tier == "gemini-3.8-flash-high"

    # 4. try_deterministic_intent_route empty string
    assert try_deterministic_intent_route("") is None

    # 5. Daemon scheduled pulse triggers & warnings
    daemon = FleetDaemon()
    daemon.last_security_scan_time = 0.0
    daemon.last_pr_review_time = 0.0
    daemon.last_spool_flush_time = 0.0

    with patch.object(daemon, "run_scheduled_security_scan") as mock_sec:
        with patch.object(daemon, "run_scheduled_pr_review") as mock_pr:
            with patch("fleet.core.network_spool.flush_offline_spool"):
                daemon.check_and_trigger()
                mock_sec.assert_called_once()
                mock_pr.assert_called_once()

    # Daemon run_scheduled_security_scan with warning toast
    with patch("fleet.tools.security_scanner.run_security_scan", return_value={"score": 80, "status": "WARN", "total_findings": 2}):
        with patch.object(daemon.bus, "dispatch") as mock_disp:
            daemon.run_scheduled_security_scan()
            mock_disp.assert_called_once()


# ==============================================================================
# 10. AGENT REGISTRY & OPTIMIZER
# ==============================================================================

def test_registry_and_optimizer_deep(tmp_path):
    from fleet.core.registry import AgentRegistry
    import fleet.core.optimizer as opt_mod
    from fleet.api.router import ApiRouter

    # 1. AgentRegistry custom_agents_dir in config and is_default override
    reg = AgentRegistry(
        config={"custom_agents_dir": str(tmp_path / "custom"), "default_agent": "overview"},
        agents_dir=tmp_path / "builtin",
    )
    agent1 = MagicMock(id="agent1", enabled=True, is_default=False)
    agent2 = MagicMock(id="agent2", enabled=True, is_default=False)
    reg.agents = {"agent1": agent1, "agent2": agent2}
    reg._all_discovered_agents = {"agent1": agent1, "agent2": agent2}

    reg.customize_agent("agent1", {"is_default": True})
    assert agent2._override_default is False

    # 2. Test create_custom_agent invalid ID
    with pytest.raises(ValueError, match="Invalid agent ID"):
        reg.create_custom_agent("", "Empty")

    # 3. Test register_all_routes POST custom create
    router = ApiRouter()
    reg.register_all_routes(router)
    handler = MagicMock()
    with patch.object(reg, "create_custom_agent", return_value={"id": "new_agent"}):
        router.dispatch_post(handler, "/api/fleet/agents/custom/create", {"id": "new_agent"})
        handler._send_json.assert_called_with({"status": "success", "agent": {"id": "new_agent"}})

    # 4. Optimizer: memory diagnostics Darwin & Linux failure branches
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
        assert opt_mod._get_memory_status_darwin() is None

    with patch("pathlib.Path.is_file", return_value=False):
        assert opt_mod._get_memory_status_linux() is None

    # clean_temp_files
    clean_target = PROJECT_ROOT / "fleet" / "data" / "user" / "temp_clean_test_dir"
    clean_target.mkdir(parents=True, exist_ok=True)
    (clean_target / "test_artifact.txt").write_text("artifact", encoding="utf-8")
    with patch("tempfile.gettempdir", return_value=str(clean_target)):
        res = opt_mod.clean_temp_files()
        assert res["deleted_files"] >= 1
    if clean_target.exists():
        shutil.rmtree(clean_target, ignore_errors=True)


# ==============================================================================
# 11. ANTIGRAVITY MIRROR, SESSION AUTH & MCP SERVER
# ==============================================================================

def test_antigravity_mirror_session_auth_mcp(tmp_path):
    import fleet.core.antigravity_mirror as ag_mod
    import fleet.core.session_auth as sa_mod
    import fleet.mcp_server as mcp_mod

    # 1. Antigravity mirror: token health status "exhausted"
    mock_db = MagicMock()
    mock_db.get_setting.return_value = "exhausted"
    mock_db.get_vaulted_prompts.return_value = []
    with patch.object(ag_mod, "db", mock_db):
        h = ag_mod.get_token_health()
        assert h["status"] == "exhausted"

    # Antigravity command dispatching to deterministic intent router
    with patch("fleet.core.token_optimizer.try_deterministic_intent_route", return_value={"status": "tier0_success"}):
        cmd_res = ag_mod.execute_dashboard_command("system status")
        assert cmd_res == {"status": "tier0_success"}

    # 2. Session auth: empty headers & sliding window rate limiter
    assert sa_mod.validate_request_security({}, "GET", set()) == (True, "ok")

    sa_mod._REQUEST_TIMESTAMPS.clear()
    now = time.time()
    # Add expired timestamps
    sa_mod._REQUEST_TIMESTAMPS.append(now - 100)
    assert sa_mod.check_rate_limit() == (True, "ok")

    # Fill rate limit to max
    for _ in range(sa_mod.RATE_LIMIT_MAX_REQUESTS + 5):
        sa_mod._REQUEST_TIMESTAMPS.append(time.time())
    lim_ok, lim_msg = sa_mod.check_rate_limit()
    assert lim_ok is False
    assert "Rate limit exceeded" in lim_msg
    sa_mod._REQUEST_TIMESTAMPS.clear()

    # 3. MCP server tools
    with patch("fleet.server.agent_registry.customize_agent", return_value={"id": "overview"}):
        res = mcp_mod.fleet_customize_agent(
            agent_id="overview",
            icon="🚀",
            is_default=True,
            provider="google",
            model="gemini-2.5-pro",
            system_prompt="Custom instructions"
        )
        assert "overview" in res

    with patch("fleet.core.scheduler.get_fleet_scheduler") as mock_sched:
        mock_sched.return_value.get_schedules.return_value = []
        assert mcp_mod.fleet_list_schedules() == "No agent schedules configured."

        mock_sched.return_value.toggle_schedule.return_value = {"status": "error", "message": "Not found"}
        assert "Error: Not found" in mcp_mod.fleet_toggle_schedule("invalid_id")

        mock_sched.return_value.run_now.return_value = {"status": "ERROR", "result": {"error": "Failed to run"}}
        assert "Failed to execute task" in mcp_mod.fleet_run_scheduled_task(schedule_id="invalid")


# ==============================================================================
# 12. SETTINGS API, SERVER & CONFIG
# ==============================================================================

def test_settings_server_config(tmp_path):
    from fleet.api.settings_api import create_backup_snapshot, update_fleet_settings
    from fleet.api.system_api import post_run_tests
    import fleet.config as cfg_mod
    from fleet.server import FleetDashboardHandler

    # 1. Settings API: non-dict update & backup snapshot
    handler = MagicMock()
    update_fleet_settings(handler, {"settings": "not_a_dict"})
    handler._send_json.assert_called_with({"status": "error", "message": "Expected a JSON object of settings"}, status=400)

    # Backup snapshot with real file
    fake_db = tmp_path / "fleet.db"
    fake_db.write_text("sqlite format 3", encoding="utf-8")
    with patch("fleet.api.settings_api.DATA_DIR", tmp_path):
        create_backup_snapshot(handler, {})
        assert any(call[0][0].get("status") == "success" for call in handler._send_json.call_args_list)

    # 2. System API post_run_tests
    with patch("fleet.tools.test_runner.run_test_suite_isolated", return_value={"passed": 100}):
        post_run_tests(handler, {})
        handler._send_json.assert_called_with({"status": "success", "results": {"passed": 100}})

    # 3. Server: _send_security_headers with Origin in ALLOWED_ORIGINS
    server_h = FleetDashboardHandler.__new__(FleetDashboardHandler)
    server_h.headers = {"Origin": "http://127.0.0.1:7890"}
    server_h.send_header = MagicMock()
    server_h._send_security_headers()
    server_h.send_header.assert_any_call("Access-Control-Allow-Origin", "http://127.0.0.1:7890")

    # 4. Config: fleet.json loader
    fleet_json = tmp_path / "fleet.json"
    fleet_json.write_text(json.dumps({"app_name": "Fleet JSON Test"}), encoding="utf-8")
    with patch.object(cfg_mod, "BASE_DIR", tmp_path):
        loaded_cfg = cfg_mod.load_fleet_config()
        assert loaded_cfg.get("app_name") == "Fleet JSON Test"


# ==============================================================================
# 13. EXERCISE, LIFECYCLE, GMAIL & REMAINING MICROKERNEL MODULES
# ==============================================================================

def test_exercise_lifecycle_gmail_and_more(tmp_path):
    from fleet.agents.pr_review.agent import PRReviewAgent
    from fleet.core.base_agent import FleetAgent
    from fleet.core.briefing import BriefingEngine
    from fleet.core.db.base import BaseDatabase
    from fleet.core.db.migrations import apply_migrations
    from fleet.core.db.pool import SQLiteConnectionPool
    from fleet.core.exercise_manager import get_video_type_and_category, list_exercise_videos
    from fleet.core.http_client import ResilientHttpClient
    import fleet.core.lifecycle as lc_mod
    from fleet.core.logger import JsonLogFormatter, RingBufferLogHandler
    from fleet.core.network_spool import flush_offline_spool, is_network_available
    from fleet.core.plugin_sandbox import ScopedDatabaseProxy
    from fleet.core.rate_limiter import RateLimiter, check_rate_limit
    from fleet.core.supervisor import FleetSupervisor
    from fleet.integrations.gmail_client import GmailManager
    try:
        import pong
        import pygame
        has_pong = True
    except Exception:
        has_pong = False

    # 1. Exercise manager: categories and missing directory
    assert get_video_type_and_category("chair_stretch.mp4")[1] == "Desk & Office Conditioning"
    assert get_video_type_and_category("random_movement.mp4")[1] == "Exercise & Conditioning"
    with patch("fleet.core.exercise_manager.FFD_VIDEOS_DIR", tmp_path / "nonexistent"):
        assert list_exercise_videos() == []

    # 2. Lifecycle: closed stream in _safe_log and clean shutdown early exit
    mock_handler = MagicMock()
    mock_handler.stream.closed = True
    with patch("logging.root.handlers", [mock_handler]):
        lc_mod._safe_log("test message")

    with patch.object(lc_mod, "_SHUTDOWN_TRIGGERED", True):
        lc_mod.execute_clean_shutdown()

    # 3. Base agent: non-int order & custom setting fallback
    class ConcreteAgent(FleetAgent):
        @property
        def id(self): return "concrete"
        @property
        def name(self): return "Concrete"
        @property
        def icon(self): return "🧱"

    ca = ConcreteAgent(agent_dir=tmp_path, config={"order": "invalid_int", "custom_prop": "custom_val"})
    assert ca.display_order == 100
    assert ca.get_setting("custom_prop") == "custom_val"

    # 4. Briefing engine with metabolic profile
    mock_db = MagicMock()
    mock_db.get_metabolic_profile.return_value = {"days_remaining": 60, "target_hba1c": 6.2, "target_weight_kg": 74.0}
    mock_db.list_medications.return_value = [{"taken_today": True}]
    mock_db.get_all_tasks.return_value = []
    mock_db.get_vaulted_prompts.return_value = []
    be = BriefingEngine(db=mock_db)
    briefing = be.generate_daily_briefing()
    assert "Metabolic Goal" in briefing["briefing_markdown"]

    # 5. Network spool: is_network_available & flush_offline_spool noop
    with patch("socket.socket.connect", return_value=None):
        assert is_network_available() is True
    with patch("socket.socket.connect", side_effect=OSError("down")):
        assert is_network_available() is False

    with patch("fleet.core.network_spool.is_network_available", return_value=True):
        with patch("fleet.core.network_spool.list_spooled_events", return_value=[]):
            spool_res = flush_offline_spool(MagicMock())
            assert spool_res["status"] == "noop"

    # 6. Plugin sandbox: non-callable attr and permission errors
    mock_raw_db = MagicMock()
    mock_raw_db.db_path = "/path/to/db"
    proxy = ScopedDatabaseProxy(raw_db=mock_raw_db, agent_id="test", permissions=["db:read"])
    assert proxy.db_path == "/path/to/db"

    with pytest.raises(PermissionError, match="lacks 'db:read'"):
        ScopedDatabaseProxy(raw_db=mock_raw_db, agent_id="test", permissions=[]).get_tasks()

    # 7. Rate limiter: bucket cleanup > 1000 and check_rate_limit helper
    limiter = RateLimiter()
    limiter._buckets = {f"k_{i}": MagicMock(last_update=time.time() - 400) for i in range(1005)}
    limiter.check("new_key")
    assert len(limiter._buckets) <= 10

    assert check_rate_limit("127.0.0.1")[0] is True

    # 8. Pong: AI paddle moving down & POINT_SCORED overlay draw
    if has_pong:
        game = pong.PingPongGame()
        game.ai_y = 100
        game.ball.y = 300
        game.update_ai()
        assert game.ai_y > 100

        game.state = "POINT_SCORED"
        game.point_timer = 0
        with patch("pygame.time.get_ticks", return_value=500):
            game.draw()

    # 9. PR Review Agent: GITHUB_TOKEN set
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_mock_token"}):
        pr_agent = PRReviewAgent()
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps([]).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp
            pr_res = pr_agent.audit_pull_requests()
            assert pr_res["status"] == "SUCCESS"

    # 10. Migrations: nonexistent DB
    assert apply_migrations(tmp_path / "nonexistent.db")["status"] == "skipped"

    # 11. Base DB: get_encrypted_setting default fallback
    bdb = BaseDatabase(db_path=tmp_path / "test.db")
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value.execute.return_value.fetchone.return_value = None
    with patch.object(bdb, "_get_connection", return_value=mock_conn):
        assert bdb.get_encrypted_setting("missing_key", default="fallback_val") == "fallback_val"

    # 12. Pool: get_connection creating parent directory
    pool = SQLiteConnectionPool()
    conn = pool.get_connection(tmp_path / "nested" / "dir" / "test.db")
    assert (tmp_path / "nested" / "dir").is_dir()
    conn.close()

    # 13. Logger: non-dict metadata
    rec = logging.LogRecord("test", logging.INFO, "file.py", 10, "msg", (), None)
    rec.metadata = "scalar_metadata"
    jf = JsonLogFormatter()
    formatted = jf.format(rec)
    assert '"raw": "scalar_metadata"' in formatted

    rbuf = RingBufferLogHandler(capacity=10)
    rbuf.emit(rec)
    assert len(rbuf._buffer) == 1

    # 14. Supervisor: register already existing worker & auto_start
    sup = FleetSupervisor()
    sup._running = True
    sup.register_worker("worker1", lambda: None, restart_strategy="temporary", auto_start=False)
    # Re-register
    w2 = sup.register_worker("worker1", lambda: None, restart_strategy="temporary", auto_start=True)
    assert w2 is not None
    sup.stop()

    # 15. HTTP client: last_error is None
    client = ResilientHttpClient(max_retries=0)
    with pytest.raises(RuntimeError, match="Request failed with unknown error"):
        client.request("http://localhost", retries=-1)

    # 16. Gmail manager: known_ids=None & auto_archive_ignore=True
    gm = GmailManager(db=mock_db)
    gm.is_connected = True
    gm.service = MagicMock()
    gm.service.users().messages().list().execute.return_value = {"messages": []}
    assert gm._fetch_real_emails("is:unread", known_ids=None) == []

    gm.label_ids = {3: "label_3"}
    gm._apply_labels_to_gmail([{"id": "msg_1", "category_id": 3}], auto_archive_ignore=True)
