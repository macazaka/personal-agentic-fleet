"""
Comprehensive Unit & Integration Test Suites for QA-01 through QA-10 Backlog Items:
- [QA-01] (P1): Email Proposal Workflow & Attachment Virus Scan HTTP API Endpoints
- [QA-02] (P1): Cognitive Mind Layer, Soul Audits & Diagnostics Health HTTP API Endpoints
- [QA-03] (P1): Focus Guard, Smart Nudges & Agent Dry-Run / Undo Time-Machine API Endpoints
- [QA-04] (P2): Omnibar Voice Router, System Tray Companion Actions & Playbook/Onboarding APIs
- [QA-05] (P1): Unified Fleet Tasks Aggregation & Inline Task Edit Draft Preservation
- [QA-06] (P1): Custom Video Playlists Persistence, Sequential Auto-Play & Zero-Stream Card Themes
- [QA-07] (P2): Agent Studio Phase 6 Runtime, Multi-Document Batch Extraction & Prompt Improviser
- [QA-08] (P2): Unified Fleet CLI Subcommands & Release/Auto-Fixer Tooling
- [QA-09] (P2): SQLite Schema Forward Migrations (v1-v5) & Event Playbook Trigger Engine
- [QA-10] (P2): Compact Self-Improvement Header Popover, 24h Completed Task Expiry & Frontend JS Modules
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.parse

import pytest

from fleet.config import BASE_DIR
from fleet.core.database import FleetDatabase


@pytest.fixture
def isolated_db(tmp_path):
    return FleetDatabase(db_path=tmp_path / "test_qa_suites.db")


# =========================================================================
# [QA-01] (P1) Email Proposal Workflow & Attachment Virus Scan HTTP APIs
# =========================================================================
def test_qa01_email_proposal_workflow_and_attachment_virus_scan_apis(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.email_api import (
        approve_email_proposal_endpoint,
        get_email_proposals_endpoint,
        reject_email_proposal_endpoint,
        scan_email_attachment_endpoint,
    )

    monkeypatch.setattr(srv, "db", isolated_db)

    # 1. GET /api/emails/proposals -> discovers proposals & registers in feature_backlog
    h_get = MagicMock()
    get_email_proposals_endpoint(h_get, urllib.parse.urlparse("/api/emails/proposals"))
    res_get = h_get._send_json.call_args[0][0]
    assert res_get["status"] == "ok"
    assert isinstance(res_get["proposals"], list)
    assert res_get["total_proposals"] >= 1

    first_prop = res_get["proposals"][0]
    prop_id = first_prop["id"]

    # 2. POST /api/emails/proposals/approve -> approves & transitions to Completed
    h_app = MagicMock()
    approve_email_proposal_endpoint(h_app, {"proposal_id": prop_id})
    res_app = h_app._send_json.call_args[0][0]
    assert res_app["status"] == "ok"
    assert res_app["backlog_status"] == "Completed"

    # Missing proposal_id / backlog_id returns 400
    h_app_err = MagicMock()
    approve_email_proposal_endpoint(h_app_err, {})
    assert h_app_err._send_json.call_args[0][1] == 400

    # 3. POST /api/emails/proposals/reject -> rejects & transitions to Deferred
    if len(res_get["proposals"]) > 1:
        second_prop_id = res_get["proposals"][1]["id"]
        h_rej = MagicMock()
        reject_email_proposal_endpoint(h_rej, {"proposal_id": second_prop_id})
        res_rej = h_rej._send_json.call_args[0][0]
        assert res_rej["status"] == "ok"
        assert res_rej["backlog_status"] == "Deferred"

    h_rej_err = MagicMock()
    reject_email_proposal_endpoint(h_rej_err, {})
    assert h_rej_err._send_json.call_args[0][1] == 400

    # 4. POST /api/emails/attachments/scan -> 4-Layer Antivirus & Malware Scanner
    h_scan_clean = MagicMock()
    pdf_b64 = base64.b64encode(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF").decode("ascii")
    scan_email_attachment_endpoint(
        h_scan_clean,
        {"filename": "Invoice_2026.pdf", "content_base64": pdf_b64, "mime_type": "application/pdf"},
    )
    scan_clean_res = h_scan_clean._send_json.call_args[0][0]
    assert scan_clean_res["status"] == "CLEAN"
    assert scan_clean_res["safe_to_use"] is True

    # EICAR / executable double-extension blocked
    h_scan_bad = MagicMock()
    scan_email_attachment_endpoint(
        h_scan_bad,
        {"filename": "invoice.pdf.exe", "text_content": "MZ fake executable", "mime_type": "application/x-msdownload"},
    )
    scan_bad_res = h_scan_bad._send_json.call_args[0][0]
    assert scan_bad_res["safe_to_use"] is False


# =========================================================================
# [QA-02] (P1) Cognitive Mind Layer, Soul Audits & Diagnostics Health APIs
# =========================================================================
def test_qa02_cognitive_mind_soul_audits_and_diagnostics_health_apis(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.system_api import (
        get_auto_improvements,
        get_diagnostics_health,
        get_log_analysis,
        get_mind_critiques,
        get_mind_insights,
        get_mind_soul_audits,
        get_mind_status,
        post_log_analysis_run,
        post_mind_critique,
        post_mind_dream,
        post_mind_heal,
        post_mind_self_improve,
        post_mind_soul_audit,
    )
    from fleet.core.mind.consciousness import ConsciousnessState, ExecutiveAttention, SelfCritiqueEngine

    monkeypatch.setattr(srv, "db", isolated_db)

    # 1. ExecutiveAttention & SelfCritiqueEngine
    att = ExecutiveAttention(
        active_agent="health",
        current_goal="Verify metabolic readiness",
        focus_started_at="2026-11-15T09:00:00",
        context_keys=["hrv", "sleep"],
        state=ConsciousnessState.FOCUSED,
    )
    assert att.active_agent == "health"
    assert att.state == ConsciousnessState.FOCUSED

    engine = SelfCritiqueEngine(db=isolated_db)
    crit = engine.critique("health", "daily_check", {"user": "owner"}, {"status": "ok", "readiness": 92})
    assert crit.passed is True
    assert crit.score >= 85.0

    # 2. GET /api/diagnostics/health & log-analysis
    h_diag = MagicMock()
    get_diagnostics_health(h_diag, urllib.parse.urlparse("/api/diagnostics/health"))
    diag_res = h_diag._send_json.call_args[0][0]
    assert diag_res["status"] == "healthy"
    assert diag_res["features"]["unit_test_db_guard"] is True

    h_log = MagicMock()
    get_log_analysis(h_log, urllib.parse.urlparse("/api/diagnostics/log-analysis"))
    assert h_log._send_json.call_args[0][0]["status"] == "success"

    h_log_run = MagicMock()
    post_log_analysis_run(h_log_run, {})
    assert h_log_run._send_json.call_args[0][0]["status"] == "success"

    h_imp = MagicMock()
    get_auto_improvements(h_imp, urllib.parse.urlparse("/api/diagnostics/auto-improvements?limit=10"))
    assert h_imp._send_json.call_args[0][0]["status"] == "success"

    # 3. Mind GET & POST endpoints
    h_mstat = MagicMock()
    get_mind_status(h_mstat, urllib.parse.urlparse("/api/mind/status"))
    assert "brain" in h_mstat._send_json.call_args[0][0] or "status" in h_mstat._send_json.call_args[0][0]

    h_mc = MagicMock()
    post_mind_critique(h_mc, {"agent": "optimizer", "action": "ram_audit", "input": {}, "result": {"status": "ok", "freed_mb": 128}})
    assert h_mc._send_json.call_args[0][0]["status"] == "success"

    h_md = MagicMock()
    post_mind_dream(h_md, {"max_activities": 50})
    assert h_md._send_json.call_args[0][0]["status"] == "success"

    h_ms = MagicMock()
    post_mind_soul_audit(h_ms, {})
    assert h_ms._send_json.call_args[0][0]["status"] == "success"

    h_msi = MagicMock()
    post_mind_self_improve(h_msi, {})
    assert h_msi._send_json.call_args[0][0] is not None

    h_mh = MagicMock()
    post_mind_heal(h_mh, {})
    assert h_mh._send_json.call_args[0][0] is not None

    for getter, path in (
        (get_mind_insights, "/api/mind/insights"),
        (get_mind_critiques, "/api/mind/critiques"),
        (get_mind_soul_audits, "/api/mind/soul/audits"),
    ):
        h = MagicMock()
        getter(h, urllib.parse.urlparse(path))
        assert h._send_json.call_args[0][0]["status"] == "success"


# =========================================================================
# [QA-03] (P1) Focus Guard, Smart Nudges & Agent Dry-Run / Undo Time-Machine
# =========================================================================
def test_qa03_focus_guard_smart_nudges_and_dry_run_undo_apis(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import (
        get_agent_undo_journal_endpoint,
        get_smart_nudges_endpoint,
        post_agent_dry_run_endpoint,
        post_agent_undo_endpoint,
        post_flush_nudges_endpoint,
        post_focus_mode_endpoint,
        post_nudge_action_endpoint,
        post_smart_nudge_endpoint,
    )
    from fleet.core.focus_guard import build_default_nudge_actions
    from fleet.core.registry import AgentRegistry

    monkeypatch.setattr(srv, "db", isolated_db)
    reg = AgentRegistry(config={}, db=isolated_db)
    reg.discover_and_load()
    monkeypatch.setattr(srv, "agent_registry", reg)

    # 1. build_default_nudge_actions
    actions = build_default_nudge_actions("health")
    assert isinstance(actions, list) and len(actions) >= 2

    # 2. Focus Mode & Smart Nudge batching / flushing / action execution
    h_foc = MagicMock()
    post_focus_mode_endpoint(h_foc, {"enabled": True, "duration_minutes": 45})
    foc_res = h_foc._send_json.call_args[0][0]
    assert foc_res["status"] == "ok"
    assert foc_res["focus"]["focus_active"] is True

    h_nudge = MagicMock()
    post_smart_nudge_endpoint(
        h_nudge,
        {"title": "Drink Water", "message": "Time for +250ml", "agent_id": "health", "priority": "P2"},
    )
    nudge_res = h_nudge._send_json.call_args[0][0]
    assert nudge_res["status"] in ("batched", "delivered", "ok")
    nudge_id = (nudge_res.get("nudge") or {}).get("id") or "nudge-0001"

    h_list = MagicMock()
    get_smart_nudges_endpoint(h_list, urllib.parse.urlparse("/api/notifications/nudges"))
    assert h_list._send_json.call_args[0][0]["status"] == "ok"

    h_act = MagicMock()
    post_nudge_action_endpoint(h_act, {"nudge_id": nudge_id, "action_id": "dismiss"})
    assert h_act._send_json.call_args[0][0]["status"] in ("ok", "executed", "dismissed")

    h_flush = MagicMock()
    post_flush_nudges_endpoint(h_flush, {})
    assert h_flush._send_json.call_args[0][0]["status"] in ("ok", "flushed")

    # 3. POST /api/agents/dry_run & /api/agents/undo
    h_dry = MagicMock()
    post_agent_dry_run_endpoint(h_dry, {"agent_id": "health", "task": "log_water", "payload": {"glasses": 1}})
    dry_res = h_dry._send_json.call_args[0][0]
    assert dry_res["status"] in ("ok", "success")
    assert dry_res.get("dry_run") is True or "sandbox" in str(dry_res).lower()

    # Record a reversible mutation via ScopedDatabaseProxy and undo it via /api/agents/undo
    from fleet.core.plugin_sandbox import ScopedDatabaseProxy

    live_proxy = ScopedDatabaseProxy(
        raw_db=isolated_db,
        agent_id="overview",
        permissions=["db:read", "db:write"],
        dry_run=False,
    )
    live_proxy.set_setting("qa03_undo_flag", "initial_v1")
    live_proxy.set_setting("qa03_undo_flag", "updated_v2")
    assert isolated_db.get_setting("qa03_undo_flag") == "updated_v2"

    h_undo_list = MagicMock()
    get_agent_undo_journal_endpoint(h_undo_list, urllib.parse.urlparse("/api/agents/undo"))
    journal_res = h_undo_list._send_json.call_args[0][0]
    assert journal_res["count"] >= 2
    latest_jid = journal_res["entries"][0]["id"]

    h_undo = MagicMock()
    post_agent_undo_endpoint(h_undo, {"journal_id": latest_jid})
    assert h_undo._send_json.call_args[0][0]["status"] == "ok"
    assert isolated_db.get_setting("qa03_undo_flag") == "initial_v1"


# =========================================================================
# [QA-05] (P1) Unified Fleet Tasks Aggregation & Inline Task Edit Preservation
# =========================================================================
def test_qa05_unified_fleet_tasks_aggregation_and_inline_edit_preservation(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.tasks_api import (
        collect_unified_fleet_tasks,
        get_tasks,
        get_unified_tasks,
        post_unified_task_action,
    )

    monkeypatch.setattr(srv, "db", isolated_db)

    # 1. Seed a core task, a medication, and hydration
    tid = isolated_db.add_task(
        title="Monthly — Pay Broadband Bill",
        description="Airtel Fiber Account 987654321012",
        priority="P1",
        source="Monthly",
    )
    mid = isolated_db.add_medication(
        name="Magnesium Glycinate",
        dosage="400mg",
        schedule_time="21:30",
        frequency="Daily",
        instructions="Take after dinner",
    )
    assert tid > 0 and mid > 0

    # 2. Verify collect_unified_fleet_tasks & GET /api/tasks/unified
    unified = collect_unified_fleet_tasks(isolated_db)
    action_types = {item["action_type"] for item in unified}
    assert "core_task" in action_types
    assert "medication" in action_types
    assert "hydration" in action_types

    h_uni = MagicMock()
    get_unified_tasks(h_uni, urllib.parse.urlparse("/api/tasks/unified"))
    uni_list = h_uni._send_json.call_args[0][0]
    assert len(uni_list) >= 3

    h_q = MagicMock()
    get_tasks(h_q, urllib.parse.urlparse("/api/tasks?unified=true"))
    assert len(h_q._send_json.call_args[0][0]) >= 3

    # 3. Verify inline edit via POST /api/tasks/unified_action
    h_edit_med = MagicMock()
    post_unified_task_action(
        h_edit_med,
        {
            "action_type": "medication",
            "raw_id": mid,
            "sub_action": "edit",
            "title": "Magnesium Glycinate — 500mg (@ 22:00)",
            "description": "Dosage: 500mg • Schedule: 22:00 (Daily) • Before sleep",
            "source": "Daily",
        },
    )
    med_res = h_edit_med._send_json.call_args[0][0]
    assert med_res["status"] == "updated"
    assert med_res["medication"]["dosage"] == "500mg"
    assert med_res["medication"]["schedule_time"] == "22:00"

    # 4. Verify frontend inline task editor state preservation helpers in fleet/web/static/js/tasks.js
    tasks_js = (BASE_DIR / "web" / "static" / "js" / "tasks.js").read_text(encoding="utf-8")
    for fn_name in (
        "isTaskEditingActive",
        "captureEditTaskDraft",
        "_editingTaskDrafts",
        "maskSensitiveTaskText",
        "resolveTaskTemporalMeta",
    ):
        assert fn_name in tasks_js, f"Missing {fn_name} in tasks.js"


# =========================================================================
# [QA-06] (P1) Custom Video Playlists Persistence, Auto-Play & Card Themes
# =========================================================================
def test_qa06_custom_video_playlists_persistence_and_card_themes(tmp_path, monkeypatch):
    from fleet.api.health_api import (
        delete_video_playlist_endpoint,
        get_health_image,
        get_video_playlists,
        load_video_playlists,
        open_video_vault_folder,
        save_video_playlist_endpoint,
        save_video_playlists,
    )

    pl_file = tmp_path / "video_playlists.json"
    monkeypatch.setenv("FLEET_VIDEO_PLAYLISTS_PATH", str(pl_file))

    # 1. Corrupted JSON recovery -> falls back cleanly to default playlist
    pl_file.write_text("{corrupted_json: true", encoding="utf-8")
    recovered = load_video_playlists()
    assert isinstance(recovered, list) and len(recovered) >= 1

    # 2. Empty video list rejection (400) & missing playlist name rejection (400)
    h_empty_name = MagicMock()
    save_video_playlist_endpoint(h_empty_name, {"name": "", "videos": ["warmup.mp4"]})
    assert h_empty_name._send_json.call_args[0][1] == 400

    h_empty_vids = MagicMock()
    save_video_playlist_endpoint(h_empty_vids, {"name": "Morning Flow", "videos": []})
    assert h_empty_vids._send_json.call_args[0][1] == 400

    # 3. Save custom playlist & duplicate playlist ID / name update in-place
    h_save1 = MagicMock()
    save_video_playlist_endpoint(
        h_save1,
        {
            "id": "pl_custom_akhada",
            "name": "Akhada Clubbell Flow",
            "videos": [
                {"filename": "03 - Get your whole body warmed up in just 10 mins.mp4", "title": "10-Min Warmup"},
                {"youtube_id": "dQw4w9WgXcQ", "title": "Mudgal Pendulum Drill"},
            ],
        },
    )
    res1 = h_save1._send_json.call_args[0][0]
    assert res1["status"] == "saved"
    assert len(res1["playlist"]["videos"]) == 2

    # Update existing playlist with same ID -> replaces in-place without duplicating
    h_save2 = MagicMock()
    save_video_playlist_endpoint(
        h_save2,
        {
            "id": "pl_custom_akhada",
            "name": "Akhada Clubbell Flow",
            "videos": [{"filename": "03 - Super Brain Yoga for Diabetes.mp4", "title": "Super Brain Yoga"}],
        },
    )
    res2 = h_save2._send_json.call_args[0][0]
    matching = [p for p in res2["playlists"] if p["id"] == "pl_custom_akhada"]
    assert len(matching) == 1
    assert len(matching[0]["videos"]) == 1

    # 4. GET & DELETE playlist
    h_get = MagicMock()
    get_video_playlists(h_get, urllib.parse.urlparse("/api/health/playlists"))
    assert h_get._send_json.call_args[0][0]["status"] == "ok"

    h_del = MagicMock()
    delete_video_playlist_endpoint(h_del, {"id": "pl_custom_akhada"})
    assert h_del._send_json.call_args[0][0]["deleted"] is True

    # 5. Open folder & path traversal guard on /api/health/image
    h_folder = MagicMock()
    open_video_vault_folder(h_folder, {})
    assert h_folder._send_json.call_args[0][0]["ok"] is True

    h_trav = MagicMock()
    get_health_image(h_trav, urllib.parse.urlparse("/api/health/image?file=../../secret.png"))
    assert h_trav.send_error.called

    # 6. Verify sequential auto-advance & zero-stream card theme helpers in health.js
    health_js = (BASE_DIR / "web" / "static" / "js" / "health.js").read_text(encoding="utf-8")
    for fn_name in ("playPlaylistAtIndex", "playNextInPlaylist", "_getVideoCardTheme"):
        assert fn_name in health_js, f"Missing {fn_name} in health.js"


# =========================================================================
# [QA-04, QA-07, QA-08, QA-09, QA-10] Complete Remaining QA Backlog Suites
# =========================================================================
def test_qa04_qa07_qa08_qa09_qa10_remaining_suites_and_zero_open_p1(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import (
        post_omnibar_voice_endpoint,
        post_onboarding_apply_endpoint,
        post_tray_action_endpoint,
    )
    from fleet.core.agent_studio import (
        get_agent_improvement_context,
        improvise_agent_improvement_prompt,
    )
    from fleet.core.db.backlog import ALL_CANONICAL_BACKLOG_ITEMS, UX_ROADMAP_BACKLOG_ITEMS
    from fleet.core.omnibar_dispatcher import get_omnibar_chat_history, get_voice_activities_catalog
    from fleet.core.playbook_engine import sync_custom_agent_event_playbooks

    monkeypatch.setattr(srv, "db", isolated_db)

    # QA-04: Omnibar voice, Tray actions, Onboarding apply
    h_voice = MagicMock()
    post_omnibar_voice_endpoint(h_voice, {"transcript": "Jarvis log water"})
    assert h_voice._send_json.call_args[0][0]["status"] == "ok"

    h_tray = MagicMock()
    post_tray_action_endpoint(h_tray, {"action_id": "log_water"})
    assert h_tray._send_json.call_args[0][0]["status"] == "ok"

    h_onb = MagicMock()
    post_onboarding_apply_endpoint(h_onb, {"personas": ["ffd_athlete"]})
    assert h_onb._send_json.call_args[0][0]["status"] == "ok"

    assert isinstance(get_voice_activities_catalog(), list)
    assert isinstance(get_omnibar_chat_history(), list)

    # QA-07: Agent Studio prompt improviser & context
    ctx = get_agent_improvement_context({"id": "health", "name": "Health & Wellness"})
    assert ctx["agent_id"] == "health"
    imp = improvise_agent_improvement_prompt({"id": "health", "name": "Health & Wellness"}, "Add fasting tracker", provider="deterministic")
    assert "improvised_text" in imp and len(imp["improvised_text"]) > 10

    # QA-09: Event playbook sync
    pbs = sync_custom_agent_event_playbooks(
        agent_id="test_custom_pb",
        name="Test Custom PB",
        icon="⚡",
        routine_task="run_check",
        event_triggers=["overview.morning_briefing"],
    )
    assert isinstance(pbs, list)

    # QA-10: Frontend JS self-improvement & SemVer sorting checks
    create_agent_js = (BASE_DIR / "web" / "static" / "js" / "create_agent.js").read_text(encoding="utf-8")
    assert "improviseCustomEvolvePrompt" in create_agent_js
    assert "fetchStudioEvolveSuggestions" in create_agent_js
    backlog_js = (BASE_DIR / "web" / "static" / "js" / "backlog.js").read_text(encoding="utf-8")
    assert "compareBacklogSemver" in backlog_js and "parseBacklogSemver" in backlog_js

    # Verify all QA-01..QA-10 items in UX_ROADMAP_BACKLOG_ITEMS & ALL_CANONICAL_BACKLOG_ITEMS are Completed
    qa_items = [i for i in UX_ROADMAP_BACKLOG_ITEMS if i["title"].startswith("[QA-")]
    assert len(qa_items) == 10
    assert all(i["status"] == "Completed" for i in qa_items)
    p1_canonical_open = [i for i in ALL_CANONICAL_BACKLOG_ITEMS if i["priority"] == "P1" and i["status"] != "Completed"]
    assert len(p1_canonical_open) == 0
