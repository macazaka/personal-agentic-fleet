"""
Tasks & Routines API endpoints for Personal Agentic Fleet.
"""

from datetime import datetime
import json
import re
from typing import Any, Dict, List
import urllib.parse
from fleet.api.router import router
import fleet.server as srv


def _parse_and_update_medication_from_task_edit(
    db: Any,
    med_id: int,
    title: str,
    description: str,
    due_date: str = "",
    source: str = "",
) -> Dict[str, Any]:
    """
    Parses inline task edits on a medication item (from title, description, due_date, and source)
    and updates `name`, `dosage`, `schedule_time`, `frequency`, and `instructions` in `medications`.
    """
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, dosage, schedule_time, frequency, instructions FROM medications WHERE id = ?", (med_id,))
        row = cur.fetchone()
        if not row:
            return {"updated": False, "id": med_id}
        old_name = str(row["name"] or "").strip()
        old_dosage = str(row["dosage"] or "1 Dose").strip()
        old_sched = str(row["schedule_time"] or "08:30").strip()
        old_freq = str(row["frequency"] or "Daily").strip()
        old_instr = str(row["instructions"] or "").strip()

    clean_title = (title or "").strip()
    clean_desc = (description or "").strip()
    clean_due = (due_date or "").strip()
    clean_src = (source or "").strip()

    # 1. Parse title: "{name} — {dosage} (@ {sched_time})"
    title_dosage = None
    title_sched = None
    if "—" in clean_title:
        left_part, right_part = clean_title.split("—", 1)
        new_name = left_part.strip() or old_name
        sched_m = re.search(r"\(@\s*([^)]+)\)", right_part)
        if sched_m:
            title_sched = sched_m.group(1).strip()
        dos_candidate = re.sub(r"\(@[^)]*\)", "", right_part).strip()
        if dos_candidate:
            title_dosage = dos_candidate
    else:
        new_name = clean_title or old_name

    # 2. Parse description: "Dosage: {dosage} • Schedule: {sched_time} ({freq}) • {instr}"
    desc_dosage = None
    desc_sched = None
    desc_freq = None
    dos_m = re.search(r"Dosage:\s*([^•\n]+)", clean_desc, re.IGNORECASE)
    if dos_m:
        desc_dosage = dos_m.group(1).strip()
    sch_m = re.search(r"Schedule:\s*([0-9]{1,2}:[0-9]{2})(?:\s*\(([^)]+)\))?", clean_desc, re.IGNORECASE)
    if sch_m:
        desc_sched = sch_m.group(1).strip()
        if sch_m.group(2):
            desc_freq = sch_m.group(2).strip()

    # Strip all leading "Dosage: ... •" and "Schedule: ... •" prefixes so instructions never duplicate
    stripped_instr = clean_desc
    while True:
        next_instr = re.sub(
            r"^(?:Dosage:\s*[^•\n]+•\s*|Schedule:\s*[^•\n]+•\s*)+",
            "",
            stripped_instr,
            flags=re.IGNORECASE,
        ).strip()
        if next_instr == stripped_instr:
            break
        stripped_instr = next_instr
    new_instr = stripped_instr if stripped_instr else old_instr

    # 3. Parse due_date for schedule time if changed there
    due_sched = None
    due_m = re.search(r"\bat\s+([0-9]{1,2}:[0-9]{2})\b", clean_due, re.IGNORECASE)
    if due_m:
        due_sched = due_m.group(1).strip()

    # 4. Prefer whichever field the user actually modified compared to old values
    if desc_dosage and desc_dosage != old_dosage:
        new_dosage = desc_dosage
    elif title_dosage and title_dosage != old_dosage:
        new_dosage = title_dosage
    else:
        new_dosage = desc_dosage or title_dosage or old_dosage

    if desc_sched and desc_sched != old_sched:
        new_sched = desc_sched
    elif title_sched and title_sched != old_sched:
        new_sched = title_sched
    elif due_sched and due_sched != old_sched:
        new_sched = due_sched
    else:
        new_sched = desc_sched or title_sched or due_sched or old_sched

    if clean_src in ("Daily", "Monthly", "Yearly") and clean_src.lower() != old_freq.lower():
        new_freq = clean_src
    elif desc_freq and desc_freq != old_freq:
        new_freq = desc_freq
    else:
        new_freq = old_freq or "Daily"

    ok = db.update_medication(
        med_id,
        name=new_name,
        dosage=new_dosage,
        schedule_time=new_sched,
        frequency=new_freq,
        instructions=new_instr,
    )
    return {
        "updated": ok,
        "id": med_id,
        "name": new_name,
        "dosage": new_dosage,
        "schedule_time": new_sched,
        "frequency": new_freq,
        "instructions": new_instr,
    }


def collect_unified_fleet_tasks(db: Any, registry: Any = None) -> List[Dict[str, Any]]:
    """
    Aggregates actionable Daily, Monthly, and Yearly tasks across ALL agents in the fleet
    into a single unified stream with full context and inline action metadata so the user
    never needs to visit individual agent pages to review or act on pending items.
    """
    now = datetime.now()
    today_fmt = now.strftime("%d %b %Y")
    month_short = now.strftime("%b")
    month_full = now.strftime("%B")
    year = now.year
    next_year = year + 1
    unified: List[Dict[str, Any]] = []

    # 1. Core Overview & Tasks (Daily, Monthly, Yearly tasks in `tasks` table)
    core_tasks = db.list_tasks(limit=250, exclude_tests=True)
    for t in core_tasks:
        src = str(t.get("source") or t.get("assigned_agent") or "Manual").strip()
        src_low = src.lower()
        cadence = "Monthly" if src_low == "monthly" else ("Yearly" if src_low == "yearly" else "Daily")
        unified.append({
            **t,
            "raw_id": t["id"],
            "action_type": "core_task",
            "agent_id": "overview",
            "agent_name": "Overview & Tasks",
            "agent_icon": "⚡",
            "cadence": cadence,
        })

    # 2. Health & Wellness Agent — Active Medications & Supplements (`medications` table)
    try:
        meds = db.list_medications()
        for m in meds:
            freq = str(m.get("frequency") or "Daily").strip()
            freq_low = freq.lower()
            cadence = "Monthly" if "month" in freq_low else ("Yearly" if "year" in freq_low else "Daily")
            sched_time = m.get("schedule_time") or "08:30"
            dosage = m.get("dosage") or "1 Dose"
            instr = m.get("instructions") or "Scheduled FFD & wellness supplement/medication protocol."
            due_str = (
                f"By 30 {month_short} {year} at {sched_time} (Monthly Supplement)"
                if cadence == "Monthly"
                else f"{today_fmt} at {sched_time} ({freq})"
            )
            unified.append({
                "id": f"med_{m['id']}",
                "raw_id": m["id"],
                "action_type": "medication",
                "agent_id": "health",
                "agent_name": "Health & Wellness",
                "agent_icon": "🌿",
                "source": cadence,
                "cadence": cadence,
                "priority": "P1" if not m.get("taken_today") else "P2",
                "status": "completed" if m.get("taken_today") else "pending",
                "title": f"{m['name']} — {dosage} (@ {sched_time})",
                "description": f"Dosage: {dosage} • Schedule: {sched_time} ({freq}) • {instr}",
                "due_date": due_str,
                "created_at": m.get("created_at") or now.isoformat(),
                "updated_at": m.get("taken_at") or now.isoformat(),
            })
    except Exception:
        pass

    # 3. Health & Wellness Agent — Daily Hydration Target (`hydration_logs` table)
    try:
        hyd = db.get_today_hydration()
        glasses = int(hyd.get("glasses") or 0)
        amount_ml = int(hyd.get("amount_ml") or 0)
        goal_ml = int(hyd.get("goal_ml") or 2500)
        pct = float(hyd.get("percentage") or 0.0)
        is_hyd_done = amount_ml >= goal_ml
        unified.append({
            "id": "hyd_today",
            "raw_id": "hyd_today",
            "action_type": "hydration",
            "agent_id": "health",
            "agent_name": "Health & Wellness",
            "agent_icon": "💧",
            "source": "Daily",
            "cadence": "Daily",
            "priority": "P1" if amount_ml < 1000 else "P2",
            "status": "completed" if is_hyd_done else "pending",
            "title": f"Daily Hydration Target — {amount_ml} / {goal_ml} ml ({glasses} Glasses • {pct}%)",
            "description": f"{hyd.get('reminder_status', 'Drink water regularly')} • Goal: {goal_ml} ml/day (10 glasses of 250ml).",
            "due_date": f"{today_fmt} (Daily Hydration — {month_short} {year})",
            "created_at": now.isoformat(),
            "updated_at": hyd.get("last_drank_at") or now.isoformat(),
        })
    except Exception:
        pass

    # 4. FFD & Daily Routines (`routines` table)
    try:
        routines = db.list_routines()
        for r in routines:
            t_target = r.get("time_target") or "09:00"
            r_title = r.get("title") or "Daily Routine"
            is_ffd = any(k in r_title.lower() for k in ("ffd", "smoothie", "shahi pani", "meds", "sleep"))
            unified.append({
                "id": f"routine_{r['id']}",
                "raw_id": r["id"],
                "action_type": "routine",
                "agent_id": "health" if is_ffd else "overview",
                "agent_name": "Health & Wellness" if is_ffd else "Overview & Tasks",
                "agent_icon": "🌿" if is_ffd else "⚡",
                "source": "Daily",
                "cadence": "Daily",
                "priority": "P1" if not r.get("completed_today") else "P2",
                "status": "completed" if r.get("completed_today") else "pending",
                "title": f"Daily Routine (@ {t_target}) — {r_title}",
                "description": f"Scheduled Time: {t_target} IST • Category: {(r.get('category') or 'FFD / Daily Habit').title()} • Check off when completed today.",
                "due_date": f"{today_fmt} at {t_target} (Month: {month_short} • Year: {year})",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
    except Exception:
        pass

    # 5. Custom Agents (e.g., Billing, Statement & Subscription Sentinel `cloud_subscription_sentinel` & others)
    try:
        manifests = registry.get_manifests(include_disabled=False) if registry else []
        custom_ids = [m["id"] for m in manifests if m.get("is_custom")] or ["cloud_subscription_sentinel"]
        name_map = {m["id"]: (m.get("name") or m["id"], m.get("icon") or "💳") for m in manifests}
        for cid in custom_ids:
            c_name, c_icon = name_map.get(cid, (cid.replace("_", " ").title(), "💳"))
            state = db.get_custom_agent_dashboard_state(cid)
            for entry in state.get("entries", []):
                e_id = entry.get("id")
                e_title = entry.get("title") or "Tracked Item"
                e_status = "completed" if str(entry.get("status") or "").lower() in ("completed", "done", "paid") else "pending"
                e_due = entry.get("due_date") or f"By 30 {month_short} {year}"
                num_val = entry.get("numeric_value")
                data_obj = entry.get("data") if isinstance(entry.get("data"), dict) else {}
                if data_obj.get("custom_description"):
                    desc_str = str(data_obj.get("custom_description")).strip()
                else:
                    details_parts = []
                    if num_val:
                        details_parts.append(f"Amount/Value: ₹{num_val}")
                    for k, v in data_obj.items():
                        if v and k != "custom_description":
                            details_parts.append(f"{k.replace('_', ' ').title()}: {v}")
                    desc_str = " • ".join(details_parts) if details_parts else f"Tracked by {c_name}"
                unified.append({
                    "id": f"custom_rec_{e_id}",
                    "raw_id": e_id,
                    "action_type": "custom_agent_entry",
                    "agent_id": cid,
                    "agent_name": c_name,
                    "agent_icon": c_icon,
                    "source": "Monthly",
                    "cadence": "Monthly",
                    "priority": "P1" if e_status == "pending" else "P2",
                    "status": e_status,
                    "title": f"[{c_name}] {e_title}",
                    "description": desc_str,
                    "due_date": f"{e_due} (Month: {month_full} • Year: {year})",
                    "created_at": entry.get("created_at") or now.isoformat(),
                    "updated_at": entry.get("created_at") or now.isoformat(),
                })
    except Exception:
        pass

    # 6. Email Intelligence Agent (`gmail`) — Unapproved Email/Attachment Proposals & Urgent/Actionable Emails
    try:
        backlog_items = db.list_feature_backlog_items(status="Unapproved")
        for b in backlog_items:
            unified.append({
                "id": f"backlog_{b['id']}",
                "raw_id": b["id"],
                "action_type": "email_proposal",
                "agent_id": "gmail",
                "agent_name": "Email Intelligence",
                "agent_icon": "📬",
                "source": "Daily",
                "cadence": "Daily",
                "priority": b.get("priority") or "P1",
                "status": "pending",
                "title": f"[Unapproved Email Proposal] {b.get('title', 'New Proposal')}",
                "description": f"{b.get('description', '')} • 🛡️ 4-Layer Virus Scan: CLEAN • Requires your approval before implementation.",
                "due_date": f"Pending Approval ({today_fmt})",
                "created_at": b.get("created_at") or now.isoformat(),
                "updated_at": b.get("updated_at") or now.isoformat(),
            })
    except Exception:
        pass

    try:
        emails = db.get_classified_emails(limit=40)
        action_emails = [
            em for em in emails
            if em.get("category_name") in ("Urgent", "Important", "Calendar & Meetings")
        ][:8]
        for em in action_emails:
            msg_id = em.get("id") or em.get("message_id")
            cat = em.get("category_name") or "Important"
            subj = em.get("subject") or "(No Subject)"
            sender = em.get("from") or em.get("sender") or "Unknown Sender"
            snippet = (em.get("snippet") or "")[:180]
            rec_date = str(em.get("received_date") or today_fmt)[:16]
            unified.append({
                "id": f"email_{msg_id}",
                "raw_id": msg_id,
                "action_type": "urgent_email",
                "agent_id": "gmail",
                "agent_name": "Email Intelligence",
                "agent_icon": "📬",
                "source": "Daily",
                "cadence": "Daily",
                "priority": "P1" if cat == "Urgent" else "P2",
                "status": "pending",
                "title": f"[{cat} Email] {subj}",
                "description": f"From: {sender}\nSummary: {snippet}",
                "due_date": f"Received: {rec_date} ({month_short} {year})",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
    except Exception:
        pass

    # 7. PC Optimizer Agent (`optimizer`) — Live RAM, Temp Bloat & Autonomous OS/Software Upgrades
    try:
        from fleet.core.optimizer import _get_memory_status_win32, check_os_and_software_upgrades
        mem = _get_memory_status_win32() or {"used_gb": 0, "total_gb": 16, "percent_used": 50, "status": "Optimal"}
        pct_ram = int(mem.get("percent_used") or 0)
        is_opt_needed = pct_ram >= 75
        unified.append({
            "id": "opt_workstation_health",
            "raw_id": "opt_workstation_health",
            "action_type": "optimizer",
            "agent_id": "optimizer",
            "agent_name": "PC Optimizer",
            "agent_icon": "🚀",
            "source": "Daily",
            "cadence": "Daily",
            "priority": "P1" if is_opt_needed else "P3",
            "status": "pending" if is_opt_needed else "completed",
            "title": f"Workstation RAM & Cache Health — {mem.get('used_gb', 0)} / {mem.get('total_gb', 0)} GB ({pct_ram}% {mem.get('status', 'Optimal')})",
            "description": "1-Click PC Optimization: Trim background working-set RAM, flush DNS resolver cache, and purge temporary bloat files.",
            "due_date": f"{today_fmt} (Daily Workstation Check)",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        upg_info = check_os_and_software_upgrades(force_refresh=False)
        pending_upg = int(upg_info.get("total_pending_count") or 0)
        os_ver_label = str(upg_info.get("os_info", {}).get("display_version") or "Windows")
        unified.append({
            "id": "opt_os_software_upgrades",
            "raw_id": "opt_os_software_upgrades",
            "action_type": "optimizer_upgrade",
            "agent_id": "optimizer",
            "agent_name": "PC Optimizer",
            "agent_icon": "🚀",
            "source": "Daily",
            "cadence": "Daily",
            "priority": "P1" if upg_info.get("security_critical_count", 0) > 0 else ("P2" if pending_upg > 0 else "P3"),
            "status": "pending" if pending_upg > 0 else "completed",
            "title": (
                f"OS & Software Upgrades ({os_ver_label}) — {pending_upg} Pending Upgrade(s)"
                if pending_upg > 0
                else f"OS & Software Upgrades ({os_ver_label}) — Up to Date (Auto-Managed)"
            ),
            "description": (
                f"OS Updates: {upg_info.get('os_updates_count', 0)} • Software Upgrades: {upg_info.get('eligible_software_count', 0)} "
                f"• Auto-Pilot: {'ON' if upg_info.get('policy', {}).get('auto_install_all_software', True) else 'Security Only'}"
            ),
            "due_date": f"{today_fmt} (Auto-Upgrade Check)",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
    except Exception:
        pass

    return unified


@router.get("/api/tasks")
def get_tasks(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    if query.get("unified", ["false"])[0].lower() in ("true", "1"):
        unified = collect_unified_fleet_tasks(srv.db, getattr(srv, "agent_registry", None))
        handler._send_json(unified)
        return
    tasks = srv.db.list_tasks(limit=200, exclude_tests=True)
    handler._send_json(tasks)


@router.get("/api/tasks/unified")
def get_unified_tasks(handler: Any, parsed_url: urllib.parse.ParseResult):
    unified = collect_unified_fleet_tasks(srv.db, getattr(srv, "agent_registry", None))
    handler._send_json(unified)


@router.post("/api/tasks/unified_action")
def post_unified_task_action(handler: Any, body: Dict[str, Any]):
    action_type = str(body.get("action_type") or body.get("origin_type") or "").strip()
    raw_id = body.get("raw_id")
    sub_action = str(body.get("sub_action") or "toggle").strip()

    try:
        if action_type == "core_task":
            task_id = int(str(raw_id or 0))
            if sub_action == "delete":
                srv.db.delete_task(task_id)
                handler._send_json({"status": "deleted"})
            elif sub_action == "edit":
                title = str(body.get("title") or "").strip()
                description = str(body.get("description") or "").strip()
                priority = str(body.get("priority") or "P2").strip()
                source = str(body.get("source") or "").strip() or None
                due_date = str(body.get("due_date") or "").strip() or None
                if due_date:
                    due_date = re.sub(r"\s*\(Added\s+[^)]+\)\s*$", "", due_date, flags=re.IGNORECASE).strip() or None
                if not title or not description:
                    handler._send_json({"error": "Both title and description are required"}, 400)
                    return
                ok = srv.db.update_task(
                    task_id,
                    title=title,
                    description=description,
                    priority=priority,
                    source=source,
                    due_date=due_date,
                )
                if not ok:
                    handler._send_json({"error": "Task not found"}, 404)
                    return
                handler._send_json({"status": "updated", "id": task_id})
            else:
                tasks = srv.db.list_tasks(limit=500, require_description=False)
                task = next((t for t in tasks if t["id"] == task_id), None)
                if not task:
                    handler._send_json({"error": "Task not found"}, 404)
                    return
                new_status = "completed" if task["status"] != "completed" else "pending"
                srv.db.update_task_status(task_id, new_status)
                handler._send_json({"status": "updated", "new_status": new_status})
            return

        if action_type == "medication":
            med_id = int(str(raw_id or 0))
            if sub_action == "edit":
                title = str(body.get("title") or "").strip()
                description = str(body.get("description") or "").strip()
                due_date = str(body.get("due_date") or "").strip()
                source = str(body.get("source") or "").strip()
                updated_med = _parse_and_update_medication_from_task_edit(
                    srv.db,
                    med_id=med_id,
                    title=title,
                    description=description,
                    due_date=due_date,
                    source=source,
                )
                handler._send_json({"status": "updated", "id": med_id, "medication": updated_med})
                return
            taken = srv.db.toggle_medication_today(med_id)
            handler._send_json({"status": "updated", "taken": taken})
            return

        if action_type == "hydration":
            glasses_delta = int(body.get("glasses_delta", 1))
            res = srv.db.log_water_intake(glasses_delta=glasses_delta, amount_delta_ml=glasses_delta * 250)
            handler._send_json({"status": "updated", "hydration": res})
            return

        if action_type == "routine":
            routine_id = int(str(raw_id or 0))
            if sub_action == "edit":
                title = str(body.get("title") or "").strip()
                description = str(body.get("description") or "").strip()
                due_date = str(body.get("due_date") or "").strip()
                with srv.db._get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT title, time_target, category FROM routines WHERE id = ?", (routine_id,))
                    row = cur.fetchone()
                    cur_title = str(row["title"] if row else "Routine").strip()
                    cur_time = str(row["time_target"] if row else "09:00").strip()
                    cur_cat = str(row["category"] if row else "General").strip()

                    new_time = cur_time
                    m_title_time = re.search(r"\[\s*@\s*([0-9]{1,2}:[0-9]{2})\s*\]", title)
                    if m_title_time:
                        new_time = m_title_time.group(1).strip()
                    m_desc_time = re.search(r"Scheduled\s+Time\s*:\s*([0-9]{1,2}:[0-9]{2})", description, flags=re.IGNORECASE)
                    if m_desc_time and m_desc_time.group(1).strip() != cur_time:
                        new_time = m_desc_time.group(1).strip()
                    m_due_time = re.search(r"\bat\s+([0-9]{1,2}:[0-9]{2})\b", due_date, flags=re.IGNORECASE)
                    if m_due_time and m_due_time.group(1).strip() != cur_time:
                        new_time = m_due_time.group(1).strip()

                    clean_title = title
                    if "—" in clean_title:
                        clean_title = clean_title.split("—", 1)[1].strip()
                    clean_title = re.sub(r"^\[\s*@\s*[^\]]+\]\s*", "", clean_title).strip() or cur_title

                    new_cat = cur_cat
                    m_cat = re.search(r"Category\s*:\s*([^•\n]+)", description, flags=re.IGNORECASE)
                    if m_cat:
                        new_cat = m_cat.group(1).strip() or cur_cat
                    elif description and "Scheduled Time:" not in description:
                        new_cat = description.strip()

                    cur.execute(
                        "UPDATE routines SET title = ?, time_target = ?, category = ? WHERE id = ?",
                        (clean_title, new_time, new_cat, routine_id),
                    )
                    conn.commit()
                handler._send_json({"status": "updated", "id": routine_id, "title": clean_title, "time_target": new_time, "category": new_cat})
                return
            srv.db.toggle_routine(routine_id)
            handler._send_json({"status": "updated"})
            return

        if action_type == "custom_agent_entry":
            rec_id = int(str(raw_id or 0))
            with srv.db._get_connection() as conn:
                cur = conn.cursor()
                if sub_action == "edit":
                    title = str(body.get("title") or "").strip()
                    if title.startswith("[") and "]" in title:
                        title = title.split("]", 1)[1].strip()
                    due_date = str(body.get("due_date") or "").strip()
                    due_date = re.sub(r"\s*\(Month:\s*[^)]+\)\s*$", "", due_date, flags=re.IGNORECASE).strip()
                    description = str(body.get("description") or "").strip()
                    cur.execute("SELECT data_json FROM custom_agent_records WHERE id = ?", (rec_id,))
                    rec_row = cur.fetchone()
                    import json as _json
                    data_obj: Dict[str, Any] = {}
                    if rec_row and rec_row["data_json"]:
                        try:
                            parsed = _json.loads(rec_row["data_json"])
                            if isinstance(parsed, dict):
                                data_obj = parsed
                        except Exception:
                            data_obj = {}
                    if description:
                        data_obj["custom_description"] = description
                    cur.execute(
                        "UPDATE custom_agent_records SET title = ?, due_date = ?, data_json = ? WHERE id = ?",
                        (title, due_date, _json.dumps(data_obj), rec_id),
                    )
                    conn.commit()
                    handler._send_json({"status": "updated", "id": rec_id, "title": title, "due_date": due_date, "description": description})
                    return
                cur.execute("SELECT status FROM custom_agent_records WHERE id = ?", (rec_id,))
                row = cur.fetchone()
                cur_status = str(row["status"] if row else "pending").lower()
                new_status = "pending" if cur_status in ("completed", "done", "paid") else "completed"
                cur.execute("UPDATE custom_agent_records SET status = ? WHERE id = ?", (new_status, rec_id))
                conn.commit()
            handler._send_json({"status": "updated", "new_status": new_status})
            return

        if action_type == "email_proposal":
            backlog_id = int(str(raw_id or 0))
            if sub_action == "reject":
                srv.db.update_feature_backlog_item(backlog_id, status="Rejected")
                handler._send_json({"status": "rejected"})
            else:
                from fleet.integrations.email_intelligence_proposals import approve_email_proposal
                res = approve_email_proposal(
                    proposal_id="",
                    db=srv.db,
                    registry=getattr(srv, "agent_registry", None),
                    backlog_id=backlog_id,
                )
                handler._send_json({"status": "approved", "result": res})
            return

        if action_type == "optimizer":
            ram_res = srv.optimize_ram()
            temp_res = srv.clean_temp_files()
            handler._send_json({"status": "optimized", "ram": ram_res, "temp": temp_res})
            return

        if action_type == "optimizer_upgrade":
            upg_res = srv.run_automatic_upgrade_manager(force_scan=True, dry_run=False)
            handler._send_json({"status": "upgraded", "upgrades": upg_res})
            return

        handler._send_json({"error": f"Unsupported action_type: {action_type}"}, 400)
    except Exception as exc:
        handler._send_json({"error": str(exc)}, 500)


@router.post("/api/tasks")
def create_task(handler: Any, body: Dict[str, Any]):
    title = body.get("title", "").strip()
    description = body.get("description", "").strip()
    priority = body.get("priority", "P2")
    source = body.get("source", "Dashboard").strip() or "Dashboard"
    due_date = (body.get("due_date") or "").strip() or None
    if not title:
        handler._send_json({"error": "Title required"}, 400)
        return
    if not description:
        handler._send_json({"error": "Description required"}, 400)
        return
    task_id = srv.db.add_task(title, description=description, priority=priority, due_date=due_date, source=source)
    handler._send_json({"id": task_id, "status": "created"})


@router.post("/api/tasks/toggle")
def toggle_task(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing task ID"}, 400)
        return
    task_id = int(raw_id)
    tasks = srv.db.list_tasks(limit=500)
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        handler._send_json({"error": "Not found"}, 404)
        return
    new_status = "completed" if task["status"] != "completed" else "pending"
    srv.db.update_task_status(task_id, new_status)
    handler._send_json({"status": "updated", "new_status": new_status})


@router.post("/api/tasks/update")
def update_task_endpoint(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id") if body.get("id") is not None else body.get("task_id")
    if raw_id is None:
        handler._send_json({"error": "Missing task ID"}, 400)
        return
    title = str(body.get("title") or "").strip()
    description = str(body.get("description") or "").strip()
    priority = str(body.get("priority") or "P2").strip()
    source = str(body.get("source") or "").strip() or None
    due_date = str(body.get("due_date") or "").strip() or None
    if not title or not description:
        handler._send_json({"error": "Both title and description are required"}, 400)
        return
    ok = srv.db.update_task(
        int(raw_id),
        title=title,
        description=description,
        priority=priority,
        source=source,
        due_date=due_date,
    )
    if not ok:
        handler._send_json({"error": "Task not found"}, 404)
        return
    handler._send_json({"status": "updated", "id": int(raw_id)})


@router.post("/api/tasks/delete")
def delete_task(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing task ID"}, 400)
        return
    task_id = int(raw_id)
    srv.db.delete_task(task_id)
    handler._send_json({"status": "deleted"})


@router.get("/api/routines")
def get_routines(handler: Any, parsed_url: urllib.parse.ParseResult):
    routines = srv.db.list_routines()
    handler._send_json(routines)


@router.post("/api/routines/toggle")
def toggle_routine(handler: Any, body: Dict[str, Any]):
    raw_id = body.get("id")
    if raw_id is None:
        handler._send_json({"error": "Missing routine ID"}, 400)
        return
    routine_id = int(raw_id)
    srv.db.toggle_routine(routine_id)
    handler._send_json({"status": "toggled"})

