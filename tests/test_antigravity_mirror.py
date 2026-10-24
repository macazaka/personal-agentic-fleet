"""Unit tests for fleet.core.antigravity_mirror."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fleet.core.antigravity_mirror import (
    clean_user_input,
    execute_dashboard_command,
    get_active_transcript_path,
    parse_transcript,
)


def test_clean_user_input():
    assert clean_user_input("") == ""
    # XML envelope
    wrapped = "<USER_REQUEST>How do I test my code?</USER_REQUEST><ADDITIONAL_METADATA>date</ADDITIONAL_METADATA>"
    assert clean_user_input(wrapped) == "How do I test my code?"
    # Stripping other tags
    other = "Hello world <SYSTEM_MESSAGE>notice</SYSTEM_MESSAGE>"
    assert clean_user_input(other) == "Hello world"


def test_transcript_parsing():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock transcript structure
        t_dir = Path(tmpdir) / ".gemini" / "antigravity" / "brain" / "sess-1" / ".system_generated" / "logs"
        t_dir.mkdir(parents=True)
        t_file = t_dir / "transcript.jsonl"

        entries = [
            {"step_index": 1, "type": "USER_INPUT", "created_at": "2026-10-13T10:00:00", "content": "<USER_REQUEST>Add task</USER_REQUEST>"},
            {
                "step_index": 2,
                "type": "PLANNER_RESPONSE",
                "created_at": "2026-10-13T10:00:05",
                "content": "I have added your task.",
                "thinking": "Adding task via fleet_add_task",
                "tool_calls": [{"name": "fleet_add_task", "args": {"title": "Test"}}]
            },
            {"invalid_json": True}
        ]
        with open(t_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
            f.write("not valid json\n")

        with patch.dict("os.environ", {"USERPROFILE": tmpdir}):
            path = get_active_transcript_path()
            assert path == t_file

            res = parse_transcript(limit=10)
            assert res["status"] == "success"
            assert len(res["messages"]) == 2
            assert res["messages"][0]["role"] == "user"
            assert res["messages"][1]["role"] == "assistant"
            assert res["messages"][1]["thinking"] == "Adding task via fleet_add_task"

            # Filter since_step
            since_res = parse_transcript(since_step=1)
            assert len(since_res["messages"]) == 1

    # Missing transcript path
    with patch.dict("os.environ", {"USERPROFILE": ""}):
        err_res = parse_transcript()
        assert err_res["status"] == "error"


def test_execute_dashboard_commands():
    from fleet.core.antigravity_mirror import AGENT_STATE, set_active_model
    from fleet.core.database import FleetDatabase
    FleetDatabase().set_setting("token_exhaustion_override", "")
    AGENT_STATE["status"] = "idle"
    set_active_model("gemini-3.8-flash-high")

    # Empty
    assert execute_dashboard_command("")["status"] == "error"

    # Briefing
    b_res = execute_dashboard_command("/briefing")
    assert b_res["status"] == "success"
    assert b_res["type"] == "briefing"

    # Tasks
    tasks_res = execute_dashboard_command("/tasks")
    assert tasks_res["status"] == "success"

    # Task add
    add_res = execute_dashboard_command("/task Deploy updates")
    assert add_res["status"] == "success"
    assert "Created Task" in add_res["message"]

    add_err = execute_dashboard_command("/task")
    assert add_err["status"] == "error"

    # Notify
    with patch("fleet.core.antigravity_mirror.send_windows_notification", return_value=True):
        notif_res = execute_dashboard_command("/notify Focus hour")
        assert notif_res["status"] == "success"
        notif_err = execute_dashboard_command("/notify")
        assert notif_err["status"] == "error"

    # Sync success
    with patch("fleet.core.antigravity_mirror.bus.dispatch") as mock_disp:
        mock_disp.return_value = {"status": "success", "data": {"counts": {"Meetings": 1}}}
        sync_res = execute_dashboard_command("/sync")
        assert sync_res["status"] == "success"

        # Sync error
        mock_disp.return_value = {"status": "error", "message": "Failed sync"}
        sync_err = execute_dashboard_command("/sync")
        assert sync_err["status"] == "error"

    # Natural Language: agy.exe exists branch and subprocess execution
    mock_agy = MagicMock()
    mock_agy.exists.return_value = True
    with patch("pathlib.Path.__truediv__", return_value=mock_agy):
        with patch("subprocess.run") as mock_sub:
            with patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))):
                agy_res = execute_dashboard_command("Research Python 3.14 features")
                assert agy_res["type"] == "agent_dispatched"
                assert mock_sub.called
                assert any("Research Python 3.14 features" in str(c) for c in mock_sub.call_args_list)

        # Natural Language: agy.exe subprocess exception (lines 257-258)
        with patch("subprocess.run", side_effect=RuntimeError("Subprocess failed")):
            with patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))):
                agy_res_err = execute_dashboard_command("Research Python 3.14 features")
                assert agy_res_err["type"] == "agent_dispatched"


    # Natural Language: Note fallback (agy.exe does not exist)
    with patch("pathlib.Path.exists", return_value=False):
        with patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))):
            nl_res = execute_dashboard_command("Remember to call accountant")
            assert nl_res["status"] == "success"
            assert nl_res["type"] == "note_logged"


def test_transcript_error_and_tool_parsing():
    # Transcript open error
    with patch("fleet.core.antigravity_mirror.get_active_transcript_path") as mock_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.parents = [MagicMock(), MagicMock(), MagicMock(name="sess-abc")]
        mock_path.return_value = mock_file
        with patch("builtins.open", side_effect=PermissionError("Locked")):
            res = parse_transcript()
            assert res["status"] == "error"
            assert "Error reading transcript" in res["message"]


def test_transcript_empty_sessions_and_tool_args():
    # 1. Empty brain directory (no transcript files found -> line 44)
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_brain = Path(tmpdir) / ".gemini" / "antigravity" / "brain"
        empty_brain.mkdir(parents=True)
        with patch.dict("os.environ", {"USERPROFILE": tmpdir}):
            assert get_active_transcript_path() is None

    # 2. Tool calls with string args (line 130-133)
    with tempfile.TemporaryDirectory() as tmpdir:
        t_dir = Path(tmpdir) / ".gemini" / "antigravity" / "brain" / "sess-tool" / ".system_generated" / "logs"
        t_dir.mkdir(parents=True)
        t_file = t_dir / "transcript.jsonl"
        entry = {
            "step_index": 1,
            "type": "PLANNER_RESPONSE",
            "created_at": "2026-10-14T00:00:00",
            "content": "Done",
            "tool_calls": [
                {"name": "tool1", "args": '{"toolSummary": "Custom Summary"}'},
                {"name": "tool2", "args": 'invalid-json-string'},
            ]
        }
        t_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        with patch.dict("os.environ", {"USERPROFILE": tmpdir}):
            res = parse_transcript()
            assert res["status"] == "success"
            assert len(res["messages"]) == 1
            tools = res["messages"][0]["tools"]
            assert tools[0]["summary"] == "Custom Summary"
            assert tools[1]["summary"] == "tool2"


def test_models_and_usage_details():
    from fleet.core.antigravity_mirror import (
        AVAILABLE_MODELS,
        get_active_model,
        get_available_models,
        get_llm_usage_details,
        set_active_model,
    )

    models = get_available_models()
    assert len(models) == 5
    assert any(m["id"] == "gemini-3.8-flash-high" for m in models)
    assert any(m["id"] == "gemini-4-argon" for m in models)

    # Active model get / set
    set_active_model("gemini-3.8-flash-high")
    assert get_active_model() == "gemini-3.8-flash-high"

    # Set by ID
    assert set_active_model("claude-opus-5-5-medium") is True
    assert get_active_model() == "claude-opus-5-5-medium"

    # Set by Name
    assert set_active_model("Claude Sonnet 5.5") is True
    assert get_active_model() == "claude-sonnet-5-5-medium"

    # Unavailable model
    assert set_active_model("gemini-4-argon") is False

    # Nonexistent model
    assert set_active_model("nonexistent-model-xyz") is False

    # Usage details
    usage = get_llm_usage_details()
    assert usage["cost_usd"] == "$0.00"
    assert "Tier 0" in usage["tier"]
    assert "Tokens" in usage["context_window"]
    set_active_model("gemini-3.8-flash-high")
    assert get_llm_usage_details()["context_window"] == "1,000,000 Tokens"


def test_image_uploads_and_agent_queueing():
    from fleet.core.antigravity_mirror import (
        AGENT_STATE,
        get_agent_status,
        process_next_in_queue,
        save_uploaded_image,
        set_active_model,
    )
    from fleet.core.database import FleetDatabase
    FleetDatabase().set_setting("token_exhaustion_override", "")
    AGENT_STATE["status"] = "idle"
    set_active_model("gemini-3.8-flash-high")

    with tempfile.TemporaryDirectory() as tmpdir:
        fake_uploads = Path(tmpdir) / "uploads"
        with patch("fleet.core.antigravity_mirror.UPLOADS_DIR", fake_uploads):
            # 1. Save standard image
            res = save_uploaded_image("sample_screenshot.png", b"fake_png_data")
            assert res["filename"] == "sample_screenshot.png"
            assert res["url"] == "/api/antigravity/media/sample_screenshot.png"
            assert (fake_uploads / "sample_screenshot.png").is_file()

            # 2. Save image with sanitized/empty name
            res_clean = save_uploaded_image("../../bad_name:??.jpg", b"clean_data")
            assert ".." not in res_clean["filename"]
            assert (fake_uploads / res_clean["filename"]).is_file()

            # 3. Mirroring to active brain session
            mock_t_path = Path(tmpdir) / "brain" / "sess-123" / ".system_generated" / "logs" / "transcript.jsonl"
            mock_t_path.parent.mkdir(parents=True)
            mock_t_path.write_text("", encoding="utf-8")
            with patch("fleet.core.antigravity_mirror.get_active_transcript_path", return_value=mock_t_path):
                res_mirror = save_uploaded_image("mirrored_pic.png", b"mirror_bytes")
                mirrored_file = Path(tmpdir) / "brain" / "sess-123" / ".user_uploaded" / "mirrored_pic.png"
                assert mirrored_file.is_file()

    # Agent status
    st = get_agent_status()
    assert "status" in st
    assert "queue_length" in st

    # Queueing when agent is busy
    AGENT_STATE["status"] = "busy"
    try:
        q_res = execute_dashboard_command("Check my code while busy", enqueue_if_busy=True)
        assert q_res["status"] == "queued"
        assert "position" in q_res

        # Image only prompt
        img_res = execute_dashboard_command("", images=["shot.png"], enqueue_if_busy=True)
        assert img_res["status"] == "queued"

        # process_next_in_queue when busy returns early
        process_next_in_queue()
    finally:
        AGENT_STATE["status"] = "idle"

    # process_next_in_queue when idle
    with patch("fleet.core.antigravity_mirror.db.get_next_queued_chat_message") as mock_get_next:
        mock_get_next.side_effect = [
            {
                "id": 999,
                "prompt": "Test queued item",
                "images": ["test.png"],
                "model": "gemini-3.8-flash-high"
            },
            None
        ]
        with patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))):
            with patch("fleet.core.antigravity_mirror._execute_agy_or_fallback") as mock_exec:
                process_next_in_queue()
                mock_exec.assert_called_once()

        # Worker exception handling
        mock_get_next.side_effect = [
            {
                "id": 1000,
                "prompt": "Test failed item",
                "images": [],
                "model": "gemini-3.8-flash-high"
            },
            None
        ]
        with patch("threading.Thread", side_effect=lambda target, args=(), **kwargs: MagicMock(start=lambda: target(*args))):
            with patch("fleet.core.antigravity_mirror._execute_agy_or_fallback", side_effect=RuntimeError("Worker error")):
                process_next_in_queue()


def test_transcript_media_parsing():
    with tempfile.TemporaryDirectory() as tmpdir:
        t_dir = Path(tmpdir) / ".gemini" / "antigravity" / "brain" / "sess-media" / ".system_generated" / "logs"
        t_dir.mkdir(parents=True)
        t_file = t_dir / "transcript.jsonl"

        entries = [
            {
                "step_index": 1,
                "type": "USER_INPUT",
                "created_at": "2026-10-14T01:00:00",
                "content": "Check this screenshot:\n- C:/path/to/diagram.png",
                "media": [{"uri": "C:/path/to/upload.png", "mime_type": "image/png"}]
            },
            {
                "step_index": 2,
                "type": "PLANNER_RESPONSE",
                "created_at": "2026-10-14T01:00:05",
                "content": "Here is the response with - /path/to/result.jpg",
                "thinking": "Parsed image",
                "media": []
            }
        ]
        with open(t_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch.dict("os.environ", {"USERPROFILE": tmpdir}):
            res = parse_transcript()
            assert res["status"] == "success"
            assert len(res["messages"]) == 2
            user_msg = res["messages"][0]
            assert len(user_msg["media"]) >= 2
            assert any(m["name"] == "upload.png" for m in user_msg["media"])
            assert any(m["name"] == "diagram.png" for m in user_msg["media"])

            asst_msg = res["messages"][1]
            assert len(asst_msg["media"]) >= 1
            assert any(m["name"] == "result.jpg" for m in asst_msg["media"])


def test_token_exhaustion_and_vaulting():
    from fleet.core.antigravity_mirror import (
        AGENT_STATE,
        get_token_health,
        handle_token_exhaustion,
        resume_token_exhaustion,
        execute_dashboard_command,
        _execute_agy_or_fallback,
        process_next_in_queue,
        set_active_model,
        get_active_model
    )
    from fleet.core.database import FleetDatabase

    test_db = FleetDatabase()
    test_db.set_setting("token_exhaustion_override", "")
    AGENT_STATE["status"] = "idle"

    # 1. Normal Token Health
    set_active_model("gemini-3.8-flash-high")
    health = get_token_health()
    assert health["status"] in ("ok", "warning")
    assert health["token_limit"] == 1000000
    assert health["active_model_id"] == "gemini-3.8-flash-high"
    assert "recommended_fallback" in health

    # 2. Simulated Warning & Exhaustion
    warn_health = get_token_health(simulated_status="warning")
    assert warn_health["status"] == "warning"
    assert warn_health["percent_used"] == 90.0

    ex_health = get_token_health(simulated_status="exhausted")
    assert ex_health["status"] == "exhausted"
    assert ex_health["percent_used"] == 100.0
    assert ex_health["is_exhausted"] is True

    # 3. Handle Token Exhaustion
    qid = test_db.enqueue_chat_message(prompt="Pending prompt during token limit", model="gemini-3.8-flash-high")
    with patch("fleet.core.antigravity_mirror.send_windows_notification") as mock_notify:
        res = handle_token_exhaustion(reason="Rate quota 429", model="gemini-3.8-flash-high")
        assert res["status"] == "exhausted"
        assert res["vaulted_count"] >= 1
        assert AGENT_STATE["status"] == "paused_token_limit"
        mock_notify.assert_called_once()

    # While paused by token limit, process_next_in_queue should exit early
    with patch("fleet.core.antigravity_mirror._execute_agy_or_fallback") as mock_exec:
        process_next_in_queue()
        mock_exec.assert_not_called()

    # While paused, execute_dashboard_command should safely vault new prompt
    with patch("fleet.core.antigravity_mirror.send_windows_notification"):
        vault_res = execute_dashboard_command("New prompt when out of tokens")
        assert vault_res["status"] == "vaulted"
        assert "safely preserved" in vault_res["message"]

    # 4. Resume Token Exhaustion
    with patch("fleet.core.antigravity_mirror.send_windows_notification") as mock_notify:
        with patch("fleet.core.antigravity_mirror.process_next_in_queue") as mock_next:
            resume_res = resume_token_exhaustion(fallback_model="claude-opus-5-5-medium")
            assert resume_res["status"] == "resumed"
            assert resume_res["resumed_count"] >= 1
            assert get_active_model() == "claude-opus-5-5-medium"
            assert AGENT_STATE["status"] == "idle"
            mock_notify.assert_called_once()
            mock_next.assert_called_once()

    # 5. _execute_agy_or_fallback handling 429 quota exception
    with patch("pathlib.Path.exists", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="429 ResourceExhausted: Quota exceeded")
            with patch("fleet.core.antigravity_mirror.handle_token_exhaustion") as mock_handle:
                _execute_agy_or_fallback("Test command with error")
                mock_handle.assert_called_once()

    # Cleanup state after test
    test_db.set_setting("token_exhaustion_override", "")
    AGENT_STATE["status"] = "idle"
    set_active_model("gemini-3.8-flash-high")


def test_execute_dashboard_command_task_formats():
    from fleet.core.antigravity_mirror import execute_dashboard_command
    res1 = execute_dashboard_command("/task Deploy App | Deploy to cloud")
    assert res1["status"] == "success"
    assert "Created Task" in res1["message"]

    res2 = execute_dashboard_command("/task Backup Data - Nightly backup")
    assert res2["status"] == "success"
    assert "Created Task" in res2["message"]

    res3 = execute_dashboard_command("/task")
    assert res3["status"] == "error"


def test_parallel_agent_pool_and_fast_track():
    import threading
    import time
    from fleet.core.antigravity_mirror import (
        ACTIVE_PARALLEL_AGENTS,
        _spawn_parallel_agent_worker,
        fast_track_queue,
        get_active_agent_count,
        get_agent_status,
        get_max_parallel_agents,
        get_parallel_agents,
        process_next_in_queue,
        set_max_parallel_agents,
        sync_agent_state,
        execute_dashboard_command,
    )
    from fleet.core.database import FleetDatabase

    test_db = FleetDatabase()

    # 1. Concurrency limit settings
    orig_limit = get_max_parallel_agents()
    assert set_max_parallel_agents(6) == 6
    assert get_max_parallel_agents() == 6
    # Clamping
    assert set_max_parallel_agents(12) == 8
    assert set_max_parallel_agents(0) == 1
    set_max_parallel_agents(4)
    assert get_max_parallel_agents() == 4

    # 2. Spawning parallel agents
    ACTIVE_PARALLEL_AGENTS.clear()
    sync_agent_state()
    assert get_active_agent_count() == 0

    worker_event = threading.Event()
    with patch("fleet.core.antigravity_mirror._execute_agy_or_fallback", side_effect=lambda *a, **k: worker_event.wait(timeout=2)):
        agent1 = _spawn_parallel_agent_worker("Task 1 in parallel")
        agent2 = _spawn_parallel_agent_worker("Task 2 in parallel")
        assert agent1 == "Agent-1"
        assert agent2 == "Agent-2"
        assert get_active_agent_count() == 2

        status = get_agent_status()
        assert status["active_agents_count"] == 2
        assert status["max_parallel_agents"] == 4
        assert len(status["parallel_agents"]) == 2

        # Parallel dispatching via execute_dashboard_command
        res = execute_dashboard_command("Research 3 dispatched directly")
        assert res["status"] == "success"
        assert res["type"] in ("agent_dispatched", "note_logged")
        assert "Launched parallel" in res["message"] or "Fleet Note" in res["message"]

        # When slots are full (4/4), next command is queued
        agent4 = _spawn_parallel_agent_worker("Task 4 fill slot")
        assert get_active_agent_count() == 4

        res_queued = execute_dashboard_command("Research 5 should queue")
        assert res_queued["status"] == "queued"
        assert "Agent capacity reached" in res_queued["message"] or "slots active" in res_queued["message"]

        # Edge case: enqueue_if_busy=False when capacity is reached (lines 834-837)
        res_busy = execute_dashboard_command("Research 6 busy", enqueue_if_busy=False)
        assert res_busy["status"] == "busy"
        assert "All 4 parallel agent slots are currently occupied" in res_busy["message"]

        # Fast track queue
        ft_res = fast_track_queue()
        assert ft_res["status"] == "success"

        # Allow workers to complete
        worker_event.set()
        time.sleep(0.05)

    ACTIVE_PARALLEL_AGENTS.clear()
    sync_agent_state()
    set_max_parallel_agents(orig_limit)

    # Edge cases: invalid max_parallel_agents setting (lines 94-95)
    with patch("fleet.core.antigravity_mirror.db.get_setting", return_value="invalid_int"):
        assert get_max_parallel_agents() == 4

    # Edge cases: invalid model fallback (line 148)
    from fleet.core.antigravity_mirror import get_active_model
    with patch("fleet.core.antigravity_mirror.db.get_setting", return_value="nonexistent_model"):
        assert get_active_model() == "gemini-3.8-flash-high"

    # Edge cases: token exhaustion during process_next_in_queue (lines 411-412)
    with patch("fleet.core.antigravity_mirror.get_token_health", return_value={"is_exhausted": True, "active_model_id": "gemini-3.8-flash-high"}):
        with patch("fleet.core.antigravity_mirror.handle_token_exhaustion") as mock_exhaust:
            process_next_in_queue()
            mock_exhaust.assert_called_once()



