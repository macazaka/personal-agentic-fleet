"""
Feature Backlog domain repository mixin for FleetDatabase.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


UX_ROADMAP_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "[UX-01] Natural-Language 'Zero-Code' Agent Studio Skill & Conversational Workflow",
        "description": "Describe any agent in 1 plain-English sentence to auto-synthesize manifest.json, schedules.yaml, 6 declarative UI blocks (kpi_row, history_table, checklist), and unit tests in <15s. Spec: docs/backlog/UX-01-natural-language-agent-studio-skill.md",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Planned",
        "target_version": "v2.9.0",
    },
    {
        "title": "[UX-02] Autonomous Process Discovery & Agent Recommendation Engine (process_discovery)",
        "description": "100% local ($0.00 token) workflow miner observing dashboard logs, Win32 PSAPI app clusters, Git repos, and email triage over 1-14 days to recommend ready-to-spawn agents at 21:00 with 1-click creation. Spec: docs/backlog/UX-02-process-discovery-and-recommendation-agent.md",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Planned",
        "target_version": "v2.9.0",
    },
    {
        "title": "[UX-03] Visual Multi-Agent Playbook & Event-Chain Composer (IFTTT for Fleet)",
        "description": "Connect multiple agents into automated pipelines (WHEN [Trigger] -> IF [Condition] -> THEN [Agent A -> Agent B -> Toast]) via playbooks.yaml and a visual builder. Spec: docs/backlog/UX-03-multi-agent-playbook-and-workflow-chaining.md",
        "category": "Automation",
        "priority": "P1",
        "status": "Planned",
        "target_version": "v2.9.0",
    },
    {
        "title": "[UX-04] 1-Click Agent Blueprint Templates & Portable .fleetagent Share Packs",
        "description": "15+ ready-to-use domain blueprints (Pomodoro Guardian, Subscription Sentinel, Multi-Repo Git Watcher, CGM Glucose Log) + drag-and-drop .fleetagent export/import audited by 12-Layer Security Scanner. Spec: docs/backlog/UX-04-agent-blueprint-templates-and-share-packs.md",
        "category": "Core",
        "priority": "P1",
        "status": "Planned",
        "target_version": "v2.9.0",
    },
    {
        "title": "[UX-05] Unified 'Ask Fleet Anything' Omnibar & Cross-Agent Dispatcher (Ctrl+K)",
        "description": "Upgrades Ctrl+K Spotlight into a Raycast-style universal Omnibar supporting @agent commands, natural-language Tier-0 execution, and instant inline result cards without switching tabs. Spec: docs/backlog/UX-05-unified-ask-fleet-omnibar-and-nl-dispatcher.md",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Planned",
        "target_version": "v2.9.0",
    },
    {
        "title": "[UX-06] Interactive First-Run Persona Onboarding & Goal-Driven Auto-Setup",
        "description": "60-second guided setup where users pick personas (FFD Athlete, Software Engineer, Inbox Zero) to auto-configure layouts, themes, schedules.yaml, and pinned tabs. Spec: docs/backlog/UX-06-interactive-persona-onboarding-and-auto-setup.md",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Planned",
        "target_version": "v3.0.0",
    },
    {
        "title": "[UX-07] Focus-Aware Smart Nudges & Actionable Notification Cards",
        "description": "Detects full-screen meetings/deep-work flow to batch non-urgent alerts, and adds 1-click action buttons ([+1 Glass], [Snooze 30m], [Complete]) directly inside notifications. Spec: docs/backlog/UX-07-context-aware-smart-nudges-and-interactive-toasts.md",
        "category": "Automation",
        "priority": "P2",
        "status": "Planned",
        "target_version": "v3.0.0",
    },
    {
        "title": "[UX-08] Agent Time-Machine, 1-Click Undo Rollback & Safe Dry-Run Sandbox",
        "description": "Adds a Simulate (Dry Run) preview button using SQLite savepoints and a transactional agent_undo_journal allowing 1-click rollback of any agent mutation. Spec: docs/backlog/UX-08-agent-time-machine-undo-and-dry-run-sandbox.md",
        "category": "Security",
        "priority": "P2",
        "status": "Planned",
        "target_version": "v3.0.0",
    },
    {
        "title": "[UX-09] Pin-to-Overview Micro-Widgets & Customizable Executive Bento Grid",
        "description": "Pin compact 1x1 or 2x1 live micro-widgets (get_micro_widget) from your favorite agents onto the main Overview Executive Cockpit. Spec: docs/backlog/UX-09-pin-to-overview-micro-widgets-and-bento-grid.md",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Idea",
        "target_version": "v3.0.0",
    },
    {
        "title": "[UX-10] Ambient System Tray Companion, Global Hotkey (Alt+Space) & Voice Capture",
        "description": "Native OS system tray status icon, global Alt+Space quick-capture HUD over any app, and zero-token voice command transcription. Spec: docs/backlog/UX-10-system-tray-companion-global-hotkey-and-voice-capture.md",
        "category": "Integration",
        "priority": "P3",
        "status": "Idea",
        "target_version": "v3.1.0",
    },
]


class BacklogMixin(_DbBase):
    def sync_ux_roadmap_backlog(self) -> int:
        """Idempotently ensures all 10 UX-01..UX-10 roadmap features exist in feature_backlog."""
        inserted = 0
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM feature_backlog")
            existing_titles = {row["title"] for row in cursor.fetchall()}
            for item in UX_ROADMAP_BACKLOG_ITEMS:
                if item["title"] not in existing_titles:
                    cursor.execute(
                        """
                        INSERT INTO feature_backlog (title, description, category, priority, status, target_version, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["title"],
                            item["description"],
                            item["category"],
                            item["priority"],
                            item["status"],
                            item["target_version"],
                            now,
                            now,
                        ),
                    )
                    inserted += 1
            if inserted > 0:
                conn.commit()
        return inserted

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
            return cursor.lastrowid or 0

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
        ALLOWED_FIELDS = {
            "title": "title = ?",
            "description": "description = ?",
            "category": "category = ?",
            "priority": "priority = ?",
            "status": "status = ?",
            "target_version": "target_version = ?",
        }
        set_clauses = []
        params = []
        for k, clause in ALLOWED_FIELDS.items():
            if k in kwargs and kwargs[k] is not None:
                set_clauses.append(clause)
                params.append(kwargs[k])
        if not set_clauses:
            return False
        set_clauses.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(item_id)
        sql = "UPDATE feature_backlog SET " + ", ".join(set_clauses) + " WHERE id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
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

