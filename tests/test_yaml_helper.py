"""Unit tests for the pure-Python zero-dependency YAML helper."""

from pathlib import Path
import tempfile
import pytest

from fleet.core.yaml_helper import (
    dump_yaml,
    load_yaml_file,
    parse_yaml_scalar,
    safe_load_yaml,
    save_yaml_file,
)


def test_parse_yaml_scalar():
    assert parse_yaml_scalar("true") is True
    assert parse_yaml_scalar("False") is False
    assert parse_yaml_scalar("null") is None
    assert parse_yaml_scalar("~") is None
    assert parse_yaml_scalar("123") == 123
    assert parse_yaml_scalar("45.67") == 45.67
    assert parse_yaml_scalar('"quoted string"') == "quoted string"
    assert parse_yaml_scalar("'single quoted'") == "single quoted"
    assert parse_yaml_scalar('["mon", "tue"]') == ["mon", "tue"]
    assert parse_yaml_scalar("") == ""


def test_safe_load_yaml_dict_and_list():
    raw_yaml = """
# Top comment
server:
  host: "127.0.0.1"
  port: 7890
  debug: false

agents:
  overview:
    enabled: true
    order: 10
  optimizer:
    enabled: true
    scan_interval_hours: 6

schedules:
  - agent: overview
    task: morning_briefing
    time: "08:30"
    days: ["monday", "tuesday"]
    enabled: true
  - agent: optimizer
    task: quick_optimize
    interval_hours: 6
    enabled: true
"""
    data = safe_load_yaml(raw_yaml)
    assert isinstance(data, dict)
    assert data["server"]["host"] == "127.0.0.1"
    assert data["server"]["port"] == 7890
    assert data["server"]["debug"] is False
    assert data["agents"]["overview"]["enabled"] is True
    assert data["agents"]["optimizer"]["scan_interval_hours"] == 6

    scheds = data["schedules"]
    assert len(scheds) == 2
    assert scheds[0]["agent"] == "overview"
    assert scheds[0]["task"] == "morning_briefing"
    assert scheds[0]["time"] == "08:30"
    assert scheds[0]["days"] == ["monday", "tuesday"]
    assert scheds[1]["interval_hours"] == 6


def test_yaml_roundtrip_file():
    sample_data = {
        "version": "1.0",
        "timezone": "Asia/Kolkata",
        "schedules": [
            {
                "id": "health_smoothie",
                "agent": "health",
                "task": "smoothie_reminder",
                "time": "07:15",
                "enabled": True,
            },
            {
                "id": "optimizer_scan",
                "agent": "optimizer",
                "task": "quick_optimize",
                "interval_hours": 6,
                "enabled": False,
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        f_path = Path(tmp_dir) / "test_schedules.yaml"
        save_yaml_file(f_path, sample_data)
        assert f_path.is_file()

        loaded = load_yaml_file(f_path)
        assert loaded["version"] == "1.0"
        assert loaded["timezone"] == "Asia/Kolkata"
        assert len(loaded["schedules"]) == 2
        assert loaded["schedules"][0]["agent"] == "health"
        assert loaded["schedules"][0]["time"] == "07:15"
        assert loaded["schedules"][0]["enabled"] is True
        assert loaded["schedules"][1]["enabled"] is False


def test_load_yaml_missing_file_and_empty():
    assert load_yaml_file("Z:/non_existent_yaml_file_9999.yaml") == {}
    assert safe_load_yaml("") == {}
    assert safe_load_yaml("   # only comments\n   \n") == {}

