"""
Unit tests for the Fleet Agent Scheduling Engine, YAML custom schedule parser,
default schedules, cron evaluator, and server API endpoints.
"""

from datetime import datetime
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from fleet.core.scheduler import (
    DEFAULT_SCHEDULES,
    FleetScheduler,
    get_fleet_scheduler,
    match_cron,
    match_cron_field,
    parse_interval_to_seconds,
)


def test_parse_interval_to_seconds():
    assert parse_interval_to_seconds(None, hours=2) == 7200
    assert parse_interval_to_seconds(None, minutes=30) == 1800
    assert parse_interval_to_seconds(None, seconds=45) == 45
    assert parse_interval_to_seconds(None, hours=1, minutes=15, seconds=30) == 4530

    assert parse_interval_to_seconds(300) == 300
    assert parse_interval_to_seconds(45.5) == 45
    assert parse_interval_to_seconds("2h") == 7200
    assert parse_interval_to_seconds("15m") == 900
    assert parse_interval_to_seconds("30s") == 30
    assert parse_interval_to_seconds("1d") == 86400
    assert parse_interval_to_seconds("invalid_str") == 3600
    assert parse_interval_to_seconds(None) == 3600


def test_match_cron_field():
    assert match_cron_field("*", 5, 0, 59) is True
    assert match_cron_field("*/15", 30, 0, 59) is True
    assert match_cron_field("*/15", 35, 0, 59) is False
    assert match_cron_field("1,15,30", 15, 0, 59) is True
    assert match_cron_field("1,15,30", 16, 0, 59) is False
    assert match_cron_field("9-17", 12, 0, 23) is True
    assert match_cron_field("9-17", 18, 0, 23) is False
    assert match_cron_field("8", 8, 0, 23) is True
    assert match_cron_field("8", 9, 0, 23) is False
    assert match_cron_field("invalid", 8, 0, 23) is False


def test_match_cron():
    # 2026-10-12 was a Monday (weekday 0, cron dow 1)
    dt_mon_8am = datetime(2026, 10, 12, 8, 0)
    assert match_cron("* * * * *", dt_mon_8am) is True
    assert match_cron("0 8 * * *", dt_mon_8am) is True
    assert match_cron("0 9 * * *", dt_mon_8am) is False
    assert match_cron("0 8 * * 1", dt_mon_8am) is True
    assert match_cron("0 8 * * 1-5", dt_mon_8am) is True
    assert match_cron("0 8 * * 0", dt_mon_8am) is False  # 0 is Sunday
    assert match_cron("invalid cron string", dt_mon_8am) is False


def test_default_schedules_in_place():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))
        schedules = scheduler.get_schedules()
        assert len(schedules) >= 7

        agent_ids = {s["agent"] for s in schedules}
        assert "overview" in agent_ids
        assert "health" in agent_ids
        assert "optimizer" in agent_ids
        assert "antigravity" in agent_ids
        assert "backlog" in agent_ids

        # Check morning briefing default
        mb = next((s for s in schedules if s["id"] == "overview_morning_briefing"), None)
        assert mb is not None
        assert mb["time"] == "08:30"
        assert mb["schedule_type"] == "time_of_day"
        assert mb["enabled"] is True

        # Check optimizer default
        opt = next((s for s in schedules if s["id"] == "optimizer_quick_optimize"), None)
        assert opt is not None
        assert opt["schedule_type"] == "interval"
        assert opt["interval_hours"] == 6


def test_custom_yaml_schedule_overrides_and_additions():
    custom_yaml = """
version: "1.0"
timezone: "Asia/Kolkata"

schedules:
  # 1. Override default morning briefing time to 09:15
  - id: overview_morning_briefing
    agent: overview
    task: morning_briefing
    time: "09:15"
    enabled: true

  # 2. Disable evening review
  - id: overview_evening_review
    enabled: false

  # 3. Add brand new custom agent schedule
  - id: custom_crypto_watcher
    agent: crypto_agent
    task: check_bitcoin
    description: "Check BTC price every 15 minutes"
    schedule_type: interval
    interval_minutes: 15
    enabled: true
"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_dir = Path(tmp_dir)
        (cfg_dir / "schedules.yaml").write_text(custom_yaml, encoding="utf-8")

        scheduler = FleetScheduler(config_dir=cfg_dir)
        scheds = {s["id"]: s for s in scheduler.get_schedules()}

        # 1. Morning briefing time updated
        assert scheds["overview_morning_briefing"]["time"] == "09:15"
        assert scheds["overview_morning_briefing"]["enabled"] is True

        # 2. Evening review disabled
        assert scheds["overview_evening_review"]["enabled"] is False

        # 3. Custom agent schedule added
        assert "custom_crypto_watcher" in scheds
        assert scheds["custom_crypto_watcher"]["agent"] == "crypto_agent"
        assert scheds["custom_crypto_watcher"]["interval_seconds"] == 900

        # 4. Untouched defaults remain active
        assert "health_smoothie_reminder" in scheds
        assert scheds["health_smoothie_reminder"]["enabled"] is True


def test_toggle_schedule_and_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))
        sid = "overview_morning_briefing"

        # Explicitly disable
        res_off = scheduler.toggle_schedule(sid, enabled=False)
        assert res_off["status"] == "success"
        assert res_off["enabled"] is False
        rule_off = next(s for s in scheduler.get_schedules() if s["id"] == sid)
        assert rule_off["enabled"] is False

        # Toggle back on
        res_on = scheduler.toggle_schedule(sid)
        assert res_on["status"] == "success"
        assert res_on["enabled"] is True
        rule_on = next(s for s in scheduler.get_schedules() if s["id"] == sid)
        assert rule_on["enabled"] is True

        # Toggle non-existent ID
        assert scheduler.toggle_schedule("non_existent_id")["status"] == "error"


def test_check_and_run_time_of_day():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))
        scheduler.bus = MagicMock()
        scheduler.bus.dispatch.return_value = {"status": "success", "data": {}}

        # Morning briefing at 08:30
        dt_before = datetime(2026, 10, 14, 8, 15)
        res_before = scheduler.check_and_run(dt_before)
        mb_before = [r for r in res_before if r["id"] == "overview_morning_briefing"]
        assert len(mb_before) == 0

        # At 08:30 (triggers)
        dt_at = datetime(2026, 10, 14, 8, 30)
        res_at = scheduler.check_and_run(dt_at)
        mb_at = [r for r in res_at if r["id"] == "overview_morning_briefing"]
        assert len(mb_at) == 1
        assert mb_at[0]["status"] == "SUCCESS"

        # At 08:35 on the same day (should NOT trigger again today)
        dt_after = datetime(2026, 10, 14, 8, 35)
        res_after = scheduler.check_and_run(dt_after)
        mb_after = [r for r in res_after if r["id"] == "overview_morning_briefing"]
        assert len(mb_after) == 0

        # Next day at 08:30 (triggers again on new date)
        dt_next_day = datetime(2026, 10, 15, 8, 30)
        res_next = scheduler.check_and_run(dt_next_day)
        mb_next = [r for r in res_next if r["id"] == "overview_morning_briefing"]
        assert len(mb_next) == 1


def test_check_and_run_interval_and_filters():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))
        scheduler.bus = MagicMock()
        scheduler.bus.dispatch.return_value = {"status": "success", "data": {}}

        test_rule = {
            "id": "test_interval_rule",
            "agent": "overview",
            "task": "task_summary",
            "schedule_type": "interval",
            "interval_seconds": 10,
            "weekdays_only": True,
            "active_hours": "09:00-17:00",
            "enabled": True,
        }
        scheduler.schedules.append(test_rule)
        scheduler._last_run_state["test_interval_rule"] = {"last_run_timestamp": 0.0}

        # 1. On a Saturday (should NOT run because weekdays_only=True)
        sat_dt = datetime(2026, 10, 17, 10, 0)  # Saturday
        res_sat = scheduler.check_and_run(sat_dt)
        assert not any(r["id"] == "test_interval_rule" for r in res_sat)

        # 2. On a Monday before active hours (08:00, outside 09:00-17:00)
        mon_early = datetime(2026, 10, 19, 8, 0)  # Monday
        res_early = scheduler.check_and_run(mon_early)
        assert not any(r["id"] == "test_interval_rule" for r in res_early)

        # 3. On a Monday within active hours (10:00) -> Runs!
        mon_ok = datetime(2026, 10, 19, 10, 0)
        res_ok = scheduler.check_and_run(mon_ok)
        assert any(r["id"] == "test_interval_rule" for r in res_ok)


def test_run_now_manual_execution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))
        scheduler.bus = MagicMock()
        scheduler.bus.dispatch.return_value = {"status": "success", "data": {}}

        # Manual run by schedule_id
        res = scheduler.run_now(schedule_id="health_smoothie_reminder")
        assert res["status"] == "SUCCESS"
        assert res["agent"] == "health"
        assert res["task"] == "smoothie_reminder"

        # Manual ad-hoc run
        res_adhoc = scheduler.run_now(agent_id="health", task="lunch_meds")
        assert res_adhoc["status"] == "SUCCESS"
        assert res_adhoc["task"] == "lunch_meds"

        # Invalid
        assert scheduler.run_now(schedule_id="fake_id")["status"] == "error"
        assert scheduler.run_now()["status"] == "error"


def test_builtin_agent_task_dispatchers():
    with tempfile.TemporaryDirectory() as tmp_dir:
        scheduler = FleetScheduler(config_dir=Path(tmp_dir))

        # Health smoothie
        res_h = scheduler.run_now(schedule_id="health_smoothie_reminder")
        assert "Smoothie" in res_h["result"]["title"]

        # Optimizer
        with patch("fleet.core.optimizer.optimize_ram", return_value={"freed_mb": 100}), \
             patch("fleet.core.optimizer.flush_dns_cache", return_value={"status": "success"}), \
             patch("fleet.core.optimizer.get_memory_status", return_value={"percent_used": 45}):
            res_opt = scheduler.run_now(schedule_id="optimizer_quick_optimize")
            assert res_opt["status"] == "SUCCESS"
            assert res_opt["result"]["memory"]["percent_used"] == 45

        # Antigravity queue & token pulse
        with patch("fleet.core.antigravity_mirror.process_next_in_queue"), \
             patch("fleet.core.antigravity_mirror.get_token_health", return_value={"status": "Optimal", "percent_used": 15}):
            res_agy = scheduler.run_now(schedule_id="antigravity_process_queue")
            assert res_agy["status"] == "SUCCESS"
            assert "Tokens" in res_agy["result"]["message"]

        # Backlog hygiene
        res_bg = scheduler.run_now(schedule_id="backlog_grooming")
        assert res_bg["status"] == "SUCCESS"
        assert "Backlog" in res_bg["result"]["title"]


def test_mcp_tools_and_server_api_integration():
    from fleet.mcp_server import fleet_list_schedules, fleet_run_scheduled_task, fleet_toggle_schedule

    # MCP fleet_list_schedules
    listing = fleet_list_schedules()
    assert "Fleet Agent Schedules" in listing
    assert "**overview**.morning_briefing" in listing

    # MCP fleet_toggle_schedule
    toggle_msg = fleet_toggle_schedule("overview_morning_briefing", enabled=False)
    assert "disabled" in toggle_msg
    toggle_back = fleet_toggle_schedule("overview_morning_briefing", enabled=True)
    assert "enabled" in toggle_back

    # MCP fleet_run_scheduled_task
    run_msg = fleet_run_scheduled_task(schedule_id="health_smoothie_reminder")
    assert "Successfully executed" in run_msg
