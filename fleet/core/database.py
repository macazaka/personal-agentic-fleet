"""
Database management for Personal Agentic Fleet.
Provides persistent storage using SQLite for tasks, memories, notes, activity logs, health metrics, and classified emails cache.

Modular Architecture:
- Base connection & self-healing schema: fleet/core/db/base.py
- Tasks & Habits: fleet/core/db/tasks.py
- Health & Wellness: fleet/core/db/health.py
- Emails & Cache: fleet/core/db/emails.py
- Feature Backlog: fleet/core/db/backlog.py
- System, Activity & Vault: fleet/core/db/system.py
"""

from pathlib import Path
from typing import Optional

from fleet.config import DATA_DIR, DB_PATH, TEST_DB_PATH
from fleet.core.db import (
    BaseDatabase,
    TasksMixin,
    HealthMixin,
    EmailsMixin,
    BacklogMixin,
    SystemMixin,
    AutoImprovementsMixin,
    MindMixin,
    is_test_environment,
    get_effective_db_path,
)


class FleetDatabase(
    TasksMixin,
    HealthMixin,
    EmailsMixin,
    BacklogMixin,
    SystemMixin,
    AutoImprovementsMixin,
    MindMixin,
    BaseDatabase
):
    """
    Unified persistent SQLite repository for Personal Agentic Fleet.
    Composed of specialized domain mixins for zero token bloat and modular maintainability.
    """
    def __init__(self, db_path: Optional[Path] = None):
        super().__init__(db_path=db_path)


__all__ = [
    "FleetDatabase",
    "is_test_environment",
    "get_effective_db_path",
    "DATA_DIR",
    "DB_PATH",
    "TEST_DB_PATH",
]
