"""
UX-01 & Phase 1/2 Zero-Code Agent Studio, Starter Blueprints, Functional Runtime & Declarative UI Synthesizer.
Converts plain-English intent descriptions into functional, SQLite-backed, least-privilege Fleet agents
with typed domain fields, live UI widgets, dry-run sandboxing, and hybrid $0.00 + Antigravity LLM execution.
"""

import argparse
import ast
from datetime import date, datetime
import html as html_lib
import json
import logging
import os
import re
import shutil
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

logger = logging.getLogger(__name__)

SUPPORTED_UI_BLOCKS: Dict[str, Dict[str, str]] = {
    "kpi_row": {
        "id": "kpi_row",
        "label": "KPI Stat Pills Row",
        "description": "4 live SQLite-backed metric cards (Status, Tracked Items, Due Soon, Runs).",
    },
    "quick_capture_bar": {
        "id": "quick_capture_bar",
        "label": "Typed Quick Capture & Run Bar",
        "description": "Domain-specific structured inputs (text, date, number, URL) + instant task runner.",
    },
    "countdown_cards": {
        "id": "countdown_cards",
        "label": "Countdown & Renewal Cards",
        "description": "Live urgency countdown cards highlighting upcoming renewals, deadlines, and expiries.",
    },
    "ai_insight_card": {
        "id": "ai_insight_card",
        "label": "AI Briefing & Insight Card",
        "description": "On-demand Antigravity LLM executive analysis over your agent's tracked data.",
    },
    "history_table": {
        "id": "history_table",
        "label": "History & Records Table",
        "description": "Interactive SQLite table displaying tracked entries, runs, and row deletion.",
    },
    "habit_checklist": {
        "id": "habit_checklist",
        "label": "Interactive Daily Checklist",
        "description": "Persistent checkable routine items with completion badges and streak tracking.",
    },
    "status_timeline": {
        "id": "status_timeline",
        "label": "Live Execution Timeline",
        "description": "Chronological feed of scheduled jobs, checks, and autonomic events.",
    },
    "alert_banner": {
        "id": "alert_banner",
        "label": "Threshold & Health Alert Banner",
        "description": "Contextual status callout highlighting warnings, renewals, or SLA compliance.",
    },
    "sparkline_chart": {
        "id": "sparkline_chart",
        "label": "Trend Sparkline Chart",
        "description": "Zero-dependency inline SVG trend chart for numeric values, amounts, and HTTP latencies.",
    },
    "kanban_board": {
        "id": "kanban_board",
        "label": "Status Kanban Board",
        "description": "3-column interactive SQLite board (Active / Safe, Due Soon / Attention, Completed) with 1-click stage transitions.",
    },
    "document_vault": {
        "id": "document_vault",
        "label": "Document Upload & AI Extractor",
        "description": "Upload PDF, Word, Excel, CSV, Email, ICS, or Image scans to extract structured tracking items via LLM.",
    },
    "agent_chat": {
        "id": "agent_chat",
        "label": "Grounded Agent Q&A & Command Chat",
        "description": "Ask questions grounded on SQLite records & vaulted documents, or issue natural-language add/renew/complete commands.",
    },
}

DECLARATIVE_UI_BLOCKS = SUPPORTED_UI_BLOCKS

SUPPORTED_EVENT_TRIGGERS: Dict[str, Dict[str, str]] = {
    "gmail.paper_trail_detected": {
        "id": "gmail.paper_trail_detected",
        "label": "📬 On Billing / Policy / Paper-Trail Email",
        "description": "Triggers when Email Intelligence classifies an incoming invoice, renewal, or paper-trail email.",
    },
    "optimizer.ram_threshold_exceeded": {
        "id": "optimizer.ram_threshold_exceeded",
        "label": "🚀 On High Workstation RAM (>=85%)",
        "description": "Triggers when PC Performance Optimizer detects memory utilization above threshold.",
    },
    "health.workout_completed": {
        "id": "health.workout_completed",
        "label": "💪 On Workout / Conditioning Logged",
        "description": "Triggers when a Mudgal, Samtola, Bhim Gadha, or daily workout session is logged.",
    },
    "overview.morning_briefing": {
        "id": "overview.morning_briefing",
        "label": "🌅 On Morning Executive Briefing",
        "description": "Triggers alongside your daily morning executive briefing generation.",
    },
    "agent.alert": {
        "id": "agent.alert",
        "label": "🚨 On Any Fleet Agent Warning Alert",
        "description": "Triggers whenever another Fleet agent publishes a warning or threshold breach.",
    },
}


def get_supported_event_triggers() -> List[Dict[str, str]]:
    """Returns canonical Fleet EventBus triggers available for custom agent subscription."""
    return [dict(v) for v in SUPPORTED_EVENT_TRIGGERS.values()]

STARTER_BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "id": "renewal_sentinel",
        "title": "Insurance & Renewal Guard",
        "icon": "🛡️",
        "category": "Finance",
        "badge": "Popular",
        "prompt": (
            "Track my car, bike, and health insurance renewals, domain expiry dates, and annual bills "
            "every morning at 08:30 and alert me 15 days before any policy expires"
        ),
    },
    {
        "id": "http_uptime_watcher",
        "title": "Website & API Uptime Watcher",
        "icon": "🌐",
        "category": "Monitoring",
        "badge": "Live HTTP",
        "prompt": (
            "Monitor my production website URLs and API health endpoints every 30 minutes, "
            "record HTTP response latency, and alert me if any service is unreachable"
        ),
    },
    {
        "id": "git_ci_sentinel",
        "title": "Git Repo & Release Sentinel",
        "icon": "🐙",
        "category": "DevOps",
        "badge": "DevOps",
        "prompt": (
            "Check my local git repos and release milestones every evening at 18:00 "
            "and alert me if uncommitted changes or overdue milestones exist"
        ),
    },
    {
        "id": "ai_research_digest",
        "title": "AI Research & Reading Digest",
        "icon": "🧠",
        "category": "Knowledge",
        "badge": "Hybrid LLM",
        "prompt": (
            "Capture research articles, papers, and technical notes throughout the day "
            "and synthesize an executive action summary every morning at 09:00"
        ),
    },
    {
        "id": "habit_vitals_coach",
        "title": "Habit & Vitals Coach",
        "icon": "🌿",
        "category": "Health",
        "badge": "Streaks",
        "prompt": (
            "Remind me to do a posture stretch, hydration check, and log daily wellness metrics "
            "every hour with an interactive daily streak checklist"
        ),
    },
    {
        "id": "system_hygiene_guard",
        "title": "Disk & System Hygiene Guard",
        "icon": "🐳",
        "category": "System",
        "badge": "$0.00 Local",
        "prompt": (
            "Audit local disk free space and workstation storage thresholds every 2 hours "
            "and notify me when free disk capacity drops below target thresholds"
        ),
    },
]


def get_starter_blueprints() -> List[Dict[str, Any]]:
    """Returns curated 1-click starter blueprints for Step 1 of Zero-Code Agent Studio."""
    return [dict(bp) for bp in STARTER_BLUEPRINTS]


_DOMAIN_RULES: List[Dict[str, Any]] = [
    {
        "keywords": [
            "insurance", "policy", "renewal", "renew", "expiry", "expire", "car", "bike",
            "vehicle", "warranty", "license", "passport", "certificate", "domain",
        ],
        "category": "Finance",
        "icon": "🛡️",
        "archetype": "tracker",
        "intelligence_mode": "hybrid",
        "default_name": "Renewal & Policy Sentinel",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "countdown_cards",
            "ai_insight_card", "history_table",
        ],
        "routine_task": "check_upcoming_renewals",
        "fields": [
            {"key": "title", "label": "Policy / Item Name", "type": "text", "placeholder": "e.g. Car Insurance / Domain"},
            {"key": "provider", "label": "Provider / Insurer", "type": "text", "placeholder": "e.g. ICICI Lombard / Cloudflare"},
            {"key": "due_date", "label": "Expiry / Renewal Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Premium / Cost", "type": "number", "placeholder": "0.00"},
        ],
        "checklist_items": [
            {"key": "review_due_15d", "label": "Review policies expiring within 15 days"},
            {"key": "compare_quotes", "label": "Verify renewal quote or auto-pay status"},
            {"key": "archive_receipt", "label": "Log updated policy expiry date after payment"},
        ],
    },
    {
        "keywords": ["git", "repo", "commit", "branch", "pull request", "pr", "code", "ci", "build"],
        "category": "DevOps",
        "icon": "🐙",
        "archetype": "system_sentinel",
        "intelligence_mode": "hybrid",
        "default_name": "Git Workspace Sentinel",
        "permissions": ["db:read", "db:write", "ui:render", "system:diagnostics", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table", "status_timeline"],
        "routine_task": "audit_repositories",
        "fields": [
            {"key": "title", "label": "Repository / Service", "type": "text", "placeholder": "e.g. afcc-core"},
            {"key": "target_path", "label": "Workspace Path or Branch", "type": "text", "placeholder": "e.g. main"},
            {"key": "due_date", "label": "Release Target Date", "type": "date", "placeholder": "YYYY-MM-DD"},
        ],
        "checklist_items": [
            {"key": "clean_worktree", "label": "Commit or stash uncommitted workspace changes"},
            {"key": "verify_tests", "label": "Verify unit tests and security scanner pass"},
            {"key": "push_remote", "label": "Sync active feature branches before EOD"},
        ],
    },
    {
        "keywords": ["read", "book", "article", "note", "study", "learn", "research", "paper", "summary", "digest"],
        "category": "Knowledge",
        "icon": "📚",
        "archetype": "llm_analyst",
        "intelligence_mode": "hybrid",
        "default_name": "Reading & Knowledge Digest",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["kpi_row", "quick_capture_bar", "ai_insight_card", "habit_checklist", "history_table"],
        "routine_task": "daily_reading_digest",
        "fields": [
            {"key": "title", "label": "Topic / Article Title", "type": "text", "placeholder": "e.g. Multi-Agent Memory Paper"},
            {"key": "target_url", "label": "Reference URL", "type": "url", "placeholder": "https://..."},
            {"key": "notes", "label": "Key Takeaway", "type": "text", "placeholder": "Core insight or follow-up question"},
        ],
        "checklist_items": [
            {"key": "capture_reading", "label": "Capture at least 1 high-signal article or note"},
            {"key": "synthesize_digest", "label": "Run AI executive digest over recent notes"},
            {"key": "apply_insight", "label": "Convert top takeaway into a concrete action"},
        ],
    },
    {
        "keywords": ["expense", "budget", "bill", "invoice", "subscription", "finance", "money", "cost", "price", "saas"],
        "category": "Finance",
        "icon": "💳",
        "archetype": "tracker",
        "intelligence_mode": "hybrid",
        "default_name": "Subscription & Expense Guard",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "countdown_cards", "history_table"],
        "routine_task": "check_upcoming_renewals",
        "fields": [
            {"key": "title", "label": "Subscription / Bill", "type": "text", "placeholder": "e.g. Cloud GPU / Figma"},
            {"key": "provider", "label": "Vendor", "type": "text", "placeholder": "e.g. Google Cloud"},
            {"key": "due_date", "label": "Next Billing Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Monthly Cost", "type": "number", "placeholder": "0.00"},
        ],
        "checklist_items": [
            {"key": "audit_recurring", "label": "Audit upcoming recurring charges"},
            {"key": "prune_unused", "label": "Flag idle subscriptions before renewal"},
        ],
    },
    {
        "keywords": ["pomodoro", "focus", "deep work", "timer", "productivity", "sprint", "habit", "task"],
        "category": "Productivity",
        "icon": "🍅",
        "archetype": "tracker",
        "intelligence_mode": "hybrid",
        "default_name": "Deep Work & Focus Guardian",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["kpi_row", "quick_capture_bar", "habit_checklist", "history_table", "status_timeline"],
        "routine_task": "focus_session_check",
        "fields": [
            {"key": "title", "label": "Focus Block / Deliverable", "type": "text", "placeholder": "e.g. Architecture Deep Dive"},
            {"key": "numeric_value", "label": "Duration (Minutes)", "type": "number", "placeholder": "50"},
            {"key": "due_date", "label": "Target Date", "type": "date", "placeholder": "YYYY-MM-DD"},
        ],
        "checklist_items": [
            {"key": "morning_sprint", "label": "Complete 1 uninterrupted deep-work sprint"},
            {"key": "clear_blockers", "label": "Log top deliverable and clear distractions"},
        ],
    },
    {
        "keywords": [
            "glucose", "bsl", "sugar", "blood", "water", "hydration", "posture", "stretch",
            "health", "sleep", "workout", "calories", "step", "fasting", "med",
        ],
        "category": "Health",
        "icon": "🩸",
        "archetype": "tracker",
        "intelligence_mode": "hybrid",
        "default_name": "Metabolic & Vitals Tracker",
        "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "habit_checklist", "history_table"],
        "routine_task": "vitals_check_reminder",
        "fields": [
            {"key": "title", "label": "Metric / Activity", "type": "text", "placeholder": "e.g. Hydration / Fasting Reading"},
            {"key": "numeric_value", "label": "Reading / Value", "type": "number", "placeholder": "95"},
            {"key": "notes", "label": "Notes / Context", "type": "text", "placeholder": "e.g. Morning pre-breakfast"},
        ],
        "checklist_items": [
            {"key": "hydration_check", "label": "Complete hydration & posture stretch break"},
            {"key": "log_vitals", "label": "Record daily baseline wellness reading"},
            {"key": "movement_goal", "label": "Complete 20-minute post-meal walk"},
        ],
    },
    {
        "keywords": ["http", "url", "website", "endpoint", "uptime", "latency", "webhook", "api", "ping"],
        "category": "Monitoring",
        "icon": "🌐",
        "archetype": "http_watcher",
        "intelligence_mode": "hybrid",
        "default_name": "Endpoint & Uptime Watcher",
        "permissions": ["db:read", "db:write", "ui:render", "network:outbound", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "history_table", "status_timeline"],
        "routine_task": "probe_endpoints",
        "fields": [
            {"key": "title", "label": "Service / Endpoint Name", "type": "text", "placeholder": "e.g. Production Health API"},
            {"key": "target_url", "label": "Target URL", "type": "url", "placeholder": "https://example.com"},
            {"key": "numeric_value", "label": "Latency Budget (ms)", "type": "number", "placeholder": "1000"},
        ],
        "checklist_items": [
            {"key": "verify_endpoints", "label": "Verify all monitored URLs return HTTP 200"},
            {"key": "review_latency", "label": "Inspect p95 latency outliers"},
        ],
    },
    {
        "keywords": ["docker", "container", "server", "port", "homelab", "disk", "cpu", "ram", "network", "folder", "storage"],
        "category": "System",
        "icon": "🐳",
        "archetype": "system_sentinel",
        "intelligence_mode": "hybrid",
        "default_name": "Homelab & System Sentinel",
        "permissions": ["db:read", "db:write", "ui:render", "system:diagnostics", "event_bus:publish"],
        "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "status_timeline", "history_table"],
        "routine_task": "probe_service_health",
        "fields": [
            {"key": "title", "label": "Resource / Volume", "type": "text", "placeholder": "e.g. Workspace Drive Z:"},
            {"key": "numeric_value", "label": "Min Free Threshold (GB)", "type": "number", "placeholder": "20"},
            {"key": "notes", "label": "Notes", "type": "text", "placeholder": "Optional threshold note"},
        ],
        "checklist_items": [
            {"key": "check_disk", "label": "Verify disk free capacity exceeds threshold"},
            {"key": "clean_temp", "label": "Prune stale temporary artifacts if warned"},
        ],
    },
]


def _normalize_fields(fields: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """Sanitizes typed domain field definitions for safe HTML/JSON rendering."""
    allowed_types = {"text", "number", "date", "url"}
    cleaned: List[Dict[str, str]] = []
    seen = set()
    for raw in fields or []:
        if not isinstance(raw, dict):
            continue
        key = re.sub(r"[^a-z0-9_]", "_", str(raw.get("key") or raw.get("id") or "").lower()).strip("_")
        if not key or key in seen:
            continue
        seen.add(key)
        label = str(raw.get("label") or key.replace("_", " ").title()).strip()[:48]
        ftype = str(raw.get("type") or "text").lower().strip()
        if ftype not in allowed_types:
            ftype = "text"
        placeholder = str(raw.get("placeholder") or f"Enter {label.lower()}...").strip()[:80]
        cleaned.append({"key": key, "label": label, "type": ftype, "placeholder": placeholder})

    if not cleaned:
        cleaned = [
            {"key": "title", "label": "Entry / Target", "type": "text", "placeholder": "Enter item, note, or target..."},
            {"key": "due_date", "label": "Due / Target Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Value / Metric", "type": "number", "placeholder": "0"},
        ]
    return cleaned[:5]


def _normalize_checklist_items(items: Optional[List[Any]], agent_name: str, routine_task: str) -> List[Dict[str, str]]:
    """Normalizes checklist items into [{'key': ..., 'label': ...}] dicts."""
    normalized: List[Dict[str, str]] = []
    seen = set()
    for idx, item in enumerate(items or []):
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            raw_key = str(item.get("key") or f"step_{idx + 1}")
        else:
            label = str(item or "").strip()
            raw_key = f"step_{idx + 1}"
        if not label:
            continue
        key = re.sub(r"[^a-z0-9_]", "_", raw_key.lower()).strip("_") or f"step_{idx + 1}"
        if key in seen:
            key = f"{key}_{idx + 1}"
        seen.add(key)
        normalized.append({"key": key, "label": label[:120]})

    if not normalized:
        normalized = [
            {"key": "review_status", "label": f"Review {agent_name} morning status"},
            {"key": "verify_output", "label": f"Verify automated task ({routine_task}) output"},
        ]
    return normalized[:8]


def _build_clarifying_chips(
    ui_blocks: List[str],
    permissions: List[str],
    fields: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Generates contextual 1-click follow-up refinement chips for Step 1 Studio UX."""
    chips: List[Dict[str, Any]] = []
    field_keys = {f["key"] for f in fields}

    if "document_vault" not in ui_blocks:
        chips.append({
            "id": "add_doc_vault",
            "label": "📄 + Add Document Upload & AI Extractor",
            "add_blocks": ["document_vault"],
            "set_intelligence_mode": "hybrid",
        })

    if "agent_chat" not in ui_blocks:
        chips.append({
            "id": "add_agent_chat",
            "label": "💬 + Add Grounded Agent Q&A & Command Chat",
            "add_blocks": ["agent_chat"],
            "set_intelligence_mode": "hybrid",
        })

    if "countdown_cards" not in ui_blocks:
        chips.append({
            "id": "add_countdowns",
            "label": "⏳ + Add Renewal / Deadline Countdowns",
            "add_blocks": ["countdown_cards"],
            "add_field": (
                {"key": "due_date", "label": "Renewal / Due Date", "type": "date", "placeholder": "YYYY-MM-DD"}
                if "due_date" not in field_keys else None
            ),
        })

    if "ai_insight_card" not in ui_blocks:
        chips.append({
            "id": "add_ai_insight",
            "label": "🧠 + Add Antigravity AI Briefing Card",
            "add_blocks": ["ai_insight_card"],
            "set_intelligence_mode": "hybrid",
        })

    if "habit_checklist" not in ui_blocks:
        chips.append({
            "id": "add_checklist",
            "label": "✅ + Add Daily Streak Checklist",
            "add_blocks": ["habit_checklist"],
        })

    if "network:outbound" not in permissions:
        chips.append({
            "id": "add_http_probe",
            "label": "🌐 + Enable Live URL / HTTP Probing",
            "add_permissions": ["network:outbound"],
            "add_field": (
                {"key": "target_url", "label": "Target URL", "type": "url", "placeholder": "https://example.com"}
                if "target_url" not in field_keys else None
            ),
        })

    if "kanban_board" not in ui_blocks:
        chips.append({
            "id": "add_kanban",
            "label": "🗂️ + Add 3-Stage Status Kanban Board",
            "add_blocks": ["kanban_board"],
        })

    if "status_timeline" not in ui_blocks:
        chips.append({
            "id": "add_timeline",
            "label": "⏱️ + Add Execution Event Timeline",
            "add_blocks": ["status_timeline"],
        })

    return chips[:4]


def _extract_schedule_from_prompt(prompt: str) -> Dict[str, Any]:
    """Deterministically extracts time, interval_hours, or cron from natural language."""
    lower = prompt.lower()

    m_min = re.search(r"every\s+(\d+)\s*(?:minutes?|mins?|m\b)", lower)
    if m_min:
        mins = max(5, min(59, int(m_min.group(1))))
        return {"type": "cron", "value": f"*/{mins} * * * *", "display": f"Every {mins}m"}

    m_hr = re.search(r"every\s+(\d+)\s*(?:hours?|hrs?|h\b)", lower)
    if m_hr:
        hrs = max(1, min(24, int(m_hr.group(1))))
        return {"type": "interval_hours", "value": hrs, "display": f"Every {hrs}h"}
    if "every hour" in lower or "hourly" in lower:
        return {"type": "interval_hours", "value": 1, "display": "Every 1h"}

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
    m_named = re.search(r"(?:called|named)\s+['\"]?([A-Za-z0-9 _\-]{3,35})['\"]?", cleaned, re.I)
    if m_named:
        raw_name = m_named.group(1).strip()
        words = [w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", raw_name)[:4]]
        name = " ".join(words)
    else:
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
    fields: Optional[List[Dict[str, Any]]] = None,
    checklist_items: Optional[List[Any]] = None,
    intelligence_mode: str = "hybrid",
) -> str:
    """
    Composes a zero-dependency, responsive HTML panel containing declarative UI blocks
    wired to CustomAgentRuntime for live SQLite state, CRUD, checklists, countdowns, and AI insights.
    """
    blocks = ui_blocks or ["kpi_row", "quick_capture_bar", "history_table"]
    safe_name = html_lib.escape(str(name))
    safe_desc = html_lib.escape(str(description))
    safe_icon = html_lib.escape(str(icon))
    safe_sched = html_lib.escape(str(schedule_display))
    safe_task = re.sub(r"[^a-zA-Z0-9_-]", "_", str(routine_task or "run_check"))
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(agent_id))

    norm_fields = _normalize_fields(fields) if fields is not None else [
        {"key": "title", "label": "Note / Target", "type": "text", "placeholder": f"Enter note, parameter, or target for {name}..."},
    ]
    norm_checks = _normalize_checklist_items(checklist_items, name, safe_task)

    mode_badge = "$0.00 Zero-Token Mode"
    if intelligence_mode == "hybrid":
        mode_badge = "⚡ $0.00 Routine + On-Demand AI"
    elif intelligence_mode == "llm":
        mode_badge = "🧠 Antigravity LLM Mode"

    sections: List[str] = []

    # 1. Alert Banner Block
    if "alert_banner" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: alert_banner -->
  <div id="{safe_id}_alert_banner" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 16px; border-radius: 10px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3);">
    <div style="display: flex; align-items: center; gap: 10px;">
      <span id="{safe_id}_alert_dot" style="font-size: 16px;">🟢</span>
      <div>
        <div id="{safe_id}_alert_title" style="font-size: 12.5px; font-weight: 700; color: #10b981;">{safe_name} Active &amp; Nominal</div>
        <div id="{safe_id}_alert_sub" style="font-size: 11.5px; color: #94a3b8;">Schedule: {safe_sched} | Task: <code>{safe_task}</code></div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <span style="font-size: 11px; padding: 3px 9px; border-radius: 999px; background: rgba(15, 23, 42, 0.6); color: #38bdf8;">{mode_badge}</span>
      <button type="button" class="btn btn-secondary" title="Execute routine check now" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.runTask('{safe_id}', '{safe_task}');}}" style="padding: 4px 10px; font-size: 11px;">▶ Run Now</button>
    </div>
  </div>"""
        )

    # 2. KPI Stat Pills Row
    if "kpi_row" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: kpi_row -->
  <div id="{safe_id}_kpi_grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 12px;">
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Status</div>
      <div id="{safe_id}_kpi_status" style="font-size: 17px; font-weight: 700; color: #10b981; margin-top: 4px;">Ready</div>
    </div>
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Tracked Items</div>
      <div id="{safe_id}_kpi_entries" style="font-size: 17px; font-weight: 700; color: #f8fafc; margin-top: 4px;">0</div>
    </div>
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Due Soon / Alerts</div>
      <div id="{safe_id}_kpi_due" style="font-size: 17px; font-weight: 700; color: #38bdf8; margin-top: 4px;">0</div>
    </div>
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
      <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Schedule Cadence</div>
      <div id="{safe_id}_kpi_runs" style="font-size: 14px; font-weight: 700; color: #38bdf8; margin-top: 4px;">{safe_sched}</div>
    </div>
  </div>"""
        )

    # 2b. Document Upload & AI Extractor Block (Phase 5)
    if "document_vault" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: document_vault -->
  <div id="{safe_id}_doc_vault_card" style="background: linear-gradient(135deg, rgba(14, 116, 144, 0.18), rgba(15, 23, 42, 0.72)); border: 1px dashed rgba(56, 189, 248, 0.42); border-radius: 10px; padding: 14px 16px;" ondragover="event.preventDefault(); this.style.borderColor='#38bdf8';" ondragleave="this.style.borderColor='rgba(56, 189, 248, 0.42)';" ondrop="if(window.CustomAgentRuntime){{CustomAgentRuntime.handleDocDrop(event, '{safe_id}');}}">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
      <div>
        <div style="font-size: 13px; font-weight: 700; color: #e0f2fe;">📄 Document Upload &amp; AI Tracking Extractor</div>
        <div style="font-size: 11.5px; color: #94a3b8;">Drop or select a policy PDF, contract DOCX, Excel/CSV schedule, lab report, invoice, email (.eml), calendar (.ics), or image scan to extract trackable items via LLM.</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <button type="button" title="Scan watched inbox drop-folder (fleet/data/user/inbox/{safe_id}) for new documents" id="{safe_id}_scan_inbox_btn" class="btn btn-secondary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.scanInboxFolder('{safe_id}');}}" style="padding: 3px 10px; font-size: 11px; font-weight: 600; border-color: rgba(56, 189, 248, 0.4); color: #7dd3fc;">📥 Scan Inbox</button>
        <span id="{safe_id}_doc_count_badge" style="font-size: 11px; padding: 2px 9px; border-radius: 999px; background: rgba(56, 189, 248, 0.15); color: #38bdf8;">PDF • DOCX • XLSX • CSV • EML • Image</span>
      </div>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
      <input type="file" id="{safe_id}_doc_file_input" multiple accept=".pdf,.docx,.xlsx,.csv,.tsv,.txt,.md,.json,.eml,.ics,.html,.htm,.png,.jpg,.jpeg,.webp" style="flex: 1; min-width: 210px; padding: 6px 10px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.35); color: #f8fafc; font-size: 12px;">
      <input type="text" id="{safe_id}_doc_hint_input" placeholder="Optional focus (e.g. extract expiry date, premium &amp; policy #)" style="flex: 1.3; min-width: 210px; padding: 7px 11px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.35); color: #f8fafc; font-size: 12px;">
      <label title="Automatically save all extracted items straight into SQLite without review step" style="display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; color: #cbd5e1; cursor: pointer;">
        <input type="checkbox" id="{safe_id}_doc_auto_commit">
        <span>Auto-track</span>
      </label>
      <button type="button" title="Extract structured tracking items from uploaded document using LLM" id="{safe_id}_doc_extract_btn" class="btn btn-primary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.uploadAndExtractDocument('{safe_id}');}}" style="padding: 7px 14px; font-size: 12px; font-weight: 700; white-space: nowrap;">🧠 Extract Items</button>
    </div>
    <div id="{safe_id}_doc_preview_box" style="display: none; margin-top: 12px; padding: 12px; border-radius: 8px; background: rgba(2, 6, 23, 0.72); border: 1px solid rgba(56, 189, 248, 0.3);"></div>
    <div id="{safe_id}_doc_history_box" style="display: none; margin-top: 10px; font-size: 11.5px; color: #94a3b8;"></div>
  </div>"""
        )

    # 3. Typed Quick Capture & Action Bar
    if "quick_capture_bar" in blocks:
        field_inputs: List[str] = []
        for idx, fld in enumerate(norm_fields):
            fkey = html_lib.escape(fld["key"])
            flabel = html_lib.escape(fld["label"])
            ftype = html_lib.escape(fld["type"])
            fph = html_lib.escape(fld["placeholder"])
            input_id = f"{safe_id}_quick_input" if idx == 0 else f"{safe_id}_field_{fkey}"
            flex_style = "flex: 2; min-width: 190px;" if idx == 0 else "flex: 1; min-width: 140px;"
            step_attr = ' step="any"' if ftype == "number" else ""
            field_inputs.append(
                f"""      <div style="{flex_style} display: flex; flex-direction: column; gap: 4px;">
        <label for="{input_id}" style="font-size: 10.5px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">{flabel}</label>
        <input type="{ftype}"{step_attr} id="{input_id}" data-studio-field="{fkey}" placeholder="{fph}" style="width: 100%; padding: 8px 11px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.12); background: rgba(0, 0, 0, 0.35); color: #f8fafc; font-size: 12.5px; box-sizing: border-box;">
      </div>"""
            )
        inputs_html = "\n".join(field_inputs)
        sections.append(
            f"""  <!-- Declarative Block: quick_capture_bar -->
  <div id="{safe_id}_capture_card" style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px 16px;">
    <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;">
{inputs_html}
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <button type="button" title="Save entry to SQLite" class="btn btn-secondary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.submitRecord('{safe_id}');}}" style="padding: 8px 14px; font-size: 12.5px; font-weight: 600; border-color: rgba(56, 189, 248, 0.4); color: #38bdf8;">➕ Save Entry</button>
        <button type="button" title="Trigger scheduled task {safe_task} now" class="btn btn-primary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.runTask('{safe_id}', '{safe_task}');}}else if(window.triggerScheduledTaskNow){{triggerScheduledTaskNow('{safe_id}', '{safe_task}');}}" style="padding: 8px 15px; font-size: 12.5px; font-weight: 600;">▶ Run {safe_task}</button>
      </div>
    </div>
  </div>"""
        )

    # 4. Countdown & Renewal Cards Block
    if "countdown_cards" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: countdown_cards -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
      <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">⏳ Upcoming Renewals &amp; Deadlines</div>
      <span id="{safe_id}_countdown_badge" style="font-size: 11px; color: #94a3b8;">15-day alert window</span>
    </div>
    <div id="{safe_id}_countdown_box" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; font-size: 12.5px; color: #94a3b8;">
      <div style="padding: 10px 12px; border-radius: 8px; background: rgba(0, 0, 0, 0.25);">Add an entry with a date above to track live countdowns and expiry alerts.</div>
    </div>
  </div>"""
        )

    # 4b. Trend Sparkline Chart Block (Phase 3)
    if "sparkline_chart" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: sparkline_chart -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
      <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">📈 Metric &amp; Latency Trend Sparkline</div>
      <div id="{safe_id}_sparkline_stats" style="font-size: 11px; color: #38bdf8; font-family: monospace;">Min: -- • Avg: -- • Latest: --</div>
    </div>
    <div id="{safe_id}_sparkline_box" style="min-height: 92px; padding: 10px 12px; border-radius: 8px; background: rgba(0, 0, 0, 0.28); display: flex; align-items: center; justify-content: center; font-size: 12px; color: #94a3b8;">
      Log numeric entries or run HTTP latency checks to render a live SVG trend sparkline.
    </div>
  </div>"""
        )

    # 4c. Status Kanban Board Block (Phase 4)
    if "kanban_board" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: kanban_board -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
      <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">🗂️ Status Kanban Board</div>
      <span id="{safe_id}_kanban_badge" style="font-size: 11px; color: #94a3b8;">Active • Attention • Completed</span>
    </div>
    <div id="{safe_id}_kanban_box" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; font-size: 12px; color: #94a3b8;">
      <div style="padding: 10px 12px; border-radius: 8px; background: rgba(0, 0, 0, 0.25);">Add entries in Quick Capture to organize items across Active, Due Soon, and Completed columns.</div>
    </div>
  </div>"""
        )

    # 5. AI Briefing & Insight Card Block
    if "ai_insight_card" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: ai_insight_card -->
  <div style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.55), rgba(15, 23, 42, 0.75)); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
      <div style="font-size: 13px; font-weight: 700; color: #e9d5ff;">🧠 Antigravity AI Briefing &amp; Insights</div>
      <button type="button" title="Run on-demand Antigravity LLM analysis over tracked entries" class="btn btn-secondary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.runAiAnalyze('{safe_id}');}}" style="padding: 5px 12px; font-size: 11.5px; font-weight: 600; border-color: rgba(167, 139, 250, 0.45); color: #ddd6fe;">✨ Analyze with Antigravity LLM</button>
    </div>
    <div id="{safe_id}_insight_box" style="font-size: 12.5px; color: #cbd5e1; line-height: 1.55; padding: 10px 12px; border-radius: 8px; background: rgba(0, 0, 0, 0.28);">
      Routine checks run at $0.00 token cost. Click <strong>Analyze with Antigravity LLM</strong> anytime for an executive briefing over your tracked entries.
    </div>
  </div>"""
        )

    # 5b. Grounded Agent Q&A & Command Chat Block (Phase 6)
    if "agent_chat" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: agent_chat -->
  <div id="{safe_id}_chat_card" style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.78), rgba(17, 24, 39, 0.88)); border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
      <div>
        <div style="font-size: 13px; font-weight: 700; color: #e0f2fe;">💬 Ask &amp; Command Agent (Grounded RAG)</div>
        <div style="font-size: 11.5px; color: #94a3b8;">Query your SQLite entries &amp; uploaded documents, or command: <code>add ... due YYYY-MM-DD for 1500</code>, <code>renew ...</code>, <code>complete ...</code></div>
      </div>
      <div style="display: flex; gap: 6px; flex-wrap: wrap;">
        <button type="button" title="Ask for upcoming deadlines and total tracked amount" class="btn btn-secondary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.sendAgentChat('{safe_id}', 'What items are due soon and what is my active total?');}}" style="padding: 3px 9px; font-size: 11px; color: #7dd3fc; border-color: rgba(56, 189, 248, 0.35);">⏳ Due soon &amp; total?</button>
        <button type="button" title="Summarize key details from uploaded documents" class="btn btn-secondary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.sendAgentChat('{safe_id}', 'Summarize key numbers and dates from my uploaded documents');}}" style="padding: 3px 9px; font-size: 11px; color: #c4b5fd; border-color: rgba(167, 139, 250, 0.35);">📄 Doc highlights</button>
      </div>
    </div>
    <div id="{safe_id}_chat_log" style="max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; border-radius: 8px; background: rgba(0, 0, 0, 0.34); font-size: 12.5px; color: #cbd5e1; margin-bottom: 10px;">
      <div style="color: #94a3b8; font-size: 12px;">Ask any question about tracked items or uploaded PDFs/docs, or type a direct command below.</div>
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <input type="text" id="{safe_id}_chat_input" placeholder="Ask about your records/docs or type 'add Policy Renewal due 2026-12-15 for 18500'..." onkeydown="if(event.key==='Enter'&amp;&amp;window.CustomAgentRuntime){{event.preventDefault();CustomAgentRuntime.sendAgentChat('{safe_id}');}}" style="flex: 1; padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.4); color: #f8fafc; font-size: 12.5px;">
      <button type="button" title="Send question or command to grounded agent chat" id="{safe_id}_chat_send_btn" class="btn btn-primary" onclick="if(window.CustomAgentRuntime){{CustomAgentRuntime.sendAgentChat('{safe_id}');}}" style="padding: 8px 14px; font-size: 12px; font-weight: 700; white-space: nowrap;">💬 Ask / Command</button>
    </div>
  </div>"""
        )

    # 6. Habit Checklist Block
    if "habit_checklist" in blocks:
        check_rows = []
        for item in norm_checks:
            ckey = html_lib.escape(item["key"])
            clabel = html_lib.escape(item["label"])
            check_rows.append(
                f'      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;"><input type="checkbox" data-check-key="{ckey}" onchange="if(window.CustomAgentRuntime){{CustomAgentRuntime.toggleCheck(\'{safe_id}\', \'{ckey}\', this.checked, \'{clabel}\');}}"> <span>{clabel}</span></label>'
            )
        checks_html = "\n".join(check_rows)
        sections.append(
            f"""  <!-- Declarative Block: habit_checklist -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
      <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">✅ Daily Action Checklist</div>
      <span id="{safe_id}_checklist_streak" style="font-size: 11px; padding: 2px 8px; border-radius: 999px; background: rgba(16, 185, 129, 0.15); color: #34d399;">0 / {len(norm_checks)} Done</span>
    </div>
    <div id="{safe_id}_checklist_box" style="display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #cbd5e1;">
{checks_html}
    </div>
  </div>"""
        )

    # 7. History Table Block (Phase 4: Live Search Filter + 1-Click CSV Export)
    if "history_table" in blocks:
        sections.append(
            f"""  <!-- Declarative Block: history_table -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">📋 Recent Execution &amp; Activity Log</div>
        <span id="{safe_id}_history_count" style="font-size: 11px; color: #94a3b8;">SQLite Backed</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <input type="search" id="{safe_id}_history_search" placeholder="Filter records..." oninput="if(window.CustomAgentRuntime){{CustomAgentRuntime.filterHistory('{safe_id}', this.value);}}" style="padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.35); color: #f8fafc; font-size: 11.5px; min-width: 155px;">
        <a href="/api/fleet/agents/{safe_id}/export.csv" download="{safe_id}_records.csv" title="Download all SQLite records as CSV" class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px; text-decoration: none; border-color: rgba(16, 185, 129, 0.4); color: #34d399;">📥 Export CSV</a>
      </div>
    </div>
    <div id="{safe_id}_history_box" style="font-size: 12.5px; color: #94a3b8; padding: 10px; border-radius: 8px; background: rgba(0, 0, 0, 0.25); overflow-x: auto;">
      {safe_desc} — Ready for scheduled or manual execution.
    </div>
  </div>"""
        )

    # 8. Status Timeline Block
    if "status_timeline" in blocks:
        perms_str = html_lib.escape(", ".join(permissions))
        sections.append(
            f"""  <!-- Declarative Block: status_timeline -->
  <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 8px;">⏱️ Autonomic Event Timeline</div>
    <div id="{safe_id}_timeline_box" style="font-size: 12px; color: #38bdf8; font-family: monospace; display: flex; flex-direction: column; gap: 5px;">
      <div>[INIT] {safe_icon} {safe_name} mounted with permissions: {perms_str}</div>
    </div>
  </div>"""
        )

    joined_sections = "\n\n".join(sections)
    return f"""<div class="panel-section" id="studio_panel_{safe_id}" data-studio-agent="{safe_id}" data-routine-task="{safe_task}" style="display: flex; flex-direction: column; gap: 14px;">
{joined_sections}
</div>
"""


def _is_safe_public_http_url(url: str) -> bool:
    """Validates HTTP/HTTPS URL scheme for outbound health probes."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    host = (parsed.hostname or "").lower()
    if host in ("169.254.169.254", "metadata.google.internal"):
        return False
    return True


def execute_studio_agent_runtime(
    agent: Any,
    task: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Universal functional execution engine for Zero-Code Studio custom agents.
    Evaluates SQLite entries, renewal countdowns, HTTP probes, disk health, and optional Antigravity LLM analysis.
    """
    payload = payload if isinstance(payload, dict) else {}
    meta = getattr(agent, "manifest_meta", {}) or {}
    archetype = str(meta.get("archetype") or getattr(agent, "archetype", "tracker") or "tracker")
    intelligence_mode = str(meta.get("intelligence_mode") or getattr(agent, "intelligence_mode", "hybrid") or "hybrid")
    perms = set(getattr(agent, "permissions", []) or [])
    db = getattr(agent, "db", None)

    # Phase 6: Watched Drop-Folder & EventBus Email Payload Auto-Ingestion
    inbox_scan_summary: Optional[Dict[str, Any]] = None
    has_event_doc_payload = bool(
        payload.get("subject") or payload.get("email_subject") or payload.get("attachment_base64") or payload.get("content_base64")
    )
    if db is not None and "db:write" in perms and (
        bool(meta.get("auto_ingest_inbox")) or task == "scan_inbox" or has_event_doc_payload
    ):
        try:
            from fleet.core.studio_phase6 import scan_and_ingest_agent_inbox
            inbox_scan_summary = scan_and_ingest_agent_inbox(agent=agent, db=db, payload=payload)
        except Exception as exc:
            logger.debug("Phase 6 inbox auto-ingestion skipped for %s: %s", agent.id, exc)

    entries: List[Dict[str, Any]] = []
    if db is not None and "db:read" in perms:
        try:
            entries = db.list_custom_agent_records(agent.id, record_type="entry", limit=50)
        except Exception as exc:
            logger.debug("Could not read custom_agent_records for %s: %s", agent.id, exc)

    today = date.today()
    overdue_items: List[str] = []
    due_soon_items: List[str] = []
    total_numeric = 0.0
    urls_to_probe: List[tuple[str, str]] = []

    for entry in entries:
        title = str(entry.get("title") or "Item")
        entry_status = str(entry.get("status") or "ok").strip().lower()
        is_completed = entry_status in ("completed", "done", "resolved")
        total_numeric += float(entry.get("numeric_value") or 0.0)
        due_raw = str(entry.get("due_date") or "").strip()
        if due_raw and not is_completed:
            try:
                days_left = (date.fromisoformat(due_raw[:10]) - today).days
                if days_left < 0:
                    overdue_items.append(f"{title} ({abs(days_left)}d overdue)")
                elif days_left <= 15:
                    due_soon_items.append(f"{title} (in {days_left}d)")
            except ValueError:
                pass
        raw_edata = entry.get("data")
        edata: Dict[str, Any] = raw_edata if isinstance(raw_edata, dict) else {}
        t_url = str(edata.get("target_url") or "").strip()
        if t_url and _is_safe_public_http_url(t_url):
            urls_to_probe.append((title, t_url))

    direct_url = str(payload.get("target_url") or "").strip()
    if direct_url and _is_safe_public_http_url(direct_url):
        urls_to_probe.insert(0, (str(payload.get("title") or direct_url), direct_url))

    run_status = "ok"
    findings: List[str] = []
    metrics: Dict[str, Any] = {
        "tracked_entries": len(entries),
        "overdue_count": len(overdue_items),
        "due_soon_count": len(due_soon_items),
        "numeric_sum": round(total_numeric, 2),
    }

    if inbox_scan_summary is not None:
        metrics["inbox_ingested_docs"] = int(inbox_scan_summary.get("ingested_documents_count") or 0)
        metrics["inbox_committed_items"] = int(inbox_scan_summary.get("committed_items_count") or 0)
        if metrics["inbox_ingested_docs"] > 0:
            findings.append(
                f"Auto-ingested {metrics['inbox_ingested_docs']} document(s) ({metrics['inbox_committed_items']} item(s)) from inbox/event"
            )

    if overdue_items:
        run_status = "warning"
        findings.append(f"Overdue ({len(overdue_items)}): " + ", ".join(overdue_items[:3]))
    if due_soon_items:
        if run_status == "ok":
            run_status = "warning"
        findings.append(f"Due within 15d ({len(due_soon_items)}): " + ", ".join(due_soon_items[:3]))

    # Archetype: HTTP Watcher
    if (archetype == "http_watcher" or urls_to_probe) and "network:outbound" in perms and urls_to_probe:
        probe_results = []
        for label, url in urls_to_probe[:5]:
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(url, method="GET", headers={"User-Agent": "AFCC-AgentSentinel/2.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310 - scheme validated via _is_safe_public_http_url
                    ms = round((time.perf_counter() - t0) * 1000, 1)
                    code = int(getattr(resp, "status", 200))
                    probe_results.append({"name": label, "url": url, "http_status": code, "latency_ms": ms})
                    if code >= 400:
                        run_status = "warning"
                        findings.append(f"{label} returned HTTP {code} ({ms}ms)")
                    else:
                        findings.append(f"{label}: HTTP {code} in {ms}ms")
            except Exception as exc:
                ms = round((time.perf_counter() - t0) * 1000, 1)
                run_status = "warning"
                probe_results.append({"name": label, "url": url, "http_status": 0, "latency_ms": ms, "error": str(exc)})
                findings.append(f"{label} unreachable ({exc})")
        metrics["http_probes"] = probe_results

    # Archetype: System Sentinel
    if archetype == "system_sentinel" and "system:diagnostics" in perms:
        try:
            target_dir = str(getattr(agent, "agent_dir", "."))
            usage = shutil.disk_usage(target_dir)
            free_gb = round(usage.free / (1024 ** 3), 1)
            used_pct = round((usage.used / max(usage.total, 1)) * 100, 1)
            metrics["disk_free_gb"] = free_gb
            metrics["disk_used_pct"] = used_pct
            threshold = float(agent.get_setting("target_threshold", 85) or 85)
            if used_pct >= threshold:
                run_status = "warning"
                findings.append(f"Disk utilization {used_pct}% exceeds {threshold}% threshold ({free_gb} GB free)")
            else:
                findings.append(f"Workspace storage healthy: {free_gb} GB free ({used_pct}% used)")
        except Exception as exc:
            logger.debug("System diagnostics check skipped: %s", exc)

    if not findings:
        if entries:
            findings.append(
                f"Audited {len(entries)} tracked item(s); all deadlines and thresholds nominal."
            )
        else:
            findings.append(
                f"Ready and monitoring ({task}). Add items in Quick Capture to track renewals, targets, or metrics."
            )

    summary_message = " | ".join(findings)
    ai_summary = ""
    used_llm = False

    # On-demand AI Analysis or Full LLM Intelligence Mode
    wants_llm = (task == "ai_analyze") or (intelligence_mode == "llm" and not payload.get("skip_llm"))
    if wants_llm:
        entries_digest = "\n".join(
            f"- {e.get('title')} (due={e.get('due_date') or 'n/a'}, value={e.get('numeric_value') or 0}, data={json.dumps(e.get('data') or {})})"
            for e in entries[:20]
        ) or "(No tracked records yet)"
        analysis_prompt = (
            f"Agent: {agent.display_name} ({agent.id})\n"
            f"Purpose: {meta.get('description') or agent.display_name}\n"
            f"Deterministic Findings: {summary_message}\n"
            f"Tracked Records:\n{entries_digest}\n\n"
            "Provide a concise, well-formatted executive briefing in Markdown using short section bullets:\n"
            "- **Priorities**: key upcoming items with dates/amounts\n"
            "- **Risks / Gaps**: overdue or <=15-day renewal risks\n"
            "- **Recommended Next Action**: concrete immediate step"
        )
        try:
            from fleet.core.document_extractor import resolve_afcc_connected_llm
            llm_cfg = resolve_afcc_connected_llm(
                provider=str(meta.get("provider") or getattr(agent, "preferred_provider", "") or "auto"),
                model=str(meta.get("model") or getattr(agent, "preferred_model", "") or "") or None,
            )
            eff_prov = str(llm_cfg.get("provider") or "").strip() if llm_cfg.get("is_llm_connected") else None
            eff_mdl = str(llm_cfg.get("model") or "").strip() if llm_cfg.get("is_llm_connected") else None
            llm_resp = (
                agent.complete_prompt(analysis_prompt, provider=eff_prov, model=eff_mdl)
                if (eff_prov or eff_mdl)
                else agent.complete_prompt(analysis_prompt)
            )
            resp_status = ""
            used_model_label = eff_mdl or agent.preferred_model or "auto"
            if isinstance(llm_resp, dict):
                resp_status = str(llm_resp.get("status") or "").upper()
                if llm_resp.get("model"):
                    used_model_label = str(llm_resp["model"])
                ai_summary = str(llm_resp.get("text") or llm_resp.get("response") or "").strip()
            elif isinstance(llm_resp, str):
                ai_summary = llm_resp.strip()

            is_generic_fallback = (
                resp_status == "FALLBACK"
                or ai_summary.startswith("Fleet Autonomous Intelligence: Processed prompt")
            )
            if ai_summary and not is_generic_fallback:
                used_llm = True
            else:
                total_val = round(sum(float(e.get("numeric_value") or 0.0) for e in entries), 2)
                ai_summary = (
                    f"- **Status**: {summary_message}\n"
                    f"- **Portfolio Snapshot**: **{len(entries)}** tracked record(s)"
                    + (f" totaling **{total_val:,.2f}**" if total_val else "")
                    + ".\n"
                    f"- **Next Action**: Review flagged items within `15d` and mark completed steps in your Daily Action Checklist."
                )

            if ai_summary and db is not None and "db:write" in perms:
                db.add_custom_agent_record(
                    agent.id,
                    title=f"AI Briefing ({datetime.now().strftime('%H:%M')})",
                    record_type="ai_insight",
                    data={
                        "summary": ai_summary,
                        "model": used_model_label if used_llm else "hybrid-local",
                        "findings": summary_message,
                    },
                    status=run_status,
                )
        except Exception as exc:
            ai_summary = f"LLM analysis unavailable ({exc}). Deterministic status: {summary_message}"

    # Phase 6: Execute Configurable Outbound Action Hooks (auto_create_task, desktop_toast, markdown_report, emit_followup_event)
    if task != "ai_analyze":
        try:
            from fleet.core.studio_phase6 import execute_outbound_action_hooks
            hook_res = execute_outbound_action_hooks(
                agent=agent,
                db=db,
                run_status=run_status,
                summary_message=summary_message,
                entries=entries,
                overdue_items=overdue_items,
                due_soon_items=due_soon_items,
            )
            if hook_res.get("executed"):
                metrics["outbound_actions_executed"] = hook_res["executed"]
            if hook_res.get("report_path"):
                metrics["report_path"] = hook_res["report_path"]
        except Exception as exc:
            logger.debug("Outbound action hooks skipped for %s: %s", agent.id, exc)

    # Persist execution run record
    if db is not None and "db:write" in perms and task != "ai_analyze":
        try:
            db.add_custom_agent_record(
                agent.id,
                title=summary_message[:200],
                record_type="run",
                data={"task": task, "metrics": metrics, "used_llm": used_llm},
                status=run_status,
                numeric_value=float(len(entries)),
            )
        except Exception as exc:
            logger.debug("Could not persist run record for %s: %s", agent.id, exc)

    # Publish warning event on EventBus if configured
    event_bus = getattr(agent, "event_bus", None)
    if run_status == "warning" and event_bus is not None and "event_bus:publish" in perms:
        try:
            event_bus.publish(
                "agent.alert",
                {"agent_id": agent.id, "name": agent.display_name, "message": summary_message},
            )
        except Exception:
            pass

    return {
        "status": "success",
        "health_status": run_status,
        "title": f"{agent.display_icon} {agent.display_name}",
        "message": ai_summary if (task == "ai_analyze" and ai_summary) else summary_message,
        "ai_insight": ai_summary,
        "metrics": metrics,
        "used_llm": used_llm,
        "agent_id": agent.id,
        "task": task,
    }


def generate_custom_agent_code(
    agent_id: str,
    name: str,
    icon: str,
    description: str,
    routine_task: str = "run_check",
    initial_order: int = 75,
    archetype: str = "tracker",
    intelligence_mode: str = "hybrid",
    settings_schema: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generates clean, AST-audited, functional Python code for a Zero-Code Studio custom agent."""
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", agent_id.lower()).strip("_") or "custom_agent"
    class_name = "".join(part.capitalize() for part in clean_id.split("_") if part) + "Agent"
    safe_doc = description.replace('"""', "'''").replace("\r", " ").strip()
    schema_list = settings_schema or [
        {
            "id": "enabled_notifications",
            "label": "Enable Desktop Alerts",
            "type": "boolean",
            "default": True,
            "description": f"Send desktop notification when {name} flags warnings.",
        },
        {
            "id": "target_threshold",
            "label": "Alert Threshold / Target",
            "type": "number",
            "default": 85,
            "description": "Numeric threshold for automated warning checks.",
        },
    ]

    return f'''"""
{name} ({clean_id}) — Synthesized by Fleet Zero-Code Agent Studio.
Goal: {safe_doc}
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent
from fleet.core.agent_studio import execute_studio_agent_runtime


class {class_name}(FleetAgent):
    archetype = {repr(archetype)}
    intelligence_mode = {repr(intelligence_mode)}
    routine_task = {repr(routine_task)}

    @property
    def id(self) -> str:
        return {repr(clean_id)}

    @property
    def name(self) -> str:
        return {repr(name)}

    @property
    def icon(self) -> str:
        return {repr(icon)}

    @property
    def order(self) -> int:
        return {int(initial_order)}

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return {repr(schema_list)}

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        active_task = task or self.routine_task
        return execute_studio_agent_runtime(self, task=active_task, payload=payload)
'''


def dry_run_agent_spec(spec: Dict[str, Any], sample_input: str = "") -> Dict[str, Any]:
    """
    Phase 2 Sandbox Dry-Run Validator:
    1. Verifies Python AST syntax & blocks unsafe calls on agent_py.
    2. Validates all declared permissions against ALLOWED_AGENT_PERMISSIONS.
    3. Simulates deterministic archetype execution in-memory without mutating SQLite.
    """
    t0 = time.perf_counter()
    if not isinstance(spec, dict):
        raise ValueError("Dry-run spec must be a JSON object.")

    agent_id = str(spec.get("agent_id") or spec.get("id") or "preview_agent").strip()
    name = str(spec.get("name") or "Preview Agent").strip()
    icon = str(spec.get("icon") or "✨").strip()
    archetype = str(spec.get("archetype") or "tracker").strip()
    routine_task = str(spec.get("routine_task") or "run_check").strip()
    intelligence_mode = str(spec.get("intelligence_mode") or "hybrid").strip()

    perm_aliases = {
        "network:http": "network:outbound",
        "notifications:send": "event_bus:publish",
        "system:exec": "system:diagnostics",
        "storage:data_read": "db:read",
        "storage:data_write": "db:write",
    }
    raw_perms = spec.get("permissions") or ["db:read", "db:write", "ui:render"]
    perms = [perm_aliases.get(str(p), str(p)) for p in raw_perms]
    invalid_perms = [p for p in perms if p not in ALLOWED_AGENT_PERMISSIONS]
    if invalid_perms:
        return {
            "status": "error",
            "ast_valid": False,
            "permissions_valid": False,
            "message": f"Blocked permissions outside sandbox allowlist: {invalid_perms}",
        }

    code = str(spec.get("agent_py") or "").strip()
    if not code:
        code = generate_custom_agent_code(
            agent_id=agent_id,
            name=name,
            icon=icon,
            description=str(spec.get("description") or name),
            routine_task=routine_task,
            archetype=archetype,
            intelligence_mode=intelligence_mode,
        )

    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        return {
            "status": "error",
            "ast_valid": False,
            "permissions_valid": True,
            "message": f"AST syntax error on line {se.lineno}: {se.msg}",
        }

    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                return {
                    "status": "error",
                    "ast_valid": False,
                    "permissions_valid": True,
                    "message": f"AST security gate blocked forbidden call '{node.func.id}()'",
                }
            if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                return {
                    "status": "error",
                    "ast_valid": False,
                    "permissions_valid": True,
                    "message": "AST security gate blocked 'os.system()'",
                }

    # Simulate execution safely with an in-memory mock agent stub (zero DB writes)
    sample_text = (sample_input or "").strip()
    simulated_checks: List[str] = [
        f"AST verified ({len(code.splitlines())} lines, 0 unsafe calls)",
        f"Least-privilege ACL verified ({len(perms)} permissions: {', '.join(perms)})",
    ]
    sample_url = ""
    m_url = re.search(r"https?://[^\s]+", sample_text)
    if m_url and _is_safe_public_http_url(m_url.group(0)):
        sample_url = m_url.group(0)

    if sample_url and "network:outbound" in perms:
        t_http = time.perf_counter()
        try:
            req = urllib.request.Request(sample_url, method="GET", headers={"User-Agent": "AFCC-StudioDryRun/2.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:  # nosec B310
                ms = round((time.perf_counter() - t_http) * 1000, 1)
                simulated_checks.append(f"Live HTTP dry-run probe -> {sample_url} returned HTTP {resp.status} in {ms}ms")
        except Exception as exc:
            simulated_checks.append(f"Live HTTP dry-run probe -> {sample_url} raised: {exc}")
    elif archetype == "system_sentinel" and "system:diagnostics" in perms:
        usage = shutil.disk_usage(".")
        free_gb = round(usage.free / (1024 ** 3), 1)
        simulated_checks.append(f"Live system diagnostic check -> {free_gb} GB free workspace storage")
    elif sample_text:
        simulated_checks.append(f"Simulated '{routine_task}' capture & validation on sample input: '{sample_text[:80]}'")
    else:
        simulated_checks.append(f"Simulated '{routine_task}' ({archetype} / {intelligence_mode} mode) -> Ready for live SQLite records")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "status": "ok",
        "ast_valid": True,
        "permissions_valid": True,
        "agent_id": agent_id,
        "archetype": archetype,
        "intelligence_mode": intelligence_mode,
        "routine_task": routine_task,
        "duration_ms": elapsed_ms,
        "checks": simulated_checks,
        "summary": " | ".join(simulated_checks),
    }


def _infer_event_triggers_from_prompt(prompt: str) -> List[str]:
    """Infers inter-agent EventBus triggers from plain-English intent descriptions."""
    lower = (prompt or "").lower()
    triggers: List[str] = []
    if any(k in lower for k in ("email", "inbox", "gmail", "invoice", "receipt", "paper-trail", "paper trail", "billing notice")):
        triggers.append("gmail.paper_trail_detected")
    if any(k in lower for k in ("high ram", "memory spike", "ram exceeds", "85%", "memory threshold")):
        triggers.append("optimizer.ram_threshold_exceeded")
    if any(k in lower for k in ("after workout", "post-workout", "mudgal", "samtola", "gadha", "workout completed")):
        triggers.append("health.workout_completed")
    if any(k in lower for k in ("morning briefing", "executive briefing", "with my briefing")):
        triggers.append("overview.morning_briefing")
    if any(k in lower for k in ("when an alert", "on agent alert", "on any warning", "incident alert")):
        triggers.append("agent.alert")
    return triggers


def build_antigravity_deep_build_prompt(spec: Dict[str, Any]) -> str:
    """
    Phase 3 & Evolve Advisor: Generates a structured Antigravity Live engineering brief so a 1-click dispatch
    can author bespoke domain logic and unit tests directly in the custom agent's package.
    """
    ag_id = str(spec.get("id") or spec.get("agent_id") or "custom_agent").strip()
    name = str(spec.get("name") or ag_id).strip()
    icon = str(spec.get("icon") or "✨").strip()
    category = str(spec.get("category") or "Productivity").strip()
    archetype = str(spec.get("archetype") or "tracker").strip()
    intel = str(spec.get("intelligence_mode") or "hybrid").strip()
    desc = str(spec.get("description") or f"Custom Fleet agent: {name}").strip()
    raw_perms = spec.get("permissions")
    perms: List[str] = [str(p) for p in raw_perms if p] if isinstance(raw_perms, list) and raw_perms else ["db:read", "db:write", "ui:render"]
    raw_fields = spec.get("fields")
    fields: List[Dict[str, Any]] = [f for f in raw_fields if isinstance(f, dict)] if isinstance(raw_fields, list) else []
    raw_blocks = spec.get("ui_blocks")
    blocks: List[str] = [str(b) for b in raw_blocks if b] if isinstance(raw_blocks, list) else []
    raw_triggers = spec.get("event_triggers")
    triggers: List[str] = [str(t) for t in raw_triggers if t] if isinstance(raw_triggers, list) else []
    raw_actions = spec.get("outbound_actions")
    outbound_actions: List[str] = [str(a) for a in raw_actions if a] if isinstance(raw_actions, list) else []
    routine_task = str(spec.get("routine_task") or "run_check").strip()

    fields_summary = ", ".join(f"{f.get('key')} ({f.get('type')})" for f in fields) or "title (text)"
    triggers_summary = ", ".join(triggers) if triggers else "none (schedule/manual)"
    hooks_summary = f" | Outbound Hooks: `{', '.join(outbound_actions)}`" if outbound_actions else ""

    evo_lines: List[str] = []
    raw_evo = spec.get("evolution_improvements")
    if isinstance(raw_evo, list):
        for idx, item in enumerate(raw_evo, start=1):
            if isinstance(item, dict):
                imp_title = str(item.get("title") or "").strip()
                imp_brief = str(item.get("code_enhancement_brief") or item.get("description") or "").strip()
                if imp_title and imp_brief and imp_brief.lower() != imp_title.lower():
                    evo_lines.append(f"  {idx}. {imp_title}: {imp_brief}")
                elif imp_title:
                    evo_lines.append(f"  {idx}. {imp_title}")
            elif isinstance(item, str) and item.strip():
                evo_lines.append(f"  {idx}. {item.strip()}")

    evo_section = ""
    if evo_lines:
        evo_section = "- Requested Evolution Improvements & Custom Logic:\n" + "\n".join(evo_lines) + "\n"

    return (
        f"Deep-build custom business logic and unit tests for my Fleet custom agent '{icon} {name}' (ID: `{ag_id}`).\n"
        f"- Package Directory: `fleet/data/user/custom_agents/{ag_id}/` (`agent.py`, `manifest.json`, `ui/panel.html`)\n"
        f"- Category & Archetype: `{category}` / `{archetype}` (Intelligence Mode: `{intel}`)\n"
        f"- Operational Goal: {desc}\n"
        f"- Typed SQLite Fields: {fields_summary}\n"
        f"- UI Blocks: {', '.join(blocks)}\n"
        f"- Routine Task & Event Triggers: `{routine_task}` | Triggers: `{triggers_summary}`{hooks_summary}\n"
        f"- Allowed Sandbox Permissions: `{', '.join(perms)}` (maintain 100/100 on `python -X utf8 -m fleet.tools.security_scanner` and 0 Pyright/Pylance errors by checking `self.db is not None` and binding optional dicts to local variables before `.get()`)\n"
        f"{evo_section}"
        f"Please enhance `execute_task()` in `fleet/data/user/custom_agents/{ag_id}/agent.py` with rich domain-specific validation/analytics "
        f"and add unit tests in `tests/test_custom_{ag_id}.py`."
    )


_OUTBOUND_ACTION_LABELS: Dict[str, str] = {
    "auto_create_task": "Auto-Create Fleet Task",
    "desktop_toast": "Desktop Toast Alert",
    "markdown_report": "Markdown Audit Report",
    "emit_followup_event": "Downstream Squad Event",
}

_VALID_RECURRENCES = ("monthly", "quarterly", "semi_annual", "annual")
_VALID_CADENCES = ("every_30_min", "hourly", "daily_morning", "manual_only")
_STUDIO_EVOLVE_PERMISSIONS = (
    "ui:render",
    "db:read",
    "db:write",
    "event_bus:publish",
    "network:outbound",
    "system:diagnostics",
)


def _build_improvement_change_pills(patch: Dict[str, Any]) -> List[str]:
    """Generates human-readable capability pills describing what an evolution improvement changes."""
    pills: List[str] = []
    raw_blocks = patch.get("add_blocks")
    if isinstance(raw_blocks, list):
        for b in raw_blocks:
            b_str = str(b)
            if b_str in SUPPORTED_UI_BLOCKS:
                pills.append(f"+Widget: {SUPPORTED_UI_BLOCKS[b_str]['label']}")

    raw_field = patch.get("add_field")
    if isinstance(raw_field, dict) and raw_field.get("label"):
        f_type = str(raw_field.get("type") or "text")
        pills.append(f"+Field: {raw_field['label']} ({f_type})")

    raw_actions = patch.get("add_outbound_actions")
    if isinstance(raw_actions, list):
        for act in raw_actions:
            a_str = str(act)
            if a_str in _OUTBOUND_ACTION_LABELS:
                pills.append(f"+Hook: {_OUTBOUND_ACTION_LABELS[a_str]}")

    raw_triggers = patch.get("add_event_triggers")
    if isinstance(raw_triggers, list):
        for trig in raw_triggers:
            t_str = str(trig)
            if t_str in SUPPORTED_EVENT_TRIGGERS:
                pills.append(f"+Trigger: {t_str}")

    rec = str(patch.get("set_recurrence") or "").strip().lower()
    if rec in _VALID_RECURRENCES:
        pills.append(f"+Recurrence: {rec}")

    if patch.get("set_auto_ingest_inbox") is True:
        pills.append("+Inbox Drop-Folder Auto-Ingest")

    cadence = str(patch.get("set_schedule_cadence") or "").strip()
    if cadence in _VALID_CADENCES:
        pills.append(f"+Cadence: {cadence}")

    intel_mode = str(patch.get("set_intelligence_mode") or "").strip()
    if intel_mode in ("hybrid", "llm"):
        pills.append(f"+AI Mode: {intel_mode}")

    raw_perms = patch.get("add_permissions")
    if isinstance(raw_perms, list):
        for p in raw_perms:
            p_str = str(p)
            if p_str in _STUDIO_EVOLVE_PERMISSIONS:
                pills.append(f"+Perm: {p_str}")

    raw_chk = patch.get("add_checklist_items")
    if isinstance(raw_chk, list) and raw_chk:
        pills.append(f"+Checklist (+{len(raw_chk)})")

    if str(patch.get("system_prompt_directive") or "").strip():
        pills.append("+AI Prompt Rule")

    if not pills and str(patch.get("code_enhancement_brief") or "").strip():
        pills.append("+Deep-Build Logic")
    return pills


def _sanitize_improvement_patch(
    raw_patch: Dict[str, Any],
    existing_blocks: List[str],
    existing_actions: List[str],
    existing_triggers: List[str],
    existing_perms: List[str],
    existing_field_keys: List[str],
    existing_recurrence: str,
    existing_auto_ingest: bool,
    existing_cadence: str,
    existing_intel_mode: str,
) -> Dict[str, Any]:
    """Strips already-enabled capabilities and invalid enums from a candidate improvement patch."""
    clean: Dict[str, Any] = {}

    raw_add_blocks = raw_patch.get("add_blocks")
    if isinstance(raw_add_blocks, list):
        new_blocks: List[str] = []
        for b in raw_add_blocks:
            b_str = str(b).strip()
            if b_str in SUPPORTED_UI_BLOCKS and b_str not in existing_blocks and b_str not in new_blocks:
                new_blocks.append(b_str)
        if new_blocks:
            clean["add_blocks"] = new_blocks

    raw_add_actions = raw_patch.get("add_outbound_actions")
    if isinstance(raw_add_actions, list):
        new_actions: List[str] = []
        for a in raw_add_actions:
            a_str = str(a).strip()
            if a_str in _OUTBOUND_ACTION_LABELS and a_str not in existing_actions and a_str not in new_actions:
                new_actions.append(a_str)
        if new_actions:
            clean["add_outbound_actions"] = new_actions

    raw_add_triggers = raw_patch.get("add_event_triggers")
    if isinstance(raw_add_triggers, list):
        new_trigs: List[str] = []
        for t in raw_add_triggers:
            t_str = str(t).strip()
            if t_str in SUPPORTED_EVENT_TRIGGERS and t_str not in existing_triggers and t_str not in new_trigs:
                new_trigs.append(t_str)
        if new_trigs:
            clean["add_event_triggers"] = new_trigs

    perm_aliases = {
        "network:http": "network:outbound",
        "notifications:send": "event_bus:publish",
        "system:exec": "system:diagnostics",
    }
    raw_add_perms = raw_patch.get("add_permissions")
    new_perms: List[str] = []
    if isinstance(raw_add_perms, list):
        for p in raw_add_perms:
            p_str = perm_aliases.get(str(p).strip(), str(p).strip())
            if p_str in _STUDIO_EVOLVE_PERMISSIONS and p_str not in existing_perms and p_str not in new_perms:
                new_perms.append(p_str)
    # Automatically ensure event_bus:publish if desktop_toast or emit_followup_event is added
    added_acts = clean.get("add_outbound_actions")
    if isinstance(added_acts, list) and any(a in ("desktop_toast", "emit_followup_event") for a in added_acts):
        if "event_bus:publish" not in existing_perms and "event_bus:publish" not in new_perms:
            new_perms.append("event_bus:publish")
    if new_perms:
        clean["add_permissions"] = new_perms

    raw_field = raw_patch.get("add_field")
    if isinstance(raw_field, dict) and len(existing_field_keys) < 5:
        f_key = re.sub(r"[^a-z0-9_]+", "_", str(raw_field.get("key") or raw_field.get("label") or "").lower()).strip("_")[:28]
        f_label = str(raw_field.get("label") or f_key.replace("_", " ").title()).strip()[:36]
        f_type = str(raw_field.get("type") or "text").strip().lower()
        if f_type not in ("text", "number", "date", "url"):
            f_type = "text"
        f_ph = str(raw_field.get("placeholder") or f"Enter {f_label.lower()}...").strip()[:60]
        if f_key and f_label and f_key not in existing_field_keys:
            clean["add_field"] = {
                "key": f_key,
                "label": f_label,
                "type": f_type,
                "placeholder": f_ph,
            }

    rec = str(raw_patch.get("set_recurrence") or "").strip().lower()
    if rec in _VALID_RECURRENCES and rec != existing_recurrence:
        clean["set_recurrence"] = rec

    if raw_patch.get("set_auto_ingest_inbox") is True and not existing_auto_ingest:
        clean["set_auto_ingest_inbox"] = True

    cad = str(raw_patch.get("set_schedule_cadence") or "").strip()
    if cad in _VALID_CADENCES and cad != existing_cadence:
        clean["set_schedule_cadence"] = cad

    intel = str(raw_patch.get("set_intelligence_mode") or "").strip().lower()
    if intel in ("hybrid", "llm") and intel != existing_intel_mode:
        clean["set_intelligence_mode"] = intel

    raw_chk = raw_patch.get("add_checklist_items")
    if isinstance(raw_chk, list):
        chk_clean: List[Dict[str, str]] = []
        for idx, c in enumerate(raw_chk[:3]):
            if isinstance(c, dict):
                c_lbl = str(c.get("label") or "").strip()
            else:
                c_lbl = str(c or "").strip()
            if c_lbl:
                c_key = re.sub(r"[^a-z0-9_]+", "_", c_lbl.lower()).strip("_")[:28] or f"evo_step_{idx + 1}"
                chk_clean.append({"key": c_key, "label": c_lbl[:90]})
        if chk_clean:
            clean["add_checklist_items"] = chk_clean

    directive = str(raw_patch.get("system_prompt_directive") or "").strip()
    if directive:
        clean["system_prompt_directive"] = directive[:360]

    code_brief = str(raw_patch.get("code_enhancement_brief") or "").strip()
    if code_brief:
        clean["code_enhancement_brief"] = code_brief[:420]

    return clean


def parse_custom_improvement_to_patch(
    text: str,
    current_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts a user-authored free-text improvement request into a structured Studio improvement item
    with inferred declarative patches (widgets, hooks, fields, triggers, recurrence, cadence, permissions)
    plus an AI system prompt directive and Deep-Build code enhancement brief.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Custom improvement text cannot be empty.")

    manifest: Dict[str, Any] = current_manifest if isinstance(current_manifest, dict) else {}
    raw_eb = manifest.get("ui_blocks")
    existing_blocks: List[str] = [str(b) for b in raw_eb if b] if isinstance(raw_eb, list) else []
    raw_ea = manifest.get("outbound_actions")
    existing_actions: List[str] = [str(a) for a in raw_ea if a] if isinstance(raw_ea, list) else []
    raw_et = manifest.get("event_triggers")
    existing_triggers: List[str] = [str(t) for t in raw_et if t] if isinstance(raw_et, list) else []
    raw_ep = manifest.get("permissions")
    existing_perms: List[str] = [str(p) for p in raw_ep if p] if isinstance(raw_ep, list) else []
    raw_ef = manifest.get("fields")
    existing_field_keys: List[str] = [
        str(f.get("key") or "") for f in raw_ef if isinstance(f, dict) and f.get("key")
    ] if isinstance(raw_ef, list) else []
    existing_recurrence = str(manifest.get("default_recurrence") or "none").strip().lower()
    existing_auto_ingest = bool(manifest.get("auto_ingest_inbox", False))
    existing_cadence = str(manifest.get("schedule_cadence") or "").strip()
    existing_intel_mode = str(manifest.get("intelligence_mode") or "hybrid").strip()

    lower = clean_text.lower()
    draft_patch: Dict[str, Any] = {
        "system_prompt_directive": clean_text,
        "code_enhancement_brief": clean_text,
    }

    add_blocks: List[str] = []
    block_keywords = [
        ("sparkline_chart", ("sparkline", "chart", "trend", "graph", "plot")),
        ("kanban_board", ("kanban", "board", "columns", "pipeline")),
        ("document_vault", ("document vault", "upload pdf", "pdf upload", "document upload", "extract pdf", "vault")),
        ("agent_chat", ("chat", "q&a", "ask question", "conversational", "command chat")),
        ("countdown_cards", ("countdown", "expiry card", "renewal card", "days remaining")),
        ("habit_checklist", ("checklist", "habit", "streak", "daily steps")),
        ("status_timeline", ("timeline", "execution log", "audit trail", "activity feed")),
        ("ai_insight_card", ("ai briefing", "insight card", "executive summary", "ai card")),
        ("alert_banner", ("alert banner", "health banner", "top banner")),
        ("history_table", ("history table", "records table", "sqlite table")),
        ("kpi_row", ("kpi", "stat pills", "metric cards")),
    ]
    for blk_id, kws in block_keywords:
        if any(k in lower for k in kws):
            add_blocks.append(blk_id)
    if add_blocks:
        draft_patch["add_blocks"] = add_blocks

    add_actions: List[str] = []
    if any(k in lower for k in ("toast", "desktop alert", "desktop notification", "popup", "notify me")):
        add_actions.append("desktop_toast")
    if any(k in lower for k in ("markdown", "export report", "audit report", "digest file")):
        add_actions.append("markdown_report")
    if any(k in lower for k in ("create task", "auto-task", "auto task", "task queue", "todo")):
        add_actions.append("auto_create_task")
    if any(k in lower for k in ("squad", "downstream", "handoff", "follow-up event", "followup event")):
        add_actions.append("emit_followup_event")
    if add_actions:
        draft_patch["add_outbound_actions"] = add_actions

    inferred_triggers = _infer_event_triggers_from_prompt(clean_text)
    if inferred_triggers:
        draft_patch["add_event_triggers"] = inferred_triggers

    add_perms: List[str] = []
    if any(k in lower for k in ("http", "webhook", "api", "fetch url", "portal", "scrape", "endpoint")):
        add_perms.append("network:outbound")
    if any(k in lower for k in ("cpu", "ram", "disk", "process", "system diagnostic")):
        add_perms.append("system:diagnostics")
    if any(k in lower for k in ("eventbus", "publish event", "toast", "alert")):
        add_perms.append("event_bus:publish")
    if add_perms:
        draft_patch["add_permissions"] = add_perms

    if any(k in lower for k in ("annual recurrence", "auto-rollover annual", "yearly rollover", "annual renewal cycle", "renew annually")):
        draft_patch["set_recurrence"] = "annual"
    elif any(k in lower for k in ("semi-annual", "semi annual", "every 6 months")):
        draft_patch["set_recurrence"] = "semi_annual"
    elif any(k in lower for k in ("quarterly rollover", "quarterly recurrence", "every quarter")):
        draft_patch["set_recurrence"] = "quarterly"
    elif any(k in lower for k in ("monthly rollover", "monthly recurrence", "renew monthly")):
        draft_patch["set_recurrence"] = "monthly"

    if any(k in lower for k in ("inbox", "drop folder", "drop-folder", "watch folder", "auto-ingest", "auto ingest")):
        draft_patch["set_auto_ingest_inbox"] = True

    if any(k in lower for k in ("every 30 min", "30-minute", "30 minutes", "half hour")):
        draft_patch["set_schedule_cadence"] = "every_30_min"
    elif any(k in lower for k in ("every hour", "hourly check", "run hourly")):
        draft_patch["set_schedule_cadence"] = "hourly"
    elif any(k in lower for k in ("every morning", "daily morning")):
        draft_patch["set_schedule_cadence"] = "daily_morning"

    if existing_intel_mode == "deterministic" and any(k in lower for k in ("llm", "ai ", "summarize", "analyze", "compare")):
        draft_patch["set_intelligence_mode"] = "hybrid"

    # Optional field inference: e.g. "Add claim helpline field" or "Track sum insured column"
    field_match = re.search(
        r"(?:add|include|track|capture)\s+(?:a\s+|an\s+|new\s+)?([a-zA-Z0-9_ /&-]{2,28}?)\s+(?:field|column|input|attribute)\b",
        clean_text,
        flags=re.IGNORECASE,
    )
    if field_match and len(existing_field_keys) < 5:
        raw_lbl = re.sub(r"\s+", " ", field_match.group(1)).strip()
        f_key = re.sub(r"[^a-z0-9_]+", "_", raw_lbl.lower()).strip("_")[:26]
        f_type = "text"
        if any(w in f_key for w in ("amount", "value", "price", "cost", "sum", "idv", "pct", "percent", "score", "count", "km", "mileage")):
            f_type = "number"
        elif any(w in f_key for w in ("date", "expiry", "due", "renewal", "deadline")):
            f_type = "date"
        elif any(w in f_key for w in ("url", "link", "portal", "website")):
            f_type = "url"
        draft_patch["add_field"] = {
            "key": f_key,
            "label": raw_lbl.title()[:34],
            "type": f_type,
            "placeholder": f"Enter {raw_lbl.lower()}...",
        }

    sanitized_patch = _sanitize_improvement_patch(
        raw_patch=draft_patch,
        existing_blocks=existing_blocks,
        existing_actions=existing_actions,
        existing_triggers=existing_triggers,
        existing_perms=existing_perms,
        existing_field_keys=existing_field_keys,
        existing_recurrence=existing_recurrence,
        existing_auto_ingest=existing_auto_ingest,
        existing_cadence=existing_cadence,
        existing_intel_mode=existing_intel_mode,
    )
    if "system_prompt_directive" not in sanitized_patch:
        sanitized_patch["system_prompt_directive"] = clean_text[:360]
    if "code_enhancement_brief" not in sanitized_patch:
        sanitized_patch["code_enhancement_brief"] = clean_text[:420]

    short_title = clean_text if len(clean_text) <= 58 else (clean_text[:55].rstrip() + "...")
    slug = re.sub(r"[^a-z0-9_]+", "_", clean_text.lower()).strip("_")[:28] or "user_improvement"
    return {
        "id": f"custom_{slug}_{int(time.time() * 1000) % 100000}",
        "title": short_title,
        "description": f"Custom user-defined evolution requirement: {clean_text}",
        "category": "Custom Enhancement",
        "impact": "high",
        "icon": "➕",
        "recommended": True,
        "is_custom": True,
        "patch": sanitized_patch,
        "change_pills": _build_improvement_change_pills(sanitized_patch),
    }


def _detect_evolution_domain_flavor(agent_manifest: Dict[str, Any]) -> str:
    """Classifies an agent into a domain flavor so deterministic & hybrid suggestions feel bespoke."""
    blob = " ".join([
        str(agent_manifest.get("id") or ""),
        str(agent_manifest.get("name") or ""),
        str(agent_manifest.get("category") or ""),
        str(agent_manifest.get("description") or ""),
        str(agent_manifest.get("system_prompt") or ""),
    ]).lower()
    if any(k in blob for k in ("insurance", "policy", "acko", "vehicle", "car", "bike", "idv", "premium", "claim", "warranty")):
        return "insurance"
    if any(k in blob for k in ("invoice", "bill", "tax", "finance", "emi", "subscription", "expense", "fd", "bond", "investment")):
        return "finance"
    if any(k in blob for k in ("health", "lab", "biomarker", "workout", "mudgal", "medical", "prescription", "wellness", "glucose")):
        return "health"
    if any(k in blob for k in ("http", "uptime", "api", "git", "repo", "ci", "pr ", "deploy", "devops", "docker", "ram", "cpu")):
        return "devops"
    return "general"


def _build_deterministic_evolution_pool(
    agent_manifest: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Builds an ordered pool of 18+ domain-tailored candidate improvements covering missing UI blocks,
    outbound hooks, EventBus triggers, recurrence, inbox auto-ingest, typed fields, and AI analytical rules.
    Filtered later via `_sanitize_improvement_patch` so only genuinely new improvements are suggested.
    """
    flavor = _detect_evolution_domain_flavor(agent_manifest)
    name = str(agent_manifest.get("name") or "this agent")
    entries_cnt = int(runtime_summary.get("entries_count") or 0)
    docs_cnt = int(runtime_summary.get("documents_count") or 0)

    spark_titles = {
        "insurance": ("Premium & Coverage Trend Sparkline", "Visualize annual policy premiums and insured value trajectory across your tracked policies with an inline SVG sparkline."),
        "finance": ("Spend & Cash-Flow Trend Sparkline", "Plot recurring bill amounts, EMI totals, and payment history trends directly inside the agent dashboard."),
        "health": ("Biomarker & Conditioning Trend Sparkline", "Chart biomarker readings, recovery scores, and session metrics over time with a zero-dependency SVG trend line."),
        "devops": ("Latency & SLA Trend Sparkline", "Render real-time HTTP latency, error counts, and build health metrics on an inline SVG sparkline."),
        "general": ("Numeric Metric & Value Trend Sparkline", f"Plot historical numeric values across {name}'s SQLite records for instant visual anomaly detection."),
    }
    sp_title, sp_desc = spark_titles.get(flavor, spark_titles["general"])

    rec_by_flavor = {
        "insurance": ("annual", "Auto-Rollover Annual Policy Renewals", "Automatically advance completed policy expiry dates by 1 year so renewed car, bike, or health policies stay continuously tracked."),
        "finance": ("monthly", "Auto-Rollover Recurring Billing Cycles", "Automatically roll completed monthly bills, EMIs, and subscriptions forward to their next due date without manual re-entry."),
        "health": ("quarterly", "Quarterly Lab & Checkup Auto-Recurrence", "Automatically schedule the next quarterly biomarker screening or wellness checkup upon completing an item."),
        "devops": ("monthly", "Monthly Cert, Token & SLA Audit Rollover", "Automatically roll recurring certificate, API key rotation, and release audits forward each cycle."),
        "general": ("monthly", "Automated Due-Date Recurrence Rollover", "Automatically advance completed deadlines to the next recurring cycle so recurring obligations never drop off."),
    }
    rec_val, rec_title, rec_desc = rec_by_flavor.get(flavor, rec_by_flavor["general"])

    field_candidates_by_flavor: Dict[str, List[Dict[str, str]]] = {
        "insurance": [
            {"key": "sum_insured_idv", "label": "Sum Insured / IDV", "type": "number", "placeholder": "e.g. 650000"},
            {"key": "claim_helpline_url", "label": "Claim Portal / Helpline", "type": "text", "placeholder": "e.g. 1800-266-2256 / insurer URL"},
        ],
        "finance": [
            {"key": "payment_method", "label": "Account / Auto-Pay Mode", "type": "text", "placeholder": "e.g. HDFC Auto-Debit / UPI"},
            {"key": "tax_category", "label": "Tax / Budget Bucket", "type": "text", "placeholder": "e.g. 80C / Business Expense"},
        ],
        "health": [
            {"key": "reference_range", "label": "Target / Normal Range", "type": "text", "placeholder": "e.g. 70-99 mg/dL"},
            {"key": "provider_lab", "label": "Lab / Specialist", "type": "text", "placeholder": "e.g. Clinical Lab / Specialist"},
        ],
        "devops": [
            {"key": "endpoint_url", "label": "Service / PR URL", "type": "url", "placeholder": "https://api.example.com/health"},
            {"key": "sla_target_ms", "label": "SLA Threshold (ms)", "type": "number", "placeholder": "250"},
        ],
        "general": [
            {"key": "priority_tier", "label": "Priority / Owner", "type": "text", "placeholder": "e.g. P1 Critical / Personal"},
            {"key": "reference_url", "label": "Reference Link / ID", "type": "text", "placeholder": "https://... or REF-101"},
        ],
    }

    candidates: List[Dict[str, Any]] = [
        {
            "id": "add_desktop_toast_alerts",
            "title": "Proactive Desktop Toast Deadline & Breach Alerts",
            "description": f"Fire native Windows/OS desktop toast notifications whenever {name} detects overdue items or upcoming 15-day deadlines.",
            "category": "Automation & Hooks",
            "impact": "high",
            "icon": "🔔",
            "patch": {
                "add_outbound_actions": ["desktop_toast"],
                "add_permissions": ["event_bus:publish"],
                "system_prompt_directive": "Prioritize urgent desktop-alert summaries for items expiring within 15 days or breaching thresholds.",
            },
        },
        {
            "id": "add_sparkline_analytics",
            "title": sp_title,
            "description": sp_desc,
            "category": "UI & Analytics",
            "impact": "high",
            "icon": "📈",
            "patch": {
                "add_blocks": ["sparkline_chart"],
                "system_prompt_directive": "Highlight directional trends, spikes, and outliers across tracked numeric values.",
            },
        },
        {
            "id": "enable_smart_recurrence",
            "title": rec_title,
            "description": rec_desc,
            "category": "Automation & Hooks",
            "impact": "high",
            "icon": "🔁",
            "patch": {
                "set_recurrence": rec_val,
            },
        },
        {
            "id": "add_morning_briefing_sync",
            "title": "Sync Alerts into Daily Morning Executive Briefing",
            "description": f"Subscribe {name} to `overview.morning_briefing` so upcoming renewals and high-risk items appear automatically in your daily Fleet briefing.",
            "category": "EventBus & Schedule",
            "impact": "high",
            "icon": "🌅",
            "patch": {
                "add_event_triggers": ["overview.morning_briefing"],
            },
        },
        {
            "id": "add_document_vault_rag",
            "title": "Multi-Format Document Vault & AI Item Extractor",
            "description": "Upload PDFs, Word contracts, Excel/CSV schedules, emails, or image scans directly inside the agent to extract trackable items via AFCC's LLM.",
            "category": "Schema & Extraction",
            "impact": "high",
            "icon": "📄",
            "patch": {
                "add_blocks": ["document_vault"],
                "set_auto_ingest_inbox": True,
            },
        },
        {
            "id": "add_grounded_agent_chat",
            "title": "Grounded Vault & SQLite Q&A Command Chat",
            "description": f"Ask natural-language questions grounded on {name}'s {entries_cnt} tracked record(s) and {docs_cnt} vaulted document(s), or add/complete items via chat.",
            "category": "UI & Analytics",
            "impact": "high",
            "icon": "💬",
            "patch": {
                "add_blocks": ["agent_chat"],
            },
        },
        {
            "id": "add_auto_task_escalation",
            "title": "Auto-Escalate Due-Soon Items to Central Task Queue",
            "description": "Automatically create actionable to-do tasks in Fleet Overview whenever items enter the Due-Soon or Overdue window.",
            "category": "Automation & Hooks",
            "impact": "high",
            "icon": "✅",
            "patch": {
                "add_outbound_actions": ["auto_create_task"],
            },
        },
        {
            "id": "add_markdown_digest_export",
            "title": "Automated Markdown Audit & Digest Report Export",
            "description": f"Write a clean timestamped Markdown audit report to disk after every scheduled `{agent_manifest.get('routine_task') or 'run_check'}` execution.",
            "category": "Automation & Hooks",
            "impact": "medium",
            "icon": "📝",
            "patch": {
                "add_outbound_actions": ["markdown_report"],
            },
        },
        {
            "id": "add_email_paper_trail_trigger",
            "title": "Auto-Trigger on Incoming Policy & Billing Emails",
            "description": "Run automatically whenever Email Intelligence detects a new policy PDF, invoice, renewal notice, or receipt email (`gmail.paper_trail_detected`).",
            "category": "EventBus & Schedule",
            "impact": "high",
            "icon": "📬",
            "patch": {
                "add_event_triggers": ["gmail.paper_trail_detected"],
            },
        },
        {
            "id": "enable_inbox_drop_folder",
            "title": "Zero-Click Watched Drop-Folder Auto-Ingestion",
            "description": f"Watch `fleet/data/user/inbox/{agent_manifest.get('id') or 'agent'}/` and automatically extract & vault newly dropped files on every scheduled run.",
            "category": "Schema & Extraction",
            "impact": "medium",
            "icon": "📥",
            "patch": {
                "set_auto_ingest_inbox": True,
            },
        },
        {
            "id": "add_habit_audit_checklist",
            "title": "Interactive Verification & Renewal Readiness Checklist",
            "description": "Add a persistent checkable routine card with streak tracking so pre-renewal comparisons and compliance checks are never missed.",
            "category": "UI & Analytics",
            "impact": "medium",
            "icon": "☑️",
            "patch": {
                "add_blocks": ["habit_checklist"],
                "add_checklist_items": [
                    "Verify upcoming 30-day expiries & compare renewal quotes",
                    "Confirm vaulted source PDFs match active SQLite amounts & dates",
                ],
            },
        },
        {
            "id": "add_execution_status_timeline",
            "title": "Chronological Execution & Alert Audit Timeline",
            "description": "Display a live chronological feed of scheduled checks, document extractions, and EventBus triggers directly on the agent panel.",
            "category": "UI & Analytics",
            "impact": "medium",
            "icon": "⏱️",
            "patch": {
                "add_blocks": ["status_timeline"],
            },
        },
        {
            "id": "add_kanban_workflow_board",
            "title": "3-Stage Status Kanban Board (Safe / Due Soon / Done)",
            "description": "Organize all tracked records into interactive Active, Due Soon, and Completed columns with 1-click stage transitions.",
            "category": "UI & Analytics",
            "impact": "medium",
            "icon": "📋",
            "patch": {
                "add_blocks": ["kanban_board"],
            },
        },
        {
            "id": "add_countdown_urgency_cards",
            "title": "Live 15-Day Urgency & Renewal Countdown Cards",
            "description": "Surface color-coded countdown cards highlighting exact days remaining for every upcoming deadline or policy expiry.",
            "category": "UI & Analytics",
            "impact": "high",
            "icon": "⏳",
            "patch": {
                "add_blocks": ["countdown_cards"],
            },
        },
        {
            "id": "add_ai_executive_briefing_card",
            "title": "On-Demand AI Risk & Executive Insight Card",
            "description": "Add a dedicated AI Briefing card for 1-click executive synthesis across tracked SQLite items and vaulted documents.",
            "category": "Domain Intelligence",
            "impact": "high",
            "icon": "🧠",
            "patch": {
                "add_blocks": ["ai_insight_card"],
                "set_intelligence_mode": "hybrid",
            },
        },
        {
            "id": "add_squad_followup_hook",
            "title": "Emit Downstream Squad Handoff Events on Warnings",
            "description": "Publish structured follow-up events on the Fleet EventBus when warnings occur so companion agents can coordinate automatically.",
            "category": "Automation & Hooks",
            "impact": "medium",
            "icon": "🤝",
            "patch": {
                "add_outbound_actions": ["emit_followup_event"],
                "add_permissions": ["event_bus:publish"],
            },
        },
        {
            "id": "add_cross_agent_alert_correlation",
            "title": "Cross-Agent Incident & Warning Correlation Trigger",
            "description": "Subscribe to `agent.alert` so this sentinel cross-checks its portfolio whenever a related Fleet warning fires.",
            "category": "EventBus & Schedule",
            "impact": "medium",
            "icon": "🚨",
            "patch": {
                "add_event_triggers": ["agent.alert"],
            },
        },
    ]

    for f_idx, f_cand in enumerate(field_candidates_by_flavor.get(flavor, field_candidates_by_flavor["general"])):
        candidates.insert(4 + f_idx, {
            "id": f"add_field_{f_cand['key']}",
            "title": f"Capture '{f_cand['label']}' in Quick-Capture & Extraction",
            "description": f"Add a typed `{f_cand['key']}` ({f_cand['type']}) column so both manual quick-capture and LLM document extraction populate {f_cand['label']}.",
            "category": "Schema & Extraction",
            "impact": "high" if f_idx == 0 else "medium",
            "icon": "🗂️",
            "patch": {
                "add_field": dict(f_cand),
            },
        })

    # Always-available Domain Intelligence & Deep-Build upgrades (guaranteeing 10 items even on maxed-out UI manifests!)
    domain_intel_upgrades: Dict[str, List[Dict[str, Any]]] = {
        "insurance": [
            {
                "id": "intel_tiered_renewal_escalation",
                "title": "Tiered 45 / 30 / 15 / 7-Day Renewal Escalation Matrix",
                "description": "Upgrade AI & routine triage from a flat 15-day check to a 4-tier escalation playbook (45d quote comparison, 30d NCB audit, 15d renewal lock, 7d critical).",
                "category": "Domain Intelligence",
                "impact": "high",
                "icon": "🛡️",
                "patch": {
                    "system_prompt_directive": "Apply a 4-tier renewal escalation matrix: 45 days (compare insurer quotes), 30 days (verify No-Claim Bonus & IDV), 15 days (lock renewal), and <=7 days (CRITICAL lapse warning).",
                    "code_enhancement_brief": "Implement 45/30/15/7-day tiered renewal urgency classification and lapse-risk scoring in execute_task().",
                },
            },
            {
                "id": "intel_idv_ncb_coverage_gap_audit",
                "title": "Coverage Gap, IDV Depreciation & NCB Protection Audit",
                "description": "Instruct the connected LLM to flag policies with excessive IDV depreciation, missing zero-dep/roadside riders, or unprotected No-Claim Bonus.",
                "category": "Domain Intelligence",
                "impact": "high",
                "icon": "🔍",
                "patch": {
                    "system_prompt_directive": "Audit vaulted policy schedules for IDV depreciation >15%, No-Claim Bonus (NCB) tier accuracy, deductibles, and missing zero-depreciation or third-party coverage gaps.",
                    "code_enhancement_brief": "Add coverage-gap and premium-to-IDV ratio anomaly detection across tracked policies in execute_task().",
                },
            },
            {
                "id": "intel_yoy_premium_drift_detector",
                "title": "Year-over-Year Premium Hike & Duplicate Policy Detector",
                "description": "Detect abnormal premium increases (>12% YoY) and flag overlapping or duplicate vehicle/health coverage records across uploaded PDFs.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "📊",
                "patch": {
                    "system_prompt_directive": "Compare premiums across policies to flag >12% YoY hikes, duplicate policy/registration numbers, and multi-policy bundling savings opportunities.",
                    "code_enhancement_brief": "Add duplicate registration/policy-number detection and premium outlier flagging in execute_task().",
                },
            },
            {
                "id": "intel_claim_readiness_packet",
                "title": "Instant Claim-Readiness & Emergency Summary Protocol",
                "description": "Synthesize a 1-glance emergency claim cheat-sheet (insurer, policy #, expiry validity, exclusions, and cashless garage steps) during AI briefings.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🚑",
                "patch": {
                    "system_prompt_directive": "Include a concise Claim-Readiness Cheat Sheet (active policy number, validity status, key exclusions, and step-by-step claim filing checklist) in briefings.",
                    "code_enhancement_brief": "Generate structured claim-readiness summary metadata per active policy during routine checks.",
                },
            },
            {
                "id": "intel_insurer_portal_verification",
                "title": "Enable Outbound Insurer Portal & Webhook Verification",
                "description": "Grant `network:outbound` permission so custom Deep-Build routines can probe insurer renewal links or push webhook alerts.",
                "category": "EventBus & Schedule",
                "impact": "medium",
                "icon": "🌐",
                "patch": {
                    "add_permissions": ["network:outbound"],
                    "code_enhancement_brief": "Support optional HTTP health/link validation for policy renewal URLs when network:outbound is enabled.",
                },
            },
        ],
        "general": [
            {
                "id": "intel_tiered_sla_escalation",
                "title": "Tiered 30 / 14 / 7 / 2-Day Deadline Escalation Matrix",
                "description": "Upgrade deadline triage into a 4-stage urgency matrix with concrete next-step recommendations at each threshold.",
                "category": "Domain Intelligence",
                "impact": "high",
                "icon": "🎯",
                "patch": {
                    "system_prompt_directive": "Classify every dated record into a 30d / 14d / 7d / <=2d urgency matrix and recommend the single highest-leverage action first.",
                    "code_enhancement_brief": "Implement 30/14/7/2-day tiered urgency scoring and priority sorting in execute_task().",
                },
            },
            {
                "id": "intel_anomaly_outlier_audit",
                "title": "Statistical Outlier, Drift & Duplicate Record Detector",
                "description": "Automatically flag abnormal numeric spikes, missing target dates, and duplicate entries across SQLite records and vaulted files.",
                "category": "Domain Intelligence",
                "impact": "high",
                "icon": "🔍",
                "patch": {
                    "system_prompt_directive": "Detect numeric outliers (>2x median), records missing due dates, and potential duplicate entries across tracked items.",
                    "code_enhancement_brief": "Add median/outlier anomaly detection and duplicate-title warning checks in execute_task().",
                },
            },
            {
                "id": "intel_cross_doc_reconciliation",
                "title": "Vault-to-SQLite Cross-Document Reconciliation Rule",
                "description": "Cross-check vaulted attachment metadata against tracked SQLite rows to surface unlogged renewals, amounts, or discrepancies.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "📑",
                "patch": {
                    "system_prompt_directive": "Reconcile vaulted document metadata against active SQLite entries and highlight any unlogged dates, mismatched totals, or stale items.",
                    "code_enhancement_brief": "Cross-reference vaulted documents against active SQLite entries during routine runs.",
                },
            },
            {
                "id": "intel_weekly_executive_scorecard",
                "title": "Structured Health Score (0–100) & Risk Rubric",
                "description": "Compute a clear 0–100 portfolio health score factoring overdue ratio, upcoming load, and data completeness in every AI briefing.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🏆",
                "patch": {
                    "system_prompt_directive": "Begin every AI briefing with a 0-100 Portfolio Health Score based on overdue count, 15-day upcoming load, and field completeness.",
                    "code_enhancement_brief": "Compute a deterministic 0-100 health score KPI in execute_task() summary output.",
                },
            },
            {
                "id": "intel_outbound_webhook_readiness",
                "title": "Enable Outbound HTTP Endpoint & Link Verification",
                "description": "Grant `network:outbound` permission so custom routines can verify external URLs, APIs, or webhook endpoints.",
                "category": "EventBus & Schedule",
                "impact": "medium",
                "icon": "🌐",
                "patch": {
                    "add_permissions": ["network:outbound"],
                    "code_enhancement_brief": "Validate any URL fields via lightweight HTTP HEAD/GET checks when network:outbound is granted.",
                },
            },
            {
                "id": "intel_root_cause_action_plan",
                "title": "Next-Best-Action & Root-Cause Triage Recommendations",
                "description": "Pair every warning or overdue item with a concrete 1-step remediation instruction and estimated effort in AI summaries.",
                "category": "Domain Intelligence",
                "impact": "high",
                "icon": "🧭",
                "patch": {
                    "system_prompt_directive": "For every warning or overdue item, output a concrete 1-step Next-Best-Action and root-cause triage note.",
                    "code_enhancement_brief": "Attach structured next_action recommendations to warning items returned by execute_task().",
                },
            },
            {
                "id": "intel_quarter_over_quarter_forecast",
                "title": "90-Day Workload & Obligation Forecast Projection",
                "description": "Project upcoming 30 / 60 / 90-day renewal load and cumulative numeric exposure so busy clusters are spotted months ahead.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "📅",
                "patch": {
                    "system_prompt_directive": "Project 30-day, 60-day, and 90-day upcoming obligation counts and cumulative numeric exposure to highlight peak load windows.",
                    "code_enhancement_brief": "Compute 30/60/90-day horizon buckets and cumulative exposure totals in execute_task().",
                },
            },
            {
                "id": "intel_data_hygiene_completeness_guard",
                "title": "Automated Schema Completeness & Missing-Field Audit",
                "description": "Identify tracked entries with blank dates, zero amounts, or missing identifiers so your SQLite ledger stays 100% audit-ready.",
                "category": "Schema & Extraction",
                "impact": "medium",
                "icon": "🧹",
                "patch": {
                    "system_prompt_directive": "Flag any tracked records missing critical fields (dates, reference IDs, or amounts) in a concise Data Hygiene section.",
                    "code_enhancement_brief": "Scan SQLite entries for missing typed fields and report a data_completeness_pct metric in execute_task().",
                },
            },
            {
                "id": "intel_pareto_concentration_analysis",
                "title": "Top-20% Concentration & High-Exposure Risk Ranking",
                "description": "Rank tracked records by numeric impact (80/20 Pareto rule) so high-value policies, bills, or SLAs receive priority scrutiny.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "⚖️",
                "patch": {
                    "system_prompt_directive": "Apply an 80/20 Pareto concentration lens to highlight the top 20% highest-value or highest-impact tracked items.",
                    "code_enhancement_brief": "Rank records by numeric_value descending and compute top-20% concentration share in execute_task().",
                },
            },
            {
                "id": "intel_stale_record_archival_advisor",
                "title": "Stale Record & Dormant Item Archival Advisor",
                "description": "Surface items untouched for >90 days or past-completed milestones that are ready for clean archival or renewal review.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🗄️",
                "patch": {
                    "system_prompt_directive": "Identify dormant or stale records older than 90 days without updates and recommend archival or refresh.",
                    "code_enhancement_brief": "Detect records with stale updated_at timestamps (>90 days) during scheduled checks.",
                },
            },
            {
                "id": "intel_vendor_counterparty_grouping",
                "title": "Provider / Counterparty Grouping & Bundling Insights",
                "description": "Group tracked items by provider, vendor, or category to reveal consolidation opportunities and single-vendor concentration risk.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🏢",
                "patch": {
                    "system_prompt_directive": "Group active records by provider/vendor/source to highlight single-counterparty concentration and bundling opportunities.",
                    "code_enhancement_brief": "Aggregate record counts and numeric totals grouped by provider/category metadata in execute_task().",
                },
            },
            {
                "id": "intel_plain_english_delta_digest",
                "title": "Run-over-Run Change Delta Summary (What Changed Since Last Check)",
                "description": "Highlight newly added items, newly crossed 15-day thresholds, and resolved entries compared to the previous routine check.",
                "category": "Domain Intelligence",
                "impact": "medium",
                "icon": "🔄",
                "patch": {
                    "system_prompt_directive": "Lead status updates with a crisp 'What Changed' delta highlighting newly due-soon, newly added, and recently completed items.",
                    "code_enhancement_brief": "Compare current check counts against the last run record to emit a run-over-run delta summary.",
                },
            },
        ],
    }
    candidates.extend(domain_intel_upgrades.get(flavor, domain_intel_upgrades["general"]))
    if flavor != "general":
        candidates.extend(domain_intel_upgrades["general"])
    return candidates


_EVOLVE_SUGGESTIONS_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def generate_agent_evolution_suggestions(
    agent_manifest: Dict[str, Any],
    runtime_summary: Optional[Dict[str, Any]] = None,
    provider: str = "auto",
    model: Optional[str] = None,
    target_count: int = 10,
    force_llm: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Analyzes an existing custom agent's manifest, missing Studio capabilities, and non-PII SQLite
    runtime telemetry using AFCC's connected LLM (`HyperscalerGateway`), returning exact `target_count` (10)
    actionable, non-redundant evolution suggestions with structured patches ready for 1-click application.
    """
    desired_count = max(1, min(15, int(target_count or 10)))
    manifest: Dict[str, Any] = agent_manifest if isinstance(agent_manifest, dict) else {}
    rt_summary: Dict[str, Any] = runtime_summary if isinstance(runtime_summary, dict) else {}

    agent_id = str(manifest.get("id") or manifest.get("agent_id") or "custom_agent").strip()
    agent_name = str(manifest.get("name") or agent_id).strip()
    category = str(manifest.get("category") or "Productivity").strip()
    archetype = str(manifest.get("archetype") or "tracker").strip()
    description = str(manifest.get("description") or "").strip()
    system_prompt = str(manifest.get("system_prompt") or "").strip()

    raw_eb = manifest.get("ui_blocks")
    existing_blocks: List[str] = [str(b) for b in raw_eb if b] if isinstance(raw_eb, list) else []
    raw_ea = manifest.get("outbound_actions")
    existing_actions: List[str] = [str(a) for a in raw_ea if a] if isinstance(raw_ea, list) else []
    raw_et = manifest.get("event_triggers")
    existing_triggers: List[str] = [str(t) for t in raw_et if t] if isinstance(raw_et, list) else []
    raw_ep = manifest.get("permissions")
    existing_perms: List[str] = [str(p) for p in raw_ep if p] if isinstance(raw_ep, list) else ["db:read", "db:write", "ui:render"]
    raw_ef = manifest.get("fields")
    existing_fields: List[Dict[str, Any]] = [f for f in raw_ef if isinstance(f, dict)] if isinstance(raw_ef, list) else []
    existing_field_keys: List[str] = [str(f.get("key") or "") for f in existing_fields if f.get("key")]
    existing_recurrence = str(manifest.get("default_recurrence") or "none").strip().lower()
    existing_auto_ingest = bool(manifest.get("auto_ingest_inbox", False))
    existing_cadence = str(manifest.get("schedule_cadence") or "daily_morning").strip()
    existing_intel_mode = str(manifest.get("intelligence_mode") or "hybrid").strip()

    applied_titles_lower: set[str] = set()
    raw_prev_evo = manifest.get("evolution_improvements")
    if isinstance(raw_prev_evo, list):
        for prev in raw_prev_evo:
            if isinstance(prev, dict) and prev.get("title"):
                applied_titles_lower.add(str(prev["title"]).strip().lower())
            elif isinstance(prev, str) and prev.strip():
                applied_titles_lower.add(prev.strip().lower())

    missing_blocks = [b for b in SUPPORTED_UI_BLOCKS if b not in existing_blocks]
    missing_actions = [a for a in _OUTBOUND_ACTION_LABELS if a not in existing_actions]
    missing_triggers = [t for t in SUPPORTED_EVENT_TRIGGERS if t not in existing_triggers]
    missing_perms = [p for p in _STUDIO_EVOLVE_PERMISSIONS if p not in existing_perms]
    remaining_field_slots = max(0, 5 - len(existing_field_keys))

    from fleet.core.document_extractor import resolve_afcc_connected_llm
    conn_llm = resolve_afcc_connected_llm(provider=provider, model=model)
    req_provider = str(conn_llm.get("provider") or "deterministic")
    req_model = conn_llm.get("model")

    # Prefer low-latency flash-low tier when routing interactive Studio UI requests through Antigravity CLI
    raw_cfg_provs = conn_llm.get("configured_providers")
    cfg_provs: List[Dict[str, Any]] = [p for p in raw_cfg_provs if isinstance(p, dict)] if isinstance(raw_cfg_provs, list) else []
    uses_agy_cli = any(p.get("auth_method") == "antigravity_cli" for p in cfg_provs[:1])
    if not model and uses_agy_cli and str(req_model or "") in ("", "gemini-2.5-pro"):
        req_model = "gemini-3.8-flash-low"

    cache_key = json.dumps(
        {
            "id": agent_id,
            "b": sorted(existing_blocks),
            "a": sorted(existing_actions),
            "t": sorted(existing_triggers),
            "f": sorted(existing_field_keys),
            "r": existing_recurrence,
            "i": existing_auto_ingest,
            "e": sorted(list(applied_titles_lower)),
            "p": req_provider,
            "m": str(req_model or ""),
            "n": desired_count,
        },
        sort_keys=True,
    )
    if not force_refresh and os.environ.get("FLEET_TEST_MODE") != "1":
        cached_entry = _EVOLVE_SUGGESTIONS_CACHE.get(cache_key)
        if cached_entry and (time.time() - cached_entry[0]) < 300:
            return json.loads(json.dumps(cached_entry[1]))

    engine_used = "deterministic-$0.00"
    model_used = "tier0-evolution-architect"
    tokens_used = 0
    analysis_summary = ""
    final_suggestions: List[Dict[str, Any]] = []
    seen_titles: set[str] = set(applied_titles_lower)
    seen_ids: set[str] = set()

    # 1. Invoke AFCC's Connected LLM via HyperscalerGateway when available
    try:
        from fleet.core.hyperscalers import HyperscalerGateway
        gateway = HyperscalerGateway()
        in_test_mode = os.environ.get("FLEET_TEST_MODE") == "1"
        is_mocked_gateway = (
            hasattr(HyperscalerGateway, "assert_called")
            or hasattr(getattr(gateway, "complete", None), "assert_called")
            or type(gateway).__module__.startswith("unittest.mock")
        )
        should_invoke_llm = (req_provider != "deterministic") and (
            force_llm or (not in_test_mode) or is_mocked_gateway
        )

        if should_invoke_llm:
            sys_inst = (
                "You are the AFCC Agent Evolution Architect. Answer IMMEDIATELY in a single response using ONLY the JSON input below. "
                "DO NOT call any tools, DO NOT inspect files, and DO NOT run shell commands. "
                f"Propose EXACTLY {desired_count} distinct, high-impact improvements tailored to this Fleet agent. "
                "Output ONLY valid raw JSON (no markdown fences):\n"
                '{"analysis_summary":"1-sentence summary","suggestions":[{'
                '"id":"snake_id","title":"4-8 word title","description":"1-sentence value rationale",'
                '"category":"UI & Analytics | Automation & Hooks | Schema & Extraction | EventBus & Schedule | Domain Intelligence",'
                '"impact":"high | medium","icon":"emoji","recommended":true,'
                '"patch":{'
                f'"add_blocks":["subset of {missing_blocks}"],'
                f'"add_outbound_actions":["subset of {missing_actions}"],'
                f'"add_event_triggers":["subset of {missing_triggers}"],'
                f'"add_permissions":["subset of {missing_perms}"],'
                '"add_field":{"key":"snake_key","label":"Label","type":"text|number|date|url","placeholder":"..."},'
                '"set_recurrence":"monthly|quarterly|semi_annual|annual",'
                '"set_auto_ingest_inbox":true,'
                '"system_prompt_directive":"Concise domain rule for AI prompt",'
                '"code_enhancement_brief":"Concise Python execute_task() enhancement"'
                "}}]}\n"
                f"RULES: Return {desired_count} unique items; omit empty patch keys; never suggest already_enabled items; "
                f"only include add_field if remaining_field_slots ({remaining_field_slots}) > 0; mark top 3 recommended=true."
            )

            agent_context = {
                "id": agent_id,
                "name": agent_name,
                "category": category,
                "archetype": archetype,
                "intelligence_mode": existing_intel_mode,
                "description": description[:360],
                "already_enabled": {
                    "ui_blocks": existing_blocks,
                    "fields": [f.get("key") for f in existing_fields],
                    "outbound_actions": existing_actions,
                    "event_triggers": existing_triggers,
                    "permissions": existing_perms,
                    "default_recurrence": existing_recurrence,
                    "auto_ingest_inbox": existing_auto_ingest,
                    "previously_applied": sorted(list(applied_titles_lower))[:12],
                },
                "available_to_add": {
                    "missing_ui_blocks": missing_blocks,
                    "missing_outbound_actions": missing_actions,
                    "missing_event_triggers": missing_triggers,
                    "remaining_field_slots": remaining_field_slots,
                },
                "telemetry": {
                    "entries": int(rt_summary.get("entries_count") or 0),
                    "documents": int(rt_summary.get("documents_count") or 0),
                    "due_soon": int(rt_summary.get("due_soon_count") or 0),
                    "overdue": int(rt_summary.get("overdue_count") or 0),
                    "numeric_total": rt_summary.get("numeric_sum", 0),
                },
            }

            llm_prompt = (
                f"Agent Blueprint & Telemetry JSON:\n{json.dumps(agent_context, separators=(',', ':'), ensure_ascii=False)}\n"
                f"Output {desired_count} tailored evolution improvements as raw JSON now:"
            )
            resp = gateway.complete(
                prompt=llm_prompt,
                provider=None if req_provider == "auto" else req_provider,
                model=req_model,
                system_instruction=sys_inst,
                max_tokens=2200,
                allow_tier0=False,
                max_prompt_chars=18000,
            )

            if isinstance(resp, dict) and resp.get("status") not in ("FALLBACK", "ERROR", "error"):
                raw_txt = str(resp.get("text") or resp.get("response") or "").strip()
                if raw_txt:
                    cleaned = raw_txt
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
                    parsed_obj: Any = None
                    try:
                        parsed_obj = json.loads(cleaned)
                    except Exception:
                        brace_m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
                        if brace_m:
                            try:
                                parsed_obj = json.loads(brace_m.group(1))
                            except Exception:
                                parsed_obj = None

                    raw_list: List[Any] = []
                    if isinstance(parsed_obj, dict):
                        analysis_summary = str(parsed_obj.get("analysis_summary") or "").strip()
                        cand_sugs = parsed_obj.get("suggestions")
                        if isinstance(cand_sugs, list):
                            raw_list = cand_sugs
                    elif isinstance(parsed_obj, list):
                        raw_list = parsed_obj

                    for idx, item in enumerate(raw_list):
                        if not isinstance(item, dict):
                            continue
                        s_title = str(item.get("title") or "").strip()
                        if not s_title or s_title.lower() in seen_titles:
                            continue
                        raw_p = item.get("patch")
                        p_dict: Dict[str, Any] = raw_p if isinstance(raw_p, dict) else {}
                        clean_p = _sanitize_improvement_patch(
                            raw_patch=p_dict,
                            existing_blocks=existing_blocks,
                            existing_actions=existing_actions,
                            existing_triggers=existing_triggers,
                            existing_perms=existing_perms,
                            existing_field_keys=existing_field_keys,
                            existing_recurrence=existing_recurrence,
                            existing_auto_ingest=existing_auto_ingest,
                            existing_cadence=existing_cadence,
                            existing_intel_mode=existing_intel_mode,
                        )
                        if not clean_p:
                            # Ensure valid LLM analytical suggestions still apply as an AI prompt/code directive
                            s_desc_fallback = str(item.get("description") or s_title).strip()
                            clean_p = {
                                "system_prompt_directive": f"{s_title}: {s_desc_fallback}"[:360],
                                "code_enhancement_brief": f"{s_title}: {s_desc_fallback}"[:420],
                            }
                        base_sid = re.sub(r"[^a-z0-9_]+", "_", str(item.get("id") or s_title).lower()).strip("_")[:32] or f"llm_imp_{idx + 1}"
                        sid = base_sid
                        s_seq = 2
                        while sid in seen_ids:
                            sid = f"{base_sid}_{s_seq}"
                            s_seq += 1

                        seen_titles.add(s_title.lower())
                        seen_ids.add(sid)
                        s_impact = str(item.get("impact") or "high").strip().lower()
                        if s_impact not in ("high", "medium", "low"):
                            s_impact = "high"
                        final_suggestions.append({
                            "id": sid,
                            "title": s_title[:80],
                            "description": str(item.get("description") or f"Enhance {agent_name} with {s_title}.")[:260],
                            "category": str(item.get("category") or "Domain Intelligence")[:40],
                            "impact": s_impact,
                            "icon": str(item.get("icon") or "✨").strip()[:4] or "✨",
                            "recommended": bool(item.get("recommended", False)),
                            "is_custom": False,
                            "source": "llm",
                            "patch": clean_p,
                            "change_pills": _build_improvement_change_pills(clean_p),
                        })
                        if len(final_suggestions) >= desired_count:
                            break

                    if final_suggestions:
                        engine_used = str(resp.get("provider") or req_provider or "connected-llm")
                        model_used = str(resp.get("model") or req_model or "connected-llm")
                        tokens_used = int(resp.get("tokens") or resp.get("total_tokens") or 0)
    except Exception as exc:
        logger.debug("Evolution LLM suggestion generation fell back to deterministic architect: %s", exc)

    # 2. Top up (or provide instant $0.00 deterministic 10 suggestions) from Gap-Aware Deterministic Pool
    llm_generated_count = len(final_suggestions)
    if len(final_suggestions) < desired_count:
        det_pool = _build_deterministic_evolution_pool(manifest, rt_summary)
        for cand in det_pool:
            if len(final_suggestions) >= desired_count:
                break
            c_title = str(cand.get("title") or "").strip()
            if not c_title or c_title.lower() in seen_titles:
                continue
            raw_cp = cand.get("patch")
            cp_dict: Dict[str, Any] = raw_cp if isinstance(raw_cp, dict) else {}
            clean_cp = _sanitize_improvement_patch(
                raw_patch=cp_dict,
                existing_blocks=existing_blocks,
                existing_actions=existing_actions,
                existing_triggers=existing_triggers,
                existing_perms=existing_perms,
                existing_field_keys=existing_field_keys,
                existing_recurrence=existing_recurrence,
                existing_auto_ingest=existing_auto_ingest,
                existing_cadence=existing_cadence,
                existing_intel_mode=existing_intel_mode,
            )
            if not clean_cp:
                continue

            base_cid = str(cand.get("id") or re.sub(r"[^a-z0-9_]+", "_", c_title.lower()).strip("_"))[:32] or "det_imp"
            cid = base_cid
            c_seq = 2
            while cid in seen_ids:
                cid = f"{base_cid}_{c_seq}"
                c_seq += 1

            seen_titles.add(c_title.lower())
            seen_ids.add(cid)
            final_suggestions.append({
                "id": cid,
                "title": c_title,
                "description": str(cand.get("description") or ""),
                "category": str(cand.get("category") or "Studio Upgrade"),
                "impact": str(cand.get("impact") or "medium"),
                "icon": str(cand.get("icon") or "✨"),
                "recommended": False,
                "is_custom": False,
                "source": "deterministic",
                "patch": clean_cp,
                "change_pills": _build_improvement_change_pills(clean_cp),
            })

    # Ensure sensible default recommended flags (top 3 pre-recommended if none marked)
    if final_suggestions and not any(bool(s.get("recommended")) for s in final_suggestions):
        for s in final_suggestions[: min(3, len(final_suggestions))]:
            s["recommended"] = True

    if 0 < llm_generated_count < len(final_suggestions):
        engine_used = f"{engine_used}+gap-architect"

    if not analysis_summary:
        entries_cnt = int(rt_summary.get("entries_count") or 0)
        docs_cnt = int(rt_summary.get("documents_count") or 0)
        analysis_summary = (
            f"Analyzed '{agent_name}' ({len(existing_blocks)}/12 widgets, {len(existing_field_keys)}/5 fields, "
            f"{entries_cnt} SQLite record(s), {docs_cnt} vaulted document(s)) and synthesized "
            f"{len(final_suggestions)} tailored upgrades."
        )

    result_payload: Dict[str, Any] = {
        "status": "ok",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "count": len(final_suggestions),
        "llm_generated_count": llm_generated_count,
        "engine_used": engine_used,
        "model_used": model_used,
        "tokens_used": tokens_used,
        "connected_llm": conn_llm,
        "analysis_summary": analysis_summary,
        "suggestions": final_suggestions[:desired_count],
    }
    if os.environ.get("FLEET_TEST_MODE") != "1":
        if len(_EVOLVE_SUGGESTIONS_CACHE) > 40:
            _EVOLVE_SUGGESTIONS_CACHE.clear()
        _EVOLVE_SUGGESTIONS_CACHE[cache_key] = (time.time(), json.loads(json.dumps(result_payload)))
    return result_payload


def _synthesize_with_llm(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Synthesizes an enriched agent specification using HyperscalerGateway / Antigravity LLM.
    Falls back cleanly to None if offline or unavailable.
    """
    try:
        from fleet.core.hyperscalers import HyperscalerGateway
        gateway = HyperscalerGateway()

        system_instruction = (
            "You are the Fleet Agent Studio AI Architect. Analyze the user's natural-language request "
            "and output ONLY a valid raw JSON object (no markdown fences) for a sandboxed Fleet agent:\n"
            "{\n"
            '  "name": "Short Agent Name (3-5 words max)",\n'
            '  "agent_id": "snake_case_id",\n'
            '  "icon": "Single representative emoji",\n'
            '  "category": "One of: Productivity, Monitoring, DevOps, Knowledge, Health, System, Finance",\n'
            '  "archetype": "One of: tracker, http_watcher, llm_analyst, system_sentinel",\n'
            '  "intelligence_mode": "One of: hybrid, deterministic, llm",\n'
            '  "description": "Clear 1-2 sentence description of what the agent automates or tracks",\n'
            '  "preset": "One of: observer, notifier, analyst, autonomous",\n'
            '  "permissions": ["subset of: db:read, db:write, ui:render, event_bus:publish, network:outbound, system:diagnostics"],\n'
            '  "schedule_cadence": "One of: every_30_min, hourly, daily_morning, manual_only",\n'
            '  "sync_interval": 60,\n'
            '  "enable_alerts": true,\n'
            '  "routine_task": "valid_snake_case_task_name",\n'
            '  "system_prompt": "Tailored system prompt for this agent",\n'
            '  "ui_blocks": ["subset of: alert_banner, kpi_row, document_vault, quick_capture_bar, countdown_cards, kanban_board, sparkline_chart, ai_insight_card, agent_chat, history_table, habit_checklist, status_timeline"],\n'
            '  "event_triggers": ["optional subset of: gmail.paper_trail_detected, optimizer.ram_threshold_exceeded, health.workout_completed, overview.morning_briefing, agent.alert"],\n'
            '  "fields": [{"key": "title", "label": "Item Name", "type": "text|number|date|url", "placeholder": "..."}],\n'
            '  "checklist_items": ["Actionable daily step 1", "Actionable daily step 2"]\n'
            "}"
        )

        user_content = f'Create a Fleet agent for this purpose:\n"{prompt}"'
        resp = gateway.complete(
            prompt=f"{system_instruction}\n\nUser Request: {user_content}\nJSON Output:",
            model="gemini-3.8-flash-low",
            system_instruction=system_instruction,
            allow_tier0=False,
        )

        if not isinstance(resp, dict) or resp.get("status") == "FALLBACK":
            return None

        raw = str(resp.get("text") or resp.get("response") or "").strip()
        if not raw:
            return None

        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

        data = json.loads(raw)
        if isinstance(data, dict) and data.get("name") and data.get("agent_id"):
            return data
    except Exception as exc:
        logger.debug("LLM agent synthesis skipped or encountered error (using deterministic fallback): %s", exc)
    return None


def synthesize_agent_from_prompt(
    prompt: str,
    custom_id: Optional[str] = None,
    requested_blocks: Optional[List[str]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    Synthesizes a complete, sandbox-compliant, functional Fleet agent specification from plain English.
    Uses Antigravity/Hyperscaler LLM synthesis when available, with an instant deterministic fallback.
    """
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Prompt description is required to synthesize an agent.")

    lower = clean_prompt.lower()

    best_rule: Optional[Dict[str, Any]] = None
    best_score = 0
    for rule in _DOMAIN_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in lower)
        if score > best_score:
            best_score = score
            best_rule = rule

    if not best_rule:
        best_rule = {
            "category": "Productivity",
            "icon": "✨",
            "archetype": "tracker",
            "intelligence_mode": "hybrid",
            "default_name": "Custom Workflow Sentinel",
            "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
            "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "ai_insight_card", "history_table"],
            "routine_task": "run_scheduled_check",
            "fields": [
                {"key": "title", "label": "Item / Action", "type": "text", "placeholder": "Enter item, milestone, or note..."},
                {"key": "due_date", "label": "Target Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                {"key": "numeric_value", "label": "Value / Metric", "type": "number", "placeholder": "0"},
            ],
            "checklist_items": [
                {"key": "review_items", "label": "Review active tracked items and deadlines"},
                {"key": "run_routine", "label": "Verify daily routine check output"},
            ],
        }

    llm_spec = _synthesize_with_llm(clean_prompt) if use_llm else None

    perms = list(best_rule["permissions"])
    for core_p in ("db:read", "db:write", "ui:render"):
        if core_p not in perms:
            perms.insert(0, core_p)
    if any(w in lower for w in ("http", "url", "webhook", "api", "fetch", "weather", "stock", "crypto", "web", "website")):
        if "network:outbound" not in perms:
            perms.append("network:outbound")
    if any(w in lower for w in ("cpu", "ram", "memory", "process", "disk", "git", "bash", "command", "system", "folder")):
        if "system:diagnostics" not in perms:
            perms.append("system:diagnostics")
    perms = [p for p in perms if p in ALLOWED_AGENT_PERMISSIONS]

    name, agent_id = _derive_name_and_id(clean_prompt, best_rule["default_name"], custom_id=custom_id)
    schedule_info = _extract_schedule_from_prompt(clean_prompt)
    routine_task = str(best_rule["routine_task"])
    icon = str(best_rule["icon"])
    category = str(best_rule["category"])
    archetype = str(best_rule.get("archetype", "tracker"))
    intelligence_mode = str(best_rule.get("intelligence_mode", "hybrid"))
    model = "gemini-3.8-flash-low"
    fields = _normalize_fields(best_rule.get("fields"))
    checklist_items = _normalize_checklist_items(best_rule.get("checklist_items"), name, routine_task)

    if any(w in lower for w in ("summarize", "analyze", "briefing", "llm", "ai ", "research", "synthesize")):
        if intelligence_mode == "deterministic":
            intelligence_mode = "hybrid"

    schedule_cadence = "hourly"
    if "minute" in lower or "min" in lower or "30" in lower:
        schedule_cadence = "every_30_min"
    elif "morning" in lower or "daily" in lower or "8" in lower or "9" in lower or "day" in lower or "evening" in lower:
        schedule_cadence = "daily_morning"
    elif "manual" in lower or "ad-hoc" in lower or "on-demand" in lower:
        schedule_cadence = "manual_only"

    preset = "analyst"
    if "system:diagnostics" in perms:
        preset = "autonomous"
    elif "network:outbound" in perms:
        preset = "observer"
    elif "event_bus:publish" in perms:
        preset = "notifier"

    sync_interval = 60
    enable_alerts = True
    system_prompt = (
        f"You are {name}, a specialized autonomous Fleet agent dedicated to: {clean_prompt}. "
        f"Analyze tracked SQLite records, highlight upcoming deadlines or threshold breaches, "
        f"and deliver concise, actionable recommendations."
    )

    ui_blocks = [b for b in (requested_blocks or best_rule["ui_blocks"]) if b in SUPPORTED_UI_BLOCKS]
    if not ui_blocks:
        ui_blocks = ["kpi_row", "quick_capture_bar", "history_table"]
    if not requested_blocks and any(
        w in lower for w in ("chart", "trend", "sparkline", "graph", "latency", "price", "glucose", "metric")
    ):
        if "sparkline_chart" not in ui_blocks:
            ui_blocks.append("sparkline_chart")
    if not requested_blocks and any(
        w in lower for w in ("kanban", "board", "pipeline", "stages", "columns")
    ):
        if "kanban_board" not in ui_blocks:
            ui_blocks.append("kanban_board")
    if not requested_blocks and any(
        w in lower
        for w in (
            "document", "upload", "pdf", "docx", "policy", "contract", "lease", "invoice",
            "receipt", "bill", "lab report", "prescription", "syllabus", "warranty",
            "itinerary", "passport", "visa", "extract", "statement", "certificate",
        )
    ):
        if "document_vault" not in ui_blocks:
            insert_idx = 2 if len(ui_blocks) >= 2 else len(ui_blocks)
            ui_blocks.insert(insert_idx, "document_vault")
    if not requested_blocks and (
        "document_vault" in ui_blocks
        or any(w in lower for w in ("chat", "ask", "q&a", "question", "command", "query", "assistant"))
    ):
        if "agent_chat" not in ui_blocks:
            ui_blocks.append("agent_chat")

    event_triggers = _infer_event_triggers_from_prompt(clean_prompt)

    outbound_actions: List[str] = []
    if any(w in lower for w in ("auto-task", "create task", "todo", "action item", "task queue", "policy", "renewal", "warranty", "overdue")):
        outbound_actions.append("auto_create_task")
    if any(w in lower for w in ("toast", "desktop alert", "notify me", "notification")):
        outbound_actions.append("desktop_toast")
    if any(w in lower for w in ("markdown report", "digest report", "export report", "daily report")):
        outbound_actions.append("markdown_report")
    if any(w in lower for w in ("squad", "downstream", "follow-up event", "handoff")):
        outbound_actions.append("emit_followup_event")

    auto_ingest_inbox = ("document_vault" in ui_blocks) or any(
        w in lower for w in ("inbox", "drop folder", "watch folder", "auto-ingest", "auto ingest")
    )

    default_recurrence = "none"
    if any(w in lower for w in ("annual", "yearly", "insurance", "policy", "passport", "license", "domain", "ssl")):
        default_recurrence = "annual"
    elif any(w in lower for w in ("quarterly", "quarter", "biomarker", "lab report", "hba1c")):
        default_recurrence = "quarterly"
    elif any(w in lower for w in ("monthly", "rent", "subscription", "bill", "emi", "utility")):
        default_recurrence = "monthly"

    # Overlay with LLM synthesis when available
    if llm_spec:
        if llm_spec.get("name") and not custom_id:
            name = str(llm_spec["name"])
        if llm_spec.get("agent_id") and not custom_id:
            raw_id = re.sub(r"[^a-z0-9_]+", "_", str(llm_spec["agent_id"]).lower()).strip("_")
            if raw_id:
                agent_id = raw_id[:30].rstrip("_")
        if llm_spec.get("icon"):
            icon = str(llm_spec["icon"])
        if llm_spec.get("category"):
            category = str(llm_spec["category"])
        if llm_spec.get("archetype") in ("tracker", "http_watcher", "llm_analyst", "system_sentinel"):
            archetype = str(llm_spec["archetype"])
        if llm_spec.get("intelligence_mode") in ("hybrid", "deterministic", "llm"):
            intelligence_mode = str(llm_spec["intelligence_mode"])
        if llm_spec.get("routine_task"):
            r_task = re.sub(r"[^a-z0-9_]+", "_", str(llm_spec["routine_task"]).lower()).strip("_")
            if r_task:
                routine_task = r_task
        if llm_spec.get("schedule_cadence") in ("every_30_min", "hourly", "daily_morning", "manual_only"):
            schedule_cadence = str(llm_spec["schedule_cadence"])
        if llm_spec.get("preset") in ("observer", "notifier", "analyst", "autonomous"):
            preset = str(llm_spec["preset"])
        if isinstance(llm_spec.get("sync_interval"), (int, float)):
            sync_interval = max(5, min(86400, int(llm_spec["sync_interval"])))
        if "enable_alerts" in llm_spec:
            enable_alerts = bool(llm_spec["enable_alerts"])
        if llm_spec.get("system_prompt"):
            system_prompt = str(llm_spec["system_prompt"])
        if isinstance(llm_spec.get("permissions"), list):
            perm_aliases = {
                "network:http": "network:outbound",
                "notifications:send": "event_bus:publish",
                "system:exec": "system:diagnostics",
            }
            mapped = [perm_aliases.get(str(p), str(p)) for p in llm_spec["permissions"]]
            valid_p = [p for p in mapped if p in ALLOWED_AGENT_PERMISSIONS]
            for core_p in ("db:read", "db:write", "ui:render"):
                if core_p not in valid_p:
                    valid_p.insert(0, core_p)
            perms = valid_p
        if isinstance(llm_spec.get("ui_blocks"), list) and not requested_blocks:
            valid_b = [b for b in llm_spec["ui_blocks"] if b in SUPPORTED_UI_BLOCKS]
            if valid_b:
                ui_blocks = valid_b
        if isinstance(llm_spec.get("fields"), list) and llm_spec["fields"]:
            fields = _normalize_fields(llm_spec["fields"])
        if isinstance(llm_spec.get("checklist_items"), list) and llm_spec["checklist_items"]:
            checklist_items = _normalize_checklist_items(llm_spec["checklist_items"], name, routine_task)
        if isinstance(llm_spec.get("event_triggers"), list):
            for trig in llm_spec["event_triggers"]:
                t_str = str(trig).strip()
                if t_str in SUPPORTED_EVENT_TRIGGERS and t_str not in event_triggers:
                    event_triggers.append(t_str)

    settings_schema = [
        {
            "id": "enabled_notifications",
            "label": "Enable Desktop Alerts",
            "type": "boolean",
            "default": enable_alerts,
            "description": f"Send desktop notification when {name} detects warnings in {routine_task}.",
        },
        {
            "id": "target_threshold",
            "label": "Alert Threshold / Target",
            "type": "number",
            "default": 85,
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
        "version": "2.0.0",
        "icon": icon,
        "category": category,
        "archetype": archetype,
        "intelligence_mode": intelligence_mode,
        "model": model,
        "system_prompt": system_prompt,
        "description": clean_prompt,
        "permissions": perms,
        "ui_blocks": ui_blocks,
        "fields": fields,
        "checklist_items": checklist_items,
        "event_triggers": event_triggers,
        "outbound_actions": outbound_actions,
        "auto_ingest_inbox": auto_ingest_inbox,
        "default_recurrence": default_recurrence,
        "routine_task": routine_task,
        "schedule_cadence": schedule_cadence,
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
        fields=fields,
        checklist_items=checklist_items,
        intelligence_mode=intelligence_mode,
    )

    agent_py = generate_custom_agent_code(
        agent_id=agent_id,
        name=name,
        icon=icon,
        description=clean_prompt,
        routine_task=routine_task,
        initial_order=75,
        archetype=archetype,
        intelligence_mode=intelligence_mode,
        settings_schema=settings_schema,
    )

    clarifying_chips = _build_clarifying_chips(ui_blocks=ui_blocks, permissions=perms, fields=fields)

    return {
        "status": "ok",
        "agent_id": agent_id,
        "name": name,
        "icon": icon,
        "category": category,
        "archetype": archetype,
        "intelligence_mode": intelligence_mode,
        "model": model,
        "description": clean_prompt,
        "permissions": perms,
        "preset": preset,
        "schedule_cadence": schedule_cadence,
        "sync_interval": sync_interval,
        "enable_alerts": enable_alerts,
        "system_prompt": system_prompt,
        "ui_blocks": ui_blocks,
        "fields": fields,
        "checklist_items": checklist_items,
        "event_triggers": event_triggers,
        "outbound_actions": outbound_actions,
        "auto_ingest_inbox": auto_ingest_inbox,
        "default_recurrence": default_recurrence,
        "clarifying_chips": clarifying_chips,
        "routine_task": routine_task,
        "schedule": schedule_info,
        "settings_schema": settings_schema,
        "manifest": manifest,
        "panel_html": panel_html,
        "agent_py": agent_py,
        "supported_ui_blocks": list(SUPPORTED_UI_BLOCKS.values()),
        "supported_event_triggers": get_supported_event_triggers(),
        "synthesized_via": "llm" if llm_spec else "deterministic",
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
