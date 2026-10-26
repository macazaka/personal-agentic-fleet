"""
Automated Daily Snapshot Backup & Corruption Recovery Engine for Personal Agentic Fleet.
Performs non-blocking online SQLite backups with SHA-256 integrity verification.
"""

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fleet.config import DATA_DIR, DB_PATH

BACKUPS_DIR = DATA_DIR / "backups"


def perform_database_backup(
    source_db_path: Path = DB_PATH,
    backup_dir: Path = BACKUPS_DIR,
    max_retained: int = 7
) -> Dict[str, Any]:
    """
    Performs a consistent online SQLite backup using the standard sqlite3.backup API.
    Computes SHA-256 digest, checks integrity, and prunes older backups.
    """
    source_path = Path(source_db_path).resolve()
    target_dir = Path(backup_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.is_file():
        return {
            "status": "skipped",
            "message": f"Source database '{source_path}' does not exist yet.",
            "timestamp": datetime.now().isoformat(),
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"fleet_backup_{timestamp}.db"
    backup_path = target_dir / backup_filename

    # Execute SQLite online backup
    start_time = time.time()
    source_conn = sqlite3.connect(str(source_path), timeout=15.0)
    target_conn = sqlite3.connect(str(backup_path), timeout=15.0)

    try:
        with target_conn:
            source_conn.backup(target_conn, pages=100)
    finally:
        source_conn.close()
        target_conn.close()

    duration_ms = round((time.time() - start_time) * 1000, 2)

    # Compute cryptographic SHA-256 digest
    sha256 = hashlib.sha256()
    with open(backup_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    digest = sha256.hexdigest()

    # Append to checksums manifest
    checksum_file = target_dir / "checksums.sha256"
    with open(checksum_file, "a", encoding="utf-8") as f:
        f.write(f"{digest}  {backup_filename}\n")

    # Verify backup integrity
    integrity_ok = verify_backup_integrity(backup_path)

    # Automatic FIFO pruning: keep latest `max_retained` backups
    pruned_count = prune_old_backups(target_dir, max_retained=max_retained)

    return {
        "status": "success" if integrity_ok else "warn",
        "backup_file": str(backup_path),
        "filename": backup_filename,
        "size_bytes": backup_path.stat().st_size,
        "sha256": digest,
        "integrity_verified": integrity_ok,
        "duration_ms": duration_ms,
        "pruned_backups": pruned_count,
        "timestamp": datetime.now().isoformat(),
    }


def verify_backup_integrity(backup_path: Path) -> bool:
    """Runs PRAGMA quick_check on backup database to verify zero corruption."""
    try:
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check")
        res = cursor.fetchone()
        conn.close()
        return bool(res and res[0] == "ok")
    except Exception:
        return False


def prune_old_backups(backup_dir: Path, max_retained: int = 7) -> int:
    """Removes oldest backups beyond the retention ceiling."""
    if not backup_dir.is_dir():
        return 0

    backups = sorted(
        [f for f in backup_dir.glob("fleet_backup_*.db") if f.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    pruned = 0
    if len(backups) > max_retained:
        for old_backup in backups[max_retained:]:
            try:
                old_backup.unlink()
                pruned += 1
            except Exception:
                pass

    return pruned


def list_backups(backup_dir: Path = BACKUPS_DIR) -> List[Dict[str, Any]]:
    """Returns metadata for all available backups."""
    if not backup_dir.is_dir():
        return []

    backups = sorted(
        [f for f in backup_dir.glob("fleet_backup_*.db") if f.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    items = []
    for b in backups:
        items.append({
            "filename": b.name,
            "path": str(b),
            "size_bytes": b.stat().st_size,
            "created_at": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
        })
    return items

