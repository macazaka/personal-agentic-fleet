"""
Autonomous Improvements and Self-Healing domain repository mixin for FleetDatabase.
Tracks autonomous log analysis findings, proactive remediations, and performance metrics.
"""

from datetime import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional


class AutoImprovementsMixin:
    """Repository mixin for persisting and querying autonomous self-healing improvements."""

    def log_auto_improvement(
        self,
        scan_id: str,
        issue_type: str,
        severity: str,
        description: str,
        action_taken: str,
        status: str = "APPLIED",
        metrics_before: Optional[Dict[str, Any]] = None,
        metrics_after: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = datetime.now().isoformat()
        mb_json = json.dumps(metrics_before or {}, ensure_ascii=False)
        ma_json = json.dumps(metrics_after or {}, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO auto_improvements (
                    scan_id, issue_type, severity, description, action_taken, status, metrics_before, metrics_after, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                issue_type.upper(),
                severity.upper(),
                description,
                action_taken,
                status.upper(),
                mb_json,
                ma_json,
                now,
            ))
            conn.commit()
            item_id = cursor.lastrowid
            self.log_activity(
                "AutoHealer",
                "auto_improvement",
                f"[{status.upper()}] {issue_type}: {action_taken} ({severity})"
            )
            return item_id

    def list_auto_improvements(
        self,
        limit: int = 50,
        issue_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if issue_type and status:
                query = "SELECT * FROM auto_improvements WHERE issue_type = ? AND status = ? ORDER BY id DESC LIMIT ?"
                params = [issue_type.upper(), status.upper(), limit]
            elif issue_type:
                query = "SELECT * FROM auto_improvements WHERE issue_type = ? ORDER BY id DESC LIMIT ?"
                params = [issue_type.upper(), limit]
            elif status:
                query = "SELECT * FROM auto_improvements WHERE status = ? ORDER BY id DESC LIMIT ?"
                params = [status.upper(), limit]
            else:
                query = "SELECT * FROM auto_improvements ORDER BY id DESC LIMIT ?"
                params = [limit]

            cursor.execute(query, params)

            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["metrics_before"] = json.loads(d.get("metrics_before") or "{}")
                except Exception:
                    d["metrics_before"] = {}
                try:
                    d["metrics_after"] = json.loads(d.get("metrics_after") or "{}")
                except Exception:
                    d["metrics_after"] = {}
                results.append(d)
            return results

    def get_auto_improvements_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM auto_improvements")
            total = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM auto_improvements
                GROUP BY status
            """)
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT issue_type, COUNT(*) as count
                FROM auto_improvements
                GROUP BY issue_type
            """)
            by_type = {row["issue_type"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT created_at FROM auto_improvements ORDER BY id DESC LIMIT 1")
            last_row = cursor.fetchone()
            last_improvement = last_row["created_at"] if last_row else None

            return {
                "total_improvements": total,
                "by_status": by_status,
                "by_type": by_type,
                "last_improvement": last_improvement,
            }
