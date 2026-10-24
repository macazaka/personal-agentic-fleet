"""Unit tests for fleet.server."""
import io
import json
from unittest.mock import MagicMock, patch

from fleet.config import VERSION
from fleet.server import FleetDashboardHandler


def create_handler(method: str, path: str, body_dict: dict | None = None):
    body_bytes = json.dumps(body_dict).encode("utf-8") if body_dict is not None else b""
    handler = FleetDashboardHandler.__new__(FleetDashboardHandler)
    handler.rfile = io.BytesIO(body_bytes)
    handler.wfile = io.BytesIO()
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.headers = {"Content-Length": str(len(body_bytes)), "Content-Type": "application/json"}
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 54321)
    handler.close_connection = False
    return handler, handler.wfile


def test_server_do_get_endpoints():
    # 1. GET / (HTML Dashboard)
    h, out = create_handler("GET", "/")
    h.do_GET()
    response = out.getvalue().decode("utf-8")
    assert "200 OK" in response
    assert "Personal Agentic Fleet" in response

    # 2. GET /api/briefing
    h, out = create_handler("GET", "/api/briefing")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 3. GET /api/tasks
    h, out = create_handler("GET", "/api/tasks?status=pending")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 4. GET /api/routines
    h, out = create_handler("GET", "/api/routines")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 5. GET /api/logs
    h, out = create_handler("GET", "/api/logs?limit=5")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 6. GET /api/emails
    with patch("fleet.server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"counts": {}}}
        h, out = create_handler("GET", "/api/emails?category=0")
        h.do_GET()
        assert "200 OK" in out.getvalue().decode("utf-8")

    # 6b. GET /api/emails/body
    h, out = create_handler("GET", "/api/emails/body?id=msg_001")
    h.do_GET()
    email_body_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in email_body_resp
    assert "Roadmap Sync" in email_body_resp

    # 7. GET /api/status
    h, out = create_handler("GET", "/api/status")
    h.do_GET()
    status_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in status_resp
    assert "version" in status_resp

    # 7b. GET /api/version
    h, out = create_handler("GET", "/api/version")
    h.do_GET()
    v_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in v_resp
    assert VERSION in v_resp

    # 7c. GET /api/release_notes
    h, out = create_handler("GET", "/api/release_notes")
    h.do_GET()
    rn_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in rn_resp
    assert "changelog_markdown" in rn_resp
    assert VERSION in rn_resp

    # 8. GET /api/antigravity/transcript
    h, out = create_handler("GET", "/api/antigravity/transcript?limit=5")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 8b. GET /static/css/dashboard.css
    h, out = create_handler("GET", "/static/css/dashboard.css")
    h.do_GET()
    css_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in css_resp
    assert "text/css" in css_resp

    # 8c. GET /static/js/app.js
    h, out = create_handler("GET", "/static/js/app.js")
    h.do_GET()
    js_resp = out.getvalue().decode("utf-8")
    assert "200 OK" in js_resp
    assert "application/javascript" in js_resp

    # 8d. GET /static/non_existent.js -> 404
    h_s404, _ = create_handler("GET", "/static/non_existent.js")
    h_s404.send_error = MagicMock()
    h_s404.do_GET()
    h_s404.send_error.assert_called_with(404, "Static asset not found")

    # 9. GET 404 for unknown path
    h, out = create_handler("GET", "/api/non_existent_route")
    h.send_error = MagicMock()
    h.do_GET()
    h.send_error.assert_called_with(404, "Not Found")


def test_server_do_post_endpoints():
    # 1. POST /api/tasks with title and description
    h, out = create_handler("POST", "/api/tasks", {"title": "Server Task", "description": "Automated server test task", "priority": "P1"})
    h.do_POST()
    resp_text = out.getvalue().decode("utf-8")
    assert "200 OK" in resp_text

    # Clean up test task immediately so it never pollutes the live database
    try:
        from fleet.core.database import FleetDatabase
        db_inst = FleetDatabase()
        created_json = json.loads(resp_text.split("\r\n\r\n")[1])
        db_inst.delete_task(created_json["id"])
    except Exception:
        pass

    # Missing title -> 400
    h_bad, out_bad = create_handler("POST", "/api/tasks", {"title": "", "description": "Some description"})
    h_bad.do_POST()
    assert "400 Bad Request" in out_bad.getvalue().decode("utf-8")

    # Missing description -> 400
    h_no_desc, out_no_desc = create_handler("POST", "/api/tasks", {"title": "Server Task", "description": ""})
    h_no_desc.do_POST()
    assert "400 Bad Request" in out_no_desc.getvalue().decode("utf-8")

    # 2. POST /api/tasks/toggle
    h, out = create_handler("POST", "/api/tasks/toggle", {"id": 1})
    h.do_POST()
    # 200 or 404 depending on id
    assert "HTTP/1.0" in out.getvalue().decode("utf-8")

    # 3. POST /api/tasks/delete
    h, out = create_handler("POST", "/api/tasks/delete", {"id": 1})
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 4. POST /api/routines/toggle
    h, out = create_handler("POST", "/api/routines/toggle", {"id": 1})
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 5. POST /api/antigravity/command
    h, out = create_handler("POST", "/api/antigravity/command", {"command": "/briefing"})
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 6. POST /api/notify
    with patch("fleet.server.send_windows_notification", return_value=True):
        h, out = create_handler("POST", "/api/notify", {"title": "T", "message": "M"})
        h.do_POST()
        assert "200 OK" in out.getvalue().decode("utf-8")

    # 7. POST /api/emails/sync
    with patch("fleet.server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"counts": {}}}
        h, out = create_handler("POST", "/api/emails/sync", {"auto_archive_ignore": False})
        h.do_POST()
        assert "200 OK" in out.getvalue().decode("utf-8")

    # 7b. POST /api/emails/unsubscribe
    with patch("fleet.server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"status": "success", "unsubscribed": True}}
        h, out = create_handler("POST", "/api/emails/unsubscribe", {
            "id": "msg_004",
            "url": "https://github.com/settings/notifications",
            "type": "http"
        })
        h.do_POST()
        assert "200 OK" in out.getvalue().decode("utf-8")
        assert "unsubscribed" in out.getvalue().decode("utf-8")

        # Missing id -> 400
        h_bad, out_bad = create_handler("POST", "/api/emails/unsubscribe", {"url": "https://foo.com"})
        h_bad.do_POST()
        assert "400 Bad Request" in out_bad.getvalue().decode("utf-8")

        # Dispatch error -> 500
        mock_bus.return_value = {"status": "error", "message": "Failed unsub"}
        h_err, out_err = create_handler("POST", "/api/emails/unsubscribe", {"id": "msg_fail"})
        h_err.do_POST()
        assert "500 Internal Server Error" in out_err.getvalue().decode("utf-8")

    # 8. POST 404 for unknown path
    h_404, out_404 = create_handler("POST", "/api/unknown_post")
    h_404.send_error = MagicMock()
    h_404.do_POST()
    h_404.send_error.assert_called_with(404, "Not Found")

    # 9. GET /api/test_results (from database and from file)
    h, out = create_handler("GET", "/api/test_results")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    mock_res_file = MagicMock()
    mock_res_file.exists.return_value = True
    mock_res_file.read_text.return_value = '{"pass_pct": 100.0, "total_tests": 39}'
    with patch("fleet.server.db.get_latest_test_run", return_value=None):
        with patch("fleet.tools.test_runner.RESULTS_FILE", mock_res_file):
            h_f, out_f = create_handler("GET", "/api/test_results")
            h_f.do_GET()
            assert "200 OK" in out_f.getvalue().decode("utf-8")

    # 10. POST /api/run_tests
    with patch("fleet.tools.test_runner.run_test_suite_isolated") as mock_runner:
        mock_runner.return_value = {"status": "PASS", "pass_pct": 100.0, "total_tests": 25}
        h, out = create_handler("POST", "/api/run_tests")
        h.do_POST()
        assert "200 OK" in out.getvalue().decode("utf-8")

    # 11. Test toggle task when existing
    with patch("fleet.server.db.list_tasks", return_value=[{"id": 42, "status": "pending"}]):
        with patch("fleet.server.db.update_task_status") as mock_update:
            h, out = create_handler("POST", "/api/tasks/toggle", {"id": 42})
            h.do_POST()
            assert "200 OK" in out.getvalue().decode("utf-8")
            mock_update.assert_called_with(42, "completed")

    with patch("fleet.server.db.list_tasks", return_value=[{"id": 43, "status": "completed"}]):
        with patch("fleet.server.db.update_task_status") as mock_update:
            h, out = create_handler("POST", "/api/tasks/toggle", {"id": 43})
            h.do_POST()
            assert "200 OK" in out.getvalue().decode("utf-8")
            mock_update.assert_called_with(43, "pending")

    # 12. Email errors on GET and POST
    with patch("fleet.server.bus.dispatch", return_value={"status": "error", "message": "Sim error"}):
        h, out = create_handler("GET", "/api/emails")
        h.do_GET()
        assert "500 Internal Server Error" in out.getvalue().decode("utf-8")

        h2, out2 = create_handler("POST", "/api/emails/sync")
        h2.do_POST()
        assert "500 Internal Server Error" in out2.getvalue().decode("utf-8")


def test_server_helper_methods():
    from fleet.server import start_server

    # _read_json empty or invalid
    h, _ = create_handler("POST", "/api/test")
    h.rfile = io.BytesIO(b"not-json")
    h.headers["Content-Length"] = "8"
    assert h._read_json() == {}

    # log_message no-op
    h.log_message("format string %s", "arg")

    # start_server invocation
    with patch("fleet.server.RobustThreadingHTTPServer") as mock_srv:
        srv_inst = MagicMock()
        mock_srv.return_value = srv_inst
        srv_inst.serve_forever.side_effect = KeyboardInterrupt
        start_server(port=9999)
        srv_inst.server_close.assert_called_once()

    # Connection error guards test
    h_err_test, _ = create_handler("GET", "/api/test")
    with patch.object(h_err_test.wfile, "write", side_effect=ConnectionResetError("Socket aborted")):
        h_err_test._send_json({"test": True})

    with patch("http.server.BaseHTTPRequestHandler.handle_one_request", side_effect=ConnectionAbortedError("Aborted")):
        h_err_test.handle_one_request()

    with patch("http.server.BaseHTTPRequestHandler.finish", side_effect=BrokenPipeError("Broken pipe")):
        h_err_test.finish()

    from fleet.server import RobustThreadingHTTPServer
    srv_mock = MagicMock(spec=RobustThreadingHTTPServer)
    with patch("sys.exc_info", return_value=(ConnectionResetError, ConnectionResetError("Reset"), None)):
        RobustThreadingHTTPServer.handle_error(srv_mock, None, None)
    with patch("sys.exc_info", return_value=(RuntimeError, RuntimeError("Other error"), None)):
        with patch("socketserver.BaseServer.handle_error"):
            RobustThreadingHTTPServer.handle_error(srv_mock, None, None)


def test_server_antigravity_features():
    import base64
    import tempfile
    from pathlib import Path

    # 1. GET /api/antigravity/models
    h, out = create_handler("GET", "/api/antigravity/models")
    h.do_GET()
    res = out.getvalue().decode("utf-8")
    assert "200 OK" in res
    assert "gemini-3.8-flash-high" in res

    # 2. GET /api/antigravity/usage
    h, out = create_handler("GET", "/api/antigravity/usage")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 3. GET /api/antigravity/queue
    h, out = create_handler("GET", "/api/antigravity/queue")
    h.do_GET()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # 4. GET /api/antigravity/media/ - success and 404
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_uploads = Path(tmpdir) / "uploads"
        fake_uploads.mkdir(parents=True)
        sample_img = fake_uploads / "test_thumb.png"
        sample_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        with patch("fleet.server.UPLOADS_DIR", fake_uploads):
            h_media, out_media = create_handler("GET", "/api/antigravity/media/test_thumb.png")
            h_media.do_GET()
            assert "200 OK" in out_media.getvalue().decode("utf-8", errors="replace")
            assert "image/png" in out_media.getvalue().decode("utf-8", errors="replace")

            # Fallback to brain session .user_uploaded
            brain_dir = Path(tmpdir) / "brain" / "sess-x"
            uploaded_dir = brain_dir / ".user_uploaded"
            uploaded_dir.mkdir(parents=True)
            brain_img = uploaded_dir / "brain_thumb.png"
            brain_img.write_bytes(b"\x89PNG\r\n\x1a\nbrainbytes")
            mock_t_path = brain_dir / ".system_generated" / "logs" / "transcript.jsonl"
            mock_t_path.parent.mkdir(parents=True)
            mock_t_path.write_text("", encoding="utf-8")

            with patch("fleet.server.get_active_transcript_path", return_value=mock_t_path):
                h_b, out_b = create_handler("GET", "/api/antigravity/media/brain_thumb.png")
                h_b.do_GET()
                assert "200 OK" in out_b.getvalue().decode("utf-8", errors="replace")

            # 404
            h_404, out_404 = create_handler("GET", "/api/antigravity/media/missing_thumb.png")
            h_404.send_error = MagicMock()
            h_404.do_GET()
            h_404.send_error.assert_called_with(404, "Media file not found")

    # 5. POST /api/antigravity/models
    h, out = create_handler("POST", "/api/antigravity/models", {"model": "claude-opus-5-5-medium"})
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")
    assert "success" in out.getvalue().decode("utf-8")

    # 6. POST /api/antigravity/upload
    b64_content = base64.b64encode(b"hello image").decode("utf-8")
    h, out = create_handler("POST", "/api/antigravity/upload", {
        "filename": "uploaded_pic.png",
        "data": f"data:image/png;base64,{b64_content}"
    })
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")
    assert "uploaded_pic.png" in out.getvalue().decode("utf-8")

    # Upload error (invalid base64)
    with patch("base64.b64decode", side_effect=ValueError("Corrupt b64")):
        h_err, out_err = create_handler("POST", "/api/antigravity/upload", {
            "filename": "err.png",
            "data": "xyz"
        })
        h_err.do_POST()
        assert "400 Bad Request" in out_err.getvalue().decode("utf-8")

    # 7. POST /api/antigravity/queue/cancel
    h, out = create_handler("POST", "/api/antigravity/queue/cancel", {"id": 123})
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")

    # Missing queue id
    h_no_id, out_no_id = create_handler("POST", "/api/antigravity/queue/cancel", {})
    h_no_id.do_POST()
    assert "400 Bad Request" in out_no_id.getvalue().decode("utf-8")

    # 8. POST /api/antigravity/command with images and model
    h, out = create_handler("POST", "/api/antigravity/command", {
        "command": "Inspect UI",
        "images": ["shot1.png"],
        "model": "claude-sonnet-5-5-medium"
    })
    h.do_POST()
    assert "200 OK" in out.getvalue().decode("utf-8")


def test_server_feature_backlog_endpoints():
    # 1. GET /api/backlog
    h, out = create_handler("GET", "/api/backlog?status=Planned&category=Core&target_version=v1.4.0")
    h.do_GET()
    res = out.getvalue().decode("utf-8")
    assert "200 OK" in res
    assert "items" in res
    assert "stats" in res

    # 2. POST /api/backlog - Success
    h, out = create_handler("POST", "/api/backlog", {
        "title": "Discord Integration Bot",
        "description": "Control fleet via Discord server.",
        "category": "Integration",
        "priority": "P2",
        "status": "Idea",
        "target_version": "v1.5.0"
    })
    h.do_POST()
    post_res = out.getvalue().decode("utf-8")
    assert "200 OK" in post_res
    assert "created" in post_res

    # Missing title -> 400
    h_bad, out_bad = create_handler("POST", "/api/backlog", {"title": ""})
    h_bad.do_POST()
    assert "400 Bad Request" in out_bad.getvalue().decode("utf-8")

    # 3. POST /api/backlog/update
    h_up, out_up = create_handler("POST", "/api/backlog/update", {
        "id": 1,
        "status": "In Progress",
        "priority": "P1"
    })
    h_up.do_POST()
    assert "200 OK" in out_up.getvalue().decode("utf-8")

    # Missing ID -> 400
    h_up_bad, out_up_bad = create_handler("POST", "/api/backlog/update", {})
    h_up_bad.do_POST()
    assert "400 Bad Request" in out_up_bad.getvalue().decode("utf-8")

    # 4. POST /api/backlog/delete
    h_del, out_del = create_handler("POST", "/api/backlog/delete", {"id": 1})
    h_del.do_POST()
    assert "200 OK" in out_del.getvalue().decode("utf-8")

    # Missing ID -> 400
    h_del_bad, out_del_bad = create_handler("POST", "/api/backlog/delete", {})
    h_del_bad.do_POST()
    assert "400 Bad Request" in out_del_bad.getvalue().decode("utf-8")


def test_server_token_endpoints():
    # 1. GET /api/antigravity/tokens
    h, out = create_handler("GET", "/api/antigravity/tokens")
    h.do_GET()
    res = out.getvalue().decode("utf-8")
    assert "200 OK" in res
    assert "token_limit" in res
    assert "status" in res

    # With simulation query
    h_sim, out_sim = create_handler("GET", "/api/antigravity/tokens?simulate=warning")
    h_sim.do_GET()
    res_sim = out_sim.getvalue().decode("utf-8")
    assert "200 OK" in res_sim
    assert "warning" in res_sim

    # 2. POST /api/antigravity/tokens/simulate (exhausted)
    with patch("fleet.core.antigravity_mirror.send_windows_notification"):
        h_post_sim, out_post_sim = create_handler("POST", "/api/antigravity/tokens/simulate", {
            "status": "exhausted",
            "reason": "Test quota limit"
        })
        h_post_sim.do_POST()
        assert "200 OK" in out_post_sim.getvalue().decode("utf-8")
        assert "simulated" in out_post_sim.getvalue().decode("utf-8")

    # 3. POST /api/antigravity/tokens/resume
    with patch("fleet.core.antigravity_mirror.send_windows_notification"):
        h_res, out_res = create_handler("POST", "/api/antigravity/tokens/resume", {
            "fallback_model": "gemini-3.8-flash-high"
        })
        h_res.do_POST()
        assert "200 OK" in out_res.getvalue().decode("utf-8")
        assert "resumed" in out_res.getvalue().decode("utf-8")

    # 4. POST /api/antigravity/tokens/simulate (clear)
    h_clr, out_clr = create_handler("POST", "/api/antigravity/tokens/simulate", {
        "status": "clear"
    })
    h_clr.do_POST()
    assert "200 OK" in out_clr.getvalue().decode("utf-8")
    assert "cleared" in out_clr.getvalue().decode("utf-8")

    # 5. POST /api/antigravity/fast_track
    with patch("fleet.server.fast_track_queue") as mock_ft:
        mock_ft.return_value = {"status": "success", "launched_count": 2, "active_parallel_agents": 2}
        h_ft, out_ft = create_handler("POST", "/api/antigravity/fast_track")
        h_ft.do_POST()
        assert "200 OK" in out_ft.getvalue().decode("utf-8")
        assert "launched_count" in out_ft.getvalue().decode("utf-8")

    # 6. POST /api/antigravity/parallel_limit
    with patch("fleet.server.set_max_parallel_agents", return_value=6) as mock_lim:
        h_lim, out_lim = create_handler("POST", "/api/antigravity/parallel_limit", {"limit": 6})
        h_lim.do_POST()
        assert "200 OK" in out_lim.getvalue().decode("utf-8")
        assert "max_parallel_agents" in out_lim.getvalue().decode("utf-8")
        mock_lim.assert_called_with(6)

    # Cleanup state after test
    from fleet.core.antigravity_mirror import set_active_model, AGENT_STATE
    from fleet.server import db
    db.set_setting("token_exhaustion_override", "")
    AGENT_STATE["status"] = "idle"
    set_active_model("gemini-3.8-flash-high")


def test_server_optimizer_endpoints():
    # 1. GET /api/optimizer/diagnostics
    h_diag, out_diag = create_handler("GET", "/api/optimizer/diagnostics")
    h_diag.do_GET()
    res_diag = out_diag.getvalue().decode("utf-8")
    assert "200 OK" in res_diag
    assert "health_score" in res_diag
    assert "recommendations" in res_diag

    # 2. POST /api/optimizer/clean_temp
    with patch("fleet.server.clean_temp_files", return_value={"status": "success", "deleted_files": 5, "reclaimed_mb": 12.5}):
        h_clean, out_clean = create_handler("POST", "/api/optimizer/clean_temp")
        h_clean.do_POST()
        res_clean = out_clean.getvalue().decode("utf-8")
        assert "200 OK" in res_clean
        assert "deleted_files" in res_clean

    # 3. POST /api/optimizer/flush_dns
    with patch("fleet.core.optimizer.subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stdout="Successfully flushed")
        h_dns, out_dns = create_handler("POST", "/api/optimizer/flush_dns")
        h_dns.do_POST()
        res_dns = out_dns.getvalue().decode("utf-8")
        assert "200 OK" in res_dns
        assert "status" in res_dns

    # 4. POST /api/optimizer/purge_caches
    with patch("fleet.server.purge_dev_caches", return_value={"status": "success", "removed_files": 10, "removed_dirs": 2, "reclaimed_mb": 3.4}):
        h_purge, out_purge = create_handler("POST", "/api/optimizer/purge_caches")
        h_purge.do_POST()
        res_purge = out_purge.getvalue().decode("utf-8")
        assert "200 OK" in res_purge
        assert "removed_files" in res_purge

    # 5. POST /api/optimizer/optimize_ram
    h_ram, out_ram = create_handler("POST", "/api/optimizer/optimize_ram")
    h_ram.do_POST()
    res_ram = out_ram.getvalue().decode("utf-8")
    assert "200 OK" in res_ram
    assert "memory_load" in res_ram

    # 6. POST /api/optimizer/open_startup
    with patch("fleet.core.optimizer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        h_start, out_start = create_handler("POST", "/api/optimizer/open_startup")
        h_start.do_POST()
        res_start = out_start.getvalue().decode("utf-8")
        assert "200 OK" in res_start
        assert "Startup Apps" in res_start

    # 7. POST /api/optimizer/auto_tune
    with patch("fleet.core.optimizer.subprocess.run") as mock_tune_sub:
        mock_tune_sub.return_value = MagicMock(returncode=0, stdout="Successfully flushed")
        h_tune, out_tune = create_handler("POST", "/api/optimizer/auto_tune")
        h_tune.do_POST()
        res_tune = out_tune.getvalue().decode("utf-8")
        assert "200 OK" in res_tune
        assert "auto_tune" in res_tune or "reclaimed_mb" in res_tune


def test_server_health_endpoints():
    # 1. GET /api/health/summary
    h_sum, out_sum = create_handler("GET", "/api/health/summary")
    h_sum.do_GET()
    res_sum = out_sum.getvalue().decode("utf-8")
    assert "200 OK" in res_sum
    assert "hydration" in res_sum

    # 2. GET /api/health/water
    h_w, out_w = create_handler("GET", "/api/health/water")
    h_w.do_GET()
    res_w = out_w.getvalue().decode("utf-8")
    assert "200 OK" in res_w
    assert "glasses" in res_w

    # 3. GET /api/health/medications
    h_m, out_m = create_handler("GET", "/api/health/medications")
    h_m.do_GET()
    res_m = out_m.getvalue().decode("utf-8")
    assert "200 OK" in res_m

    # 4. GET /api/health/trends
    h_t, out_t = create_handler("GET", "/api/health/trends?metric=water_ml&days=7")
    h_t.do_GET()
    res_t = out_t.getvalue().decode("utf-8")
    assert "200 OK" in res_t

    # 5. POST /api/health/water
    h_pw, out_pw = create_handler("POST", "/api/health/water", {"delta_glasses": 1, "delta_ml": 250})
    h_pw.do_POST()
    res_pw = out_pw.getvalue().decode("utf-8")
    assert "200 OK" in res_pw
    assert "hydration" in res_pw

    # 6. POST /api/health/water/goal
    h_pg, out_pg = create_handler("POST", "/api/health/water/goal", {"goal_ml": 2800})
    h_pg.do_POST()
    res_pg = out_pg.getvalue().decode("utf-8")
    assert "200 OK" in res_pg

    # 7. POST /api/health/medications (success & validation)
    h_pm, out_pm = create_handler("POST", "/api/health/medications", {"name": "Zinc Sulfate 50mg", "dosage": "1 tablet"})
    h_pm.do_POST()
    res_pm = out_pm.getvalue().decode("utf-8")
    assert "200 OK" in res_pm
    assert "created" in res_pm

    h_bad_m, out_bad_m = create_handler("POST", "/api/health/medications", {"name": ""})
    h_bad_m.do_POST()
    assert "400 Bad Request" in out_bad_m.getvalue().decode("utf-8")

    # 8. POST /api/health/medications/toggle (success & validation)
    h_tog, out_tog = create_handler("POST", "/api/health/medications/toggle", {"id": 1})
    h_tog.do_POST()
    res_tog = out_tog.getvalue().decode("utf-8")
    assert "200 OK" in res_tog
    assert "toggled" in res_tog

    h_bad_tog, out_bad_tog = create_handler("POST", "/api/health/medications/toggle", {})
    h_bad_tog.do_POST()
    assert "400 Bad Request" in out_bad_tog.getvalue().decode("utf-8")

    # 9. POST /api/health/medications/delete (success & validation)
    h_del, out_del = create_handler("POST", "/api/health/medications/delete", {"id": 1})
    h_del.do_POST()
    res_del = out_del.getvalue().decode("utf-8")
    assert "200 OK" in res_del

    h_bad_del, out_bad_del = create_handler("POST", "/api/health/medications/delete", {})
    h_bad_del.do_POST()
    assert "400 Bad Request" in out_bad_del.getvalue().decode("utf-8")

    # 10. POST /api/health/metrics/log
    h_log_v, out_log_v = create_handler("POST", "/api/health/metrics/log", {"metric_type": "resting_hr", "value": 66.0, "unit": "bpm"})
    h_log_v.do_POST()
    res_log_v = out_log_v.getvalue().decode("utf-8")
    assert "200 OK" in res_log_v
    assert "logged" in res_log_v

    # 11. Incremental GET /api/emails with force_refresh
    h_em, out_em = create_handler("GET", "/api/emails?force_refresh=true")
    h_em.do_GET()
    res_em = out_em.getvalue().decode("utf-8")
    assert "200 OK" in res_em

    # 12. POST /api/tasks/toggle with not-found task
    h_nt, out_nt = create_handler("POST", "/api/tasks/toggle", {"id": 999999})
    h_nt.do_POST()
    assert "404 Not Found" in out_nt.getvalue().decode("utf-8")

    # 13. POST /api/antigravity/tokens/simulate clear
    h_clr, out_clr = create_handler("POST", "/api/antigravity/tokens/simulate", {"status": "clear"})
    h_clr.do_POST()
    assert "200 OK" in out_clr.getvalue().decode("utf-8")






