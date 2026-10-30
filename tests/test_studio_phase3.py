"""
End-to-End Verification Suite for Zero-Code Agent Studio Phase 3:
1. 9th Declarative UI Block (`sparkline_chart`) & Natural-Language `event_triggers` Auto-Synthesis.
2. Inter-Agent `EventBus` Trigger & Playbook Wiring (`When Event -> Run Agent`), Live Event Dispatch,
   Cycle-Guard Protection, and Cleanup on Agent Deletion.
3. Proactive Step 1 Local Process Discovery Suggestions (`$0.00`) & 1-Click Scheduled v2.0 Spawn.
4. 1-Click Clone (`Duplicate` without copying private SQLite records) + Portable `.fleetagent` Export & Import.
5. 1-Click `🤖 Deep-Build with Antigravity` Direct Bridge (`POST /api/studio/deep_build`).
"""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.api.settings_api import (
    clone_custom_agent_endpoint,
    create_new_agent_endpoint,
    deep_build_agent_studio_endpoint,
    delete_custom_agent_endpoint,
    emit_studio_event_trigger_endpoint,
    evolve_custom_agent_endpoint,
    export_agent_pack_endpoint,
    get_discovery_recommendations_endpoint,
    get_studio_blueprints_endpoint,
    import_agent_pack_endpoint,
    spawn_discovery_recommendation_endpoint,
)
from fleet.core.agent_studio import (
    SUPPORTED_EVENT_TRIGGERS,
    SUPPORTED_UI_BLOCKS,
    build_antigravity_deep_build_prompt,
    synthesize_agent_from_prompt,
)
from fleet.core.database import FleetDatabase
from fleet.core.event_bus import DeterministicEventBus
import fleet.core.playbook_engine as pb_engine
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
import fleet.server as srv


@pytest.fixture
def studio_p3_env(tmp_path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    db = FleetDatabase(tmp_path / "test_studio_phase3.db")
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

    mock_dispatch_cmd = MagicMock(return_value={"status": "queued", "slot": 1})

    with (
        patch.object(registry, "_get_overrides_file", return_value=overrides_file),
        patch.object(scheduler, "_get_overrides_file", return_value=sched_overrides),
        patch.object(srv, "db", db),
        patch.object(srv, "agent_registry", registry),
        patch.object(srv, "execute_dashboard_command", mock_dispatch_cmd),
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
            "mock_dispatch_cmd": mock_dispatch_cmd,
        }
    pb_engine._TEST_PLAYBOOKS_MEMORY = None


def test_phase3_sparkline_block_and_event_triggers_synthesis():
    assert "sparkline_chart" in SUPPORTED_UI_BLOCKS
    assert len(SUPPORTED_UI_BLOCKS) >= 9
    assert len(SUPPORTED_EVENT_TRIGGERS) == 5
    assert "gmail.paper_trail_detected" in SUPPORTED_EVENT_TRIGGERS

    h_bp = MagicMock()
    get_studio_blueprints_endpoint(h_bp, urllib.parse.urlparse("/api/studio/blueprints"))
    bp_res = h_bp._send_json.call_args[0][0]
    assert bp_res["status"] == "ok"
    assert len(bp_res["supported_ui_blocks"]) >= 9
    assert len(bp_res["supported_event_triggers"]) == 5

    spec = synthesize_agent_from_prompt(
        "Monitor production API HTTP latency trend chart every 30 minutes and trigger whenever a billing email invoice arrives"
    )
    assert spec["status"] == "ok"
    assert "sparkline_chart" in spec["ui_blocks"]
    assert "gmail.paper_trail_detected" in spec["event_triggers"]
    assert f'{spec["agent_id"]}_sparkline_box' in spec["panel_html"]


def test_phase3_event_bus_playbooks_wiring_dispatch_and_cleanup(studio_p3_env):
    registry = studio_p3_env["registry"]
    db = studio_p3_env["db"]

    # 1. Create custom agent subscribed to 2 EventBus triggers
    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "invoice_watcher",
            "name": "Invoice & Paper-Trail Watcher",
            "icon": "📬",
            "category": "Finance",
            "ui_blocks": ["alert_banner", "kpi_row", "sparkline_chart", "history_table"],
            "event_triggers": ["gmail.paper_trail_detected", "overview.morning_briefing"],
        },
    )
    create_res = h_create._send_json.call_args[0][0]
    assert create_res["status"] == "success"
    assert len(create_res["event_playbooks"]) == 2

    all_pbs = pb_engine.list_playbooks()
    auto_pbs = [p for p in all_pbs if str(p.get("id", "")).startswith("auto_evt_invoice_watcher_")]
    assert len(auto_pbs) == 2

    # 2. Emit gmail.paper_trail_detected via POST /api/studio/events/emit -> triggers invoice_watcher
    h_emit = MagicMock()
    emit_studio_event_trigger_endpoint(
        h_emit,
        {"event": "gmail.paper_trail_detected", "payload": {"subject": "Car Insurance Renewal Notice"}},
    )
    emit_res = h_emit._send_json.call_args[0][0]
    assert emit_res["status"] == "ok"
    assert "invoice_watcher" in emit_res["agents_triggered"]

    runs_after_emit = db.list_custom_agent_records("invoice_watcher", record_type="run")
    assert len(runs_after_emit) == 1

    # 3. Publish overview.morning_briefing via DeterministicEventBus.publish -> triggers second run
    bus = DeterministicEventBus()
    bus_res = bus.publish("overview.morning_briefing", payload={"source": "test"}, agent_registry=registry)
    assert "invoice_watcher" in bus_res["agents_triggered"]
    assert len(db.list_custom_agent_records("invoice_watcher", record_type="run")) == 2

    # 4. Evolve agent to subscribe ONLY to 'agent.alert' -> replaces old playbooks & respects self-cycle guard
    h_evo = MagicMock()
    evolve_custom_agent_endpoint(
        h_evo,
        {
            "id": "invoice_watcher",
            "event_triggers": ["agent.alert"],
        },
    )
    evo_res = h_evo._send_json.call_args[0][0]
    assert evo_res["status"] == "success"
    assert len(evo_res["event_playbooks"]) == 1

    # Self-emitted agent.alert must NOT re-trigger invoice_watcher (cycle guard)
    h_self_alert = MagicMock()
    emit_studio_event_trigger_endpoint(
        h_self_alert,
        {"event": "agent.alert", "payload": {"agent_id": "invoice_watcher"}},
    )
    self_alert_res = h_self_alert._send_json.call_args[0][0]
    assert "invoice_watcher" not in self_alert_res["agents_triggered"]

    # Alert from a DIFFERENT agent MUST trigger invoice_watcher
    h_other_alert = MagicMock()
    emit_studio_event_trigger_endpoint(
        h_other_alert,
        {"event": "agent.alert", "payload": {"agent_id": "optimizer"}},
    )
    other_alert_res = h_other_alert._send_json.call_args[0][0]
    assert "invoice_watcher" in other_alert_res["agents_triggered"]

    # 5. Delete custom agent -> removes auto-wired playbooks automatically
    h_del = MagicMock()
    delete_custom_agent_endpoint(h_del, {"id": "invoice_watcher"})
    del_res = h_del._send_json.call_args[0][0]
    assert del_res["status"] == "success"
    assert del_res["removed_playbooks"] == 1
    assert not any(
        str(p.get("id", "")).startswith("auto_evt_invoice_watcher_") for p in pb_engine.list_playbooks()
    )


def test_phase3_discovery_suggestions_and_one_click_spawn(studio_p3_env):
    scheduler = studio_p3_env["scheduler"]
    registry = studio_p3_env["registry"]
    db = studio_p3_env["db"]

    if hasattr(db, "add_task"):
        db.add_task("Renew annual car insurance policy before expiry", priority="high")

    h_disc = MagicMock()
    get_discovery_recommendations_endpoint(
        h_disc,
        urllib.parse.urlparse("/api/discovery/recommendations"),
    )
    disc_res = h_disc._send_json.call_args[0][0]
    assert disc_res["status"] == "ok"
    recs = disc_res["recommendations"]
    assert len(recs) >= 3

    target_rec = next(r for r in recs if not r.get("already_installed"))
    h_spawn = MagicMock()
    spawn_discovery_recommendation_endpoint(h_spawn, {"recommendation_id": target_rec["id"]})
    spawn_res = h_spawn._send_json.call_args[0][0]
    assert spawn_res["status"] == "success"
    spawned_id = spawn_res["agent_id"]
    assert spawned_id in registry.agents
    assert spawn_res["manifest"]["version"] == "2.0.0"
    assert any(s.get("agent") == spawned_id for s in scheduler.schedules)


def test_phase3_clone_export_and_import_fleetagent_pack(studio_p3_env):
    router = studio_p3_env["router"]
    registry = studio_p3_env["registry"]
    scheduler = studio_p3_env["scheduler"]
    db = studio_p3_env["db"]

    # 1. Create source custom agent and add a private SQLite record
    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "fleet_policy_tracker",
            "name": "Fleet Policy Tracker",
            "icon": "🛡️",
            "category": "Finance",
            "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "countdown_cards", "sparkline_chart", "history_table"],
            "fields": [
                {"key": "title", "label": "Policy Name", "type": "text", "placeholder": "e.g. Car Policy"},
                {"key": "due_date", "label": "Expiry Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                {"key": "numeric_value", "label": "Premium", "type": "number", "placeholder": "12000"},
            ],
            "event_triggers": ["gmail.paper_trail_detected"],
        },
    )
    assert h_create._send_json.call_args[0][0]["status"] == "success"

    h_rec = MagicMock()
    due = (date.today() + timedelta(days=10)).isoformat()
    assert router.dispatch_post(
        h_rec,
        "/api/fleet/agents/fleet_policy_tracker/records",
        {"fields": {"title": "Private Car Policy #991", "due_date": due, "numeric_value": 18250}},
    )
    assert len(db.list_custom_agent_records("fleet_policy_tracker", record_type="entry")) == 1

    # 2. Clone agent -> duplicates blueprint, schedule & triggers WITHOUT copying private SQLite records
    h_clone = MagicMock()
    clone_custom_agent_endpoint(h_clone, {"source_id": "fleet_policy_tracker"})
    clone_res = h_clone._send_json.call_args[0][0]
    assert clone_res["status"] == "success"
    cloned_id = clone_res["agent_id"]
    assert cloned_id == "fleet_policy_tracker_copy"
    assert cloned_id in registry.agents
    assert "sparkline_chart" in clone_res["manifest"]["ui_blocks"]
    assert "gmail.paper_trail_detected" in clone_res["manifest"]["event_triggers"]
    assert len(db.list_custom_agent_records(cloned_id, record_type="entry")) == 0
    assert any(s.get("agent") == cloned_id for s in scheduler.schedules)

    # 3. Export source agent as SHA-256 verified .fleetagent bundle
    h_exp = MagicMock()
    export_agent_pack_endpoint(
        h_exp,
        urllib.parse.urlparse("/api/agents/export?id=fleet_policy_tracker"),
    )
    exp_res = h_exp._send_json.call_args[0][0]
    assert exp_res["status"] == "ok"
    pack = exp_res["pack"]
    assert pack["format"] == "fleetagent-v1"
    assert pack["sha256_digest"]

    # 4. Import under a new ID ('imported_policy_pack') -> AST-audited, hot-loaded, scheduled & event-wired
    remapped_pack = {
        "format": "fleetagent-v1",
        "manifest": {**pack["manifest"], "id": "imported_policy_pack", "name": "Imported Policy Pack"},
        "agent_code": pack["agent_code"].replace('"fleet_policy_tracker"', '"imported_policy_pack"'),
        "panel_html": pack["panel_html"].replace("fleet_policy_tracker", "imported_policy_pack"),
    }
    h_imp = MagicMock()
    import_agent_pack_endpoint(h_imp, {"pack": remapped_pack})
    imp_res = h_imp._send_json.call_args[0][0]
    assert imp_res["status"] == "success"
    assert imp_res["agent_id"] == "imported_policy_pack"
    assert "imported_policy_pack" in registry.agents
    assert any(s.get("agent") == "imported_policy_pack" for s in scheduler.schedules)
    assert len(imp_res.get("event_playbooks", [])) == 1


def test_phase3_deep_build_with_antigravity_bridge(studio_p3_env):
    registry = studio_p3_env["registry"]
    scheduler = studio_p3_env["scheduler"]
    mock_dispatch_cmd = studio_p3_env["mock_dispatch_cmd"]

    spec = synthesize_agent_from_prompt(
        "Monitor my local microservice endpoints every 30 minutes with latency sparkline chart"
    )
    spec["id"] = "microservice_deep_guard"
    spec["agent_id"] = "microservice_deep_guard"

    prompt_preview = build_antigravity_deep_build_prompt(spec)
    assert "microservice_deep_guard" in prompt_preview
    assert "security_scanner" in prompt_preview

    h_deep = MagicMock()
    deep_build_agent_studio_endpoint(
        h_deep,
        {
            "spec": spec,
            "scaffold_first": True,
            "model": "gemini-3.8-pro-high",
        },
    )
    deep_res = h_deep._send_json.call_args[0][0]
    assert deep_res["status"] == "success"
    assert deep_res["agent_id"] == "microservice_deep_guard"
    assert "microservice_deep_guard" in registry.agents
    assert any(s.get("agent") == "microservice_deep_guard" for s in scheduler.schedules)

    mock_dispatch_cmd.assert_called_once()
    dispatched_prompt = mock_dispatch_cmd.call_args[0][0]
    dispatched_kwargs = mock_dispatch_cmd.call_args[1]
    assert "microservice_deep_guard" in dispatched_prompt
    assert dispatched_kwargs["model"] == "gemini-3.8-pro-high"

