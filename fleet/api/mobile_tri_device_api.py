"""
Tri-Device Ecosystem REST API Endpoints (Apple Watch • iPhone • Windows Laptop AFCC Hub)
and GitHub Project Governance & Telemetry API.

Implements:
  - TD-02: `POST /api/mobile/health/ingest` (Encrypted Apple Watch & HealthKit ingestion + FFD Readiness Score)
  - TD-03 / TD-11: `GET /api/mobile/shortcuts/template` (iOS Shortcuts & Watch Action Button recipes)
  - TD-08 / TD-09: `POST /api/mobile/payments/deeplink` (1-Tap BHIM / ICICI / GPay / PhonePe UPI deep links + Auto-Close)
  - TD-10: `GET/POST /api/mobile/watch/complication` (Ultra-compact <2KB watchOS Smart Stack Complication snapshot)
  - TD-12: `GET /api/github/projects/tri-device` & `POST /api/github/projects/tri-device/sync`
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

from fleet.api.router import router
from fleet.config import DATA_DIR
from fleet.core.crypto_vault import (
    fpe_encrypt_identifier,
    read_encrypted_json_file,
    write_encrypted_json_file,
)
from fleet.core.database import is_test_environment
import fleet.server as srv


def _get_apple_health_vault_path() -> Path:
    sub_dir = "test_user" if is_test_environment() else "user"
    target = DATA_DIR / sub_dir / "apple_health_sync_vault.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def compute_ffd_workout_readiness(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a deterministic 0-100 FFD & Traditional Strength Workout Readiness Score
    from Apple Watch biometrics (HRV SDNN ms, Sleep hours, Resting HR bpm, SpO2 %).
    """
    score = 85
    reasons: List[str] = []

    sleep_hrs = float(metrics.get("sleep_hours") or 0.0)
    hrv_ms = float(metrics.get("hrv_sdnn_ms") or 0.0)
    rhr_bpm = float(metrics.get("resting_hr_bpm") or 0.0)
    spo2_pct = float(metrics.get("spo2_pct") or 0.0)

    if sleep_hrs > 0:
        if sleep_hrs >= 7.0:
            score += 8
            reasons.append(f"Restorative sleep ({sleep_hrs:.1f}h)")
        elif sleep_hrs < 6.0:
            score -= 20
            reasons.append(f"Short sleep ({sleep_hrs:.1f}h < 6.0h target)")

    if hrv_ms > 0:
        if hrv_ms >= 45:
            score += 7
            reasons.append(f"Strong autonomic recovery (HRV {int(hrv_ms)} ms)")
        elif hrv_ms < 28:
            score -= 18
            reasons.append(f"Low HRV recovery ({int(hrv_ms)} ms)")

    if rhr_bpm > 0:
        if rhr_bpm <= 62:
            score += 4
        elif rhr_bpm >= 78:
            score -= 10
            reasons.append(f"Elevated resting heart rate ({int(rhr_bpm)} bpm)")

    if spo2_pct > 0 and spo2_pct < 95:
        score -= 10
        reasons.append(f"SpO2 below baseline ({spo2_pct:.1f}%)")

    score = max(20, min(100, int(score)))
    if score >= 80:
        tier = "PEAK_STRENGTH"
        recommendation = "Full 6-Day Mudgal / Samtola / Bhim Gadha volume + Mandatory Warm-up & Nitric Oxide Dump."
    elif score >= 60:
        tier = "MODERATE_VOLUME"
        recommendation = "Moderate strength volume (reduce heavy sets by 20%) + full mobility warm-up."
    else:
        tier = "ACTIVE_RECOVERY"
        recommendation = "Prioritize recovery: Mandatory Warm-up, Surya Namaskar, Pranayama & light mobility."

    return {
        "readiness_score": score,
        "readiness_tier": tier,
        "recommendation": recommendation,
        "factors": reasons or ["Baseline readiness nominal"],
    }


@router.post("/api/mobile/health/ingest")
def post_mobile_health_ingest_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-02: Receives Apple Watch & iPhone HealthKit telemetry, logs metrics to SQLite,
    encrypts the snapshot in `apple_health_sync_vault.json` (AES-256-GCM + HKDF-SHA256),
    and returns the FFD Workout Readiness Score.
    """
    payload = body if isinstance(body, dict) else {}
    device_source = str(payload.get("device") or "Apple Watch + iPhone HealthKit").strip()
    raw_metrics = payload.get("metrics")
    metrics: Dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else dict(payload)

    db_inst = getattr(srv, "db", None)
    logged_metrics: List[str] = []

    metric_mapping = (
        ("steps", "steps"),
        ("active_kcal", "kcal"),
        ("resting_hr_bpm", "bpm"),
        ("hrv_sdnn_ms", "ms"),
        ("sleep_hours", "hours"),
        ("spo2_pct", "%"),
        ("fasting_glucose", "mg/dL"),
        ("pp_glucose", "mg/dL"),
        ("weight_kg", "kg"),
    )

    for key, unit in metric_mapping:
        val = metrics.get(key)
        if val is not None:
            try:
                num_val = float(val)
                if db_inst and hasattr(db_inst, "log_health_metric"):
                    db_inst.log_health_metric(key, num_val, unit, f"Synced via {device_source}")
                logged_metrics.append(f"{key}={num_val}{unit}")
            except (ValueError, TypeError):
                pass

    water_ml = metrics.get("water_ml")
    if water_ml is not None:
        try:
            w_int = int(float(water_ml))
            if w_int > 0 and db_inst:
                if hasattr(db_inst, "log_water_intake"):
                    db_inst.log_water_intake(glasses_delta=max(1, round(w_int / 250)), amount_delta_ml=w_int)
                elif hasattr(db_inst, "log_hydration"):
                    db_inst.log_hydration(w_int, "water")
                logged_metrics.append(f"water_ml=+{w_int}ml")
        except (ValueError, TypeError):
            pass

    readiness = compute_ffd_workout_readiness(metrics)

    # Persist encrypted snapshot in local vault (AES-256-GCM + HKDF-SHA256)
    vault_path = _get_apple_health_vault_path()
    raw_vault = read_encrypted_json_file(vault_path, default={"history": []})
    vault_data: Dict[str, Any] = raw_vault if isinstance(raw_vault, dict) else {"history": []}
    raw_hist = vault_data.get("history")
    history: List[Any] = list(raw_hist) if isinstance(raw_hist, list) else []
    snapshot = {
        "synced_at": datetime.now().isoformat(),
        "device_source": device_source,
        "metrics": {k: metrics.get(k) for k, _ in metric_mapping if metrics.get(k) is not None},
        "readiness": readiness,
    }
    history.insert(0, snapshot)
    vault_data["latest"] = snapshot
    vault_data["history"] = history[:90]
    write_encrypted_json_file(vault_path, vault_data)

    if db_inst and hasattr(db_inst, "log_activity"):
        db_inst.log_activity(
            "HealthAgent",
            "apple_watch_sync",
            f"Apple Watch/iPhone sync ({len(logged_metrics)} metrics) • Readiness {readiness['readiness_score']}/100",
        )

    handler._send_json({
        "status": "ok",
        "device_source": device_source,
        "logged_metrics": logged_metrics,
        "logged_count": len(logged_metrics),
        "readiness": readiness,
        "encrypted_at_rest": True,
        "vault_file": f"fleet/data/{'test_user' if is_test_environment() else 'user'}/apple_health_sync_vault.json",
    })


@router.get("/api/mobile/watch/complication")
def get_watch_complication_snapshot_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-10: Ultra-compact (<2 KB, <5ms) watchOS Smart Stack Complication & iOS Lock Screen Widget snapshot.
    """
    db_inst = getattr(srv, "db", None)
    all_tasks = db_inst.list_tasks(limit=100, exclude_tests=True) if (db_inst and hasattr(db_inst, "list_tasks")) else []
    pending_tasks = [t for t in all_tasks if str(t.get("status") or "").lower() != "completed"]
    closed_tasks = [t for t in all_tasks if str(t.get("status") or "").lower() == "completed"]
    top_task = pending_tasks[0] if pending_tasks else None

    hydration = {"amount_ml": 0, "goal_ml": 2500, "glasses": 0, "pct": 0}
    if db_inst and hasattr(db_inst, "get_today_hydration"):
        try:
            h = db_inst.get_today_hydration() or {}
            amt = int(h.get("amount_ml") or 0)
            goal = max(1, int(h.get("goal_ml") or 2500))
            hydration = {
                "amount_ml": amt,
                "goal_ml": goal,
                "glasses": amt // 250,
                "pct": min(100, int(round((amt / goal) * 100))),
            }
        except Exception:
            pass

    vault_data = read_encrypted_json_file(_get_apple_health_vault_path(), default={})
    latest_readiness = (
        vault_data.get("latest", {}).get("readiness", {})
        if isinstance(vault_data, dict)
        else {}
    ) or {"readiness_score": 85, "readiness_tier": "PEAK_STRENGTH"}

    day_map = {
        0: "Mudgal (Indian Clubbells)",
        1: "Core & Mobility Conditioning",
        2: "Samtola (Hindu Barbell)",
        3: "Active Pranayama & FFD Walk",
        4: "Bhim Gadha (Heavy Mace)",
        5: "Full-Body Akhada Circuit",
        6: "Rest & Parasympathetic Recovery",
    }
    today_workout = day_map.get(datetime.now().weekday(), "Mandatory Warm-up & Strength")

    handler._send_json({
        "status": "ok",
        "complication": {
            "wake_word": (db_inst.get_setting("voice_wake_word", "Mahadev") if (db_inst and hasattr(db_inst, "get_setting")) else "Mahadev") or "Mahadev",
            "hydration_pct": hydration["pct"],
            "hydration_label": f"{hydration['glasses']} gl ({hydration['amount_ml']}ml)",
            "today_workout": today_workout,
            "readiness_score": latest_readiness.get("readiness_score", 85),
            "open_action_items": len(pending_tasks),
            "closed_action_items": len(closed_tasks),
            "top_action_item": {
                "id": top_task["id"],
                "title": str(top_task.get("title") or "").replace("Monthly — ", ""),
                "priority": top_task.get("priority", "P1"),
            } if top_task else None,
        },
    })


@router.post("/api/mobile/watch/complication")
def post_watch_complication_quick_action_endpoint(handler: Any, body: Dict[str, Any]):
    """TD-10: Executes a 1-tap Apple Watch complication quick action (+250ml Water or Close Top Action Item)."""
    payload = body if isinstance(body, dict) else {}
    action = str(payload.get("action") or "").strip().lower()
    db_inst = getattr(srv, "db", None)

    if action in ("log_water", "water", "+250ml"):
        ml = int(payload.get("amount_ml") or 250)
        if db_inst:
            if hasattr(db_inst, "log_water_intake"):
                db_inst.log_water_intake(glasses_delta=max(1, round(ml / 250)), amount_delta_ml=ml)
            elif hasattr(db_inst, "log_hydration"):
                db_inst.log_hydration(ml, "water")
        handler._send_json({"status": "ok", "action": "log_water", "logged_ml": ml, "spoken_reply": f"Logged {ml} milliliters of water from Apple Watch."})
        return

    if action in ("close_top_action_item", "close_action_item"):
        tid = payload.get("task_id")
        if db_inst and hasattr(db_inst, "list_tasks") and hasattr(db_inst, "update_task_status"):
            tasks = [t for t in db_inst.list_tasks(limit=100, exclude_tests=True) if t.get("status") != "completed"]
            target = next((t for t in tasks if tid and int(t["id"]) == int(tid)), tasks[0] if tasks else None)
            if target:
                db_inst.update_task_status(int(target["id"]), "completed")
                handler._send_json({
                    "status": "ok",
                    "action": "close_action_item",
                    "closed_task_id": target["id"],
                    "closed_title": target["title"],
                    "spoken_reply": f"Closed action item {target['title']}.",
                })
                return
        handler._send_json({"status": "ok", "action": "close_action_item", "message": "No open action items remaining."})
        return

    handler._send_json({"status": "error", "message": f"Unsupported watch action: {action}"}, status=400)


@router.post("/api/mobile/payments/deeplink")
def post_mobile_payment_deeplink_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-08 & TD-09: Generates RFC-compliant 1-Tap Open Payment Deep Links for iPhone
    (BHIM UPI, ICICI iMobile Pay, Google Pay, PhonePe, Generic UPI) for any Monthly Action Item,
    and optionally marks the Action Item closed (`confirm_paid: True`).
    """
    payload = body if isinstance(body, dict) else {}
    task_id = payload.get("task_id")
    payee_vpa = str(payload.get("vpa") or payload.get("payee_vpa") or "biller@upi").strip()
    payee_name = str(payload.get("payee_name") or payload.get("title") or "Monthly Bill Payment").strip()
    amount = payload.get("amount")
    note = str(payload.get("note") or payee_name).strip()
    preferred_app = str(payload.get("app") or "bhim").strip().lower()
    confirm_paid = bool(payload.get("confirm_paid", False))

    db_inst = getattr(srv, "db", None)
    matched_task: Optional[Dict[str, Any]] = None
    if task_id is not None and db_inst and hasattr(db_inst, "list_tasks"):
        all_tasks = db_inst.list_tasks(limit=200, exclude_tests=True)
        matched_task = next((t for t in all_tasks if int(t.get("id") or 0) == int(task_id)), None)
        if matched_task and payee_name == "Monthly Bill Payment":
            payee_name = str(matched_task.get("title") or payee_name).replace("Monthly — ", "")

    query_params: Dict[str, str] = {
        "pa": payee_vpa,
        "pn": payee_name,
        "tn": note,
        "cu": "INR",
    }
    if amount is not None and str(amount).strip():
        try:
            query_params["am"] = f"{float(amount):.2f}"
        except (ValueError, TypeError):
            pass

    qs = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    deep_links = {
        "bhim": f"bhim://pay?{qs}",
        "icici_imobile": f"imobileapp://upi/pay?{qs}",
        "gpay": f"tez://upi/pay?{qs}",
        "phonepe": f"phonepe://pay?{qs}",
        "upi_generic": f"upi://pay?{qs}",
    }
    selected_uri = deep_links.get(preferred_app, deep_links["bhim"])

    task_closed = False
    if confirm_paid and matched_task and db_inst and hasattr(db_inst, "update_task_status"):
        tid = int(matched_task["id"])
        db_inst.update_task_status(tid, "completed")
        if hasattr(db_inst, "update_task"):
            old_desc = str(matched_task.get("description") or "").strip()
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            db_inst.update_task(tid, description=f"{old_desc} | Paid via {preferred_app.upper()} on {stamp}".strip(" |"))
        task_closed = True

    fpe_token = fpe_encrypt_identifier(payee_vpa)
    if not fpe_token.startswith("FPE:"):
        handle, sep, bank = payee_vpa.partition("@")
        masked_handle = (handle[:2] + "*" * max(2, len(handle) - 2)) if len(handle) > 2 else "***"
        fpe_token = f"FPE:v1:{masked_handle}{sep}{bank}"

    handler._send_json({
        "status": "ok",
        "task_id": matched_task["id"] if matched_task else task_id,
        "payee_name": payee_name,
        "masked_vpa_token": fpe_token,
        "preferred_app": preferred_app,
        "selected_deep_link": selected_uri,
        "deep_links": deep_links,
        "task_closed": task_closed,
    })


@router.get("/api/mobile/shortcuts/template")
def get_mobile_shortcuts_template_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-03 & TD-11: Returns ready-to-import iOS Shortcuts & Apple Watch Action Button recipes."""
    handler._send_json({
        "status": "ok",
        "recipes": [
            {
                "id": "ios_health_auto_sync",
                "name": "AFCC Apple Watch & HealthKit Background Sync",
                "trigger": "iOS Personal Automation (When iPhone connects to Charger or Daily at 07:00 AM)",
                "method": "POST",
                "endpoint": "/api/mobile/health/ingest",
                "sample_payload": {
                    "device": "Apple Watch + iPhone HealthKit",
                    "metrics": {
                        "steps": 8420,
                        "active_kcal": 460,
                        "resting_hr_bpm": 58,
                        "hrv_sdnn_ms": 52,
                        "sleep_hours": 7.4,
                        "spo2_pct": 98,
                        "water_ml": 250,
                    },
                },
            },
            {
                "id": "watch_action_button_mahadev",
                "name": "Apple Watch Action Button — 'Ask Mahadev' Voice Bridge",
                "trigger": "Apple Watch Action Button or Hey Siri 'Ask Mahadev'",
                "method": "POST",
                "endpoint": "/api/voice/converse",
                "sample_payload": {
                    "transcript": "Mahadev, let's talk about my action items",
                    "language": "en",
                    "gender": "female",
                    "accent": "IN",
                },
            },
        ],
    })


@router.get("/api/github/projects/tri-device")
def get_github_tri_device_project_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-12: Returns live Tri-Device GitHub Project telemetry, Milestones, and Deliverable Issues."""
    from fleet.tools.github_project_manager import compute_tri_device_project_status

    handler._send_json(compute_tri_device_project_status())


@router.post("/api/github/projects/tri-device/sync")
def post_github_tri_device_project_sync_endpoint(handler: Any, body: Dict[str, Any]):
    """TD-12: Synchronizes Labels, Milestones, Master Epic, Issues TD-01..TD-12, and Docs/Wiki with GitHub."""
    from fleet.tools.github_project_manager import sync_tri_device_project_to_github

    payload = body if isinstance(body, dict) else {}
    token = str(payload.get("token") or "").strip() or None
    res = sync_tri_device_project_to_github(token=token)
    handler._send_json(res)
