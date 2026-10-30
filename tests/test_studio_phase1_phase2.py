"""
End-to-End Verification Suite for Zero-Code Agent Studio Phase 1 & Phase 2:
- Phase 1: SQLite custom_agent_records & custom_agent_checklists, Typed Domain Fields,
  Countdown Urgency, Functional Runtime Archetypes, Hybrid Antigravity AI Briefing,
  and Automatic FleetScheduler Registration / Cleanup.
- Phase 2: Starter Blueprints, Clarifying Chips, Sandbox Dry-Run & AST Gate,
  and In-Place Custom Agent Studio Evolution (preserving SQLite data).
"""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.api.settings_api import (
    create_new_agent_endpoint,
    delete_custom_agent_endpoint,
    dry_run_agent_studio_endpoint,
    evolve_custom_agent_endpoint,
    get_studio_blueprints_endpoint,
    synthesize_agent_studio_endpoint,
)
from fleet.core.agent_studio import (
    SUPPORTED_UI_BLOCKS,
    dry_run_agent_spec,
    get_starter_blueprints,
    synthesize_agent_from_prompt,
)
from fleet.core.database import FleetDatabase
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
import fleet.server as srv


@pytest.fixture
def studio_env(tmp_path):
    db = FleetDatabase(tmp_path / "test_studio_p1_p2.db")
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir(parents=True, exist_ok=True)
    overrides_file = tmp_path / "agent_overrides.json"
    sched_yaml = tmp_path / "schedules.yaml"
    sched_yaml.write_text("schedules: []\n", encoding="utf-8")
    sched_overrides = tmp_path / "schedule_overrides.json"

    registry = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=custom_dir,
        db=db,
    )
    with patch.object(registry, "_get_overrides_file", return_value=overrides_file):
        registry.discover_and_load()

    scheduler = FleetScheduler(config_dir=tmp_path, db=db, registry=registry)

    router = ApiRouter()
    registry.register_all_routes(router)

    with (
        patch.object(registry, "_get_overrides_file", return_value=overrides_file),
        patch.object(scheduler, "_get_overrides_file", return_value=sched_overrides),
        patch.object(srv, "db", db),
        patch.object(srv, "agent_registry", registry),
        patch("fleet.core.scheduler.get_fleet_scheduler", return_value=scheduler),
        patch("fleet.tools.system_tools.send_notification"),
    ):
        scheduler.reload()
        yield {
            "db": db,
            "registry": registry,
            "scheduler": scheduler,
            "router": router,
            "custom_dir": custom_dir,
            "tmp_path": tmp_path,
        }


def test_phase2_starter_blueprints_and_enriched_synthesis():
    bps = get_starter_blueprints()
    assert len(bps) == 6
    assert "countdown_cards" in SUPPORTED_UI_BLOCKS
    assert "ai_insight_card" in SUPPORTED_UI_BLOCKS

    h_bp = MagicMock()
    get_studio_blueprints_endpoint(h_bp, urllib.parse.urlparse("/api/studio/blueprints"))
    bp_payload = h_bp._send_json.call_args[0][0]
    assert bp_payload["status"] == "ok"
    assert bp_payload["total"] == 6

    spec = synthesize_agent_from_prompt(
        "Track my car and bike insurance policy renewals every morning at 08:30 with 15-day expiry alerts"
    )
    assert spec["status"] == "ok"
    assert spec["archetype"] == "tracker"
    assert spec["intelligence_mode"] == "hybrid"
    assert "countdown_cards" in spec["ui_blocks"]
    assert "ai_insight_card" in spec["ui_blocks"]
    field_keys = {f["key"] for f in spec["fields"]}
    assert "due_date" in field_keys
    assert "numeric_value" in field_keys
    assert isinstance(spec["clarifying_chips"], list)


def test_phase2_dry_run_validates_ast_and_permissions():
    spec = synthesize_agent_from_prompt("Audit local disk free space every 2 hours")
    ok_res = dry_run_agent_spec(spec)
    assert ok_res["status"] == "ok"
    assert ok_res["ast_valid"] is True
    assert ok_res["permissions_valid"] is True

    # Rejects unsafe eval() in agent_py
    bad_spec = dict(spec, agent_py="x = eval('2+2')\n")
    h_bad = MagicMock()
    dry_run_agent_studio_endpoint(h_bad, {"spec": bad_spec})
    bad_payload = h_bad._send_json.call_args[0][0]
    assert bad_payload["status"] == "error"
    assert bad_payload["ast_valid"] is False

    # Rejects forbidden permission outside sandbox allowlist
    bad_perm = dict(spec, permissions=["ui:render", "root:kernel"])
    perm_res = dry_run_agent_spec(bad_perm)
    assert perm_res["status"] == "error"
    assert perm_res["permissions_valid"] is False


def test_phase1_and_phase2_full_custom_agent_lifecycle(studio_env):
    router = studio_env["router"]
    scheduler = studio_env["scheduler"]
    registry = studio_env["registry"]
    db = studio_env["db"]

    # 1. Create custom agent via 1-step Studio prompt with run_immediately=True
    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "policy_guard",
            "nl_prompt": "Track my car and health insurance renewals every morning at 08:30",
            "run_immediately": True,
        },
    )
    create_res = h_create._send_json.call_args[0][0]
    assert create_res["status"] == "success"
    assert create_res["agent_id"] == "policy_guard"
    assert create_res["initial_run"]["status"] == "success"

    # Verify live FleetScheduler rule registered & persists across reload
    assert any(s.get("agent") == "policy_guard" for s in scheduler.schedules)
    scheduler.reload()
    assert any(s.get("agent") == "policy_guard" for s in scheduler.schedules)

    # 2. Add two typed domain entries via POST /api/fleet/agents/policy_guard/records
    soon_date = (date.today() + timedelta(days=6)).isoformat()
    later_date = (date.today() + timedelta(days=90)).isoformat()

    h_rec1 = MagicMock()
    assert router.dispatch_post(
        h_rec1,
        "/api/fleet/agents/policy_guard/records",
        {
            "fields": {
                "title": "Car Comprehensive Policy",
                "provider": "ICICI Lombard",
                "due_date": soon_date,
                "numeric_value": 14500,
            }
        },
    )
    rec1_res = h_rec1._send_json.call_args[0][0]
    assert rec1_res["status"] == "success"
    rec1_id = rec1_res["record_id"]

    # Also test custom LLM-synthesized domain keys (vehicle_name, expiry_date, premium_amount)
    h_rec2 = MagicMock()
    router.dispatch_post(
        h_rec2,
        "/api/fleet/agents/policy_guard/records",
        {
            "fields": {
                "vehicle_name": "Health Floater Policy",
                "provider": "HDFC Ergo",
                "expiry_date": later_date,
                "premium_amount": 28000,
            }
        },
    )

    # 3. Verify GET /api/fleet/agents/policy_guard/state KPIs & countdown urgency
    h_state = MagicMock()
    parsed = urllib.parse.urlparse("/api/fleet/agents/policy_guard/state")
    assert router.dispatch_get(h_state, parsed.path, parsed)
    state_payload = h_state._send_json.call_args[0][0]["state"]
    assert state_payload["kpis"]["total_entries"] == 2
    assert state_payload["kpis"]["due_soon"] == 1
    assert state_payload["kpis"]["numeric_sum"] == 42500.0
    assert state_payload["countdowns"][0]["urgency"] == "due_soon"

    # 4. Toggle checklist item & verify persistence + streak
    first_check_key = state_payload["checklist"][0]["item_key"]
    h_chk = MagicMock()
    assert router.dispatch_post(
        h_chk,
        "/api/fleet/agents/policy_guard/checklist",
        {"item_key": first_check_key, "checked": True},
    )
    chk_state = h_chk._send_json.call_args[0][0]["state"]
    assert chk_state["checklist_done"] == 1
    assert chk_state["checklist_streak"] >= 1

    # 5. Execute routine task -> detects 15-day renewal warning deterministically ($0.00)
    h_run = MagicMock()
    assert router.dispatch_post(
        h_run,
        "/api/fleet/agents/policy_guard/run",
        {"task": "check_upcoming_renewals"},
    )
    run_res = h_run._send_json.call_args[0][0]
    assert run_res["status"] == "success"
    assert run_res["result"]["health_status"] == "warning"
    assert "Car Comprehensive Policy" in run_res["result"]["message"]

    # 6. Execute on-demand Antigravity AI Briefing (task='ai_analyze')
    with patch(
        "fleet.core.hyperscalers.HyperscalerGateway.complete",
        return_value={"status": "SUCCESS", "text": "**Priority 1**: Renew Car Comprehensive Policy within 6 days."},
    ):
        h_ai = MagicMock()
        assert router.dispatch_post(
            h_ai,
            "/api/fleet/agents/policy_guard/run",
            {"task": "ai_analyze"},
        )
        ai_res = h_ai._send_json.call_args[0][0]
        assert ai_res["result"]["used_llm"] is True
        assert "Priority 1" in ai_res["state"]["latest_insight"]["data"]["summary"]

    # 7. Evolve custom agent in-place -> updates name, schedule, and blocks while preserving SQLite records!
    h_evo = MagicMock()
    evolve_custom_agent_endpoint(
        h_evo,
        {
            "id": "policy_guard",
            "name": "Vehicle & Health Renewal Command",
            "icon": "🛡️",
            "schedule_cadence": "hourly",
            "ui_blocks": [
                "alert_banner", "kpi_row", "quick_capture_bar",
                "countdown_cards", "ai_insight_card", "habit_checklist", "history_table",
            ],
        },
    )
    evo_res = h_evo._send_json.call_args[0][0]
    assert evo_res["status"] == "success"
    assert evo_res["manifest"]["name"] == "Vehicle & Health Renewal Command"

    # Existing SQLite entries & AI insights are 100% preserved after evolution!
    post_evo_state = db.get_custom_agent_dashboard_state("policy_guard", manifest=evo_res["manifest"])
    assert post_evo_state["kpis"]["total_entries"] == 2
    assert post_evo_state["latest_insight"] is not None

    # Built-in core agents cannot be overwritten via evolve_custom_agent
    with pytest.raises(ValueError, match="built-in core agent"):
        registry.evolve_custom_agent("overview", {"name": "Blocked"})

    # 8. Delete 1 entry row
    h_del_row = MagicMock()
    assert router.dispatch_post(
        h_del_row,
        "/api/fleet/agents/policy_guard/records/delete",
        {"record_id": rec1_id},
    )
    assert h_del_row._send_json.call_args[0][0]["state"]["kpis"]["total_entries"] == 1

    # 9. Permanently delete custom agent -> removes directory, FleetScheduler rule, and SQLite records
    h_del_agent = MagicMock()
    delete_custom_agent_endpoint(h_del_agent, {"id": "policy_guard"})
    del_payload = h_del_agent._send_json.call_args[0][0]
    assert del_payload["status"] == "success"
    assert del_payload["removed_schedules"] >= 1
    assert not any(s.get("agent") == "policy_guard" for s in scheduler.schedules)
    assert db.list_custom_agent_records("policy_guard") == []
