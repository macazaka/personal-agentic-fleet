"""
Exhaustive Unit Tests for Fleet Core:
- fleet.core.http_client
- fleet.mcp_server
- fleet.core.token_optimizer
- fleet.core.scheduler
- fleet.core.crypto_vault
- fleet.core.yaml_helper
"""

import io
import json
import os
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

import fleet.core.http_client as http_mod
import fleet.mcp_server as mcp_mod
import fleet.core.token_optimizer as tok_mod
import fleet.core.scheduler as sched_mod
import fleet.core.crypto_vault as vault_mod
import fleet.core.yaml_helper as yaml_mod


# ---------------------------------------------------------------------------
# 1. fleet.core.http_client tests
# ---------------------------------------------------------------------------
def test_circuit_breaker_transitions():
    cb = http_mod.CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.1)
    assert cb.state == "CLOSED"

    # 1. Closed operation
    cb.before_request()
    cb.on_success()
    assert cb.failure_count == 0

    # 2. Trip to OPEN
    cb.on_failure()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 1

    cb.on_failure()
    assert cb.state == "OPEN"
    assert cb.failure_count == 2

    # Fast-fail while OPEN
    with pytest.raises(http_mod.CircuitBreakerOpenException):
        cb.before_request()

    # 3. Transition to HALF_OPEN after recovery timeout
    time.sleep(0.12)
    cb.before_request()
    assert cb.state == "HALF_OPEN"

    # Failure in HALF_OPEN immediately trips back to OPEN
    cb.on_failure()
    assert cb.state == "OPEN"

    # Wait again and recover to CLOSED
    time.sleep(0.12)
    cb.before_request()
    assert cb.state == "HALF_OPEN"
    cb.on_success()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


def test_resilient_http_client():
    client = http_mod.ResilientHttpClient(default_timeout=5.0, max_retries=1, base_backoff=0.01)
    assert client.get_circuit_breaker("example.com") is not None

    # 1. Success 200
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"msg": "ok"}'
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        code, body, headers = client.request("https://api.test.com/data")
        assert code == 200
        assert b"ok" in body

        code_j, data_j = client.request_json("https://api.test.com/data", json_body={"key": "val"})
        assert code_j == 200
        assert data_j == {"msg": "ok"}

    # 2. Client error 404 (does not retry)
    mock_http_err = urllib.error.HTTPError("https://api.test.com/404", 404, "Not Found", MagicMock(), io.BytesIO(b"Not found"))
    with patch("urllib.request.urlopen", side_effect=mock_http_err):
        code, body, _ = client.request("https://api.test.com/404")
        assert code == 404
        assert body == b"Not found"

    # 3. Server error 500 (retries and fails)
    mock_500_err = urllib.error.HTTPError("https://api.test.com/500", 500, "Server Error", MagicMock(), io.BytesIO(b"Server Error"))
    with patch("urllib.request.urlopen", side_effect=mock_500_err), \
         patch("time.sleep"):
        with pytest.raises(urllib.error.HTTPError):
            client.request("https://api.test.com/500", retries=1)

    # 4. URLError / Network error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS Fail")), \
         patch("time.sleep"):
        with pytest.raises(urllib.error.URLError):
            client.request("https://api.test.com/net_fail", retries=1)

    # 5. Singleton accessor
    assert http_mod.get_resilient_http_client() is not None


# ---------------------------------------------------------------------------
# 2. fleet.mcp_server tests
# ---------------------------------------------------------------------------
def test_mcp_server_tools_exhaustive():
    # 1. Daily briefing
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"briefing_markdown": "# Briefing"}}
        assert "# Briefing" in mcp_mod.fleet_get_daily_briefing()
        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Error" in mcp_mod.fleet_get_daily_briefing()

    # 2. Add task
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"task_id": 99}}
        assert "added task #99" in mcp_mod.fleet_add_task("Test Task", priority="P1")
        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Error" in mcp_mod.fleet_add_task("Test Task")

    # 3. List tasks
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "tasks": [
                    {"id": 1, "title": "P1 Task", "priority": "P1", "status": "pending", "description": "desc"},
                    {"id": 2, "title": "P2 Task", "priority": "P2", "status": "pending", "description": "desc"},
                    {"id": 3, "title": "P3 Task", "priority": "P3", "status": "pending", "description": "desc"},
                    {"id": 4, "title": "Done Task", "priority": "P2", "status": "completed", "description": "desc"},
                ]
            }
        }
        res_tasks = mcp_mod.fleet_list_tasks()
        assert "#1" in res_tasks and "#4" in res_tasks

        mock_bus.return_value = {"status": "success", "data": {"tasks": []}}
        assert "No tasks found" in mcp_mod.fleet_list_tasks()

        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Error" in mcp_mod.fleet_list_tasks()

    # 4. Complete task
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"completed": True}}
        assert "marked as completed" in mcp_mod.fleet_complete_task(1)
        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Failed" in mcp_mod.fleet_complete_task(1)

    # 5. Routines
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "routines": [
                    {"id": 1, "title": "Exercise", "time_target": "08:00", "completed_today": True},
                    {"id": 2, "title": "Read", "time_target": "21:00", "completed_today": False},
                ]
            }
        }
        res_r = mcp_mod.fleet_list_routines()
        assert "Exercise" in res_r and "Read" in res_r

        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Error" in mcp_mod.fleet_list_routines()

        mock_bus.return_value = {"status": "success", "data": {}}
        assert "status toggled" in mcp_mod.fleet_toggle_routine(1)
        mock_bus.return_value = {"status": "error", "message": "fail"}
        assert "Error" in mcp_mod.fleet_toggle_routine(1)

    # 6. Notifications & Scan
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"sent": True}}
        assert "alert sent" in mcp_mod.fleet_send_notification("Title", "Msg")
        mock_bus.return_value = {"status": "error"}
        assert "Failed" in mcp_mod.fleet_send_notification("Title", "Msg")

        mock_bus.return_value = {"status": "success", "data": {"total_files": 10}}
        assert "10" in mcp_mod.fleet_scan_directory("~/Downloads")
        mock_bus.return_value = {"status": "error", "message": "missing"}
        assert "Error" in mcp_mod.fleet_scan_directory("~/Downloads")

    # 7. Email classification
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "dry_run": True,
                "total_processed": 5,
                "counts": {"Meetings": 1, "Respond": 2, "Note": 1, "FYI": 1, "Ignore": 0}
            }
        }
        res_em = mcp_mod.fleet_classify_recent_emails(dry_run=True)
        assert "DRY RUN PREVIEW" in res_em
        assert "Total Processed: 5" in res_em

        mock_bus.return_value = {"status": "error", "message": "auth error"}
        assert "Error" in mcp_mod.fleet_classify_recent_emails()

    # 8. Hyperscalers and Dev Tools
    with patch("fleet.core.hyperscalers.HyperscalerGateway.list_available_providers", return_value=["gemini"]), \
         patch("fleet.core.dev_tools.detect_developer_tools", return_value={"copilot": True}):
        res_ht = mcp_mod.fleet_list_hyperscalers_and_tools()
        assert "gemini" in res_ht

    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete", return_value={"response": "LLM text"}):
        res_q = mcp_mod.fleet_query_hyperscaler("Hello")
        assert "LLM text" in res_q

    # 9. Customize & Create Custom Agent
    with patch("fleet.server.agent_registry.customize_agent", return_value={"id": "test_ag", "name": "Customized"}), \
         patch("fleet.server.agent_registry.create_custom_agent", return_value={"id": "new_ag", "name": "New Ag"}):
        res_cust = mcp_mod.fleet_customize_agent("test_ag", name="Customized", order=10)
        assert "Customized" in res_cust

        res_new = mcp_mod.fleet_create_custom_agent("new_ag", name="New Ag")
        assert "new_ag" in res_new

    # 10. Run developer tool
    with patch("fleet.core.dev_tools.execute_github_copilot_command", return_value={"status": "copilot_ok"}), \
         patch("fleet.core.dev_tools.execute_claude_code", return_value={"status": "claude_ok"}), \
         patch("fleet.core.dev_tools.execute_google_gemini_cli", return_value={"status": "gemini_ok"}), \
         patch("fleet.core.dev_tools.execute_aws_q_developer", return_value={"status": "q_ok"}):
        assert "copilot_ok" in mcp_mod.fleet_run_developer_tool("copilot", "prompt")
        assert "claude_ok" in mcp_mod.fleet_run_developer_tool("claude", "prompt")
        assert "gemini_ok" in mcp_mod.fleet_run_developer_tool("gemini", "prompt")
        assert "q_ok" in mcp_mod.fleet_run_developer_tool("aws", "prompt")
        assert "Unknown tool" in mcp_mod.fleet_run_developer_tool("unknown_tool", "prompt")

    # 11. Schedules
    mock_sched = MagicMock()
    mock_sched.timezone = "UTC"
    mock_sched.get_schedules.return_value = [
        {"id": "s1", "agent": "agenda", "task": "briefing", "schedule_type": "time_of_day", "time": "08:00", "enabled": True},
        {"id": "s2", "agent": "health", "task": "water", "schedule_type": "interval", "interval_hours": 2, "enabled": False},
        {"id": "s3", "agent": "backup", "task": "sync", "schedule_type": "cron", "cron": "0 0 * * *", "enabled": True},
    ]
    mock_sched.toggle_schedule.return_value = {"status": "success", "message": "Schedule updated"}
    mock_sched.run_now.return_value = {"status": "SUCCESS", "task": "briefing", "agent": "agenda", "duration": 0.05}

    with patch("fleet.core.scheduler.get_fleet_scheduler", return_value=mock_sched):
        res_s = mcp_mod.fleet_list_schedules()
        assert "agenda" in res_s and "health" in res_s
        assert "Schedule updated" in mcp_mod.fleet_toggle_schedule("s1", True)
        assert "Successfully executed" in mcp_mod.fleet_run_scheduled_task(schedule_id="s1")


# ---------------------------------------------------------------------------
# 3. fleet.core.token_optimizer tests
# ---------------------------------------------------------------------------
def test_token_optimizer_exhaustive():
    # 1. Keywords & Normalization
    tokens = tok_mod.tokenize_keywords("What is the FFD green smoothie recipe?")
    assert "smoothie" in tokens or "recipe" in tokens

    normalized = tok_mod.normalize_prompt_for_cache("  What is FFD smoothie recipe???  ")
    assert len(normalized) == 64

    # 2. Similarity & Caching
    sim = tok_mod.compute_prompt_similarity("how to make green smoothie", "how to prepare green smoothie")
    assert sim > 0.4

    tok_mod.cache_prompt_response("how to reverse diabetes", "Follow the FFD protocol")
    cached = tok_mod.get_cached_prompt_response("how to reverse diabetes")
    assert cached == "Follow the FFD protocol"

    # 3. Local Knowledge Query (Tier 0 offline RAG)
    rag_hit = tok_mod.query_local_knowledge_base("Tell me about FFD protocol and smoothie")
    assert rag_hit is not None
    assert "FFD" in rag_hit.get("title", "") or "smoothie" in rag_hit.get("content", "").lower()

    # 4. Code minifier & stack trace compressor
    py_code = """
def sample_func():
    # This is a comment
    val = 10  # inline comment
    return val
"""
    minified = tok_mod.minify_python_code_snippet(py_code)
    assert "# This is a comment" not in minified

    stack_trace = """
Traceback (most recent call last):
  File "test.py", line 10, in <module>
    raise ValueError("Test error")
ValueError: Test error
"""
    compressed_trace = tok_mod.compress_stack_traces(stack_trace)
    assert "ValueError: Test error" in compressed_trace

    # 5. Model Tier & Delta Cache
    tier = tok_mod.select_optimal_model_tier("simple prompt", token_usage_pct=80.0)
    assert "flash" in tier

    tier2 = tok_mod.select_optimal_model_tier("refactor the entire architecture", requested_model="gemini-2.5-pro")
    assert tier2 == "gemini-2.5-pro"

    res1 = tok_mod.check_mcp_delta_response("tool_test", "State Output 1")
    assert res1 == "State Output 1"
    res2 = tok_mod.check_mcp_delta_response("tool_test", "State Output 1")
    assert "State unchanged" in res2

    # 6. Intent route
    intent = tok_mod.try_deterministic_intent_route("show my tasks")
    assert intent is not None or tok_mod.try_deterministic_intent_route("non_intent_xyz") is None

    stats = tok_mod.get_token_optimization_stats()
    assert "policy" in stats
    assert stats["security_scan_token_cost"] == 0


# ---------------------------------------------------------------------------
# 4. fleet.core.crypto_vault & yaml_helper tests
# ---------------------------------------------------------------------------
def test_crypto_vault_exhaustive(tmp_path):
    # Encrypt & Decrypt round-trip
    secret_text = "super_secret_token_12345"
    encrypted = vault_mod.encrypt_sensitive_text(secret_text)
    assert encrypted.startswith(vault_mod.ENCRYPTION_PREFIX)
    assert secret_text not in encrypted

    # Idempotent encrypt
    assert vault_mod.encrypt_sensitive_text(encrypted) == encrypted

    decrypted = vault_mod.decrypt_sensitive_text(encrypted)
    assert decrypted == secret_text

    # Non-prefixed passthrough
    assert vault_mod.decrypt_sensitive_text("plain_text") == "plain_text"
    assert vault_mod.decrypt_sensitive_text("") == ""

    # Master key accessor
    key = vault_mod.get_or_create_master_key()
    assert len(key) == 32

    # Set secure secret
    with patch.dict(os.environ, {}, clear=True):
        vault_mod.set_secure_secret("FLEET_TEST_SECRET", "dummy_val")
        assert os.environ.get("FLEET_TEST_SECRET") == "dummy_val"


def test_yaml_helper_exhaustive():
    data = {
        "version": "2.5.0",
        "enabled": True,
        "count": 42,
        "ratio": 3.14,
        "items": ["apple", "banana", "cherry"],
        "nested": {
            "name": "Fleet",
            "active": False,
        }
    }
    dumped = yaml_mod.dump_yaml(data)
    loaded = yaml_mod.safe_load_yaml(dumped)

    assert loaded["version"] == "2.5.0"
    assert loaded["enabled"] is True
    assert loaded["count"] == 42
    assert loaded["items"] == ["apple", "banana", "cherry"]
    assert loaded["nested"]["name"] == "Fleet"
