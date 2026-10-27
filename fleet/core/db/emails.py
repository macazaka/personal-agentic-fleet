"""
Classified Emails cache & unsubscription state mixin for FleetDatabase.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


class EmailsMixin(_DbBase):
    # --- Unsubscribed Email Operations ---
    def record_unsubscribed_email(self, message_id: str, sender: str = "",
                                  subject: str = "", unsubscribe_url: str = "") -> int:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO unsubscribed_emails (message_id, sender, subject, unsubscribe_url, unsubscribed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    sender = excluded.sender,
                    subject = excluded.subject,
                    unsubscribe_url = excluded.unsubscribe_url,
                    unsubscribed_at = excluded.unsubscribed_at
            """, (message_id, sender, subject, unsubscribe_url, now_str))
            conn.commit()
            return cursor.lastrowid or 0

    def is_email_unsubscribed(self, message_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM unsubscribed_emails WHERE message_id = ?", (message_id,))
            return cursor.fetchone() is not None

    def list_unsubscribed_emails(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM unsubscribed_emails ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]


    # --- Classified Emails Cache Operations ---
    def save_classified_emails(self, emails: List[Dict[str, Any]]) -> int:
        """
        Saves or updates classified emails in the local cache table.
        Ensures zero-token deterministic caching so repeated queries do not reload or re-classify.
        """
        if not emails:
            return 0
        now_str = datetime.now().isoformat()
        saved = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for em in emails:
                msg_id = str(em.get("id") or em.get("message_id") or "").strip()
                if not msg_id:
                    continue
                subject = em.get("subject", "")
                sender = em.get("from") or em.get("sender", "")
                snippet = em.get("snippet", "")
                body = em.get("body", "") or snippet
                cat_id = int(em.get("category_id", 4))
                cat_name = em.get("category_name", "Ignore")
                reason = em.get("reason", "")
                can_unsub = 1 if em.get("can_unsubscribe") else 0
                unsub_url = em.get("unsubscribe_url") or ""
                unsub_type = em.get("unsubscribe_type") or ""
                unsub = 1 if em.get("unsubscribed") else 0
                received_date = em.get("date") or em.get("received_date") or now_str

                cursor.execute("""
                    INSERT INTO classified_emails (
                        message_id, subject, sender, snippet, body, category_id, category_name,
                        reason, can_unsubscribe, unsubscribe_url, unsubscribe_type, unsubscribed,
                        received_date, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET
                        subject = excluded.subject,
                        sender = excluded.sender,
                        snippet = excluded.snippet,
                        body = excluded.body,
                        category_id = excluded.category_id,
                        category_name = excluded.category_name,
                        reason = excluded.reason,
                        can_unsubscribe = excluded.can_unsubscribe,
                        unsubscribe_url = excluded.unsubscribe_url,
                        unsubscribe_type = excluded.unsubscribe_type,
                        unsubscribed = CASE WHEN excluded.unsubscribed = 1 THEN 1 ELSE classified_emails.unsubscribed END,
                        received_date = excluded.received_date,
                        updated_at = excluded.updated_at
                """, (
                    msg_id, subject, sender, snippet, body, cat_id, cat_name,
                    reason, can_unsub, unsub_url, unsub_type, unsub,
                    received_date, now_str, now_str
                ))
                saved += 1
            conn.commit()
        return saved

    def get_classified_emails(self, limit: int = 100, category_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns cached classified emails ordered by id DESC."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category_name and category_name.upper() != "ALL":
                cursor.execute("""
                    SELECT * FROM classified_emails
                    WHERE category_name = ?
                    ORDER BY id DESC LIMIT ?
                """, (category_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM classified_emails
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            emails = []
            for r in rows:
                d = dict(r)
                d["id"] = d["message_id"]
                d["from"] = d["sender"]
                d["can_unsubscribe"] = bool(d["can_unsubscribe"])
                d["unsubscribed"] = bool(d["unsubscribed"])
                emails.append(d)
            return emails

    def get_known_email_ids(self) -> Set[str]:
        """Returns a set of message IDs already stored in the local classified emails cache."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT message_id FROM classified_emails")
            return {row["message_id"] for row in cursor.fetchall()}

    def update_email_unsubscribed(self, message_id: str) -> bool:
        """Marks an email as unsubscribed in both the cache table and unsubscribed_emails."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE classified_emails
                SET unsubscribed = 1, updated_at = ?
                WHERE message_id = ?
            """, (now_str, message_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_cached_email_body(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves cached body and metadata for a given message_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM classified_emails WHERE message_id = ?", (message_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["id"] = d["message_id"]
            d["from"] = d["sender"]
            d["can_unsubscribe"] = bool(d["can_unsubscribe"])
            d["unsubscribed"] = bool(d["unsubscribed"])
            return d

