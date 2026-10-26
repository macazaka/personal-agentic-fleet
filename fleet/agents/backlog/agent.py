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

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "daily_grooming_time",
                "label": "Morning Backlog Grooming Time",
                "type": "text",
                "default": "09:00",
                "description": "Daily scheduled reminder time to review and prioritize backlog"
            },
            {
                "id": "auto_prioritize_due_today",
                "label": "Auto-Elevate Tasks Due Today",
                "type": "boolean",
                "default": True,
                "description": "Automatically boost task priority to High when due date matches today"
            },
            {
                "id": "show_completed_tasks_days",
                "label": "Keep Completed Tasks Visible (Days)",
                "type": "number",
                "default": 7,
                "description": "Number of days completed backlog items remain shown before archiving"
            },
            {
                "id": "task_completion_sound",
                "label": "Completion Audio Feedback",
                "type": "boolean",
                "default": True,
                "description": "Play a subtle audio tone when marking tasks completed"
            }
        ]

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
