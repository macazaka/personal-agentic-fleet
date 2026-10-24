"""
Feature Backlog Agent for Personal Agentic Fleet.
Manages kanban items, roadmaps, feature priorities, and software lifecycle.
"""

from typing import Any, Dict, List
from fleet.core.base_agent import FleetAgent
from fleet.api import backlog_api


class BacklogAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "backlog"

    @property
    def name(self) -> str:
        return "Feature Backlog"

    @property
    def icon(self) -> str:
        return "📋"

    @property
    def order(self) -> int:
        return 50

    @property
    def is_default(self) -> bool:
        return False

    def register_routes(self, router) -> None:
        router.include_router(backlog_api.router)
