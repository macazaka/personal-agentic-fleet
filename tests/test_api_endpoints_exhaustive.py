"""
Exhaustive Unit Test Suite for all Fleet API Routers.
Tests tasks_api, backlog_api, email_api, optimizer_api, health_api,
antigravity_api, system_api, hyperscalers_api, and settings_api.
"""

import base64
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import urllib.parse
import pytest

from fleet.api.router import ApiRouter, router
from fleet.core.database import FleetDatabase
from fleet.core.registry import AgentRegistry
import fleet.server as srv


@pytest.fixture
def mock_api_env(tmp_path):
    db_file = tmp_path / "test_api_fleet.db"
    db = FleetDatabase(db_file)
    registry = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=tmp_path / "custom_agents",
        db=db,
    )
    with patch.object(srv, "db", db), \
         patch.object(srv, "agent_registry", registry), \
         patch.object(srv, "bus", MagicMock()) as mock_bus:
        mock_bus.dispatch.return_value = {"status": "success", "data": {"items": []}}
        yield {"db": db, "registry": registry, "bus": mock_bus, "tmp_path": tmp_path}


def test_tasks_api_exhaustive(mock_api_env):
    import fleet.api.tasks_api as tasks_mod

    handler = MagicMock()

    # 1. GET /api/tasks
    tasks_mod.get_tasks(handler, urllib.parse.urlparse("/api/tasks"))
    assert handler._send_json.called
    handler.reset_mock()

    # 2. POST /api/tasks validation failure (missing title)
    tasks_mod.create_task(handler, {"title": "", "description": "desc"})
    assert handler._send_json.called
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    # 3. POST /api/tasks validation failure (missing description)
    tasks_mod.create_task(handler, {"title": "Task", "description": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    # 4. POST /api/tasks success
    tasks_mod.create_task(handler, {"title": "New Task", "description": "A test task", "priority": "P1"})
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "created"
    task_id = res["id"]
    handler.reset_mock()

    # 5. POST /api/tasks/toggle
    tasks_mod.toggle_task(handler, {"id": task_id})
    res_toggle = handler._send_json.call_args[0][0]
    assert res_toggle["status"] == "updated"
    handler.reset_mock()

    # Toggle not found
    tasks_mod.toggle_task(handler, {"id": 999999})
    assert handler._send_json.call_args[0][1] == 404
    handler.reset_mock()

    # 6. POST /api/tasks/delete
    tasks_mod.delete_task(handler, {"id": task_id})
    assert handler._send_json.call_args[0][0]["status"] == "deleted"
    handler.reset_mock()

    # 7. GET /api/routines
    tasks_mod.get_routines(handler, urllib.parse.urlparse("/api/routines"))
    assert handler._send_json.called
    handler.reset_mock()

    # 8. POST /api/routines/toggle
    # Add dummy routine first
    r_id = mock_api_env["db"].add_routine("Daily Standup", "09:30")
    tasks_mod.toggle_routine(handler, {"id": r_id})
    assert handler._send_json.called
    assert handler._send_json.call_args[0][0]["status"] == "toggled"
    handler.reset_mock()


def test_backlog_api_exhaustive(mock_api_env):
    import fleet.api.backlog_api as backlog_mod

    handler = MagicMock()

    # 1. GET /api/backlog with query filters
    parsed = urllib.parse.urlparse("/api/backlog?status=Idea&category=Core&target_version=v1.4.0")
    backlog_mod.get_backlog(handler, parsed)
    assert handler._send_json.called
    handler.reset_mock()

    # 2. POST /api/backlog missing title
    backlog_mod.add_backlog_item(handler, {"title": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    # 3. POST /api/backlog success
    backlog_mod.add_backlog_item(handler, {"title": "Cool Feature", "description": "Detail"})
    res = handler._send_json.call_args[0][0]
    assert res["status"] == "created"
    item_id = res["id"]
    handler.reset_mock()

    # 4. POST /api/backlog/update
    backlog_mod.update_backlog_item(handler, {"id": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    backlog_mod.update_backlog_item(handler, {"id": item_id, "status": "In Progress"})
    assert handler._send_json.call_args[0][0]["status"] == "updated"
    handler.reset_mock()

    # 5. POST /api/backlog/delete
    backlog_mod.delete_backlog_item(handler, {"id": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    backlog_mod.delete_backlog_item(handler, {"id": item_id})
    assert handler._send_json.call_args[0][0]["status"] == "deleted"


def test_email_api_exhaustive(mock_api_env):
    import fleet.api.email_api as email_mod

    handler = MagicMock()

    # 1. GET /api/emails success and error branches
    mock_api_env["bus"].dispatch.return_value = {"status": "success", "data": {"emails": []}}
    email_mod.get_emails(handler, urllib.parse.urlparse("/api/emails?force_refresh=true"))
    assert handler._send_json.called
    handler.reset_mock()

    mock_api_env["bus"].dispatch.return_value = {"status": "error", "message": "Failed"}
    email_mod.get_emails(handler, urllib.parse.urlparse("/api/emails"))
    assert handler._send_json.call_args[0][1] == 500
    handler.reset_mock()

    # 2. GET /api/emails/body
    with patch("fleet.integrations.gmail_client.gmail_manager.get_email_full_body", return_value={"body": "Hello"}):
        email_mod.get_email_body(handler, urllib.parse.urlparse("/api/emails/body?id=msg_123"))
        assert handler._send_json.called
        assert handler._send_json.call_args[0][0]["body"] == "Hello"
    handler.reset_mock()

    # 3. POST /api/emails/sync
    mock_api_env["bus"].dispatch.return_value = {"status": "success", "data": {"synced": 5}}
    email_mod.sync_emails(handler, {"auto_archive_ignore": True, "force_refresh": True})
    assert handler._send_json.called
    handler.reset_mock()

    mock_api_env["bus"].dispatch.return_value = {"status": "error", "message": "Sync fail"}
    email_mod.sync_emails(handler, {})
    assert handler._send_json.call_args[0][1] == 500
    handler.reset_mock()

    # 4. POST /api/emails/unsubscribe
    email_mod.unsubscribe_email(handler, {"id": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    mock_api_env["bus"].dispatch.return_value = {"status": "success", "data": {"unsubscribed": True}}
    email_mod.unsubscribe_email(handler, {"id": "msg_999"})
    assert handler._send_json.called


def test_optimizer_api_exhaustive(mock_api_env):
    import fleet.api.optimizer_api as opt_mod

    handler = MagicMock()

    # 1. GET /api/optimizer/diagnostics
    opt_mod.get_diagnostics(handler, urllib.parse.urlparse("/api/optimizer/diagnostics"))
    assert handler._send_json.called
    handler.reset_mock()

    # 2. POST /api/optimizer/clean_temp
    opt_mod.post_clean_temp(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 3. POST /api/optimizer/flush_dns
    opt_mod.post_flush_dns(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 4. POST /api/optimizer/purge_caches
    opt_mod.post_purge_caches(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 5. POST /api/optimizer/optimize_ram
    opt_mod.post_optimize_ram(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 6. POST /api/optimizer/open_startup
    opt_mod.post_open_startup(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 7. POST /api/optimizer/auto_tune
    opt_mod.post_auto_tune(handler, {})
    assert handler._send_json.called


def test_health_api_exhaustive(mock_api_env):
    import fleet.api.health_api as health_mod

    handler = MagicMock()

    # 1. Summary
    health_mod.get_health_summary(handler, urllib.parse.urlparse("/api/health/summary"))
    assert handler._send_json.called
    handler.reset_mock()

    # 2. Water GET & POST
    health_mod.get_water(handler, urllib.parse.urlparse("/api/health/water"))
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.log_water(handler, {"glasses_delta": 2, "amount_delta_ml": 500})
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.set_water_goal(handler, {"goal_ml": 3000})
    assert handler._send_json.called
    handler.reset_mock()

    # 3. Medications GET, POST, toggle, delete
    health_mod.get_medications(handler, urllib.parse.urlparse("/api/health/medications"))
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.add_medication(handler, {"name": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    health_mod.add_medication(handler, {"name": "Metformin", "dosage": "500mg"})
    res_med = handler._send_json.call_args[0][0]
    med_id = res_med["id"]
    handler.reset_mock()

    health_mod.toggle_medication(handler, {"id": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    health_mod.toggle_medication(handler, {"id": med_id})
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.delete_medication(handler, {"id": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    health_mod.delete_medication(handler, {"id": med_id})
    assert handler._send_json.called
    handler.reset_mock()

    # 4. Trends & Metrics
    health_mod.get_health_trends(handler, urllib.parse.urlparse("/api/health/trends?metric=water_ml&days=7"))
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.log_health_metric(handler, {"metric_type": "weight", "value": 75.5, "unit": "kg"})
    assert handler._send_json.called
    handler.reset_mock()

    # 5. Profile GET & POST
    health_mod.get_health_profile(handler, urllib.parse.urlparse("/api/health/profile"))
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.update_health_profile(handler, {"target_weight_kg": 70.0, "target_hba1c": 5.5, "target_date": "2026-12-31"})
    assert handler._send_json.called
    handler.reset_mock()

    # 6. Plans
    health_mod.get_strength_plan(handler, urllib.parse.urlparse("/api/health/strength_plan"))
    assert handler._send_json.called
    handler.reset_mock()

    health_mod.get_exercise_plan(handler, urllib.parse.urlparse("/api/health/exercise_plan"))
    assert handler._send_json.called
    handler.reset_mock()

    # 7. Videos list
    health_mod.get_exercise_videos(handler, urllib.parse.urlparse("/api/health/videos?type=warmup"))
    assert handler._send_json.called
    handler.reset_mock()

    # 8. Video streaming & image error handling and success
    v_dir = mock_api_env["tmp_path"] / "videos"
    v_dir.mkdir(exist_ok=True)
    sample_img = v_dir / "sample.jpg"
    sample_img.write_bytes(b"\xFF\xD8\xFF\xE0dummy_jpg")
    sample_png = v_dir / "sample.png"
    sample_png.write_bytes(b"\x89PNGdummy_png")
    sample_vid = v_dir / "sample.mp4"
    sample_vid.write_bytes(b"dummy_mp4_bytes_1234567890_abcdef")

    with patch("fleet.api.health_api.FFD_VIDEOS_DIR", v_dir):
        # image jpg
        health_mod.get_health_image(handler, urllib.parse.urlparse("/api/health/image?file=sample.jpg"))
        assert handler.send_response.called
        handler.reset_mock()

        # image png
        health_mod.get_health_image(handler, urllib.parse.urlparse("/api/health/image?file=sample.png"))
        assert handler.send_response.called
        handler.reset_mock()

        # stream video full
        health_mod.stream_video(handler, urllib.parse.urlparse("/api/health/video/stream?file=sample.mp4"))
        assert handler.send_response.called
        handler.reset_mock()

        # stream video byte range
        handler.headers = {"Range": "bytes=0-10"}
        health_mod.stream_video(handler, urllib.parse.urlparse("/api/health/video/stream?file=sample.mp4"))
        assert handler.send_response.called
        handler.headers = {}
        handler.reset_mock()

        # open video in system
        with patch("os.startfile", create=True):
            health_mod.open_video_in_system(handler, {"filename": "sample.mp4"})
            assert handler._send_json.called
            handler.reset_mock()

    health_mod.get_health_image(handler, urllib.parse.urlparse("/api/health/image?file="))
    assert handler.send_error.called
    handler.reset_mock()

    health_mod.stream_video(handler, urllib.parse.urlparse("/api/health/video/stream?file="))
    assert handler.send_error.called
    handler.reset_mock()

    health_mod.open_video_in_system(handler, {"filename": "non_existent.mp4"})
    assert handler._send_json.called
    assert handler._send_json.call_args[0][1] == 404


def test_antigravity_api_exhaustive(mock_api_env):
    import fleet.api.antigravity_api as ag_mod

    handler = MagicMock()

    # 1. Transcript
    ag_mod.get_transcript(handler, urllib.parse.urlparse("/api/antigravity/transcript?limit=10&since_step=0"))
    assert handler._send_json.called
    handler.reset_mock()

    # 2. Models GET & POST
    ag_mod.get_models(handler, urllib.parse.urlparse("/api/antigravity/models"))
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.post_models(handler, {"model": "gemini-2.5-flash"})
    assert handler._send_json.called
    handler.reset_mock()

    # 3. Usage & Tokens
    ag_mod.get_usage(handler, urllib.parse.urlparse("/api/antigravity/usage"))
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.get_tokens(handler, urllib.parse.urlparse("/api/antigravity/tokens?simulate=warning"))
    assert handler._send_json.called
    handler.reset_mock()

    # 4. Queue GET & cancel
    ag_mod.get_queue(handler, urllib.parse.urlparse("/api/antigravity/queue"))
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.cancel_queue(handler, {})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    ag_mod.cancel_queue(handler, {"id": 1})
    assert handler._send_json.called
    handler.reset_mock()

    # 5. Media prefix route
    media_f = mock_api_env["tmp_path"] / "uploaded_media.png"
    media_f.write_bytes(b"\x89PNGdummy_media")
    with patch("fleet.server.UPLOADS_DIR", mock_api_env["tmp_path"]):
        ag_mod.get_media(handler, "/api/antigravity/media/uploaded_media.png", urllib.parse.urlparse("/api/antigravity/media/uploaded_media.png"))
        assert handler.send_response.called
        handler.reset_mock()

    ag_mod.get_media(handler, "/api/antigravity/media/missing.png", urllib.parse.urlparse("/api/antigravity/media/missing.png"))
    assert handler.send_error.called
    handler.reset_mock()

    # 6. Command
    ag_mod.post_command(handler, {"command": "status", "images": [], "model": "gemini-2.5-flash"})
    assert handler._send_json.called
    handler.reset_mock()

    # 7. Upload
    ag_mod.post_upload(handler, {"filename": "test.png", "data": base64.b64encode(b"PNG_DATA").decode("ascii")})
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.post_upload(handler, {"filename": "fail.png", "data": "invalid base64 %%%"})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    # 8. Fast track, Parallel Limit, Token Resume & Simulation
    ag_mod.post_fast_track(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.post_parallel_limit(handler, {"limit": 6})
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.resume_tokens(handler, {"fallback_model": "gemini-2.5-flash"})
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.post_simulate_tokens(handler, {"status": "exhausted", "reason": "Test"})
    assert handler._send_json.called
    handler.reset_mock()

    ag_mod.post_simulate_tokens(handler, {"status": "clear"})
    assert handler._send_json.called


def test_system_api_exhaustive(mock_api_env):
    import fleet.api.system_api as sys_mod

    handler = MagicMock()

    sys_mod.get_briefing(handler, urllib.parse.urlparse("/api/briefing"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_logs(handler, urllib.parse.urlparse("/api/logs?limit=5"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_status(handler, urllib.parse.urlparse("/api/status"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_version(handler, urllib.parse.urlparse("/api/version"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_release_notes(handler, urllib.parse.urlparse("/api/release_notes"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.post_notify(handler, {"title": "Test Title", "message": "Test Message"})
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_test_results(handler, urllib.parse.urlparse("/api/test_results"))
    assert handler._send_json.called
    handler.reset_mock()

    dummy_report = {"score": 100, "findings": []}
    dummy_sbom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "components": []}
    with patch("fleet.tools.security_scanner.run_security_scan", return_value=dummy_report), \
         patch("fleet.tools.sbom_generator.generate_sbom", return_value=dummy_sbom):
        sys_mod.get_security_scan(handler, urllib.parse.urlparse("/api/security/scan?refresh=true"))
        assert handler._send_json.called
        handler.reset_mock()

        sys_mod.get_security_scan(handler, urllib.parse.urlparse("/api/security/scan?refresh=false"))
        assert handler._send_json.called
        handler.reset_mock()

        sys_mod.post_security_scan(handler, {})
        assert handler._send_json.called
        handler.reset_mock()

        sys_mod.get_security_sbom(handler, urllib.parse.urlparse("/api/security/sbom?refresh=true"))
        assert handler._send_json.called
        handler.reset_mock()

        sys_mod.get_security_sbom(handler, urllib.parse.urlparse("/api/security/sbom?refresh=false"))
        assert handler._send_json.called
        handler.reset_mock()

    sys_mod.get_security_doctor(handler, urllib.parse.urlparse("/api/security/doctor"))
    assert handler._send_json.called
    handler.reset_mock()

    sys_mod.get_security_token_stats(handler, urllib.parse.urlparse("/api/security/token_stats"))
    assert handler._send_json.called


def test_hyperscalers_api_exhaustive(mock_api_env):
    import fleet.api.hyperscalers_api as hyper_mod

    handler = MagicMock()

    # 1. Providers & Dev tools
    hyper_mod.get_hyperscaler_providers(handler, urllib.parse.urlparse("/api/hyperscalers/providers"))
    assert handler._send_json.called
    handler.reset_mock()

    hyper_mod.get_developer_tools_status(handler, urllib.parse.urlparse("/api/hyperscalers/dev_tools"))
    assert handler._send_json.called
    handler.reset_mock()

    # 2. Generate missing prompt vs success
    hyper_mod.post_hyperscaler_generate(handler, {"prompt": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete", return_value={"response": "Generated output"}):
        hyper_mod.post_hyperscaler_generate(handler, {"prompt": "Hello world", "provider": "auto", "model": "gemini-2.5-flash"})
        assert handler._send_json.called
        assert handler._send_json.call_args[0][0]["response"] == "Generated output"
    handler.reset_mock()

    # 3. Dev tools CLI execution
    hyper_mod.post_execute_claude_code(handler, {"prompt": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    hyper_mod.post_execute_gemini_cli(handler, {"prompt": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    hyper_mod.post_execute_copilot(handler, {"prompt": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    hyper_mod.post_execute_aws_q(handler, {"prompt": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    with patch("fleet.api.hyperscalers_api.execute_claude_code", return_value={"status": "ok"}), \
         patch("fleet.api.hyperscalers_api.execute_google_gemini_cli", return_value={"status": "ok"}), \
         patch("fleet.api.hyperscalers_api.execute_github_copilot_command", return_value={"status": "ok"}), \
         patch("fleet.api.hyperscalers_api.execute_aws_q_developer", return_value={"status": "ok"}):
        hyper_mod.post_execute_claude_code(handler, {"prompt": "test"})
        assert handler._send_json.called
        handler.reset_mock()
        hyper_mod.post_execute_gemini_cli(handler, {"prompt": "test"})
        assert handler._send_json.called
        handler.reset_mock()
        hyper_mod.post_execute_copilot(handler, {"prompt": "test"})
        assert handler._send_json.called
        handler.reset_mock()
        hyper_mod.post_execute_aws_q(handler, {"prompt": "test"})
        assert handler._send_json.called
        handler.reset_mock()

    # 4. Sync instructions
    hyper_mod.post_sync_copilot_instructions(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    hyper_mod.post_sync_all_instructions(handler, {})
    assert handler._send_json.called
    handler.reset_mock()

    # 5. Vault store key
    hyper_mod.post_configure_hyperscaler_key(handler, {"key_name": "", "secret_value": ""})
    assert handler._send_json.call_args[0][1] == 400
    handler.reset_mock()

    with patch("fleet.api.hyperscalers_api.set_secure_secret", return_value=True):
        hyper_mod.post_configure_hyperscaler_key(handler, {"key_name": "OPENAI_API_KEY", "secret_value": "dummy_val"})
        assert handler._send_json.called


def test_api_router_methods():
    r = ApiRouter()
    r2 = ApiRouter()

    @r.get("/exact")
    def eg(h, p):
        pass

    @r.post("/exact")
    def ep(h, b):
        pass

    @r.get_prefix("/pre/")
    def pg(h, p, pu):
        pass

    @r.get_prefix("/short_pre/")
    def spg(h, pu):
        pass

    @r.post_prefix("/post_pre/")
    def pp(h, p, b):
        pass

    @r.post_prefix("/short_post_pre/")
    def spp(h, b):
        pass

    r2.include_router(r)
    r2.include_router(r2)
    r2.include_router(None)

    h = MagicMock()
    assert r2.dispatch_get(h, "/exact", urllib.parse.urlparse("/exact")) is True
    assert r2.dispatch_get(h, "/pre/123", urllib.parse.urlparse("/pre/123")) is True
    assert r2.dispatch_get(h, "/short_pre/123", urllib.parse.urlparse("/short_pre/123")) is True
    assert r2.dispatch_get(h, "/unknown", urllib.parse.urlparse("/unknown")) is False

    assert r2.dispatch_post(h, "/exact", {}) is True
    assert r2.dispatch_post(h, "/post_pre/123", {}) is True
    assert r2.dispatch_post(h, "/short_post_pre/123", {}) is True
    assert r2.dispatch_post(h, "/unknown", {}) is False

