"""
Thread-Safe SQLite Connection Pool & Busy Timeout Guard for Personal Agentic Fleet.
Eliminates database lock contention under multi-threading via thread-local connections.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional


class SQLiteConnectionPool:
    """
    Thread-local SQLite connection pool.
    Reuses an open connection per OS thread with busy_timeout=10000ms
    and WAL journal mode to prevent lock timeouts across threads.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = float(timeout)
        self._local = threading.local()
        self._all_connections: Dict[int, sqlite3.Connection] = {}
        self._lock = threading.Lock()

    def get_connection(self, db_path: Path) -> sqlite3.Connection:
        db_path = Path(db_path).resolve()
        thread_id = threading.get_ident()

        # Check if current thread has an active open connection for this db path
        conn = getattr(self._local, "conn", None)
        conn_path = getattr(self._local, "db_path", None)

        if conn is not None and conn_path == db_path:
            try:
                # Probe connection vitality
                conn.execute("SELECT 1")
                return conn
            except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                # Stale or closed connection, recreate
                pass

        # Ensure parent directory exists safely
        if not db_path.parent.exists():
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # Open new connection with busy timeout
        conn = sqlite3.connect(
            str(db_path),
            timeout=self.timeout,
            check_same_thread=True
        )
        conn.row_factory = sqlite3.Row

        # Configure high-concurrency pragmas
        try:
            conn.execute(f"PRAGMA busy_timeout = {int(self.timeout * 1000)}")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA secure_delete = ON")
        except Exception:
            pass

        self._local.conn = conn
        self._local.db_path = db_path

        with self._lock:
            self._all_connections[thread_id] = conn

        return conn

    def close_current_thread_connection(self) -> None:
        """Closes the current thread's connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
            self._local.db_path = None
            thread_id = threading.get_ident()
            with self._lock:
                self._all_connections.pop(thread_id, None)

    def close_all(self) -> None:
        """Closes all cached connections across all threads."""
        with self._lock:
            for thread_id, conn in list(self._all_connections.items()):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()


# Global singleton connection pool
_GLOBAL_POOL = SQLiteConnectionPool(timeout=10.0)


def get_pooled_connection(db_path: Path, timeout: float = 10.0) -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with busy timeout and WAL configuration."""
    return _GLOBAL_POOL.get_connection(db_path)


def close_all_pooled_connections() -> None:
    """Closes all pooled connections on shutdown."""
    _GLOBAL_POOL.close_all()
