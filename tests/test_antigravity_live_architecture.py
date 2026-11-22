"""
Verification Suite for Antigravity Live via AFCC Architecture & [AGL-01]..[AGL-10] Hardenings.
Covers documentation & Mermaid integrity, backlog registration, thread-safe newline-aligned
transcript I/O, managed subprocess cancellation & RAM admission guard, orphan queue recovery &
atomic SQLite claims, primary CLI conversation lease, real token/cost accounting, non-recursive
fallback + circuit breaker, upload/media hardening, and live diagnostics APIs.
"""

import base64
import json
import os
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from fleet.config import BASE_DIR
from fleet.core import antigravity_mirror as ag_mirror
from fleet.core.database import FleetDatabase


REPO_ROOT = BASE_DIR.parent


@pytest.fixture
def isolated_db(tmp_path):
    return FleetDatabase(db_path=tmp_path / "isolated_agl.db")


def test_antigravity_architecture_docs_and_backlog_registration(isolated_db):
    doc_path = REPO_ROOT / "docs" / "ANTIGRAVITY_LIVE_AFCC_ARCHITECTURE.md"
    wiki_path = REPO_ROOT / "wiki" / "Antigravity-Live-via-AFCC-Architecture.md"
    arch_doc = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    sidebar_md = REPO_ROOT / "wiki" / "_Sidebar.md"

    assert doc_path.is_file()
    assert wiki_path.is_file()
    doc_txt = doc_path.read_text(encoding="utf-8")
    wiki_txt = wiki_path.read_text(encoding="utf-8")

    # Verify >= 6 detailed Mermaid diagrams exist in docs & wiki
    assert doc_txt.count("```mermaid") >= 6
    assert wiki_txt.count("```mermaid") >= 6
    for diagram_type in ("flowchart TD", "sequenceDiagram", "stateDiagram-v2", "flowchart LR", "erDiagram"):
        assert diagram_type in doc_txt
        assert diagram_type in wiki_txt

    # Verify cross-links exist
    assert "ANTIGRAVITY_LIVE_AFCC_ARCHITECTURE.md" in arch_doc.read_text(encoding="utf-8")
    assert "Antigravity-Live-via-AFCC-Architecture" in sidebar_md.read_text(encoding="utf-8")

    # Verify all 10 [AGL-01]..[AGL-10] items are registered and Completed in backlog
    isolated_db.sync_ux_roadmap_backlog()
    items = isolated_db.list_feature_backlog_items()
    for i in range(1, 11):
        tag = f"[AGL-{i:02d}]"
        matched = [it for it in items if tag in it["title"]]
        assert len(matched) == 1, f"Expected single backlog entry for {tag}, found {len(matched)}"
        assert matched[0]["status"] == "Completed"


def test_agl01_transcript_lock_and_newline_aligned_partial_delta_read(tmp_path):
    conv_dir = tmp_path / "conv_agl01" / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True, exist_ok=True)
    t_path = conv_dir / "transcript.jsonl"
    s1 = {"step_index": 1, "type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Hello", "created_at": "2026-11-22T00:00:00Z"}
    t_path.write_text(json.dumps(s1) + "\n", encoding="utf-8")

    saved_cache = dict(ag_mirror._TRANSCRIPT_MEM_CACHE)
    try:
        ag_mirror._TRANSCRIPT_MEM_CACHE.update({
            "path": None, "mtime_ns": -1, "size": -1, "first_sig": b"", "tail_only": False, "raw_steps": [], "line_count": 0
        })
        with patch.object(ag_mirror, "get_active_transcript_path", return_value=t_path):
            full = ag_mirror.parse_transcript(limit=50)
            assert full["latest_step"] == 1
            cached_before_partial = ag_mirror._TRANSCRIPT_MEM_CACHE["size"]

            # Simulate an external writer flushing an incomplete JSON line without '\n'
            with open(t_path, "ab") as fb:
                fb.write(b'{"step_index": 2, "type": "PLANNER_RESPONSE", "content": "Half')

            partial_before = ag_mirror.get_transcript_cache_stats()["partial_line_deferrals"]
            mid = ag_mirror.parse_transcript(limit=50, since_step=1)
            assert mid["messages"] == []
            assert ag_mirror._TRANSCRIPT_MEM_CACHE["size"] == cached_before_partial
            assert ag_mirror.get_transcript_cache_stats()["partial_line_deferrals"] == partial_before + 1

            # Finish writing the JSONL line with '\n' -> next poll picks up step 2 cleanly without data loss
            with open(t_path, "ab") as fb:
                fb.write(b' reply", "created_at": "2026-11-22T00:00:01Z"}\n')

            done = ag_mirror.parse_transcript(limit=50, since_step=1)
            assert len(done["messages"]) == 1
            assert done["messages"][0]["step_index"] == 2
            assert done["messages"][0]["text"] == "Half reply"
    finally:
        ag_mirror._TRANSCRIPT_MEM_CACHE.clear()
        ag_mirror._TRANSCRIPT_MEM_CACHE.update(saved_cache)

    # Concurrent append + parse under _TRANSCRIPT_IO_LOCK keeps step_index monotonic
    with patch.object(ag_mirror, "get_active_transcript_path", return_value=t_path), patch.dict("os.environ", {"USERPROFILE": str(tmp_path)}):
        errors = []

        def _append_worker(idx: int):
            try:
                ag_mirror.append_transcript_turn("USER_INPUT", f"Concurrent prompt {idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_append_worker, args=(i,)) for i in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert not errors
        lines = [json.loads(ln) for ln in t_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 8
        step_nums = [x["step_index"] for x in lines]
        assert len(step_nums) == len(set(step_nums))


def test_agl02_agent_cancellation_tree_kill_and_ram_admission_guard(isolated_db, monkeypatch):
    monkeypatch.setattr(ag_mirror, "db", isolated_db)
    ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
    ag_mirror._ACTIVE_SUBPROCESSES.clear()
    ag_mirror._ACTIVE_CANCEL_EVENTS.clear()
    ag_mirror.sync_agent_state()

    try:
        qid = isolated_db.enqueue_chat_message(prompt="Long running CLI task", model="gemini-3.8-flash-high")
        ev = threading.Event()
        fake_proc = MagicMock()
        ag_mirror._ACTIVE_CANCEL_EVENTS["Agent-1"] = ev
        ag_mirror._ACTIVE_SUBPROCESSES["Agent-1"] = fake_proc
        ag_mirror.ACTIVE_PARALLEL_AGENTS["Agent-1"] = {
            "agent_id": "Agent-1",
            "worker_uuid": "w-cancel-1",
            "task": "Long running CLI task",
            "queue_id": qid,
            "model": "gemini-3.8-flash-high",
            "status": "running",
            "started_at": "11:00:00",
            "started_at_ts": time.time(),
            "elapsed_sec": 0.0,
            "pid": 99999,
            "timestamp": "2026-11-22T11:00:00",
        }
        ag_mirror.sync_agent_state()

        with patch.object(ag_mirror, "_terminate_process_tree") as mock_kill, patch.object(ag_mirror, "process_next_in_queue"):
            cancel_res = ag_mirror.cancel_running_agent("Agent-1")
            assert cancel_res["cancelled"] is True
            assert ev.is_set()
            mock_kill.assert_called_once_with(fake_proc)
            assert "Agent-1" not in ag_mirror.ACTIVE_PARALLEL_AGENTS

        not_found = ag_mirror.cancel_running_agent("Agent-999")
        assert not_found["cancelled"] is False

        # High host RAM (>= 88%) admits >=1 running agent and queues additional concurrent prompts
        ag_mirror.ACTIVE_PARALLEL_AGENTS["Agent-1"] = {
            "agent_id": "Agent-1",
            "worker_uuid": "w-ram-1",
            "task": "Existing active work",
            "queue_id": None,
            "model": "gemini-3.8-flash-high",
            "status": "running",
            "started_at": "11:00:00",
            "started_at_ts": time.time(),
            "pid": None,
            "timestamp": "2026-11-22T11:00:00",
        }
        ag_mirror.sync_agent_state()
        with patch.object(ag_mirror, "_get_system_ram_percent", return_value=92.5):
            q_res = ag_mirror.execute_dashboard_command("Second concurrent task", enqueue_if_busy=True, bypass_tier0=True)
            assert q_res["status"] == "queued"
            assert q_res["type"] == "ram_pressure_queued"
            assert q_res["ram_percent_used"] == 92.5
    finally:
        ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
        ag_mirror._ACTIVE_SUBPROCESSES.clear()
        ag_mirror._ACTIVE_CANCEL_EVENTS.clear()
        ag_mirror.sync_agent_state()


def test_agl03_orphan_recovery_atomic_claim_and_intrabatch_overlap(isolated_db, monkeypatch):
    monkeypatch.setattr(ag_mirror, "db", isolated_db)
    ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
    ag_mirror.sync_agent_state()

    try:
        q1 = isolated_db.enqueue_chat_message(prompt="@health log fasting glucose", model="gemini-3.8-flash-high")
        q2 = isolated_db.enqueue_chat_message(prompt="@health record morning blood pressure", model="gemini-3.8-flash-high")
        isolated_db.update_chat_queue_status(q1, "processing")

        # 1. Recover orphaned processing item on startup
        recovered = ag_mirror.recover_orphaned_queue_on_startup()
        assert recovered >= 1
        assert ag_mirror._ORPHAN_RECOVERY_STATS["recovered_count"] >= 1

        # 2. Atomic claim succeeds once and rejects double-claim
        assert isolated_db.claim_queued_chat_message(q1) is True
        assert isolated_db.claim_queued_chat_message(q1) is False

        # Re-queue q1 and verify intra-batch overlap stops q2 from launching alongside q1
        isolated_db.update_chat_queue_status(q1, "queued")
        with patch("threading.Thread.start"), patch.object(ag_mirror, "_get_system_ram_percent", return_value=45.0):
            ag_mirror.process_next_in_queue()
            assert len(ag_mirror.ACTIVE_PARALLEL_AGENTS) == 1
            remaining_q = [x for x in isolated_db.get_queued_chat_messages() if x["id"] == q2]
            assert len(remaining_q) == 1
    finally:
        ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
        ag_mirror.sync_agent_state()


def test_agl04_primary_conversation_lease_isolation(isolated_db, monkeypatch):
    monkeypatch.setattr(ag_mirror, "db", isolated_db)
    ag_mirror._PRIMARY_CONV_LEASE_OWNER = None
    ag_mirror._AFCC_CLI_CONVERSATION_ID = None
    isolated_db.set_setting("antigravity_cli_conversation_id", "conv-persisted-123")

    try:
        is_prim1, cid1 = ag_mirror._acquire_cli_conversation_lease("Agent-1")
        assert is_prim1 is True
        assert cid1 == "conv-persisted-123"

        # Sibling parallel worker must NOT hijack primary conversation lease or ID
        is_prim2, cid2 = ag_mirror._acquire_cli_conversation_lease("Agent-2")
        assert is_prim2 is False
        assert cid2 is None

        ag_mirror._release_cli_conversation_lease("Agent-1", "conv-updated-456")
        assert isolated_db.get_setting("antigravity_cli_conversation_id") == "conv-updated-456"
    finally:
        ag_mirror._PRIMARY_CONV_LEASE_OWNER = None
        ag_mirror._AFCC_CLI_CONVERSATION_ID = None
        isolated_db.set_setting("antigravity_cli_conversation_id", "")


def test_agl05_session_usage_ledger_and_post_compaction_estimation(tmp_path):
    with ag_mirror._SESSION_USAGE_LOCK:
        saved_usage = dict(ag_mirror._SESSION_USAGE_TELEMETRY)
        ag_mirror._SESSION_USAGE_TELEMETRY.update({
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "llm_calls": 0, "tier0_calls": 0, "estimated_cost_usd": 0.0,
            "last_provider": "tier0_local", "last_context_tokens": 0,
        })
    try:
        ag_mirror.record_llm_turn_usage("tier0_intent_router", "deterministic", tier0=True)
        d0 = ag_mirror.get_llm_usage_details()
        assert d0["cost_usd"] == "$0.00"
        assert d0["tier0_calls"] == 1

        ag_mirror.record_llm_turn_usage("Google (Gemini/Vertex)", "gemini-2.5-pro", input_tokens=10000, output_tokens=5000, total_tokens=15000)
        d1 = ag_mirror.get_llm_usage_details()
        assert d1["llm_calls"] == 1
        assert d1["real_tokens_billed"] == 15000
        assert float(d1["estimated_cost_usd"]) > 0.0
        assert d1["cost_usd"] != "$0.00"

        # Post-compaction context estimation ignores huge historical text before <CONTEXT_SUMMARY>
        t_file = tmp_path / "transcript.jsonl"
        big_prefix = ("X" * 300000) + "\n<CONTEXT_SUMMARY>\nSmall post-compaction tail.\n"
        t_file.write_text(big_prefix, encoding="utf-8")
        est = ag_mirror._estimate_transcript_active_tokens(t_file)
        assert est == 18450
    finally:
        with ag_mirror._SESSION_USAGE_LOCK:
            ag_mirror._SESSION_USAGE_TELEMETRY.update(saved_usage)


def test_agl06_agl07_frontend_adaptive_polling_and_worker_visible_error(isolated_db, monkeypatch, tmp_path):
    ag_js = (BASE_DIR / "web" / "static" / "js" / "antigravity.js").read_text(encoding="utf-8")
    app_js = (BASE_DIR / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    dash_html = (BASE_DIR / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")

    for js_sym in (
        "function scheduleAgPoll(",
        "_agCommandSubmitting",
        "cancelRunningAgent(",
        "agLiveWorkingIndicator",
        "/api/antigravity/diagnostics",
        "MAX_TRANSCRIPT_DOM_MESSAGES = 80",
        "since_step=",
        "data.unchanged",
    ):
        assert js_sym in ag_js, f"Missing {js_sym} in antigravity.js"

    assert "agPollManagedByDock" in app_js
    assert 'id="agLiveWorkingIndicator"' in dash_html

    # Worker failure appends visible error notice to transcript.jsonl
    t_dir = tmp_path / ".gemini" / "antigravity" / "brain" / "sess-err" / ".system_generated" / "logs"
    t_dir.mkdir(parents=True)
    t_file = t_dir / "transcript.jsonl"
    t_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ag_mirror, "db", isolated_db)
    ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
    try:
        with patch.dict("os.environ", {"USERPROFILE": str(tmp_path)}), \
             patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))), \
             patch.object(ag_mirror, "_execute_agy_or_fallback", side_effect=RuntimeError("Simulated CLI crash")), \
             patch.object(ag_mirror, "process_next_in_queue"):
            ag_mirror._spawn_parallel_agent_worker("Run crashing task")
        written = t_file.read_text(encoding="utf-8")
        assert "Agent Execution Error" in written
        assert "Simulated CLI crash" in written
    finally:
        ag_mirror.ACTIVE_PARALLEL_AGENTS.clear()
        ag_mirror.sync_agent_state()


def test_agl08_upload_guards_media_nosniff_and_pruning(tmp_path):
    import fleet.server as srv
    from fleet.api.antigravity_api import get_media, post_upload

    # 1. Reject dangerous extension (.svg / .html) with 400
    h_ext = MagicMock()
    b64_ok = base64.b64encode(b"<svg></svg>").decode("utf-8")
    post_upload(h_ext, {"filename": "evil.svg", "data": f"data:image/svg+xml;base64,{b64_ok}"})
    assert h_ext._send_json.call_args[0][1] == 400

    # 2. Reject > 10MB decoded payload with 413
    h_big = MagicMock()
    big_b64 = base64.b64encode(b"A" * (10 * 1024 * 1024 + 64)).decode("utf-8")
    post_upload(h_big, {"filename": "huge.png", "data": f"data:image/png;base64,{big_b64}"})
    assert h_big._send_json.call_args[0][1] == 413

    # 3. Media endpoint emits X-Content-Type-Options: nosniff and Cache-Control headers
    up_dir = tmp_path / "uploads"
    up_dir.mkdir(parents=True)
    (up_dir / "safe_shot.png").write_bytes(b"pngbytes")
    h_media = MagicMock()
    with patch.object(srv, "UPLOADS_DIR", up_dir):
        get_media(h_media, "/api/antigravity/media/safe_shot.png", urllib.parse.urlparse("/api/antigravity/media/safe_shot.png"))
    hdrs = {c[0][0]: c[0][1] for c in h_media.send_header.call_args_list}
    assert hdrs.get("X-Content-Type-Options") == "nosniff"
    assert "max-age=" in hdrs.get("Cache-Control", "")

    # 4. Upload directory LRU pruning trims oldest files when exceeding max_files
    for idx in range(5):
        fp = up_dir / f"old_{idx}.png"
        fp.write_bytes(b"x" * 100)
        os.utime(fp, (1000 + idx, 1000 + idx))
    removed = ag_mirror._prune_old_uploads(up_dir, max_files=3, max_bytes=1024 * 1024)
    assert removed >= 2
    assert len(list(up_dir.iterdir())) == 3


def test_agl09_non_recursive_fallback_and_cli_circuit_breaker():
    from fleet.core.hyperscalers import HyperscalerGateway

    gw = HyperscalerGateway()
    with patch("fleet.core.hyperscalers.get_secure_secret", return_value=""), \
         patch("fleet.core.hyperscalers._get_antigravity_cli_path", return_value="C:/fake/agy.exe"), \
         patch.object(gw, "_call_antigravity_cli") as mock_cli:
        res = gw.complete("Analyze this bug", provider="google", allow_tier0=False, allow_agy_cli=False)
        mock_cli.assert_not_called()
        assert res["status"] == "FALLBACK"

    with ag_mirror._AGY_CB_LOCK:
        saved_cb = dict(ag_mirror._AGY_CIRCUIT_BREAKER)
        ag_mirror._AGY_CIRCUIT_BREAKER.update({"consecutive_failures": 0, "open_until_ts": 0.0, "threshold": 3, "cooldown_sec": 60.0, "last_error": "", "trips": 0})
    try:
        assert ag_mirror._agy_cb_record_failure("err1") is False
        assert ag_mirror._agy_cb_record_failure("err2") is False
        assert ag_mirror._agy_cb_record_failure("err3") is True
        with patch("subprocess.run", new=ag_mirror._run_agy_subprocess_managed.__globals__["subprocess"].run):
            assert ag_mirror._agy_cb_allow() is False
        ag_mirror._agy_cb_record_success()
        assert ag_mirror._AGY_CIRCUIT_BREAKER["consecutive_failures"] == 0
    finally:
        with ag_mirror._AGY_CB_LOCK:
            ag_mirror._AGY_CIRCUIT_BREAKER.update(saved_cb)


def test_agl10_diagnostics_and_cancel_api_endpoints():
    from fleet.api.antigravity_api import cancel_agent, get_diagnostics

    h_diag = MagicMock()
    get_diagnostics(h_diag, urllib.parse.urlparse("/api/antigravity/diagnostics"))
    diag_payload = h_diag._send_json.call_args[0][0]
    assert diag_payload["status"] == "ok"
    assert "transcript_cache" in diag_payload
    assert "cli_circuit_breaker" in diag_payload
    assert "usage_telemetry" in diag_payload
    assert "orphan_recovery" in diag_payload
    assert "ram_admission" in diag_payload

    h_bad = MagicMock()
    cancel_agent(h_bad, {})
    assert h_bad._send_json.call_args[0][1] == 400

    h_ok = MagicMock()
    with patch("fleet.server.cancel_running_agent", return_value={"status": "cancelled", "cancelled": True, "agent_id": "Agent-1"}) as mock_cancel:
        cancel_agent(h_ok, {"agent_id": "Agent-1"})
        mock_cancel.assert_called_once_with("Agent-1")
        assert h_ok._send_json.call_args[0][0]["cancelled"] is True
