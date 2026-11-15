"""
Comprehensive Verification Suite for Feature Backlog Completion (UX-06 to UX-10)
and the 3 New Built-in Fleet Agents (remote_chat, mcp_studio, local_llm).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import urllib.parse

import pytest

from fleet.api.router import ApiRouter


@pytest.fixture
def isolated_db(tmp_path: Path):
    from fleet.core.database import FleetDatabase

    db_file = tmp_path / "test_backlog_complete.db"
    return FleetDatabase(db_path=db_file)


def test_ux06_persona_onboarding_engine(isolated_db):
    from fleet.core.onboarding_engine import (
        PERSONA_PROFILES,
        apply_persona_onboarding,
        get_onboarding_state,
    )

    assert len(PERSONA_PROFILES) >= 4
    initial = get_onboarding_state(db=isolated_db)
    assert initial["completed"] is False

    applied = apply_persona_onboarding(
        payload={
            "personas": ["ffd_athlete", "software_engineer"],
            "rhythm": {
                "wake_time": "07:00",
                "deep_work_start": "09:00",
                "evening_wrap_time": "20:30",
                "water_target_ml": 3500,
            },
            "ergonomics": {"layout": "command_deck", "theme": "aurora"},
        },
        db=isolated_db,
        persist_files=False,
    )
    assert applied["status"] == "ok"
    assert "ffd_athlete" in applied["onboarding"]["personas"]
    assert "health" in applied["onboarding"]["pinned_agents"]
    assert "pr_review" in applied["onboarding"]["pinned_agents"]

    after = get_onboarding_state(db=isolated_db)
    assert after["completed"] is True
    assert after["rhythm"]["water_target_ml"] == 3500


def test_ux07_focus_guard_and_smart_nudges(isolated_db):
    from fleet.core.focus_guard import (
        detect_focus_state,
        dispatch_or_batch_nudge,
        execute_nudge_action,
        flush_nudge_digest,
        list_smart_nudges,
        set_focus_mode,
    )

    set_focus_mode(enabled=False, db=isolated_db)
    state0 = detect_focus_state(db=isolated_db)
    assert state0["manual_focus"] is False

    # Enable focus mode and verify non-critical nudge is batched
    set_focus_mode(enabled=True, duration_minutes=45, db=isolated_db)
    batched = dispatch_or_batch_nudge(
        title="Hydration Reminder",
        message="Drink 250ml of water",
        agent_id="health",
        priority="P2",
        db=isolated_db,
    )
    assert batched["status"] == "batched"
    assert len(batched["nudge"]["actions"]) >= 2

    listing = list_smart_nudges(db=isolated_db)
    assert listing["batched_count"] >= 1

    # Execute 1-click hydration action
    act_res = execute_nudge_action(
        nudge_id=batched["nudge"]["id"],
        action_id="log_water_250",
        db=isolated_db,
    )
    assert act_res["status"] == "ok"

    # Queue another nudge and flush digest
    dispatch_or_batch_nudge(
        title="Routine Check",
        message="Stretch for 2 minutes",
        agent_id="health",
        priority="P2",
        db=isolated_db,
    )
    flushed = flush_nudge_digest(db=isolated_db)
    assert flushed["flushed_count"] >= 1
    assert list_smart_nudges(db=isolated_db)["batched_count"] == 0
    set_focus_mode(enabled=False, db=isolated_db)


def test_ux08_agent_time_machine_undo_and_dry_run(isolated_db):
    from fleet.core.plugin_sandbox import ScopedDatabaseProxy

    proxy = ScopedDatabaseProxy(
        raw_db=isolated_db,
        agent_id="test_agent",
        permissions=["db:read", "db:write"],
        dry_run=True,
    )
    task_id = proxy.add_task("Simulated Dry Run Task", priority="P1")
    assert task_id == 0
    assert len(proxy.recorded_mutations) == 1
    assert len(isolated_db.list_tasks()) == 0

    # Real execution records undo journal entry and allows 1-click rollback
    live_proxy = ScopedDatabaseProxy(
        raw_db=isolated_db,
        agent_id="test_agent",
        permissions=["db:read", "db:write"],
        dry_run=False,
    )
    live_proxy.set_setting("custom_agent_flag", "alpha")
    assert isolated_db.get_setting("custom_agent_flag") == "alpha"

    live_proxy.set_setting("custom_agent_flag", "beta")
    assert isolated_db.get_setting("custom_agent_flag") == "beta"

    journal = isolated_db.list_agent_undo_journal(limit=10)
    assert len(journal) >= 2

    revert_res = isolated_db.undo_agent_mutation(journal_id=journal[0]["id"])
    assert revert_res["status"] == "ok"
    assert isolated_db.get_setting("custom_agent_flag") == "alpha"


def test_ux09_and_ux10_tray_and_voice_commands(isolated_db):
    from fleet.core.omnibar_dispatcher import transcribe_and_dispatch_voice_command
    from fleet.tools.tray_companion import execute_tray_action, get_tray_companion_status

    tray_status = get_tray_companion_status(db=isolated_db)
    assert tray_status["status"] == "ok"
    assert tray_status["global_hotkey"] == "Alt+Space"
    assert len(tray_status["menu_actions"]) >= 4

    water_act = execute_tray_action("log_water", db=isolated_db)
    assert water_act["status"] == "ok"

    voice_res = transcribe_and_dispatch_voice_command(
        transcript="Please log a glass of water",
        db=isolated_db,
    )
    assert voice_res["status"] == "ok"
    assert voice_res["normalized_command"] == "@health water +250"


def test_three_new_agents_remote_chat_mcp_studio_local_llm(isolated_db):
    from fleet.agents.local_llm.agent import LocalLLMAgent
    from fleet.agents.mcp_studio.agent import MCPStudioAgent
    from fleet.agents.remote_chat.agent import RemoteChatAgent

    router = ApiRouter()
    agents_root = Path(__file__).resolve().parents[1] / "fleet" / "agents"

    # 1. RemoteChatAgent (#2 Telegram & WhatsApp Remote Bot Interface)
    rc_agent = RemoteChatAgent(agent_dir=agents_root / "remote_chat", db=isolated_db)
    rc_agent.register_routes(router)
    rc_res = rc_agent.execute_task("poll_remote_chat_bridge")
    assert rc_res["status"] == "success"
    assert rc_agent.get_micro_widget()["agent_id"] == "remote_chat"

    sim_res = rc_agent.handle_incoming_message(
        channel="telegram",
        sender_id="owner_local",
        text="/status",
    )
    assert sim_res["status"] == "ok"
    assert sim_res["cost_usd"] == "$0.00"

    # 2. MCPStudioAgent (#4 Custom MCP Tool Creator UI)
    mcp_agent = MCPStudioAgent(agent_dir=agents_root / "mcp_studio", db=isolated_db)
    mcp_agent.register_routes(router)
    mcp_res = mcp_agent.execute_task("audit_custom_mcp_tools")
    assert mcp_res["status"] == "success"
    assert mcp_agent.get_micro_widget()["agent_id"] == "mcp_studio"

    tools = mcp_agent.list_mcp_tools()
    assert len(tools) >= 3
    created = mcp_agent.create_or_update_mcp_tool(
        {
            "name": "mcp_custom_ping",
            "description": "Returns ping health check.",
            "category": "DevOps",
            "response_template": "Pong from local MCP studio",
        }
    )
    assert created["status"] == "ok"
    tested = mcp_agent.test_mcp_tool("mcp_custom_ping", {"target": "localhost"})
    assert tested["status"] == "ok"

    # 3. LocalLLMAgent (#5 Local Ollama Offline LLM Fine-Tuning)
    llm_agent = LocalLLMAgent(agent_dir=agents_root / "local_llm", db=isolated_db)
    llm_agent.register_routes(router)
    llm_res = llm_agent.execute_task("sync_local_models")
    assert llm_res["status"] == "success"
    assert llm_agent.get_micro_widget()["agent_id"] == "local_llm"

    models_info = llm_agent.list_local_models()
    assert len(models_info["models"]) >= 3
    ds_res = llm_agent.build_personal_lora_dataset(max_samples=10)
    assert ds_res["status"] == "ok"
    assert ds_res["sample_count"] >= 1
    mf_res = llm_agent.generate_modelfile(
        base_model="llama3.2:3b",
        persona_name="offline-coach",
        system_prompt="Keep answers concise.",
    )
    assert mf_res["status"] == "ok"
    assert "FROM llama3.2:3b" in mf_res["modelfile_entry"]["modelfile"]
    gen_res = llm_agent.run_local_inference(prompt="Plan my afternoon deep work block")
    assert gen_res["status"] == "ok"
    assert gen_res["cost_usd"] == 0.0


def test_backlog_100_percent_completed(isolated_db):
    isolated_db.sync_ux_roadmap_backlog()
    stats = isolated_db.get_feature_backlog_stats()
    assert stats["total"] >= 57
    assert stats["completed"] >= 57
    assert (
        stats["completed"] + stats["planned"] + stats["idea"] + stats["in_progress"]
        == stats["total"]
    )


def test_ux06_to_ux10_settings_api_endpoints():
    from fleet.api.settings_api import (
        get_agent_undo_journal_endpoint,
        get_onboarding_state_endpoint,
        get_overview_micro_widgets_endpoint,
        get_smart_nudges_endpoint,
        get_tray_status_endpoint,
        post_pin_overview_widget_endpoint,
    )

    h1 = MagicMock()
    get_onboarding_state_endpoint(h1, urllib.parse.urlparse("/api/settings/onboarding"))
    assert "personas_catalog" in h1._send_json.call_args[0][0]

    h2 = MagicMock()
    get_smart_nudges_endpoint(h2, urllib.parse.urlparse("/api/notifications/nudges"))
    assert "focus" in h2._send_json.call_args[0][0]

    h3 = MagicMock()
    get_agent_undo_journal_endpoint(h3, urllib.parse.urlparse("/api/agents/undo?limit=5"))
    assert h3._send_json.call_args[0][0]["status"] == "ok"

    h4 = MagicMock()
    get_overview_micro_widgets_endpoint(h4, urllib.parse.urlparse("/api/overview/widgets"))
    assert h4._send_json.call_args[0][0]["status"] == "ok"

    h4_pin = MagicMock()
    post_pin_overview_widget_endpoint(h4_pin, {"agent_id": "health", "action": "pin"})
    assert h4_pin._send_json.call_args[0][0]["status"] == "ok"

    h5 = MagicMock()
    get_tray_status_endpoint(h5, urllib.parse.urlparse("/api/tray/status"))
    assert h5._send_json.call_args[0][0]["global_hotkey"] == "Alt+Space"


def test_jarvis_voice_brain_and_speaker_biometrics(isolated_db):
    from fleet.api.settings_api import (
        get_voiceprint_profile_endpoint,
        post_voiceprint_profile_endpoint,
    )
    from fleet.core.omnibar_dispatcher import _clean_for_speech, execute_voice_conversation_turn

    # 1. "Can you hear me?" -> Instant $0.00 Jarvis Presence Check
    res_hear = execute_voice_conversation_turn("Can you hear me?", language="en", gender="female", accent="IN")
    assert res_hear["mode"] == "jarvis_presence"
    assert res_hear["tokens_used"] == 0
    assert "Loud and clear" in res_hear["spoken_reply"]
    assert not res_hear["spoken_reply"].startswith("{")

    # 2. Phonetic distortion "crisis" with N-best alternatives=["crisis", "can you hear me"]
    res_alt = execute_voice_conversation_turn(
        "crisis",
        language="en",
        gender="female",
        accent="IN",
        alternatives=["crisis", "can you hear me"],
    )
    assert res_alt["selected_transcript"] == "can you hear me"
    assert res_alt["mode"] == "jarvis_presence"
    assert res_alt["tokens_used"] == 0

    # 3. Isolated background noise word "crisis" -> Ignored at $0.00 (0 tokens, empty spoken reply)
    res_noise = execute_voice_conversation_turn("crisis", language="en", gender="female", accent="IN")
    assert res_noise.get("ignored_noise") is True
    assert res_noise["tokens_used"] == 0
    assert res_noise["spoken_reply"] == ""

    # 4. Ask About All Agents ("What agents do I have?")
    res_roster = execute_voice_conversation_turn("What agents do I have?", language="en")
    assert res_roster["mode"] == "agent_roster"
    assert res_roster["tokens_used"] == 0
    assert "Health" in res_roster["message"]

    # 5. Ask About Specific Agent ("Tell me about the Health agent")
    res_health_info = execute_voice_conversation_turn("Tell me about the Health agent", language="en")
    assert res_health_info["mode"] == "agent_introspection"
    assert res_health_info["agent_id"] == "health"
    assert res_health_info["tokens_used"] == 0

    # 6. Recent Agent Activity ("What did my agents do recently?")
    res_activity = execute_voice_conversation_turn("What did my agents do recently?", language="en")
    assert res_activity["mode"] == "agent_activity_log"
    assert res_activity["tokens_used"] == 0

    # 7. Play Workout Video / Playlist by Voice
    res_video = execute_voice_conversation_turn("Play my workout playlist", language="en")
    assert res_video["mode"] == "voice_activity"
    assert any(a.get("type") == "play_video_by_voice" for a in res_video.get("ui_actions", []))

    # 8. Direct Antigravity Live Bridge ("Ask Antigravity to check database indexes")
    res_ag = execute_voice_conversation_turn("Ask Antigravity to check database indexes", language="en")
    assert res_ag["mode"] == "antigravity_direct"
    assert any(a.get("type") == "send_to_antigravity" for a in res_ag.get("ui_actions", []))

    # 9. Raw JSON Telemetry Shield in _clean_for_speech
    raw_json = '{"conversation_id":"eb079753-31f7-47f6-a188-72967eb956e5","status":"SUCCESS","response":"","usage":{"total_tokens":15320}}'
    cleaned_speech = _clean_for_speech(raw_json)
    assert not cleaned_speech.startswith("{")
    assert "conversation_id" not in cleaned_speech

    # 10. Biometric Speaker Voiceprint staging, audio file replay, and user confirmation gate
    from fleet.api.settings_api import get_voiceprint_audio_replay_endpoint
    import base64

    sample_wav_b64 = base64.b64encode(b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00").decode("ascii")
    sample_data_url = f"data:audio/wav;base64,{sample_wav_b64}"

    # Step 10a: Stage recorded voiceprint audio for replay BEFORE processing/enrolling
    h_stage = MagicMock()
    post_voiceprint_profile_endpoint(
        h_stage,
        {
            "profile": {"pitchMeanHz": 134, "pitchStdHz": 20, "centroidMeanHz": 1568},
            "audio_data_url": sample_data_url,
            "stage_only": True,
            "confirmed": False,
        },
    )
    stage_payload = h_stage._send_json.call_args[0][0]
    assert stage_payload["status"] == "staged_awaiting_confirmation"
    assert stage_payload["awaiting_confirmation"] is True
    assert stage_payload["confirmed"] is False
    assert stage_payload["audio_saved"] is True
    assert "voiceprint_sample.wav" in stage_payload["audio_file"]

    # Step 10b: Replay the saved voiceprint audio file
    h_audio = MagicMock(spec=["_send_json"])
    get_voiceprint_audio_replay_endpoint(h_audio, urllib.parse.urlparse("/api/voice/voiceprint/audio?format=json"))
    audio_payload = h_audio._send_json.call_args[0][0]
    assert audio_payload["status"] == "ok"
    assert audio_payload["audio_saved"] is True
    assert audio_payload["audio_data_url"] == sample_data_url

    # Step 10c: User confirms & processes the voiceprint
    h_post = MagicMock()
    post_voiceprint_profile_endpoint(
        h_post,
        {
            "profile": {"pitchMeanHz": 134, "pitchStdHz": 20, "centroidMeanHz": 1568},
            "audio_data_url": sample_data_url,
            "stage_only": False,
            "confirmed": True,
        },
    )
    assert h_post._send_json.call_args[0][0]["status"] == "ok"
    assert h_post._send_json.call_args[0][0]["confirmed"] is True
    assert h_post._send_json.call_args[0][0]["enrolled"] is True
    assert h_post._send_json.call_args[0][0]["audio_saved"] is True

    h_get = MagicMock()
    get_voiceprint_profile_endpoint(h_get, urllib.parse.urlparse("/api/voice/voiceprint"))
    assert h_get._send_json.call_args[0][0]["enrolled"] is True
    assert h_get._send_json.call_args[0][0]["profile"]["pitchMeanHz"] == 134
    assert h_get._send_json.call_args[0][0]["audio_saved"] is True
    assert h_get._send_json.call_args[0][0]["audio_url"] == "/api/voice/voiceprint/audio"


def test_local_tls_certificate_and_https_dual_stack():
    from fleet.core.local_tls import build_local_ssl_context, ensure_local_tls_certificates
    from fleet.server import ALLOWED_ORIGINS

    res = ensure_local_tls_certificates()
    assert res["status"] in ("existing", "generated")
    ctx = build_local_ssl_context()
    assert ctx is not None
    assert "https://127.0.0.1:7890" in ALLOWED_ORIGINS
    assert "https://localhost:7890" in ALLOWED_ORIGINS


def test_voice_action_items_conversational_engine(isolated_db):
    from fleet.core.omnibar_dispatcher import execute_voice_conversation_turn

    # Seed two realistic action items in isolated_db
    t1_id = isolated_db.add_task(
        title="Monthly — HDFC Credit Card Bill Payment",
        description="Pay monthly HDFC statement before the 5th.",
        priority="P2",
        source="Monthly",
    )
    t2_id = isolated_db.add_task(
        title="Monthly — Pay Electricity Bill",
        description="Pay Maharashtra MSEB consumer bill.",
        priority="P2",
        source="Monthly",
    )
    assert t1_id > 0 and t2_id > 0

    # 1. Start daily conversation on open action items
    r_open = execute_voice_conversation_turn("Mahadev, let's talk about my action items", db=isolated_db)
    assert r_open["mode"] == "voice_action_items_open_review"
    assert r_open["tokens_used"] == 0
    assert r_open["pending_count"] >= 2
    assert r_open["active_action_item"] is not None
    first_focused_id = r_open["active_action_item"]["id"]

    # 2. Step to next action item
    r_next = execute_voice_conversation_turn("Next action item", db=isolated_db)
    assert r_next["mode"] == "voice_action_item_step"
    assert r_next["active_action_item"]["id"] != first_focused_id

    # Step back to the Electricity Bill item so we edit Electricity Bill and keep HDFC Credit Card intact
    execute_voice_conversation_turn("Next action item", db=isolated_db)

    # 3. Edit focused action item title verbally ("Edit it to ...")
    r_edit = execute_voice_conversation_turn("Edit it to Monthly — Pay Pune Electricity Bill", db=isolated_db)
    assert r_edit["mode"] == "voice_task_edited"
    assert "Pay Pune Electricity Bill" in r_edit["active_action_item"]["title"]

    # 4. Change priority verbally ("Change priority of it to high priority")
    r_prio = execute_voice_conversation_turn("Change priority of it to high priority", db=isolated_db)
    assert r_prio["mode"] == "voice_task_edited"
    assert r_prio["active_action_item"]["priority"] == "P1"

    # 5. Add note verbally
    r_note = execute_voice_conversation_turn("Add note: Paid via BHIM UPI", db=isolated_db)
    assert r_note["mode"] == "voice_task_edited"
    assert "Paid via BHIM UPI" in r_note["active_action_item"]["description"]

    # 6. Close the focused action item using conversational pronoun ("Close it")
    r_close1 = execute_voice_conversation_turn("Close it", db=isolated_db)
    assert r_close1["mode"] == "voice_task_completed"
    assert r_close1["tokens_used"] == 0

    # 7. Close another action item by natural phrase ("I already closed the HDFC credit card action item")
    r_close2 = execute_voice_conversation_turn("I already closed the HDFC credit card action item", db=isolated_db)
    assert r_close2["mode"] == "voice_task_completed"
    assert r_close2["task_id"] == t1_id

    # 8. Talk with the voice cockpit about action items already closed
    r_closed_list = execute_voice_conversation_turn("What action items have I already closed?", db=isolated_db)
    assert r_closed_list["mode"] == "voice_action_items_closed_review"
    assert r_closed_list["closed_count"] >= 2
    assert "HDFC Credit Card" in r_closed_list["spoken_reply"] or "Electricity Bill" in r_closed_list["spoken_reply"]

    # 9. Reopen the focused closed action item verbally ("Reopen it")
    r_reopen = execute_voice_conversation_turn("Reopen it", db=isolated_db)
    assert r_reopen["mode"] == "voice_task_reopened"
    assert r_reopen["active_action_item"]["status"] == "pending"


def test_fine_12d_voiceprint_child_rejection_auto_refine_and_sandbox(isolated_db, monkeypatch):
    import urllib.parse
    import fleet.server as srv
    from fleet.api.settings_api import (
        auto_refine_voiceprint_profile,
        evaluate_speaker_biometric_match,
        get_voiceprint_profile_endpoint,
        post_verify_voiceprint_sandbox_endpoint,
        save_voiceprint_profile_endpoint,
    )

    monkeypatch.setattr(srv, "db", isolated_db)

    class _DummyHandler:
        def __init__(self):
            self.last_json: dict = {}
            self.last_status = 200

        def _send_json(self, data: dict, status: int = 200):
            self.last_json = data
            self.last_status = status

    # 1. Verify GET /api/voice/voiceprint returns 20s default, [10,12,15,20,25,30] durations, and 5-Phase Script
    h = _DummyHandler()
    get_voiceprint_profile_endpoint(h, urllib.parse.urlparse("/api/voice/voiceprint"))
    assert h.last_json["recommended_duration_sec"] == 20
    assert h.last_json["supported_durations_sec"] == [10, 12, 15, 20, 25, 30]
    assert len(h.last_json["calibration_script"]["phases"]) == 5

    # 2. Enroll a 12-D adult owner voiceprint profile
    owner_profile = {
        "pitchMeanHz": 134,
        "pitchStdHz": 14,
        "pitchMinHz": 112,
        "pitchMaxHz": 165,
        "centroidMeanHz": 1240,
        "f1MeanHz": 485,
        "f2MeanHz": 1475,
        "f3MeanHz": 2560,
        "vtlCm": 17.1,
        "chestResonanceRatio": 1.42,
        "rolloffMeanHz": 2320,
        "subBandVector": [0.42, 0.48, 0.39, 0.35, 0.31, 0.28, 0.22, 0.16],
        "strictnessThreshold": 78,
        "autoRefineEnabled": True,
        "autoRefinementCount": 0,
        "durationSec": 20,
    }
    save_voiceprint_profile_endpoint(h, {"profile": owner_profile, "confirmed": True})
    assert h.last_json["enrolled"] is True

    # 3. Direct 12-D evaluation: Owner voice sample MUST be ACCEPTED (>= 85%)
    owner_sample = {
        "pitchMeanHz": 136,
        "centroidMeanHz": 1225,
        "f1MeanHz": 492,
        "f2MeanHz": 1460,
        "f3MeanHz": 2580,
        "vtlCm": 17.0,
        "chestResonanceRatio": 1.38,
        "rolloffMeanHz": 2345,
        "subBandVector": [0.41, 0.47, 0.40, 0.35, 0.31, 0.28, 0.23, 0.16],
    }
    owner_eval = evaluate_speaker_biometric_match(owner_profile, owner_sample, strictness_threshold=78)
    assert owner_eval["allowed"] is True
    assert owner_eval["verdict"] == "AUTHORIZED_OWNER"
    assert owner_eval["match_pct"] >= 85
    assert owner_eval["is_child_or_octave_impostor"] is False

    # 4. Direct 12-D evaluation: Child voice sample (268 Hz, VTL 12.1 cm, Chest 0.42x) MUST be REJECTED (< 45%)
    child_sample = {
        "pitchMeanHz": 268,
        "centroidMeanHz": 1940,
        "f1MeanHz": 710,
        "f2MeanHz": 2120,
        "f3MeanHz": 3340,
        "vtlCm": 12.1,
        "chestResonanceRatio": 0.42,
        "rolloffMeanHz": 3180,
        "subBandVector": [0.14, 0.21, 0.34, 0.46, 0.49, 0.42, 0.33, 0.28],
    }
    child_eval = evaluate_speaker_biometric_match(owner_profile, child_sample, strictness_threshold=78)
    assert child_eval["allowed"] is False
    assert child_eval["is_child_or_octave_impostor"] is True
    assert child_eval["verdict"] == "REJECTED_IMPOSTOR_OR_CHILD"
    assert child_eval["match_pct"] <= 42

    # 5. Sandbox endpoint POST /api/voice/voiceprint/verify tracks accuracy & auto-refines on owner match
    post_verify_voiceprint_sandbox_endpoint(
        h,
        {
            "candidate": owner_sample,
            "expected_role": "owner",
            "label": "Owner Live Test",
            "auto_refine_if_matched": True,
        },
    )
    assert h.last_json["verification"]["allowed"] is True
    assert h.last_json["auto_refined"] is True
    assert h.last_json["profile"]["autoRefinementCount"] == 1

    post_verify_voiceprint_sandbox_endpoint(
        h,
        {
            "candidate": child_sample,
            "expected_role": "child",
            "label": "Child Impostor Test",
            "auto_refine_if_matched": False,
        },
    )
    assert h.last_json["verification"]["allowed"] is False
    metrics = h.last_json["sandbox_metrics"]
    assert metrics["total_tests"] == 2
    assert metrics["owner_acceptance_rate_pct"] == 100
    assert metrics["impostor_rejection_rate_pct"] == 100
    assert metrics["overall_accuracy_pct"] == 100

    # 6. Negative feedback ("Not Me") tightens boundary threshold and narrows pitchStdHz
    tightened = auto_refine_voiceprint_profile(owner_profile, child_sample, negative_feedback=True)
    assert tightened["strictnessThreshold"] == 80
    assert tightened["pitchStdHz"] < owner_profile["pitchStdHz"]


def test_lets_discuss_action_items_across_routing_modes_and_107hz_voiceprint(isolated_db):
    from pathlib import Path
    from fleet.api.settings_api import evaluate_speaker_biometric_match
    from fleet.core.omnibar_dispatcher import execute_voice_conversation_turn

    # Seed realistic open action items
    t1 = isolated_db.add_task(
        title="Monthly — Pay Electricity Bill",
        description="Pay MSEB bill before due date.",
        priority="P1",
        source="Monthly",
    )
    t2 = isolated_db.add_task(
        title="Review Quarterly Investment Portfolio",
        description="Rebalance equity and debt allocation.",
        priority="P2",
        source="Manual",
    )
    assert t1 > 0 and t2 > 0

    # 1. Exact user phrase "Let's discuss action items" (without wake word) when Brain Target is "antigravity"
    # MUST execute the Action Items review conversation and speak back the items aloud (NOT hijack to @antigravity)
    res_discuss = execute_voice_conversation_turn(
        "Let's discuss action items",
        db=isolated_db,
        language="en",
        gender="female",
        accent="IN",
        routing_mode="antigravity",
    )
    assert res_discuss["status"] == "ok"
    assert res_discuss["mode"] == "voice_action_items_open_review"
    assert res_discuss["pending_count"] >= 2
    assert res_discuss["active_action_item"] is not None
    assert "open action items" in res_discuss["spoken_reply"].lower()

    # 2. Follow-up conversational turns ("Next action item", "Close it") in routing_mode="antigravity"
    res_next = execute_voice_conversation_turn(
        "Next action item",
        db=isolated_db,
        routing_mode="antigravity",
    )
    assert res_next["mode"] == "voice_action_item_step"
    assert "action item" in res_next["spoken_reply"].lower()

    res_close = execute_voice_conversation_turn(
        "Close it",
        db=isolated_db,
        routing_mode="antigravity",
    )
    assert res_close["mode"] == "voice_task_completed"
    assert "closed" in res_close["spoken_reply"].lower()

    # 3. Explicit "Ask Antigravity to ..." still routes to Antigravity Live Console
    res_ag = execute_voice_conversation_turn(
        "Ask Antigravity to analyze my system architecture",
        db=isolated_db,
        routing_mode="antigravity",
    )
    assert res_ag["mode"] == "antigravity_direct"

    # 4. 107 Hz / 18.81 cm Adult Male Voiceprint speaking "Let's discuss action items" with natural 148 Hz inflection
    profile_107hz = {
        "pitchMeanHz": 107,
        "pitchStdHz": 15,
        "pitchMinHz": 88,
        "pitchMaxHz": 135,
        "centroidMeanHz": 1180,
        "f1MeanHz": 465,
        "f2MeanHz": 1410,
        "f3MeanHz": 2480,
        "vtlCm": 18.81,
        "chestResonanceRatio": 1.42,
        "rolloffMeanHz": 2250,
        "subBandVector": [0.44, 0.48, 0.39, 0.34, 0.30, 0.26, 0.21, 0.15],
        "strictnessThreshold": 78,
    }
    inflected_owner_utt = {
        "pitchMeanHz": 148,
        "centroidMeanHz": 1245,
        "f1MeanHz": 480,
        "f2MeanHz": 1440,
        "f3MeanHz": 2510,
        "vtlCm": 18.35,
        "chestResonanceRatio": 1.31,
        "rolloffMeanHz": 2340,
        "subBandVector": [0.42, 0.47, 0.40, 0.35, 0.31, 0.27, 0.22, 0.16],
    }
    eval_inflected = evaluate_speaker_biometric_match(profile_107hz, inflected_owner_utt, strictness_threshold=78)
    assert eval_inflected["allowed"] is True
    assert eval_inflected["verdict"] == "AUTHORIZED_OWNER"
    assert eval_inflected["is_child_or_octave_impostor"] is False

    # 5. Verify JS client guards in antigravity.js (isExplicitJarvisCommandPhrase, lastInterimTranscript, TTS watchdog)
    js_src = Path("fleet/web/static/js/antigravity.js").read_text(encoding="utf-8")
    assert "function isExplicitJarvisCommandPhrase(" in js_src
    assert "lastInterimTranscript" in js_src
    assert "sameVocalTractOwner" in js_src
    assert "if (!/^en/i.test(vLang))" in js_src


def test_open_source_licenses_are_100_percent_commercial_safe():
    from pathlib import Path

    pyproject_txt = Path("pyproject.toml").read_text(encoding="utf-8")
    notice_txt = Path("NOTICE").read_text(encoding="utf-8")
    third_party_txt = Path("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    # 1. Core runtime must remain zero mandatory dependencies
    assert "dependencies = []" in pyproject_txt

    # 2. Ensure zero copyleft (LGPL / GPL / AGPL / SSPL) packages in pyproject.toml or NOTICE
    banned_copyleft_packages = ["pygame-ce", "pyqt5", "pyqt6", "pyside2", "pyside6", "gpl", "lgpl", "agpl", "sspl"]
    for banned in banned_copyleft_packages:
        assert banned not in pyproject_txt.lower(), f"Restricted/copyleft dependency '{banned}' found in pyproject.toml"
    assert "lgpl-2.1" not in notice_txt.lower()
    assert "Commercial & End-User Safety Guarantee" in third_party_txt






