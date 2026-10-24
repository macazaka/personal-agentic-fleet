"""
Fleet Overview Agent for Personal Agentic Fleet.
Monitors system status, machine metrics, tasks, and daily autonomous briefings.
"""

from typing import Any, Dict, List
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

    def register_routes(self, router) -> None:
        router.include_router(system_api.router)
        router.include_router(tasks_api.router)
