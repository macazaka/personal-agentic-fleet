import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fleet.config import TIMEZONE_NAME
from fleet.core.database import FleetDatabase

_BRIEFING_CACHE: Dict[str, Dict[str, Any]] = {}
_BRIEFING_CACHE_TTL_SEC = 10.0
_MEETINGS_PREP_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_MEETINGS_PREP_TTL_SEC = 60.0
_BRIEFING_CACHE_LOCK = threading.Lock()
_BRIEFING_CACHE_STATS: Dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "meetings_hits": 0,
    "invalidations": 0,
}


def invalidate_briefing_cache() -> None:
    """Write-through invalidation for cached daily briefings after task/routine/health/email updates."""
    with _BRIEFING_CACHE_LOCK:
        _BRIEFING_CACHE.clear()
        _MEETINGS_PREP_CACHE["ts"] = 0.0
        _MEETINGS_PREP_CACHE["data"] = None
        _BRIEFING_CACHE_STATS["invalidations"] += 1


def get_briefing_cache_stats() -> Dict[str, Any]:
    """Returns briefing cache hit/miss telemetry."""
    with _BRIEFING_CACHE_LOCK:
        return {
            "entries": len(_BRIEFING_CACHE),
            "hits": _BRIEFING_CACHE_STATS["hits"],
            "misses": _BRIEFING_CACHE_STATS["misses"],
            "meetings_hits": _BRIEFING_CACHE_STATS["meetings_hits"],
            "invalidations": _BRIEFING_CACHE_STATS["invalidations"],
        }


def extract_meeting_agenda(subject: str, snippet: str = "", sender: str = "") -> Dict[str, Any]:
    """
    Parses an incoming meeting email/invite and generates an automated agenda preparation note.
    Tier 0: Pure deterministic heuristic (0 tokens).
    """
    clean_title = re.sub(r"^(?:Invitation:\s*|Updated invitation:\s*|New Event:\s*|Event:\s*)", "", subject, flags=re.I).strip()
    
    time_match = re.search(r"@\s*([A-Za-z]+ \d{1,2}(?:, \d{4})?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", subject, flags=re.I)
    meeting_time = time_match.group(1) if time_match else "Scheduled Today"

    text_combined = f"{subject} {snippet}".lower()
    if "google meet" in text_combined:
        platform = "Google Meet"
    elif "zoom" in text_combined:
        platform = "Zoom"
    elif "microsoft teams" in text_combined or "teams meeting" in text_combined:
        platform = "Microsoft Teams"
    elif "calendly" in text_combined:
        platform = "Calendly"
    else:
        platform = "Calendar Sync"

    prep_items = []
    if any(k in clean_title.lower() for k in ["roadmap", "product", "sprint", "planning", "sync"]):
        prep_items.append("Review active roadmap milestones, pending PRs, and top P1 goals.")
        prep_items.append("Check blockers or dependencies with the team.")
    elif any(k in clean_title.lower() for k in ["client", "proposal", "pitch", "sales"]):
        prep_items.append("Review revised proposal draft, pricing terms, and client requirements.")
        prep_items.append("Prepare clear next steps and timeline commitments.")
    elif any(k in clean_title.lower() for k in ["intro", "interview", "call with", "1:1", "one-on-one"]):
        prep_items.append("Review background profile / notes before the call.")
        prep_items.append("Outline 2-3 key discussion topics and desired outcomes.")
    else:
        prep_items.append("Review relevant task deliverables and recent activity logs.")
        prep_items.append("Verify meeting link and agenda attachments.")

    return {
        "title": clean_title,
        "time": meeting_time,
        "platform": platform,
        "sender": sender,
        "prep_notes": prep_items,
        "agenda_summary": f"{clean_title} via {platform} ({meeting_time})"
    }


class BriefingEngine:
    def __init__(self, db: Any = None, agent_registry: Any = None):
        self.db = db or FleetDatabase()
        self.agent_registry = agent_registry

    def generate_daily_briefing(self, agent_registry: Any = None, use_cache: Optional[bool] = None) -> Dict[str, Any]:
        if use_cache is None:
            from fleet.core.db.base import is_test_environment
            cache_enabled = not is_test_environment()
        else:
            cache_enabled = bool(use_cache)

        cache_key = str(getattr(self.db, "db_path", "default"))
        now_mono = time.monotonic()
        if cache_enabled:
            with _BRIEFING_CACHE_LOCK:
                entry = _BRIEFING_CACHE.get(cache_key)
                if entry is not None and (now_mono - float(entry.get("ts", 0.0))) < _BRIEFING_CACHE_TTL_SEC:
                    _BRIEFING_CACHE_STATS["hits"] += 1
                    return dict(entry["data"])

        tasks = self.db.list_tasks(exclude_tests=True)
        routines = self.db.list_routines()

        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = f"{now.strftime('%I:%M %p')} {TIMEZONE_NAME}"

        # Categorize tasks
        pending_tasks = [t for t in tasks if t["status"] in ("pending", "in_progress")]
        completed_tasks = [t for t in tasks if t["status"] == "completed"]

        p1_tasks = [t for t in pending_tasks if t["priority"] == "P1"]
        p2_tasks = [t for t in pending_tasks if t["priority"] == "P2"]
        p3_tasks = [t for t in pending_tasks if t["priority"] == "P3"]

        total_tasks = len(tasks)
        completion_rate = round((len(completed_tasks) / total_tasks * 100), 1) if total_tasks > 0 else 0

        # Completed routines today
        routines_done = [r for r in routines if r.get("completed_today")]

        # Metabolic Health & FFD Protocol Adherence
        metabolic = {}
        med_summary = ""
        try:
            metabolic = self.db.get_metabolic_profile()
            meds = self.db.list_medications()
            meds_taken = sum(1 for m in meds if m.get("taken_today"))
            total_meds = len(meds)
            if metabolic:
                days_left = metabolic.get("days_remaining", 75)
                target_a1c = metabolic.get("target_hba1c", 6.4)
                target_wt = metabolic.get("target_weight_kg", 75.0)
                med_summary = f"- 🩺 **Metabolic Goal:** HbA1c < {target_a1c}% by target date ({days_left}d remaining) • Target: {target_wt}kg\n- 💊 **Prescription Adherence:** {meds_taken}/{total_meds} doses taken today\n"
        except Exception:
            pass

        # Determine greeting based on hour
        hour = now.hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        # Formulate daily focus headline
        if p1_tasks:
            headline = f"You have {len(p1_tasks)} high-priority goal{'s' if len(p1_tasks) > 1 else ''} today: '{p1_tasks[0]['title']}'."
        elif pending_tasks:
            headline = f"You have {len(pending_tasks)} open task{'s' if len(pending_tasks) > 1 else ''} to tackle today."
        else:
            headline = "Your task board is clear! Great job staying ahead."

        # Key action items for the day (Top 3)
        top_focus = (p1_tasks + p2_tasks + p3_tasks)[:3]

        briefing_text = (
            f"📅 **Daily Briefing — {date_str} ({time_str})**\n\n"
            f"**{greeting}!** {headline}\n\n"
            f"📊 **Status Overview:**\n"
            f"- 🔴 High Priority (P1): {len(p1_tasks)}\n"
            f"- 🟡 Medium Priority (P2): {len(p2_tasks)}\n"
            f"- 🟢 Low Priority (P3): {len(p3_tasks)}\n"
            f"- ✅ Completed: {len(completed_tasks)} ({completion_rate}%)\n"
            f"- 🔄 Daily Habits Done: {len(routines_done)}/{len(routines)}\n"
            f"{med_summary}\n"
        )

        if top_focus:
            briefing_text += "**🎯 Today's Top Priorities:**\n"
            for idx, t in enumerate(top_focus, 1):
                badge = "🔴" if t["priority"] == "P1" else ("🟡" if t["priority"] == "P2" else "🟢")
                briefing_text += f"{idx}. {badge} **{t['title']}**\n"

        # Check calendar / meeting emails and auto-agenda prep (60s cached to avoid re-scanning inbox on every 8-15s poll)
        meetings_prep = []
        cached_meetings = None
        if cache_enabled:
            with _BRIEFING_CACHE_LOCK:
                m_ts = float(_MEETINGS_PREP_CACHE.get("ts", 0.0))
                if _MEETINGS_PREP_CACHE.get("data") is not None and (now_mono - m_ts) < _MEETINGS_PREP_TTL_SEC:
                    cached_meetings = list(_MEETINGS_PREP_CACHE["data"])
                    _BRIEFING_CACHE_STATS["meetings_hits"] += 1
        if cached_meetings is not None:
            meetings_prep = cached_meetings
        else:
            try:
                from fleet.integrations.gmail_client import gmail_manager
                sample_emails = gmail_manager.sync_and_classify(dry_run=True).get("classified_sample", [])
                for em in sample_emails:
                    if em.get("category_id") == 0 or em.get("has_calendar_part"):
                        prep = extract_meeting_agenda(em.get("subject", ""), em.get("snippet", ""), em.get("from", ""))
                        meetings_prep.append(prep)
            except Exception:
                meetings_prep = []
            if cache_enabled:
                with _BRIEFING_CACHE_LOCK:
                    _MEETINGS_PREP_CACHE["ts"] = now_mono
                    _MEETINGS_PREP_CACHE["data"] = list(meetings_prep)

        if meetings_prep:
            briefing_text += "\n**📅 Scheduled Meetings & Auto-Agenda Prep:**\n"
            for m in meetings_prep[:3]:
                briefing_text += f"- **{m['title']}** ({m['platform']} • {m['time']})\n"
                for p_note in m["prep_notes"]:
                    briefing_text += f"  • 💡 *Prep*: {p_note}\n"

        # Phase 4: $0.00 SQLite Rollup across Custom Studio Agents (urgent renewals <= 15d & warnings)
        custom_rollup: Dict[str, Any] = {
            "custom_agents_count": 0,
            "total_alerts": 0,
            "urgent_items": [],
            "warning_runs": [],
            "alerts": [],
        }
        try:
            if hasattr(self.db, "get_custom_agents_fleet_rollup"):
                reg = agent_registry or self.agent_registry
                if reg is None:
                    try:
                        import fleet.server as srv
                        if getattr(srv, "db", None) is self.db and getattr(srv, "agent_registry", None) is not None:
                            reg = srv.agent_registry
                    except Exception:
                        reg = None
                c_manifests = (
                    [m for m in reg.get_manifests() if m.get("is_custom")]
                    if reg is not None and hasattr(reg, "get_manifests")
                    else None
                )
                custom_rollup = self.db.get_custom_agents_fleet_rollup(custom_manifests=c_manifests)
        except Exception:
            pass

        custom_alerts = custom_rollup.get("alerts") or []
        if custom_alerts:
            briefing_text += f"\n**🛡️ Custom Agent Alerts & Upcoming Renewals ({custom_rollup.get('total_alerts', len(custom_alerts))}):**\n"
            for al in custom_alerts[:5]:
                if al.get("kind") == "deadline":
                    days_l = int(al.get("days_left", 0))
                    when_str = f"{abs(days_l)}d OVERDUE" if days_l < 0 else ("DUE TODAY" if days_l == 0 else f"due in {days_l}d")
                    briefing_text += f"- {al.get('agent_icon', '✨')} **{al.get('agent_name')}**: {al.get('title')} ({when_str} • {al.get('due_date')})\n"
                else:
                    briefing_text += f"- {al.get('agent_icon', '✨')} **{al.get('agent_name')}**: {al.get('title')}\n"

        result = {
            "date": date_str,
            "time": time_str,
            "greeting": greeting,
            "headline": headline,
            "briefing_markdown": briefing_text,
            "summary_stats": {
                "total_tasks": total_tasks,
                "pending_count": len(pending_tasks),
                "completed_count": len(completed_tasks),
                "completion_rate": completion_rate,
                "p1_count": len(p1_tasks),
                "p2_count": len(p2_tasks),
                "p3_count": len(p3_tasks),
                "routines_done": len(routines_done),
                "routines_total": len(routines),
                "meetings_count": len(meetings_prep),
                "custom_alerts_count": int(custom_rollup.get("total_alerts") or 0),
            },
            "top_focus": top_focus,
            "upcoming_meetings": meetings_prep,
            "metabolic_profile": metabolic,
            "custom_agent_alerts": custom_alerts,
            "custom_agents_rollup": custom_rollup,
        }
        if cache_enabled:
            with _BRIEFING_CACHE_LOCK:
                _BRIEFING_CACHE_STATS["misses"] += 1
                if cache_key not in _BRIEFING_CACHE and len(_BRIEFING_CACHE) >= 4:
                    oldest_key = min(_BRIEFING_CACHE.keys(), key=lambda k: float(_BRIEFING_CACHE[k].get("ts", 0.0)))
                    _BRIEFING_CACHE.pop(oldest_key, None)
                _BRIEFING_CACHE[cache_key] = {"ts": now_mono, "data": result}
        return dict(result) if cache_enabled else result
