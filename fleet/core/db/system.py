"""
System preferences, activity logging, test run metrics, and token vault mixin for FleetDatabase.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class SystemMixin:
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
            note_id = cursor.lastrowid
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
    def log_activity(self, agent: str, action: str, details: str):
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
            return cursor.lastrowid

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
            return cursor.lastrowid

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

