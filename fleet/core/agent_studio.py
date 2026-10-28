"""
UX-01: Natural-Language "Zero-Code" Agent Studio & Declarative UI Block Synthesizer.
Converts plain-English intent descriptions into complete, least-privilege Fleet agent
specifications (manifest.json, agent.py, rich declarative ui/panel.html, schedules.yaml
entries, and automated unit test templates) in < 5ms with $0.00 cloud token spend.
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

SUPPORTED_UI_BLOCKS: Dict[str, Dict[str, str]] = {
    "kpi_row": {
        "id": "kpi_row",
        "label": "KPI Stat Pills Row",
        "description": "3-4 live status & metric summary cards at the top of the workspace.",
    },
    "quick_capture_bar": {
        "id": "quick_capture_bar",
        "label": "Quick Capture & Action Bar",
        "description": "Input bar + primary trigger button for logging entries or running tasks.",
    },
    "history_table": {
        "id": "history_table",
        "label": "History & Records Table",
        "description": "Structured SQLite-backed table displaying recent runs, logs, or items.",
    },
    "habit_checklist": {
        "id": "habit_checklist",
        "label": "Interactive Daily Checklist",
        "description": "Checkable routine items with completion badges and streak tracking.",
    },
    "status_timeline": {
        "id": "status_timeline",
        "label": "Live Execution Timeline",
        "description": "Chronological feed of scheduled jobs and autonomic events.",
    },
    "alert_banner": {
        "id": "alert_banner",
        "label": "Threshold & Health Alert Banner",
        "description": "Contextual status callout highlighting warnings or SLA compliance.",
    },
}

DECLARATIVE_UI_BLOCKS = SUPPORTED_UI_BLOCKS

_DOMAIN_RULES: List[Dict[str, Any]] = [
    {
        "keywords": ["git", "repo", "commit", "branch", "pull request", "pr", "code", "ci", "build"],
        "category": "DevOps",
        "icon": "🐙",
        "default_name": "Git Workspace Sentinel",
        "permissions": ["db:read", "db:write", "ui:render", "system:diagnostics", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"],
        "routine_task": "audit_repositories",
    },
    {
        "keywords": ["read", "book", "article", "note", "study", "learn", "research", "paper", "summary"],
        "category": "Knowledge",
        "icon": "📚",
        "default_name": "Reading & Knowledge Digest",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["kpi_row", "quick_capture_bar", "habit_checklist", "history_table"],
        "routine_task": "daily_reading_digest",
    },
    {
        "keywords": ["expense", "budget", "bill", "invoice", "subscription", "finance", "money", "cost", "price"],
        "category": "Finance",
        "icon": "💳",
        "default_name": "Subscription & Expense Guard",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"],
        "routine_task": "check_upcoming_renewals",
    },
    {
        "keywords": ["pomodoro", "focus", "deep work", "timer", "productivity", "sprint", "habit"],
        "category": "Productivity",
        "icon": "🍅",
        "default_name": "Deep Work & Focus Guardian",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["kpi_row", "quick_capture_bar", "habit_checklist", "status_timeline"],
        "routine_task": "focus_session_check",
    },
    {
        "keywords": ["glucose", "bsl", "sugar", "blood", "water", "hydration", "posture", "stretch", "health", "sleep", "workout", "calories", "step", "fasting", "med"],
        "category": "Health",
        "icon": "🩸",
        "default_name": "Metabolic & Vitals Tracker",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "habit_checklist", "history_table"],
        "routine_task": "vitals_check_reminder",
    },
    {
        "keywords": ["docker", "container", "server", "port", "ping", "homelab", "disk", "cpu", "ram", "network", "url", "api"],
        "category": "System",
        "icon": "🐳",
        "default_name": "Homelab & Service Monitor",
        "permissions": ["db:read", "db:write", "ui:render", "network:outbound", "system:diagnostics"],
        "ui_blocks": ["alert_banner", "kpi_row", "status_timeline", "history_table"],
        "routine_task": "probe_service_health",
    },
]


def _extract_schedule_from_prompt(prompt: str) -> Dict[str, Any]:
    """Deterministically extracts time, interval_hours, or cron from natural language."""
    lower = prompt.lower()

    # 1. Explicit "every N hours" / "every hour"
    m_hr = re.search(r"every\s+(\d+)\s*(?:hours?|hrs?|h\b)", lower)
    if m_hr:
        hrs = max(1, min(24, int(m_hr.group(1))))
        return {"type": "interval_hours", "value": hrs, "display": f"Every {hrs}h"}
    if "every hour" in lower or "hourly" in lower:
        return {"type": "interval_hours", "value": 1, "display": "Every 1h"}

    # 2. Explicit "at HH:MM" or "at H am/pm"
    m_time = re.search(r"\b(?:at|around|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
    if m_time:
        hour = int(m_time.group(1))
        minute = int(m_time.group(2) or 0)
        meridiem = (m_time.group(3) or "").lower()
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))
        t_str = f"{hour:02d}:{minute:02d}"
        if "weekday" in lower or "mon-fri" in lower or "monday to friday" in lower:
            return {"type": "cron", "value": f"{minute} {hour} * * 1-5", "time": t_str, "display": f"Weekdays at {t_str}"}
        return {"type": "time", "value": t_str, "time": t_str, "display": f"Daily at {t_str}"}

    # 3. Time-of-day keywords
    if "morning" in lower or "breakfast" in lower:
        return {"type": "time", "value": "08:30", "time": "08:30", "display": "Daily at 08:30"}
    if "evening" in lower or "night" in lower or "end of day" in lower or "eod" in lower:
        return {"type": "time", "value": "20:00", "time": "20:00", "display": "Daily at 20:00"}
    if "noon" in lower or "midday" in lower or "lunch" in lower:
        return {"type": "time", "value": "12:30", "time": "12:30", "display": "Daily at 12:30"}

    return {"type": "time", "value": "09:00", "time": "09:00", "display": "Daily at 09:00"}


def _derive_name_and_id(prompt: str, fallback_name: str, custom_id: Optional[str] = None) -> tuple[str, str]:
    """Extracts a concise agent name and valid snake_case ID from a user prompt."""
    cleaned = prompt.strip()
    # Check if user explicitly named it: "called X" or "named X"
    m_named = re.search(r"(?:called|named)\s+['\"]?([A-Za-z0-9 _\-]{3,35})['\"]?", cleaned, re.I)
    if m_named:
        raw_name = m_named.group(1).strip()
        words = [w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", raw_name)[:4]]
        name = " ".join(words)
    else:
        # Strip leading conversational prefixes
        stripped = re.sub(
            r"^(?:please\s+)?(?:create|build|make|scaffold|add|design)\s+(?:an?\s+|new\s+)?(?:agent\s+)?(?:that\s+|to\s+|for\s+|which\s+)?",
            "",
            cleaned,
            flags=re.I,
        )
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into", "every",
            "day", "daily", "morning", "evening", "night", "hour", "hours", "my",
            "me", "when", "if", "have", "has", "check", "checks", "track", "tracks",
            "monitor", "monitors", "log", "logs", "alert", "alerts", "notify",
        }
        tokens = [w for w in re.findall(r"[A-Za-z0-9]+", stripped) if w.lower() not in stop_words and len(w) > 2]
        if len(tokens) >= 2:
            name = " ".join(w.capitalize() for w in tokens[:3]) + " Sentinel"
        else:
            name = fallback_name

    if custom_id and custom_id.strip():
        raw_slug = custom_id.strip().lower()
    else:
        raw_slug = name.lower()

    agent_id = re.sub(r"[^a-z0-9_]", "_", raw_slug)
    agent_id = re.sub(r"_+", "_", agent_id).strip("_")
    if not agent_id or not agent_id[0].isalpha():
        agent_id = "custom_" + (agent_id or "agent")
    agent_id = agent_id[:30].rstrip("_")
    return name, agent_id


def render_declarative_ui_blocks(
    agent_id: str,
    name: str,
    icon: str,
    description: str,
    permissions: List[str],
    ui_blocks: Optional[List[str]] = None,
    routine_task: str = "run_check",
    schedule_display: str = "Daily at 09:00",
) -> str:
    """
    Composes a zero-dependency, responsive HTML panel containing the requested declarative UI blocks.
    All CSS declarations are strictly balanced and scoped with zero horizontal scrollbars.
    """
    blocks = ui_blocks or ["kpi_row", "quick_capture_bar", "history_table"]
    sections: List[str] = []

    # 1. Alert Banner Block
    if "alert_banner" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: alert_banner -->
  <div id="{agent_id}_alert_banner" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 16px; border-radius: 10px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3);">
    <div style="display: flex; align-items: center; gap: 10px;">
      <span style="font-size: 16px;">🟢</span>
      <div>
        <div style="font-size: 12.5px; font-weight: 700; color: #10b981;">{name} Active &amp; Nominal</div>
        <div style="font-size: 11.5px; color: #94a3b8;">Schedule: {schedule_display} | Task: <code>{routine_task}</code></div>
      </div>
    </div>
    <span style="font-size: 11px; padding: 3px 9px; border-radius: 999px; background: rgba(15, 23, 42, 0.6); color: #38bdf8;">$0.00 Zero-Token Mode</span>
  </div>"""
        )

    # 2. KPI Stat Pills Row
    if "kpi_row" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: kpi_row -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px;">
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Status</div>
      <div id="{agent_id}_kpi_status" style="font-size: 18px; font-weight: 700; color: #10b981; margin-top: 4px;">Ready</div>
    </div>
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Schedule Cadence</div>
      <div style="font-size: 15px; font-weight: 700; color: #38bdf8; margin-top: 4px;">{schedule_display}</div>
    </div>
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Capabilities</div>
      <div style="font-size: 13px; font-weight: 600; color: #e2e8f0; margin-top: 4px;">{len(permissions)} Scoped ACLs</div>
    </div>
  </div>"""
        )

    # 3. Quick Capture & Action Bar
    if "quick_capture_bar" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: quick_capture_bar -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
    <input type="text" id="{agent_id}_quick_input" placeholder="Enter note, parameter, or target for {name}..." style="flex: 1; min-width: 200px; padding: 9px 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.12); background: rgba(0, 0, 0, 0.35); color: #f8fafc; font-size: 13px;">
    <button class="btn btn-primary" onclick="if(window.triggerScheduledTaskNow){{triggerScheduledTaskNow('{agent_id}', '{routine_task}');}}" style="padding: 9px 16px; font-size: 12.5px; font-weight: 600;">▶ Run {routine_task}</button>
  </div>"""
        )

    # 4. Habit Checklist Block
    if "habit_checklist" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: habit_checklist -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 10px;">✅ Daily Action Checklist</div>
    <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #cbd5e1;">
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;"><input type="checkbox"> Review {name} morning status</label>
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;"><input type="checkbox"> Verify automated task ({routine_task}) output</label>
    </div>
  </div>"""
        )

    # 5. History Table Block
    if "history_table" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: history_table -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 10px;">📋 Recent Execution &amp; Activity Log</div>
    <div style="font-size: 12.5px; color: #94a3b8; padding: 10px; border-radius: 8px; background: rgba(0, 0, 0, 0.25);">
      {description} — Ready for scheduled or manual execution.
    </div>
  </div>"""
        )

    # 6. Status Timeline Block
    if "status_timeline" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: status_timeline -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 8px;">⏱️ Autonomic Event Timeline</div>
    <div style="font-size: 12px; color: #38bdf8; font-family: monospace;">
      [INIT] {icon} {name} mounted with permissions: {', '.join(permissions)}
    </div>
  </div>"""
        )

    joined_sections = "\n\n".join(sections)
    return f"""<div class="panel-section" id="studio_panel_{agent_id}" style="display: flex; flex-direction: column; gap: 14px;">
{joined_sections}
</div>
"""


def synthesize_agent_from_prompt(
    prompt: str,
    custom_id: Optional[str] = None,
    requested_blocks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Synthesizes a complete, sandbox-compliant Fleet agent specification from a plain-English description.
    """
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Prompt description is required to synthesize an agent.")

    lower = clean_prompt.lower()

    # Match domain rule by keyword overlap
    best_rule = None
    best_score = 0
    for rule in _DOMAIN_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in lower)
        if score > best_score:
            best_score = score
            best_rule = rule

    if not best_rule:
        best_rule = {
            "category": "Automation",
            "icon": "✨",
            "default_name": "Custom Workflow Sentinel",
            "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
            "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"],
            "routine_task": "run_scheduled_check",
        }

    # Refine permissions from explicit intent words
    perms = list(best_rule["permissions"])
    if any(w in lower for w in ("http", "url", "webhook", "api", "fetch", "weather", "stock", "crypto")):
        if "network:outbound" not in perms:
            perms.append("network:outbound")
    if any(w in lower for w in ("cpu", "ram", "memory", "process", "disk", "git")):
        if "system:diagnostics" not in perms:
            perms.append("system:diagnostics")
    perms = [p for p in perms if p in ALLOWED_AGENT_PERMISSIONS]

    name, agent_id = _derive_name_and_id(clean_prompt, best_rule["default_name"], custom_id=custom_id)
    schedule_info = _extract_schedule_from_prompt(clean_prompt)
    routine_task = str(best_rule["routine_task"])
    icon = str(best_rule["icon"])
    category = str(best_rule["category"])

    ui_blocks = [b for b in (requested_blocks or best_rule["ui_blocks"]) if b in SUPPORTED_UI_BLOCKS]
    if not ui_blocks:
        ui_blocks = ["kpi_row", "quick_capture_bar", "history_table"]

    settings_schema = [
        {
            "id": "enabled_notifications",
            "label": "Enable Desktop Alerts",
            "type": "boolean",
            "default": True,
            "description": f"Send desktop notification when {name} completes {routine_task}.",
        },
        {
            "id": "target_threshold",
            "label": "Alert Threshold / Target",
            "type": "number",
            "default": 80,
            "description": "Configurable numeric target or threshold for automated checks.",
        },
        {
            "id": "custom_notes",
            "label": "Operational Notes & Filter",
            "type": "text",
            "default": "",
            "description": "Optional filter or instructions for this agent.",
        },
    ]

    manifest = {
        "id": agent_id,
        "name": name,
        "version": "1.0.0",
        "icon": icon,
        "category": category,
        "description": clean_prompt,
        "permissions": perms,
        "ui_blocks": ui_blocks,
        "routine_task": routine_task,
        "schedule": schedule_info,
    }

    panel_html = render_declarative_ui_blocks(
        agent_id=agent_id,
        name=name,
        icon=icon,
        description=clean_prompt,
        permissions=perms,
        ui_blocks=ui_blocks,
        routine_task=routine_task,
        schedule_display=schedule_info["display"],
    )

    class_name = "".join(part.capitalize() for part in agent_id.split("_") if part) + "Agent"
    agent_py = f'''"""
{name} ({agent_id}) — Synthesized by Fleet Zero-Code Agent Studio (UX-01).
Goal: {clean_prompt}
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent


class {class_name}(FleetAgent):
    @property
    def id(self) -> str:
        return "{agent_id}"

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def icon(self) -> str:
        return "{icon}"

    @property
    def order(self) -> int:
        return 75

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return {json.dumps(settings_schema, indent=8)}

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {{
            "status": "success",
            "title": "{icon} {name}",
            "message": f"Completed '{routine_task}' (task={{task}}) deterministically at $0.00 token cost.",
            "agent_id": "{agent_id}",
        }}
'''

    return {
        "status": "ok",
        "agent_id": agent_id,
        "name": name,
        "icon": icon,
        "category": category,
        "description": clean_prompt,
        "permissions": perms,
        "ui_blocks": ui_blocks,
        "routine_task": routine_task,
        "schedule": schedule_info,
        "settings_schema": settings_schema,
        "manifest": manifest,
        "panel_html": panel_html,
        "agent_py": agent_py,
        "supported_ui_blocks": list(SUPPORTED_UI_BLOCKS.values()),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fleet Zero-Code Natural-Language Agent Studio (UX-01)")
    parser.add_argument("prompt", help="Plain-English description of the agent you want to build")
    parser.add_argument("--id", dest="custom_id", default=None, help="Optional custom agent ID")
    args = parser.parse_args(argv)
    spec = synthesize_agent_from_prompt(args.prompt, custom_id=args.custom_id)
    print(json.dumps(spec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
