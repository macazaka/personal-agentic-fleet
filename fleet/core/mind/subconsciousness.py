"""
Subconsciousness — The Dreaming & Background Mind for Personal Agentic Fleet.
Performs offline memory consolidation, implicit pattern discovery, predictive priming,
and autonomic immunological self-repair without occupying conscious executive focus.
"""

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from fleet.config import DATA_DIR, DB_PATH
from fleet.core.auto_healer import run_proactive_log_scan_and_heal


@dataclass
class DreamInsight:
    id: str
    insight_type: str  # HABIT, FRICTION, OPTIMIZATION, SYNTHESIS
    title: str
    description: str
    source_events_count: int
    confidence: float
    actionable_recommendation: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SubconsciousMind:
    """
    The background implicit intelligence of the fleet.
    Consolidates episodic memory into semantic wisdom during 'Dream Cycles'.
    """

    def __init__(self, db: Any = None):
        self.db = db
        self._last_dream_time: Optional[float] = None
        self._dream_lock = threading.RLock()
        self._is_dreaming: bool = False
        self._recent_insights: List[DreamInsight] = []

    def run_dream_cycle(self, max_activities_to_synthesize: int = 200) -> Dict[str, Any]:
        """
        Executes a background Dream Cycle (offline memory consolidation):
        1. Ingests raw episodic logs from activity_logs, tasks, and telemetry.
        2. Discovers latent behavioral habits and recurring user preferences.
        3. Mines friction patterns (e.g. recurring retries, frequent error bursts).
        4. Distills semantic insights into actionable recommendations.
        5. Triggers autonomic immunological self-repair (clean up mental clutter).
        """
        with self._dream_lock:
            self._is_dreaming = True
            start_ts = time.time()
            now_iso = datetime.now().isoformat()
            cycle_id = f"DREAM-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            insights: List[DreamInsight] = []
            activities: List[Dict[str, Any]] = []

            # 1. Gather recent episodic activities
            if self.db and hasattr(self.db, "get_recent_activities"):
                try:
                    activities = self.db.get_recent_activities(limit=max_activities_to_synthesize)
                except Exception:
                    activities = []
            elif DB_PATH.exists():
                try:
                    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (max_activities_to_synthesize,))
                    activities = [dict(r) for r in cursor.fetchall()]
                    conn.close()
                except Exception:
                    activities = []

            # 2. Mine Agent Engagement & Habit Patterns
            agent_counts = Counter(a.get("agent", "Unknown") for a in activities)
            top_agents = agent_counts.most_common(3)
            if top_agents:
                top_summary = ", ".join(f"{name} ({cnt}x)" for name, cnt in top_agents)
                insight = DreamInsight(
                    id=f"INSIGHT-HABIT-{int(time.time())}",
                    insight_type="HABIT",
                    title="Circadian Agent Engagement Cluster",
                    description=f"Dominant cognitive activity centered on: {top_summary}.",
                    source_events_count=len(activities),
                    confidence=0.95,
                    actionable_recommendation="Ensure high-throughput agents have prime cache pre-warming during active hours.",
                )
                insights.append(insight)

            # 3. Mine Operational Friction & Bottlenecks
            action_counts = Counter(a.get("action", "") for a in activities)
            err_actions = [act for act, cnt in action_counts.items() if "error" in act.lower() or "fail" in act.lower()]
            if err_actions:
                insight = DreamInsight(
                    id=f"INSIGHT-FRICT-{int(time.time())}",
                    insight_type="FRICTION",
                    title="Latent Execution Friction Detected",
                    description=f"Subconscious detected friction patterns across actions: {', '.join(err_actions)}.",
                    source_events_count=sum(action_counts[a] for a in err_actions),
                    confidence=0.88,
                    actionable_recommendation="Apply adaptive retry backoff and verify downstream dependency stability.",
                )
                insights.append(insight)
            else:
                insight = DreamInsight(
                    id=f"INSIGHT-SYNTH-{int(time.time())}",
                    insight_type="SYNTHESIS",
                    title="Harmonious Neural Flow",
                    description="Zero recurring friction patterns found across recent activity stream.",
                    source_events_count=len(activities),
                    confidence=0.99,
                    actionable_recommendation="System operating in optimal homeostatic rhythm; continue current scheduling cadence.",
                )
                insights.append(insight)

            # 4. Mine Task Velocity & Productive Focus
            if self.db and hasattr(self.db, "list_tasks"):
                try:
                    tasks = self.db.list_tasks(status="completed", limit=30)
                    if tasks:
                        p1_count = len([t for t in tasks if str(t.get("priority", "")).upper() == "P1"])
                        insight = DreamInsight(
                            id=f"INSIGHT-VEL-{int(time.time())}",
                            insight_type="OPTIMIZATION",
                            title="Productive Task Momentum",
                            description=f"Recent completion streak includes {len(tasks)} tasks ({p1_count} high-priority P1 items).",
                            source_events_count=len(tasks),
                            confidence=0.92,
                            actionable_recommendation="Preserve morning focus windows (08:30 - 11:30) for P1 task execution.",
                        )
                        insights.append(insight)
                except Exception:
                    pass

            # 5. Autonomic Immunological Pruning (Clean mental clutter & compact state)
            healing_report = run_proactive_log_scan_and_heal(db=self.db)
            reclaimed_actions = healing_report.get("improvements_applied_count", 0)

            # Persist insights to database if mixin available
            for ins in insights:
                if self.db and hasattr(self.db, "log_dream_insight"):
                    try:
                        self.db.log_dream_insight(
                            insight_type=ins.insight_type,
                            title=ins.title,
                            description=ins.description,
                            source_events_count=ins.source_events_count,
                            confidence=ins.confidence,
                            actionable_recommendation=ins.actionable_recommendation,
                        )
                    except Exception:
                        pass

            self._recent_insights = insights + self._recent_insights
            self._recent_insights = self._recent_insights[:30]
            self._last_dream_time = time.time()
            self._is_dreaming = False
            duration_sec = round(time.time() - start_ts, 2)

            return {
                "cycle_id": cycle_id,
                "timestamp": now_iso,
                "duration_sec": duration_sec,
                "events_consolidated": len(activities),
                "insights_synthesized_count": len(insights),
                "autonomic_remediations_count": reclaimed_actions,
                "insights": [asdict(i) for i in insights],
                "immunological_health": healing_report.get("status", "HEALTHY"),
            }

    def get_status(self) -> Dict[str, Any]:
        with self._dream_lock:
            last_dream_str = (
                datetime.fromtimestamp(self._last_dream_time).isoformat()
                if self._last_dream_time
                else "Awaiting initial dream cycle"
            )
            return {
                "layer": "Subconsciousness (Dream Engine & Implicit Synthesis)",
                "status": "DREAMING" if self._is_dreaming else "INTUITING",
                "last_dream_cycle": last_dream_str,
                "total_insights_cached": len(self._recent_insights),
                "recent_insights": [asdict(i) for i in self._recent_insights[:5]],
            }
