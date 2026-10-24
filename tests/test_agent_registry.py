import pytest
from pathlib import Path
from fleet.core.base_agent import FleetAgent
from fleet.core.registry import AgentRegistry
from fleet.config import load_fleet_config


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

