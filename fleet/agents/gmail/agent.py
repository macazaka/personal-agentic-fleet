"""
Email Intelligence Agent for Personal Agentic Fleet.
Provides email classification, VIP filters, and inbox summarization.
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent
from fleet.api import email_api


class GmailAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "gmail"

    @property
    def name(self) -> str:
        return "Email Intelligence"

    @property
    def icon(self) -> str:
        return "📧"

    @property
    def order(self) -> int:
        return 60

    @property
    def is_default(self) -> bool:
        return False

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "sync_interval_minutes",
                "label": "Mailbox Poll Interval (Minutes)",
                "type": "number",
                "default": 30,
                "description": "Background routine pulse frequency for inbox classification"
            },
            {
                "id": "max_emails_per_scan",
                "label": "Max Unread Messages per Scan",
                "type": "number",
                "default": 25,
                "description": "Maximum number of raw emails to triage per pulse"
            },
            {
                "id": "auto_classify_urgency",
                "label": "Zero-Token Urgency Classification",
                "type": "boolean",
                "default": True,
                "description": "Automatically flag action-required and meeting messages locally"
            },
            {
                "id": "notify_vip_senders_only",
                "label": "VIP Contacts Only Alerts",
                "type": "boolean",
                "default": False,
                "description": "Suppress alerts unless message is from a designated VIP address"
            },
            {
                "id": "vip_senders",
                "label": "Designated VIP Senders / Domains",
                "type": "text",
                "default": "",
                "description": "Comma-separated email addresses or domain names (e.g. boss@corp.com, vip.org)"
            }
        ]

    def register_routes(self, router) -> None:
        router.include_router(email_api.router)

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from fleet.core.event_bus import FleetEvent
        res = self.event_bus.dispatch(FleetEvent(
            sender="GmailAgent",
            target="email",
            action="CLASSIFY_RECENT",
            payload={"dry_run": False},
        )) if self.event_bus else {"status": "success", "data": {"counts": {}}}
        counts = res.get("data", {}).get("counts", {}) if res.get("status") == "success" else {}
        return {
            "status": res.get("status", "success"),
            "title": "📬 Gmail Triage Pulse",
            "message": f"Gmail Pulse: Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}",
            "counts": counts,
        }
