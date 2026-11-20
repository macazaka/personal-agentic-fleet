"""
Thread-Safe SQLite Connection Pool & Busy Timeout Guard for Personal Agentic Fleet.
Eliminates database lock contention under multi-threading via thread-local connections.
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict


class SQLiteConnectionPool:
    """
    Thread-local SQLite connection pool.
    Reuses an open connection per OS thread with bounded RAM PRAGMAs,
    busy_timeout=15000ms, WAL journal mode, and automatic dead-thread pruning.
    """

    def __init__(self, timeout: float = 10.0, probe_ttl_sec: float = 15.0):
        self.timeout = float(timeout)
        self._probe_ttl_sec = float(probe_ttl_sec)
        self._local = threading.local()
        self._all_connections: Dict[int, sqlite3.Connection] = {}
        self._lock = threading.Lock()
        self._generation = 0
        self._checkout_count = 0
        self._pruned_dead_threads = 0
        self._skipped_health_probes = 0

    def get_connection(self, db_path: Path) -> sqlite3.Connection:
        from fleet.config import DB_PATH, TEST_DB_PATH
        from fleet.core.db.base import is_test_environment
        db_path = Path(db_path).resolve()
        if is_test_environment() and db_path == DB_PATH.resolve():
            db_path = TEST_DB_PATH.resolve()
        thread_id = threading.get_ident()
        now_mono = time.monotonic()

        # Check if current thread has an active open connection for this db path and pool generation
        conn = getattr(self._local, "conn", None)
        conn_path = getattr(self._local, "db_path", None)
        conn_gen = getattr(self._local, "generation", -1)

        if conn is not None and conn_path == db_path and conn_gen == self._generation:
            last_probe = getattr(self._local, "last_probe_ts", 0.0)
            if (now_mono - last_probe) < self._probe_ttl_sec:
                try:
                    # O(1) C-level open-handle verification without SQLite query overhead
                    _ = conn.in_transaction
                    self._skipped_health_probes += 1
                    with self._lock:
                        self._checkout_count += 1
                    return conn
                except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                    pass
            try:
                # Probe connection vitality after TTL expires
                conn.execute("SELECT 1")
                self._local.last_probe_ts = now_mono
                with self._lock:
                    self._checkout_count += 1
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

        # Configure high-concurrency and bounded-RAM pragmas (~4MB page cache cap per connection)
        try:
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -4096")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA wal_autocheckpoint = 400")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA secure_delete = ON")
        except Exception:
            pass

        self._local.conn = conn
        self._local.db_path = db_path
        self._local.last_probe_ts = now_mono
        self._local.generation = self._generation

        should_prune = False
        with self._lock:
            self._all_connections[thread_id] = conn
            self._checkout_count += 1
            if len(self._all_connections) > 12 or (self._checkout_count % 50 == 0):
                should_prune = True

        if should_prune:
            self.prune_dead_thread_connections()

        return conn

    def prune_dead_thread_connections(self) -> int:
        """Releases pooled SQLite references held by OS threads that have already exited."""
        alive_ids = {t.ident for t in threading.enumerate() if t.ident is not None}
        pruned_conns = []
        with self._lock:
            dead_ids = [tid for tid in self._all_connections if tid not in alive_ids]
            for tid in dead_ids:
                conn = self._all_connections.pop(tid, None)
                if conn is not None:
                    pruned_conns.append(conn)
            self._pruned_dead_threads += len(pruned_conns)

        # Release references (close fails on cross-thread check_same_thread=True, so dropping strong ref lets GC reclaim cleanly)
        for conn in pruned_conns:
            try:
                conn.close()
            except Exception:
                pass
        return len(pruned_conns)

    def get_pool_stats(self) -> Dict[str, Any]:
        """Returns real-time SQLite connection pool metrics."""
        with self._lock:
            return {
                "active_connections": len(self._all_connections),
                "checkout_count": self._checkout_count,
                "pruned_dead_threads": self._pruned_dead_threads,
                "skipped_health_probes": self._skipped_health_probes,
            }

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
            self._local.last_probe_ts = 0.0
            thread_id = threading.get_ident()
            with self._lock:
                self._all_connections.pop(thread_id, None)

    def close_all(self) -> None:
        """Closes all cached connections across all threads."""
        with self._lock:
            self._generation += 1
            for thread_id, conn in list(self._all_connections.items()):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        self._local.conn = None
        self._local.db_path = None
        self._local.last_probe_ts = 0.0
        self._local.generation = -1
        try:
            from fleet.core.db.base import clear_verified_schema_cache
            clear_verified_schema_cache()
        except Exception:
            pass


# Global singleton connection pool
_GLOBAL_POOL = SQLiteConnectionPool(timeout=10.0)


def get_pooled_connection(db_path: Path, timeout: float = 10.0) -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with busy timeout and bounded RAM configuration."""
    return _GLOBAL_POOL.get_connection(db_path)


def prune_dead_thread_connections() -> int:
    """Prunes pooled connections belonging to exited worker threads."""
    return _GLOBAL_POOL.prune_dead_thread_connections()


def get_pool_stats() -> Dict[str, Any]:
    """Returns connection pool telemetry."""
    return _GLOBAL_POOL.get_pool_stats()


def close_all_pooled_connections() -> None:
    """Closes all pooled connections on shutdown."""
    _GLOBAL_POOL.close_all()


# Backward-compatible alias
pool = _GLOBAL_POOL


