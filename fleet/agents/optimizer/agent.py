"""
PC Optimizer Agent for Personal Agentic Fleet.
Provides disk cleanup, RAM boosting, high-memory process management, and OS vitals.
"""

from typing import Any, Dict, List
from fleet.core.base_agent import FleetAgent
from fleet.api import optimizer_api


class OptimizerAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "optimizer"

    @property
    def name(self) -> str:
        return "PC Optimizer"

    @property
    def icon(self) -> str:
        return "🚀"

    @property
    def order(self) -> int:
        return 30

    @property
    def is_default(self) -> bool:
        return False

    def register_routes(self, router) -> None:
        router.include_router(optimizer_api.router)
