"""
Email Intelligence & Unsubscribe API endpoints for Personal Agentic Fleet.
"""

from typing import Any, Dict
import urllib.parse
from fleet.api.router import router
from fleet.core.event_bus import FleetEvent
import fleet.server as srv


@router.get("/api/emails")
def get_emails(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    force = query.get("force_refresh", ["false"])[0].lower() in ("true", "1")
    res = srv.bus.dispatch(FleetEvent(
        sender="WebDashboard",
        target="email",
        action="CLASSIFY_RECENT",
        payload={"dry_run": True, "force_refresh": force}
    ))
    if res.get("status") == "success":
        handler._send_json(res["data"])
    else:
        handler._send_json({"error": res.get("message")}, 500)


@router.get("/api/emails/body")
def get_email_body(handler: Any, parsed_url: urllib.parse.ParseResult):
    q_params = urllib.parse.parse_qs(parsed_url.query)
    msg_id = q_params.get("id", [""])[0]
    from fleet.integrations.gmail_client import gmail_manager
    res = gmail_manager.get_email_full_body(msg_id)
    handler._send_json(res)


@router.post("/api/emails/sync")
def sync_emails(handler: Any, body: Dict[str, Any]):
    auto_archive = body.get("auto_archive_ignore", False)
    force_refresh = body.get("force_refresh", False)
    res = srv.bus.dispatch(FleetEvent(
        sender="WebDashboard",
        target="email",
        action="CLASSIFY_RECENT",
        payload={"dry_run": False, "auto_archive_ignore": auto_archive, "force_refresh": force_refresh}
    ))
    if res.get("status") == "success":
        handler._send_json(res["data"])
    else:
        handler._send_json({"error": res.get("message")}, 500)


@router.post("/api/emails/unsubscribe")
def unsubscribe_email(handler: Any, body: Dict[str, Any]):
    msg_id = body.get("id")
    if not msg_id:
        handler._send_json({"error": "Missing email id"}, 400)
        return
    res = srv.bus.dispatch(FleetEvent(
        sender="WebDashboard",
        target="email",
        action="UNSUBSCRIBE",
        payload={
            "message_id": msg_id,
            "url": body.get("url"),
            "type": body.get("type", "http"),
            "sender": body.get("sender", ""),
            "subject": body.get("subject", "")
        }
    ))
    if res.get("status") == "success":
        handler._send_json(res["data"])
    else:
        handler._send_json({"error": res.get("message")}, 500)

