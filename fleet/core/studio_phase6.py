"""
Phase 6: Autonomous Multi-Source Auto-Ingestion, Grounded Agent Chat,
Smart Renewal Roll-Forward, Outbound Action Hooks & Multi-Agent Squad Blueprints.

All filesystem operations (watched drop-folders and markdown reports) are strictly
isolated inside `fleet/data/user/` (`DATA_DIR / "user"`), with zero external Python
dependencies and $0.00 deterministic offline execution support.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from fleet.config import DATA_DIR
from fleet.core.document_extractor import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    extract_tracking_items_from_document,
    normalize_extracted_date,
    normalize_extracted_number,
    parse_uploaded_document,
)

logger = logging.getLogger("fleet.core.studio_phase6")

# ---------------------------------------------------------------------------
# 1. Canonical Outbound Action Hooks & Recurrence Cycles
# ---------------------------------------------------------------------------

SUPPORTED_RECURRENCE_CYCLES: Dict[str, Dict[str, Any]] = {
    "none": {"id": "none", "label": "One-Time (No Auto-Roll)", "months": 0},
    "monthly": {"id": "monthly", "label": "Monthly (+1 Month)", "months": 1},
    "quarterly": {"id": "quarterly", "label": "Quarterly (+3 Months)", "months": 3},
    "semi_annual": {"id": "semi_annual", "label": "Semi-Annual (+6 Months)", "months": 6},
    "annual": {"id": "annual", "label": "Annual (+1 Year)", "months": 12},
}

SUPPORTED_OUTBOUND_ACTIONS: List[Dict[str, str]] = [
    {
        "id": "auto_create_task",
        "label": "Auto-Create Priority Fleet Task",
        "icon": "📋",
        "description": "Automatically creates a deduplicated P1/P2 task in your main Fleet Tasks queue when an item is overdue or due within 15 days.",
    },
    {
        "id": "desktop_toast",
        "label": "Send Desktop Toast Notification",
        "icon": "🔔",
        "description": "Dispatches an immediate Windows desktop notification when warning thresholds or <=15d deadlines trigger.",
    },
    {
        "id": "markdown_report",
        "label": "Write Markdown Digest Report",
        "icon": "📝",
        "description": "Exports an up-to-date Markdown executive report to fleet/data/user/reports/<agent_id>_latest.md on each run.",
    },
    {
        "id": "emit_followup_event",
        "label": "Emit Inter-Agent Follow-Up Signal",
        "icon": "⚡",
        "description": "Publishes an EventBus follow-up signal so downstream Squad agents react automatically.",
    },
]


def get_supported_outbound_actions() -> List[Dict[str, str]]:
    """Returns copy of supported Phase 6 outbound remediation action hooks."""
    return [dict(a) for a in SUPPORTED_OUTBOUND_ACTIONS]


# ---------------------------------------------------------------------------
# 2. Multi-Agent Squad Blueprints (1-Click Coordinated Teams)
# ---------------------------------------------------------------------------

SQUAD_BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "id": "personal_cfo_compliance_squad",
        "title": "Personal CFO & Policy Squad",
        "icon": "🛡️",
        "category": "Finance",
        "summary": "3 coordinated agents: Drop-Folder Document Extractor -> Renewal & Warranty Guard -> Spend Trend Analyst.",
        "agents": [
            {
                "id": "cfo_doc_ingestor",
                "name": "Policy & Bill Inbox Extractor",
                "icon": "📄",
                "category": "Finance",
                "archetype": "tracker",
                "intelligence_mode": "hybrid",
                "description": "Watches inbox folder and paper-trail emails to extract policies, contracts, and bills automatically.",
                "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
                "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Document / Obligation", "type": "text", "placeholder": "e.g. Car Insurance Policy"},
                    {"key": "due_date", "label": "Expiry / Due Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                    {"key": "numeric_value", "label": "Premium / Amount", "type": "number", "placeholder": "15000"},
                    {"key": "reference_no", "label": "Policy / Invoice #", "type": "text", "placeholder": "POL-2026-991"},
                ],
                "routine_task": "scan_and_audit_docs",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "08:30", "time": "08:30", "display": "Daily at 08:30"},
                "event_triggers": ["gmail.paper_trail_detected"],
                "outbound_actions": ["emit_followup_event", "markdown_report"],
                "auto_ingest_inbox": True,
                "default_recurrence": "annual",
            },
            {
                "id": "cfo_renewal_guard",
                "name": "Renewal & Warranty Guard",
                "icon": "🛡️",
                "category": "Finance",
                "archetype": "tracker",
                "intelligence_mode": "hybrid",
                "description": "Monitors <=15-day policy, lease, and warranty expiries with 1-click annual roll-forward and auto-tasks.",
                "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
                "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "countdown_cards", "kanban_board", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Policy / Asset", "type": "text", "placeholder": "e.g. Creta Motor Insurance"},
                    {"key": "due_date", "label": "Renewal Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                    {"key": "numeric_value", "label": "Renewal Cost", "type": "number", "placeholder": "18500"},
                    {"key": "provider_name", "label": "Insurer / Vendor", "type": "text", "placeholder": "ICICI Lombard"},
                ],
                "routine_task": "check_upcoming_renewals",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "08:45", "time": "08:45", "display": "Daily at 08:45"},
                "event_triggers": ["agent.alert"],
                "outbound_actions": ["auto_create_task", "desktop_toast"],
                "auto_ingest_inbox": True,
                "default_recurrence": "annual",
            },
            {
                "id": "cfo_spend_analyst",
                "name": "Spend & Obligation Analyst",
                "icon": "📈",
                "category": "Finance",
                "archetype": "llm_analyst",
                "intelligence_mode": "hybrid",
                "description": "Synthesizes executive spend trends, upcoming cashflow obligations, and renewal cost deltas.",
                "permissions": ["db:read", "db:write", "ui:render"],
                "ui_blocks": ["alert_banner", "kpi_row", "sparkline_chart", "ai_insight_card", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Category / Cycle", "type": "text", "placeholder": "e.g. Q4 Annual Renewals"},
                    {"key": "due_date", "label": "Review Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                    {"key": "numeric_value", "label": "Total Spend", "type": "number", "placeholder": "42000"},
                ],
                "routine_task": "synthesize_spend_digest",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "09:00", "time": "09:00", "display": "Daily at 09:00"},
                "event_triggers": ["overview.morning_briefing"],
                "outbound_actions": ["markdown_report"],
                "auto_ingest_inbox": False,
                "default_recurrence": "monthly",
            },
        ],
    },
    {
        "id": "longevity_clinical_squad",
        "title": "Clinical Lab & Protocol Squad",
        "icon": "🩺",
        "category": "Health",
        "summary": "2 coordinated agents: Lab Biomarker & Prescription Extractor -> Daily Wellness Protocol Coach.",
        "agents": [
            {
                "id": "clinical_lab_sentinel",
                "name": "Lab Biomarker & Rx Sentinel",
                "icon": "🩺",
                "category": "Health",
                "archetype": "tracker",
                "intelligence_mode": "hybrid",
                "description": "Ingests clinical lab PDFs and prescriptions, flags out-of-range biomarkers, and schedules re-tests.",
                "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
                "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "sparkline_chart", "countdown_cards", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Biomarker / Medication", "type": "text", "placeholder": "e.g. HbA1c / Vitamin D3"},
                    {"key": "due_date", "label": "Next Re-Test / Refill", "type": "date", "placeholder": "YYYY-MM-DD"},
                    {"key": "numeric_value", "label": "Measured Value", "type": "number", "placeholder": "5.8"},
                    {"key": "reference_range", "label": "Ref Range / Dosage", "type": "text", "placeholder": "4.0 - 5.6 %"},
                ],
                "routine_task": "audit_biomarkers",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "08:00", "time": "08:00", "display": "Daily at 08:00"},
                "event_triggers": ["overview.morning_briefing"],
                "outbound_actions": ["auto_create_task", "emit_followup_event"],
                "auto_ingest_inbox": True,
                "default_recurrence": "quarterly",
            },
            {
                "id": "daily_protocol_coach",
                "name": "Daily Protocol & Vitals Coach",
                "icon": "🌿",
                "category": "Health",
                "archetype": "tracker",
                "intelligence_mode": "hybrid",
                "description": "Tracks daily supplement, conditioning, and recovery checklists linked to biomarker goals.",
                "permissions": ["db:read", "db:write", "ui:render"],
                "ui_blocks": ["alert_banner", "kpi_row", "habit_checklist", "ai_insight_card", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Protocol / Vital Note", "type": "text", "placeholder": "e.g. Morning Zone-2 + Hydration"},
                    {"key": "numeric_value", "label": "Duration / Score", "type": "number", "placeholder": "45"},
                ],
                "routine_task": "check_daily_protocol",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "08:15", "time": "08:15", "display": "Daily at 08:15"},
                "event_triggers": ["health.workout_completed", "agent.alert"],
                "outbound_actions": ["markdown_report"],
                "auto_ingest_inbox": False,
                "default_recurrence": "none",
            },
        ],
    },
    {
        "id": "devops_release_squad",
        "title": "DevOps Uptime & Release Squad",
        "icon": "🚀",
        "category": "DevOps",
        "summary": "2 coordinated agents: Production Endpoint Latency Watcher -> SOW & Release Milestone Kanban Board.",
        "agents": [
            {
                "id": "prod_endpoint_sentinel",
                "name": "Prod API & Latency Sentinel",
                "icon": "🌐",
                "category": "Monitoring",
                "archetype": "http_watcher",
                "intelligence_mode": "hybrid",
                "description": "Probes HTTP/API endpoints, charts response latency sparklines, and emits outage alerts.",
                "permissions": ["db:read", "db:write", "ui:render", "network:outbound", "event_bus:publish"],
                "ui_blocks": ["alert_banner", "kpi_row", "quick_capture_bar", "sparkline_chart", "status_timeline", "history_table"],
                "fields": [
                    {"key": "title", "label": "Service Name", "type": "text", "placeholder": "e.g. Production Gateway"},
                    {"key": "target_url", "label": "Healthcheck URL", "type": "url", "placeholder": "https://example.com/health"},
                    {"key": "numeric_value", "label": "SLA Budget (ms)", "type": "number", "placeholder": "350"},
                ],
                "routine_task": "probe_endpoints",
                "schedule_cadence": "every_30_min",
                "schedule": {"type": "cron", "value": "*/30 * * * *", "display": "Every 30m"},
                "event_triggers": [],
                "outbound_actions": ["desktop_toast", "emit_followup_event"],
                "auto_ingest_inbox": False,
                "default_recurrence": "none",
            },
            {
                "id": "release_milestone_board",
                "name": "Release & SOW Milestone Board",
                "icon": "🗂️",
                "category": "DevOps",
                "archetype": "tracker",
                "intelligence_mode": "hybrid",
                "description": "Extracts deliverables from project SOW/syllabus docs into a 3-stage Kanban board with auto-tasks.",
                "permissions": ["db:read", "db:write", "ui:render"],
                "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "kanban_board", "countdown_cards", "agent_chat", "history_table"],
                "fields": [
                    {"key": "title", "label": "Milestone / Deliverable", "type": "text", "placeholder": "e.g. v2.4 Security Sign-Off"},
                    {"key": "due_date", "label": "Target Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                    {"key": "numeric_value", "label": "Story Points / Weight", "type": "number", "placeholder": "8"},
                ],
                "routine_task": "audit_release_milestones",
                "schedule_cadence": "daily_morning",
                "schedule": {"type": "time", "value": "09:15", "time": "09:15", "display": "Daily at 09:15"},
                "event_triggers": ["agent.alert"],
                "outbound_actions": ["auto_create_task", "markdown_report"],
                "auto_ingest_inbox": True,
                "default_recurrence": "none",
            },
        ],
    },
]


def get_squad_blueprints() -> List[Dict[str, Any]]:
    """Returns copy of curated multi-agent squad blueprints."""
    return json.loads(json.dumps(SQUAD_BLUEPRINTS))


# ---------------------------------------------------------------------------
# 3. Watched Drop-Folder & Email Payload Auto-Ingestion Engine
# ---------------------------------------------------------------------------

def get_agent_inbox_dir(agent_id: str, custom_subfolder: str = "") -> Path:
    """
    Resolves and creates the isolated watched drop-folder for a custom agent,
    strictly confined inside `DATA_DIR / "user" / "inbox"`.
    """
    clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", (agent_id or "custom_agent").strip()) or "custom_agent"
    user_inbox_root = (DATA_DIR / "user" / "inbox").resolve()
    user_inbox_root.mkdir(parents=True, exist_ok=True)

    if custom_subfolder and custom_subfolder.strip():
        sub_clean = re.sub(r"[^a-zA-Z0-9_/-]", "_", custom_subfolder.strip().replace("\\", "/")).strip("/")
        candidate = (user_inbox_root / sub_clean).resolve()
        try:
            candidate.relative_to(user_inbox_root)
            target = candidate
        except ValueError:
            target = user_inbox_root / clean_agent
    else:
        target = user_inbox_root / clean_agent

    target.mkdir(parents=True, exist_ok=True)
    return target


def _collect_existing_doc_hashes(db: Any, agent_id: str) -> set[str]:
    hashes: set[str] = set()
    if db is None:
        return hashes
    try:
        docs = db.list_custom_agent_records(agent_id, record_type="document", limit=200)
        for d in docs:
            d_data = d.get("data") if isinstance(d.get("data"), dict) else {}
            h = str(d_data.get("sha256") or "").strip().lower()
            if h:
                hashes.add(h)
    except Exception as exc:
        logger.debug("Could not read existing document hashes for %s: %s", agent_id, exc)
    return hashes


def scan_and_ingest_agent_inbox(
    agent: Any,
    db: Any,
    payload: Optional[Dict[str, Any]] = None,
    provider_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Phase 6 Hands-Free Auto-Ingestion:
    1. Scans `DATA_DIR / "user" / "inbox" / <agent_id>/` for new supported documents.
    2. Deduplicates by SHA-256 against already-ingested `record_type="document"` records.
    3. Extracts structured tracking items via LLM / deterministic fallback, commits them
       into SQLite, and archives processed inbox files into `<inbox>/processed/`.
    4. Also ingests direct EventBus payloads (e.g. `gmail.paper_trail_detected` with
       `subject`/`body`/`snippet`/`content_base64`).
    """
    payload = payload if isinstance(payload, dict) else {}
    meta = getattr(agent, "manifest_meta", {}) or {}
    agent_id = str(getattr(agent, "id", "") or meta.get("id") or "custom_agent")
    inbox_dir = get_agent_inbox_dir(agent_id, str(meta.get("inbox_subfolder") or ""))
    processed_dir = inbox_dir / "processed"

    known_hashes = _collect_existing_doc_hashes(db, agent_id)
    ingested_files: List[Dict[str, Any]] = []
    skipped_duplicates = 0
    total_committed_items = 0

    prov = str(provider_override or meta.get("provider") or "auto").strip()
    if meta.get("intelligence_mode") == "deterministic" and not provider_override:
        prov = "deterministic"
    mdl = str(meta.get("model") or getattr(agent, "preferred_model", "") or "").strip() or None
    default_rec = str(meta.get("default_recurrence") or "none").strip().lower()

    # A. Scan physical files dropped in the agent's watched inbox directory
    candidate_files = sorted(
        [
            p for p in inbox_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS
        ],
        key=lambda x: x.name,
    )

    for fp in candidate_files[:20]:
        try:
            raw_bytes = fp.read_bytes()
        except Exception as exc:
            logger.warning("Could not read inbox file %s: %s", fp, exc)
            continue
        if not raw_bytes:
            continue

        sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
        if sha256_hex in known_hashes:
            skipped_duplicates += 1
            processed_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fp), str(processed_dir / f"dup_{sha256_hex[:8]}_{fp.name}"))
            continue

        import base64
        b64_str = base64.b64encode(raw_bytes).decode("ascii")
        try:
            ext_res = extract_tracking_items_from_document(
                filename=fp.name,
                content_base64=b64_str,
                agent_id=agent_id,
                agent_name=str(meta.get("name") or getattr(agent, "display_name", agent_id)),
                agent_description=str(meta.get("description") or ""),
                agent_system_prompt=str(meta.get("system_prompt") or ""),
                fields=meta.get("fields"),
                provider=prov,
                model=mdl,
                persist_to_vault=True,
            )
        except Exception as exc:
            logger.warning("Inbox extraction failed for %s: %s", fp.name, exc)
            continue

        vault_meta = ext_res.get("vault") or {}
        doc_rec_id = 0
        if db is not None:
            doc_rec_id = db.add_custom_agent_record(
                agent_id=agent_id,
                title=ext_res["filename"],
                record_type="document",
                data={
                    "filename": ext_res["filename"],
                    "sha256": sha256_hex,
                    "ingestion_source": "watched_inbox",
                    "detected_scenario": ext_res["detected_scenario"],
                    "scenario_title": ext_res["scenario_profile"]["title"],
                    "scenario_icon": ext_res["scenario_profile"]["icon"],
                    "summary": ext_res["document_summary"],
                    "items_count": ext_res["items_count"],
                    "engine_used": ext_res["engine_used"],
                    "model_used": ext_res["model_used"],
                    "vault_rel_path": vault_meta.get("vault_rel_path", ""),
                },
                status="ok",
                numeric_value=float(ext_res["items_count"]),
            )
            for item in ext_res["items"]:
                extra_d = dict(item.get("extra_fields") or {})
                extra_d.setdefault("source_document", ext_res["filename"])
                extra_d["ingestion_source"] = "watched_inbox"
                extra_d["doc_record_id"] = doc_rec_id
                if default_rec and default_rec != "none":
                    extra_d.setdefault("recurrence", default_rec)
                db.add_custom_agent_record(
                    agent_id=agent_id,
                    title=str(item.get("title") or ext_res["filename"])[:160],
                    record_type="entry",
                    data=extra_d,
                    status="ok",
                    due_date=str(item.get("due_date") or ""),
                    numeric_value=float(item.get("numeric_value") or 0.0),
                )
                total_committed_items += 1

        known_hashes.add(sha256_hex)
        processed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(fp), str(processed_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fp.name}"))
        ingested_files.append({
            "filename": ext_res["filename"],
            "items_count": ext_res["items_count"],
            "detected_scenario": ext_res["detected_scenario"],
            "doc_record_id": doc_rec_id,
        })

    # B. EventBus Email / Paper-Trail Payload Auto-Ingestion
    email_subject = str(payload.get("subject") or payload.get("email_subject") or "").strip()
    email_body = str(payload.get("body") or payload.get("snippet") or payload.get("email_text") or "").strip()
    email_b64 = str(payload.get("attachment_base64") or payload.get("content_base64") or "").strip()
    if (email_subject and email_body) or email_b64:
        combined_txt = f"Subject: {email_subject}\n{email_body}".strip()
        raw_sig = (email_b64 or combined_txt).encode("utf-8", errors="ignore")
        sha256_hex = hashlib.sha256(raw_sig).hexdigest()
        if sha256_hex not in known_hashes and len(raw_sig) > 12:
            fname = str(payload.get("filename") or (f"email_{re.sub(r'[^a-zA-Z0-9]+', '_', email_subject)[:36]}.txt" if email_subject else "event_email.txt"))
            try:
                ext_res = extract_tracking_items_from_document(
                    filename=fname,
                    content_base64=email_b64,
                    text_content="" if email_b64 else combined_txt,
                    agent_id=agent_id,
                    agent_name=str(meta.get("name") or agent_id),
                    agent_description=str(meta.get("description") or ""),
                    fields=meta.get("fields"),
                    provider=prov,
                    model=mdl,
                    persist_to_vault=True,
                )
                if db is not None and ext_res["items"]:
                    doc_rec_id = db.add_custom_agent_record(
                        agent_id=agent_id,
                        title=ext_res["filename"],
                        record_type="document",
                        data={
                            "filename": ext_res["filename"],
                            "sha256": sha256_hex,
                            "ingestion_source": "event_bus_email",
                            "detected_scenario": ext_res["detected_scenario"],
                            "scenario_title": ext_res["scenario_profile"]["title"],
                            "scenario_icon": ext_res["scenario_profile"]["icon"],
                            "summary": ext_res["document_summary"],
                            "items_count": ext_res["items_count"],
                            "engine_used": ext_res["engine_used"],
                            "model_used": ext_res["model_used"],
                        },
                        status="ok",
                        numeric_value=float(ext_res["items_count"]),
                    )
                    for item in ext_res["items"]:
                        extra_d = dict(item.get("extra_fields") or {})
                        extra_d.setdefault("source_document", ext_res["filename"])
                        extra_d["ingestion_source"] = "event_bus_email"
                        extra_d["doc_record_id"] = doc_rec_id
                        if default_rec and default_rec != "none":
                            extra_d.setdefault("recurrence", default_rec)
                        db.add_custom_agent_record(
                            agent_id=agent_id,
                            title=str(item.get("title") or ext_res["filename"])[:160],
                            record_type="entry",
                            data=extra_d,
                            status="ok",
                            due_date=str(item.get("due_date") or ""),
                            numeric_value=float(item.get("numeric_value") or 0.0),
                        )
                        total_committed_items += 1
                    ingested_files.append({
                        "filename": ext_res["filename"],
                        "items_count": ext_res["items_count"],
                        "detected_scenario": ext_res["detected_scenario"],
                        "doc_record_id": doc_rec_id,
                    })
            except Exception as exc:
                logger.debug("EventBus email payload ingestion skipped: %s", exc)

    rel_inbox = f"fleet/data/user/inbox/{inbox_dir.name}"
    return {
        "status": "ok",
        "inbox_path": rel_inbox,
        "ingested_documents_count": len(ingested_files),
        "committed_items_count": total_committed_items,
        "skipped_duplicates": skipped_duplicates,
        "ingested_files": ingested_files,
    }


# ---------------------------------------------------------------------------
# 4. Smart Recurring Cycle & 1-Click Renewal Roll-Forward Engine
# ---------------------------------------------------------------------------

def _add_months(src_date: date, months: int) -> date:
    month_idx = src_date.month - 1 + months
    year = src_date.year + month_idx // 12
    month = month_idx % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(src_date.day, max_day))


def infer_recurrence_cycle(entry: Dict[str, Any], default_recurrence: str = "none") -> str:
    """Infers the most natural recurrence cycle ('annual', 'quarterly', 'monthly') for a record."""
    raw_edata = entry.get("data")
    edata: Dict[str, Any] = raw_edata if isinstance(raw_edata, dict) else {}
    explicit = str(edata.get("recurrence") or "").strip().lower()
    if explicit in SUPPORTED_RECURRENCE_CYCLES and explicit != "none":
        return explicit
    if default_recurrence in SUPPORTED_RECURRENCE_CYCLES and default_recurrence != "none":
        return default_recurrence

    haystack = f"{entry.get('title', '')} {json.dumps(edata)}".lower()
    if any(w in haystack for w in ("monthly", "rent", "emi", "electricity", "broadband", "internet", "sip")):
        return "monthly"
    if any(w in haystack for w in ("quarter", "quarterly", "hba1c", "biomarker", "advance tax")):
        return "quarterly"
    return "annual"


def roll_forward_custom_agent_record(
    db: Any,
    agent_id: str,
    record_id: int,
    cycle: str = "",
    next_due_date: str = "",
    new_numeric_value: Optional[float] = None,
    default_recurrence: str = "none",
) -> Dict[str, Any]:
    """
    Phase 6 Smart Renewal Roll-Forward:
    1. Archives the completed/paid cycle into `record_type="cycle_history"` so multi-cycle
       spend/metric trends are preserved in SQLite and charted by `sparkline_chart`.
    2. Advances the entry's `due_date` forward by the selected cycle (`monthly`, `quarterly`,
       `semi_annual`, `annual`, or explicit `next_due_date`) and resets `status="ok"`.
    """
    entries = db.list_custom_agent_records(agent_id, record_type="entry", limit=200)
    target = next((e for e in entries if int(e.get("id") or 0) == int(record_id)), None)
    if not target:
        raise ValueError(f"Record #{record_id} not found in agent '{agent_id}'.")

    eff_cycle = str(cycle or "").strip().lower()
    if eff_cycle not in SUPPORTED_RECURRENCE_CYCLES or eff_cycle == "none":
        eff_cycle = infer_recurrence_cycle(target, default_recurrence=default_recurrence)

    old_due_str = str(target.get("due_date") or "").strip()
    today = date.today()
    base_dt = today
    if old_due_str:
        try:
            base_dt = date.fromisoformat(old_due_str[:10])
        except ValueError:
            base_dt = today

    if next_due_date and normalize_extracted_date(next_due_date):
        computed_next_iso = normalize_extracted_date(next_due_date)
    else:
        months = int(SUPPORTED_RECURRENCE_CYCLES.get(eff_cycle, SUPPORTED_RECURRENCE_CYCLES["annual"])["months"] or 12)
        next_dt = _add_months(base_dt, months)
        # If the record was more than 1 cycle overdue, ensure next_dt lands in the future
        while next_dt <= today and months > 0:
            next_dt = _add_months(next_dt, months)
        computed_next_iso = next_dt.isoformat()

    old_val = float(target.get("numeric_value") or 0.0)
    updated_val = float(new_numeric_value) if new_numeric_value is not None else old_val

    curr_data = dict(target.get("data")) if isinstance(target.get("data"), dict) else {}
    renewal_count = int(curr_data.get("renewal_count") or 0) + 1
    curr_data["recurrence"] = eff_cycle
    curr_data["renewal_count"] = renewal_count
    curr_data["previous_due_date"] = old_due_str or today.isoformat()
    curr_data["last_renewed_at"] = today.isoformat()

    # 1. Log historical paid/completed cycle record
    hist_id = db.add_custom_agent_record(
        agent_id=agent_id,
        title=f"Renewed: {target.get('title')} ({old_due_str or 'cycle'} -> {computed_next_iso})",
        record_type="cycle_history",
        data={
            "source_record_id": int(record_id),
            "item_title": target.get("title"),
            "cycle": eff_cycle,
            "previous_due_date": old_due_str,
            "next_due_date": computed_next_iso,
            "paid_value": old_val or updated_val,
            "renewal_number": renewal_count,
        },
        status="ok",
        due_date=old_due_str or today.isoformat(),
        numeric_value=old_val or updated_val,
    )

    # 2. Roll active record forward to new cycle date
    db.update_custom_agent_record(
        agent_id=agent_id,
        record_id=int(record_id),
        due_date=computed_next_iso,
        numeric_value=updated_val,
        status="ok",
        data=curr_data,
    )

    return {
        "record_id": int(record_id),
        "history_record_id": hist_id,
        "title": target.get("title"),
        "cycle": eff_cycle,
        "previous_due_date": old_due_str,
        "next_due_date": computed_next_iso,
        "numeric_value": updated_val,
        "renewal_count": renewal_count,
    }


# ---------------------------------------------------------------------------
# 5. Outbound Action Hooks Executor (`When Alert -> Auto-Action`)
# ---------------------------------------------------------------------------

def execute_outbound_action_hooks(
    agent: Any,
    db: Any,
    run_status: str,
    summary_message: str,
    entries: List[Dict[str, Any]],
    overdue_items: List[str],
    due_soon_items: List[str],
) -> Dict[str, Any]:
    """
    Executes configured Phase 6 outbound action hooks (`auto_create_task`,
    `desktop_toast`, `markdown_report`, `emit_followup_event`) safely and idempotently.
    """
    meta = getattr(agent, "manifest_meta", {}) or {}
    actions = meta.get("outbound_actions") if isinstance(meta.get("outbound_actions"), list) else []
    if not actions:
        return {"executed": []}

    perms = set(getattr(agent, "permissions", []) or [])
    executed: List[str] = []
    created_task_ids: List[int] = []
    report_rel_path = ""

    urgent_labels = overdue_items + due_soon_items

    # 1. Auto-Create Priority Fleet Task (deduplicated against open pending tasks)
    if "auto_create_task" in actions and urgent_labels and db is not None and "db:write" in perms:
        try:
            existing_pending = db.list_tasks(status="pending", limit=100, require_description=False)
            existing_titles = {str(t.get("title") or "").strip().lower() for t in existing_pending}
            for u_label in urgent_labels[:5]:
                task_title = f"[{agent.display_name}] Action Required: {u_label}"[:140]
                if task_title.lower() in existing_titles:
                    continue
                prio = "P1" if "overdue" in u_label.lower() else "P2"
                tid = db.add_task(
                    title=task_title,
                    description=f"Auto-created by custom Studio agent '{agent.display_name}' ({agent.id}). Summary: {summary_message}",
                    priority=prio,
                    due_date=date.today().isoformat(),
                    assigned_agent=agent.id,
                    source=f"StudioAgent:{agent.id}",
                )
                if tid and tid > 0:
                    created_task_ids.append(tid)
                    existing_titles.add(task_title.lower())
            if created_task_ids:
                executed.append(f"auto_create_task({len(created_task_ids)})")
        except Exception as exc:
            logger.debug("Outbound auto_create_task skipped for %s: %s", agent.id, exc)

    # 2. Desktop Toast Notification on Warning
    if "desktop_toast" in actions and run_status == "warning":
        try:
            enabled_notif = bool(agent.get_setting("enabled_notifications", True))
            if enabled_notif:
                from fleet.tools.system_tools import send_notification
                send_notification(
                    f"{agent.display_icon} {agent.display_name} Alert",
                    summary_message[:180],
                )
                executed.append("desktop_toast")
        except Exception as exc:
            logger.debug("Outbound desktop_toast skipped for %s: %s", agent.id, exc)

    # 3. Markdown Digest Report in `DATA_DIR / "user" / "reports"`
    if "markdown_report" in actions:
        try:
            clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", agent.id)
            reports_dir = (DATA_DIR / "user" / "reports").resolve()
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / f"{clean_agent}_latest.md"
            total_val = round(sum(float(e.get("numeric_value") or 0.0) for e in entries), 2)
            md_lines = [
                f"# {agent.display_icon} {agent.display_name} — Automated Digest Report",
                f"- **Agent ID**: `{agent.id}`",
                f"- **Generated At**: `{datetime.now().isoformat(timespec='seconds')}`",
                f"- **Health Status**: `{run_status.upper()}`",
                f"- **Executive Summary**: {summary_message}",
                f"- **Tracked Entries**: `{len(entries)}` (Total Numeric Value: `{total_val:,.2f}`)",
                "",
                "## Active Tracked Records",
            ]
            if not entries:
                md_lines.append("_No tracked entries yet._")
            else:
                for e in entries[:30]:
                    due_s = f" | Due: `{e.get('due_date')}`" if e.get("due_date") else ""
                    val_s = f" | Value: `{float(e.get('numeric_value') or 0):,.2f}`" if e.get("numeric_value") else ""
                    md_lines.append(f"- **{e.get('title')}** (`{e.get('status', 'ok')}`){due_s}{val_s}")
            report_file.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
            report_rel_path = f"fleet/data/user/reports/{clean_agent}_latest.md"
            executed.append("markdown_report")
        except Exception as exc:
            logger.debug("Outbound markdown_report skipped for %s: %s", agent.id, exc)

    # 4. Follow-Up Inter-Agent EventBus Signal
    if "emit_followup_event" in actions and "event_bus:publish" in perms:
        event_bus = getattr(agent, "event_bus", None)
        if event_bus is not None:
            try:
                event_bus.publish(
                    "studio.followup_requested",
                    {
                        "agent_id": agent.id,
                        "name": agent.display_name,
                        "status": run_status,
                        "message": summary_message,
                        "urgent_count": len(urgent_labels),
                    },
                )
                executed.append("emit_followup_event")
            except Exception:
                pass

    return {
        "executed": executed,
        "created_task_ids": created_task_ids,
        "report_path": report_rel_path,
    }


# ---------------------------------------------------------------------------
# 6. Grounded In-Agent Q&A & Natural-Language Mutation Engine (`agent_chat`)
# ---------------------------------------------------------------------------

_CHAT_STOP_WORDS: set[str] = {
    "a", "an", "and", "any", "are", "as", "at", "be", "been", "by", "can", "could",
    "did", "do", "does", "for", "from", "give", "had", "has", "have", "how", "i",
    "if", "in", "into", "is", "it", "its", "list", "many", "me", "much", "my", "of",
    "on", "or", "our", "please", "show", "tell", "that", "the", "their", "them",
    "there", "these", "this", "to", "us", "was", "we", "were", "what", "when",
    "where", "which", "who", "will", "with", "would", "your",
}

_META_KEY_LABELS: Dict[str, str] = {
    "policy_number": "Policy #",
    "policy_reg_no": "Policy/Reg #",
    "policy_no": "Policy #",
    "reference_no": "Ref #",
    "invoice_number": "Invoice/Ref #",
    "reference_code": "Ref #",
    "insurer": "Insurer",
    "insurer_provider": "Insurer",
    "provider_name": "Provider",
    "counterparty": "Provider",
    "asset": "Asset",
    "vehicle_reg": "Asset",
    "recurrence": "Cycle",
    "reference_range": "Ref Range",
    "reference_note": "Ref Note",
    "renewal_count": "Renewals",
}

_INTERNAL_META_KEYS: set[str] = {
    "source_document",
    "doc_record_id",
    "scenario",
    "ingestion_source",
    "created_via",
    "sha256",
    "vault_rel_path",
    "previous_due_date",
    "last_renewed_at",
}

_BOILERPLATE_DOC_PHRASES: Tuple[str, ...] = (
    "your car insurance policy",
    "your bike insurance policy",
    "your two-wheeler insurance policy",
    "document is here",
    "page 1 of",
    "digitally signed",
)


def _clean_vault_filename(raw_name: str) -> str:
    """Strips internal vault timestamp/SHA prefixes (`YYYYMMDD_HHMMSS_<hash>_`) for human-friendly citations."""
    name = str(raw_name or "").strip()
    name = re.sub(r"^\d{8}_\d{6}_[0-9a-fA-F]{6,16}_", "", name)
    name = re.sub(r"^dup_[0-9a-fA-F]{6,16}_", "", name)
    return name or "document"


def _token_matches_text(token: str, haystack_lower: str) -> bool:
    """Matches query tokens on word boundaries so short tokens never match unrelated substrings."""
    if not token or not haystack_lower:
        return False
    if len(token) <= 3:
        return bool(re.search(rf"\b{re.escape(token)}\b", haystack_lower))
    return bool(re.search(rf"\b{re.escape(token)}", haystack_lower))


def _extract_query_tokens(message: str) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for tok in re.findall(r"[a-z0-9]{2,}", str(message or "").lower()):
        if tok in _CHAT_STOP_WORDS or tok in seen:
            continue
        seen.add(tok)
        ordered.append(tok)
    return ordered


def _format_clean_record_meta(
    data_obj: Any,
    title_text: str = "",
    max_pairs: int = 4,
) -> List[str]:
    """
    Formats record metadata into concise, deduplicated human-readable badges,
    omitting duplicate alias values (e.g. policy_number == invoice_number == reference_code)
    and values already visible in the record's title.
    """
    if not isinstance(data_obj, dict):
        return []
    title_norm = re.sub(r"\s+", " ", str(title_text or "").strip().lower())
    seen_values: set[str] = set()
    badges: List[str] = []

    priority_order = [
        "policy_number", "policy_reg_no", "policy_no", "invoice_number",
        "reference_no", "reference_code", "asset", "insurer", "insurer_provider",
        "provider_name", "counterparty", "reference_range", "reference_note", "recurrence",
    ]
    ordered_keys = [k for k in priority_order if k in data_obj] + [
        k for k in data_obj.keys() if k not in priority_order
    ]

    for key in ordered_keys:
        if key in _INTERNAL_META_KEYS:
            continue
        raw_val = data_obj.get(key)
        if raw_val is None:
            continue
        val_str = str(raw_val).strip()
        if not val_str:
            continue
        val_norm = re.sub(r"\s+", " ", val_str.lower())
        if val_norm in seen_values:
            continue
        # Skip repeating insurer/asset/provider values that are already in the record title
        if len(val_norm) >= 4 and val_norm in title_norm and key in {
            "insurer", "insurer_provider", "provider_name", "counterparty", "asset", "vehicle_reg",
        }:
            seen_values.add(val_norm)
            continue
        seen_values.add(val_norm)
        label = _META_KEY_LABELS.get(key) or key.replace("_", " ").strip().title()
        if key in {"policy_number", "policy_reg_no", "policy_no", "invoice_number", "reference_no", "reference_code", "asset"}:
            badges.append(f"{label}: `{val_str}`")
        elif key == "recurrence":
            badges.append(f"{label}: {val_str.replace('_', '-').title()}")
        else:
            badges.append(f"{label}: {val_str}")
        if len(badges) >= max_pairs:
            break

    return badges


def _format_entry_markdown_bullet(entry: Dict[str, Any]) -> str:
    """Formats a single SQLite entry into a clean, scannable Markdown bullet line."""
    title = str(entry.get("title") or "Untitled Record").strip()
    segments: List[str] = [f"**{title}**"]

    due_val = str(entry.get("due_date") or "").strip()
    if due_val:
        segments.append(f"Due `{due_val}`")

    num_raw = entry.get("numeric_value")
    try:
        num_f = float(num_raw or 0.0)
    except (TypeError, ValueError):
        num_f = 0.0
    if num_f > 0:
        segments.append(f"**{num_f:,.2f}**")

    status_val = str(entry.get("status") or "ok").strip().lower()
    if status_val in {"completed", "done", "resolved"}:
        segments.append("Status: `Completed`")

    meta_badges = _format_clean_record_meta(entry.get("data"), title_text=title, max_pairs=4)
    if meta_badges:
        segments.extend(meta_badges)

    if len(segments) == 1:
        return f"- {segments[0]}"
    return f"- {segments[0]} — " + " • ".join(segments[1:])


def _load_vaulted_doc_snippets(
    agent_id: str,
    docs: List[Dict[str, Any]],
    query: str = "",
    max_chars: int = 24000,
) -> List[Tuple[str, str]]:
    """
    Loads extracted text from the agent's vaulted documents in `DATA_DIR / user / agent_docs`.
    When `query` is provided, scans the full extracted text of each vaulted document so
    clauses on later pages (e.g., Engine Protect, Add-Ons, IDV, Exclusions) are retrieved.
    """
    snippets: List[Tuple[str, str]] = []
    clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", agent_id)
    vault_dir = DATA_DIR / "user" / "agent_docs" / clean_agent
    used_chars = 0
    q_tokens = _extract_query_tokens(query)

    if vault_dir.is_dir():
        files = sorted([p for p in vault_dir.iterdir() if p.is_file()], key=lambda p: p.name, reverse=True)
        per_file_budget = max(2400, max_chars // max(1, min(len(files), 10)))
        for fp in files[:10]:
            if used_chars >= max_chars:
                break
            try:
                parsed = parse_uploaded_document(filename=fp.name, content_bytes=fp.read_bytes())
                txt = (parsed.get("extracted_text") or "").strip()
                if not txt:
                    continue
                display_name = _clean_vault_filename(fp.name)
                budget = min(per_file_budget, max_chars - used_chars)
                if len(txt) <= budget or not q_tokens:
                    chunk = txt[:budget]
                else:
                    # Preserve top header + highest-scoring query windows across the full PDF
                    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                    header_block = "\n".join(lines[:18])[: min(900, budget // 2)]
                    scored_indices: List[Tuple[int, int]] = []
                    for idx, ln in enumerate(lines):
                        low_ln = ln.lower()
                        hits = sum(1 for t in q_tokens if _token_matches_text(t, low_ln))
                        if hits > 0:
                            scored_indices.append((hits, idx))
                    scored_indices.sort(key=lambda pair: (-pair[0], pair[1]))
                    picked_line_idxs: set[int] = set()
                    window_lines: List[str] = []
                    rem_budget = max(400, budget - len(header_block) - 20)
                    curr_len = 0
                    for _hits, center_idx in scored_indices[:16]:
                        for neighbor in range(max(0, center_idx - 1), min(len(lines), center_idx + 2)):
                            if neighbor in picked_line_idxs:
                                continue
                            cand_line = lines[neighbor]
                            if curr_len + len(cand_line) + 1 > rem_budget:
                                break
                            picked_line_idxs.add(neighbor)
                            window_lines.append(cand_line)
                            curr_len += len(cand_line) + 1
                    chunk = (header_block + ("\n...\n" + "\n".join(window_lines) if window_lines else ""))[:budget]
                snippets.append((display_name, chunk))
                used_chars += len(chunk)
            except Exception:
                continue

    # Also include stored document summaries from SQLite
    seen_summary_docs = {fn.lower() for fn, _ in snippets}
    for d in docs[:10]:
        raw_dm = d.get("data")
        dm: Dict[str, Any] = raw_dm if isinstance(raw_dm, dict) else {}
        summary_txt = str(dm.get("summary") or "").strip()
        if summary_txt:
            clean_doc_title = _clean_vault_filename(str(d.get("title") or dm.get("filename") or "document"))
            tag = f"{clean_doc_title} (summary)" if clean_doc_title.lower() in seen_summary_docs else clean_doc_title
            snippets.append((tag, f"Summary: {summary_txt}"))

    return snippets


def _try_natural_language_mutation(
    agent_id: str,
    db: Any,
    message: str,
    entries: List[Dict[str, Any]],
    default_recurrence: str = "none",
) -> Optional[Dict[str, Any]]:
    """
    Handles direct natural-language commands inside `agent_chat`:
    - "add <title> due <YYYY-MM-DD> for <amount>"
    - "mark <item> completed" / "complete <item>"
    - "renew <item> [monthly|quarterly|annual] [until YYYY-MM-DD] [for <amount>]"
    """
    if db is None:
        return None
    msg = message.strip()
    low = msg.lower()

    # 1. Natural-language ADD command
    m_add = re.match(r"^(?:add|track|log|create)\s+(.+)$", msg, flags=re.I)
    if m_add and not low.endswith("?"):
        rest = m_add.group(1).strip()
        due_iso = ""
        m_date = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", rest)
        if m_date:
            due_iso = normalize_extracted_date(m_date.group(1))
            rest = (rest[: m_date.start()] + " " + rest[m_date.end() :]).strip()

        num_val = 0.0
        m_amt = re.search(r"(?:for|at|amount|rs\.?|inr|usd|\$|₹)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", rest, flags=re.I)
        if m_amt:
            num_val = normalize_extracted_number(m_amt.group(1))
            rest = (rest[: m_amt.start()] + " " + rest[m_amt.end() :]).strip()

        clean_title = re.sub(r"\b(?:due|on|by|expiring)\s*$", "", rest, flags=re.I).strip(" -:,.")
        if clean_title:
            extra_d = {"created_via": "agent_chat"}
            if default_recurrence and default_recurrence != "none":
                extra_d["recurrence"] = default_recurrence
            rec_id = db.add_custom_agent_record(
                agent_id=agent_id,
                title=clean_title[:160],
                record_type="entry",
                data=extra_d,
                status="ok",
                due_date=due_iso,
                numeric_value=num_val,
            )
            details = [f"Added **{clean_title}** (#{rec_id}) to SQLite."]
            if due_iso:
                details.append(f"Target date: `{due_iso}`.")
            if num_val:
                details.append(f"Value: `{num_val:,.2f}`.")
            return {"mutation": "add", "record_id": rec_id, "answer": " ".join(details)}

    # 2. Natural-language RENEW / ROLL FORWARD command
    m_ren = re.match(r"^(?:renew|roll\s*forward|mark\s+renewed)\s+(.+)$", msg, flags=re.I)
    if m_ren and entries:
        body_txt = m_ren.group(1).strip()
        explicit_cycle = ""
        for cyc in ("monthly", "quarterly", "semi_annual", "annual"):
            if cyc.replace("_", "-") in body_txt.lower() or cyc in body_txt.lower():
                explicit_cycle = cyc
                break
        next_due = ""
        m_date = re.search(r"(?:until|to|due)?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})", body_txt, flags=re.I)
        if m_date:
            next_due = normalize_extracted_date(m_date.group(1))
        new_amt: Optional[float] = None
        m_amt = re.search(r"(?:for|at|amount|rs\.?|inr|usd|\$|₹)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", body_txt, flags=re.I)
        if m_amt:
            new_amt = normalize_extracted_number(m_amt.group(1))

        best_entry = next(
            (e for e in entries if any(tok in str(e.get("title") or "").lower() for tok in re.findall(r"[a-z0-9]{3,}", body_txt.lower()))),
            entries[0],
        )
        rolled = roll_forward_custom_agent_record(
            db=db,
            agent_id=agent_id,
            record_id=int(best_entry["id"]),
            cycle=explicit_cycle,
            next_due_date=next_due,
            new_numeric_value=new_amt,
            default_recurrence=default_recurrence,
        )
        return {
            "mutation": "renew",
            "record_id": rolled["record_id"],
            "answer": (
                f"Rolled **{rolled['title']}** forward ({rolled['cycle']} cycle #{rolled['renewal_count']}): "
                f"`{rolled['previous_due_date'] or 'today'}` -> **`{rolled['next_due_date']}`**"
                + (f" at `{rolled['numeric_value']:,.2f}`." if rolled["numeric_value"] else ".")
            ),
        }

    # 3. Natural-language COMPLETE / DONE command
    m_done = re.match(r"^(?:complete|finish|resolve|mark)\s+(.+?)(?:\s+(?:done|completed|resolved))?$", msg, flags=re.I)
    if m_done and entries and ("complete" in low or "done" in low or "resolve" in low) and not low.endswith("?"):
        target_kw = m_done.group(1).strip().lower()
        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", target_kw) if t not in ("mark", "item", "the", "done", "completed")]
        matched = next(
            (e for e in entries if any(t in str(e.get("title") or "").lower() for t in tokens)),
            None,
        )
        if matched:
            db.update_custom_agent_record(agent_id=agent_id, record_id=int(matched["id"]), status="completed")
            return {
                "mutation": "complete",
                "record_id": int(matched["id"]),
                "answer": f"Marked **{matched.get('title')}** (#{matched['id']}) as **completed**.",
            }

    return None


def answer_custom_agent_chat(
    agent: Any,
    db: Any,
    message: str,
) -> Dict[str, Any]:
    """
    Phase 6 Grounded In-Agent Q&A & Command Engine (`agent_chat`):
    1. Executes direct natural-language mutations (`add ...`, `renew ...`, `complete ...`) immediately.
    2. Otherwise answers questions grounded strictly on the agent's SQLite records, countdowns,
       cycle history, AND extracted text from vaulted documents (`fleet/data/user/agent_docs/<id>/`).
    3. Uses `agent.complete_prompt()` when LLM/Hybrid mode is active, with an accurate $0.00
       deterministic grounded search & aggregation fallback.
    """
    clean_msg = (message or "").strip()
    if not clean_msg:
        raise ValueError("Chat message cannot be empty.")

    meta = getattr(agent, "manifest_meta", {}) or {}
    agent_id = agent.id
    default_rec = str(meta.get("default_recurrence") or "none").strip().lower()
    intelligence_mode = str(meta.get("intelligence_mode") or getattr(agent, "intelligence_mode", "hybrid") or "hybrid")

    state = db.get_custom_agent_dashboard_state(agent_id, manifest=agent.get_ui_manifest()) if db is not None else {}
    entries = state.get("entries") or []
    countdowns = state.get("countdowns") or []
    docs = state.get("documents") or []

    # Step 1: Check for direct NL mutation command
    mut_res = _try_natural_language_mutation(
        agent_id=agent_id,
        db=db,
        message=clean_msg,
        entries=entries,
        default_recurrence=default_rec,
    )
    if mut_res:
        if db is not None:
            db.add_custom_agent_record(
                agent_id=agent_id,
                title=clean_msg[:120],
                record_type="chat",
                data={"question": clean_msg, "answer": mut_res["answer"], "mutation": mut_res["mutation"], "engine": "deterministic-command"},
                status="ok",
            )
        new_state = db.get_custom_agent_dashboard_state(agent_id, manifest=agent.get_ui_manifest()) if db is not None else state
        return {
            "status": "success",
            "question": clean_msg,
            "answer": mut_res["answer"],
            "mutation": mut_res["mutation"],
            "used_llm": False,
            "engine": "deterministic-command",
            "state": new_state,
        }

    # Step 2: Assemble grounded context from SQLite records + vaulted documents
    doc_snippets = _load_vaulted_doc_snippets(agent_id, docs, query=clean_msg)
    entries_ctx = "\n".join(
        f"- [#{e.get('id')}] {e.get('title')} | status={e.get('status')} | due={e.get('due_date') or 'n/a'} | value={e.get('numeric_value') or 0} | meta={json.dumps(e.get('data') or {})}"
        for e in entries[:30]
    ) or "(No tracked entries yet)"
    docs_ctx = "\n\n".join(f"[Document: {fn}]\n{txt}" for fn, txt in doc_snippets[:8]) or "(No vaulted documents yet)"

    answer_txt = ""
    used_llm = False
    engine_label = "deterministic-rag-$0.00"

    if intelligence_mode != "deterministic":
        rag_prompt = (
            f"You are {agent.display_name} ({agent.display_icon}), answering a user question strictly grounded on "
            "this agent's tracked SQLite records and uploaded documents.\n\n"
            f"Today's Date: {date.today().isoformat()}\n"
            f"Tracked SQLite Entries:\n{entries_ctx}\n\n"
            f"Vaulted Document Excerpts:\n{docs_ctx}\n\n"
            f"User Question: {clean_msg}\n\n"
            "Formatting & Grounding Rules:\n"
            "1. Start with a direct 1-2 sentence answer to the user's question.\n"
            "2. Present supporting records or policy/document clauses as a clean Markdown bullet list (`- **Item** — details`).\n"
            "3. Bold important figures/statuses and wrap policy numbers, dates, or filenames in backticks.\n"
            "4. Never output a single long run-on paragraph or repeat duplicate metadata fields. If a specific clause is not present in the excerpts, state that clearly."
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
                agent.complete_prompt(rag_prompt, provider=eff_prov, model=eff_mdl)
                if (eff_prov or eff_mdl)
                else agent.complete_prompt(rag_prompt)
            )
            cand = ""
            resp_status = ""
            resp_model = ""
            if isinstance(llm_resp, dict):
                resp_status = str(llm_resp.get("status") or "").upper()
                resp_model = str(llm_resp.get("model") or "").strip()
                cand = str(llm_resp.get("text") or llm_resp.get("response") or "").strip()
            elif isinstance(llm_resp, str):
                cand = llm_resp.strip()
            if (
                cand
                and resp_status != "FALLBACK"
                and not cand.startswith("Fleet Autonomous Intelligence: Processed prompt")
            ):
                answer_txt = cand
                used_llm = True
                engine_label = resp_model or eff_mdl or str(getattr(agent, "preferred_model", "") or "antigravity-llm")
        except Exception as exc:
            logger.debug("Grounded agent chat fell back to deterministic RAG: %s", exc)

    # Step 3: High-precision, cleanly structured $0.00 deterministic RAG fallback
    if not answer_txt:
        q_tokens = _extract_query_tokens(clean_msg)
        entry_blobs = [
            (e, f"{e.get('title', '')} {json.dumps(e.get('data') or {})}".lower())
            for e in entries
        ]

        # Separate discriminating query terms from agent-wide generic words (e.g. "policy", "insurance")
        specific_tokens: List[str] = []
        if q_tokens:
            threshold = max(2, int(len(entry_blobs) * 0.75)) if len(entry_blobs) >= 3 else len(entry_blobs) + 1
            for tok in q_tokens:
                doc_freq = sum(1 for _e, blob in entry_blobs if _token_matches_text(tok, blob))
                if doc_freq < threshold:
                    specific_tokens.append(tok)

        active_search_tokens = specific_tokens or q_tokens

        scored_entries: List[Tuple[int, Dict[str, Any]]] = []
        if q_tokens:
            for e, blob in entry_blobs:
                spec_hits = sum(3 for t in specific_tokens if _token_matches_text(t, blob))
                gen_hits = sum(1 for t in q_tokens if _token_matches_text(t, blob))
                total_score = spec_hits + gen_hits
                if total_score > 0:
                    scored_entries.append((total_score, e))
            scored_entries.sort(key=lambda pair: -pair[0])
            matched_entries = [pair[1] for pair in scored_entries]
        else:
            matched_entries = list(entries[:5])

        scored_doc_hits: List[Tuple[int, str, str]] = []
        seen_doc_excerpts: set[str] = set()
        specific_doc_hit_count = 0
        if q_tokens and doc_snippets:
            for fn, chunk in doc_snippets:
                clean_fn = _clean_vault_filename(fn)
                for line in chunk.splitlines():
                    l_clean = re.sub(r"\s+", " ", line.strip())
                    if len(l_clean) <= 4 or l_clean == "...":
                        continue
                    low_line = l_clean.lower()
                    if any(bp == low_line or low_line.startswith(bp) for bp in _BOILERPLATE_DOC_PHRASES):
                        continue
                    spec_hits = sum(3 for t in specific_tokens if _token_matches_text(t, low_line))
                    gen_hits = sum(1 for t in q_tokens if _token_matches_text(t, low_line))
                    if specific_tokens and spec_hits == 0:
                        continue
                    line_score = spec_hits + gen_hits
                    if line_score <= 0:
                        continue
                    dedup_sig = f"{clean_fn.lower()}::{low_line[:110]}"
                    if dedup_sig in seen_doc_excerpts:
                        continue
                    seen_doc_excerpts.add(dedup_sig)
                    if spec_hits > 0:
                        specific_doc_hit_count += 1
                    scored_doc_hits.append((line_score, clean_fn, l_clean[:220]))
            scored_doc_hits.sort(key=lambda item: -item[0])

        total_active_val = round(
            sum(
                float(e.get("numeric_value") or 0.0)
                for e in entries
                if str(e.get("status", "ok")).lower() not in ("completed", "done", "resolved")
            ),
            2,
        )
        asks_totals_or_due = any(
            w in clean_msg.lower()
            for w in ("total", "sum", "spend", "cost", "premium", "amount", "due", "soon", "expir", "upcoming", "summary", "highlight")
        )

        sections: List[str] = []

        # 1. Direct answer callout if user asked about specific clause/terms not found in vaulted docs
        if specific_tokens and (docs or doc_snippets) and specific_doc_hit_count == 0 and not asks_totals_or_due:
            terms_disp = ", ".join(f"`{t}`" for t in specific_tokens[:4])
            doc_cnt = max(len(docs), len(doc_snippets))
            sections.append(
                f"> No explicit mention of {terms_disp} was found in the extracted text of your **{doc_cnt}** vaulted document(s)."
            )

        # 2. Grounded Document Excerpts (clean bullet list, clean filenames)
        if scored_doc_hits:
            doc_bullets = [
                f"- **`{fn}`** — {excerpt}"
                for _sc, fn, excerpt in scored_doc_hits[:5]
            ]
            sections.append("### 📄 Vaulted Document Findings\n" + "\n".join(doc_bullets))

        # 3. Matching Tracked SQLite Records (clean deduplicated bullets, 1 per line)
        if matched_entries:
            shown = matched_entries[:6]
            more_count = len(matched_entries) - len(shown)
            header_lbl = (
                f"### 📋 Matching Tracked Records ({len(matched_entries)})"
                if active_search_tokens
                else f"### 📋 Tracked Records ({len(entries)})"
            )
            entry_bullets = [_format_entry_markdown_bullet(e) for e in shown]
            if more_count > 0:
                entry_bullets.append(f"- _...and **{more_count}** more tracked record(s)._")
            sections.append(header_lbl + "\n" + "\n".join(entry_bullets))
        elif entries:
            soonest = countdowns[0] if countdowns else None
            summary_bullets = [
                f"- **Active Portfolio**: **{len(entries)}** tracked item(s) across **{len(docs)}** vaulted document(s)",
                f"- **Active Numeric Total**: **{total_active_val:,.2f}**",
            ]
            if soonest:
                summary_bullets.append(
                    f"- **Next Upcoming Deadline**: **{soonest['title']}** on `{soonest['due_date']}` (`{soonest['days_left']}d` left)"
                )
            sections.append("### 📊 Portfolio Snapshot\n" + "\n".join(summary_bullets))
        elif not scored_doc_hits:
            sections.append(
                "No tracked items yet. Upload a document above or type `add <Item> due YYYY-MM-DD for <Amount>`."
            )

        # 4. Totals & Upcoming Deadline Footer when requested
        if entries and asks_totals_or_due:
            soonest = countdowns[0] if countdowns else None
            due_soon_cnt = sum(
                1 for c in countdowns
                if not c.get("is_completed") and isinstance(c.get("days_left"), int) and c["days_left"] <= 15
            )
            footer_parts = [
                f"**Active Total**: **{total_active_val:,.2f}** across **{len(entries)}** record(s)",
                f"**Due <= 15d**: **{due_soon_cnt}**",
            ]
            if soonest:
                footer_parts.append(f"**Next Due**: `{soonest['due_date']}` ({soonest['days_left']}d)")
            sections.append("> " + " • ".join(footer_parts))

        answer_txt = "\n\n".join(sections)

    if db is not None:
        db.add_custom_agent_record(
            agent_id=agent_id,
            title=clean_msg[:120],
            record_type="chat",
            data={"question": clean_msg, "answer": answer_txt, "engine": engine_label},
            status="ok",
        )
    final_state = db.get_custom_agent_dashboard_state(agent_id, manifest=agent.get_ui_manifest()) if db is not None else state
    return {
        "status": "success",
        "question": clean_msg,
        "answer": answer_txt,
        "mutation": None,
        "used_llm": used_llm,
        "engine": engine_label,
        "state": final_state,
    }

