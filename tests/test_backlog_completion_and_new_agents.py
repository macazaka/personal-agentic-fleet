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

    # 10. Biometric Speaker Voiceprint persistence endpoints
    h_post = MagicMock()
    post_voiceprint_profile_endpoint(
        h_post,
        {"profile": {"pitchMeanHz": 148, "pitchStdHz": 22, "centroidMeanHz": 1180}},
    )
    assert h_post._send_json.call_args[0][0]["status"] == "ok"
    assert h_post._send_json.call_args[0][0]["enrolled"] is True

    h_get = MagicMock()
    get_voiceprint_profile_endpoint(h_get, urllib.parse.urlparse("/api/voice/voiceprint"))
    assert h_get._send_json.call_args[0][0]["enrolled"] is True
    assert h_get._send_json.call_args[0][0]["profile"]["pitchMeanHz"] == 148


def test_local_tls_certificate_and_https_dual_stack():
    from fleet.core.local_tls import build_local_ssl_context, ensure_local_tls_certificates
    from fleet.server import ALLOWED_ORIGINS

    res = ensure_local_tls_certificates()
    assert res["status"] in ("existing", "generated")
    ctx = build_local_ssl_context()
    assert ctx is not None
    assert "https://127.0.0.1:7890" in ALLOWED_ORIGINS
    assert "https://localhost:7890" in ALLOWED_ORIGINS


