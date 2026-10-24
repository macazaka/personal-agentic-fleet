"""
Antigravity Live Stream, Models & Agent Control API endpoints for Personal Agentic Fleet.
"""

import base64
import mimetypes
import os
from typing import Any, Dict
import urllib.parse

from fleet.api.router import router
import fleet.server as srv


@router.get("/api/antigravity/transcript")
def get_transcript(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [50])[0])
    since_step = int(query.get("since_step", [-1])[0])
    since_val = since_step if since_step >= 0 else None
    data = srv.parse_transcript(limit=limit, since_step=since_val)
    handler._send_json(data)


@router.get("/api/antigravity/models")
def get_models(handler: Any, parsed_url: urllib.parse.ParseResult):
    handler._send_json({
        "models": srv.get_available_models(),
        "active_model": srv.get_active_model(),
    })


@router.post("/api/antigravity/models")
def post_models(handler: Any, body: Dict[str, Any]):
    model_name = body.get("model", "")
    success = srv.set_active_model(model_name)
    handler._send_json({
        "status": "success" if success else "error",
        "model": srv.get_active_model()
    })


@router.get("/api/antigravity/usage")
def get_usage(handler: Any, parsed_url: urllib.parse.ParseResult):
    handler._send_json(srv.get_llm_usage_details())


@router.get("/api/antigravity/tokens")
def get_tokens(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    sim = query.get("simulate", [None])[0]
    handler._send_json(srv.get_token_health(simulated_status=sim))


@router.get("/api/antigravity/queue")
def get_queue(handler: Any, parsed_url: urllib.parse.ParseResult):
    handler._send_json(srv.get_agent_status())


@router.get_prefix("/api/antigravity/media/")
def get_media(handler: Any, path: str, parsed_url: urllib.parse.ParseResult):
    raw_fname = path[len("/api/antigravity/media/"):]
    filename = os.path.basename(urllib.parse.unquote(raw_fname))
    media_path = None
    if filename:
        candidate = srv.UPLOADS_DIR / filename
        if candidate.is_file():
            media_path = candidate
        else:
            t_path = srv.get_active_transcript_path()
            if t_path:
                brain_dir = t_path.parents[2]
                for c in [brain_dir / ".user_uploaded" / filename, brain_dir / filename]:
                    if c.is_file():
                        media_path = c
                        break
    if media_path and media_path.is_file():
        content_type = mimetypes.guess_type(str(media_path))[0] or "image/png"
        data = media_path.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    else:
        handler.send_error(404, "Media file not found")


@router.post("/api/antigravity/command")
def post_command(handler: Any, body: Dict[str, Any]):
    cmd = body.get("command", "")
    images = body.get("images", [])
    model = body.get("model", None)
    res = srv.execute_dashboard_command(cmd, images=images, model=model)
    handler._send_json(res)


@router.post("/api/antigravity/upload")
def post_upload(handler: Any, body: Dict[str, Any]):
    filename = body.get("filename", "")
    b64_data = body.get("data", "")
    if not b64_data and "base64" in body:
        b64_data = body.get("base64", "")
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    try:
        raw_bytes = base64.b64decode(b64_data)
        res = srv.save_uploaded_image(filename or "uploaded_image.png", raw_bytes)
        handler._send_json({"status": "success", "file": res})
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, 400)


@router.post("/api/antigravity/queue/cancel")
def cancel_queue(handler: Any, body: Dict[str, Any]):
    queue_id = body.get("id")
    if queue_id is not None:
        cancelled = srv.db.cancel_queued_chat_message(queue_id)
        handler._send_json({"status": "success" if cancelled else "failed", "cancelled": cancelled})
    else:
        handler._send_json({"status": "error", "message": "Missing queue id"}, 400)


@router.post("/api/antigravity/tokens/resume")
def resume_tokens(handler: Any, body: Dict[str, Any]):
    fallback_model = body.get("fallback_model")
    res = srv.resume_token_exhaustion(fallback_model=fallback_model)
    handler._send_json(res)


@router.post("/api/antigravity/fast_track")
def post_fast_track(handler: Any, body: Dict[str, Any]):
    res = srv.fast_track_queue()
    handler._send_json(res)


@router.post("/api/antigravity/parallel_limit")
def post_parallel_limit(handler: Any, body: Dict[str, Any]):
    limit = int(body.get("limit", 4))
    updated = srv.set_max_parallel_agents(limit)
    handler._send_json({"status": "success", "max_parallel_agents": updated})


@router.post("/api/antigravity/tokens/simulate")
def post_simulate_tokens(handler: Any, body: Dict[str, Any]):
    sim_status = body.get("status", "exhausted")
    if sim_status == "clear":
        srv.db.set_setting("token_exhaustion_override", "")
        srv.AGENT_STATE["status"] = "idle"
        handler._send_json({"status": "cleared", "override": ""})
    else:
        srv.db.set_setting("token_exhaustion_override", sim_status)
        if sim_status == "exhausted":
            srv.handle_token_exhaustion(reason=body.get("reason", "Simulated token exhaustion"))
        handler._send_json({"status": "simulated", "override": sim_status})

