"""
Offline Network Detection & Event Spooling Engine for Personal Agentic Fleet.
Detects connectivity drops and spools outbound events in SQLite until restored.
"""

import json
import logging
import socket
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fleet.config import DB_PATH
from fleet.core.db.pool import get_pooled_connection

logger = logging.getLogger("fleet.network_spool")


def is_network_available(host: str = "1.1.1.1", port: int = 53, timeout: float = 1.5) -> bool:
    """
    Fast, zero-token probe checking whether the workstation has internet connectivity.
    Defaults to probing Cloudflare DNS port 53.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, OSError):
        return False


def _ensure_spool_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offline_spool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}',
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)


def spool_offline_event(target: str, action: str, payload: Optional[Dict[str, Any]] = None) -> int:
    """Spools an outbound event to SQLite while the system is offline."""
    now = datetime.now().isoformat()
    payload_json = json.dumps(payload or {})

    conn = get_pooled_connection(DB_PATH)
    with conn:
        _ensure_spool_table(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO offline_spool (target, action, payload_json, retry_count, created_at, status)
            VALUES (?, ?, ?, 0, ?, 'pending')
        """, (target, action, payload_json, now))
        spool_id = cursor.lastrowid

    logger.info(f"[OfflineSpool] Spooled event #{spool_id} [{target}:{action}] for offline deferral.")
    return spool_id


def list_spooled_events(status: str = "pending") -> List[Dict[str, Any]]:
    """Returns currently spooled offline events."""
    conn = get_pooled_connection(DB_PATH)
    _ensure_spool_table(conn)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, target, action, payload_json, retry_count, created_at, status
        FROM offline_spool
        WHERE status = ?
        ORDER BY id ASC
    """, (status,))
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "target": r["target"],
            "action": r["action"],
            "payload": json.loads(r["payload_json"]),
            "retry_count": r["retry_count"],
            "created_at": r["created_at"],
            "status": r["status"]
        })
    return results


def flush_offline_spool(event_bus) -> Dict[str, Any]:
    """
    Flushes all pending offline events through the Deterministic Event Bus
    once network connectivity has been restored.
    """
    if not is_network_available():
        return {"status": "skipped", "message": "Host is still offline."}

    spooled = list_spooled_events(status="pending")
    if not spooled:
        return {"status": "noop", "flushed_count": 0}

    flushed = 0
    failed = 0
    conn = get_pooled_connection(DB_PATH)

    from fleet.core.event_bus import FleetEvent

    for item in spooled:
        try:
            event = FleetEvent(
                sender="OfflineSpoolRecovery",
                target=item["target"],
                action=item["action"],
                payload=item["payload"]
            )
            res = event_bus.dispatch(event)
            with conn:
                conn.execute(
                    "UPDATE offline_spool SET status = 'completed' WHERE id = ?",
                    (item["id"],)
                )
            flushed += 1
        except Exception as e:
            logger.error(f"[OfflineSpool] Failed to flush event #{item['id']}: {e}")
            with conn:
                conn.execute(
                    "UPDATE offline_spool SET retry_count = retry_count + 1 WHERE id = ?",
                    (item["id"],)
                )
            failed += 1

    return {"status": "success", "flushed_count": flushed, "failed_count": failed}
