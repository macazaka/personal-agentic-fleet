"""
API Route Registry for Personal Agentic Fleet.
Imports all domain route handlers to register them on the central ApiRouter.
"""

from fleet.api.router import router

# Import domain modules to register routes
import fleet.api.tasks_api
import fleet.api.email_api
import fleet.api.health_api
import fleet.api.backlog_api
import fleet.api.optimizer_api
import fleet.api.antigravity_api
import fleet.api.system_api
import fleet.api.hyperscalers_api
import fleet.api.settings_api

__all__ = ["router"]

