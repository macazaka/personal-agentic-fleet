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

