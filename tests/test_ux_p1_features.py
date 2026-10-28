"""
Comprehensive Unit & API Verification Suite for P1 UX Roadmap Features (UX-01 to UX-05):
- UX-01: Natural-Language 'Zero-Code' Agent Studio & Declarative UI Widget Blocks
- UX-02: Autonomous Process Discovery & Agent Recommendation Engine
- UX-03: Multi-Agent Playbook & Event-Chain Composer
- UX-04: Portable .fleetagent Share Pack Export & AST-Audited Import
- UX-05: Unified 'Ask Fleet Anything' Omnibar & Cross-Agent Dispatcher
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.core.agent_studio import (
    synthesize_agent_from_prompt,
    render_declarative_ui_blocks,
    SUPPORTED_UI_BLOCKS,
)
from fleet.core.process_miner import (
    compute_opportunity_score,
    mine_workstation_recommendations,
    spawn_recommended_agent,
)
from fleet.core.playbook_engine import (
    list_playbooks,
    add_or_update_playbook,
    execute_playbook,
)
from fleet.core.agent_catalog import (
    export_agent_pack,
    import_agent_pack,
)
from fleet.core.omnibar_dispatcher import (
    get_all_omnibar_commands,
    dispatch_omnibar_query,
)
from fleet.core.registry import AgentRegistry
from fleet.core.database import FleetDatabase
import fleet.server as srv


@pytest.fixture
def mock_fleet_env(tmp_path):
    db_file = tmp_path / "test_fleet_p1.db"
    db = FleetDatabase(db_file)

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
        yield {"db": db, "registry": registry, "tmp_path": tmp_path, "custom_dir": custom_dir}


# =====================================================================
# UX-01: Natural-Language Zero-Code Agent Studio & Declarative UI Blocks
# =====================================================================

def test_ux01_synthesize_agent_from_prompt_git_watcher():
    prompt = "Check my local git repos every evening at 6 PM and alert me if uncommitted changes exist"
    spec = synthesize_agent_from_prompt(prompt)

    assert spec["status"] == "ok"
    assert spec["category"] in ("DevOps", "Monitoring")
    assert "system:diagnostics" in spec["permissions"]
    assert "event_bus:publish" in spec["permissions"]
    assert "alert_banner" in spec["ui_blocks"]
    assert "kpi_row" in spec["ui_blocks"]
    assert "<div" in spec["panel_html"]


def test_ux01_synthesize_agent_from_prompt_finance_and_health():
    fin_spec = synthesize_agent_from_prompt("Track my recurring SaaS subscription renewals and invoice costs every 30 min")
    assert fin_spec["category"] == "Finance"
    assert fin_spec["icon"] == "💳"

    health_spec = synthesize_agent_from_prompt("Remind me to do a posture stretch and hydration check every hour")
    assert health_spec["category"] in ("Health", "Productivity", "Automation")
    assert "habit_checklist" in health_spec["ui_blocks"]


def test_ux01_render_declarative_ui_blocks():
    assert len(SUPPORTED_UI_BLOCKS) == 6
    html = render_declarative_ui_blocks(
        agent_id="demo_studio_bot",
        name="Demo Studio Bot",
        icon="✨",
        description="Automated test studio agent",
        permissions=["db:read", "ui:render"],
        ui_blocks=["alert_banner", "kpi_row", "quick_capture_bar", "habit_checklist", "history_table", "status_timeline"],
        routine_task="sync_demo",
        schedule_display="Every 60m",
    )
    assert "demo_studio_bot_alert_banner" in html
    assert "demo_studio_bot_kpi_status" in html
    assert "demo_studio_bot_quick_input" in html
    assert "Daily Action Checklist" in html
    assert "Recent Execution &amp; Activity Log" in html
    assert "Autonomic Event Timeline" in html


# =====================================================================
# UX-02: Autonomous Process Discovery & Agent Recommendation Engine
# =====================================================================

def test_ux02_compute_opportunity_score():
    score = compute_opportunity_score(
        frequency_score=96.0,
        temporal_regularity=92.0,
        time_saved_score=90.0,
        deterministic_feasibility=98.0,
    )
    assert score >= 90.0

    low_score = compute_opportunity_score(
        frequency_score=10.0,
        temporal_regularity=15.0,
        time_saved_score=20.0,
        deterministic_feasibility=30.0,
    )
    assert low_score < 25.0


def test_ux02_mine_workstation_recommendations(mock_fleet_env):
    report = mine_workstation_recommendations(db=mock_fleet_env["db"])
    assert report["status"] == "ok"
    assert report["signals_analyzed"]["token_cost_usd"] == 0.0
    assert report["total_recommendations"] >= 4
    top = report["recommendations"][0]
    assert top["opportunity_score"] >= 80.0


def test_ux02_spawn_recommended_agent(mock_fleet_env):
    registry = mock_fleet_env["registry"]
    db = mock_fleet_env["db"]
    result = spawn_recommended_agent("rec_git_eod_sentinel", agent_registry=registry, db=db)
    assert result["status"] == "success"
    assert result["agent_id"] == "git_eod_sentinel"
    assert (mock_fleet_env["custom_dir"] / "git_eod_sentinel" / "agent.py").exists()


# =====================================================================
# UX-03: Visual Multi-Agent Playbook & Event-Chain Composer
# =====================================================================

def test_ux03_list_and_execute_playbooks(mock_fleet_env):
    pbs = list_playbooks()
    assert len(pbs) >= 8
    ids = {p["id"] for p in pbs}
    assert "morning_vitality_launchpad" in ids
    assert "evening_shutdown_and_dream" in ids

    exec_res = execute_playbook(
        "morning_vitality_launchpad",
        agent_registry=mock_fleet_env["registry"],
        db=mock_fleet_env["db"],
    )
    assert exec_res["status"] == "success"
    assert exec_res["steps_executed"] >= 2
    assert len(exec_res["results"]) >= 2


def test_ux03_add_custom_playbook(mock_fleet_env):
    pb = add_or_update_playbook({
        "name": "Custom Dev Pipeline",
        "trigger": {"type": "manual", "value": "on_demand"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "overview", "task": "morning_briefing", "label": "Refresh Briefing"},
            {"agent_id": "optimizer", "task": "periodic_ram_audit", "label": "Audit RAM"},
        ],
    })
    assert pb["id"] == "custom_dev_pipeline"

    run_res = execute_playbook(pb["id"], agent_registry=mock_fleet_env["registry"])
    assert run_res["status"] == "success"
    assert run_res["steps_executed"] == 2


# =====================================================================
# UX-04: Portable .fleetagent Share Packs & AST Security Verification
# =====================================================================

def test_ux04_export_and_import_agent_pack(mock_fleet_env):
    registry = mock_fleet_env["registry"]
    custom_dir = mock_fleet_env["custom_dir"]

    pack = export_agent_pack("crypto_trader", agent_registry=registry)
    assert pack["format"] == "fleetagent-v1"
    assert len(pack["sha256_digest"]) == 64

    import_res = import_agent_pack(pack, custom_agents_dir=custom_dir, agent_registry=registry)
    assert import_res["status"] == "success"
    assert import_res["agent_id"] == "crypto_trader"
    assert (custom_dir / "crypto_trader" / "agent.py").exists()


def test_ux04_import_agent_pack_blocks_unsafe_ast(mock_fleet_env):
    bad_pack = {
        "format": "fleetagent-v1",
        "agent_id": "malicious_agent",
        "manifest": {
            "id": "malicious_agent",
            "name": "Malicious Agent",
            "permissions": ["ui:render"],
        },
        "agent_code": "import os\nos.system('calc.exe')\n",
        "panel_html": "<div>Hello</div>",
    }
    with pytest.raises(ValueError, match="Security violation"):
        import_agent_pack(bad_pack, custom_agents_dir=mock_fleet_env["custom_dir"])


# =====================================================================
# UX-05: Unified 'Ask Fleet Anything' Omnibar & Cross-Agent Dispatcher
# =====================================================================

def test_ux05_omnibar_commands_and_dispatch(mock_fleet_env):
    registry = mock_fleet_env["registry"]
    db = mock_fleet_env["db"]

    cmds = get_all_omnibar_commands(agent_registry=registry)
    assert len(cmds) >= 10
    triggers = {c["trigger"] for c in cmds}
    assert "@discover" in triggers
    assert "@studio" in triggers

    disc = dispatch_omnibar_query("@discover", agent_registry=registry, db=db)
    assert disc["status"] == "ok"
    assert disc["mode"] == "discovery"
    assert len(disc["recommendations"]) >= 1

    pb = dispatch_omnibar_query("@playbook morning_vitality_launchpad", agent_registry=registry, db=db)
    assert pb["status"] == "ok"
    assert pb["mode"] == "playbook"

    studio = dispatch_omnibar_query("@studio Monitor disk usage every hour and notify me", agent_registry=registry, db=db)
    assert studio["status"] == "ok"
    assert studio["mode"] == "studio_synthesis"
    assert "spec" in studio

    hyd = dispatch_omnibar_query("@health water +2", agent_registry=registry, db=db)
    assert hyd["status"] == "ok"
    assert hyd["mode"] == "hydration"


def test_ux_p1_api_handlers(mock_fleet_env):
    from fleet.api.settings_api import (
        synthesize_agent_studio_endpoint,
        get_discovery_recommendations_endpoint,
        spawn_discovery_recommendation_endpoint,
        get_playbooks_endpoint,
        run_playbook_endpoint,
        export_agent_pack_endpoint,
        get_omnibar_commands_endpoint,
        execute_omnibar_query_endpoint,
    )

    # UX-01: POST /api/studio/synthesize
    h1 = MagicMock()
    synthesize_agent_studio_endpoint(h1, {"prompt": "Monitor git repos every evening and alert me"})
    res1 = h1._send_json.call_args[0][0]
    assert res1["status"] == "ok"
    assert "ui_blocks" in res1

    # UX-02: GET /api/discovery/recommendations & POST /api/discovery/spawn
    h2 = MagicMock()
    get_discovery_recommendations_endpoint(h2, urllib.parse.urlparse("/api/discovery/recommendations"))
    res2 = h2._send_json.call_args[0][0]
    assert res2["status"] == "ok"
    assert res2["total_recommendations"] >= 4

    h2_spawn = MagicMock()
    spawn_discovery_recommendation_endpoint(h2_spawn, {"recommendation_id": "rec_pre_meeting_ram_guard"})
    assert h2_spawn._send_json.call_args[0][0]["status"] == "success"

    # UX-03: GET /api/playbooks & POST /api/playbooks/run
    h3 = MagicMock()
    get_playbooks_endpoint(h3, urllib.parse.urlparse("/api/playbooks"))
    assert h3._send_json.call_args[0][0]["total"] >= 8

    h3_run = MagicMock()
    run_playbook_endpoint(h3_run, {"playbook_id": "pb_morning_vitality"})
    assert h3_run._send_json.call_args[0][0]["status"] == "success"

    # UX-04: GET /api/agents/export
    h4 = MagicMock()
    export_agent_pack_endpoint(h4, urllib.parse.urlparse("/api/agents/export?id=crypto_trader"))
    assert h4._send_json.call_args[0][0]["pack"]["format"] == "fleetagent-v1"

    # UX-05: GET /api/omnibar/commands & POST /api/omnibar/execute
    h5 = MagicMock()
    get_omnibar_commands_endpoint(h5, urllib.parse.urlparse("/api/omnibar/commands"))
    assert h5._send_json.call_args[0][0]["total"] >= 10

    h5_exec = MagicMock()
    execute_omnibar_query_endpoint(h5_exec, {"query": "@discover"})
    assert h5_exec._send_json.call_args[0][0]["mode"] == "discovery"
