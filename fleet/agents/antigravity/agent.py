"""
Antigravity Live Mirror Agent for Personal Agentic Fleet.
Provides real-time telemetry, active tool reflection, and conversation monitoring.
"""

from typing import Any, Dict, List, Optional
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

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "mirror_sync_interval_sec",
                "label": "Instruction Mirror Sync Interval (Seconds)",
                "type": "number",
                "default": 10,
                "description": "Polling frequency to synchronize prompts between IDE and Fleet"
            },
            {
                "id": "fastmcp_auto_expose",
                "label": "Auto-Register Tools with FastMCP",
                "type": "boolean",
                "default": True,
                "description": "Automatically expose newly installed Fleet tools to IDE MCP clients"
            },
            {
                "id": "sync_open_editor_context",
                "label": "Synchronize Active Editor Context",
                "type": "boolean",
                "default": True,
                "description": "Keep currently open editor files reflected in fleet memory"
            }
        ]

    def register_routes(self, router) -> None:
        router.include_router(antigravity_api.router)

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from fleet.core.antigravity_mirror import get_token_health, process_next_in_queue
        process_next_in_queue()
        th = get_token_health()
        return {
            "status": "success",
            "title": "🤖 Antigravity Queue & Token Pulse",
            "message": f"Queue processed. Tokens: {th.get('percent_used', 0)}% used ({th.get('status', 'Optimal')}).",
            "token_health": th,
        }
