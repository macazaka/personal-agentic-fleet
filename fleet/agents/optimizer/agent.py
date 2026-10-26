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

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "auto_ram_threshold_pct",
                "label": "High RAM Warning Threshold (%)",
                "type": "number",
                "default": 80,
                "description": "Trigger working set sweeps and warnings when RAM exceeds this level"
            },
            {
                "id": "auto_clean_temp_mb",
                "label": "Temp Bloat Warning Threshold (MB)",
                "type": "number",
                "default": 100,
                "description": "Prompt for junk file purging when temporary folders exceed this size"
            },
            {
                "id": "auto_flush_dns_on_wake",
                "label": "Flush DNS Cache on Sleep Resume",
                "type": "boolean",
                "default": True,
                "description": "Automatically purge stale resolver caches when workstation wakes"
            },
            {
                "id": "auto_purge_dev_cache",
                "label": "Auto-Purge PyCache Artifacts",
                "type": "boolean",
                "default": False,
                "description": "Automatically remove __pycache__ and pytest artifacts on startup"
            },
            {
                "id": "process_monitor_limit",
                "label": "Top Processes Monitored",
                "type": "number",
                "default": 6,
                "description": "Number of top memory-consuming processes to inspect in-process"
            }
        ]

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
