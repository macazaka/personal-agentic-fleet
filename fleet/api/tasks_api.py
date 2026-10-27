"""
Tasks & Routines API endpoints for Personal Agentic Fleet.
"""

from typing import Any, Dict
import urllib.parse
from fleet.api.router import router
import fleet.server as srv


@router.get("/api/tasks")
def get_tasks(handler: Any, parsed_url: urllib.parse.ParseResult):
    tasks = srv.db.list_tasks()
    handler._send_json(tasks)


@router.post("/api/tasks")
def create_task(handler: Any, body: Dict[str, Any]):
    title = body.get("title", "").strip()
    description = body.get("description", "").strip()
    priority = body.get("priority", "P2")
    source = body.get("source", "Dashboard").strip() or "Dashboard"
    if not title:
        handler._send_json({"error": "Title required"}, 400)
        return
    if not description:
        handler._send_json({"error": "Description required"}, 400)
        return
    task_id = srv.db.add_task(title, description=description, priority=priority, source=source)
    handler._send_json({"id": task_id, "status": "created"})


@router.post("/api/tasks/toggle")
def toggle_task(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing task ID"}, 400)
        return
    task_id = int(raw_id)
    tasks = srv.db.list_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        handler._send_json({"error": "Not found"}, 404)
        return
    new_status = "completed" if task["status"] != "completed" else "pending"
    srv.db.update_task_status(task_id, new_status)
    handler._send_json({"status": "updated", "new_status": new_status})


@router.post("/api/tasks/delete")
def delete_task(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing task ID"}, 400)
        return
    task_id = int(raw_id)
    srv.db.delete_task(task_id)
    handler._send_json({"status": "deleted"})


@router.get("/api/routines")
def get_routines(handler: Any, parsed_url: urllib.parse.ParseResult):
    routines = srv.db.list_routines()
    handler._send_json(routines)


@router.post("/api/routines/toggle")
def toggle_routine(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing routine ID"}, 400)
        return
    routine_id = int(raw_id)
    srv.db.toggle_routine(routine_id)
    handler._send_json({"status": "toggled"})

