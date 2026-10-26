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
