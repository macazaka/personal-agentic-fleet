import urllib.parse
import re
from datetime import datetime
from typing import Any, Dict, List
from fleet.config import TIMEZONE_NAME
from fleet.core.database import FleetDatabase


def extract_meeting_agenda(subject: str, snippet: str = "", sender: str = "") -> Dict[str, Any]:
    """
    Parses an incoming meeting email/invite and generates an automated agenda preparation note.
    Tier 0: Pure deterministic heuristic (0 tokens).
    """
    clean_title = re.sub(r"^(?:Invitation:\s*|Updated invitation:\s*|New Event:\s*|Event:\s*)", "", subject, flags=re.I).strip()
    
    time_match = re.search(r"@\s*([A-Za-z]+ \d{1,2}(?:, \d{4})?\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", subject, flags=re.I)
    meeting_time = time_match.group(1) if time_match else "Scheduled Today"

    text_combined = f"{subject} {snippet}".lower()
    platform = "Calendar Sync"
    if "google meet" in text_combined:
        platform = "Google Meet"
    elif "zoom meeting" in text_combined or "zoom webinar" in text_combined:
        platform = "Zoom"
    elif "microsoft teams" in text_combined or "teams meeting" in text_combined:
        platform = "Microsoft Teams"
    elif "calendly" in text_combined:
        platform = "Calendly"
    else:
        for url_candidate in [w for w in f"{subject} {snippet}".split() if w.startswith(("http://", "https://"))]:
            try:
                host = urllib.parse.urlparse(url_candidate).netloc.lower()
                if host == "meet.google.com" or host.endswith(".meet.google.com"):
                    platform = "Google Meet"
                    break
                if host == "zoom.us" or host.endswith(".zoom.us"):
                    platform = "Zoom"
                    break
                if host == "teams.microsoft.com" or host.endswith(".teams.microsoft.com"):
                    platform = "Microsoft Teams"
                    break
            except Exception:
                pass

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
    def __init__(self, db: Any = None):
        self.db = db or FleetDatabase()

    def generate_daily_briefing(self) -> Dict[str, Any]:
        tasks = self.db.list_tasks()
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

        # Check calendar / meeting emails and auto-agenda prep
        meetings_prep = []
        try:
            from fleet.integrations.gmail_client import gmail_manager
            sample_emails = gmail_manager.sync_and_classify(dry_run=True).get("classified_sample", [])
            for em in sample_emails:
                if em.get("category_id") == 0 or em.get("has_calendar_part"):
                    prep = extract_meeting_agenda(em.get("subject", ""), em.get("snippet", ""), em.get("from", ""))
                    meetings_prep.append(prep)
        except Exception:
            meetings_prep = []

        if meetings_prep:
            briefing_text += "\n**📅 Scheduled Meetings & Auto-Agenda Prep:**\n"
            for m in meetings_prep[:3]:
                briefing_text += f"- **{m['title']}** ({m['platform']} • {m['time']})\n"
                for p_note in m["prep_notes"]:
                    briefing_text += f"  • 💡 *Prep*: {p_note}\n"

        return {
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
                "meetings_count": len(meetings_prep)
            },
            "top_focus": top_focus,
            "upcoming_meetings": meetings_prep,
            "metabolic_profile": metabolic
        }


