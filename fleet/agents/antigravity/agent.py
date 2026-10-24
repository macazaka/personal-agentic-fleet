"""
Antigravity Live Mirror Agent for Personal Agentic Fleet.
Provides real-time telemetry, active tool reflection, and conversation monitoring.
"""

from typing import Any, Dict, List
from fleet.core.base_agent import FleetAgent
from fleet.api import antigravity_api


class AntigravityAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "antigravity"

    @property
    def name(self) -> str:
        return "Antigravity Live"

    @property
    def icon(self) -> str:
        return "🤖"

    @property
    def order(self) -> int:
        return 40

    @property
    def is_default(self) -> bool:
        return False

    def register_routes(self, router) -> None:
        router.include_router(antigravity_api.router)
