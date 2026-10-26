"""
Deep Coverage Gap Fillers for Personal Agentic Fleet.
Targets:
- fleet.tools.security_scanner
- fleet.core.registry
- fleet.core.scheduler
- fleet.core.optimizer
- fleet.core.hyperscalers
- fleet.core.antigravity_mirror
- fleet.core.lifecycle
- fleet.core.supervisor
- fleet.core.power
- fleet.core.sandbox_quota
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.core.database import FleetDatabase
from fleet.core.registry import AgentRegistry
import fleet.server as srv
import fleet.tools.security_scanner as sec_scan
import fleet.core.scheduler as sched_mod
import fleet.core.optimizer as opt_mod
import fleet.core.hyperscalers as hyper_mod
import fleet.core.antigravity_mirror as ag_mirror
import fleet.core.lifecycle as life_mod
import fleet.core.supervisor as sup_mod
import fleet.core.power as power_mod
import fleet.core.sandbox_quota as quota_mod


# ---------------------------------------------------------------------------
# 1. security_scanner finding branches
# ---------------------------------------------------------------------------
def test_security_scanner_all_finding_branches(tmp_path):
    repo = tmp_path / "mock_repo"
    repo.mkdir()
    (repo / "fleet").mkdir()
    (repo / "tests").mkdir()

    # 1. Missing .gitignore triggers Check 3 finding
    rep1 = sec_scan.run_security_scan(repo_root=repo, save_report=False)
    assert any(f["category"] == "Git Hygiene" for f in rep1["findings"])

    # 2. Add .gitignore with missing required rules & add forbidden tracked file
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (repo / "client_secret_oauth.json").write_text('{"client_id": "test"}', encoding="utf-8")
    rep2 = sec_scan.run_security_scan(repo_root=repo, save_report=False)
    assert any("Forbidden" in f["category"] or "Git Hygiene" in f["category"] for f in rep2["findings"])

    # 3. Add file with PII
    with patch.object(sec_scan, "_load_pii_blocklist", return_value=["SecretAgentSmith"]):
        (repo / "pii.txt").write_text("User is SecretAgentSmith here", encoding="utf-8")
        rep3 = sec_scan.run_security_scan(repo_root=repo, save_report=False)
        assert any("PII" in f["category"] for f in rep3["findings"])

    # 4. SAST findings in fleet/
    (repo / "fleet" / "bad_cmd.py").write_text("import subprocess\nsubprocess.run('cmd', shell=True)\n", encoding="utf-8")
    rep4 = sec_scan.run_security_scan(repo_root=repo, save_report=False)
    assert any("SAST" in f["category"] for f in rep4["findings"])


# ---------------------------------------------------------------------------
# 2. fleet.core.registry UI routes and custom agents
# ---------------------------------------------------------------------------
def test_registry_ui_routes_and_custom_agent(tmp_path):
    db_file = tmp_path / "reg_test.db"
    db = FleetDatabase(db_file)
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir(parents=True)

    registry = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=custom_dir,
        db=db,
    )
    registry.discover_and_load()

    router = ApiRouter()
    registry.register_all_routes(router)

    handler = MagicMock()

    # 1. GET /api/fleet/agents/overview/style.css
    router.dispatch_get(handler, "/api/fleet/agents/overview/style.css", urllib.parse.urlparse("/api/fleet/agents/overview/style.css"))
    assert handler.send_response.called or handler.send_error.called
    handler.reset_mock()

    # 2. GET /api/fleet/agents/overview/script.js
    router.dispatch_get(handler, "/api/fleet/agents/overview/script.js", urllib.parse.urlparse("/api/fleet/agents/overview/script.js"))
    assert handler.send_response.called or handler.send_error.called
    handler.reset_mock()

    # 3. GET unknown resource
    router.dispatch_get(handler, "/api/fleet/agents/overview/unknown.xyz", urllib.parse.urlparse("/api/fleet/agents/overview/unknown.xyz"))
    assert handler.send_error.called
    handler.reset_mock()

    # 4. POST custom create
    with patch.object(registry, "create_custom_agent", return_value={"id": "my_new_agent"}):
        router.dispatch_post(handler, "/api/fleet/agents/custom/create", {"id": "my_new_agent", "name": "My New Agent"})
        assert handler._send_json.called
        handler.reset_mock()

    with patch.object(registry, "create_custom_agent", side_effect=ValueError("Duplicate")):
        router.dispatch_post(handler, "/api/fleet/agents/custom/create", {"id": "my_new_agent"})
        assert handler._send_json.called
        assert handler._send_json.call_args[1].get("status") == 400
        handler.reset_mock()

    # 5. POST config update
    with patch.object(registry, "customize_agent", return_value={"id": "overview", "name": "Customized"}):
        router.dispatch_post(handler, "/api/fleet/agents/overview/config", {"name": "Customized"})
        assert handler._send_json.called
        handler.reset_mock()

    with patch.object(registry, "customize_agent", side_effect=KeyError("Not found")):
        router.dispatch_post(handler, "/api/fleet/agents/non_existent/config", {"name": "Test"})
        assert handler.send_error.called
        handler.reset_mock()

    # 6. POST reset agent
    with patch.object(registry, "reset_agent", return_value={"id": "overview"}):
        router.dispatch_post(handler, "/api/fleet/agents/overview/reset", {})
        assert handler._send_json.called
        handler.reset_mock()

    with patch.object(registry, "reset_agent", side_effect=KeyError("Not found")):
        router.dispatch_post(handler, "/api/fleet/agents/non_existent/reset", {})
        assert handler.send_error.called


# ---------------------------------------------------------------------------
# 3. fleet.core.scheduler config loading & cron
# ---------------------------------------------------------------------------
def test_scheduler_complex_configs(tmp_path):
    mock_db = FleetDatabase(tmp_path / "sched.db")
    sched = sched_mod.FleetScheduler(db=mock_db)

    # 1. Complex config with global schedules and per-agent schedules
    complex_cfg = {
        "schedules": [
            {"id": "global_task_1", "agent": "health", "task": "smoothie_reminder", "interval_hours": 4, "enabled": True}
        ],
        "agents": {
            "optimizer": {
                "schedule": {"task": "optimize_ram", "time": "12:00", "enabled": True}
            },
            "overview": {
                "schedules": [
                    {"id": "ov_evening", "task": "evening_review", "time": "18:00", "enabled": False}
                ]
            }
        }
    }
    with patch("fleet.core.scheduler.load_fleet_config", return_value=complex_cfg):
        rules = sched.get_schedules()
        assert len(rules) >= 3

    # 2. Rule normalization
    norm = sched._normalize_rule({
        "agent": "health",
        "task": "water",
        "time": "09:00",
        "enabled": True,
    })
    assert norm["schedule_type"] == "time_of_day"

    # 3. Toggle and run_now with missing rule
    assert sched.toggle_schedule("non_existent_schedule_id")["status"] == "error"
    res_run = sched.run_now("non_existent_schedule_id")
    assert res_run["status"] in ("FAILED", "UNKNOWN_SCHEDULE", "NOT_FOUND", "error")


# ---------------------------------------------------------------------------
# 4. fleet.core.optimizer POSIX ps and memory fallback
# ---------------------------------------------------------------------------
def test_optimizer_posix_ps():
    # Mock POSIX ps command output
    ps_stdout = "COMMAND RSS\npython 51200\ncode 102400\nchrome 204800\n"
    mock_ps = MagicMock(returncode=0, stdout=ps_stdout)

    with patch("os.name", "posix"), \
         patch("subprocess.run", return_value=mock_ps):
        procs = opt_mod.get_top_processes(limit=5)
        assert len(procs) >= 1
        assert any(p["name"] in ("chrome", "code", "python") for p in procs)


# ---------------------------------------------------------------------------
# 5. fleet.core.hyperscalers multi-provider completion
# ---------------------------------------------------------------------------
def test_hyperscalers_providers():
    gw = hyper_mod.HyperscalerGateway()

    # 1. Gemini completion
    with patch.object(gw, "_call_google", return_value={"status": "success", "response": "Gemini answer"}):
        res_gemini = gw.complete(prompt="Hi", provider="gemini")
        assert res_gemini["response"] == "Gemini answer"

    # 2. Azure completion
    with patch.object(gw, "_call_microsoft_azure", return_value={"status": "success", "response": "Azure answer"}):
        res_azure = gw.complete(prompt="Hi", provider="azure")
        assert res_azure["response"] == "Azure answer"

    # 3. AWS Bedrock completion
    with patch.object(gw, "_call_aws_bedrock", return_value={"status": "success", "response": "Bedrock answer"}):
        res_bedrock = gw.complete(prompt="Hi", provider="bedrock")
        assert res_bedrock["response"] == "Bedrock answer"

    # 4. Claude completion
    with patch.object(gw, "_call_anthropic_claude", return_value={"status": "success", "response": "Claude answer"}):
        res_claude = gw.complete(prompt="Hi", provider="claude")
        assert res_claude["response"] == "Claude answer"

    # 5. Ollama completion
    with patch.object(gw, "_call_ollama", return_value={"status": "success", "response": "Ollama answer"}):
        res_ollama = gw.complete(prompt="Hi", provider="ollama")
        assert res_ollama["response"] == "Ollama answer"


# ---------------------------------------------------------------------------
# 6. fleet.core.antigravity_mirror queue and simulation
# ---------------------------------------------------------------------------
def test_antigravity_mirror_queue_and_tokens():
    # Simulate token states via simulated_status argument
    w_health = ag_mirror.get_token_health(simulated_status="warning")
    assert w_health["status"].lower() == "warning"

    e_health = ag_mirror.get_token_health(simulated_status="exhausted")
    assert e_health["status"].lower() == "exhausted"

    with patch.object(ag_mirror.db, "get_setting", return_value=None), \
         patch("fleet.core.antigravity_mirror.get_active_transcript_path", return_value=None):
        c_health = ag_mirror.get_token_health(simulated_status=None)
        assert c_health["status"].lower() == "ok"

    # Resume token exhaustion with fallback
    with patch("fleet.core.antigravity_mirror.set_active_model"):
        res = ag_mirror.resume_token_exhaustion(fallback_model="gemini-2.5-flash")
        assert res["status"] == "resumed"


# ---------------------------------------------------------------------------
# 7. fleet.core.lifecycle, supervisor, power, and quota
# ---------------------------------------------------------------------------
def test_lifecycle_and_supervisor():
    # Lifecycle safe log
    life_mod._safe_log("Test lifecycle message")

    # Supervisor
    sup = sup_mod.FleetSupervisor()
    sup.register_worker("worker_1", lambda: None)
    status = sup.get_status()
    assert "worker_1" in status.get("workers", {})

    # Power manager
    pm = power_mod.PowerLifecycleManager(gap_threshold_sec=1.0)
    assert pm is not None

    # Quota check
    q_status = quota_mod.get_process_memory_mb()
    assert q_status >= 0.0
