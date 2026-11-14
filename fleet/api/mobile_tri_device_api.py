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
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
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
from fleet.core.session_auth import get_or_create_mobile_bearer_token
import fleet.server as srv


def _discover_network_endpoints(port: int = 7890) -> Dict[str, Any]:
    """Discovers Tailscale WireGuard (`100.64.0.0/10`) and private LAN IPv4 addresses on this workstation."""
    tailscale_ips: List[str] = []
    lan_ips: List[str] = []
    tailscale_net = ipaddress.ip_network("100.64.0.0/10")

    candidate_ips: List[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip_str = str(info[4][0])
            if ip_str not in candidate_ips:
                candidate_ips.append(ip_str)
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("10.255.255.255", 1))
            primary_ip = str(s.getsockname()[0])
            if primary_ip not in candidate_ips:
                candidate_ips.append(primary_ip)
    except Exception:
        pass

    for ip_str in candidate_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_loopback:
                continue
            if ip_obj in tailscale_net:
                tailscale_ips.append(ip_str)
            elif ip_obj.is_private:
                lan_ips.append(ip_str)
        except ValueError:
            continue

    primary_url = (
        f"https://{tailscale_ips[0]}:{port}"
        if tailscale_ips
        else (f"https://{lan_ips[0]}:{port}" if lan_ips else f"https://127.0.0.1:{port}")
    )
    return {
        "tailscale_active": len(tailscale_ips) > 0,
        "tailscale_ips": tailscale_ips,
        "lan_ips": lan_ips,
        "loopback_url": f"https://127.0.0.1:{port}",
        "recommended_mobile_base_url": primary_url,
    }


@router.get("/api/mobile/gateway/status")
def get_mobile_gateway_status_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-01: Returns Phase 1 Mobile Gateway & Tailscale WireGuard Mesh provisioning status,
    Local Root CA fingerprint, and masked 256-bit Mobile Bearer Token metadata.
    """
    net_info = _discover_network_endpoints(port=7890)
    token = get_or_create_mobile_bearer_token(rotate=False)
    masked_token = f"{token[:14]}...{token[-6:]}" if len(token) > 22 else "afcc_mob_***"

    ca_path = DATA_DIR / "certs" / "afcc_root_ca.crt"
    ca_exists = ca_path.is_file()
    ca_sha256 = ""
    if ca_exists:
        try:
            ca_sha256 = hashlib.sha256(ca_path.read_bytes()).hexdigest()[:32]
        except Exception:
            pass

    base_url = net_info["recommended_mobile_base_url"]
    handler._send_json({
        "status": "ok",
        "phase": "Phase 1 — Zero-Store Foundation",
        "deliverable_id": "TD-01",
        "network": net_info,
        "tls": {
            "root_ca_installed_locally": ca_exists,
            "root_ca_download_path": "/api/security/ca.crt",
            "root_ca_download_url": f"{base_url}/api/security/ca.crt",
            "root_ca_sha256_prefix": ca_sha256,
        },
        "auth": {
            "header_name": "X-AFCC-Mobile-Token",
            "masked_bearer_token": masked_token,
            "token_configured": True,
        },
        "pwa": {
            "manifest_url": "/manifest.json",
            "service_worker_url": "/sw.js",
            "standalone_ready": True,
        },
    })


@router.post("/api/mobile/gateway/token")
def post_mobile_gateway_token_endpoint(handler: Any, body: Dict[str, Any]):
    """TD-01: Retrieves or rotates the 256-bit Mobile Bearer Token for iOS Shortcuts & Apple Watch."""
    payload = body if isinstance(body, dict) else {}
    rotate = bool(payload.get("rotate", False))
    token = get_or_create_mobile_bearer_token(rotate=rotate)
    masked_token = f"{token[:14]}...{token[-6:]}" if len(token) > 22 else "afcc_mob_***"
    handler._send_json({
        "status": "ok",
        "rotated": rotate,
        "header_name": "X-AFCC-Mobile-Token",
        "bearer_token": token,
        "masked_bearer_token": masked_token,
    })


@router.get("/api/security/ca.crt")
def get_local_root_ca_certificate_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-01: Serves `afcc_root_ca.crt` so iPhone/iPad Safari or Chrome can install the AFCC Root CA in 1 tap."""
    ca_path = DATA_DIR / "certs" / "afcc_root_ca.crt"
    if not ca_path.is_file():
        try:
            from fleet.core.tls_manager import ensure_local_https_certificates

            ensure_local_https_certificates(DATA_DIR / "certs")
        except Exception:
            pass

    if not ca_path.is_file():
        handler._send_json({"status": "error", "message": "Root CA certificate not found."}, status=404)
        return

    cert_bytes = ca_path.read_bytes()
    if hasattr(handler, "send_response") and hasattr(handler, "wfile"):
        handler.send_response(200)
        handler.send_header("Content-Type", "application/x-x509-ca-cert")
        handler.send_header("Content-Disposition", 'attachment; filename="afcc_root_ca.crt"')
        handler.send_header("Content-Length", str(len(cert_bytes)))
        if hasattr(handler, "_send_security_headers"):
            handler._send_security_headers()
        handler.end_headers()
        handler.wfile.write(cert_bytes)
    else:
        handler._send_json({
            "status": "ok",
            "filename": "afcc_root_ca.crt",
            "pem": cert_bytes.decode("utf-8", errors="ignore"),
        })


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


@router.get("/api/mobile/health/status")
def get_mobile_health_status_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-02: Returns the latest Apple Watch & iPhone HealthKit sync snapshot from the
    AES-256-GCM encrypted vault, FFD Workout Readiness Score (0-100), today's adapted
    6-Day Traditional Strength workout prescription, and 14-day sync history.
    """
    vault_path = _get_apple_health_vault_path()
    raw_vault = read_encrypted_json_file(vault_path, default={})
    vault_data: Dict[str, Any] = raw_vault if isinstance(raw_vault, dict) else {}
    latest_raw = vault_data.get("latest")
    latest: Dict[str, Any] = latest_raw if isinstance(latest_raw, dict) else {}
    raw_hist = vault_data.get("history")
    history: List[Any] = list(raw_hist[:14]) if isinstance(raw_hist, list) else []

    raw_m = latest.get("metrics")
    metrics: Dict[str, Any] = dict(raw_m) if isinstance(raw_m, dict) else {}
    raw_r = latest.get("readiness")
    readiness: Dict[str, Any] = (
        dict(raw_r)
        if isinstance(raw_r, dict)
        else compute_ffd_workout_readiness(metrics)
    )

    day_map = {
        0: "Monday — Mudgal (Indian Clubbells) + Mandatory Warm-up",
        1: "Tuesday — Core, Dand-Baithak & Mobility Conditioning",
        2: "Wednesday — Samtola (Hindu Barbell) + Mandatory Warm-up",
        3: "Thursday — Active Pranayama, Nitric Oxide Dump & FFD Walk",
        4: "Friday — Bhim Gadha (Heavy Mace) + Mandatory Warm-up",
        5: "Saturday — Full-Body Akhada Strength Circuit",
        6: "Sunday — Rest & Parasympathetic Recovery",
    }
    today_plan = day_map.get(datetime.now().weekday(), "Mandatory Warm-up & Traditional Strength")

    handler._send_json({
        "status": "ok",
        "phase": "Phase 1 — Zero-Store Foundation",
        "deliverable_id": "TD-02",
        "synced": bool(latest),
        "last_synced_at": latest.get("synced_at"),
        "device_source": latest.get("device_source", "Apple Watch + iPhone HealthKit"),
        "metrics": metrics,
        "readiness": readiness,
        "today_schedule": today_plan,
        "history_count": len(history),
        "history": history,
        "encrypted_at_rest": True,
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
    utr_reference = str(payload.get("utr_reference") or payload.get("utr") or "").strip()
    max_limit_inr = float(payload.get("max_single_payment_inr") or 200000.0)
    human_otp_confirmed = bool(payload.get("human_otp_2fa_confirmed", True))

    parsed_amount: Optional[float] = None
    if amount is not None and str(amount).strip():
        try:
            parsed_amount = float(amount)
        except (ValueError, TypeError):
            parsed_amount = None

    if parsed_amount is not None and parsed_amount > max_limit_inr and not human_otp_confirmed:
        handler._send_json(
            {
                "status": "requires_2fa_approval",
                "message": f"Amount INR {parsed_amount:.2f} exceeds single-payment guardrail (INR {max_limit_inr:.2f}). Confirm OTP/UPI 2FA to proceed.",
                "amount": parsed_amount,
                "guardrail_limit_inr": max_limit_inr,
            },
            status=400,
        )
        return

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
    if parsed_amount is not None:
        query_params["am"] = f"{parsed_amount:.2f}"

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
            utr_suffix = f" (UTR: {utr_reference})" if utr_reference else ""
            db_inst.update_task(
                tid,
                description=f"{old_desc} | Paid via {preferred_app.upper()} on {stamp}{utr_suffix}".strip(" |"),
            )
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


def build_pwa_manifest_dict() -> Dict[str, Any]:
    """TD-03: Generates the W3C Standalone Progressive Web App (PWA) Manifest for iPhone Safari & Chrome."""
    svg_icon = (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'>"
        "<rect width='192' height='192' rx='42' fill='%23090d16'/>"
        "<circle cx='96' cy='96' r='64' fill='none' stroke='%2300f2fe' stroke-width='8'/>"
        "<text x='96' y='115' font-size='56' text-anchor='middle' fill='%23ffffff' font-family='sans-serif' font-weight='bold'>⚡</text>"
        "</svg>"
    )
    return {
        "name": "Antigravity Fleet Control Center (AFCC)",
        "short_name": "AFCC Mahadev",
        "description": "Tri-Device Apple Watch, iPhone & Windows Laptop Personal Agentic Fleet Hub",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#090d16",
        "theme_color": "#00f2fe",
        "icons": [
            {"src": svg_icon, "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"},
            {"src": svg_icon, "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"},
        ],
        "shortcuts": [
            {
                "name": "Ask Mahadev (Action Items)",
                "short_name": "Mahadev Voice",
                "url": "/?tab=overview&voice=mahadev",
            },
            {
                "name": "Monthly Bill Payments (UPI)",
                "short_name": "Monthly Bills",
                "url": "/?tab=overview&filter=Monthly",
            },
            {
                "name": "Apple Watch & FFD Health",
                "short_name": "FFD Health",
                "url": "/?tab=health",
            },
        ],
    }


PWA_SERVICE_WORKER_JS = """// AFCC Tri-Device Zero-Cloud Service Worker (TD-03)
const CACHE_NAME = 'afcc-tri-device-shell-v2.18';
const SHELL_ASSETS = [
  '/',
  '/manifest.json',
  '/static/css/dashboard.css'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Never cache mutable /api/* routes blindly; always prefer live local/Tailscale hub
  if (url.pathname.startsWith('/api/')) {
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
"""


@router.get("/manifest.json")
def get_pwa_manifest_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-03: Serves the W3C Progressive Web App manifest for iPhone 'Add to Home Screen'."""
    handler._send_json(build_pwa_manifest_dict())


@router.get("/sw.js")
def get_pwa_service_worker_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-03: Serves the local-first Service Worker script (`/sw.js`)."""
    raw = PWA_SERVICE_WORKER_JS.encode("utf-8")
    if hasattr(handler, "send_response") and hasattr(handler, "wfile"):
        handler.send_response(200)
        handler.send_header("Content-Type", "application/javascript; charset=utf-8")
        handler.send_header("Service-Worker-Allowed", "/")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Content-Length", str(len(raw)))
        if hasattr(handler, "_send_security_headers"):
            handler._send_security_headers()
        handler.end_headers()
        handler.wfile.write(raw)
    else:
        handler._send_json({"status": "ok", "script": PWA_SERVICE_WORKER_JS})
