"""
Feature Backlog domain repository mixin for FleetDatabase.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class BacklogMixin:
    # --- Feature Backlog Operations ---
    def add_feature_backlog_item(self, title: str, description: str = "",
                                 category: str = "Core", priority: str = "P2",
                                 status: str = "Idea", target_version: str = "v1.4.0") -> int:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feature_backlog (title, description, category, priority, status, target_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title.strip(), description.strip(), category, priority, status, target_version, now, now))
            conn.commit()
            return cursor.lastrowid

    def list_feature_backlog_items(self, status: Optional[str] = None,
                                   category: Optional[str] = None,
                                   target_version: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM feature_backlog WHERE 1=1"
        params: List[Any] = []
        if status and status.lower() != "all":
            query += " AND status = ?"
            params.append(status)
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category)
        if target_version and target_version.lower() != "all":
            query += " AND target_version = ?"
            params.append(target_version)

        query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, id DESC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_feature_backlog_item(self, item_id: int, **kwargs) -> bool:
        allowed = {"title", "description", "category", "priority", "status", "target_version"}
        fields = []
        params = []
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(item_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE feature_backlog SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0

    def delete_feature_backlog_item(self, item_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feature_backlog WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_feature_backlog_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as count FROM feature_backlog GROUP BY status")
            counts = {row["status"]: row["count"] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) as total FROM feature_backlog")
            total = cursor.fetchone()["total"]
            return {
                "total": total,
                "idea": counts.get("Idea", 0),
                "planned": counts.get("Planned", 0),
                "in_progress": counts.get("In Progress", 0),
                "completed": counts.get("Completed", 0),
                "deferred": counts.get("Deferred", 0)
            }

