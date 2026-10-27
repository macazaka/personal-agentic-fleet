"""
Cognitive Mind, Self-Critique, Dream Insights & Soul Alignment domain repository mixin.
Persists the 4-layer cognitive architecture (Brain, Consciousness, Subconsciousness, Soul).
"""

from datetime import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


class MindMixin(_DbBase):
    """Repository mixin for persisting cognitive critiques, dream insights, and soul audits."""

    def log_critique(
        self,
        agent: str,
        action: str,
        critique_score: float,
        critique_notes: str,
        corrective_action: str = "",
        input_summary: str = "",
        output_summary: str = "",
        confidence: float = 1.0,
    ) -> int:
        """Logs a conscious self-critique of an agent action or output."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mind_critiques (
                    agent, action, critique_score, critique_notes, corrective_action,
                    input_summary, output_summary, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent,
                action,
                float(critique_score),
                critique_notes,
                corrective_action,
                input_summary[:500],
                output_summary[:500],
                float(confidence),
                now,
            ))
            conn.commit()
            item_id = cursor.lastrowid or 0
            self.log_activity(
                "Consciousness",
                "self_critique",
                f"[{agent}] {action}: Score {critique_score:.1f}/100 — {critique_notes[:80]}"
            )
            return item_id

    def list_critiques(self, limit: int = 50, agent: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if agent:
                cursor.execute("""
                    SELECT * FROM mind_critiques WHERE agent = ? ORDER BY id DESC LIMIT ?
                """, (agent, limit))
            else:
                cursor.execute("""
                    SELECT * FROM mind_critiques ORDER BY id DESC LIMIT ?
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def log_dream_insight(
        self,
        insight_type: str,
        title: str,
        description: str,
        source_events_count: int = 0,
        confidence: float = 1.0,
        actionable_recommendation: str = "",
    ) -> int:
        """Logs an insight synthesized during subconscious offline memory consolidation."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mind_dream_insights (
                    insight_type, title, description, source_events_count,
                    confidence, actionable_recommendation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                insight_type.upper(),
                title,
                description,
                source_events_count,
                float(confidence),
                actionable_recommendation,
                now,
            ))
            conn.commit()
            item_id = cursor.lastrowid or 0
            self.log_activity(
                "Subconsciousness",
                "dream_insight",
                f"[{insight_type.upper()}] {title}: {description[:80]}"
            )
            return item_id

    def list_dream_insights(self, limit: int = 50, insight_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if insight_type:
                cursor.execute("""
                    SELECT * FROM mind_dream_insights WHERE insight_type = ? ORDER BY id DESC LIMIT ?
                """, (insight_type.upper(), limit))
            else:
                cursor.execute("""
                    SELECT * FROM mind_dream_insights ORDER BY id DESC LIMIT ?
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def log_soul_audit(
        self,
        audit_id: str,
        alignment_score: float,
        violations_count: int,
        violations_json: str,
        recommendations_json: str,
        summary: str,
    ) -> int:
        """Logs a teleological soul audit measuring fleet fidelity to its core values and ethics."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mind_soul_audits (
                    audit_id, alignment_score, violations_count, violations_json,
                    recommendations_json, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id,
                float(alignment_score),
                violations_count,
                violations_json,
                recommendations_json,
                summary,
                now,
            ))
            conn.commit()
            item_id = cursor.lastrowid or 0
            self.log_activity(
                "Soul",
                "soul_audit",
                f"Soul Alignment: {alignment_score:.1f}/100 ({violations_count} violations) — {summary[:80]}"
            )
            return item_id

    def list_soul_audits(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM mind_soul_audits ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["violations"] = json.loads(d.get("violations_json") or "[]")
                except Exception:
                    d["violations"] = []
                try:
                    d["recommendations"] = json.loads(d.get("recommendations_json") or "[]")
                except Exception:
                    d["recommendations"] = []
                results.append(d)
            return results

    def get_mind_stats(self) -> Dict[str, Any]:
        """Returns aggregate cognitive statistics across all 4 mind layers."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Critiques
            cursor.execute("SELECT COUNT(*) as total, AVG(critique_score) as avg_score FROM mind_critiques")
            row_c = cursor.fetchone()
            total_critiques = row_c["total"] if row_c else 0
            avg_critique_score = round(row_c["avg_score"] or 100.0, 1) if row_c else 100.0

            # Dream Insights
            cursor.execute("SELECT COUNT(*) as total FROM mind_dream_insights")
            row_d = cursor.fetchone()
            total_dream_insights = row_d["total"] if row_d else 0

            # Soul Audits
            cursor.execute("SELECT COUNT(*) as total, AVG(alignment_score) as avg_score FROM mind_soul_audits")
            row_s = cursor.fetchone()
            total_soul_audits = row_s["total"] if row_s else 0
            avg_soul_alignment = round(row_s["avg_score"] or 100.0, 1) if row_s else 100.0

            return {
                "total_critiques": total_critiques,
                "avg_critique_score": avg_critique_score,
                "total_dream_insights": total_dream_insights,
                "total_soul_audits": total_soul_audits,
                "avg_soul_alignment": avg_soul_alignment,
            }
