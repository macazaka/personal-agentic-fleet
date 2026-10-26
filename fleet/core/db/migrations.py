"""
Zero-Dependency Database Schema Migration Engine for Personal Agentic Fleet.
Tracks schema versions via SQLite PRAGMA user_version with transactional migrations.
"""

import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


# Migration registry: (target_version, description, migration_function)
MIGRATIONS: List[Tuple[int, str, Callable[[sqlite3.Connection], None]]] = []


def migration(version: int, description: str):
    """Decorator to register a forward schema migration."""
    def decorator(fn: Callable[[sqlite3.Connection], None]):
        MIGRATIONS.append((version, description, fn))
        MIGRATIONS.sort(key=lambda m: m[0])
        return fn
    return decorator


@migration(1, "Initial baseline schema verification")
def migration_v1_baseline(conn: sqlite3.Connection):
    # Ensures baseline pragma settings
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")


@migration(2, "Add task execution audit timestamps & indexes")
def migration_v2_indexes(conn: sqlite3.Connection):
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
        ON tasks(status, priority)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_logs_created
        ON activity_logs(created_at)
    """)


@migration(3, "Add offline spool table for robust queueing")
def migration_v3_offline_spool(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offline_spool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)


def get_current_schema_version(conn: sqlite3.Connection) -> int:
    """Reads current PRAGMA user_version."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def apply_migrations(db_path: Path) -> Dict[str, Any]:
    """
    Applies any pending forward migrations sequentially in a single transaction.
    Updates PRAGMA user_version atomically on completion.
    """
    db_path = Path(db_path).resolve()
    if not db_path.exists():
        return {"status": "skipped", "message": "Database file does not exist yet."}

    conn = sqlite3.connect(str(db_path), timeout=15.0)
    current_version = get_current_schema_version(conn)
    applied_list: List[Dict[str, Any]] = []

    try:
        for ver, desc, fn in MIGRATIONS:
            if ver > current_version:
                with conn:
                    fn(conn)
                    conn.execute(f"PRAGMA user_version = {ver}")
                current_version = ver
                applied_list.append({"version": ver, "description": desc})

        conn.close()
        return {
            "status": "success",
            "current_version": current_version,
            "applied_count": len(applied_list),
            "applied": applied_list,
        }
    except Exception as exc:
        conn.close()
        return {
            "status": "error",
            "current_version": current_version,
            "error": str(exc),
            "applied": applied_list,
        }

