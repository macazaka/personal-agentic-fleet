"""
Health & Wellness Agent for Personal Agentic Fleet.
Manages metabolic tracking, vitals, water logging, medication compliance,
6-day Akhada strength training (Mudgal, Samtola, Bhim Gadha), and FFD exercise video streaming.
"""

from pathlib import Path
from typing import Any, Dict, List
from fleet.core.base_agent import FleetAgent
from fleet.api import health_api


class HealthAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "health"

    @property
    def name(self) -> str:
        return "Health & Wellness"

    @property
    def icon(self) -> str:
        return "🌿"

    @property
    def order(self) -> int:
        return 10

    @property
    def is_default(self) -> bool:
        return True

    def register_routes(self, router) -> None:
        # Re-export / wire the modular health routes
        router.include_router(health_api.router)
