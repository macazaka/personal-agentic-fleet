"""
Verification Suite for 'Evolve in Studio' AI Evolution Advisor:
1. Automatic generation of 10 tailored, non-redundant improvements via AFCC's connected LLM (`POST /api/studio/evolve/suggestions`).
2. Mocked `HyperscalerGateway.complete` LLM JSON response parsing, capability sanitization, and hybrid gap-architect top-up to exact 10 items.
3. User-authored custom improvement parsing (`POST /api/studio/evolve/parse_custom` & `parse_custom_improvement_to_patch`).
4. Pick-and-choose + custom improvement application (`POST /api/settings/agents/evolve`) preserving 100% of existing SQLite records & vaulted documents, persisting `evolution_improvements`, preventing duplicate re-suggestions, and enriching `build_antigravity_deep_build_prompt`.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch
import pytest

from fleet.api.settings_api import (
    create_new_agent_endpoint,
    deep_build_agent_studio_endpoint,
    evolve_custom_agent_endpoint,
    generate_studio_evolve_suggestions_endpoint,
    parse_custom_evolve_improvement_endpoint,
)
from fleet.core.agent_studio import (
    SUPPORTED_EVENT_TRIGGERS,
    SUPPORTED_UI_BLOCKS,
    build_antigravity_deep_build_prompt,
    generate_agent_evolution_suggestions,
    parse_custom_improvement_to_patch,
)
from fleet.core.database import FleetDatabase
import fleet.core.playbook_engine as pb_engine
from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
import fleet.server as srv


class _MockJsonHandler:
    def __init__(self) -> None:
        self.last_payload: Dict[str, Any] = {}
        self.last_status: int = 200

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        self.last_payload = payload
        self.last_status = status


@pytest.fixture
def evolve_advisor_env(tmp_path: Path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    db = FleetDatabase(tmp_path / "test_evolve_advisor.db")
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
            "custom_dir": custom_dir,
        }
    pb_engine._TEST_PLAYBOOKS_MEMORY = None


def test_generate_10_evolve_suggestions_minimal_loaded_and_maxed_manifests():
    # 1. Minimal custom agent -> exact 10 distinct suggestions, top 3 recommended, zero already-enabled blocks suggested
    minimal_manifest: Dict[str, Any] = {
        "id": "basic_policy_tracker",
        "name": "Basic Policy Tracker",
        "category": "Finance",
        "description": "Track car and bike insurance policy expiry dates",
        "ui_blocks": ["kpi_row", "quick_capture_bar", "history_table"],
        "fields": [
            {"key": "title", "label": "Policy Name", "type": "text"},
            {"key": "due_date", "label": "Expiry Date", "type": "date"},
            {"key": "numeric_value", "label": "Annual Premium", "type": "number"},
        ],
        "permissions": ["db:read", "db:write", "ui:render"],
        "outbound_actions": [],
        "event_triggers": [],
        "default_recurrence": "none",
        "auto_ingest_inbox": False,
    }
    res_min = generate_agent_evolution_suggestions(minimal_manifest, provider="deterministic")
    assert res_min["status"] == "ok"
    assert res_min["count"] == 10
    sugs_min = res_min["suggestions"]
    assert len(sugs_min) == 10
    assert len({s["id"] for s in sugs_min}) == 10
    assert len({s["title"].lower() for s in sugs_min}) == 10
    assert sum(1 for s in sugs_min if s["recommended"]) == 3
    for s in sugs_min:
        add_blocks = s["patch"].get("add_blocks") or []
        for already in ("kpi_row", "quick_capture_bar", "history_table"):
            assert already not in add_blocks
        assert isinstance(s["change_pills"], list) and len(s["change_pills"]) >= 1

    # 2. Heavily-configured Insurance & Policy Sentinel (9 widgets + 5 fields, matching live user screenshot) -> still exact 10
    loaded_manifest: Dict[str, Any] = {
        "id": "insurance_policy_sentinel",
        "name": "Insurance & Policy Sentinel",
        "category": "Custom Agents",
        "description": "Track Acko car and bike insurance policies with PDF vaulting",
        "ui_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "kanban_board", "ai_insight_card", "agent_chat", "history_table",
        ],
        "fields": [
            {"key": "title", "label": "Policy / Coverage Name", "type": "text"},
            {"key": "due_date", "label": "Expiry / Renewal Date", "type": "date"},
            {"key": "numeric_value", "label": "Annual Premium", "type": "number"},
            {"key": "policy_reg_no", "label": "Policy / Reg No.", "type": "text"},
            {"key": "insurer_provider", "label": "Insurer / Provider", "type": "text"},
        ],
        "permissions": ["ui:render", "db:read", "db:write", "event_bus:publish"],
        "outbound_actions": ["auto_create_task", "markdown_report"],
        "event_triggers": ["gmail.paper_trail_detected"],
        "default_recurrence": "annual",
        "auto_ingest_inbox": True,
    }
    res_loaded = generate_agent_evolution_suggestions(
        loaded_manifest,
        runtime_summary={"entries_count": 5, "documents_count": 5, "numeric_sum": 46941},
        provider="deterministic",
    )
    assert res_loaded["count"] == 10
    assert len(res_loaded["suggestions"]) == 10
    for s in res_loaded["suggestions"]:
        # 5 fields already present -> must never propose a 6th field
        assert "add_field" not in s["patch"]
        for existing_blk in loaded_manifest["ui_blocks"]:
            assert existing_blk not in (s["patch"].get("add_blocks") or [])

    # 3. 100%-maxed-out generic manifest -> still guarantees exact 10 Domain Intelligence improvements
    maxed_manifest: Dict[str, Any] = {
        "id": "maxed_general_sentinel",
        "name": "Maxed General Sentinel",
        "category": "Productivity",
        "description": "General milestone tracker",
        "ui_blocks": list(SUPPORTED_UI_BLOCKS.keys()),
        "fields": [{"key": f"f_{i}", "label": f"Field {i}", "type": "text"} for i in range(5)],
        "permissions": list(ALLOWED_AGENT_PERMISSIONS),
        "outbound_actions": ["auto_create_task", "desktop_toast", "markdown_report", "emit_followup_event"],
        "event_triggers": list(SUPPORTED_EVENT_TRIGGERS.keys()),
        "default_recurrence": "monthly",
        "auto_ingest_inbox": True,
    }
    res_max = generate_agent_evolution_suggestions(maxed_manifest, provider="deterministic")
    assert res_max["count"] == 10
    assert len(res_max["suggestions"]) == 10


def test_generate_10_evolve_suggestions_via_connected_llm_and_hybrid_topup():
    manifest: Dict[str, Any] = {
        "id": "car_bike_health_sentinel",
        "name": "Car Bike Health Sentinel",
        "category": "Health & Lifestyle",
        "description": "Track car, bike, and family health insurance policies",
        "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "countdown_cards", "kanban_board"],
        "fields": [
            {"key": "title", "label": "Policy Name", "type": "text"},
            {"key": "due_date", "label": "Expiry Date", "type": "date"},
            {"key": "numeric_value", "label": "Annual Premium", "type": "number"},
        ],
        "permissions": ["db:read", "db:write", "ui:render"],
        "outbound_actions": [],
        "event_triggers": [],
        "default_recurrence": "none",
        "auto_ingest_inbox": False,
    }

    mock_llm_payload = {
        "analysis_summary": "Connected Gemini LLM identified 4 high-impact upgrades for Car Bike Health Sentinel.",
        "suggestions": [
            {
                "id": "llm_sparkline_premiums",
                "title": "Add Annual Premium Trend Sparkline",
                "description": "Plot historical premium increases across car, bike, and health policies.",
                "category": "UI & Analytics",
                "impact": "high",
                "icon": "📈",
                "recommended": True,
                "patch": {
                    # Intentionally includes already-enabled kpi_row to verify sanitizer strips it
                    "add_blocks": ["sparkline_chart", "kpi_row"],
                    "system_prompt_directive": "Highlight >10% premium increases across renewals.",
                },
            },
            {
                "id": "llm_ncb_field",
                "title": "Track No-Claim Bonus (NCB %) Field",
                "description": "Capture NCB discount percentage per vehicle/health policy.",
                "category": "Schema & Extraction",
                "impact": "high",
                "icon": "🏷️",
                "recommended": True,
                "patch": {
                    "add_field": {"key": "ncb_percent", "label": "NCB %", "type": "number", "placeholder": "25"},
                },
            },
            {
                "id": "llm_toast_alerts",
                "title": "Desktop Toast Alerts for 15-Day Expiries",
                "description": "Trigger OS desktop notifications when any policy enters the 15-day renewal window.",
                "category": "Automation & Hooks",
                "impact": "high",
                "icon": "🔔",
                "recommended": True,
                "patch": {
                    "add_outbound_actions": ["desktop_toast"],
                },
            },
            {
                "id": "llm_cashless_hospital_check",
                "title": "Cashless Network & Garage Readiness Audit",
                "description": "Include cashless hospital/garage claim instructions in AI briefings.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🏥",
                "recommended": False,
                "patch": {
                    "system_prompt_directive": "Summarize cashless claim eligibility and exclusions for active policies.",
                },
            },
        ],
    }

    with (
        patch(
            "fleet.core.document_extractor.resolve_afcc_connected_llm",
            return_value={
                "provider": "google",
                "model": "gemini-3.8-flash",
                "is_llm_connected": True,
                "display_label": "Google Gemini (gemini-3.8-flash)",
            },
        ),
        patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete,
    ):
        mock_complete.return_value = {
            "status": "OK",
            "provider": "google",
            "model": "gemini-3.8-flash",
            "tokens": 640,
            "text": f"```json\n{json.dumps(mock_llm_payload)}\n```",
        }
        res = generate_agent_evolution_suggestions(manifest, provider="auto")

    assert mock_complete.called
    assert res["status"] == "ok"
    assert res["llm_generated_count"] == 4
    # Hybrid top-up guarantees exact 10 suggestions even when LLM returned 4!
    assert res["count"] == 10
    assert len(res["suggestions"]) == 10
    assert res["engine_used"] == "google+gap-architect"
    assert res["model_used"] == "gemini-3.8-flash"
    assert res["tokens_used"] == 640
    assert "Connected Gemini LLM" in res["analysis_summary"]

    first_patch = res["suggestions"][0]["patch"]
    assert first_patch["add_blocks"] == ["sparkline_chart"]
    # Desktop toast suggestion automatically adds event_bus:publish permission
    third_patch = res["suggestions"][2]["patch"]
    assert "desktop_toast" in third_patch["add_outbound_actions"]
    assert "event_bus:publish" in third_patch["add_permissions"]


def test_parse_custom_improvement_to_patch_infers_capabilities_and_directives():
    base_manifest: Dict[str, Any] = {
        "ui_blocks": ["kpi_row", "quick_capture_bar", "history_table"],
        "fields": [
            {"key": "title", "label": "Policy", "type": "text"},
            {"key": "due_date", "label": "Expiry", "type": "date"},
        ],
        "permissions": ["db:read", "db:write", "ui:render"],
        "outbound_actions": [],
        "event_triggers": [],
        "default_recurrence": "none",
    }

    s1 = parse_custom_improvement_to_patch(
        "Add sparkline chart, desktop toast alerts, and track sum insured field with morning briefing sync",
        current_manifest=base_manifest,
    )
    assert s1["is_custom"] is True
    p1 = s1["patch"]
    assert "sparkline_chart" in p1["add_blocks"]
    assert "desktop_toast" in p1["add_outbound_actions"]
    assert "event_bus:publish" in p1["add_permissions"]
    assert "overview.morning_briefing" in p1["add_event_triggers"]
    assert p1["add_field"]["key"] == "sum_insured"
    assert p1["add_field"]["type"] == "number"
    assert "sum insured" in p1["system_prompt_directive"].lower()

    s2 = parse_custom_improvement_to_patch(
        "Flag policies where No-Claim Bonus dropped below 20% or IDV depreciated > 15%",
        current_manifest=base_manifest,
    )
    assert s2["is_custom"] is True
    assert "No-Claim Bonus" in s2["patch"]["system_prompt_directive"]
    assert "IDV depreciated" in s2["patch"]["code_enhancement_brief"]


def test_http_evolve_advisor_pick_choose_custom_add_and_hot_reload_preserves_sqlite(evolve_advisor_env):
    db: FleetDatabase = evolve_advisor_env["db"]
    registry: AgentRegistry = evolve_advisor_env["registry"]

    # 1. Create an insurance custom agent & populate SQLite entries + vaulted document
    h_create = _MockJsonHandler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "my_policy_guard",
            "name": "My Policy Guard",
            "icon": "🛡️",
            "category": "Finance",
            "description": "Track car and bike insurance renewals",
            "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "history_table"],
            "fields": [
                {"key": "title", "label": "Policy Name", "type": "text"},
                {"key": "due_date", "label": "Expiry Date", "type": "date"},
                {"key": "numeric_value", "label": "Annual Premium", "type": "number"},
            ],
            "permissions": ["db:read", "db:write", "ui:render"],
            "outbound_actions": [],
            "event_triggers": [],
            "default_recurrence": "none",
            "auto_ingest_inbox": False,
        },
    )
    assert h_create.last_status == 200
    assert h_create.last_payload["status"] == "success"

    db.add_custom_agent_record(
        agent_id="my_policy_guard",
        title="Acko Comprehensive Car Policy",
        record_type="entry",
        due_date="2026-11-15",
        numeric_value=14850.0,
        data={"policy_no": "ACKO-9912"},
    )
    db.add_custom_agent_record(
        agent_id="my_policy_guard",
        title="Acko-20261030.pdf",
        record_type="document",
        data={"filename": "Acko-20261030.pdf", "items_count": 1},
    )

    # 2. Click 'Evolve in Studio' -> POST /api/studio/evolve/suggestions returns exact 10 suggestions
    h_sug = _MockJsonHandler()
    generate_studio_evolve_suggestions_endpoint(h_sug, {"id": "my_policy_guard", "provider": "auto"})
    assert h_sug.last_status == 200
    assert h_sug.last_payload["status"] == "ok"
    assert h_sug.last_payload["count"] == 10
    suggestions: List[Dict[str, Any]] = h_sug.last_payload["suggestions"]
    assert len(suggestions) == 10

    # 3. User adds a custom improvement via POST /api/studio/evolve/parse_custom
    h_cust = _MockJsonHandler()
    parse_custom_evolve_improvement_endpoint(
        h_cust,
        {
            "id": "my_policy_guard",
            "text": "Add sum insured field and flag policies where NCB discount is below 25%",
        },
    )
    assert h_cust.last_status == 200
    custom_sug = h_cust.last_payload["suggestion"]
    assert custom_sug["is_custom"] is True
    assert custom_sug["patch"]["add_field"]["key"] == "sum_insured"

    # 4. User picks 2 LLM suggestions + 1 custom suggestion and hot-reloads via POST /api/settings/agents/evolve
    picked = [suggestions[0], suggestions[1], custom_sug]
    agent_obj = registry.get_agent("my_policy_guard")
    assert agent_obj is not None
    cur_manifest = agent_obj.get_ui_manifest()

    new_blocks = list(cur_manifest["ui_blocks"])
    new_perms = list(cur_manifest["permissions"])
    new_fields = list(cur_manifest["fields"])
    new_actions = list(cur_manifest["outbound_actions"])
    new_triggers = list(cur_manifest["event_triggers"])
    new_recurrence = str(cur_manifest["default_recurrence"])
    directives: List[str] = []
    evo_meta: List[Dict[str, Any]] = []

    for s in picked:
        p = s["patch"]
        for b in p.get("add_blocks") or []:
            if b not in new_blocks:
                new_blocks.append(b)
        for perm in p.get("add_permissions") or []:
            if perm not in new_perms:
                new_perms.append(perm)
        if isinstance(p.get("add_field"), dict):
            new_fields.append(p["add_field"])
        for a in p.get("add_outbound_actions") or []:
            if a not in new_actions:
                new_actions.append(a)
        for t in p.get("add_event_triggers") or []:
            if t not in new_triggers:
                new_triggers.append(t)
        if p.get("set_recurrence"):
            new_recurrence = p["set_recurrence"]
        if p.get("system_prompt_directive"):
            directives.append(p["system_prompt_directive"])
        evo_meta.append({
            "id": s["id"],
            "title": s["title"],
            "description": s["description"],
            "code_enhancement_brief": p.get("code_enhancement_brief") or s["description"],
            "is_custom": bool(s.get("is_custom")),
        })

    evolved_prompt = "Base sentinel prompt.\n\nEvolution Directives:\n" + "\n".join(f"- {d}" for d in directives)
    evolve_payload = {
        "id": "my_policy_guard",
        "name": "My Policy Guard",
        "icon": "🛡️",
        "category": "Finance",
        "description": "Track car and bike insurance renewals",
        "ui_blocks": new_blocks,
        "permissions": new_perms,
        "fields": new_fields,
        "outbound_actions": new_actions,
        "event_triggers": new_triggers,
        "default_recurrence": new_recurrence,
        "system_prompt": evolved_prompt,
        "evolution_improvements": evo_meta,
    }
    h_evolve = _MockJsonHandler()
    evolve_custom_agent_endpoint(h_evolve, evolve_payload)
    assert h_evolve.last_status == 200
    assert h_evolve.last_payload["status"] == "success"

    updated_manifest = h_evolve.last_payload["manifest"]
    assert any(f.get("key") == "sum_insured" for f in updated_manifest["fields"])
    assert len(updated_manifest["evolution_improvements"]) == 3
    assert "NCB discount is below 25%" in updated_manifest["system_prompt"]

    # 5. Verify 100% of existing SQLite entries & vaulted PDFs are preserved after evolution
    post_state = db.get_custom_agent_dashboard_state("my_policy_guard", manifest=updated_manifest)
    assert post_state["kpis"]["entries_count"] == 1
    assert post_state["kpis"]["documents_count"] == 1
    assert post_state["entries"][0]["title"] == "Acko Comprehensive Car Policy"
    assert post_state["entries"][0]["numeric_value"] == 14850.0

    # 6. Subsequent 'Evolve in Studio' click does NOT re-suggest already-applied improvements, and still returns 10
    h_sug2 = _MockJsonHandler()
    generate_studio_evolve_suggestions_endpoint(h_sug2, {"id": "my_policy_guard", "provider": "deterministic"})
    assert h_sug2.last_status == 200
    assert h_sug2.last_payload["count"] == 10
    second_titles = {s["title"].lower() for s in h_sug2.last_payload["suggestions"]}
    for applied in evo_meta:
        assert applied["title"].lower() not in second_titles

    # 7. Deep-Build engineering brief includes selected & custom evolution improvements
    deep_brief = build_antigravity_deep_build_prompt(evolve_payload)
    assert "Requested Evolution Improvements & Custom Logic:" in deep_brief
    assert custom_sug["title"] in deep_brief


def test_deep_build_endpoint_propagates_dispatch_failures_and_vault_status(evolve_advisor_env):
    spec_payload: Dict[str, Any] = {
        "id": "deep_build_status_guard",
        "name": "Deep Build Status Guard",
        "icon": "🛡️",
        "category": "Finance",
        "description": "Track renewal milestones with Deep-Build status propagation",
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"],
        "fields": [
            {"key": "title", "label": "Policy Name", "type": "text"},
            {"key": "due_date", "label": "Expiry Date", "type": "date"},
        ],
        "permissions": ["db:read", "db:write", "ui:render"],
    }

    # 1. Dispatch failure -> HTTP 502 + status='error' so UI triggers red failure toast & modal banner
    h_err = _MockJsonHandler()
    with patch.object(
        srv,
        "execute_dashboard_command",
        return_value={"status": "error", "message": "Antigravity Live CLI bridge offline"},
    ):
        deep_build_agent_studio_endpoint(h_err, spec_payload)

    assert h_err.last_status == 502
    assert h_err.last_payload["status"] == "error"
    assert h_err.last_payload["dispatch_status"] == "error"
    assert "Antigravity Live CLI bridge offline" in h_err.last_payload["message"]

    # 2. All parallel slots busy -> HTTP 409 + status='error'
    h_busy = _MockJsonHandler()
    with patch.object(
        srv,
        "execute_dashboard_command",
        return_value={"status": "busy", "message": "All 4 parallel Antigravity slots are busy"},
    ):
        deep_build_agent_studio_endpoint(h_busy, {**spec_payload, "is_evolve": True})

    assert h_busy.last_status == 409
    assert h_busy.last_payload["status"] == "error"
    assert h_busy.last_payload["dispatch_status"] == "busy"
    assert "busy" in h_busy.last_payload["message"].lower()

    # 3. Token-exhausted vaulting -> HTTP 200 + dispatch_status='vaulted' with clear user notice
    h_vault = _MockJsonHandler()
    with patch.object(
        srv,
        "execute_dashboard_command",
        return_value={"status": "vaulted", "type": "token_exhausted"},
    ):
        deep_build_agent_studio_endpoint(h_vault, {**spec_payload, "is_evolve": True})

    assert h_vault.last_status == 200
    assert h_vault.last_payload["status"] == "success"
    assert h_vault.last_payload["dispatch_status"] == "vaulted"
    assert "vaulted" in h_vault.last_payload["message"].lower()


def test_ui_async_action_feedback_and_failure_notification_wiring():
    repo_root = Path(__file__).parent.parent
    dashboard_html = (repo_root / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    create_agent_js = (repo_root / "fleet" / "web" / "static" / "js" / "create_agent.js").read_text(encoding="utf-8")

    # Persistent modal-wide progress & error banner exists outside step panels
    assert 'id="studioGlobalActionBanner"' in dashboard_html
    assert 'id="studioGlobalActionBannerIcon"' in dashboard_html
    assert 'id="studioGlobalActionBannerText"' in dashboard_html
    assert 'id="studioGlobalActionBannerTimer"' in dashboard_html
    assert 'id="btnGuidedRibbonLaunch"' in dashboard_html

    # Universal async button feedback & error notification engine wired across Studio & CustomAgentRuntime
    for required_symbol in (
        "async function runFleetAsyncAction(",
        "function setStudioGlobalBanner(",
        "function clearStudioGlobalBanner(",
        "btnWizardDeepBuild",
        "btnApplyEvolveDeepBuild",
        "btnQuickApplyEvolveReload",
        "btnGuidedRibbonLaunch",
        "btnStageEvolveAgent",
        "clearStudioStagedDocExtraction()",
        "window.clearStudioStagedDocument = clearStudioStagedDocExtraction;",
        "setAgChatEngineMode('antigravity_live')",
    ):
        assert required_symbol in create_agent_js, f"Missing required symbol in create_agent.js: {required_symbol}"

    # Verify eliminated post-Deep-Build crash & invalid view-switch calls never reappear
    assert "nav.switchAgent('antigravity_live')" not in create_agent_js
    assert "fetchAntigravityStatus" not in create_agent_js


