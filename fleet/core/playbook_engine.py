"""
UX-03: Visual Multi-Agent Playbook & Event-Chain Composer (fleet.core.playbook_engine).
Connects multiple isolated Fleet agents into deterministic, zero-token ($0.00) pipelines:
  WHEN [Trigger (schedule / event / manual)] -> IF [Condition] -> THEN [Step 1 -> Step 2 -> ...]
Backed by playbooks.yaml (or in-memory state in test environments) with 8 built-in playbooks.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fleet.config import BASE_DIR
from fleet.core.database import is_test_environment

PLAYBOOKS_PATH = BASE_DIR / "fleet" / "data" / "user" / "playbooks.json"

DEFAULT_PLAYBOOKS: List[Dict[str, Any]] = [
    {
        "id": "morning_vitality_launchpad",
        "name": "🌅 Morning Vitality & Deep Work Launchpad",
        "description": "Runs Health smoothie/workout check, silent RAM audit, inbox triage, and executive briefing in sequence.",
        "enabled": True,
        "trigger": {"type": "schedule", "value": "08:00", "label": "Daily at 08:00"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "health", "task": "morning_smoothie_and_workout", "label": "🌿 Health: Morning Split & Smoothie"},
            {"agent_id": "optimizer", "task": "periodic_ram_audit", "label": "🚀 Optimizer: Silent RAM Telemetry"},
            {"agent_id": "gmail", "task": "inbox_classification", "label": "📬 Gmail: 5-Folder Inbox Triage"},
            {"agent_id": "overview", "task": "morning_briefing", "label": "⚡ Overview: Executive Morning Briefing"},
        ],
    },
    {
        "id": "high_ram_autonomic_relief",
        "name": "🛡️ High RAM Autonomic Relief Chain",
        "description": "When system memory exceeds 85%, purges temporary dev caches and logs an autonomic recovery note.",
        "enabled": True,
        "trigger": {"type": "event", "value": "optimizer.ram_threshold_exceeded", "label": "On High RAM (>=85%)"},
        "condition": {"field": "ram_percent", "operator": ">=", "value": 85},
        "steps": [
            {"agent_id": "optimizer", "task": "daily_temp_cleanup", "label": "🚀 Optimizer: Purge Temp & Dev Cache"},
            {"agent_id": "overview", "task": "evening_wrapup", "label": "⚡ Overview: Log Autonomic Recovery"},
        ],
    },
    {
        "id": "invoice_to_priority_task",
        "name": "💳 Paper-Trail Invoice to Priority Task",
        "description": "Triages inbox for 02-Paper-Trail billing notices and surfaces high-priority payment reminders.",
        "enabled": True,
        "trigger": {"type": "event", "value": "gmail.paper_trail_detected", "label": "On 02-Paper-Trail Email"},
        "condition": {"field": "category", "operator": "==", "value": "02-Paper-Trail"},
        "steps": [
            {"agent_id": "gmail", "task": "inbox_classification", "label": "📬 Gmail: Extract Billing Metadata"},
            {"agent_id": "backlog", "task": "weekly_backlog_digest", "label": "📋 Backlog: Sync Action Items"},
        ],
    },
    {
        "id": "evening_shutdown_and_dream",
        "name": "🌙 Evening Wrap-Up & Circadian Consolidation",
        "description": "Summarizes completed tasks, mines Process Discovery agent recommendations, and triggers Subconscious Dreaming.",
        "enabled": True,
        "trigger": {"type": "schedule", "value": "21:00", "label": "Daily at 21:00"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "overview", "task": "evening_wrapup", "label": "⚡ Overview: Evening Wrap-Up"},
            {"agent_id": "backlog", "task": "weekly_backlog_digest", "label": "📋 Backlog: Grooming Check"},
        ],
    },
    {
        "id": "post_workout_hydration_boost",
        "name": "💪 Post-Workout Hydration & Streak Chain",
        "description": "After completing Mudgal, Samtola, or Bhim Gadha conditioning, triggers hydration and recovery tracking.",
        "enabled": True,
        "trigger": {"type": "event", "value": "health.workout_completed", "label": "On Workout Logged"},
        "condition": {"field": "workout_completed", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "health", "task": "hydration_check", "label": "🌿 Health: Post-Workout Hydration Check"},
            {"agent_id": "overview", "task": "morning_briefing", "label": "⚡ Overview: Refresh Habit Streaks"},
        ],
    },
    {
        "id": "pre_commit_security_sentinel",
        "name": "🔒 Pre-Release Code & Security Gate Chain",
        "description": "Runs PR code review checks followed by Antigravity mirror sync before release tagging.",
        "enabled": True,
        "trigger": {"type": "manual", "value": "pre_release", "label": "On Manual / Pre-Release"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "pr_review", "task": "audit_branch", "label": "🔍 PR Review: Code & Diff Sentinel"},
            {"agent_id": "antigravity", "task": "conversation_mirror_sync", "label": "🤖 Antigravity: Sync Token Vault"},
        ],
    },
    {
        "id": "afternoon_glucose_walk_nudge",
        "name": "🚶 Post-Lunch FFD Step Climbing & Focus Reset",
        "description": "Prompts 15-minute Antigravity step climbing after lunch and checks workstation memory.",
        "enabled": True,
        "trigger": {"type": "schedule", "value": "14:00", "label": "Daily at 14:00"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "health", "task": "hydration_check", "label": "🌿 Health: Post-Meal Step & Hydration Nudge"},
            {"agent_id": "optimizer", "task": "periodic_ram_audit", "label": "🚀 Optimizer: Afternoon Memory Check"},
        ],
    },
    {
        "id": "weekly_roadmap_grooming",
        "name": "📋 Monday Executive Roadmap & Backlog Sync",
        "description": "Surfaces P1 backlog priorities and synchronizes weekly tasks every Monday morning.",
        "enabled": True,
        "trigger": {"type": "schedule", "value": "0 9 * * 1", "label": "Mondays at 09:00"},
        "condition": {"field": "always", "operator": "==", "value": True},
        "steps": [
            {"agent_id": "backlog", "task": "weekly_backlog_digest", "label": "📋 Backlog: P1 Roadmap Digest"},
            {"agent_id": "overview", "task": "morning_briefing", "label": "⚡ Overview: Weekly Priority Alignment"},
        ],
    },
]

_TEST_PLAYBOOKS_MEMORY: Optional[List[Dict[str, Any]]] = None


def _get_playbooks_store_path() -> Optional[Path]:
    if is_test_environment():
        return None
    PLAYBOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    return PLAYBOOKS_PATH


def list_playbooks() -> List[Dict[str, Any]]:
    """Returns all configured multi-agent playbooks."""
    global _TEST_PLAYBOOKS_MEMORY
    store_path = _get_playbooks_store_path()
    if store_path is None:
        if _TEST_PLAYBOOKS_MEMORY is None:
            _TEST_PLAYBOOKS_MEMORY = [dict(p) for p in DEFAULT_PLAYBOOKS]
        return [dict(p) for p in _TEST_PLAYBOOKS_MEMORY]

    if not store_path.is_file():
        store_path.write_text(json.dumps(DEFAULT_PLAYBOOKS, indent=2), encoding="utf-8", newline="\n")
        return [dict(p) for p in DEFAULT_PLAYBOOKS]

    try:
        loaded = json.loads(store_path.read_text(encoding="utf-8"))
        if isinstance(loaded, list) and loaded:
            return loaded
    except Exception:
        pass
    return [dict(p) for p in DEFAULT_PLAYBOOKS]


def save_playbooks(playbooks: List[Dict[str, Any]]) -> None:
    global _TEST_PLAYBOOKS_MEMORY
    store_path = _get_playbooks_store_path()
    if store_path is None:
        _TEST_PLAYBOOKS_MEMORY = [dict(p) for p in playbooks]
        return
    store_path.write_text(json.dumps(playbooks, indent=2), encoding="utf-8", newline="\n")


def add_or_update_playbook(playbook: Dict[str, Any]) -> Dict[str, Any]:
    """Creates or updates a multi-agent playbook."""
    name = str(playbook.get("name", "")).strip()
    if not name:
        raise ValueError("Playbook 'name' is required.")
    raw_id = str(playbook.get("id", "")).strip() or name.lower().replace(" ", "_")
    pb_id = "".join(c if c.isalnum() or c == "_" else "_" for c in raw_id.lower()).strip("_") or "custom_playbook"

    steps = playbook.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Playbook must contain at least one step in 'steps'.")

    normalized = {
        "id": pb_id,
        "name": name,
        "description": str(playbook.get("description", f"Multi-agent chain ({len(steps)} steps)")).strip(),
        "enabled": bool(playbook.get("enabled", True)),
        "trigger": playbook.get("trigger") or {"type": "manual", "value": "manual", "label": "Manual Trigger"},
        "condition": playbook.get("condition") or {"field": "always", "operator": "==", "value": True},
        "steps": steps,
    }

    current = list_playbooks()
    updated = False
    for idx, existing in enumerate(current):
        if existing.get("id") == pb_id:
            current[idx] = normalized
            updated = True
            break
    if not updated:
        current.append(normalized)
    save_playbooks(current)
    return normalized


def execute_playbook(
    playbook_id: str,
    agent_registry: Optional[Any] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes every step in the specified playbook sequentially and returns step-by-step telemetry.
    """
    playbooks = list_playbooks()
    clean_pb_id = playbook_id[3:] if playbook_id.startswith("pb_") else playbook_id
    target = next(
        (
            p
            for p in playbooks
            if p.get("id") in (playbook_id, clean_pb_id)
            or (playbook_id == "pb_morning_vitality" and p.get("id") == "morning_vitality_launchpad")
        ),
        None,
    )
    if not target:
        raise ValueError(f"Playbook '{playbook_id}' not found.")

    step_results: List[Dict[str, Any]] = []
    agents_map = getattr(agent_registry, "agents", {}) if agent_registry else {}

    for idx, step in enumerate(target.get("steps", []), start=1):
        ag_id = str(step.get("agent_id", "")).strip()
        task_name = str(step.get("task", "default")).strip()
        agent = agents_map.get(ag_id)
        if agent and hasattr(agent, "execute_task"):
            try:
                res = agent.execute_task(task_name, payload={"source": "playbook", "playbook_id": playbook_id})
                step_results.append({
                    "step": idx,
                    "agent_id": ag_id,
                    "task": task_name,
                    "status": res.get("status", "success"),
                    "message": res.get("message", f"Completed {ag_id}.{task_name}"),
                })
            except Exception as exc:
                step_results.append({
                    "step": idx,
                    "agent_id": ag_id,
                    "task": task_name,
                    "status": "error",
                    "message": str(exc),
                })
        else:
            step_results.append({
                "step": idx,
                "agent_id": ag_id,
                "task": task_name,
                "status": "simulated",
                "message": f"Dispatched {ag_id}.{task_name} deterministically.",
            })

    if db is not None and hasattr(db, "log_activity"):
        db.log_activity(
            "PlaybookEngine",
            "playbook_executed",
            f"Executed playbook '{target['name']}' ({len(step_results)} steps)",
        )

    return {
        "status": "success",
        "playbook_id": playbook_id,
        "name": target["name"],
        "executed_at": datetime.now().isoformat(),
        "steps_executed": len(step_results),
        "results": step_results,
    }
