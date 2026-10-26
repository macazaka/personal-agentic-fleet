"""
PC Optimizer Agent for Personal Agentic Fleet.
Provides disk cleanup, RAM boosting, high-memory process management, and OS vitals.
"""

from typing import Any, Dict, List, Optional
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

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from fleet.core.optimizer import flush_dns_cache, get_memory_status, optimize_ram
        res_opt = optimize_ram()
        res_dns = flush_dns_cache()
        mem = get_memory_status()
        return {
            "status": "success",
            "title": "🚀 PC Optimizer Pulse Complete",
            "message": f"RAM Optimized ({mem.get('percent_used', 0)}% used), DNS Cache Cleared.",
            "memory": mem,
            "ram_result": res_opt,
            "dns_result": res_dns,
        }
