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
    try:
        with patch("shutil.copy2", side_effect=PermissionError("Locked")):
            create_backup_snapshot(handler, {})
            assert handler._send_json.call_args[1].get("status") == 500
    finally:
        dummy_db.unlink(missing_ok=True)



def test_customize_agent_specific_settings(mock_fleet_env):
    from fleet.api.settings_api import customize_agent_settings

    handler = MagicMock()
    customize_agent_settings(handler, {
        "id": "health",
        "settings": {
            "daily_water_target_liters": 4.5,
            "daily_calorie_target": 2200,
            "enable_meal_reminders": False,
        }
    })

    res = handler._send_json.call_args[0][0]
    assert res["status"] == "success"
    assert "agent" in res
    assert res["agent"]["settings"]["daily_water_target_liters"] == 4.5
    assert res["agent"]["settings"]["daily_calorie_target"] == 2200
    assert res["agent"]["settings"]["enable_meal_reminders"] is False

    # Check live agent instance
    registry = mock_fleet_env["registry"]
    agent = registry.agents.get("health")
    assert agent is not None
    assert agent.get_setting("daily_water_target_liters") == 4.5
    assert agent.get_setting("daily_calorie_target") == 2200

    # Check enriched schema in UI manifest
    manifest = agent.get_ui_manifest()
    water_schema = next((s for s in manifest["agent_settings_schema"] if s["id"] == "daily_water_target_liters"), None)
    assert water_schema is not None
    assert water_schema["value"] == 4.5


def test_all_builtin_agents_declare_settings_schema(mock_fleet_env):
    registry = mock_fleet_env["registry"]
    manifests = registry.get_manifests(include_disabled=True)
    expected_ids = {"health", "overview", "optimizer", "antigravity", "backlog", "gmail", "pr_review"}

    for m in manifests:
        if m["id"] in expected_ids:
            agent = registry.agents.get(m["id"]) or registry.disabled_agents.get(m["id"])
            assert agent is not None
            schema = agent.get_agent_settings_schema()
            assert isinstance(schema, list)
            assert len(schema) >= 3
            for item in schema:
                assert "id" in item
                assert "label" in item
                assert "type" in item
                assert "default" in item


def test_version_endpoints_and_updater(mock_fleet_env):
    from fleet.api.settings_api import get_fleet_version_status, check_fleet_version_update, apply_fleet_update
    from fleet.core.updater import (
        parse_version_tuple,
        check_github_for_updates,
        download_and_apply_update,
        check_and_notify_on_startup,
        start_startup_update_check,
    )

    # 1. Version parsing
    assert parse_version_tuple("v2.5.0") == (2, 5, 0)
    assert parse_version_tuple("2.6.1-beta") == (2, 6, 1)
    assert parse_version_tuple("invalid") == (0, 0, 0)

    # 2. Check for updates mock (newer version available)
    from fleet.config import get_live_version
    future_major = parse_version_tuple(get_live_version())[0] + 10
    future_ver = f"{future_major}.0.0"
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "tag_name": f"v{future_ver}",
            "name": f"Fleet Release v{future_ver}",
            "body": "Major release with new autonomous agent capabilities",
            "html_url": f"https://github.com/macazaka/personal-agentic-fleet/releases/tag/v{future_ver}",
            "zipball_url": f"https://github.com/macazaka/personal-agentic-fleet/archive/refs/tags/v{future_ver}.zip",
            "published_at": "2026-10-27T00:00:00Z"
        }).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_resp

        res = check_github_for_updates()
        assert res["status"] == "success"
        assert res["update_available"] is True
        assert res["latest_version"] == future_ver

    # 3. Check for updates mock (already up to date)
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.5.0",
            "name": "Fleet v2.5.0",
            "body": "Current version",
        }).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_resp

        res_same = check_github_for_updates()
        assert res_same["update_available"] is False

    # 4. Check for updates mock (offline fallback)
    with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
        res_off = check_github_for_updates()
        assert res_off["status"] == "offline"
        assert res_off["update_available"] is False

    # 5. REST endpoints
    handler = MagicMock()
    with patch("fleet.core.updater.check_github_for_updates", return_value={"status": "success", "update_available": True, "latest_version": "2.6.0"}):
        get_fleet_version_status(handler, urllib.parse.urlparse("/api/settings/version"))
        assert handler._send_json.called
        assert handler._send_json.call_args[0][0]["latest_version"] == "2.6.0"

        handler.reset_mock()
        check_fleet_version_update(handler, {})
        assert handler._send_json.called

    handler.reset_mock()
    with patch("fleet.core.updater.download_and_apply_update", return_value={"status": "success", "message": "Pulled latest"}):
        apply_fleet_update(handler, {})
        assert handler._send_json.called
        assert handler._send_json.call_args[0][0]["status"] == "success"

    # 6. Startup notification check
    with patch("fleet.core.updater.check_github_for_updates", return_value={"status": "success", "update_available": True, "latest_version": "2.9.0"}),          patch("fleet.core.updater.send_notification") as mock_notify:
        check_and_notify_on_startup(mock_fleet_env["db"])
        assert mock_notify.called
        assert "2.9.0" in mock_notify.call_args[0][0]

    # 7. Start thread helper
    with patch("threading.Thread.start") as mock_thread_start:
        start_startup_update_check(mock_fleet_env["db"])
        assert mock_thread_start.called

    # 8. Download and apply update (git pull branch & zip download branch)
    tmp_repo = mock_fleet_env["tmp_path"] / "repo"
    tmp_repo.mkdir(parents=True, exist_ok=True)
    git_dir = tmp_repo / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Updating e199cef..0813157\nFast-forward")
        res_git = download_and_apply_update(repo_root=tmp_repo)
        assert res_git["status"] == "success"
        assert res_git["mode"] == "git_pull"

    # Non-git directory fallback to zip download
    non_git_repo = mock_fleet_env["tmp_path"] / "nongit"
    non_git_repo.mkdir(parents=True, exist_ok=True)
    with patch("urllib.request.urlretrieve") as mock_retrieve:
        res_zip = download_and_apply_update(repo_root=non_git_repo)
        assert res_zip["status"] == "success"
        assert res_zip["mode"] == "zip_download"


def test_agent_catalog_endpoints_and_install(mock_fleet_env):
    from fleet.api.settings_api import get_agent_catalog_list, install_catalog_agent
    from fleet.core.agent_catalog import get_agent_catalog, install_agent_from_catalog

    # 1. Direct Catalog Listing
    catalog = get_agent_catalog(installed_agent_ids={"health", "crypto_trader"})
    assert len(catalog) >= 5
    crypto_item = next((c for c in catalog if c["id"] == "crypto_trader"), None)
    assert crypto_item is not None
    assert crypto_item["is_installed"] is True
    home_item = next((c for c in catalog if c["id"] == "home_assistant"), None)
    assert home_item is not None
    assert home_item["is_installed"] is False

    # 2. REST GET /api/settings/agents/catalog
    handler = MagicMock()
    get_agent_catalog_list(handler, urllib.parse.urlparse("/api/settings/agents/catalog"))
    assert handler._send_json.called
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "ok"
    assert "catalog" in res
    assert res["total_available"] >= 5

    # 3. Direct install of home_assistant
    custom_dir = mock_fleet_env["tmp_path"] / "custom_agents"
    registry = mock_fleet_env["registry"]
    inst_res = install_agent_from_catalog("home_assistant", custom_dir, agent_registry=registry)
    assert inst_res["status"] == "success"
    assert inst_res["agent_id"] == "home_assistant"

    # Verify files created on disk
    agent_dir = custom_dir / "home_assistant"
    assert (agent_dir / "manifest.json").is_file()
    assert (agent_dir / "agent.py").is_file()
    assert (agent_dir / "ui" / "panel.html").is_file()

    # 4. REST install via endpoint
    handler.reset_mock()
    install_catalog_agent(handler, {"id": "research_scholar"})
    assert handler._send_json.called
    res_ep = handler._send_json.call_args[0][0]
    assert res_ep["status"] == "success"
    assert res_ep["agent_id"] == "research_scholar"

    # 5. Invalid / unknown agent install error handling
    handler.reset_mock()
    install_catalog_agent(handler, {"id": ""})
    assert handler._send_json.call_args[1].get("status") == 400

    handler.reset_mock()
    install_catalog_agent(handler, {"id": "unknown_super_agent_xyz"})
    assert handler._send_json.call_args[1].get("status") == 404


def test_updater_and_settings_edge_cases(mock_fleet_env):
    import urllib.error
    import urllib.parse
    from fleet.api.settings_api import get_fleet_version_status, check_fleet_version_update, get_agent_catalog_list, install_catalog_agent
    from fleet.core.updater import check_github_for_updates, download_and_apply_update

    handler = MagicMock()

    # 1. Fallback raw URL when Releases API fails
    from fleet.config import get_live_version
    from fleet.core.updater import parse_version_tuple
    future_ver = f"{parse_version_tuple(get_live_version())[0] + 10}.9.9"
    raw_payload = f'__version__ = "{future_ver}"\n'.encode("utf-8")
    def fake_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "releases/latest" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", MagicMock(), None)
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(status=200, read=lambda: raw_payload)
        return cm

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        info = check_github_for_updates()
        assert info["latest_version"] == future_ver
        assert info["update_available"] is True

    # 2. Both Releases API and Raw fail
    with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
        info_down = check_github_for_updates()
        assert info_down["status"] == "offline"
        assert info_down["update_available"] is False

    # 3. download_and_apply_update exception & failed git pull
    tmp_repo = mock_fleet_env["tmp_path"] / "broken_git"
    (tmp_repo / ".git").mkdir(parents=True)
    with patch("subprocess.run", side_effect=RuntimeError("Git broken")):
        res_fail = download_and_apply_update(repo_root=tmp_repo)
        assert res_fail["status"] == "error"

    with patch("subprocess.run") as mock_run_fail:
        mock_run_fail.return_value = MagicMock(returncode=1, stderr="fatal: merge conflict", stdout="")
        res_fail_pull = download_and_apply_update(repo_root=tmp_repo)
        assert res_fail_pull["status"] == "error"
        assert res_fail_pull["mode"] == "git_pull"

    # 4. check_fleet_version_update POST exception
    from fleet.api.settings_api import apply_fleet_update
    handler.reset_mock()
    with patch("fleet.core.updater.check_github_for_updates", side_effect=Exception("Check error")):
        check_fleet_version_update(handler, {})
        assert handler._send_json.call_args[1].get("status") == 500

    # 5. apply_fleet_update POST exception
    handler.reset_mock()
    with patch("fleet.core.updater.download_and_apply_update", side_effect=Exception("Upgrade error")):
        apply_fleet_update(handler, {})
        assert handler._send_json.call_args[1].get("status") == 500

    # 6. get_fleet_version_status GET exception
    handler.reset_mock()
    with patch("fleet.core.updater.check_github_for_updates", side_effect=Exception("Check error")):
        get_fleet_version_status(handler, urllib.parse.urlparse("/api/settings/version"))
        assert handler._send_json.call_args[1].get("status") == 500

    # 7. get_agent_catalog_list exception
    handler.reset_mock()
    with patch("fleet.core.agent_catalog.get_agent_catalog", side_effect=Exception("Catalog failure")):
        get_agent_catalog_list(handler, urllib.parse.urlparse("/api/settings/agents/catalog"))
        assert handler._send_json.call_args[1].get("status") == 500

    # 8. install_catalog_agent exception
    handler.reset_mock()
    with patch("fleet.core.agent_catalog.install_agent_from_catalog", side_effect=Exception("Install failure")):
        install_catalog_agent(handler, {"id": "crypto_trader"})
        assert handler._send_json.call_args[1].get("status") == 500

    # 9. Additional settings_api branches
    from fleet.api.settings_api import update_fleet_settings, create_backup_snapshot
    import fleet.server as srv_mod

    # Non-dict settings payload
    handler.reset_mock()
    update_fleet_settings(handler, "not-a-dict")
    assert handler._send_json.call_args[1].get("status") == 400

    handler.reset_mock()
    update_fleet_settings(handler, {"settings": "not-a-dict"})
    assert handler._send_json.call_args[1].get("status") == 400

    # Skipped keys in update_fleet_settings
    handler.reset_mock()
    update_fleet_settings(handler, {"settings": {"status": "ignored", "dark_mode": "true"}})
    assert handler._send_json.called

    # Success path of create_backup_snapshot
    handler.reset_mock()
    create_backup_snapshot(handler, {})
    assert handler._send_json.called
    res_snap = handler._send_json.call_args[0][0]
    assert res_snap["status"] == "success"

    # install_catalog_agent registry unavailable & custom_dir fallback
    handler.reset_mock()
    orig_reg = getattr(srv_mod, "agent_registry", None)
    try:
        srv_mod.agent_registry = None
        install_catalog_agent(handler, {"id": "crypto_trader"})
        assert handler._send_json.call_args[1].get("status") == 503

        # custom_dir fallback
        srv_mod.agent_registry = MagicMock(custom_agents_dir=None)
        with patch("fleet.core.agent_catalog.install_agent_from_catalog", return_value={"status": "success", "agent_id": "crypto_trader"}):
            handler.reset_mock()
            install_catalog_agent(handler, {"id": "crypto_trader"})
            assert handler._send_json.called
    finally:
        srv_mod.agent_registry = orig_reg



def test_create_new_agent_endpoint(mock_fleet_env):
    from fleet.api.settings_api import create_new_agent_endpoint
    import fleet.server as srv_mod

    handler = MagicMock()

    # 1. Non-dict body
    create_new_agent_endpoint(handler, "not-a-dict")
    assert handler._send_json.call_args[1].get("status") == 400

    # 2. Missing name
    handler.reset_mock()
    create_new_agent_endpoint(handler, {"name": ""})
    assert handler._send_json.call_args[1].get("status") == 400

    # 3. Invalid sanitized ID
    handler.reset_mock()
    create_new_agent_endpoint(handler, {"name": "???", "id": "???"})
    assert handler._send_json.call_args[1].get("status") == 400

    # 4. Registry unavailable (503)
    handler.reset_mock()
    orig_reg = getattr(srv_mod, "agent_registry", None)
    try:
        srv_mod.agent_registry = None
        create_new_agent_endpoint(handler, {"name": "Test Agent", "id": "test_agent"})
        assert handler._send_json.call_args[1].get("status") == 503
    finally:
        srv_mod.agent_registry = orig_reg

    # 5. Duplicate agent ID (409)
    handler.reset_mock()
    create_new_agent_endpoint(handler, {"name": "Health Duplicate", "id": "health"})
    assert handler._send_json.call_args[1].get("status") == 409

    # 5b. Invalid permissions (400)
    handler.reset_mock()
    create_new_agent_endpoint(handler, {"name": "Hacker Agent", "id": "hacker_agent", "permissions": ["unauthorized:all"]})
    assert handler._send_json.call_args[1].get("status") == 400

    # 6. Successful creation with custom settings and prompts
    handler.reset_mock()
    create_new_agent_endpoint(handler, {
        "name": "Weather Sentinel",
        "id": "weather_sentinel",
        "icon": "🌤️",
        "description": "Monitors atmospheric changes.",
        "permissions": ["db:read", "ui:render", "network:http"],
        "settings": {
            "poll_interval": 120,
            "enable_rain_alert": True
        },
        "system_prompt": "You are a weather watcher.",
        "prompt": "Check radar"
    })
    assert handler._send_json.called
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "success"
    assert res["agent_id"] == "weather_sentinel"
    assert "manifest" in res

    # Verify agent was loaded into live registry
    registry = mock_fleet_env["registry"]
    agent = registry.agents.get("weather_sentinel")
    assert agent is not None
    assert agent.name == "Weather Sentinel"
    assert agent.icon == "🌤️"
    assert agent.get_setting("poll_interval") == 120

    # 7. Unexpected exception during creation (500)
    handler.reset_mock()
    with patch.object(srv_mod.agent_registry, "create_custom_agent", side_effect=RuntimeError("Disk full")):
        create_new_agent_endpoint(handler, {"name": "Failing Agent", "id": "failing_agent"})
        assert handler._send_json.call_args[1].get("status") == 500

    # 8. ValueError during creation (400)
    handler.reset_mock()
    with patch.object(srv_mod.agent_registry, "create_custom_agent", side_effect=ValueError("Invalid config")):
        create_new_agent_endpoint(handler, {"name": "Bad Agent", "id": "bad_agent"})
        assert handler._send_json.call_args[1].get("status") == 400


def test_scalable_layouts_and_themes_for_100_agents(mock_fleet_env):
    """Verifies the 3 scalable layouts for 100+ agents and 4 color themes in settings API and UI."""
    from fleet.api.settings_api import get_fleet_settings, update_fleet_settings
    from fleet.web.builder import get_dashboard_html

    handler = MagicMock()
    parsed_url = urllib.parse.urlparse("/api/settings")
    get_fleet_settings(handler, parsed_url)

    res = handler._send_json.call_args[0][0]
    assert res["status"] == "ok"
    assert res["settings"]["layout"] == "sidebar_dock"
    assert res["settings"]["theme"] == "dark"
    assert len(res["available_layouts"]) == 3
    layout_ids = [item["id"] for item in res["available_layouts"]]
    assert layout_ids == ["sidebar_dock", "command_deck", "launchpad_grid"]
    assert len(res["available_themes"]) == 4

    # Persist each of the 3 layouts
    for layout_mode in ("sidebar_dock", "command_deck", "launchpad_grid"):
        handler.reset_mock()
        update_fleet_settings(handler, {"layout": layout_mode, "theme": "aurora"})
        upd_res = handler._send_json.call_args[0][0]
        assert upd_res["status"] == "success"
        assert upd_res["settings"]["layout"] == layout_mode
        assert upd_res["settings"]["theme"] == "aurora"

    # Verify HTML & bundled JS include all 3 layout containers and non-duplicating nav logic
    standalone_html = get_dashboard_html(standalone=True)
    for required_token in (
        'data-layout="sidebar_dock"',
        "fleetLeftSidebarDock",
        "wccCommandDeckBar",
        "fleetLaunchpadMatrix",
        "genSettingLayout",
        "headerQuickLayoutSelect",
        "layoutCard_sidebar_dock",
        "layoutCard_command_deck",
        "layoutCard_launchpad_grid",
        "STATIC_CORE_TAB_IDS",
        "setWorkspaceLayout",
    ):
        assert required_token in standalone_html, f"Missing {required_token} in bundled dashboard HTML"


def test_zero_duplicate_agent_info_on_wcc(mock_fleet_env):
    """Verifies zero duplicate agent entries, zero duplicate DOM IDs, and zero duplicate sections per agent."""
    import collections
    import pathlib
    import re
    from fleet.api.settings_api import get_fleet_settings

    # 1. Verify /api/settings returns strictly unique agent IDs
    handler = MagicMock()
    parsed_url = urllib.parse.urlparse("/api/settings")
    get_fleet_settings(handler, parsed_url)
    res = handler._send_json.call_args[0][0]
    agent_ids = [a["id"] for a in res["agents"]]
    assert len(agent_ids) == len(set(agent_ids)), f"Duplicate agent IDs in /api/settings: {agent_ids}"

    # 2. Verify zero duplicate HTML element IDs in dashboard.html
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    dash_html = (root_dir / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    dom_ids = re.findall(r'\bid="([^"]+)"', dash_html)
    dup_dom_ids = {k: v for k, v in collections.Counter(dom_ids).items() if v > 1}
    assert not dup_dom_ids, f"Duplicate HTML element IDs found in dashboard.html: {dup_dom_ids}"

    # 3. Verify removed duplicate widgets/inputs are absent from dashboard.html
    for removed_dup_id in ("settingsAgentSearch", "createAgentInlineForm", "healthWaterBigCount", "quickOptRam"):
        assert f'id="{removed_dup_id}"' not in dash_html, f"Duplicate widget {removed_dup_id} should be removed"

    # 4. Verify FleetNavigator deduplicates agents in fetchFleetData and renderLeftSidebarDock
    nav_js = (root_dir / "fleet" / "web" / "static" / "js" / "fleet_navigator.js").read_text(encoding="utf-8")
    assert "uniqueMap" in nav_js
    assert "coreAndPinnedIds" in nav_js
    assert "!coreAndPinnedIds.has(a.id)" in nav_js
    assert "duplicateTitle" in nav_js


def test_exercise_hub_strictly_scoped_inside_health_view():
    """Verifies the Exercise, Videos & Traditional Strength Training Hub is strictly inside viewHealth."""
    import pathlib
    import re
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    dash_html = (root_dir / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")

    vh_start = dash_html.find('id="viewHealth"')
    assert vh_start != -1, "viewHealth container not found"
    vb_start = dash_html.find('id="viewBacklog"')
    assert vb_start != -1, "viewBacklog container not found"
    assert vh_start < vb_start, "viewHealth must come before viewBacklog"

    health_view_html = dash_html[vh_start:vb_start]
    assert "Exercise, Videos & Traditional Strength Training Hub" in health_view_html, (
        "Exercise Hub must be located inside viewHealth"
    )
    assert 'id="exPanelVideos"' in health_view_html
    assert 'id="exSubTabStrength"' in health_view_html


def test_zero_horizontal_scrollbars_and_afcc_branding():
    """Verifies complete horizontal scrollbar elimination and official AFCC branding."""
    import pathlib
    root_dir = pathlib.Path(__file__).resolve().parent.parent

    # 1. Verify CSS rules eliminate horizontal scrollbars
    dash_css = (root_dir / "fleet" / "web" / "static" / "css" / "dashboard.css").read_text(encoding="utf-8")
    assert "*::-webkit-scrollbar:horizontal" in dash_css
    assert "display: none !important" in dash_css
    assert ".settings-nav-tabs" in dash_css
    assert "flex-wrap: wrap" in dash_css
    assert "overflow-x: hidden" in dash_css

    # 2. Verify AFCC branding in HTML
    dash_html = (root_dir / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "Agentic Fleet Control Center (AFCC)" in dash_html
    assert "Personal Agentic Fleet — Agentic Fleet Control Center (AFCC)" in dash_html


def test_proactive_vscode_html_css_auditor_and_auto_fixer():
    """Verifies zero VS Code HTML/CSS/Settings diagnostics across the repository and tests auto-repair."""
    import pathlib
    from fleet.tools.auto_fixer import (
        _repair_style_attribute_value,
        audit_vscode_workspace_problems,
    )

    root_dir = pathlib.Path(__file__).resolve().parent.parent

    # 1. Verify entire repo has 0 VS Code HTML/CSS/Settings problems
    audit = audit_vscode_workspace_problems(repo_root=root_dir)
    assert audit["status"] == "PASS", f"VS Code problems found: {audit['problems']}"
    assert audit["problems_count"] == 0

    # 2. Verify _repair_style_attribute_value safely repairs both missing ')' and stray ')'
    # Case A: stray ')' after hex color (e.g., color: #c084fc);)
    assert _repair_style_attribute_value("color: #c084fc); font-weight: 700;") == "color: #c084fc; font-weight: 700;"
    # Case B: missing ')' in CSS function (e.g., color: var(--text;)
    assert _repair_style_attribute_value("color: var(--text; background: rgba(16, 185, 129, 0.1;") == (
        "color: var(--text); background: rgba(16, 185, 129, 0.1);"
    )
    # Case C: already valid CSS functions are never corrupted
    valid_style = "background: var(--bg-card); border: 1px solid rgba(56, 189, 248, 0.35); color: #38bdf8;"
    assert _repair_style_attribute_value(valid_style) == valid_style

    # 3. Verify GitHub Actions workflow & Immutable Release protections in .github/workflows/
    release_yml = (root_dir / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "gh release view" in release_yml
    assert "gh release create" in release_yml
    assert "softprops/action-gh-release" not in release_yml
    assert "ubuntu-24.04" in release_yml
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" in release_yml


def test_afcc_all_buttons_have_tooltips_sop():
    """
    SOP Verification: All buttons across AFCC (dashboard.html and agent UI panels)
    MUST have a descriptive title tooltip attribute explaining what the button does.
    """
    import re
    from pathlib import Path

    root_dir = Path(__file__).resolve().parent.parent
    html_files = list((root_dir / "fleet").rglob("*.html"))
    assert len(html_files) >= 5, "Expected HTML templates in fleet/"

    btn_pattern = re.compile(r'<button\b([^>]*)>(.*?)</button>', re.DOTALL | re.IGNORECASE)
    missing_tooltips = []

    for fpath in html_files:
        content = fpath.read_text(encoding="utf-8")
        for m in btn_pattern.finditer(content):
            attrs = m.group(1)
            if not re.search(r'\btitle\s*=', attrs, re.IGNORECASE):
                line_no = content[:m.start()].count('\n') + 1
                missing_tooltips.append(f"{fpath.relative_to(root_dir)}:L{line_no} -> {m.group(0)[:80]}")

    assert not missing_tooltips, (
        f"AFCC SOP Violation: Found {len(missing_tooltips)} buttons without title tooltips:\n"
        + "\n".join(missing_tooltips)
    )


def test_improvise_prompt_and_backlog_first_self_improvement_pipeline(mock_fleet_env):
    """
    Verifies:
    1. Context-aware prompt improvisation (`POST /api/studio/evolve/improvise`) understands the specific agent
       context (e.g., Health & Wellness vs. Overview & Tasks) and returns a multi-line reviewable prompt.
    2. Undertaking a manual improvement (`POST /api/settings/agents/evolve`) first registers the item in
       `feature_backlog` (`Planned` -> `In Progress`) and then executes it to completion (`Completed`, 100%),
       recording the LLM textual response (`llm_response`) and 4-stage `execution_steps`.
    3. Live status & LLM textual response endpoint (`GET /api/studio/evolve/status`) returns the enriched status.
    """
    from fleet.api.settings_api import (
        evolve_custom_agent_endpoint,
        get_agent_evolve_status_endpoint,
        improvise_evolve_prompt_endpoint,
    )

    handler = MagicMock()

    # 1. Improvise inside Health & Wellness agent
    improvise_evolve_prompt_endpoint(handler, {
        "id": "health",
        "text": "alert me when post meal glucose spikes above 140",
    })
    res_health = handler._send_json.call_args[0][0]
    assert res_health["status"] == "ok"
    assert res_health["agent_id"] == "health"
    assert "\n" in res_health["improvised_text"]
    assert "FFD" in res_health["improvised_text"] or "Glucose" in res_health["improvised_text"]
    assert "FFD" in res_health["domain_title"]

    # 2. Improvise inside Overview & Tasks agent
    handler.reset_mock()
    improvise_evolve_prompt_endpoint(handler, {
        "id": "overview",
        "text": "enhance code coverage to over 99.5%",
    })
    res_ov = handler._send_json.call_args[0][0]
    assert res_ov["status"] == "ok"
    assert res_ov["agent_id"] == "overview"
    assert "\n" in res_ov["improvised_text"]
    assert "Coverage" in res_ov["improvised_text"] or "Pytest" in res_ov["improvised_text"]

    # 3. Undertake manual improvement -> must go to Feature Backlog first and execute to completion
    handler.reset_mock()
    evolve_custom_agent_endpoint(handler, {
        "id": "health",
        "evolution_improvements": [
            {
                "id": "custom_glucose_spike_guard",
                "title": "Post-Prandial Glucose Spike Guard (>140 mg/dL)",
                "description": res_health["improvised_text"],
                "code_enhancement_brief": res_health["improvised_text"],
                "is_custom": True,
            }
        ],
    })
    evo_res = handler._send_json.call_args[0][0]
    assert evo_res["status"] == "success"
    undertaken = evo_res["manifest"]["evolution_improvements"]
    assert len(undertaken) >= 1
    latest = undertaken[-1]
    assert latest["status"] == "completed"
    assert latest["progress"] == 100
    assert latest["backlog_id"] > 0
    assert latest["backlog_status"] == "Completed"
    assert "Self-Improvement Executed to Completion" in latest["llm_response"]
    assert len(latest["execution_steps"]) == 4

    # Verify the Feature Backlog SQLite row exists and is Completed
    db = mock_fleet_env["db"]
    bl_items = db.list_feature_backlog_items(status="Completed")
    assert any(int(item["id"]) == int(latest["backlog_id"]) for item in bl_items)

    # 4. Query live status endpoint
    handler.reset_mock()
    get_agent_evolve_status_endpoint(handler, {"id": ["health"]})
    st_res = handler._send_json.call_args[0][0]
    assert st_res["status"] == "ok"
    assert st_res["agent_id"] == "health"
    assert st_res["undertaken_count"] >= 1
    assert st_res["improvements"][-1]["backlog_id"] == latest["backlog_id"]


def test_bidirectional_voice_conversation_and_linked_activities(mock_fleet_env):
    import urllib.parse
    from fleet.api.settings_api import get_voice_activities_endpoint, post_voice_converse_endpoint

    handler = MagicMock()

    # 1. GET /api/voice/activities
    get_voice_activities_endpoint(handler, urllib.parse.urlparse("/api/voice/activities"))
    cat_res = handler._send_json.call_args[0][0]
    assert cat_res["status"] == "ok"
    assert cat_res["count"] >= 10
    assert any(a["id"] == "voice_monthly_tasks" for a in cat_res["activities"])

    # 2. Voice: Add monthly task & filter monthly tasks
    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Add monthly task Review domain renewals"})
    add_res = handler._send_json.call_args[0][0]
    assert add_res["status"] == "ok"
    assert add_res["mode"] == "voice_task_created"
    assert "spoken_reply" in add_res
    assert any(a.get("type") == "refresh_tasks" for a in add_res.get("ui_actions", []))

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Show my monthly tasks"})
    m_res = handler._send_json.call_args[0][0]
    assert m_res["status"] == "ok"
    assert m_res["normalized_command"] == "filter_tasks:Monthly"
    assert any(a.get("type") == "filter_tasks" and a.get("filter") == "Monthly" for a in m_res["ui_actions"])
    assert len(m_res["executed_activities"]) >= 1

    # 3. Voice: Complete task by title
    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Complete task Review domain renewals"})
    comp_res = handler._send_json.call_args[0][0]
    assert comp_res["status"] == "ok"
    assert comp_res["mode"] == "voice_task_completed"
    assert "completed" in comp_res["spoken_reply"].lower()

    # 4. Voice: Mask & Reveal sensitive IDs
    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Mask sensitive IDs"})
    mask_res = handler._send_json.call_args[0][0]
    assert mask_res["status"] == "ok"
    assert any(a.get("type") == "set_task_mask" and a.get("masked") is True for a in mask_res["ui_actions"])

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Reveal account numbers"})
    unmask_res = handler._send_json.call_args[0][0]
    assert unmask_res["status"] == "ok"
    assert any(a.get("type") == "set_task_mask" and a.get("masked") is False for a in unmask_res["ui_actions"])

    # 5. Voice: Log health vitals (weight & fasting sugar)
    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Log weight 74.5 kg"})
    wt_res = handler._send_json.call_args[0][0]
    assert wt_res["status"] == "ok"
    assert wt_res["agent_id"] == "health"
    assert "74.5" in wt_res["spoken_reply"]

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Log fasting sugar 96"})
    sg_res = handler._send_json.call_args[0][0]
    assert sg_res["status"] == "ok"
    assert sg_res["agent_id"] == "health"
    assert "96" in sg_res["spoken_reply"]

    # 6. Voice: Email Intelligence, Virus Shield, Backlog, and Self-Improvement
    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Check my emails and scan attachments"})
    em_res = handler._send_json.call_args[0][0]
    assert em_res["status"] == "ok"
    assert any(a.get("type") == "refresh_emails" for a in em_res["ui_actions"])

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Run antivirus block test"})
    av_res = handler._send_json.call_args[0][0]
    assert av_res["status"] == "ok"
    assert any(a.get("type") == "test_virus_shield" for a in av_res["ui_actions"])

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Show unapproved backlog items"})
    bl_res = handler._send_json.call_args[0][0]
    assert bl_res["status"] == "ok"
    assert any(a.get("type") == "filter_backlog" and a.get("status") == "Unapproved" for a in bl_res["ui_actions"])

    handler.reset_mock()
    post_voice_converse_endpoint(handler, {"transcript": "Suggest 10 ways to improve overview"})
    ev_res = handler._send_json.call_args[0][0]
    assert ev_res["status"] == "ok"
    assert any(a.get("type") == "open_evolve_modal" and a.get("agent_id") == "overview" for a in ev_res["ui_actions"])


def test_api_first_and_mcp_ready_architecture(mock_fleet_env):
    import json
    import urllib.parse
    from fleet.api.router import router
    from fleet.api.system_api import (
        get_architecture_manifest_endpoint,
        get_mcp_tools_endpoint,
        get_openapi_spec_endpoint,
        post_mcp_call_endpoint,
    )
    from fleet.mcp_server import (
        fleet_call_api,
        fleet_email_proposals_and_virus_scan,
        fleet_evolve_agent,
        fleet_health_action,
        fleet_manage_backlog,
        fleet_optimize_and_audit,
        fleet_voice_converse,
        invoke_mcp_tool,
        list_mcp_tools_metadata,
    )

    handler = MagicMock()

    # 1. Architecture Manifest endpoint verifies all 12 badge pillars + API-First & MCP-Ready metadata
    get_architecture_manifest_endpoint(handler, urllib.parse.urlparse("/api/architecture/manifest"))
    arch = handler._send_json.call_args[0][0]
    assert arch["status"] == "ok"
    assert arch["architecture"] == "Zero-Token Microkernel"
    assert arch["privacy"] == "100% Local-First DPAPI"
    assert arch["security_audit"] == "100/100 [12 Layers]"
    assert arch["wiki"] == "17 Deep-Dive Guides"
    assert arch["python"] == "3.10 | 3.11 | 3.12 | 3.13 | 3.14"
    assert arch["python_versions"] == ["3.10", "3.11", "3.12", "3.13", "3.14"]
    assert "Google" in arch["hyperscalers"] and "Ollama" in arch["hyperscalers"]
    assert "Copilot" in arch["dev_tools"] and "Amazon Q" in arch["dev_tools"]
    assert arch["api_first"]["enabled"] is True
    assert arch["api_first"]["rest_endpoints_count"] >= 40
    assert arch["mcp_ready"]["enabled"] is True
    assert arch["mcp_ready"]["mcp_tools_count"] >= 28

    # Verify README.md & wiki/Home.md badge icons and multi-version Python parity
    import re
    from fleet.config import BASE_DIR, SUPPORTED_PYTHON_VERSIONS

    repo_root = BASE_DIR.parent
    assert SUPPORTED_PYTHON_VERSIONS == ("3.10", "3.11", "3.12", "3.13", "3.14")
    py_ver_lines = [
        ln.strip()
        for ln in (repo_root / ".python-version").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    for pv in SUPPORTED_PYTHON_VERSIONS:
        assert pv in py_ver_lines

    for md_rel in ("README.md", "wiki/Home.md"):
        md_txt = (repo_root / md_rel).read_text(encoding="utf-8")
        badge_urls = re.findall(r"\[\!\[[^\]]+\]\((https://img\.shields\.io/badge/[^\)]+)\)\]", md_txt)
        assert len(badge_urls) >= 18, f"Expected >= 18 badges in {md_rel}"
        assert any("Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14" in u for u in badge_urls)
        for u in badge_urls:
            path_part = u.split("?", 1)[0]
            assert "?logo=" in u, f"Missing ?logo= icon parameter in {md_rel}: {u}"
            assert "?logo=windows" not in u, f"Removed Simple Icons ?logo=windows used in {md_rel}: {u}"
            assert "%25" not in path_part and "%2B" not in path_part, f"Camo-breaking %25/%2B in badge path: {u}"

    # 2. OpenAPI 3.1.0 live spec endpoint
    handler.reset_mock()
    get_openapi_spec_endpoint(handler, urllib.parse.urlparse("/api/openapi.json"))
    spec = handler._send_json.call_args[0][0]
    assert spec["openapi"] == "3.1.0"
    assert "/api/voice/converse" in spec["paths"]
    assert "/api/mcp/tools" in spec["paths"]

    # 3. Dual-transport MCP introspection & HTTP JSON tool invocation
    handler.reset_mock()
    get_mcp_tools_endpoint(handler, urllib.parse.urlparse("/api/mcp/tools"))
    mcp_list = handler._send_json.call_args[0][0]
    assert mcp_list["status"] == "ok"
    tool_names = {t["name"] for t in mcp_list["tools"]}
    for expected_tool in (
        "fleet_voice_converse",
        "fleet_health_action",
        "fleet_email_proposals_and_virus_scan",
        "fleet_manage_backlog",
        "fleet_evolve_agent",
        "fleet_optimize_and_audit",
        "fleet_call_api",
    ):
        assert expected_tool in tool_names

    # 4. Invoke MCP tools via HTTP POST /api/mcp/call and direct function calls
    handler.reset_mock()
    post_mcp_call_endpoint(handler, {
        "tool": "fleet_voice_converse",
        "arguments": {"transcript": "Mask sensitive IDs"},
    })
    call_res = handler._send_json.call_args[0][0]
    assert call_res["status"] == "ok"
    assert call_res["result"]["normalized_command"] == "task_mask:on"

    # Direct MCP tool checks
    h_out = json.loads(fleet_health_action(action="log_water", value=1))
    assert h_out["status"] == "ok"

    bl_out = json.loads(fleet_manage_backlog(action="list", statuses="Planned,Completed", priorities="P1,P2"))
    assert bl_out["status"] == "ok"

    ev_out = json.loads(fleet_evolve_agent(agent_id="overview", action="improvise", manual_text="improve task filters"))
    assert ev_out["status"] == "ok"

    em_out = json.loads(fleet_email_proposals_and_virus_scan(action="list_proposals", status="Unapproved"))
    assert em_out["status"] == "ok"

    api_bridge_out = json.loads(fleet_call_api(method="GET", path="/api/voice/activities"))
    assert api_bridge_out["status"] == "ok"
    assert api_bridge_out["status_code"] == 200










