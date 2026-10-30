"""
End-to-End Verification Suite for Zero-Code Agent Studio Phase 4:
1. `Ctrl+K` Omnibar Auto-Commands (`@<id>`, `@<id> open`, `@<id> add`, `@<id> ai`) & 1-Click `@studio launch <prompt>`.
2. Studio v2.0 MCP Tools (`fleet_create_custom_agent(nl_prompt=...)`, `fleet_get_custom_agent_state`, `fleet_manage_custom_agent_record`).
3. 10th UI Block (`kanban_board`), Inline Record Update & Complete (`POST .../records/update`), Live Search & CSV Export (`GET .../export.csv`).
4. Overview & Morning Briefing Custom-Agent Rollup (`BriefingEngine`, `get_custom_agents_fleet_rollup`, Omnibar `"daily briefing"`).
5. Blueprint Revision History & 1-Click Rollback (`GET /api/settings/agents/revisions` & `POST /api/settings/agents/rollback`) preserving SQLite records.
"""

from datetime import date, timedelta
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter
from fleet.api.settings_api import (
    create_new_agent_endpoint,
    evolve_custom_agent_endpoint,
    get_studio_blueprints_endpoint,
    list_custom_agent_revisions_endpoint,
    rollback_custom_agent_endpoint,
)
from fleet.core.agent_studio import (
    SUPPORTED_UI_BLOCKS,
    synthesize_agent_from_prompt,
)
from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.core.omnibar_dispatcher import (
    clear_omnibar_chat_history,
    dispatch_omnibar_query,
    get_all_omnibar_commands,
)
import fleet.core.playbook_engine as pb_engine
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
from fleet.mcp_server import (
    fleet_create_custom_agent,
    fleet_get_custom_agent_state,
    fleet_manage_custom_agent_record,
)
import fleet.server as srv


@pytest.fixture
def studio_p4_env(tmp_path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    clear_omnibar_chat_history()
    db = FleetDatabase(tmp_path / "test_studio_phase4.db")
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
        }
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    clear_omnibar_chat_history()


def test_phase4_omnibar_auto_commands_and_1click_studio_launch(studio_p4_env):
    registry = studio_p4_env["registry"]
    db = studio_p4_env["db"]
    scheduler = studio_p4_env["scheduler"]

    # 1. `@studio launch <prompt>` creates & schedules the custom agent in 1 step
    res_launch = dispatch_omnibar_query(
        "@studio launch Track domain SSL renewals every morning and alert 14 days before expiry",
        agent_registry=registry,
        db=db,
    )
    assert res_launch["status"] == "ok"
    assert res_launch["mode"] == "studio_created"
    created_id = res_launch["agent_id"]
    assert created_id in registry.agents

    agent = registry.get_agent(created_id)
    assert agent is not None
    assert agent.is_custom is True
    assert any(s.get("agent") == created_id for s in scheduler.schedules)

    # 2. Custom Studio agent automatically exposes `@<id>`, `@<id> open`, `@<id> add`, `@<id> ai`
    all_cmds = get_all_omnibar_commands(registry)
    triggers = {c["trigger"] for c in all_cmds if c.get("agent_id") == created_id}
    assert f"@{created_id}" in triggers
    assert f"@{created_id} open" in triggers
    assert f"@{created_id} add" in triggers
    assert f"@{created_id} ai" in triggers

    # 3. `@<id> add <Title> <YYYY-MM-DD> <Amount>` inserts directly into SQLite at $0.00
    soon_due = (date.today() + timedelta(days=6)).isoformat()
    res_add = dispatch_omnibar_query(
        f"@{created_id} add Cloudflare Enterprise SSL {soon_due} 1450",
        agent_registry=registry,
        db=db,
    )
    assert res_add["status"] == "ok"
    assert res_add["mode"] == "agent_record_added"
    assert res_add["tokens_used"] == 0

    state = db.get_custom_agent_dashboard_state(created_id, manifest=agent.get_ui_manifest())
    assert state["kpis"]["total_entries"] == 1
    assert state["kpis"]["due_soon"] == 1
    assert state["entries"][0]["title"] == "Cloudflare Enterprise SSL"
    assert state["entries"][0]["numeric_value"] == 1450.0

    # 4. `@<id> run` & `@<id> ai` execute via Omnibar
    res_run = dispatch_omnibar_query(f"@{created_id} run", agent_registry=registry, db=db)
    assert res_run["status"] == "ok"
    assert res_run["mode"] == "agent_task"

    res_ai = dispatch_omnibar_query(f"@{created_id} ai", agent_registry=registry, db=db)
    assert res_ai["status"] == "ok"
    assert res_ai["mode"] == "agent_task"


def test_phase4_mcp_studio_v2_create_state_and_record_crud(studio_p4_env):
    registry = studio_p4_env["registry"]
    scheduler = studio_p4_env["scheduler"]

    # 1. Create custom Studio v2.0 agent directly via MCP `nl_prompt`
    raw_create = fleet_create_custom_agent(
        agent_id="mcp_vendor_kanban",
        nl_prompt="Track SaaS vendor contracts on a kanban board every weekday morning and trigger on billing email",
    )
    created = json.loads(raw_create)
    assert created["status"] == "success"
    manifest = created["agent"]
    assert manifest["id"] == "mcp_vendor_kanban"
    assert "kanban_board" in manifest["ui_blocks"]
    assert "mcp_vendor_kanban" in registry.agents
    assert any(s.get("agent") == "mcp_vendor_kanban" for s in scheduler.schedules)

    # 2. Add record via `fleet_manage_custom_agent_record`
    due_soon = (date.today() + timedelta(days=4)).isoformat()
    add_res = json.loads(
        fleet_manage_custom_agent_record(
            agent_id="mcp_vendor_kanban",
            action="add",
            title="Datadog APM Renewal",
            due_date=due_soon,
            numeric_value=3200.0,
            extra_json='{"owner": "PlatformOps"}',
        )
    )
    assert add_res["status"] == "success"
    rec_id = add_res["record_id"]
    assert add_res["kpis"]["total_entries"] == 1
    assert add_res["kpis"]["due_soon"] == 1

    # 3. Query state via `fleet_get_custom_agent_state`
    st_res = json.loads(fleet_get_custom_agent_state("mcp_vendor_kanban"))
    assert st_res["status"] == "ok"
    assert st_res["state"]["kpis"]["numeric_sum"] == 3200.0

    # 4. Update record & then mark completed via MCP
    upd_res = json.loads(
        fleet_manage_custom_agent_record(
            agent_id="mcp_vendor_kanban",
            action="update",
            record_id=rec_id,
            title="Datadog APM Negotiated Renewal",
            numeric_value=2800.0,
        )
    )
    assert upd_res["status"] == "success"
    assert upd_res["kpis"]["numeric_sum"] == 2800.0

    cmp_res = json.loads(
        fleet_manage_custom_agent_record(
            agent_id="mcp_vendor_kanban",
            action="complete",
            record_id=rec_id,
        )
    )
    assert cmp_res["status"] == "success"
    assert cmp_res["kpis"]["due_soon"] == 0
    assert cmp_res["kpis"]["completed_entries"] == 1

    # 5. Delete record via MCP
    del_res = json.loads(
        fleet_manage_custom_agent_record(
            agent_id="mcp_vendor_kanban",
            action="delete",
            record_id=rec_id,
        )
    )
    assert del_res["status"] == "success"
    assert del_res["deleted"] is True
    assert del_res["kpis"]["total_entries"] == 0


def test_phase4_kanban_block_inline_record_update_and_csv_export(studio_p4_env):
    router = studio_p4_env["router"]

    assert "kanban_board" in SUPPORTED_UI_BLOCKS
    assert len(SUPPORTED_UI_BLOCKS) >= 10

    h_bp = MagicMock()
    get_studio_blueprints_endpoint(h_bp, urllib.parse.urlparse("/api/studio/blueprints"))
    bp_payload = h_bp._send_json.call_args[0][0]
    assert len(bp_payload["supported_ui_blocks"]) >= 10
    assert any(b["id"] == "kanban_board" for b in bp_payload["supported_ui_blocks"])

    spec = synthesize_agent_from_prompt(
        "Manage client onboarding pipeline stages on a kanban board with due dates and contract value"
    )
    assert "kanban_board" in spec["ui_blocks"]
    assert f'{spec["agent_id"]}_kanban_box' in spec["panel_html"]
    assert f'{spec["agent_id"]}_history_search' in spec["panel_html"]
    assert f'/api/fleet/agents/{spec["agent_id"]}/export.csv' in spec["panel_html"]

    # Create agent via Studio endpoint
    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "onboarding_kanban",
            "name": "Onboarding Kanban",
            "icon": "🗂️",
            "description": spec["description"],
            "ui_blocks": [
                "kpi_row",
                "quick_add_form",
                "kanban_board",
                "countdown_cards",
                "history_table",
            ],
            "fields": spec["fields"],
        },
    )
    assert h_create._send_json.call_args[0][0]["status"] == "success"

    # Insert 2 records (one with leading '=' to verify CSV formula-injection defense)
    due_soon = (date.today() + timedelta(days=5)).isoformat()
    h_rec1 = MagicMock()
    router.dispatch_post(
        h_rec1,
        "/api/fleet/agents/onboarding_kanban/records",
        {"title": "Acme Corp Kickoff", "due_date": due_soon, "numeric_value": 5000},
    )
    r1_payload = h_rec1._send_json.call_args[0][0]
    assert r1_payload["status"] == "success"
    rec1_id = r1_payload["record_id"]
    assert r1_payload["state"]["kpis"]["due_soon"] == 1

    h_rec2 = MagicMock()
    router.dispatch_post(
        h_rec2,
        "/api/fleet/agents/onboarding_kanban/records",
        {"title": "=HYPERLINK(\"http://evil.invalid\")", "due_date": due_soon, "numeric_value": 100},
    )
    assert h_rec2._send_json.call_args[0][0]["status"] == "success"

    # Inline edit + mark record 1 completed via POST /api/fleet/agents/<id>/records/update
    h_upd = MagicMock()
    router.dispatch_post(
        h_upd,
        "/api/fleet/agents/onboarding_kanban/records/update",
        {
            "record_id": rec1_id,
            "title": "Acme Corp Signed & Live",
            "numeric_value": 7500,
            "status": "completed",
        },
    )
    upd_payload = h_upd._send_json.call_args[0][0]
    assert upd_payload["status"] == "success"
    assert upd_payload["updated"] is True
    # Completed record no longer triggers due_soon alert; only record 2 remains due_soon
    assert upd_payload["state"]["kpis"]["due_soon"] == 1
    assert upd_payload["state"]["kpis"]["completed_entries"] == 1

    # Export CSV via GET /api/fleet/agents/<id>/export.csv
    h_csv = MagicMock()
    h_csv.wfile = io.BytesIO()
    csv_path = "/api/fleet/agents/onboarding_kanban/export.csv"
    dispatched = router.dispatch_get(
        h_csv,
        csv_path,
        urllib.parse.urlparse(csv_path),
    )
    assert dispatched is True
    h_csv.send_response.assert_called_with(200)
    sent_headers = {call.args[0]: call.args[1] for call in h_csv.send_header.call_args_list}
    assert sent_headers["Content-Type"] == "text/csv; charset=utf-8"
    assert sent_headers["X-Content-Type-Options"] == "nosniff"
    csv_text = h_csv.wfile.getvalue().decode("utf-8")
    assert "id,record_type,title,status,due_date,numeric_value,created_at,extra_fields" in csv_text
    assert "Acme Corp Signed & Live" in csv_text
    # Leading '=' formula cell must be prefixed with single-quote
    assert "'=HYPERLINK" in csv_text


def test_phase4_overview_and_morning_briefing_custom_agent_rollup(studio_p4_env):
    registry = studio_p4_env["registry"]
    db = studio_p4_env["db"]

    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "passport_watch",
            "name": "Passport Watch",
            "icon": "🛂",
            "description": "Monitors family passport and visa expirations.",
            "ui_blocks": ["kpi_row", "quick_add_form", "countdown_cards", "history_table"],
        },
    )
    assert h_create._send_json.call_args[0][0]["status"] == "success"

    urgent_due = (date.today() + timedelta(days=7)).isoformat()
    rec_id = db.add_custom_agent_record(
        agent_id="passport_watch",
        title="Schengen Visa Renewal",
        due_date=urgent_due,
        numeric_value=180.0,
    )

    # 1. Direct DB fleet rollup surfaces the urgent item
    custom_manifests = [m for m in registry.get_manifests() if m.get("is_custom")]
    rollup = db.get_custom_agents_fleet_rollup(custom_manifests=custom_manifests)
    assert rollup["total_alerts"] >= 1
    assert any(a["agent_id"] == "passport_watch" for a in rollup["alerts"])

    # 2. BriefingEngine includes custom_agent_alerts & summary_stats.custom_alerts_count
    engine = BriefingEngine(db=db, agent_registry=registry)
    briefing = engine.generate_daily_briefing()
    assert briefing["summary_stats"]["custom_alerts_count"] >= 1
    assert any(a["agent_id"] == "passport_watch" for a in briefing["custom_agent_alerts"])
    assert "Passport Watch" in briefing["briefing_markdown"]

    # 3. Conversational Omnibar "daily briefing" includes the custom agent alert
    omni_brief = dispatch_omnibar_query("Give me my daily briefing", agent_registry=registry, db=db)
    assert omni_brief["status"] == "ok"
    assert "Schengen Visa Renewal" in omni_brief["message"]

    # 4. Marking the record completed clears the urgent alert from the rollup
    db.update_custom_agent_record("passport_watch", rec_id, status="completed")
    rollup_after = db.get_custom_agents_fleet_rollup(custom_manifests=custom_manifests)
    assert not any(a["agent_id"] == "passport_watch" for a in rollup_after["alerts"])


def test_phase4_blueprint_revision_history_and_1click_rollback(studio_p4_env):
    registry = studio_p4_env["registry"]
    db = studio_p4_env["db"]

    # 1. Create v1 custom agent
    h_create = MagicMock()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "sla_sentinel",
            "name": "SLA Sentinel v1",
            "icon": "🛡️",
            "description": "Original v1 SLA tracker.",
            "ui_blocks": ["kpi_row", "quick_add_form", "history_table"],
            "schedule_cadence": "daily_morning",
        },
    )
    assert h_create._send_json.call_args[0][0]["status"] == "success"

    # Insert a tracked SQLite record that MUST survive evolutions and rollbacks
    rec_id = db.add_custom_agent_record(
        agent_id="sla_sentinel",
        title="Tier-1 Core API 99.95% SLA",
        due_date=(date.today() + timedelta(days=20)).isoformat(),
        numeric_value=99.95,
    )

    # 2. Evolve to v2 (adds kanban_board)
    h_ev1 = MagicMock()
    evolve_custom_agent_endpoint(
        h_ev1,
        {
            "id": "sla_sentinel",
            "name": "SLA Sentinel v2",
            "icon": "⚡",
            "ui_blocks": ["kpi_row", "quick_add_form", "kanban_board", "history_table"],
            "schedule_cadence": "hourly",
        },
    )
    assert h_ev1._send_json.call_args[0][0]["status"] == "success"

    # 3. Evolve to v3 (adds ai_briefing)
    h_ev2 = MagicMock()
    evolve_custom_agent_endpoint(
        h_ev2,
        {
            "id": "sla_sentinel",
            "name": "SLA Sentinel v3",
            "icon": "🚀",
            "ui_blocks": ["kpi_row", "quick_add_form", "kanban_board", "ai_briefing", "history_table"],
            "schedule_cadence": "every_30m",
        },
    )
    assert h_ev2._send_json.call_args[0][0]["status"] == "success"
    assert registry.get_agent("sla_sentinel").name == "SLA Sentinel v3"

    # 4. List revisions via GET /api/settings/agents/revisions?id=sla_sentinel
    h_revs = MagicMock()
    list_custom_agent_revisions_endpoint(
        h_revs,
        urllib.parse.urlparse("/api/settings/agents/revisions?id=sla_sentinel"),
    )
    revs_payload = h_revs._send_json.call_args[0][0]
    assert revs_payload["status"] == "ok"
    assert revs_payload["count"] == 2
    revisions = revs_payload["revisions"]
    # Oldest snapshot is v1 (taken right before v2 evolution)
    v1_rev_id = revisions[-1]["revision_id"]
    assert revisions[-1]["name"] == "SLA Sentinel v1"

    # 5. Rollback to v1 via POST /api/settings/agents/rollback
    h_rb = MagicMock()
    rollback_custom_agent_endpoint(
        h_rb,
        {"id": "sla_sentinel", "revision_id": v1_rev_id},
    )
    rb_payload = h_rb._send_json.call_args[0][0]
    assert rb_payload["status"] == "success"
    assert rb_payload["restored_revision_id"] == v1_rev_id

    restored_agent = registry.get_agent("sla_sentinel")
    restored_manifest = restored_agent.get_ui_manifest()
    assert restored_manifest["name"] == "SLA Sentinel v1"
    assert restored_manifest["icon"] == "🛡️"
    assert "kanban_board" not in restored_manifest["ui_blocks"]
    panel_text = (restored_agent.agent_dir / "ui" / "panel.html").read_text(encoding="utf-8")
    assert "sla_sentinel_kanban_box" not in panel_text

    # 6. Verify 100% of SQLite records survived evolution + rollback untouched
    records = db.list_custom_agent_records("sla_sentinel")
    assert len(records) == 1
    assert records[0]["id"] == rec_id
    assert records[0]["title"] == "Tier-1 Core API 99.95% SLA"
