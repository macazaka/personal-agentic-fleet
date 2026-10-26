"""
Feature Backlog Agent for Personal Agentic Fleet.
Manages kanban items, roadmaps, feature priorities, and software lifecycle.
"""

from typing import Any, Dict, List, Optional
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

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stats = self.db.get_feature_backlog_stats() if hasattr(self.db, "get_feature_backlog_stats") else {}
        return {
            "status": "success",
            "title": "📋 Feature Backlog Hygiene",
            "message": f"Backlog: {stats.get('total', 0)} items ({stats.get('in_progress', 0)} in progress, {stats.get('todo', 0)} todo).",
            "stats": stats,
        }
