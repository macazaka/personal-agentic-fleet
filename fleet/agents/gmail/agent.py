"""
Email Intelligence Agent for Personal Agentic Fleet.
Provides email classification, VIP filters, and inbox summarization.
"""

from typing import Any, Dict, List
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
