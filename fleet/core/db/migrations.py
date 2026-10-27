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


@migration(4, "Add auto_improvements table for autonomous log self-healing")
def migration_v4_auto_improvements(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auto_improvements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            status TEXT NOT NULL,
            metrics_before TEXT DEFAULT '{}',
            metrics_after TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_auto_improvements_created
        ON auto_improvements(created_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_auto_improvements_type_status
        ON auto_improvements(issue_type, status)
    """)


@migration(5, "Add cognitive mind tables: critiques, dream insights & soul audits")
def migration_v5_cognitive_mind(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mind_critiques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            critique_score REAL NOT NULL,
            critique_notes TEXT NOT NULL,
            corrective_action TEXT DEFAULT '',
            input_summary TEXT DEFAULT '',
            output_summary TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mind_critiques_created
        ON mind_critiques(created_at)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mind_dream_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            source_events_count INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            actionable_recommendation TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mind_dream_created
        ON mind_dream_insights(created_at)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mind_soul_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT NOT NULL,
            alignment_score REAL NOT NULL,
            violations_count INTEGER DEFAULT 0,
            violations_json TEXT DEFAULT '[]',
            recommendations_json TEXT DEFAULT '[]',
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mind_soul_created
        ON mind_soul_audits(created_at)
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
                    conn.execute("PRAGMA user_version = %d" % int(ver))
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

