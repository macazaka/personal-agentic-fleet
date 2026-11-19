"""
Comprehensive End-to-End Unit & Regression Test Suite for J.A.R.V.I.S. Voice Cockpit.

Covers every J.A.R.V.I.S. subsystem and guards against all historical failure modes:
  1. API Route Registration Parity & Stale Port Eviction (`/api/voice/stream`, `/api/voice/converse`, etc.)
  2. Live News & City Updates (`"tell me today's news"`, `"tell me about latest updates of Pune"`) in both
     Test Mode and simulated Production Mode (`is_test_environment() == False` with mocked RSS XML & cache eviction)
  3. Automatic Zero-Token Jarvis -> Antigravity Live Fallback (both open-ended factual/world questions and engineering directives)
  4. Full Action-Item Conversational Lifecycle (Open Review, Next/Prev, Details, Edit, Priority, Note, UPI Pay, Close, Closed Review, Reopen)
  5. Multi-Question & Multi-Intent Decomposition, Priority Ordering (`P0=95` -> `P1=80` -> `P2=65` -> `P3=50`),
     Explicit Ordinal Preservation (`"First ..., second ..."`), and Stateful Chain Preservation (`"Close it and next action item"`)
  6. Human-Like Conversational Topic Stack: Interrupt Priority Arbitration, Auto-Resume Bridge (single & multi-part interrupts),
     Explicit Deferred Topic Parking (`"After this, ..."`), and Explicit Topic Resumption (`"Resume parked topic"`)
  7. 12-D Acoustic Biometric Speaker Verification (`evaluate_speaker_biometric_match`), Adult Conversational Inflection Tolerance,
     Strict Child/High-Pitch Impostor Rejection, and EMA Auto-Refinement
  8. Multilingual Normalization & Voice Localization (`en`, `hi`, `te`, `mr`, `IN`/`US`/`GB`, `female`/`male`),
     N-Best ASR Alternative Scoring, and Single-Word Background Noise Shield
  9. All Voice Macros (`Good morning`, `Start my workout`, `Wrap up my day`) & Linked Agent Activities
     (Hydration, Weight, Glucose, Workout Video, PC Auto-Tune, RAM/Temp/DNS, Security Scan, Email/Antivirus, Backlog, Theme)
 10. Frontend & Laptop Hardware Constraint Guardrails in `antigravity.js` & `dashboard.html`
     (Hot-mic barge-in 1100ms grace window, short-burst 2500ms suppression, 15-min client cache, `/api/voice/stream` -> `/api/voice/converse`
      fallback, zero-GC `_SHARED_NSDF_BUF`, silence short-circuit, and sequential audio queue player)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent / "fleet"


@pytest.fixture
def isolated_db(tmp_path):
    """Provides a fast, isolated SQLite database in tmp_path so tests never touch production data."""
    from fleet.core.database import FleetDatabase

    db_file = tmp_path / "test_jarvis_isolated.db"
    return FleetDatabase(db_path=db_file)


# =========================================================================
# 1. Route Registration Parity & Server Port Eviction Invariants
# =========================================================================
def test_jarvis_route_registration_parity_and_stale_port_eviction(isolated_db, monkeypatch):
    import urllib.parse
    import fleet.server as srv
    from fleet.api.router import router
    from fleet.api.settings_api import get_voice_action_items_endpoint

    monkeypatch.setattr(srv, "db", isolated_db)
    isolated_db.add_task(title="Test Action Item Cache", description="Verify /api/voice/action_items", priority="P1")

    required_post_routes = (
        "/api/voice/converse",
        "/api/voice/stream",
        "/api/voice/voiceprint",
        "/api/voice/voiceprint/verify",
        "/api/omnibar/voice",
    )
    required_get_routes = (
        "/api/voice/activities",
        "/api/voice/action_items",
        "/api/voice/voiceprint",
        "/api/voice/voiceprint/audio",
    )
    for route_path in required_post_routes:
        assert route_path in router.post_routes, f"Missing POST route {route_path} in ApiRouter"
    for route_path in required_get_routes:
        assert route_path in router.get_routes, f"Missing GET route {route_path} in ApiRouter"

    assert hasattr(srv, "_evict_stale_port_listener"), "Missing _evict_stale_port_listener in fleet.server"

    # Verify GET /api/voice/action_items?status=all returns open & closed items for the <15ms client reflex cache
    h_act = MagicMock()
    get_voice_action_items_endpoint(h_act, urllib.parse.urlparse("/api/voice/action_items?status=all"))
    act_payload = h_act._send_json.call_args[0][0]
    assert act_payload["status"] == "ok"
    assert act_payload["open_count"] >= 1
    assert len(act_payload["items"]) >= 1


# =========================================================================
# 2. Live News & City Updates (Test Mode + Simulated Production RSS XML Mode)
# =========================================================================
def test_jarvis_live_news_and_pune_updates_in_test_and_production_rss_modes(isolated_db, monkeypatch):
    import urllib.request
    import fleet.server as srv
    import fleet.core.database as db_mod
    import fleet.core.omnibar_dispatcher as disp
    from fleet.api.settings_api import post_voice_stream_endpoint

    monkeypatch.setattr(srv, "db", isolated_db)
    disp._LIVE_NEWS_CACHE.clear()
    disp.reset_voice_topic_stack()

    # 2A. Test-mode offline fallback for "Tell me today's news" and "Tell me about latest updates of Pune"
    h1 = MagicMock()
    post_voice_stream_endpoint(h1, {"transcript": "Tell me today's news", "concise_mode": False})
    p1 = h1._send_json.call_args[0][0]
    assert p1["status"] == "ok"
    assert p1["mode"] == "voice_live_news_digest"
    assert len(p1["headlines"]) >= 2
    assert "Today's Top Headlines" in p1["topic"]

    h2 = MagicMock()
    post_voice_stream_endpoint(h2, {"transcript": "Tell me about latest updates of Pune", "concise_mode": True})
    p2 = h2._send_json.call_args[0][0]
    assert p2["status"] == "ok"
    assert p2["mode"] == "voice_live_news_digest"
    assert "Pune" in p2["topic"]
    assert "Pune" in p2["spoken_reply"]
    assert "Pune" in p2["spoken_reply_concise"]

    # 2B. Simulated Production Mode (`is_test_environment() == False` and `FLEET_TEST_MODE` unset)
    # Verifies the exact live XML RSS parsing & bounded 16-entry cache branch without hitting real network sockets.
    sample_rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Google News - Pune</title>
        <item>
          <title>Pune Metro Line 3 Hinjawadi corridor completes key trial run - Times of India</title>
          <source>Times of India</source>
        </item>
        <item>
          <title>Pune IT Park expansion adds 15,000 new engineering roles in Kharadi - Indian Express</title>
          <source>Indian Express</source>
        </item>
        <item>
          <title>IMD forecasts pleasant morning weather across Pune city - Hindustan Times</title>
          <source>Hindustan Times</source>
        </item>
      </channel>
    </rss>"""

    class _DummyRssResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, max_bytes=262144):
            return sample_rss_xml

    monkeypatch.setattr(db_mod, "is_test_environment", lambda: False)
    monkeypatch.delenv("FLEET_TEST_MODE", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=1.8: _DummyRssResponse())

    disp._LIVE_NEWS_CACHE.clear()
    live_digest = disp._fetch_live_news_and_web_digest("Pune latest news updates", "Pune")
    assert live_digest["source_mode"] == "live_web_rss"
    assert len(live_digest["headlines"]) == 3
    assert "Pune Metro Line 3" in live_digest["headlines"][0]["title"]
    assert live_digest["headlines"][0]["source"] == "Times of India"
    assert "Times of India" not in live_digest["headlines"][0]["title"]  # Trailing " - Source" stripped cleanly

    # Second call hits the 10-minute bounded in-memory cache (`live_cache`) in 0ms
    cached_digest = disp._fetch_live_news_and_web_digest("Pune latest news updates", "Pune")
    assert cached_digest["source_mode"] == "live_cache"
    assert cached_digest["headlines"] == live_digest["headlines"]

    # Verify bounded cache ring buffer eviction (`_MAX_NEWS_CACHE_ENTRIES = 16`)
    for idx in range(22):
        disp._fetch_live_news_and_web_digest(f"topic_{idx}", f"Topic {idx}")
    assert len(disp._LIVE_NEWS_CACHE) <= disp._MAX_NEWS_CACHE_ENTRIES


# =========================================================================
# 3. Automatic Zero-Token Jarvis -> Antigravity Live Fallback
# =========================================================================
def test_jarvis_automatic_fallback_to_antigravity_live(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import post_voice_converse_endpoint
    from fleet.core.omnibar_dispatcher import reset_voice_topic_stack

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()

    # 3A. Open-ended engineering directive not handled by deterministic zero-token rules
    h_eng = MagicMock()
    post_voice_converse_endpoint(
        h_eng,
        {"transcript": "Architect a zero-downtime blue-green deployment pipeline for billing"},
    )
    eng_res = h_eng._send_json.call_args[0][0]
    assert eng_res["status"] == "ok"
    assert eng_res["mode"] == "antigravity_auto_fallback"
    assert eng_res["escalated_to_antigravity"] is True
    assert "Antigravity Live" in eng_res["spoken_reply"]
    assert any(a.get("type") == "send_to_antigravity" for a in eng_res.get("ui_actions", []))

    # 3B. Open-ended factual/world question ("Tell me about quantum computing breakthroughs")
    # Scrapes web/news context AND escalates to Antigravity Live
    h_fact = MagicMock()
    post_voice_converse_endpoint(
        h_fact,
        {"transcript": "Tell me about quantum computing breakthroughs"},
    )
    fact_res = h_fact._send_json.call_args[0][0]
    assert fact_res["status"] == "ok"
    assert fact_res["mode"] == "antigravity_auto_fallback"
    assert fact_res["escalated_to_antigravity"] is True
    assert "Antigravity Live" in fact_res["spoken_reply"]

    # 3C. Explicit "Ask Antigravity to ..." bridge
    h_direct = MagicMock()
    post_voice_converse_endpoint(
        h_direct,
        {"transcript": "Ask Antigravity to review my database schema"},
    )
    dir_res = h_direct._send_json.call_args[0][0]
    assert dir_res["status"] == "ok"
    assert dir_res["mode"] == "antigravity_direct"
    assert any(a.get("type") == "send_to_antigravity" for a in dir_res.get("ui_actions", []))


# =========================================================================
# 4. Full Action-Item Conversational Lifecycle & 1-Word Contextual Follow-Ups
# =========================================================================
def test_jarvis_full_action_items_conversational_lifecycle(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import post_voice_converse_endpoint, post_voice_stream_endpoint
    from fleet.core.omnibar_dispatcher import reset_voice_topic_stack

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()

    t1 = isolated_db.add_task(
        title="Monthly — Pay Pune Electricity Bill",
        description="MSEB consumer 123456789012 due on 25th",
        priority="P2",
        source="Monthly",
    )
    t2 = isolated_db.add_task(
        title="Yearly — Renew Health Insurance Policy",
        description="Annual family floater renewal",
        priority="P1",
        source="Yearly",
    )

    def _ask(phrase: str, stream: bool = True):
        h = MagicMock()
        if stream:
            post_voice_stream_endpoint(h, {"transcript": phrase, "concise_mode": True})
        else:
            post_voice_converse_endpoint(h, {"transcript": phrase, "concise_mode": True})
        return h._send_json.call_args[0][0]

    # 1. Start open action items review ("let's discuss action items")
    r_open = _ask("let's discuss action items")
    assert r_open["status"] == "ok"
    assert r_open["mode"] == "voice_action_items_open_review"
    assert r_open["pending_count"] == 2
    assert r_open["active_action_item"]["id"] in (t1, t2)
    assert len(r_open["spoken_stream_clauses"]) >= 2

    # 2. 1-word contextual follow-up: "Details"
    r_det = _ask("Details")
    assert r_det["mode"] == "voice_action_item_details"
    assert r_det["active_action_item"]["id"] == r_open["active_action_item"]["id"]

    # 3. Step to next and previous action items
    r_next = _ask("Next action item")
    assert r_next["mode"] == "voice_action_item_step"
    second_id = r_next["active_action_item"]["id"]
    assert second_id != r_open["active_action_item"]["id"]

    r_prev = _ask("Previous action item")
    assert r_prev["mode"] == "voice_action_item_step"
    assert r_prev["active_action_item"]["id"] == r_open["active_action_item"]["id"]

    # 4. In-place edit title, priority, and note (must NEVER be overwritten by stale parked_item)
    r_edit = _ask("Edit it to Monthly — Pay Maharashtra Electricity Bill")
    assert r_edit["mode"] == "voice_task_edited"
    assert "Pay Maharashtra Electricity Bill" in r_edit["active_action_item"]["title"]

    r_prio = _ask("Change priority of it to high priority")
    assert r_prio["mode"] == "voice_task_edited"
    assert r_prio["active_action_item"]["priority"] == "P1"

    r_note = _ask("Add note: Paid via BHIM UPI")
    assert r_note["mode"] == "voice_task_edited"
    assert "Paid via BHIM UPI" in r_note["active_action_item"]["description"]

    # 5. 1-word UPI payment trigger ("Pay")
    r_upi = _ask("Pay")
    assert r_upi["mode"] == "voice_action_item_upi_pay"

    # 6. 1-word completion ("Done") -> closes item 1 and auto-advances focus to remaining item 2
    r_done = _ask("Done")
    assert r_done["mode"] == "voice_task_completed"
    assert r_done["active_action_item"]["id"] == second_id

    # 7. Close the second item ("Close it") -> queue complete
    r_close2 = _ask("Close it")
    assert r_close2["mode"] == "voice_task_completed"
    assert r_close2.get("active_action_item") is None

    # 8. Review closed action items & reopen via 1-word follow-up ("Reopen")
    r_closed = _ask("What action items have I already closed?")
    assert r_closed["mode"] == "voice_action_items_closed_review"
    assert r_closed["closed_count"] == 2
    assert r_closed["active_action_item"] is not None

    r_reopen = _ask("Reopen")
    assert r_reopen["mode"] == "voice_task_reopened"


# =========================================================================
# 5. Multi-Question Decomposition, Priority Ordering & Ordinal Preservation
# =========================================================================
def test_jarvis_multi_question_decomposition_priority_and_ordinals(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import post_voice_stream_endpoint
    from fleet.core.omnibar_dispatcher import reset_voice_topic_stack

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()
    isolated_db.add_task(title="Review Sprint Goals", description="Q4 planning", priority="P1")

    # 5A. Unordered multi-question + action utterance:
    # "Let's discuss action items? Also tell me about latest updates of Pune. And please log a glass of water."
    # Priority Arbitrator sorts P0 (Water=95) -> P1 (Pune News=80) -> P2 (Action Items=65)
    h_prio = MagicMock()
    post_voice_stream_endpoint(
        h_prio,
        {
            "transcript": "Let's discuss action items? Also tell me about latest updates of Pune. And please log a glass of water.",
            "concise_mode": True,
        },
    )
    prio_res = h_prio._send_json.call_args[0][0]
    assert prio_res["status"] == "ok"
    assert prio_res["mode"] == "voice_chained_multi_command"
    assert prio_res["chained_commands_count"] == 3
    assert prio_res["priority_reordered"] is True
    q_items = prio_res["voice_queue_items"]
    assert [item["priority_score"] for item in q_items] == [95, 80, 65]
    assert [item["part_index"] for item in q_items] == [1, 2, 3]
    assert all(item["total_parts"] == 3 for item in q_items)

    # 5B. Explicit user ordinals ("First tell me today's news, second log a glass of water")
    # Must preserve the exact user-specified order (`priority_reordered is False`)
    reset_voice_topic_stack()
    h_ord = MagicMock()
    post_voice_stream_endpoint(
        h_ord,
        {
            "transcript": "First tell me today's news, second log a glass of water",
            "concise_mode": True,
        },
    )
    ord_res = h_ord._send_json.call_args[0][0]
    assert ord_res["status"] == "ok"
    assert ord_res["mode"] == "voice_chained_multi_command"
    assert ord_res["priority_reordered"] is False
    ord_items = ord_res["voice_queue_items"]
    assert len(ord_items) == 2
    assert ord_items[0]["topic_id"] == "live_news_bulletin"
    assert ord_items[1]["topic_id"] == "health_hydration"


# =========================================================================
# 6. Human-Like Conversational Topic Stack: Single & Multi-Part Interrupts, Park & Resume
# =========================================================================
def test_jarvis_human_conversational_topic_stack_interrupt_and_resume(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.api.settings_api import post_voice_converse_endpoint, post_voice_stream_endpoint
    from fleet.core.omnibar_dispatcher import reset_voice_topic_stack

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()
    t_id = isolated_db.add_task(title="Pay Property Tax", description="PMC property tax", priority="P1")
    isolated_db.add_task(title="File GST Return", description="Monthly filing", priority="P2")

    # Step 1: Start multi-turn Action Items conversation (focuses #t_id)
    h_start = MagicMock()
    post_voice_stream_endpoint(h_start, {"transcript": "Let's discuss action items", "concise_mode": True})
    start_res = h_start._send_json.call_args[0][0]
    assert start_res["active_action_item"]["id"] == t_id
    assert start_res["topic_stack"]["active_topic"]["topic_id"] == "action_items_review"

    # Step 2: Interrupt mid-conversation with a single higher-priority topic ("Tell me about latest updates of Pune")
    h_int1 = MagicMock()
    post_voice_stream_endpoint(h_int1, {"transcript": "Tell me about latest updates of Pune", "concise_mode": True})
    int1_res = h_int1._send_json.call_args[0][0]
    assert int1_res["topic_interrupted_and_resumed"] is True
    assert int1_res["arbitration_decision"] == "interrupted_by_higher_priority_topic_then_auto_resumed"
    assert len(int1_res["voice_queue_items"]) == 2
    assert int1_res["voice_queue_items"][0]["is_auto_resume"] is False
    assert "Pune" in int1_res["voice_queue_items"][0]["spoken_reply"]
    assert int1_res["voice_queue_items"][1]["is_auto_resume"] is True
    assert "Pay Property Tax" in int1_res["voice_queue_items"][1]["spoken_reply"]
    assert int1_res["active_action_item"]["id"] == t_id

    # Step 3: Interrupt mid-conversation with a 2-part multi-command ("Log a glass of water and optimize my RAM")
    # Should produce 3 queued audio messages: Part 1 (Water), Part 2 (RAM), Part 3 (Auto-Resume Action Item #t_id)
    h_int2 = MagicMock()
    post_voice_stream_endpoint(
        h_int2,
        {"transcript": "Please log a glass of water and optimize my RAM", "concise_mode": True},
    )
    int2_res = h_int2._send_json.call_args[0][0]
    assert int2_res["arbitration_decision"] == "parked_ongoing_topic_and_auto_resumed_after_queue"
    assert len(int2_res["voice_queue_items"]) == 3
    assert int2_res["voice_queue_items"][0]["is_auto_resume"] is False
    assert int2_res["voice_queue_items"][1]["is_auto_resume"] is False
    assert int2_res["voice_queue_items"][2]["is_auto_resume"] is True
    assert int2_res["active_action_item"]["id"] == t_id

    # Step 4: Explicitly defer a topic for later ("After this, tell me today's news")
    h_defer = MagicMock()
    post_voice_converse_endpoint(h_defer, {"transcript": "After this, tell me today's news"})
    defer_res = h_defer._send_json.call_args[0][0]
    assert defer_res["mode"] == "voice_topic_parked"
    assert defer_res["topic_stack"]["parked_count"] >= 1

    # Step 5: Resume the parked topic via natural voice phrase ("What did we park?")
    h_res = MagicMock()
    post_voice_converse_endpoint(h_res, {"transcript": "What did we park?"})
    res_payload = h_res._send_json.call_args[0][0]
    assert res_payload["mode"] == "voice_topic_resumed"
    assert "Headlines" in res_payload["title"] or "News" in res_payload["title"]


# =========================================================================
# 7. 12-D Biometric Speaker Verification, Adult Inflection & Child/Impostor Rejection
# =========================================================================
def test_jarvis_12d_biometric_speaker_verification_and_ema_refinement():
    from fleet.api.settings_api import (
        auto_refine_voiceprint_profile,
        evaluate_speaker_biometric_match,
    )

    enrolled_owner = {
        "pitchMeanHz": 107,
        "pitchStdHz": 14,
        "pitchMinHz": 90,
        "pitchMaxHz": 135,
        "centroidMeanHz": 1220,
        "f1MeanHz": 480,
        "f2MeanHz": 1460,
        "f3MeanHz": 2540,
        "vtlCm": 17.4,
        "chestResonanceRatio": 1.45,
        "rolloffMeanHz": 2300,
        "subBandVector": [0.44, 0.47, 0.38, 0.35, 0.30, 0.27, 0.21, 0.16],
        "strictnessThreshold": 78,
    }

    # 7A. Enrolled owner speaking with natural conversational inflection (107Hz -> 146Hz, same vocal tract 17.2cm)
    owner_inflected = {
        "pitchMeanHz": 146,
        "centroidMeanHz": 1265,
        "f1MeanHz": 492,
        "f2MeanHz": 1490,
        "f3MeanHz": 2580,
        "vtlCm": 17.2,
        "chestResonanceRatio": 1.36,
        "rolloffMeanHz": 2360,
        "subBandVector": [0.43, 0.46, 0.39, 0.35, 0.31, 0.27, 0.22, 0.16],
    }
    res_owner = evaluate_speaker_biometric_match(enrolled_owner, owner_inflected, strictness_threshold=78)
    assert res_owner["allowed"] is True
    assert res_owner["verdict"] == "AUTHORIZED_OWNER"
    assert res_owner["is_child_or_octave_impostor"] is False

    # 7B. Child voice (268Hz, VTL 12.1cm, chest 0.42x) -> Strictly rejected
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
    res_child = evaluate_speaker_biometric_match(enrolled_owner, child_sample, strictness_threshold=78)
    assert res_child["allowed"] is False
    assert res_child["verdict"] == "REJECTED_IMPOSTOR_OR_CHILD"
    assert res_child["is_child_or_octave_impostor"] is True

    # 7C. Unvoiced / silent sample (pitchMeanHz = 0) -> Rejected cleanly
    res_silent = evaluate_speaker_biometric_match(enrolled_owner, {"pitchMeanHz": 0}, strictness_threshold=78)
    assert res_silent["allowed"] is False
    assert res_silent["verdict"] == "REJECTED_NO_VOICE"

    # 7D. Positive EMA Auto-Refinement & Negative Boundary Tightening
    refined = auto_refine_voiceprint_profile(enrolled_owner, {"pitchMeanHz": 115, "vtlCm": 17.3}, learning_rate=0.10)
    assert refined["autoRefinementCount"] == 1
    assert 107 <= refined["pitchMeanHz"] <= 115

    tightened = auto_refine_voiceprint_profile(enrolled_owner, {}, negative_feedback=True)
    assert tightened["strictnessThreshold"] == 80
    assert tightened["pitchStdHz"] < enrolled_owner["pitchStdHz"]


# =========================================================================
# 8. Multilingual Normalization (`en`, `hi`, `te`, `mr`), N-Best ASR & Noise Shield
# =========================================================================
def test_jarvis_multilingual_localization_nbest_scoring_and_noise_gate(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.core.omnibar_dispatcher import (
        reset_voice_topic_stack,
        transcribe_and_dispatch_voice_command,
    )

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()

    # 8A. N-Best alternative selection picks actionable command over acoustic noise word
    res_nbest = transcribe_and_dispatch_voice_command(
        transcript="crisis",
        alternatives=["crisis", "let's discuss action items"],
        db=isolated_db,
    )
    assert res_nbest["mode"] == "voice_action_items_open_review"
    assert res_nbest["selected_transcript"] == "let's discuss action items"

    # 8B. Isolated single-word background noise ("crisis") is filtered at $0.00 with empty spoken_reply
    res_noise = transcribe_and_dispatch_voice_command(
        transcript="crisis",
        alternatives=["crisis"],
        db=isolated_db,
    )
    assert res_noise.get("ignored_noise") is True
    assert res_noise["spoken_reply"] == ""

    # 8C. Hindi, Telugu, and Marathi voice localization & phonetic fallback generation
    for lang_code, expected_bcp47 in (("hi", "hi-IN"), ("te", "te-IN"), ("mr", "mr-IN"), ("en", "en-IN")):
        res_loc = transcribe_and_dispatch_voice_command(
            transcript="Please log a glass of water",
            db=isolated_db,
            language=lang_code,
            gender="female",
            accent="IN",
        )
        assert res_loc["status"] == "ok"
        assert res_loc["voice_profile"]["bcp47"] == expected_bcp47
        assert len(res_loc["spoken_reply"]) > 10
        assert len(res_loc["spoken_reply_phonetic"]) > 10


# =========================================================================
# 9. All Built-In Voice Macros & Linked Agent Activities Coverage
# =========================================================================
def test_jarvis_all_voice_macros_and_agent_activities(isolated_db, monkeypatch):
    import fleet.server as srv
    from fleet.core.omnibar_dispatcher import (
        reset_voice_topic_stack,
        transcribe_and_dispatch_voice_command,
    )

    monkeypatch.setattr(srv, "db", isolated_db)
    reset_voice_topic_stack()
    isolated_db.add_task(title="Verify Production Backup", description="Daily check", priority="P1")

    commands_and_expected_modes = [
        ("Can you hear me?", "jarvis_presence"),
        ("Good morning", "voice_macro_routine"),
        ("Start my workout", "voice_macro_routine"),
        ("Wrap up my day", "voice_macro_routine"),
        ("What agents do I have?", "agent_roster"),
        ("Tell me about the Health agent", "agent_introspection"),
        ("What did my agents do recently?", "agent_activity_log"),
        ("Play my workout playlist", "voice_activity"),
        ("Auto tune my PC", "voice_activity"),
        ("Mask sensitive IDs", "voice_activity"),
        ("Reveal account numbers", "voice_activity"),
        ("Show my monthly tasks", "voice_activity"),
        ("Show my yearly tasks", "voice_activity"),
        ("Log weight 72.5 kg", "voice_activity"),
        ("Log fasting blood sugar 92", "voice_activity"),
        ("Run antivirus block test", "voice_activity"),
        ("Check my emails and scan attachments", "voice_activity"),
        ("Clean temporary files", "voice_activity"),
        ("Flush DNS cache", "voice_activity"),
        ("Run security scan", "voice_activity"),
        ("Show unapproved backlog items", "voice_activity"),
        ("Switch theme to midnight", "voice_activity"),
    ]

    for phrase, expected_mode in commands_and_expected_modes:
        reset_voice_topic_stack()
        res = transcribe_and_dispatch_voice_command(transcript=phrase, db=isolated_db, concise_mode=True)
        assert res["status"] == "ok", f"Voice command '{phrase}' failed: {res}"
        assert res["mode"] == expected_mode, f"Voice command '{phrase}' returned mode '{res.get('mode')}' != '{expected_mode}'"
        assert len(res.get("spoken_reply", "")) > 5, f"Empty spoken_reply for '{phrase}'"
        assert len(res.get("voice_queue_items", [])) >= 1, f"Missing voice_queue_items for '{phrase}'"


# =========================================================================
# 10. Frontend & Laptop Hardware Constraint Guardrails (`antigravity.js` & `dashboard.html`)
# =========================================================================
def test_jarvis_frontend_and_laptop_hardware_guardrails():
    ag_js = (BASE_DIR / "web" / "static" / "js" / "antigravity.js").read_text(encoding="utf-8")
    dash_html = (BASE_DIR / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")

    # 1. Zero-GC pre-allocated DSP buffers & bounded ring-buffer constants
    for sym in (
        "const _SHARED_NSDF_BUF = new Float32Array(1024);",
        "const _STATIC_BARK_BANDS =",
        "const MAX_UTTERANCE_FRAMES = 80;",
        "const MAX_CALIBRATION_PCM_CHUNKS = 120;",
        "const MAX_VOICE_AUDIO_QUEUE = 10;",
        "if (rms < 0.013)",
        "ctx.suspend()",
        "}, 110);",
    ):
        assert sym in ag_js, f"Missing laptop CPU/RAM optimization guardrail in antigravity.js: {sym}"

    # 2. Hot-mic barge-in self-cancellation protection & short-burst suppression
    assert "Date.now() - (window.AFCCVoice.speakingStartedAtMs || 0) > 1100" in ag_js
    assert "snrDb >= 27 && pitchHz >= 65 && pitchHz <= 195" in ag_js
    assert "Date.now() - (window.AFCCVoice.lastTurnDispatchedAtMs || 0) < 2500" in ag_js
    assert "Date.now() - (cache.lastSyncedAt || 0) < 900000" in ag_js
    assert "if (!res.ok && endpointUrl === '/api/voice/stream')" in ag_js

    # 3. Sequential Audio Queue & Parked Topic Stack UI elements
    for html_id in (
        "voiceQueueAndTopicStackBar",
        "voiceQueueStepBadge",
        "voiceQueueCurrentTopicLabel",
        "voiceParkedTopicsBadge",
        "btnVoiceSkipQueuePart",
        "btnVoiceResumeParkedTopic",
        "btnVoiceClearAudioQueue",
    ):
        assert html_id in dash_html, f"Missing HUD element #{html_id} in dashboard.html"
