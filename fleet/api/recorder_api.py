"""
REST API Endpoints for Multimodal Activity & Audio Narration Recording,
Brain Requirements & Unit Test Synthesis, Visible Sandbox Dry-Run,
Autonomous/Audio-Guided Self-Healing, Approval Publishing, and
Headless Workflow Execution with Human-in-the-Loop Input Resume.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict

from fleet.api.router import router
from fleet.core.activity_recorder import (
    execute_recorded_workflow,
    get_recorder_manager,
    heal_and_iterate_workflow,
    publish_recorded_agent,
    recommend_recording_modality,
    resume_workflow_run,
    run_generated_agent_unit_tests,
    run_visible_sandbox_dry_run,
    synthesize_agent_from_recording,
)
import fleet.server as srv


def _is_trusted_loopback_origin(handler: Any) -> bool:
    """Checks whether the HTTP request originated from local AFCC UI/in-process caller."""
    headers = getattr(handler, "headers", None)
    if not headers:
        return True
    origin = str(headers.get("Origin") or "").strip()
    if not origin:
        return True
    parsed = urllib.parse.urlparse(origin)
    host = (parsed.hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _extract_server_origin(handler: Any) -> str:
    headers = getattr(handler, "headers", None)
    host = headers.get("Host") if headers else None
    if host and any(str(host).startswith(p) for p in ("127.0.0.1", "localhost", "[::1]")):
        return f"http://{host}"
    return "http://127.0.0.1:7890"


@router.post("/api/studio/recorder/recommend_modality")
def post_recorder_recommend_modality_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    raw_apps = payload.get("target_apps")
    apps = [str(a) for a in raw_apps] if isinstance(raw_apps, list) else None
    res = recommend_recording_modality(
        requirement_text=str(payload.get("requirement") or payload.get("prompt") or ""),
        start_url=str(payload.get("start_url") or ""),
        target_apps=apps,
        needs_strict_headless=bool(payload.get("needs_strict_headless", True)),
        needs_existing_login=bool(payload.get("needs_existing_login", False)),
    )
    handler._send_json(res)


@router.get("/api/studio/recorder/status")
def get_recorder_status_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    try:
        limit = max(1, min(100, int((query.get("limit") or ["25"])[0])))
    except ValueError:
        limit = 25
    mgr = get_recorder_manager()
    handler._send_json(mgr.get_status(recent_limit=limit))


@router.get("/api/studio/recorder/sessions")
def get_recorder_sessions_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    try:
        limit = max(1, min(100, int((query.get("limit") or ["25"])[0])))
    except ValueError:
        limit = 25
    mgr = get_recorder_manager()
    sessions = mgr.list_sessions(limit=limit)
    handler._send_json({"status": "ok", "count": len(sessions), "sessions": sessions})


@router.post("/api/studio/recorder/start")
def post_recorder_start_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    mgr = get_recorder_manager()
    try:
        res = mgr.start_recording(
            mode=str(payload.get("mode") or "browser"),
            start_url=str(payload.get("start_url") or ""),
            launch_browser=bool(payload.get("launch_browser", False)),
            record_audio=bool(payload.get("record_audio", True)),
            label=str(payload.get("label") or ""),
            server_origin=_extract_server_origin(handler),
        )
        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/stop")
def post_recorder_stop_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    mgr = get_recorder_manager()
    try:
        res = mgr.stop_recording(
            session_id=str(payload.get("session_id") or "") or None,
            audio_base64=str(payload.get("audio_base64") or ""),
            audio_mime=str(payload.get("audio_mime") or "audio/webm"),
            audio_segments=payload.get("audio_segments") if isinstance(payload.get("audio_segments"), list) else None,
        )
        handler._send_json(res)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/event")
def post_recorder_event_endpoint(handler: Any, body: Dict[str, Any]):
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    mgr = get_recorder_manager()
    provided_token = body.get("capture_token")
    trusted = _is_trusted_loopback_origin(handler) and (provided_token is None)
    try:
        res = mgr.ingest_event(
            raw_event=body,
            session_id=str(body.get("session_id") or "") or None,
            capture_token=str(provided_token) if provided_token is not None else None,
            trusted_internal=trusted,
        )
        handler._send_json(res)
    except PermissionError as pe:
        handler._send_json({"status": "error", "message": str(pe)}, status=403)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/audio_segment")
def post_recorder_audio_segment_endpoint(handler: Any, body: Dict[str, Any]):
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    mgr = get_recorder_manager()
    provided_token = body.get("capture_token")
    trusted = _is_trusted_loopback_origin(handler) and (provided_token is None)
    try:
        res = mgr.ingest_audio_segment(
            transcript=str(body.get("transcript") or ""),
            offset_sec=float(body["offset_sec"]) if body.get("offset_sec") is not None else None,
            duration_sec=float(body.get("duration_sec") or 0.0),
            confidence=float(body.get("confidence") or 0.9),
            is_final=bool(body.get("is_final", True)),
            session_id=str(body.get("session_id") or "") or None,
            capture_token=str(provided_token) if provided_token is not None else None,
            trusted_internal=trusted,
        )
        handler._send_json(res)
    except PermissionError as pe:
        handler._send_json({"status": "error", "message": str(pe)}, status=403)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/mark_input")
def post_recorder_mark_input_endpoint(handler: Any, body: Dict[str, Any]):
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    mgr = get_recorder_manager()
    try:
        res = mgr.mark_dynamic_input(
            name=str(body.get("name") or body.get("label") or "user_input"),
            label=str(body.get("label") or ""),
            input_type=str(body.get("input_type") or "text"),
            prompt_question=str(body.get("prompt_question") or body.get("prompt") or ""),
            required=bool(body.get("required", True)),
            sensitive=bool(body.get("sensitive", False)),
            default_value=str(body.get("default_value") or ""),
            session_id=str(body.get("session_id") or "") or None,
            capture_token=str(body["capture_token"]) if body.get("capture_token") is not None else None,
            trusted_internal=_is_trusted_loopback_origin(handler),
        )
        handler._send_json(res)
    except PermissionError as pe:
        handler._send_json({"status": "error", "message": str(pe)}, status=403)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/convert")
def post_recorder_convert_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    mgr = get_recorder_manager()
    try:
        res = synthesize_agent_from_recording(
            session_id=str(payload.get("session_id") or "") or None,
            raw_events=payload.get("events") if isinstance(payload.get("events"), list) else None,
            audio_segments=payload.get("audio_segments") if isinstance(payload.get("audio_segments"), list) else None,
            label=str(payload.get("label") or ""),
            use_llm=bool(payload.get("use_llm", True)),
            auto_run_tests=bool(payload.get("auto_run_tests", False)),
            manager=mgr,
        )
        handler._send_json(res)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/run_tests")
def post_recorder_run_tests_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    session_id = str(payload.get("session_id") or "").strip()
    mgr = get_recorder_manager()
    try:
        if session_id:
            sess = mgr.load_session(session_id)
            draft = sess.get("draft")
            if not isinstance(draft, dict) or not isinstance(draft.get("spec"), dict):
                synth = synthesize_agent_from_recording(session_id=session_id, use_llm=False, manager=mgr)
                sess = mgr.load_session(session_id)
                draft = sess["draft"]
            spec = draft["spec"]
            code = draft.get("unit_tests_code")
            report = run_generated_agent_unit_tests(spec, unit_tests_code=code)
            draft["unit_test_report"] = report
            sess["draft"] = draft
            mgr.save_session(sess)
            handler._send_json({"session_id": session_id, **report})
        elif isinstance(payload.get("spec"), dict):
            report = run_generated_agent_unit_tests(payload["spec"], unit_tests_code=payload.get("unit_tests_code"))
            handler._send_json(report)
        else:
            handler._send_json({"status": "error", "message": "Provide session_id or spec."}, status=400)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/sandbox_run")
def post_recorder_sandbox_run_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        handler._send_json({"status": "error", "message": "Field 'session_id' is required."}, status=400)
        return
    mgr = get_recorder_manager()
    try:
        res = run_visible_sandbox_dry_run(
            session_id=session_id,
            user_inputs=payload.get("inputs") if isinstance(payload.get("inputs"), dict) else None,
            visible_browser=bool(payload.get("visible_browser", True)),
            simulate_only=bool(payload.get("simulate_only", False)),
            inject_failure_step=payload.get("inject_failure_step"),
            manager=mgr,
        )
        handler._send_json(res)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/heal")
def post_recorder_heal_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        handler._send_json({"status": "error", "message": "Field 'session_id' is required."}, status=400)
        return
    mgr = get_recorder_manager()
    try:
        res = heal_and_iterate_workflow(
            session_id=session_id,
            failures=payload.get("failures") if isinstance(payload.get("failures"), list) else None,
            user_audio_feedback=str(payload.get("user_audio_feedback") or ""),
            user_text_feedback=str(payload.get("user_text_feedback") or ""),
            requirements_override=payload.get("requirements_override") if isinstance(payload.get("requirements_override"), dict) else None,
            rerun_tests=bool(payload.get("rerun_tests", True)),
            manager=mgr,
        )
        handler._send_json(res)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/recorder/publish")
def post_recorder_publish_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        handler._send_json({"status": "error", "message": "Field 'session_id' is required."}, status=400)
        return
    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return
    mgr = get_recorder_manager()
    try:
        res = publish_recorded_agent(
            session_id=session_id,
            agent_registry=srv.agent_registry,
            user_approved=bool(payload.get("user_approved", False)),
            overrides=payload.get("overrides") if isinstance(payload.get("overrides"), dict) else None,
            db=getattr(srv, "db", None),
            manager=mgr,
        )
        handler._send_json(res)
    except FileNotFoundError as fnf:
        handler._send_json({"status": "error", "message": str(fnf)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/workflows/run")
def post_studio_workflow_run_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    agent_id = str(payload.get("agent_id") or payload.get("id") or "").strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Field 'agent_id' is required."}, status=400)
        return
    reg = getattr(srv, "agent_registry", None)
    agent = reg.get_agent(agent_id) if reg else None
    if not agent:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found."}, status=404)
        return
    try:
        res = execute_recorded_workflow(
            agent=agent,
            user_inputs=payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {},
            dry_run=bool(payload.get("dry_run", False)),
            task=str(payload.get("task") or "run_workflow"),
        )
        db = getattr(srv, "db", None)
        state = db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest()) if (db and hasattr(db, "get_custom_agent_dashboard_state")) else None
        handler._send_json({"status": res.get("status", "ok"), "result": res, "state": state})
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)


@router.post("/api/studio/workflows/resume")
def post_studio_workflow_resume_endpoint(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    agent_id = str(payload.get("agent_id") or payload.get("id") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    if not agent_id or not run_id:
        handler._send_json({"status": "error", "message": "Fields 'agent_id' and 'run_id' are required."}, status=400)
        return
    reg = getattr(srv, "agent_registry", None)
    agent = reg.get_agent(agent_id) if reg else None
    if not agent:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found."}, status=404)
        return
    try:
        res = resume_workflow_run(
            agent=agent,
            run_id=run_id,
            user_inputs=payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {},
            dry_run=payload.get("dry_run") if "dry_run" in payload else None,
        )
        db = getattr(srv, "db", None)
        state = db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest()) if (db and hasattr(db, "get_custom_agent_dashboard_state")) else None
        handler._send_json({"status": res.get("status", "ok"), "result": res, "state": state})
    except KeyError as ke:
        handler._send_json({"status": "error", "message": str(ke)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as exc:
        handler._send_json({"status": "error", "message": str(exc)}, status=500)
