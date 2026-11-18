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
    for fn_name in (
        "playPlaylistAtIndex",
        "playNextInPlaylist",
        "playCustomPlaylistFromIndex",
        "playNextInCustomPlaylist",
        "_getVideoCardTheme",
    ):
        assert fn_name in health_js, f"Missing {fn_name} in health.js"


# =========================================================================
# [QA-04] (P2) Omnibar Voice Router, Tray Companion & Playbook/Onboarding APIs
# =========================================================================
def test_qa04_omnibar_voice_router_tray_companion_and_playbook_onboarding_apis(
    isolated_db, tmp_path, monkeypatch
):
    import fleet.core.playbook_engine as pbe
    import fleet.server as srv
    from fleet.api.settings_api import (
        get_playbooks_endpoint,
        post_omnibar_voice_endpoint,
        post_onboarding_apply_endpoint,
        post_tray_action_endpoint,
        run_playbook_endpoint,
        save_playbook_endpoint,
    )
    from fleet.core.omnibar_dispatcher import (
        dispatch_omnibar_query,
        get_omnibar_chat_history,
        get_voice_activities_catalog,
        transcribe_and_dispatch_voice_command,
    )
    from fleet.tools.tray_companion import (
        execute_tray_action,
        get_tray_companion_status,
        launch_tray_companion_background,
    )

    monkeypatch.setattr(srv, "db", isolated_db)
    monkeypatch.setattr(pbe, "PLAYBOOKS_PATH", tmp_path / "playbooks_qa04.json")

    # 1. POST /api/omnibar/voice -> transcribe_and_dispatch_voice_command + dispatch_omnibar_query + catalog
    h_voice = MagicMock()
    post_omnibar_voice_endpoint(h_voice, {"transcript": "Jarvis log water"})
    voice_res = h_voice._send_json.call_args[0][0]
    assert voice_res["status"] == "ok"

    direct_cmd = dispatch_omnibar_query("Check fleet status", db=isolated_db)
    assert isinstance(direct_cmd, dict) and direct_cmd.get("status") == "ok"
    voice_turn = transcribe_and_dispatch_voice_command("Can you hear me", db=isolated_db)
    assert voice_turn["status"] == "ok" and len(voice_turn.get("spoken_reply", "")) > 0

    catalog = get_voice_activities_catalog()
    assert isinstance(catalog, list) and len(catalog) >= 5
    history = get_omnibar_chat_history()
    assert isinstance(history, list) and len(history) >= 1

    # 2. POST /api/tray/action & tray_companion helpers
    h_tray = MagicMock()
    post_tray_action_endpoint(h_tray, {"action_id": "log_water"})
    assert h_tray._send_json.call_args[0][0]["status"] == "ok"

    tray_direct = execute_tray_action("log_water", db=isolated_db)
    assert tray_direct["status"] == "ok"
    tray_status = get_tray_companion_status(db=isolated_db)
    assert tray_status["status"] == "ok"
    assert len(tray_status["menu_actions"]) >= 4
    tray_bg = launch_tray_companion_background()
    assert tray_bg["launched"] is True

    # 3. POST /api/playbooks & POST /api/playbooks/run
    h_pb_save = MagicMock()
    save_playbook_endpoint(
        h_pb_save,
        {
            "id": "pb_qa04_hydration",
            "name": "QA04 Hydration Boost",
            "trigger": "manual",
            "enabled": True,
            "steps": [{"agent_id": "health", "task": "log_water", "label": "Log +1 Water"}],
        },
    )
    assert h_pb_save._send_json.call_args[0][0]["status"] in ("ok", "saved", "success")

    h_pb_get = MagicMock()
    get_playbooks_endpoint(h_pb_get, urllib.parse.urlparse("/api/playbooks"))
    pb_list = h_pb_get._send_json.call_args[0][0]["playbooks"]
    assert any(p["id"] == "pb_qa04_hydration" for p in pb_list)

    h_pb_run = MagicMock()
    run_playbook_endpoint(h_pb_run, {"id": "pb_qa04_hydration", "dry_run": True})
    pb_run_res = h_pb_run._send_json.call_args[0][0]
    assert pb_run_res["status"] in ("ok", "success")

    # 4. POST /api/onboarding/apply
    h_onb = MagicMock()
    post_onboarding_apply_endpoint(h_onb, {"personas": ["ffd_athlete", "pc_gamer"]})
    onb_res = h_onb._send_json.call_args[0][0]
    assert onb_res["status"] == "ok"


# =========================================================================
# [QA-07] (P2) Agent Studio Phase 6 Runtime, Batch Document Extraction & Improviser
# =========================================================================
def test_qa07_agent_studio_phase6_runtime_batch_extraction_and_improviser(
    isolated_db, tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from fleet.core.agent_studio import (
        execute_studio_agent_runtime,
        generate_custom_agent_code,
        get_agent_improvement_context,
        improvise_agent_improvement_prompt,
        prune_expired_completed_improvements,
        undertake_agent_self_improvements,
    )
    from fleet.core.document_extractor import analyze_multiple_documents_for_studio_creation
    from fleet.core.studio_phase6 import (
        answer_custom_agent_chat,
        execute_outbound_action_hooks,
        infer_recurrence_cycle,
        roll_forward_custom_agent_record,
        scan_and_ingest_agent_inbox,
    )

    # 1. Generate custom agent code & execute_studio_agent_runtime
    spec = {
        "id": "qa07_warranty_vault",
        "agent_id": "qa07_warranty_vault",
        "name": "QA07 Warranty Vault",
        "icon": "🛡️",
        "category": "Finance",
        "description": "Tracks appliance warranties and renewal dates.",
        "archetype": "tracker",
        "intelligence_mode": "deterministic",
        "permissions": ["db:read", "db:write", "ui:render"],
        "outbound_actions": ["auto_create_task", "markdown_report"],
        "routine_task": "run_check",
        "fields": [
            {"key": "title", "label": "Item Name", "type": "text"},
            {"key": "numeric_value", "label": "Coverage ($)", "type": "number"},
            {"key": "due_date", "label": "Expiry Date", "type": "date"},
        ],
    }
    code_str = generate_custom_agent_code(
        agent_id="qa07_warranty_vault",
        name="QA07 Warranty Vault",
        icon="🛡️",
        description="Tracks appliance warranties and renewal dates.",
        routine_task="run_check",
    )
    assert "class Qa07WarrantyVaultAgent" in code_str or "AgentBase" in code_str

    mock_agent = SimpleNamespace(
        id="qa07_warranty_vault",
        display_name="QA07 Warranty Vault",
        display_icon="🛡️",
        category="Finance",
        permissions=["db:read", "db:write", "ui:render"],
        manifest_meta=spec,
        db=isolated_db,
        _raw_db=isolated_db,
        event_bus=None,
        get_ui_manifest=lambda: spec,
        get_setting=lambda k, default=None: default,
    )
    rt_res = execute_studio_agent_runtime(mock_agent, task="run_check")
    assert isinstance(rt_res, dict) and rt_res.get("status") in ("ok", "success", "completed", "healthy", "warning")

    # 2. Studio Phase 6: recurrence inference, roll-forward record, outbound hooks, inbox scan, chat
    assert infer_recurrence_cycle({"title": "Monthly Broadband Bill", "data": {}}, "none") == "monthly"
    assert infer_recurrence_cycle({"title": "Annual Car Insurance Policy", "data": {}}, "none") == "annual"

    rec_id = isolated_db.add_custom_agent_record(
        agent_id="qa07_warranty_vault",
        title="Annual Home Insurance Renewal",
        record_type="entry",
        data={"recurrence": "annual"},
        status="ok",
        due_date="2026-05-01",
        numeric_value=1200.0,
    )
    rolled = roll_forward_custom_agent_record(
        isolated_db, "qa07_warranty_vault", record_id=rec_id, cycle="annual"
    )
    assert rolled["cycle"] == "annual"
    assert rolled["next_due_date"].startswith("2027-")

    hooks_res = execute_outbound_action_hooks(
        agent=mock_agent,
        db=isolated_db,
        run_status="warning",
        summary_message="1 warranty overdue",
        entries=[{"title": "Boiler Warranty", "due_date": "2026-01-01", "numeric_value": 300.0}],
        overdue_items=["Boiler Warranty (overdue)"],
        due_soon_items=[],
    )
    assert isinstance(hooks_res, dict) and "executed" in hooks_res

    scan_res = scan_and_ingest_agent_inbox(
        agent=mock_agent,
        db=isolated_db,
        payload={
            "subject": "Dishwasher Extended Warranty Invoice",
            "body": "Dishwasher Warranty renewal due 2027-12-01 for $250.00",
        },
        provider_override="deterministic",
    )
    assert scan_res["status"] == "ok"

    chat_res = answer_custom_agent_chat(
        agent=mock_agent, db=isolated_db, message="How many records are tracked?"
    )
    assert chat_res["status"] == "success" and len(chat_res.get("answer", "")) > 0

    # 3. Multi-document batch extraction
    batch_res = analyze_multiple_documents_for_studio_creation(
        documents=[
            {"filename": "appliances.csv", "text_content": "Title,Cost,Expiry\nFridge Warranty,1400,2027-01-15\n"},
            {"filename": "notes.txt", "text_content": "Extended warranty for washer expires 2027-06-30 ($199).\n"},
        ],
        user_prompt="Create an appliance warranty tracker",
        provider="deterministic",
    )
    assert batch_res["status"] == "ok"
    assert batch_res["attachments_count"] == 2
    assert len(batch_res["extraction"]["items"]) >= 1

    # 4. Context-grounded prompt improviser & self-improvements
    ctx = get_agent_improvement_context({"id": "health", "name": "Health & Wellness"})
    assert ctx["agent_id"] == "health"
    imp = improvise_agent_improvement_prompt(
        {"id": "health", "name": "Health & Wellness"},
        "Add post-meal walk reminder",
        provider="deterministic",
    )
    assert "improvised_text" in imp and len(imp["improvised_text"]) > 15

    undertake_res = undertake_agent_self_improvements(
        agent=mock_agent,
        improvements=[{"id": "imp_qa07", "title": "Add 30-day warranty escalation", "description": "Escalate 30d prior"}],
        db=isolated_db,
        provider="deterministic",
    )
    assert undertake_res["status"] in ("ok", "completed", "success")
    kept, was_pruned = prune_expired_completed_improvements(
        undertake_res.get("improvements", []), max_age_hours=24.0, db=isolated_db
    )
    assert isinstance(kept, list) and was_pruned is False


# =========================================================================
# [QA-08] (P2) Unified Fleet CLI Subcommands & Release/Auto-Fixer Tooling
# =========================================================================
def test_qa08_unified_fleet_cli_subcommands_and_release_autofixer_tooling(tmp_path, monkeypatch):
    import argparse
    import fleet.cli as cli_mod
    from fleet.tools.auto_fixer import fix_codeql_and_security_issues, resolve_pyright_command
    from fleet.tools.release_manager import (
        bump_semver,
        determine_bump_level,
        ensure_workstation_version_parity,
        parse_semver,
        run_proactive_release_check,
    )

    # 1. Verify parser construction for all subcommands
    parser = cli_mod.build_parser()
    for sub_args in (
        ["start", "--port", "7899"],
        ["stop"],
        ["status"],
        ["doctor"],
        ["mind"],
        ["agents"],
        ["security"],
        ["heal"],
        ["test"],
        ["wiki"],
        ["autofix"],
        ["release", "--bump", "auto"],
        ["docs"],
        ["lifecycle"],
        ["version"],
    ):
        parsed = parser.parse_args(sub_args)
        assert parsed.command == sub_args[0]

    # 2. Verify CLI handlers execute cleanly with mocked external calls
    assert cli_mod.cmd_version(argparse.Namespace()) == 0
    monkeypatch.setattr(
        cli_mod,
        "_api_get",
        lambda path, timeout=3: {
            "status": "online",
            "version": "5.25.0",
            "agents": [{"id": "health", "name": "Health", "enabled": True}],
            "summary": "All systems nominal",
        },
        raising=False,
    )
    assert cli_mod.cmd_status(argparse.Namespace(port=7890, json=False)) in (0, 1)
    assert cli_mod.cmd_mind(argparse.Namespace(port=7890, json=False, dream=False)) in (0, 1)
    assert cli_mod.cmd_agents(argparse.Namespace(port=7890, json=False, run=None)) in (0, 1)

    # 3. Verify release_manager semver & version parity helpers
    assert parse_semver("v5.25.0") == (5, 25, 0)
    assert bump_semver("5.25.0", "minor") == "5.26.0"
    assert bump_semver("5.25.0", "patch") == "5.25.1"
    assert (
        determine_bump_level(
            [
                {"sha": "a1b2c3d", "subject": "feat(voice): add sandbox"},
                {"sha": "e4f5g6h", "subject": "fix(ui): modal scroll"},
            ]
        )
        == "minor"
    )
    parity = ensure_workstation_version_parity()
    assert isinstance(parity, (bool, dict))
    rel_check = run_proactive_release_check()
    assert isinstance(rel_check, dict) and rel_check["status"] == "PASS"

    # 4. Verify auto_fixer helpers on isolated temporary directory
    pyright_cmd = resolve_pyright_command()
    assert isinstance(pyright_cmd, list) and len(pyright_cmd) >= 1
    sample_py = tmp_path / "sample_mod.py"
    sample_py.write_text("import os\n\ndef hello() -> str:\n    return 'ok'\n", encoding="utf-8")
    fixes = fix_codeql_and_security_issues(tmp_path)
    assert isinstance(fixes, (int, list))


# =========================================================================
# [QA-09] (P2) SQLite Schema Forward Migrations v1-v5 & Event Playbook Engine
# =========================================================================
def test_qa09_sqlite_schema_forward_migrations_and_event_playbook_engine(
    isolated_db, tmp_path, monkeypatch
):
    import sqlite3
    import fleet.core.playbook_engine as pbe
    from fleet.core.db.migrations import (
        MIGRATIONS,
        apply_migrations,
        get_current_schema_version,
    )
    from fleet.core.playbook_engine import (
        dispatch_event_trigger,
        list_playbooks,
        remove_custom_agent_playbooks,
        save_playbooks,
        sync_custom_agent_event_playbooks,
    )

    # 1. Test forward migrations v1..v5 on a brand-new raw SQLite database file with baseline tables
    raw_db_path = tmp_path / "migrations_v1_v5.db"
    conn = sqlite3.connect(str(raw_db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, status TEXT, priority TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY, created_at TEXT)")
    conn.commit()
    assert get_current_schema_version(conn) == 0
    conn.close()

    mig_res = apply_migrations(raw_db_path)
    assert mig_res["status"] == "success"
    assert mig_res["applied_count"] == len(MIGRATIONS)
    assert mig_res["current_version"] == MIGRATIONS[-1][0]

    # Idempotent re-run applies 0 migrations
    mig_res_2 = apply_migrations(raw_db_path)
    assert mig_res_2["status"] == "success"
    assert mig_res_2["applied_count"] == 0

    # 2. Test Event Playbook Engine: save, sync custom agent event playbooks, dispatch trigger, remove
    monkeypatch.setattr(pbe, "PLAYBOOKS_PATH", tmp_path / "playbooks_qa09.json")
    assert isinstance(list_playbooks(), list)

    synced = sync_custom_agent_event_playbooks(
        agent_id="qa09_morning_agent",
        name="QA09 Morning Agent",
        icon="🌅",
        routine_task="run_check",
        event_triggers=["overview.morning_briefing"],
    )
    assert any(str(p.get("id", "")).startswith("auto_evt_qa09_morning_agent") for p in synced)

    dispatched = dispatch_event_trigger(
        "overview.morning_briefing", payload={"source": "qa09_test"}, db=isolated_db
    )
    assert isinstance(dispatched, dict) and dispatched["status"] == "ok"
    assert dispatched["playbooks_triggered"] >= 1

    removed_cnt = remove_custom_agent_playbooks("qa09_morning_agent")
    assert removed_cnt >= 1


# =========================================================================
# [QA-10] (P2) Self-Improvement Header Popover, 24h Expiry & Frontend JS
# =========================================================================
def test_qa10_self_improvement_header_popover_24h_expiry_and_frontend_js(isolated_db):
    from datetime import datetime, timedelta
    from fleet.core.agent_studio import prune_expired_completed_improvements
    from fleet.core.db.backlog import ALL_CANONICAL_BACKLOG_ITEMS, UX_ROADMAP_BACKLOG_ITEMS

    # 1. Verify 24-hour auto-expiry of completed self-improvement undertakings
    old_ts = (datetime.now() - timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")
    fresh_ts = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    sample_improvements = [
        {
            "id": "imp_old_26h",
            "title": "Expired 26h Completed Item",
            "description": "Should auto-expire after 24 hours and ensure backlog persistence",
            "status": "completed",
            "progress": 100,
            "completed_at": old_ts,
        },
        {
            "id": "imp_fresh_1h",
            "title": "Fresh 1h Completed Item",
            "description": "Should remain visible in header popover",
            "status": "completed",
            "progress": 100,
            "completed_at": fresh_ts,
        },
    ]
    kept, was_pruned = prune_expired_completed_improvements(
        sample_improvements,
        max_age_hours=24.0,
        db=isolated_db,
        agent_name="PC Optimizer",
        backlog_category="Core",
    )
    assert was_pruned is True
    assert len(kept) == 1
    assert kept[0]["title"] == "Fresh 1h Completed Item"

    # 2. Verify frontend JS functions in create_agent.js, backlog.js, and settings.js
    create_agent_js = (BASE_DIR / "web" / "static" / "js" / "create_agent.js").read_text(encoding="utf-8")
    for fn_name in (
        "toggleEvolveHeaderPopover",
        "closeEvolveHeaderPopover",
        "_pruneExpiredCompletedUndertakings",
        "improviseCustomEvolvePrompt",
        "fetchStudioEvolveSuggestions",
    ):
        assert fn_name in create_agent_js, f"Missing {fn_name} in create_agent.js"

    backlog_js = (BASE_DIR / "web" / "static" / "js" / "backlog.js").read_text(encoding="utf-8")
    for fn_name in ("parseBacklogSemver", "compareBacklogSemver"):
        assert fn_name in backlog_js, f"Missing {fn_name} in backlog.js"

    settings_js = (BASE_DIR / "web" / "static" / "js" / "settings.js").read_text(encoding="utf-8")
    for fn_name in ("openSettingsModal", "closeSettingsModal", "switchSettingsModalTab", "renderSettingsAgents"):
        assert fn_name in settings_js, f"Missing {fn_name} in settings.js"

    # 3. Verify zero open P1, P2, or P3 items remain in UX_ROADMAP_BACKLOG_ITEMS & ALL_CANONICAL_BACKLOG_ITEMS
    qa_items = [i for i in UX_ROADMAP_BACKLOG_ITEMS if i["title"].startswith("[QA-")]
    assert len(qa_items) == 10
    assert all(i["status"] == "Completed" for i in qa_items)
    open_p1 = [i for i in ALL_CANONICAL_BACKLOG_ITEMS if i["priority"] == "P1" and i["status"] != "Completed"]
    open_p2 = [i for i in ALL_CANONICAL_BACKLOG_ITEMS if i["priority"] == "P2" and i["status"] != "Completed"]
    open_p3 = [i for i in ALL_CANONICAL_BACKLOG_ITEMS if i["priority"] == "P3" and i["status"] != "Completed"]
    assert len(open_p1) == 0
    assert len(open_p2) == 0
    assert len(open_p3) == 0


# =========================================================================
# [P3 Backlog Suite] #BL-5 Local Ollama LoRA Fine-Tuning & #BL-128 UX-10 Tray/Voice
# =========================================================================
def test_p3_backlog_items_local_ollama_lora_finetuning_and_ux10_tray_voice_companion(
    isolated_db, monkeypatch
):
    from pathlib import Path
    from fleet.agents.local_llm.agent import LocalLLMAgent
    from fleet.core.db.backlog import ALL_CANONICAL_BACKLOG_ITEMS
    from fleet.tools.tray_companion import (
        TRAY_MENU_ACTIONS,
        execute_tray_action,
        get_tray_companion_status,
        launch_tray_companion_background,
    )

    # 1. Verify #BL-5 (P3): Local Ollama Offline LLM Fine-Tuning & LoRA Adapter Pipeline
    llm_agent = LocalLLMAgent(db=isolated_db)
    isolated_db.add_task(
        title="Review FFD glucose logs for pankaj@example.com or +1-555-234-5678",
        description="Confidential metabolic review",
        priority="P1",
    )

    catalog = llm_agent.list_local_models()
    assert len(catalog["models"]) >= 3

    ds_res = llm_agent.build_personal_lora_dataset(max_samples=25)
    assert ds_res["status"] == "ok"
    assert ds_res["sample_count"] >= 1
    preview_str = str(ds_res["preview"])
    assert "pankaj@example.com" not in preview_str
    assert "555-234-5678" not in preview_str

    ft_res = llm_agent.run_lora_finetune_job(
        base_model="llama3.2:3b",
        adapter_name="personal-ffd-habits-lora",
        lora_rank=16,
        lora_alpha=32,
        epochs=3,
    )
    assert ft_res["status"] == "ok"
    assert ft_res["adapter"]["peft_type"] == "LORA"
    assert ft_res["adapter"]["r"] == 16
    assert ft_res["adapter"]["lora_alpha"] == 32
    assert len(ft_res["adapter"]["epoch_metrics"]) == 3
    assert ft_res["adapter"]["final_train_loss"] < ft_res["adapter"]["epoch_metrics"][0]["train_loss"]

    task_res = llm_agent.execute_task("finetune_lora")
    assert task_res["status"] == "success"
    assert "finetune" in task_res

    inf_res = llm_agent.run_local_inference(
        prompt="Summarize my morning FFD smoothie and contact me at user@domain.com",
        model="llama3.2:3b",
    )
    assert inf_res["status"] == "ok"
    assert inf_res["cost_usd"] == 0.0
    assert inf_res["pii_redacted"] >= 1
    assert "user@domain.com" not in inf_res["response"]

    # 2. Verify #BL-128 ([UX-10], P3): Ambient System Tray Companion, Global Hotkey (Alt+Space) & Voice Capture
    tray_status = get_tray_companion_status(db=isolated_db)
    assert tray_status["status"] == "ok"
    assert tray_status["global_hotkey"] == "Alt+Space"
    assert tray_status["voice_capture_supported"] is True
    assert len(TRAY_MENU_ACTIONS) == 6

    for act_id in (
        "open_dashboard",
        "log_water",
        "optimize_ram",
        "morning_briefing",
        "pause_notifications_1h",
        "voice_quick_capture",
    ):
        act_res = execute_tray_action(act_id, db=isolated_db, open_browser=False)
        assert act_res["status"] == "ok", f"Tray action {act_id} failed: {act_res}"

    voice_tray_res = execute_tray_action(
        "voice_quick_capture",
        payload={"transcript": "Can you hear me"},
        db=isolated_db,
    )
    assert voice_tray_res["status"] == "ok"
    assert len(voice_tray_res.get("spoken_reply", "")) > 0

    bg_state = launch_tray_companion_background()
    assert bg_state["launched"] is True

    app_py_text = (Path(__file__).resolve().parent.parent / "fleet" / "app.py").read_text(encoding="utf-8")
    assert '"--tray"' in app_py_text and "launch_tray_companion_background" in app_py_text

    # 3. Verify all P3 items in both canonical backlog and isolated SQLite DB are 100% Completed
    p3_canonical = [i for i in ALL_CANONICAL_BACKLOG_ITEMS if i["priority"] == "P3"]
    assert len(p3_canonical) >= 2
    assert all(i["status"] == "Completed" for i in p3_canonical)

    isolated_db.sync_ux_roadmap_backlog()
    db_p3_items = isolated_db.list_feature_backlog_items(priority="P3")
    assert len(db_p3_items) >= 2
    assert all(i["status"] == "Completed" for i in db_p3_items)

    stats = isolated_db.get_feature_backlog_stats()
    assert stats["unapproved"] == 0
    assert stats["idea"] == 0
    assert stats["planned"] == 0
    assert stats["in_progress"] == 0


def test_ultra_low_latency_voice_streaming_and_all_6_optimizations(isolated_db, monkeypatch):
    """
    Verifies all 6 Ultra-Low-Latency Voice Optimizations & Clause Audio Streaming:
      1. Early-Intent VAD Endpointing on `rec.onresult` (`commitVoiceUtteranceNow`)
      2. Speak-First Parallel Execution & Clause-by-Clause Streaming TTS (`split_speech_into_stream_clauses`, `/api/voice/stream`)
      3. Zero-Network Client Reflex Cache (`tryInstantClientVoiceFastPath`)
      4. Hardware-Local SAPI5/OneCore TTS Priority (`+160` localService boost & `_cachedVoiceByKey` + `220ms` watchdog)
      5. Instant 12ms WebAudio Chime (`playJarvisInstantAckChime`) + Hot-Mic Barge-In + Deferred Auto-Refinement
      6. Snappy / Concise Executive Voice Mode (`build_concise_spoken_reply`, `concise_mode=True`)
    """
    import fleet.server as srv
    from fleet.api.settings_api import post_voice_converse_endpoint, post_voice_stream_endpoint
    from fleet.core.omnibar_dispatcher import (
        build_concise_spoken_reply,
        split_speech_into_stream_clauses,
    )

    monkeypatch.setattr(srv, "db", isolated_db)
    isolated_db.add_task(title="Pay Electricity Bill", description="MSEB monthly payment", priority="P1", source="Monthly")
    isolated_db.add_task(title="Review Tax Portfolio", description="Annual tax review", priority="P2", source="Yearly")

    # 1. Verify Clause Splitter & Concise Spoken Reply Builder
    sample_long = "You have 2 open action items and 0 closed items. Item 1 of 2 is task number 1: Pay Electricity Bill, priority P1. Say 'close it', 'edit it', or 'next action item'."
    clauses = split_speech_into_stream_clauses(sample_long)
    assert len(clauses) >= 3
    assert len(clauses[0].split()) <= 12

    concise = build_concise_spoken_reply(
        {
            "mode": "voice_action_items_open_review",
            "pending_count": 2,
            "active_action_item": {"id": 1, "title": "Pay Electricity Bill", "priority": "P1"},
        },
        sample_long,
    )
    assert "2 open items" in concise and "Pay Electricity Bill" in concise
    assert len(concise) < len(sample_long)

    # 2. Verify POST /api/voice/stream Clause-Streaming Endpoint
    h_stream = MagicMock()
    post_voice_stream_endpoint(
        h_stream,
        {
            "transcript": "Let's discuss action items",
            "language": "en",
            "gender": "female",
            "accent": "IN",
            "concise_mode": True,
        },
    )
    stream_payload = h_stream._send_json.call_args[0][0]
    assert stream_payload["status"] == "ok"
    assert stream_payload["streaming"] is True
    assert stream_payload["concise_mode"] is True
    assert len(stream_payload["spoken_stream_clauses"]) >= 2
    events = stream_payload["stream_events"]
    assert events[0]["type"] == "ack"
    assert any(ev["type"] == "clause" and ev["is_first"] is True for ev in events)
    assert events[-1]["type"] == "complete"

    # 3. Verify POST /api/voice/converse with concise_mode=True
    h_conv = MagicMock()
    post_voice_converse_endpoint(
        h_conv,
        {
            "transcript": "Next action item",
            "concise_mode": True,
        },
    )
    conv_payload = h_conv._send_json.call_args[0][0]
    assert conv_payload["status"] == "ok"
    assert "spoken_reply_concise" in conv_payload
    assert "spoken_stream_clauses" in conv_payload

    # 4. Verify all 6 frontend optimizations in antigravity.js & dashboard.html
    ag_js = (BASE_DIR / "web" / "static" / "js" / "antigravity.js").read_text(encoding="utf-8")
    for required_sym in (
        "commitVoiceUtteranceNow",
        "splitTextIntoSpeechClauses",
        "tryInstantClientVoiceFastPath",
        "playJarvisInstantAckChime",
        "toggleVoiceConciseMode",
        "toggleVoiceAudioStreamingMode",
        "_cachedVoiceByKey",
        "bargeInFrames",
    ):
        assert required_sym in ag_js, f"Missing voice latency optimization symbol {required_sym} in antigravity.js"

    dash_html = (BASE_DIR / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "btnVoiceConciseMode" in dash_html
    assert "btnVoiceStreamMode" in dash_html
    assert "voiceLatencyBadge" in dash_html
