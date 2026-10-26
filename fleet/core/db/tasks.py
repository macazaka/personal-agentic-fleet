"""
Tasks & Routines domain repository mixin for FleetDatabase.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class TasksMixin:
    # --- Task Operations ---
    def add_task(self, title: str, description: str = "", priority: str = "P2",
                 due_date: Optional[str] = None, assigned_agent: str = "AgendaAgent",
                 source: Optional[str] = None) -> int:
        now = datetime.now().isoformat()
        clean_title = (title or "").strip()
        clean_desc = (description or "").strip()
        task_source = (source or assigned_agent or "Manual").strip()

        # In production workstation mode, strictly reject unit test task pollution
        if os.environ.get("FLEET_PRODUCTION_SERVER") == "1":
            s_low = task_source.lower()
            t_low = clean_title.lower()
            if s_low in ('e2e_test', 'testagent', 'pytest', 'unittest') or 'e2e deep' in t_low:
                return -1

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (title, description, source, priority, status, due_date, created_at, updated_at, assigned_agent)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """, (clean_title, clean_desc, task_source, priority.upper(), due_date, now, now, assigned_agent))
            conn.commit()
            task_id = cursor.lastrowid
            self.log_activity(assigned_agent, "add_task", f"Created task #{task_id}: {clean_title} [Source: {task_source}]")
            return task_id

    def list_tasks(self, status: Optional[str] = None, limit: int = 50, require_description: bool = True, exclude_tests: bool = True) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if require_description:
                conditions.append("description IS NOT NULL AND TRIM(description) != ''")

            if exclude_tests:
                conditions.append("""(
                    (source IS NULL OR (
                        LOWER(source) NOT IN ('test', 'unittest', 'pytest', 'testagent', 'e2e_test', 'test_runner')
                        AND LOWER(source) NOT LIKE '%test%'
                    ))
                    AND (title IS NULL OR (
                        LOWER(title) NOT LIKE '%test task%'
                        AND LOWER(title) NOT LIKE '%e2e deep verification%'
                        AND LOWER(title) NOT LIKE '%automated test task%'
                        AND LOWER(title) NOT LIKE '%unauthorized task%'
                    ))
                )""")

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            if status:
                cursor.execute(f"""
                    SELECT * FROM tasks {where_clause}
                    ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, id DESC
                    LIMIT ?
                """, (*params, limit))
            else:
                cursor.execute(f"""
                    SELECT * FROM tasks {where_clause}
                    ORDER BY CASE status WHEN 'pending' THEN 1 WHEN 'in_progress' THEN 2 ELSE 3 END,
                             CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, id DESC
                    LIMIT ?
                """, (*params, limit))
            rows = []
            for row in cursor.fetchall():
                d = dict(row)
                if not d.get("source"):
                    d["source"] = d.get("assigned_agent") or "Manual"
                rows.append(d)
            return rows


    def update_task_status(self, task_id: int, status: str) -> bool:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?
            """, (status, now, task_id))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                self.log_activity("AgendaAgent", "update_task", f"Task #{task_id} marked as {status}")
            return updated

    def delete_task(self, task_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                self.log_activity("AgendaAgent", "delete_task", f"Task #{task_id} deleted")
            return deleted


    # --- Routine & Habit Operations ---
    def list_routines(self) -> List[Dict[str, Any]]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM routines ORDER BY time_target ASC")
            routines = [dict(row) for row in cursor.fetchall()]
            for r in routines:
                r["completed_today"] = (r.get("last_completed_date") == today_str)
            return routines

    def toggle_routine(self, routine_id: int) -> bool:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM routines WHERE id = ?", (routine_id,))
            row = cursor.fetchone()
            if not row:
                return False
            is_today = (row["last_completed_date"] == today_str)
            new_date = "" if is_today else today_str
            cursor.execute("UPDATE routines SET last_completed_date = ? WHERE id = ?", (new_date, routine_id))
            conn.commit()
            action = "uncompleted" if is_today else "completed"
            self.log_activity("AgendaAgent", "routine_toggle", f"Routine '{row['title']}' marked {action} for today")
            return True

    def add_routine(self, title: str, time_target: str, category: str = "general") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO routines (title, time_target, category, last_completed_date)
                VALUES (?, ?, ?, '')
            """, (title, time_target, category))
            conn.commit()
            r_id = cursor.lastrowid
            self.log_activity("AgendaAgent", "add_routine", f"Added routine #{r_id}: {title} at {time_target}")
            return r_id

