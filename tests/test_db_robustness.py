"""
Unit tests for Database Robustness: Connection Pooling, Backups, and Migrations.
"""

import sqlite3
import threading
from pathlib import Path

from fleet.core.db.pool import SQLiteConnectionPool, get_pooled_connection
from fleet.core.db.backup import perform_database_backup, verify_backup_integrity, prune_old_backups
from fleet.core.db.migrations import apply_migrations, get_current_schema_version


def test_sqlite_connection_pool(tmp_path):
    db_file = tmp_path / "pool_test.db"
    pool = SQLiteConnectionPool(timeout=5.0)

    # Main thread connection
    conn1 = pool.get_connection(db_file)
    conn1.execute("CREATE TABLE test_data (id INT, val TEXT)")
    conn1.execute("INSERT INTO test_data VALUES (1, 'hello')")
    conn1.commit()

    # Worker thread connection
    worker_conns = []
    def worker():
        c = pool.get_connection(db_file)
        row = c.execute("SELECT val FROM test_data WHERE id=1").fetchone()
        worker_conns.append((c, row[0]))

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert len(worker_conns) == 1
    worker_conn, val = worker_conns[0]
    assert val == "hello"
    # Thread-local: different connection objects across threads
    assert worker_conn is not conn1

    pool.close_all()


def test_database_backup_and_integrity(tmp_path):
    db_file = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"

    # Create dummy database
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE items (id INT PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items VALUES (101, 'Alpha')")
    conn.execute("INSERT INTO items VALUES (102, 'Beta')")
    conn.commit()
    conn.close()

    # Perform backup
    res = perform_database_backup(source_db_path=db_file, backup_dir=backup_dir, max_retained=3)
    assert res["status"] == "success"
    assert res["integrity_verified"] is True
    assert len(res["sha256"]) == 64
    assert Path(res["backup_file"]).is_file()

    # Verify backup integrity function directly
    assert verify_backup_integrity(Path(res["backup_file"])) is True

    # Check pruning
    for i in range(5):
        dummy = backup_dir / f"fleet_backup_2026010{i}_000000.db"
        dummy.write_text("dummy")

    pruned = prune_old_backups(backup_dir, max_retained=3)
    assert pruned > 0


def test_schema_migrations(tmp_path):
    db_file = tmp_path / "migrate_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE tasks (id INT, title TEXT, status TEXT, priority TEXT)")
    conn.execute("CREATE TABLE activity_logs (id INT, created_at TEXT)")
    conn.commit()
    conn.close()

    res = apply_migrations(db_file)
    assert res["status"] == "success"
    assert res["current_version"] >= 3

    # Verify tables & indexes exist
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='offline_spool'")
    assert cur.fetchone() is not None
    conn.close()
