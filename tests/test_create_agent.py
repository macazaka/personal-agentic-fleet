"""
Unit tests for the Fleet Agent Scaffolder CLI (fleet.tools.create_agent).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from fleet.tools.create_agent import scaffold_agent, sanitize_agent_id, main


def test_sanitize_agent_id():
    assert sanitize_agent_id("My_New_Agent") == "my_new_agent"
    assert sanitize_agent_id("  test-agent  ") == "test_agent"
    assert sanitize_agent_id("weather123") == "weather123"

    with pytest.raises(ValueError):
        sanitize_agent_id("!!!")


def test_scaffold_agent_success(tmp_path):
    target = scaffold_agent(
        agent_id="test_widget",
        name="Test Widget",
        icon="🧩",
        description="A widget for testing.",
        permissions=["db:read", "ui:render"],
        order=75,
        target_dir=tmp_path
    )

    assert target.exists()
    manifest_file = target / "manifest.json"
    agent_file = target / "agent.py"
    ui_file = target / "ui" / "panel.html"

    assert manifest_file.is_file()
    assert agent_file.is_file()
    assert ui_file.is_file()

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["id"] == "test_widget"
    assert manifest["name"] == "Test Widget"
    assert manifest["icon"] == "🧩"
    assert manifest["order"] == 75
    assert manifest["permissions"] == ["db:read", "ui:render"]

    agent_code = agent_file.read_text(encoding="utf-8")
    assert "class TestWidgetAgent(FleetAgent):" in agent_code
    assert 'return "test_widget"' in agent_code

    ui_code = ui_file.read_text(encoding="utf-8")
    assert 'id="panel_test_widget"' in ui_code


def test_scaffold_agent_invalid_permission(tmp_path):
    with pytest.raises(ValueError, match="Invalid permissions"):
        scaffold_agent(
            agent_id="bad_agent",
            permissions=["db:read", "root:destroy_universe"],
            target_dir=tmp_path
        )


def test_scaffold_agent_already_exists(tmp_path):
    scaffold_agent(agent_id="dup_agent", target_dir=tmp_path)
    with pytest.raises(FileExistsError):
        scaffold_agent(agent_id="dup_agent", target_dir=tmp_path)


def test_scaffold_cli_main(tmp_path):
    test_args = [
        "create_agent",
        "--id", "cli_demo",
        "--name", "CLI Demo",
        "--icon", "🚀",
        "--permissions", "db:read,ui:render",
        "--target-dir", str(tmp_path)
    ]
    with patch("sys.argv", test_args):
        ret = main()
        assert ret == 0

    assert (tmp_path / "cli_demo" / "manifest.json").exists()


def test_delete_custom_agent_and_protect_builtin(tmp_path):
    from fleet.core.registry import AgentRegistry

    builtin_dir = tmp_path / "agents"
    custom_dir = tmp_path / "custom_agents"
    builtin_dir.mkdir()
    custom_dir.mkdir()

    scaffold_agent(agent_id="core_builtin", name="Core Builtin", target_dir=builtin_dir)
    reg = AgentRegistry(agents_dir=builtin_dir, custom_agents_dir=custom_dir)
    reg.discover_and_load()

    manifest = reg.create_custom_agent(agent_id="temp_custom", name="Temp Custom", icon="🧪")
    assert manifest["is_custom"] is True
    assert "temp_custom" in reg.agents
    assert (custom_dir / "temp_custom").is_dir()

    # Built-in agent is protected from permanent disk deletion
    with pytest.raises(ValueError, match="built-in core agent"):
        reg.delete_custom_agent("core_builtin")

    # Custom agent is permanently deleted and unregistered
    del_res = reg.delete_custom_agent("temp_custom")
    assert del_res["deleted"] is True
    assert "temp_custom" not in reg.agents
    assert not (custom_dir / "temp_custom").exists()

    with pytest.raises(KeyError):
        reg.delete_custom_agent("temp_custom")


def test_agent_studio_llm_dict_response_and_afcc_rag():
    from fleet.core.agent_studio import synthesize_agent_from_prompt
    from fleet.core.token_optimizer import query_local_knowledge_base

    fake_llm_json = json.dumps({
        "name": "Latency Watcher",
        "agent_id": "latency_watcher",
        "icon": "📡",
        "category": "Monitoring",
        "preset": "observer",
        "schedule_cadence": "every_30_min",
        "sync_interval": 45,
        "enable_alerts": True,
        "routine_task": "probe_latency",
        "system_prompt": "Monitor database latency continuously.",
        "ui_blocks": ["alert_banner", "kpi_row"],
    })
    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete", return_value={"status": "SUCCESS", "text": fake_llm_json}):
        spec = synthesize_agent_from_prompt("Monitor postgres latency every 30 min")
        assert spec["name"] == "Latency Watcher"
        assert spec["agent_id"] == "latency_watcher"
        assert spec["category"] == "Monitoring"
        assert spec["sync_interval"] == 45

    hit_del = query_local_knowledge_base("How can I delete an agent from AFCC?")
    assert hit_del is not None
    assert hit_del["doc_id"] == "afcc_delete_agent"

    hit_route = query_local_knowledge_base(
        "How does the Fleet Autonomous Intelligence decide which prompts to send to LLM or which ones to send to deterministic engine?"
    )
    assert hit_route is not None
    assert hit_route["doc_id"] == "afcc_llm_vs_deterministic_routing"

    # Normal coding prompt without required_any words must not false-match
    assert query_local_knowledge_base("Write a python script for my custom agent") is None


