"""
Exhaustive unit tests targeting remaining branches in fleet/core/scheduler.py and fleet/core/registry.py
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest
from datetime import datetime

import fleet.core.scheduler as sched_mod
import fleet.core.registry as reg_mod
from fleet.api.router import ApiRouter
from fleet.core.base_agent import FleetAgent


# ==============================================================================
# SCHEDULER BRANCH TESTS
# ==============================================================================

def test_scheduler_interval_parsing_and_cron_errors():
    # Value errors in interval strings
    assert sched_mod.parse_interval_to_seconds("badh") == 3600
    assert sched_mod.parse_interval_to_seconds("badm") == 3600
    assert sched_mod.parse_interval_to_seconds("bads") == 3600
    assert sched_mod.parse_interval_to_seconds("badd") == 3600
    assert sched_mod.parse_interval_to_seconds("invalid") == 3600

    # Errors in cron matching
    assert sched_mod.match_cron_field("*/bad", 10, 0, 59) is False
    assert sched_mod.match_cron_field("10-bad", 10, 0, 59) is False
    assert sched_mod.match_cron_field("bad", 10, 0, 59) is False


def test_scheduler_overrides_and_reload(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)
    
    # Overrides file corrupted
    overrides_file = tmp_path / "schedule_overrides.json"
    overrides_file.write_text("corrupted json{{", encoding="utf-8")
    with patch.object(sched, "_get_overrides_file", return_value=overrides_file):
        assert sched.load_overrides() == {}

    # Save overrides exception
    with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
        sched.save_overrides({"test": {"enabled": False}})

    # Reload with custom schedules file candidate
    custom_yaml = tmp_path / "schedules.yaml"
    custom_yaml.write_text("schedules:\n  - id: custom_task\n    agent: health\n    task: routine\n    every: 10m\n", encoding="utf-8")
    with patch("fleet.core.scheduler.load_fleet_config", return_value={"schedules": [{"id": "global_task", "agent": "overview", "task": "run"}]}):
        sched.reload()
        sched_ids = [s["id"] for s in sched.schedules]
        assert "global_task" in sched_ids or "custom_task" in sched_ids


def test_scheduler_normalize_rule_variations(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)
    # Days as string and times as string
    r1 = sched._normalize_rule({
        "id": "r1",
        "agent": "overview",
        "task": "briefing",
        "days": "mon, tue, wed",
        "times": "09:00, 17:00",
        "schedule_type": "time_of_day",
    })
    assert r1["days"] == ["mon", "tue", "wed"]
    assert r1["times"] == ["09:00", "17:00"]

    # Days as list, time as single string, cron schedule_type
    r2 = sched._normalize_rule({
        "id": "r2",
        "agent": "health",
        "task": "smoothie",
        "cron": "*/15 * * * *",
        "days": ["Mon", "Fri"],
        "time": "08:30",
    })
    assert r2["schedule_type"] == "cron"
    assert r2["days"] == ["mon", "fri"]
    assert r2["time"] == "08:30"


def test_scheduler_toggle_and_run_now(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)
    
    # Toggle nonexistent
    res = sched.toggle_schedule("nonexistent_id")
    assert res["status"] == "error"

    # Toggle existing
    sched.schedules = [{"id": "test_rule", "enabled": True}]
    res = sched.toggle_schedule("test_rule")
    assert res["status"] == "success"
    assert res["enabled"] is False

    # run_now with unknown schedule
    res = sched.run_now(schedule_id="missing_rule")
    assert res["status"] == "error"

    # run_now with missing args
    res = sched.run_now()
    assert res["status"] == "error"

    # run_now with agent and task adhoc
    with patch.object(sched, "run_task", return_value={"status": "SUCCESS"}):
        res = sched.run_now(agent_id="overview", task="run")
        assert res["status"] == "SUCCESS"


def test_scheduler_check_and_run_filters(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)
    
    # 1. Weekdays only rule on weekend
    weekend_dt = datetime(2026, 10, 25, 12, 0, 0) # Sunday
    sched.schedules = [{
        "id": "wd_rule",
        "enabled": True,
        "weekdays_only": True,
        "schedule_type": "interval",
        "interval_seconds": 60,
    }]
    results = sched.check_and_run(now=weekend_dt)
    assert len(results) == 0

    # 2. Days filter mismatch
    sched.schedules = [{
        "id": "days_rule",
        "enabled": True,
        "days": ["monday"],
        "schedule_type": "interval",
        "interval_seconds": 60,
    }]
    results = sched.check_and_run(now=weekend_dt)
    assert len(results) == 0

    # 3. Active hours filter mismatch
    sched.schedules = [{
        "id": "ah_rule",
        "enabled": True,
        "active_hours": "08:00-10:00",
        "schedule_type": "interval",
        "interval_seconds": 60,
    }]
    results = sched.check_and_run(now=weekend_dt)
    assert len(results) == 0


def test_scheduler_built_in_agent_dispatches(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)

    # Health Agent Routines
    res_h = sched._dispatch_builtin_agent_task("health", "routine_check", {}, {})
    assert res_h["status"] == "success"

    # PC Optimizer Agent
    with patch("fleet.core.optimizer.optimize_ram", return_value={"freed_mb": 100}):
        with patch("fleet.core.optimizer.flush_dns_cache", return_value={"status": "ok"}):
            with patch("fleet.core.optimizer.get_memory_status", return_value={"percent_used": 50}):
                res_opt = sched._dispatch_builtin_agent_task("optimizer", "pulse", {}, {})
                assert res_opt["status"] == "success"

    # Gmail Agent
    with patch.object(sched.bus, "dispatch", return_value={"status": "success", "data": {"counts": {"Meetings": 1}}}):
        res_gm = sched._dispatch_builtin_agent_task("gmail", "triage", {}, {})
        assert res_gm["status"] == "success"

    # PR Review Agent
    import fleet.agents.pr_review.agent
    with patch("fleet.agents.pr_review.agent.PRReviewAgent") as mock_pra:
        inst = mock_pra.return_value
        inst.audit_pull_requests.return_value = {"open_count": 0}
        inst.check_ci_status.return_value = {"status": "SUCCESS"}
        res_pr = sched._dispatch_builtin_agent_task("pr_review", "gate", {}, {})
        assert res_pr["status"] == "success"

    # General event bus fallback
    with patch.object(sched.bus, "dispatch", return_value={"status": "success", "data": {}, "message": "done"}):
        res_fb = sched._dispatch_builtin_agent_task("unknown_agent", "custom_task", {}, {})
        assert res_fb["status"] == "success"


def test_scheduler_task_execution_error_and_notification(tmp_path):
    sched = sched_mod.FleetScheduler(config_dir=tmp_path)
    
    # Task error
    rule_err = {"id": "err_rule", "agent": "broken", "task": "fail"}
    with patch.object(sched, "_dispatch_builtin_agent_task", side_effect=RuntimeError("Task failed")):
        res = sched.run_task(rule_err)
        assert res["status"] == "ERROR"

    # Task notify with windows notification fallback
    rule_notify = {"id": "notif_rule", "agent": "health", "task": "smoothie_reminder", "notify": True}
    with patch.object(sched.bus, "dispatch", side_effect=Exception("Bus failed")):
        with patch("fleet.core.scheduler.send_windows_notification") as mock_toast:
            sched.run_task(rule_notify)
            mock_toast.assert_called_once()

    # get_fleet_scheduler singleton reload
    s1 = sched_mod.get_fleet_scheduler(reload=False)
    s2 = sched_mod.get_fleet_scheduler(reload=True)
    assert s1 == s2


# ==============================================================================
# REGISTRY BRANCH TESTS
# ==============================================================================

def test_registry_init_and_overrides_corrupt(tmp_path):
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir()
    reg = reg_mod.AgentRegistry(custom_agents_dir=custom_dir)
    assert reg.custom_agents_dir == custom_dir

    # Corrupted overrides file
    overrides_file = reg._get_overrides_file()
    overrides_file.write_text("bad json{{", encoding="utf-8")
    assert reg.load_overrides() == {}

    # Save overrides exception
    with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
        reg.save_overrides({"agent": {"enabled": False}})


def test_registry_discover_scan_skips(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir()

    # Hidden dir
    (agents_dir / ".hidden").mkdir()
    # Dir without agent.py
    (agents_dir / "empty_dir").mkdir()

    reg = reg_mod.AgentRegistry(agents_dir=agents_dir, custom_agents_dir=custom_dir)
    loaded = reg.discover_and_load()
    assert len(loaded) == 0


def test_registry_routes_exhaustive(tmp_path):
    reg = reg_mod.AgentRegistry()
    router = ApiRouter()
    reg.register_all_routes(router)

    get_manifest_handler = router.get_routes.get("/api/fleet/agents")
    assert get_manifest_handler is not None

    prefix_get_handler = None
    for prefix, fn in router.get_prefix_routes:
        if prefix == "/api/fleet/agents/":
            prefix_get_handler = fn
            break

    prefix_post_handler = None
    for prefix, fn in router.post_prefix_routes:
        if prefix == "/api/fleet/agents/":
            prefix_post_handler = fn
            break

    assert prefix_get_handler is not None
    assert prefix_post_handler is not None

    # Test get_manifests endpoint
    fake_handler = MagicMock()
    get_manifest_handler(fake_handler, urllib.parse.urlparse("/api/fleet/agents?all=true"))
    fake_handler._send_json.assert_called_once()

    # Test prefix_get: invalid path length (< 4 parts)
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet", urllib.parse.urlparse("/api/fleet"))
    fake_h.send_error.assert_called_with(400, "Invalid agent path")

    # Test prefix_get: invalid agent identifier
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/invalid!id/config", urllib.parse.urlparse("/api/fleet/agents/invalid!id/config"))
    fake_h.send_error.assert_called_with(400, "Invalid agent identifier")

    # Test prefix_get: agent not found
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/notfound/config", urllib.parse.urlparse("/api/fleet/agents/notfound/config"))
    fake_h.send_error.assert_called_with(404, "Agent 'notfound' not found")

    # Test prefix_get with loaded dummy agent
    dummy_agent = MagicMock()
    dummy_agent.id = "mock_agent"
    dummy_agent.agent_dir = tmp_path
    dummy_agent.get_ui_manifest.return_value = {"id": "mock_agent"}
    dummy_agent.config = {}
    dummy_agent.preferred_provider = "auto"
    dummy_agent.preferred_model = "auto"
    dummy_agent.system_prompt = ""
    reg.agents["mock_agent"] = dummy_agent

    # 1. Config subpath
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/config", urllib.parse.urlparse("/api/fleet/agents/mock_agent/config"))
    fake_h._send_json.assert_called_once()

    # 2. style.css found and not found
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    css_file = ui_dir / "style.css"
    css_file.write_text("body { color: red; }", encoding="utf-8")

    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/style.css", urllib.parse.urlparse("/api/fleet/agents/mock_agent/style.css"))
    fake_h.send_response.assert_called_with(200)

    css_file.unlink()
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/style.css", urllib.parse.urlparse("/api/fleet/agents/mock_agent/style.css"))
    fake_h.send_error.assert_called_with(404, "Style not found")

    # 3. script.js found and not found
    js_file = ui_dir / "script.js"
    js_file.write_text("console.log('hi');", encoding="utf-8")

    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/script.js", urllib.parse.urlparse("/api/fleet/agents/mock_agent/script.js"))
    fake_h.send_response.assert_called_with(200)

    js_file.unlink()
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/script.js", urllib.parse.urlparse("/api/fleet/agents/mock_agent/script.js"))
    fake_h.send_error.assert_called_with(404, "Script not found")

    # 4. Unknown subpath
    fake_h = MagicMock()
    prefix_get_handler(fake_h, "/api/fleet/agents/mock_agent/unknown_file", urllib.parse.urlparse("/api/fleet/agents/mock_agent/unknown_file"))
    fake_h.send_error.assert_called_with(404, "Unknown agent resource")

    # Test prefix_post:
    # 1. custom/create failure
    fake_h = MagicMock()
    with patch.object(reg, "create_custom_agent", side_effect=ValueError("Invalid agent ID")):
        prefix_post_handler(fake_h, "/api/fleet/agents/custom/create", {"id": "bad!"})
        fake_h._send_json.assert_called_with({"status": "error", "message": "Invalid agent ID"}, status=400)

    # 2. <agent_id>/config KeyError & Exception
    fake_h = MagicMock()
    with patch.object(reg, "customize_agent", side_effect=KeyError("not found")):
        prefix_post_handler(fake_h, "/api/fleet/agents/missing/config", {})
        fake_h.send_error.assert_called_with(404, "Agent 'missing' not found")

    fake_h = MagicMock()
    with patch.object(reg, "customize_agent", side_effect=ValueError("invalid config")):
        prefix_post_handler(fake_h, "/api/fleet/agents/missing/config", {})
        fake_h._send_json.assert_called_with({"status": "error", "message": "invalid config"}, status=400)

    # 3. <agent_id>/reset KeyError & Exception
    fake_h = MagicMock()
    with patch.object(reg, "reset_agent", side_effect=KeyError("not found")):
        prefix_post_handler(fake_h, "/api/fleet/agents/missing/reset", {})
        fake_h.send_error.assert_called_with(404, "Agent 'missing' not found")

    fake_h = MagicMock()
    with patch.object(reg, "reset_agent", side_effect=ValueError("reset fail")):
        prefix_post_handler(fake_h, "/api/fleet/agents/missing/reset", {})
        fake_h._send_json.assert_called_with({"status": "error", "message": "reset fail"}, status=400)

    # 4. Unknown POST endpoint
    fake_h = MagicMock()
    prefix_post_handler(fake_h, "/api/fleet/agents/bad/endpoint", {})
    fake_h.send_error.assert_called_with(404, "Unknown agent endpoint")


def test_registry_lifecycle_and_manifests():
    reg = reg_mod.AgentRegistry()
    mock_agent = MagicMock()
    mock_agent.id = "test_agent"
    mock_agent.enabled = True
    mock_agent._override_default = True
    mock_agent.get_ui_manifest.return_value = {"id": "test_agent", "order": 1, "name": "Test"}
    mock_agent.on_startup.side_effect = RuntimeError("startup error")
    mock_agent.on_shutdown.side_effect = RuntimeError("shutdown error")

    reg.agents["test_agent"] = mock_agent
    reg._all_discovered_agents["test_agent"] = mock_agent

    # startup and shutdown error handling
    reg.startup_all()
    reg.shutdown_all()

    # get_manifests with override default
    manifests = reg.get_manifests(include_disabled=True)
    assert len(manifests) >= 1
    assert manifests[0]["is_default"] is True

