import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.core.base_agent import FleetAgent
from fleet.core.registry import AgentRegistry
from fleet.config import load_fleet_config
from fleet.api.router import ApiRouter


class DummyTestAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "dummy_test"

    @property
    def name(self) -> str:
        return "Dummy Test Agent"

    @property
    def icon(self) -> str:
        return "🧪"

    @property
    def order(self) -> int:
        return 999


def test_fleet_agent_base_contract(tmp_path):
    agent = DummyTestAgent(agent_dir=tmp_path, config={"enabled": True})
    assert agent.id == "dummy_test"
    assert agent.name == "Dummy Test Agent"
    assert agent.icon == "🧪"
    assert agent.order == 999
    assert agent.enabled is True

    manifest = agent.get_ui_manifest()
    assert manifest["id"] == "dummy_test"
    assert manifest["name"] == "Dummy Test Agent"
    assert manifest["icon"] == "🧪"
    assert manifest["order"] == 999


def test_agent_registry_discover_built_in_agents():
    registry = AgentRegistry()
    agents = registry.discover_and_load()

    assert "health" in agents
    assert "overview" in agents
    assert "optimizer" in agents
    assert "antigravity" in agents
    assert "backlog" in agents
    assert "gmail" in agents

    health_agent = agents["health"]
    assert health_agent.name == "Health & Wellness"
    assert health_agent.icon == "🌿"


def test_agent_registry_manifests_sorting_and_default():
    registry = AgentRegistry(config={"default_agent": "health"})
    registry.discover_and_load()
    manifests = registry.get_manifests()

    assert len(manifests) >= 5
    # Confirm health is default
    health_m = next((m for m in manifests if m["id"] == "health"), None)
    assert health_m is not None
    assert health_m["is_default"] is True

    # Confirm order sorting
    orders = [m["order"] for m in manifests]
    assert orders == sorted(orders)


def test_agent_registry_respects_disabled_agent():
    registry = AgentRegistry(config={"agents": {"gmail": {"enabled": False}}})
    agents = registry.discover_and_load()
    assert "gmail" not in agents
    assert "health" in agents


def test_load_fleet_config_defaults():
    cfg = load_fleet_config()
    assert "server" in cfg
    assert "agents" in cfg
    assert "health" in cfg["agents"]


def test_agent_customization_via_config(tmp_path):
    custom_cfg = {
        "name": "Customized Health & Fitness",
        "icon": "🏋️",
        "order": 5,
        "is_default": True,
        "provider": "anthropic",
        "model": "claude-3-7-sonnet",
        "system_prompt": "You are a metabolic fitness and workout coach.",
        "settings": {"custom_target": 10000},
    }
    agent = DummyTestAgent(agent_dir=tmp_path, config=custom_cfg)

    assert agent.display_name == "Customized Health & Fitness"
    assert agent.display_icon == "🏋️"
    assert agent.display_order == 5
    assert agent.is_active_default is True
    assert agent.preferred_provider == "anthropic"
    assert agent.preferred_model == "claude-3-7-sonnet"
    assert agent.system_prompt == "You are a metabolic fitness and workout coach."
    assert agent.get_setting("custom_target") == 10000

    manifest = agent.get_ui_manifest()
    assert manifest["name"] == "Customized Health & Fitness"
    assert manifest["icon"] == "🏋️"
    assert manifest["order"] == 5
    assert manifest["is_default"] is True
    assert manifest["provider"] == "anthropic"
    assert manifest["model"] == "claude-3-7-sonnet"
    assert manifest["is_customized"] is True


def test_agent_custom_ui_panel_override(tmp_path):
    panel_file = tmp_path / "my_custom_panel.html"
    panel_file.write_text("<h1>Custom Agent Panel</h1>", encoding="utf-8")

    agent = DummyTestAgent(
        agent_dir=tmp_path,
        config={"custom_panel_path": str(panel_file)},
    )
    manifest = agent.get_ui_manifest()
    assert "<h1>Custom Agent Panel</h1>" in manifest["html"]


def test_agent_hyperscaler_completion_helper(tmp_path):
    agent = DummyTestAgent(
        agent_dir=tmp_path,
        config={
            "provider": "google",
            "model": "gemini-2.5-pro",
            "system_prompt": "Answer in bullet points.",
        },
    )
    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
        mock_complete.return_value = {"status": "success", "response": "Mocked answer", "tokens_used": 15}
        res = agent.complete_prompt("What is Samtola?")
        assert res["status"] == "success"
        assert res["response"] == "Mocked answer"
        mock_complete.assert_called_once_with(
            prompt="What is Samtola?",
            provider="google",
            model="gemini-2.5-pro",
            system_instruction="Answer in bullet points.",
        )


def test_agent_runtime_customization_and_persistence(tmp_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir)
        registry = AgentRegistry(custom_agents_dir=vault_dir / "custom_agents")
        with patch.object(registry, "_get_overrides_file", return_value=vault_dir / "agent_overrides.json"):
            registry.discover_and_load()
            assert "health" in registry.agents

            # Customize health agent
            updated = registry.customize_agent(
                "health",
                {
                    "name": "Metabolic Command",
                    "icon": "⚡",
                    "order": 1,
                    "provider": "anthropic",
                    "model": "claude-3-7-sonnet",
                },
            )
            assert updated["name"] == "Metabolic Command"
            assert updated["icon"] == "⚡"
            assert updated["order"] == 1
            assert updated["provider"] == "anthropic"

            # Verify persisted
            overrides = registry.load_overrides()
            assert "health" in overrides
            assert overrides["health"]["name"] == "Metabolic Command"

            # Reset back to defaults
            reset = registry.reset_agent("health")
            assert reset["name"] == "Health & Wellness"
            assert reset["icon"] == "🌿"
            assert "health" not in registry.load_overrides()


def test_create_and_load_user_custom_agent():
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_agents_dir = Path(tmpdir) / "custom_agents"
        registry = AgentRegistry(custom_agents_dir=custom_agents_dir)
        registry.discover_and_load()

        # Create new custom agent
        created = registry.create_custom_agent(
            agent_id="home_iot",
            name="Smart Home Assistant",
            icon="🏠",
            permissions=["db:read", "ui:render"],
            description="Controls lights, climate, and IoT sensors.",
            initial_order=15,
        )
        assert created["id"] == "home_iot"
        assert created["name"] == "Smart Home Assistant"
        assert created["icon"] == "🏠"
        assert created["order"] == 15
        assert "home_iot" in registry.agents

        # Confirm files were created
        agent_dir = custom_agents_dir / "home_iot"
        assert (agent_dir / "manifest.json").is_file()
        assert (agent_dir / "agent.py").is_file()
        assert (agent_dir / "ui" / "panel.html").is_file()
        assert (agent_dir / "ui" / "style.css").is_file()


def test_agent_customization_api_endpoints():
    router = ApiRouter()
    registry = AgentRegistry()
    registry.discover_and_load()
    registry.register_all_routes(router)

    # 1. GET /api/fleet/agents/overview/config
    mock_handler = MagicMock()
    mock_handler.path = "/api/fleet/agents/overview/config"
    parsed_url = urllib.parse.urlparse(mock_handler.path)
    handled_get = router.dispatch_get(mock_handler, mock_handler.path, parsed_url)
    assert handled_get is True
    assert mock_handler._send_json.called
    data = mock_handler._send_json.call_args[0][0]
    assert data["status"] == "ok"
    assert data["id"] == "overview"

    # 2. POST /api/fleet/agents/overview/config
    mock_handler_post = MagicMock()
    mock_handler_post.path = "/api/fleet/agents/overview/config"
    with patch.object(registry, "save_overrides"):
        handled_post = router.dispatch_post(
            mock_handler_post,
            mock_handler_post.path,
            {"name": "Mission Control", "icon": "🛰️"},
        )
        assert handled_post is True
        assert mock_handler_post._send_json.called
        res_post = mock_handler_post._send_json.call_args[0][0]
        assert res_post["status"] == "success"
        assert res_post["agent"]["name"] == "Mission Control"
        assert res_post["agent"]["icon"] == "🛰️"
