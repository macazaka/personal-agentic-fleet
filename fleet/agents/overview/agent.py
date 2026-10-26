"""
Fleet Overview Agent for Personal Agentic Fleet.
Monitors system status, machine metrics, tasks, and daily autonomous briefings.
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent
from fleet.api import system_api, tasks_api


class OverviewAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "overview"

    @property
    def name(self) -> str:
        return "Overview & Tasks"

    @property
    def icon(self) -> str:
        return "⚡"

    @property
    def order(self) -> int:
        return 20

    @property
    def is_default(self) -> bool:
        return False

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "show_performance_gauge",
                "label": "Display PC Health & RAM Gauge",
                "type": "boolean",
                "default": True,
                "description": "Show the real-time memory and system performance meter on the overview panel"
            },
            {
                "id": "show_quick_actions",
                "label": "Display Quick Action Shortcuts",
                "type": "boolean",
                "default": True,
                "description": "Show one-click PC cleanup and morning briefing trigger buttons"
            },
            {
                "id": "daily_briefing_time",
                "label": "Morning Executive Briefing Time",
                "type": "text",
                "default": "08:30",
                "description": "Time of day to compile and dispatch morning intelligence summary"
            },
            {
                "id": "evening_review_time",
                "label": "Evening Routine Review Time",
                "type": "text",
                "default": "20:00",
                "description": "Time of day for evening compliance checklist alert"
            }
        ]

    def register_routes(self, router) -> None:
        router.include_router(system_api.router)
        router.include_router(tasks_api.router)

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t_low = (task or "").lower()
        if "morning" in t_low or "briefing" in t_low:
            from fleet.core.briefing import BriefingEngine
            be = BriefingEngine(self._raw_db or self.db)
            data = be.generate_daily_briefing()
            stats = data.get("summary_stats", {})
            return {
                "status": "success",
                "title": "☀️ Good Morning! Daily Briefing Ready",
                "message": f"{data.get('headline', '')} ({stats.get('pending_count', 0)} open tasks, {stats.get('p1_count', 0)} P1 priorities).",
                "briefing": data,
            }
        elif "evening" in t_low or "review" in t_low:
            from fleet.core.briefing import BriefingEngine
            be = BriefingEngine(self._raw_db or self.db)
            data = be.generate_daily_briefing()
            stats = data.get("summary_stats", {})
            return {
                "status": "success",
                "title": "🌙 Evening Review Time",
                "message": f"You completed {stats.get('completed_count', 0)} tasks today ({stats.get('completion_rate', 0)}%). Time to wrap up!",
                "briefing": data,
            }
        return {"status": "SUCCESS", "agent": self.id, "task": task}
