"""
Feature Backlog API endpoints for Personal Agentic Fleet.
"""

from typing import Any, Dict
import urllib.parse
from fleet.api.router import router
import fleet.server as srv


@router.get("/api/backlog")
def get_backlog(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    status_filter = query.get("status", [None])[0]
    cat_filter = query.get("category", [None])[0]
    ver_filter = query.get("target_version", [None])[0]
    items = srv.db.list_feature_backlog_items(status=status_filter, category=cat_filter, target_version=ver_filter)
    stats = srv.db.get_feature_backlog_stats()
    handler._send_json({"items": items, "stats": stats})


@router.post("/api/backlog")
def add_backlog_item(handler: Any, body: Dict[str, Any]):
    title = body.get("title", "").strip()
    if not title:
        handler._send_json({"error": "Title required"}, 400)
        return
    desc = body.get("description", "")
    cat = body.get("category", "Core")
    priority = body.get("priority", "P2")
    status = body.get("status", "Idea")
    ver = body.get("target_version", "v1.4.0")
    item_id = srv.db.add_feature_backlog_item(title=title, description=desc, category=cat, priority=priority, status=status, target_version=ver)
    srv.db.log_activity("User", "backlog_add", f"Added backlog feature: {title} ({priority})")
    handler._send_json({"status": "created", "id": item_id})


@router.post("/api/backlog/update")
def update_backlog_item(handler: Any, body: Dict[str, Any]):
    item_id = body.get("id")
    if not item_id:
        handler._send_json({"error": "Item ID required"}, 400)
        return
    up_data = {k: v for k, v in body.items() if k != "id"}
    ok = srv.db.update_feature_backlog_item(item_id, **up_data)
    handler._send_json({"status": "updated" if ok else "not_found", "success": ok})


@router.post("/api/backlog/delete")
def delete_backlog_item(handler: Any, body: Dict[str, Any]):
    item_id = body.get("id")
    if not item_id:
        handler._send_json({"error": "Item ID required"}, 400)
        return
    ok = srv.db.delete_feature_backlog_item(item_id)
    handler._send_json({"status": "deleted" if ok else "not_found", "success": ok})

