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


@router.get("/api/emails/proposals")
def get_email_proposals_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    Discovers and returns AFCC tracking additions (`track_addition`) and new agent proposals
    (`new_agent`) from classified emails and pre-scanned CLEAN attachments, registering
    pending items in `feature_backlog` with `status="Unapproved"`.
    """
    try:
        from fleet.integrations.email_intelligence_proposals import (
            discover_email_and_attachment_proposals,
        )
        res = discover_email_and_attachment_proposals(db=srv.db)
        handler._send_json(res)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, 500)


@router.post("/api/emails/proposals/approve")
def approve_email_proposal_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Approves an `Unapproved` email/attachment proposal after verifying its attachment virus scan
    is CLEAN, implements the new agent or tracking task, and updates its Feature Backlog status
    from `Unapproved` -> `Completed`.
    """
    proposal_id = str(body.get("proposal_id") or body.get("id") or "").strip()
    backlog_id = int(body.get("backlog_id") or 0)
    if not proposal_id and backlog_id <= 0:
        handler._send_json({"error": "Missing 'proposal_id' or 'backlog_id'."}, 400)
        return
    try:
        from fleet.integrations.email_intelligence_proposals import approve_email_proposal
        res = approve_email_proposal(
            proposal_id=proposal_id,
            db=srv.db,
            registry=getattr(srv, "agent_registry", None),
            backlog_id=backlog_id,
        )
        handler._send_json(res)
    except KeyError as exc:
        handler._send_json({"error": str(exc)}, 404)
    except ValueError as exc:
        handler._send_json({"error": str(exc)}, 400)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, 500)


@router.post("/api/emails/proposals/reject")
def reject_email_proposal_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Rejects/defers an `Unapproved` email/attachment proposal and marks its Feature Backlog item `Deferred`.
    """
    proposal_id = str(body.get("proposal_id") or body.get("id") or "").strip()
    backlog_id = int(body.get("backlog_id") or 0)
    if not proposal_id and backlog_id <= 0:
        handler._send_json({"error": "Missing 'proposal_id' or 'backlog_id'."}, 400)
        return
    try:
        from fleet.integrations.email_intelligence_proposals import reject_email_proposal
        res = reject_email_proposal(
            proposal_id=proposal_id,
            db=srv.db,
            backlog_id=backlog_id,
        )
        handler._send_json(res)
    except KeyError as exc:
        handler._send_json({"error": str(exc)}, 404)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, 500)


@router.post("/api/emails/attachments/scan")
def scan_email_attachment_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Executes the 4-Layer Pre-Download / Pre-Use Antivirus & Malware Scanner on an attachment payload.
    """
    filename = str(body.get("filename") or "attachment.bin").strip()
    content_base64 = str(body.get("content_base64") or "").strip()
    text_content = str(body.get("text_content") or "").strip()
    mime_type = str(body.get("mime_type") or "application/octet-stream").strip()
    run_os_av = bool(body.get("run_os_av", False))

    raw_bytes = text_content.encode("utf-8") if text_content and not content_base64 else None
    try:
        from fleet.integrations.email_intelligence_proposals import scan_email_attachment_security
        res = scan_email_attachment_security(
            filename=filename,
            content_bytes=raw_bytes,
            content_base64=content_base64,
            mime_type=mime_type,
            run_os_av=run_os_av,
        )
        handler._send_json(res)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, 500)


