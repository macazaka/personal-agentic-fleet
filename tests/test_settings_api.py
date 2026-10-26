import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.core.registry import AgentRegistry
from fleet.core.database import FleetDatabase
import fleet.server as srv


@pytest.fixture
def mock_fleet_env(tmp_path):
    # Setup temporary database
    db_file = tmp_path / "test_fleet.db"
    db = FleetDatabase(db_file)

    # Setup agent registry with mock custom agents dir
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir(parents=True, exist_ok=True)
    overrides_file = tmp_path / "agent_overrides.json"

    registry = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=custom_dir,
        db=db,
    )
    with patch.object(registry, "_get_overrides_file", return_value=overrides_file):
        registry.discover_and_load()

    with patch.object(srv, "db", db), patch.object(srv, "agent_registry", registry):
        yield {"db": db, "registry": registry, "tmp_path": tmp_path}


def test_get_settings_endpoint(mock_fleet_env):
    from fleet.api.settings_api import get_fleet_settings

    handler = MagicMock()
    parsed_url = urllib.parse.urlparse("/api/settings")
    get_fleet_settings(handler, parsed_url)

    assert handler._send_json.called
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "ok"
    assert "settings" in res
    assert res["settings"]["timezone"].startswith("Asia/Kolkata")
    assert "agents" in res
    assert len(res["agents"]) >= 5
    assert res["active_agents_count"] >= 5
    assert res["total_agents_count"] >= res["active_agents_count"]


def test_update_settings_endpoint(mock_fleet_env):
    from fleet.api.settings_api import update_fleet_settings

    handler = MagicMock()
    body = {
        "timezone": "UTC",
        "notifications_enabled": False,
        "cost_policy": "LOWEST_COST_FIRST",
    }
    update_fleet_settings(handler, body)

    assert handler._send_json.called
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "success"
    assert res["settings"]["timezone"] == "UTC"
    assert res["settings"]["notifications_enabled"] == "false"
    assert res["settings"]["cost_policy"] == "LOWEST_COST_FIRST"


def test_toggle_agent_activation(mock_fleet_env):
    from fleet.api.settings_api import toggle_agent_activation

    handler = MagicMock()

    # 1. Deactivate health agent
    toggle_agent_activation(handler, {"id": "health", "enabled": False})
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "success"
    assert res["agent"]["enabled"] is False

    registry = mock_fleet_env["registry"]
    active_manifests = registry.get_manifests(include_disabled=False)
    assert not any(m["id"] == "health" for m in active_manifests)

    all_manifests = registry.get_manifests(include_disabled=True)
    health_m = next((m for m in all_manifests if m["id"] == "health"), None)
    assert health_m is not None
    assert health_m["enabled"] is False

    # 2. Reactivate health agent
    handler.reset_mock()
    toggle_agent_activation(handler, {"id": "health", "enabled": True})
    res2 = handler._send_json.call_args[0][0]
    assert res2["status"] == "success"
    assert res2["agent"]["enabled"] is True

    active_manifests2 = registry.get_manifests(include_disabled=False)
    assert any(m["id"] == "health" for m in active_manifests2)


def test_customize_and_reset_agent(mock_fleet_env):
    from fleet.api.settings_api import customize_agent_settings, reset_agent_settings

    handler = MagicMock()

    # Customize
    customize_agent_settings(handler, {
        "id": "overview",
        "name": "Fleet Ops Center",
        "icon": "🪐",
        "order": 2,
        "model": "gemini-2.5-pro",
    })
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "success"
    assert res["agent"]["name"] == "Fleet Ops Center"
    assert res["agent"]["icon"] == "🪐"
    assert res["agent"]["model"] == "gemini-2.5-pro"

    # Reset
    handler.reset_mock()
    reset_agent_settings(handler, {"id": "overview"})
    res_reset = handler._send_json.call_args[0][0]
    assert res_reset["status"] == "success"
    assert res_reset["agent"]["name"] == "Overview & Tasks"
    assert res_reset["agent"]["icon"] == "⚡"


def test_settings_api_error_branches(mock_fleet_env):
    from fleet.api.settings_api import (
        toggle_agent_activation,
        customize_agent_settings,
        reset_agent_settings,
        create_backup_snapshot,
        get_fleet_settings,
        update_fleet_settings,
    )

    handler = MagicMock()

    # 1. Missing id
    toggle_agent_activation(handler, {"id": ""})
    assert handler._send_json.call_args[1].get("status") == 400
    handler.reset_mock()

    customize_agent_settings(handler, {"id": ""})
    assert handler._send_json.call_args[1].get("status") == 400
    handler.reset_mock()

    reset_agent_settings(handler, {"id": ""})
    assert handler._send_json.call_args[1].get("status") == 400
    handler.reset_mock()

    # 2. Registry unavailable
    with patch.object(srv, "agent_registry", None):
        toggle_agent_activation(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 503
        handler.reset_mock()

        customize_agent_settings(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 503
        handler.reset_mock()

        reset_agent_settings(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 503
        handler.reset_mock()

    # 3. Not found (KeyError)
    toggle_agent_activation(handler, {"id": "non_existent_agent_999"})
    assert handler._send_json.call_args[1].get("status") == 404
    handler.reset_mock()

    customize_agent_settings(handler, {"id": "non_existent_agent_999"})
    assert handler._send_json.call_args[1].get("status") == 404
    handler.reset_mock()

    reset_agent_settings(handler, {"id": "non_existent_agent_999"})
    assert handler._send_json.call_args[1].get("status") == 404
    handler.reset_mock()

    # 4. Unexpected Exception
    with patch.object(srv.agent_registry, "customize_agent", side_effect=RuntimeError("Boom")):
        toggle_agent_activation(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 500
        handler.reset_mock()

        customize_agent_settings(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 500
        handler.reset_mock()

    with patch.object(srv.agent_registry, "reset_agent", side_effect=RuntimeError("Boom")):
        reset_agent_settings(handler, {"id": "health"})
        assert handler._send_json.call_args[1].get("status") == 500
        handler.reset_mock()

    # 5. Backup snapshot copy error
    from fleet.config import DATA_DIR
    dummy_db = DATA_DIR / "fleet.db"
    dummy_db.write_text("dummy", encoding="utf-8")
    with patch("shutil.copy2", side_effect=PermissionError("Locked")):
        create_backup_snapshot(handler, {})
        assert handler._send_json.call_args[1].get("status") == 500

