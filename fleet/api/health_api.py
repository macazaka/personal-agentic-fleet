"""
Health & Wellness API endpoints for Personal Agentic Fleet.
"""

from typing import Any, Dict
import urllib.parse
from fleet.api.router import router
import fleet.server as srv


@router.get("/api/health/summary")
def get_health_summary(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.db.get_health_dashboard_summary()
    handler._send_json(data)


@router.get("/api/health/water")
def get_water(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.db.get_today_hydration()
    handler._send_json(data)


@router.post("/api/health/water")
def log_water(handler: Any, body: Dict[str, Any]):
    delta_glasses = int(body.get("glasses_delta", 1))
    delta_ml = int(body.get("amount_delta_ml", delta_glasses * 250))
    res = srv.db.log_water_intake(glasses_delta=delta_glasses, amount_delta_ml=delta_ml)
    handler._send_json({"status": "success", "hydration": res})


@router.post("/api/health/water/goal")
def set_water_goal(handler: Any, body: Dict[str, Any]):
    goal_ml = int(body.get("goal_ml", 2500))
    res = srv.db.set_hydration_goal(goal_ml=goal_ml)
    handler._send_json({"status": "success", "hydration": res})


@router.get("/api/health/medications")
def get_medications(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.db.list_medications()
    handler._send_json(data)


@router.post("/api/health/medications")
def add_medication(handler: Any, body: Dict[str, Any]):
    name = body.get("name", "").strip()
    if not name:
        handler._send_json({"error": "Medication name required"}, 400)
        return
    dosage = body.get("dosage", "")
    time_val = body.get("schedule_time", "09:00")
    freq = body.get("frequency", "Daily")
    instructions = body.get("instructions", "")
    med_id = srv.db.add_medication(name=name, dosage=dosage, schedule_time=time_val, frequency=freq, instructions=instructions)
    handler._send_json({"status": "created", "id": med_id})


@router.post("/api/health/medications/toggle")
def toggle_medication(handler: Any, body: Dict[str, Any]):
    med_id = body.get("id")
    if not med_id:
        handler._send_json({"error": "Medication ID required"}, 400)
        return
    taken = srv.db.toggle_medication_today(med_id)
    handler._send_json({"status": "toggled", "taken": taken})


@router.post("/api/health/medications/delete")
def delete_medication(handler: Any, body: Dict[str, Any]):
    med_id = body.get("id")
    if not med_id:
        handler._send_json({"error": "Medication ID required"}, 400)
        return
    deleted = srv.db.delete_medication(med_id)
    handler._send_json({"status": "deleted", "deleted": deleted})


@router.get("/api/health/trends")
def get_health_trends(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    metric = query.get("metric", ["water_ml"])[0]
    days = int(query.get("days", [7])[0])
    data = srv.db.get_health_trends(metric_type=metric, days=days)
    handler._send_json(data)


@router.post("/api/health/metrics/log")
def log_health_metric(handler: Any, body: Dict[str, Any]):
    m_type = body.get("metric_type", "").strip()
    val = float(body.get("value", 0.0))
    unit = body.get("unit", "")
    notes = body.get("notes", "")
    mid = srv.db.log_health_metric(metric_type=m_type, value=val, unit=unit, notes=notes)
    handler._send_json({"status": "logged", "id": mid})



@router.get("/api/health/profile")
def get_health_profile(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.db.get_metabolic_profile()
    handler._send_json(data)


@router.post("/api/health/profile")
def update_health_profile(handler: Any, body: Dict[str, Any]):
    target_wt = body.get("target_weight_kg")
    target_a1c = body.get("target_hba1c")
    target_date = body.get("target_date")
    res = srv.db.update_metabolic_profile(
        target_weight_kg=float(target_wt) if target_wt is not None else None,
        target_hba1c=float(target_a1c) if target_a1c is not None else None,
        target_date=str(target_date) if target_date else None
    )
    handler._send_json({"status": "updated", "profile": res})

import os
from pathlib import Path
from fleet.core.exercise_manager import (
    FFD_VIDEOS_DIR,
    list_exercise_videos,
    get_strength_training_plan,
    get_ffd_exercise_protocol
)


@router.get("/api/health/videos")
def get_exercise_videos(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    v_type = query.get("type", [None])[0]
    videos = list_exercise_videos(video_type_filter=v_type)
    handler._send_json(videos)

@router.get("/api/health/image")
def get_health_image(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    filename = query.get("file", [""])[0]
    safe_name = os.path.basename(filename)
    if not safe_name:
        handler.send_error(400, "Missing filename")
        return
    file_path = (FFD_VIDEOS_DIR / safe_name).resolve()
    if not file_path.is_file() or not str(file_path).startswith(str(FFD_VIDEOS_DIR)):
        handler.send_error(404, "Image not found")
        return
    ext = file_path.suffix.lower()
    content_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
    data = file_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    handler.wfile.write(data)



@router.get("/api/health/video/stream")
def stream_video(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    filename = query.get("file", [""])[0]
    safe_name = os.path.basename(filename)
    if not safe_name:
        handler.send_error(400, "Missing filename")
        return
    file_path = (FFD_VIDEOS_DIR / safe_name).resolve()
    if not file_path.is_file() or not str(file_path).startswith(str(FFD_VIDEOS_DIR)):
        handler.send_error(404, "Video not found")
        return

    file_size = file_path.stat().st_size
    range_header = getattr(handler, "headers", {}).get("Range")

    if range_header and range_header.startswith("bytes="):
        try:
            byte_range = range_header.split("=")[1].strip()
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else min(start + 2 * 1024 * 1024 - 1, file_size - 1)
            end = min(end, file_size - 1)
            length = end - start + 1

            handler.send_response(206)
            handler.send_header("Content-Type", "video/mp4")
            handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            handler.send_header("Content-Length", str(length))
            handler.send_header("Accept-Ranges", "bytes")
            handler.end_headers()

            with open(file_path, "rb") as f:
                f.seek(start)
                handler.wfile.write(f.read(length))
            return
        except Exception:
            pass

    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "video/mp4")
        handler.send_header("Content-Length", str(file_size))
        handler.send_header("Accept-Ranges", "bytes")
        handler.end_headers()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 512):
                handler.wfile.write(chunk)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        pass


@router.post("/api/health/video/open_system")
def open_video_in_system(handler: Any, body: Dict[str, Any]):
    filename = body.get("filename", "")
    safe_name = os.path.basename(filename)
    file_path = (FFD_VIDEOS_DIR / safe_name).resolve()
    if not file_path.is_file():
        handler._send_json({"error": "Video not found"}, 404)
        return
    try:
        os.startfile(str(file_path))
        handler._send_json({"status": "opened", "filename": safe_name})
    except Exception as e:
        handler._send_json({"error": str(e)}, 500)


@router.get("/api/health/strength_plan")
def get_strength_plan(handler: Any, parsed_url: urllib.parse.ParseResult):
    plan = get_strength_training_plan()
    handler._send_json(plan)


@router.get("/api/health/exercise_plan")
def get_exercise_plan(handler: Any, parsed_url: urllib.parse.ParseResult):
    plan = get_ffd_exercise_protocol()
    handler._send_json(plan)
