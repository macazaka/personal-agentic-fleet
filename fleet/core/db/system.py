"""
System preferences, activity logging, test run metrics, and token vault mixin for FleetDatabase.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


class SystemMixin(_DbBase):
    # --- Memory Operations ---
    def set_memory(self, category: str, key: str, value: str):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memories (category, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    category = excluded.category,
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (category, key, value, now))
            conn.commit()
            self.log_activity("Orchestrator", "set_memory", f"Stored memory: [{category}] {key} = {value}")

    def get_memory(self, key: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM memories WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def list_memories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("SELECT * FROM memories WHERE category = ? ORDER BY key ASC", (category,))
            else:
                cursor.execute("SELECT * FROM memories ORDER BY category ASC, key ASC")
            return [dict(row) for row in cursor.fetchall()]

    # --- Notes Operations ---
    def add_note(self, title: str, content: str, tags: str = "") -> int:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes (title, content, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (title, content, tags, now, now))
            conn.commit()
            note_id = cursor.lastrowid or 0
            self.log_activity("NotesAgent", "add_note", f"Added note #{note_id}: {title}")
            return note_id

    def search_notes(self, query: str) -> List[Dict[str, Any]]:
        like_query = f"%{query}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notes 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC LIMIT 20
            """, (like_query, like_query, like_query))
            return [dict(row) for row in cursor.fetchall()]

    def list_notes(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Activity Log Operations ---
    def log_activity(self, agent: str, action: str, details: str = "") -> None:
        # In production workstation mode, strictly reject unit test logging
        if os.environ.get("FLEET_PRODUCTION_SERVER") == "1":
            ag_low = (agent or "").lower()
            ac_low = (action or "").lower()
            dt_low = (details or "").lower()
            if ag_low in ('testagent', 'e2e_test', 'pytest', 'testrunner', 'tester'):
                return
            if ac_low in ('test_run', 'run_test_suite'):
                return
            if 'e2e deep' in dt_low or 'test task' in dt_low:
                return

        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (agent, action, details, timestamp)
                VALUES (?, ?, ?, ?)
            """, (agent, action, details, now))
            conn.commit()

    def get_recent_activities(self, limit: int = 25, exclude_tests: bool = True) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if exclude_tests:
                cursor.execute("""
                    SELECT * FROM activity_logs 
                    WHERE (agent IS NULL OR (
                        LOWER(agent) NOT IN ('testagent', 'e2e_test', 'pytest', 'testrunner', 'tester')
                        AND LOWER(agent) NOT LIKE '%test%'
                    ))
                    AND (action IS NULL OR (
                        LOWER(action) NOT IN ('test_run', 'run_test_suite')
                        AND LOWER(action) NOT LIKE '%test%'
                    ))
                    AND (details IS NULL OR (
                        LOWER(details) NOT LIKE '%e2e deep verification%'
                        AND LOWER(details) NOT LIKE '%test task%'
                        AND LOWER(details) NOT LIKE '%ran test%'
                        AND LOWER(details) NOT LIKE '%passed test%'
                    ))
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]


    # --- Test Suite Metrics ---
    def save_test_run(self, total_tests: int, passed_tests: int, failed_tests: int,
                      pass_pct: float, coverage_pct: float, duration_sec: float,
                      status: str, details_json: str = "{}") -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_runs (timestamp, total_tests, passed_tests, failed_tests,
                                       pass_pct, coverage_pct, duration_sec, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, total_tests, passed_tests, failed_tests, pass_pct, coverage_pct, duration_sec, status, details_json))
            conn.commit()
            return cursor.lastrowid or 0

    def get_latest_test_run(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_runs ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_test_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_runs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Settings / Key-Value Preferences ---
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings ORDER BY key ASC")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # --- Chat Message Queue ---
    def enqueue_chat_message(self, prompt: str, images: Optional[List[str]] = None,
                             model: str = "gemini-3.8-flash-high") -> int:
        now = datetime.now().isoformat()
        images_json = json.dumps(images or [])
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_queue (prompt, images_json, model, status, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', ?, ?)
            """, (prompt, images_json, model, now, now))
            conn.commit()
            return cursor.lastrowid or 0

    def get_queued_chat_messages(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_queue WHERE status = 'queued' ORDER BY id ASC")
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["images"] = json.loads(d.get("images_json", "[]"))
                results.append(d)
            return results

    def get_next_queued_chat_message(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_queue WHERE status = 'queued' ORDER BY id ASC LIMIT 1")
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["images"] = json.loads(d.get("images_json", "[]"))
                return d
            return None

    def get_next_n_queued_chat_messages(self, limit: int = 4) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_queue WHERE status = 'queued' ORDER BY id ASC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["images"] = json.loads(d.get("images_json", "[]"))
                results.append(d)
            return results

    def update_chat_queue_status(self, queue_id: int, status: str) -> bool:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chat_queue SET status = ?, updated_at = ? WHERE id = ?
            """, (status, now, queue_id))
            conn.commit()
            return cursor.rowcount > 0

    def cancel_queued_chat_message(self, queue_id: int) -> bool:
        return self.update_chat_queue_status(queue_id, "cancelled")


    # --- Token Preservation Vault Operations ---
    def vault_pending_prompts(self, session_id: str = "current", model: str = "default",
                              tokens_used: int = 0, token_limit: int = 1000000,
                              reason: str = "Token limit reached") -> int:
        """
        Safely vaults all pending or in-flight chat queue messages so work and prompts are never lost.
        """
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_queue WHERE status IN ('queued', 'processing')")
            pending = [dict(row) for row in cursor.fetchall()]

            cursor.execute("UPDATE chat_queue SET status = 'vaulted', updated_at = ? WHERE status IN ('queued', 'processing')", (now_str,))
            
            cursor.execute("""
                INSERT INTO token_preservation_vault
                (session_id, model, tokens_used, token_limit, status, reason, preserved_prompts_json, created_at)
                VALUES (?, ?, ?, ?, 'exhausted', ?, ?, ?)
            """, (session_id, model, tokens_used, token_limit, reason, json.dumps(pending), now_str))
            conn.commit()
            return len(pending)

    def resume_vaulted_prompts(self, fallback_model: Optional[str] = None) -> int:
        """
        Re-activates vaulted prompts back to 'queued' state with optional fallback model.
        """
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if fallback_model:
                cursor.execute("""
                    UPDATE chat_queue
                    SET status = 'queued', model = ?, updated_at = ?
                    WHERE status = 'vaulted'
                """, (fallback_model, now_str))
            else:
                cursor.execute("""
                    UPDATE chat_queue
                    SET status = 'queued', updated_at = ?
                    WHERE status = 'vaulted'
                """, (now_str,))
            resumed_count = cursor.rowcount
            conn.commit()
            return resumed_count

    def get_vaulted_prompts(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_queue WHERE status = 'vaulted' ORDER BY id ASC")
            items = []
            for row in cursor.fetchall():
                d = dict(row)
                try:
                    d["images"] = json.loads(d.get("images_json", "[]"))
                except Exception:
                    d["images"] = []
                items.append(d)
            return items

    def get_latest_token_vault_event(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM token_preservation_vault ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["preserved_prompts"] = json.loads(d.get("preserved_prompts_json", "[]"))
            except Exception:
                d["preserved_prompts"] = []
            return d

    # --- Custom Agent Records, Checklists & Live Workspace State (Phase 1 & 2) ---
    def add_custom_agent_record(
        self,
        agent_id: str,
        title: str,
        record_type: str = "entry",
        data: Optional[Dict[str, Any]] = None,
        status: str = "ok",
        due_date: str = "",
        numeric_value: float = 0.0,
    ) -> int:
        now_str = datetime.now().isoformat()
        payload_dict = dict(data or {})
        eff_due = str(due_date or "").strip()
        eff_num = float(numeric_value or 0.0)

        if not eff_due:
            for k, v in payload_dict.items():
                s_val = str(v or "").strip()
                if len(s_val) == 10 and s_val[4:5] == "-" and s_val[7:8] == "-":
                    eff_due = s_val
                    break
        if eff_num == 0.0:
            for k, v in payload_dict.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    eff_num = float(v)
                    break
                try:
                    s_num = str(v or "").strip().replace(",", "")
                    if s_num and s_num.replace(".", "", 1).lstrip("-").isdigit() and "date" not in k.lower():
                        eff_num = float(s_num)
                        break
                except Exception:
                    pass

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO custom_agent_records
                (agent_id, record_type, title, data_json, status, due_date, numeric_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(agent_id),
                    str(record_type or "entry"),
                    str(title or "Record"),
                    json.dumps(payload_dict),
                    str(status or "ok"),
                    eff_due,
                    eff_num,
                    now_str,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def list_custom_agent_records(
        self,
        agent_id: str,
        record_type: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if record_type:
                cursor.execute(
                    """
                    SELECT * FROM custom_agent_records
                    WHERE agent_id = ? AND record_type = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (str(agent_id), str(record_type), int(limit)),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM custom_agent_records
                    WHERE agent_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (str(agent_id), int(limit)),
                )
            out: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                item = dict(row)
                try:
                    item["data"] = json.loads(item.get("data_json") or "{}")
                except Exception:
                    item["data"] = {}
                out.append(item)
            return out

    def update_custom_agent_record(
        self,
        agent_id: str,
        record_id: int,
        title: Optional[str] = None,
        due_date: Optional[str] = None,
        numeric_value: Optional[float] = None,
        status: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM custom_agent_records WHERE agent_id = ? AND id = ?",
                (str(agent_id), int(record_id)),
            )
            row = cursor.fetchone()
            if not row:
                return False
            curr = dict(row)
            try:
                curr_data = json.loads(curr.get("data_json") or "{}")
                if not isinstance(curr_data, dict):
                    curr_data = {}
            except Exception:
                curr_data = {}

            if isinstance(data, dict):
                for k, v in data.items():
                    if v is None:
                        curr_data.pop(k, None)
                    else:
                        curr_data[k] = v

            new_title = str(title).strip() if title is not None and str(title).strip() else str(curr.get("title") or "Record")
            new_due = str(due_date).strip() if due_date is not None else str(curr.get("due_date") or "")
            new_num = float(numeric_value) if numeric_value is not None else float(curr.get("numeric_value") or 0.0)
            new_status = str(status).strip() if status is not None and str(status).strip() else str(curr.get("status") or "ok")

            cursor.execute(
                """
                UPDATE custom_agent_records
                SET title = ?, due_date = ?, numeric_value = ?, status = ?, data_json = ?
                WHERE agent_id = ? AND id = ?
                """,
                (
                    new_title,
                    new_due,
                    new_num,
                    new_status,
                    json.dumps(curr_data),
                    str(agent_id),
                    int(record_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_custom_agent_record(self, agent_id: str, record_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM custom_agent_records WHERE agent_id = ? AND id = ?",
                (str(agent_id), int(record_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_custom_agent_data(self, agent_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_agent_records WHERE agent_id = ?", (str(agent_id),))
            cursor.execute("DELETE FROM custom_agent_checklists WHERE agent_id = ?", (str(agent_id),))
            conn.commit()

    def get_custom_agent_checklist(
        self,
        agent_id: str,
        default_items: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM custom_agent_checklists WHERE agent_id = ? ORDER BY id ASC",
                (str(agent_id),),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            if not rows and default_items:
                for idx, lbl in enumerate(default_items):
                    clean_lbl = str(lbl).strip()
                    if not clean_lbl:
                        continue
                    ikey = f"item_{idx + 1}"
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO custom_agent_checklists
                        (agent_id, item_key, label, checked, last_checked_date, streak)
                        VALUES (?, ?, ?, 0, '', 0)
                        """,
                        (str(agent_id), ikey, clean_lbl),
                    )
                conn.commit()
                cursor.execute(
                    "SELECT * FROM custom_agent_checklists WHERE agent_id = ? ORDER BY id ASC",
                    (str(agent_id),),
                )
                rows = [dict(r) for r in cursor.fetchall()]

            for r in rows:
                r["checked"] = bool(r.get("checked")) and (r.get("last_checked_date") == today_str)
            return rows

    def toggle_custom_agent_checklist_item(
        self,
        agent_id: str,
        item_key: str,
        label: str = "",
        checked: Optional[bool] = None,
    ) -> Dict[str, Any]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM custom_agent_checklists WHERE agent_id = ? AND item_key = ?",
                (str(agent_id), str(item_key)),
            )
            row = cursor.fetchone()
            if not row:
                new_checked = True if checked is None else bool(checked)
                streak = 1 if new_checked else 0
                cursor.execute(
                    """
                    INSERT INTO custom_agent_checklists
                    (agent_id, item_key, label, checked, last_checked_date, streak)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(agent_id),
                        str(item_key),
                        str(label or item_key),
                        1 if new_checked else 0,
                        today_str if new_checked else "",
                        streak,
                    ),
                )
            else:
                curr = dict(row)
                is_checked_today = bool(curr.get("checked")) and (curr.get("last_checked_date") == today_str)
                new_checked = (not is_checked_today) if checked is None else bool(checked)
                prev_streak = int(curr.get("streak") or 0)
                if new_checked and not is_checked_today:
                    new_streak = prev_streak + 1
                elif not new_checked and is_checked_today:
                    new_streak = max(0, prev_streak - 1)
                else:
                    new_streak = prev_streak
                cursor.execute(
                    """
                    UPDATE custom_agent_checklists
                    SET checked = ?, last_checked_date = ?, streak = ?, label = COALESCE(NULLIF(?, ''), label)
                    WHERE agent_id = ? AND item_key = ?
                    """,
                    (
                        1 if new_checked else 0,
                        today_str if new_checked else "",
                        new_streak,
                        str(label or ""),
                        str(agent_id),
                        str(item_key),
                    ),
                )
            conn.commit()
        items = self.get_custom_agent_checklist(agent_id)
        return next((x for x in items if x["item_key"] == item_key), {"item_key": item_key, "checked": bool(checked)})

    def get_custom_agent_dashboard_state(
        self,
        agent_id: str,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        mf = manifest or {}
        default_checks = mf.get("checklist_items") if isinstance(mf.get("checklist_items"), list) else None
        all_records = self.list_custom_agent_records(agent_id, limit=80)
        entries = [r for r in all_records if r.get("record_type") == "entry"]
        runs = [r for r in all_records if r.get("record_type") == "run"]
        insights = [r for r in all_records if r.get("record_type") == "ai_insight"]
        documents = [r for r in all_records if r.get("record_type") == "document"]
        cycle_history = [r for r in all_records if r.get("record_type") == "cycle_history"]
        chat_history = list(reversed([r for r in all_records if r.get("record_type") == "chat"][:12]))
        checklist = self.get_custom_agent_checklist(agent_id, default_items=default_checks)

        today = datetime.now().date()
        countdowns: List[Dict[str, Any]] = []
        urgent_count = 0
        completed_entries_count = 0
        numeric_sum = 0.0
        for rec in entries:
            rec_status = str(rec.get("status") or "ok").strip().lower()
            is_done = rec_status in ("completed", "done", "resolved")
            if is_done:
                completed_entries_count += 1
            try:
                numeric_sum += float(rec.get("numeric_value") or 0.0)
            except (TypeError, ValueError):
                pass
            due = str(rec.get("due_date") or "").strip()
            if due:
                try:
                    due_dt = datetime.strptime(due[:10], "%Y-%m-%d").date()
                    days_left = (due_dt - today).days
                    if is_done:
                        urgency = "completed"
                    else:
                        urgency = (
                            "overdue"
                            if days_left < 0
                            else ("due_soon" if days_left <= 15 else ("soon" if days_left <= 30 else "safe"))
                        )
                        if days_left <= 15:
                            urgent_count += 1
                    countdowns.append({
                        "id": rec["id"],
                        "title": rec["title"],
                        "due_date": due[:10],
                        "days_left": days_left,
                        "urgency": urgency,
                        "status": rec_status,
                        "is_completed": is_done,
                        "numeric_value": rec.get("numeric_value", 0.0),
                        "data": rec.get("data", {}),
                    })
                except Exception:
                    pass
        countdowns.sort(key=lambda x: (1 if x.get("is_completed") else 0, x["days_left"]))
        numeric_sum = round(numeric_sum, 2)

        completed_checks = sum(1 for c in checklist if c.get("checked"))
        max_streak = max([int(c.get("streak") or 0) for c in checklist], default=0)
        last_run = runs[0] if runs else None
        last_status = last_run.get("status") if last_run else "ready"

        return {
            "status": "ok",
            "agent_id": agent_id,
            "kpis": {
                "total_entries": len(entries),
                "entries_count": len(entries),
                "completed_entries": completed_entries_count,
                "documents_count": len(documents),
                "renewals_count": len(cycle_history),
                "total_runs": len(runs),
                "runs_count": len(runs),
                "due_soon": urgent_count,
                "urgent_alerts": urgent_count,
                "numeric_sum": numeric_sum,
                "checklist_done": completed_checks,
                "checklist_total": len(checklist),
                "max_streak": max_streak,
                "last_status": last_status,
                "last_run_status": last_status,
                "last_run_at": (last_run.get("created_at") if last_run else ""),
            },
            "checklist_done": completed_checks,
            "checklist_total": len(checklist),
            "checklist_streak": max_streak,
            "entries": entries[:25],
            "runs": runs[:15],
            "countdowns": countdowns[:12],
            "documents": documents[:15],
            "cycle_history": cycle_history[:20],
            "chat_history": chat_history,
            "latest_insight": insights[0] if insights else None,
            "checklist": checklist,
        }

    def get_custom_agents_fleet_rollup(
        self,
        custom_manifests: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Phase 4: $0.00 SQLite Fleet-wide Rollup across all custom Studio agents.
        Surfaces urgent renewals/deadlines (<= 15 days and not completed) and recent warning runs
        into the Morning Briefing & Overview dashboard.
        """
        meta_by_id: Dict[str, Dict[str, str]] = {}
        if custom_manifests is not None:
            for m in custom_manifests:
                if isinstance(m, dict) and m.get("id"):
                    aid = str(m["id"])
                    meta_by_id[aid] = {
                        "name": str(m.get("name") or aid),
                        "icon": str(m.get("icon") or "✨"),
                    }
            if not meta_by_id:
                return {
                    "custom_agents_count": 0,
                    "total_alerts": 0,
                    "urgent_items": [],
                    "warning_runs": [],
                    "alerts": [],
                }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM custom_agent_records ORDER BY id DESC LIMIT 500"
            )
            all_rows = [dict(r) for r in cursor.fetchall()]

        if custom_manifests is not None:
            rows = [r for r in all_rows if str(r.get("agent_id") or "") in meta_by_id]
        else:
            rows = all_rows

        today = datetime.now().date()
        urgent_items: List[Dict[str, Any]] = []
        latest_run_seen: set[str] = set()
        warning_runs: List[Dict[str, Any]] = []
        urgent_agents_seen: set[str] = set()

        for r in rows:
            aid = str(r.get("agent_id") or "")
            if not aid:
                continue
            ag_info = meta_by_id.get(aid, {"name": aid.replace("_", " ").title(), "icon": "✨"})
            rtype = str(r.get("record_type") or "entry")
            rstatus = str(r.get("status") or "ok").strip().lower()

            if rtype == "entry" and rstatus not in ("completed", "done", "resolved"):
                due = str(r.get("due_date") or "").strip()
                if due:
                    try:
                        due_dt = datetime.strptime(due[:10], "%Y-%m-%d").date()
                        days_left = (due_dt - today).days
                        if days_left <= 15:
                            urgency = "overdue" if days_left < 0 else "due_soon"
                            urgent_agents_seen.add(aid)
                            urgent_items.append({
                                "kind": "deadline",
                                "record_id": r["id"],
                                "agent_id": aid,
                                "agent_name": ag_info["name"],
                                "agent_icon": ag_info["icon"],
                                "title": str(r.get("title") or "Item"),
                                "due_date": due[:10],
                                "days_left": days_left,
                                "urgency": urgency,
                                "numeric_value": float(r.get("numeric_value") or 0.0),
                            })
                    except Exception:
                        pass
            elif rtype == "run" and aid not in latest_run_seen:
                latest_run_seen.add(aid)
                if rstatus == "warning":
                    warning_runs.append({
                        "kind": "warning_run",
                        "record_id": r["id"],
                        "agent_id": aid,
                        "agent_name": ag_info["name"],
                        "agent_icon": ag_info["icon"],
                        "title": str(r.get("title") or "Warning detected"),
                        "created_at": str(r.get("created_at") or ""),
                        "urgency": "warning",
                    })

        urgent_items.sort(key=lambda x: x["days_left"])
        # Avoid double-alerting a warning_run when that agent already has explicit urgent_items surfaced
        dedup_warnings = [w for w in warning_runs if w["agent_id"] not in urgent_agents_seen]
        combined_alerts = (urgent_items + dedup_warnings)[:12]

        return {
            "custom_agents_count": len(meta_by_id) if custom_manifests is not None else len({str(r.get("agent_id")) for r in rows if r.get("agent_id")}),
            "total_alerts": len(urgent_items) + len(dedup_warnings),
            "urgent_items": urgent_items[:12],
            "warning_runs": dedup_warnings[:8],
            "alerts": combined_alerts,
        }


