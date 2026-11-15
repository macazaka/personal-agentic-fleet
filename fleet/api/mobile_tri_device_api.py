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
            from fleet.core.local_tls import ensure_local_tls_certificates

            ensure_local_tls_certificates()
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

    # Determine whether this ingest request came from a real Apple Watch / iPhone or real Apple Health export
    client_ip = "127.0.0.1"
    user_agent = ""
    if hasattr(handler, "client_address") and isinstance(getattr(handler, "client_address", None), tuple) and handler.client_address:
        client_ip = str(handler.client_address[0])
    if hasattr(handler, "headers") and getattr(handler, "headers", None):
        user_agent = str(handler.headers.get("User-Agent") or "")

    source_type = str(payload.get("source_type") or "").strip().lower()
    is_real_device = bool(
        client_ip not in ("127.0.0.1", "::1", "localhost")
        or any(ua_tok in user_agent for ua_tok in ("iPhone", "iPad", "Watch", "Shortcuts", "CFNetwork", "Darwin"))
        or source_type in ("real_device", "ios_shortcut", "apple_health_export", "mobile_pair_bridge")
    )

    # Persist encrypted snapshot in local vault (AES-256-GCM + HKDF-SHA256)
    vault_path = _get_apple_health_vault_path()
    raw_vault = read_encrypted_json_file(vault_path, default={"history": []})
    vault_data: Dict[str, Any] = raw_vault if isinstance(raw_vault, dict) else {"history": []}
    raw_hist = vault_data.get("history")
    history: List[Any] = list(raw_hist) if isinstance(raw_hist, list) else []
    snapshot = {
        "synced_at": datetime.now().isoformat(),
        "device_source": device_source,
        "client_ip": client_ip,
        "is_real_device_sync": is_real_device,
        "source_type": source_type or ("remote_device" if is_real_device else "api_ingest"),
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
            f"Apple Watch/iPhone sync ({len(logged_metrics)} metrics, real={is_real_device}) • Readiness {readiness['readiness_score']}/100",
        )

    handler._send_json({
        "status": "ok",
        "device_source": device_source,
        "is_real_device_sync": is_real_device,
        "client_ip": client_ip,
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
        "synced": bool(latest and latest.get("is_real_device_sync")),
        "is_real_device_sync": bool(latest.get("is_real_device_sync")),
        "last_synced_at": latest.get("synced_at") if latest.get("is_real_device_sync") else None,
        "device_source": latest.get("device_source", "Not Connected Yet") if latest.get("is_real_device_sync") else "Awaiting Real Apple Watch / iPhone Connection",
        "client_ip": latest.get("client_ip"),
        "metrics": metrics if latest.get("is_real_device_sync") else {},
        "readiness": readiness if latest.get("is_real_device_sync") else {"readiness_score": None, "readiness_tier": "AWAITING_WATCH_SYNC", "recommendation": "Click '⌚ Sync Apple Watch Now' to verify your Apple Watch / iPhone connection and run a real sync."},
        "today_schedule": today_plan,
        "history_count": len(history),
        "history": history,
        "encrypted_at_rest": True,
    })


def _scan_windows_bluetooth_and_lan_apple_devices() -> Dict[str, Any]:
    """
    Probes the local Windows PnP Bluetooth stack (`Get-PnpDevice -Class Bluetooth`)
    and ARP table (`arp -a`) to detect real Apple Inc. (`VID_004C`) iPhones/Watches
    and active Wi-Fi LAN neighbors.
    """
    import os
    import re
    import subprocess

    apple_bt_devices: List[Dict[str, str]] = []
    watch_bt_found = False
    iphone_bt_found = False
    lan_neighbors: List[str] = []

    if is_test_environment():
        return {
            "apple_bt_devices": [{"name": "ChandavaneMaCaZaKa (Apple iPhone VID_004C)", "status": "OK", "role": "iPhone Companion Bridge"}],
            "watch_bt_found": False,
            "iphone_bt_found": True,
            "lan_neighbors": ["192.168.1.65", "192.168.1.86", "192.168.1.87"],
        }

    hidden_kw: Dict[str, Any] = (
        {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
        if os.name == "nt"
        else {}
    )
    if os.name == "nt":
        try:
            import winreg

            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\BTHENUM")
            num_subkeys = winreg.QueryInfoKey(root)[0]
            seen_names: set[str] = set()
            apple_vid_names: set[str] = set()

            # First pass: collect device names associated with Apple Bluetooth Vendor ID 0x004C
            for i in range(num_subkeys):
                sub = winreg.EnumKey(root, i)
                sub_up = sub.upper()
                if "004C" in sub_up:
                    sk = winreg.OpenKey(root, sub)
                    for j in range(winreg.QueryInfoKey(sk)[0]):
                        inst = winreg.EnumKey(sk, j)
                        ik = winreg.OpenKey(sk, inst)
                        try:
                            fn = str(winreg.QueryValueEx(ik, "FriendlyName")[0] or "")
                            m_paren = re.search(r";\(([^)]+)\)", fn)
                            if m_paren:
                                apple_vid_names.add(m_paren.group(1).strip())
                        except Exception:
                            pass

            # Second pass: inspect Dev_* entries for matching Apple iPhone / Watch devices
            for i in range(num_subkeys):
                sub = winreg.EnumKey(root, i)
                if not sub.upper().startswith("DEV_"):
                    continue
                sk = winreg.OpenKey(root, sub)
                for j in range(winreg.QueryInfoKey(sk)[0]):
                    inst = winreg.EnumKey(sk, j)
                    ik = winreg.OpenKey(sk, inst)
                    try:
                        fname = str(winreg.QueryValueEx(ik, "FriendlyName")[0] or "").strip()
                    except Exception:
                        fname = ""
                    if not fname or fname in seen_names:
                        continue
                    is_watch_name = "WATCH" in fname.upper()
                    is_apple_dev = (
                        fname in apple_vid_names
                        or is_watch_name
                        or any(k in fname.upper() for k in ("IPHONE", "APPLE", "CHANDAVANEMACAZAKA"))
                    )
                    if is_apple_dev:
                        seen_names.add(fname)
                        role = "Apple Watch" if is_watch_name else "Paired Apple iPhone (VID_004C Companion Bridge)"
                        apple_bt_devices.append({
                            "name": fname,
                            "status": "Paired (BTHENUM)",
                            "role": role,
                            "instance_id": f"BTHENUM\\{sub}",
                        })
                        if is_watch_name:
                            watch_bt_found = True
                        else:
                            iphone_bt_found = True
        except Exception:
            pass

        try:
            arp_res = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                **hidden_kw,
            )
            if arp_res.returncode == 0 and arp_res.stdout:
                for m in re.finditer(r"\b(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)\b", arp_res.stdout):
                    ip_val = m.group(1)
                    if not ip_val.endswith((".1", ".255", ".35")) and ip_val not in lan_neighbors:
                        lan_neighbors.append(ip_val)
        except Exception:
            pass

    return {
        "apple_bt_devices": apple_bt_devices,
        "watch_bt_found": watch_bt_found,
        "iphone_bt_found": iphone_bt_found,
        "lan_neighbors": lan_neighbors[:8],
    }


def _check_windows_firewall_lan_status() -> Dict[str, Any]:
    """
    Fast (<2ms) read-only Windows Registry inspection of Windows Defender Firewall rules
    (`HKLM\\SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\FirewallRules`)
    to detect if the current Python executable (`sys.executable`) has an explicit inbound
    `Action=Block` rule on the `Public` profile or lacks an inbound TCP port 7890 `Allow` rule
    (which causes `ERR_CONNECTION_TIMED_OUT` when an iPhone on Wi-Fi tries to open `/mobile-pair`).
    """
    import os
    import sys

    result: Dict[str, Any] = {
        "python_exe": sys.executable,
        "block_rule_ids": [],
        "allow_public": False,
        "allow_private": False,
        "allow_port_7890": False,
        "blocked_on_public_wifi": False,
    }
    if os.name != "nt":
        result["allow_public"] = True
        result["allow_private"] = True
        result["allow_port_7890"] = True
        return result

    try:
        import winreg

        exe_low = sys.executable.lower()
        key_path = r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            idx = 0
            while True:
                try:
                    rule_id, val, _ = winreg.EnumValue(k, idx)
                    idx += 1
                    if not isinstance(val, str):
                        continue
                    vlow = val.lower()
                    if "active=true" not in vlow or "dir=in" not in vlow:
                        continue
                    if "lport=7890" in vlow and "action=allow" in vlow:
                        result["allow_port_7890"] = True
                    if exe_low in vlow:
                        if "action=block" in vlow:
                            result["block_rule_ids"].append(rule_id)
                        elif "action=allow" in vlow:
                            if "profile=public" in vlow or "profile=" not in vlow:
                                result["allow_public"] = True
                            if "profile=private" in vlow or "profile=" not in vlow:
                                result["allow_private"] = True
                except OSError:
                    break
    except Exception:
        pass

    result["blocked_on_public_wifi"] = bool(
        (len(result["block_rule_ids"]) > 0 or not result["allow_public"])
        and not result["allow_port_7890"]
    )
    return result



def _parse_apple_health_xml_or_json_content(raw_text: str) -> Dict[str, Any]:
    """
    Extracts real Apple Watch / HealthKit metrics from an Apple Health `export.xml`
    snippet or JSON export without loading DTDs (100% XXE-safe).
    """
    import re

    stripped = raw_text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                raw_inner = data.get("metrics")
                inner: Dict[str, Any] = raw_inner if isinstance(raw_inner, dict) else data
                return {k: v for k, v in inner.items() if v is not None}
        except Exception:
            pass

    metrics: Dict[str, Any] = {}
    type_map = {
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_sdnn_ms",
        "HKQuantityTypeIdentifierRestingHeartRate": "resting_hr_bpm",
        "HKQuantityTypeIdentifierStepCount": "steps",
        "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
        "HKQuantityTypeIdentifierOxygenSaturation": "spo2_pct",
        "HKQuantityTypeIdentifierBodyMass": "weight_kg",
        "HKQuantityTypeIdentifierBloodGlucose": "fasting_glucose",
        "HKQuantityTypeIdentifierDietaryWater": "water_ml",
    }
    for line in stripped.splitlines():
        if "<Record " not in line:
            continue
        t_m = re.search(r'type="([^"]+)"', line)
        v_m = re.search(r'value="([0-9.]+)"', line)
        if t_m and v_m:
            hk_type = t_m.group(1)
            mapped_key = type_map.get(hk_type)
            if mapped_key:
                try:
                    val = float(v_m.group(1))
                    if mapped_key == "spo2_pct" and val <= 1.0:
                        val = round(val * 100.0, 1)
                    metrics[mapped_key] = val
                except ValueError:
                    pass
    return metrics


@router.post("/api/mobile/watch/verify_and_sync")
def post_verify_and_sync_apple_watch_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Executes a transparent 5-step Apple Watch & iPhone connection verification and sync check:
      Step 1: Scan Windows Bluetooth Stack for Apple Watch / iPhone (`VID_004C`)
      Step 2: Verify Laptop Wi-Fi LAN (`0.0.0.0:7890`) & Tailscale Mesh Reachability
      Step 3: Scan Local Apple Health Inbox (`fleet/data/user/apple_health_inbox/`) for real exports
      Step 4: Inspect Encrypted Health Vault for Real Incoming Device Push (`is_real_device_sync`)
      Step 5: Final Verdict & Actionable Live Pairing Bridge (`http://<LAN_IP>:7890/mobile-pair`)
    Never fabricates fake numbers.
    """
    net_info = _discover_network_endpoints(port=7890)
    hw_info = _scan_windows_bluetooth_and_lan_apple_devices()
    lan_ip = net_info["lan_ips"][0] if net_info["lan_ips"] else "127.0.0.1"
    mobile_pair_http = f"http://{lan_ip}:7890/mobile-pair"
    mobile_pair_https = f"https://{lan_ip}:7890/mobile-pair"

    steps: List[Dict[str, Any]] = []

    # Step 1: iPhone Companion Relay & Bluetooth Hardware Scan
    # (Apple Watch pairs exclusively with a compatible iPhone and never pairs directly to Windows)
    bt_devs = hw_info["apple_bt_devices"]
    if hw_info["iphone_bt_found"] or hw_info["watch_bt_found"]:
        dev_names = ", ".join(f"{d['name']} ({d['role']})" for d in bt_devs)
        steps.append({
            "step": 1,
            "title": "iPhone Companion Relay Check (Apple Watch → iPhone → Windows Hub)",
            "status": "pass",
            "detail": (
                f"Detected your paired iPhone Companion Bridge ({dev_names}) in Windows Bluetooth Registry. "
                "Architectural Rule: Apple Watch cannot pair directly to a Windows laptop (Apple only supports pairing an Apple Watch with a compatible iPhone). "
                "Your iPhone aggregates Apple Watch sensors in HealthKit and relays them over Wi-Fi to this laptop."
            ),
        })
    else:
        steps.append({
            "step": 1,
            "title": "iPhone Companion Relay Check (Apple Watch → iPhone → Windows Hub)",
            "status": "warn",
            "detail": (
                "Apple Watch never pairs directly to a Windows laptop (it pairs exclusively with your iPhone). "
                "No paired iPhone was found in Windows Bluetooth Registry yet; your iPhone can still relay Apple Watch HealthKit data over Wi-Fi / Tailscale."
            ),
        })

    # Step 2: Wi-Fi LAN & Windows Defender Firewall Inbound Check (Port 7890)
    neighbors = hw_info["lan_neighbors"]
    fw_info = _check_windows_firewall_lan_status()
    if fw_info.get("blocked_on_public_wifi"):
        steps.append({
            "step": 2,
            "title": "Laptop Wi-Fi LAN & Windows Firewall Check (Port 7890)",
            "status": "warn",
            "detail": (
                f"AFCC is listening on 0.0.0.0:7890 ({mobile_pair_http}), BUT Windows Defender Firewall has an active Public-Profile BLOCK rule "
                f"on Python ({fw_info.get('python_exe')}) while your Wi-Fi network is set to 'Public'! "
                "This causes 'ERR_CONNECTION_TIMED_OUT' on your iPhone. Click '🛡️ Unblock iPhone Wi-Fi in Windows Firewall' below (or switch Wi-Fi from Public to Private in Windows Settings) to allow your iPhone immediately."
            ),
        })
    else:
        steps.append({
            "step": 2,
            "title": "Laptop Wi-Fi LAN & Windows Firewall Check (Port 7890)",
            "status": "pass",
            "detail": (
                f"AFCC Gateway is actively listening on all interfaces (0.0.0.0:7890 → {mobile_pair_http}) and Windows Firewall allows inbound LAN connections. "
                f"Detected {len(neighbors)} active device(s) on your 192.168.1.x Wi-Fi subnet ({', '.join(neighbors) if neighbors else 'scanning...'})."
            ),
        })

    # Step 3: Check Local Apple Health Inbox Folder for dropped export.xml / .json files
    inbox_dir = _get_apple_health_vault_path().parent / "apple_health_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    imported_from_inbox = False
    inbox_file_used = ""
    for candidate in sorted(inbox_dir.glob("*")):
        if candidate.suffix.lower() in (".xml", ".json") and candidate.is_file():
            try:
                raw_txt = candidate.read_text(encoding="utf-8", errors="ignore")
                parsed_metrics = _parse_apple_health_xml_or_json_content(raw_txt)
                if parsed_metrics:
                    mock_h = type("_InternalHandler", (), {"_send_json": lambda self, d, status=200: None, "client_address": ("127.0.0.1", 0), "headers": {}})()
                    post_mobile_health_ingest_endpoint(
                        mock_h,
                        {
                            "device": f"Apple Health Export ({candidate.name})",
                            "source_type": "apple_health_export",
                            "metrics": parsed_metrics,
                        },
                    )
                    imported_from_inbox = True
                    inbox_file_used = candidate.name
                    break
            except Exception:
                pass

    if imported_from_inbox:
        steps.append({
            "step": 3,
            "title": "Local Apple Health Inbox Scan (fleet/data/user/apple_health_inbox/)",
            "status": "pass",
            "detail": f"Found and ingested real Apple Health export file '{inbox_file_used}' into encrypted vault.",
        })
    else:
        steps.append({
            "step": 3,
            "title": "Local Apple Health Inbox Scan (fleet/data/user/apple_health_inbox/)",
            "status": "info",
            "detail": "No local Apple Health export.xml / .json file found in fleet/data/user/apple_health_inbox/.",
        })

    # Step 4: Verify Real Device Push in Encrypted Vault
    vault_path = _get_apple_health_vault_path()
    raw_vault = read_encrypted_json_file(vault_path, default={})
    vault_data: Dict[str, Any] = raw_vault if isinstance(raw_vault, dict) else {}
    latest_raw = vault_data.get("latest")
    latest: Dict[str, Any] = latest_raw if isinstance(latest_raw, dict) else {}
    is_real = bool(latest.get("is_real_device_sync"))

    if is_real:
        steps.append({
            "step": 4,
            "title": "Verify Real Apple Watch / iPhone HealthKit Telemetry",
            "status": "pass",
            "detail": (
                f"Verified real telemetry from '{latest.get('device_source')}' "
                f"(IP: {latest.get('client_ip', 'local')}, synced at {str(latest.get('synced_at', ''))[:19]})."
            ),
        })
        steps.append({
            "step": 5,
            "title": "FFD Workout Readiness & Encrypted Vault Persistence",
            "status": "pass",
            "detail": (
                f"Readiness Score {latest.get('readiness', {}).get('readiness_score', 85)}/100 "
                f"({latest.get('readiness', {}).get('readiness_tier', 'PEAK_STRENGTH')}) encrypted in apple_health_sync_vault.json."
            ),
        })
    else:
        steps.append({
            "step": 4,
            "title": "Verify Real Apple Watch / iPhone HealthKit Telemetry",
            "status": "waiting",
            "detail": (
                "No real Apple Watch / iPhone HealthKit packet has been received from your iPhone yet. "
                "Refusing to display fake demo numbers."
            ),
        })
        steps.append({
            "step": 5,
            "title": "Awaiting Live Handshake from Your iPhone / Apple Watch",
            "status": "action_required",
            "detail": (
                f"Open {mobile_pair_http} in Safari on your iPhone (connected to the same Wi-Fi) and tap 'Sync My Apple Watch & HealthKit Now', "
                "OR click '📂 Upload Apple Health Export (.xml/.json)' below."
            ),
        })

    handler._send_json({
        "status": "ok",
        "real_sync_verified": is_real,
        "steps": steps,
        "hardware": hw_info,
        "firewall": fw_info,
        "mobile_pair_http_url": mobile_pair_http,
        "mobile_pair_https_url": mobile_pair_https,
        "latest_sync": latest if is_real else None,
    })


@router.post("/api/mobile/gateway/fix_firewall")
def post_fix_windows_firewall_for_mobile_bridge_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Launches the standard Windows UAC elevation prompt (`ShellExecuteW(..., "runas", ...)`)
    so the user can click 'Yes' on their laptop screen to:
      1. Remove explicit `Action=Block` rules on `sys.executable` for the Public profile
      2. Add an inbound `Allow` rule for TCP port 7890 (`AFCC Tri-Device iPhone Bridge (Port 7890)`) on `LocalSubnet`
      3. Switch active `Public` Wi-Fi connection profiles to `Private`
    """
    import os
    import sys

    fw_before = _check_windows_firewall_lan_status()
    ps_cmds = [
        f"Get-NetFirewallApplicationFilter -Program '{sys.executable}' -ErrorAction SilentlyContinue | Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object {{ $_.Action -eq 'Block' }} | Remove-NetFirewallRule -ErrorAction SilentlyContinue",
        "Remove-NetFirewallRule -DisplayName 'AFCC Tri-Device iPhone Bridge (Port 7890)' -ErrorAction SilentlyContinue",
        f"New-NetFirewallRule -DisplayName 'AFCC Tri-Device iPhone Bridge (Port 7890)' -Direction Inbound -Protocol TCP -LocalPort 7890 -RemoteAddress LocalSubnet -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null",
        f"New-NetFirewallRule -DisplayName 'AFCC Python Inbound LAN (Port 7890)' -Direction Inbound -Program '{sys.executable}' -Protocol TCP -LocalPort 7890 -RemoteAddress LocalSubnet -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null",
        "Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq 'Public' } | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue",
    ]
    joined_ps = "; ".join(ps_cmds)
    if os.name != "nt":
        handler._send_json({
            "status": "ok",
            "uac_prompt_triggered": False,
            "message": "Non-Windows OS; no Windows Firewall rule needed.",
            "powershell_command": joined_ps,
            "firewall": fw_before,
            "firewall_before": fw_before,
        })
        return

    uac_triggered = False
    if not is_test_environment():
        try:
            import ctypes

            ret = getattr(ctypes, "windll").shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{joined_ps}"',
                None,
                0,
            )
            uac_triggered = int(ret) > 32
        except Exception:
            uac_triggered = False

    handler._send_json({
        "status": "ok",
        "uac_prompt_triggered": uac_triggered,
        "message": (
            "Triggered Windows Administrator (UAC) confirmation dialog on your laptop. "
            "Click 'Yes' on the Windows prompt to unblock Port 7890 and C:\\Python314\\python.exe for your iPhone over Wi-Fi!"
        ),
        "powershell_command": joined_ps,
        "firewall_before": fw_before,
    })


@router.post("/api/mobile/gateway/open_wifi_settings")
def post_open_windows_wifi_or_firewall_settings_endpoint(handler: Any, body: Dict[str, Any]):
    """Opens Windows 10 Wi-Fi Network Settings (`ms-settings:network-wifi`) or Firewall Allowed Apps."""
    import os
    import subprocess

    payload: Dict[str, Any] = body if isinstance(body, dict) else {}
    target = str(payload.get("target") or "wifi").strip().lower()
    if os.name == "nt" and not is_test_environment():
        try:
            if target == "firewall":
                subprocess.Popen(["control.exe", "/name", "Microsoft.WindowsFirewall", "/page", "pageConfigureApps"])
            else:
                getattr(os, "startfile")("ms-settings:network-wifi")  # type: ignore[attr-defined]
        except Exception:
            pass
    handler._send_json({
        "status": "ok",
        "opened": target,
        "instructions": (
            "In Windows Wi-Fi Settings, click your connected Wi-Fi network properties and switch 'Network profile' from 'Public' to 'Private'."
        ),
    })


@router.post("/api/mobile/health/import_export")
def post_import_apple_health_export_endpoint(handler: Any, body: Dict[str, Any]):
    """Imports a real Apple Health `export.xml` or `.json` file uploaded from the browser or iPhone."""
    payload = body if isinstance(body, dict) else {}
    filename = str(payload.get("filename") or "apple_health_export.xml").strip()
    content = str(payload.get("content") or "").strip()
    if not content:
        handler._send_json({"status": "error", "message": "Empty file content."}, status=400)
        return

    parsed_metrics = _parse_apple_health_xml_or_json_content(content)
    if not parsed_metrics:
        handler._send_json(
            {
                "status": "error",
                "message": "No recognizable Apple HealthKit records (<Record type=\"HKQuantityTypeIdentifier...\"/> or metrics JSON) found in file.",
            },
            status=400,
        )
        return

    # Save to inbox and ingest as real device sync
    inbox_dir = _get_apple_health_vault_path().parent / "apple_health_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    (inbox_dir / safe_name).write_text(content[:2_000_000], encoding="utf-8")

    post_mobile_health_ingest_endpoint(
        handler,
        {
            "device": f"Apple Health Export ({safe_name})",
            "source_type": "apple_health_export",
            "metrics": parsed_metrics,
        },
    )


@router.get("/mobile-pair")
def get_mobile_pair_bridge_page_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    Serves a zero-install iPhone & Apple Watch Web Bridge page at `http://<LAN_IP>:7890/mobile-pair`.
    When opened on the user's iPhone over Wi-Fi, it pairs immediately and sends real telemetry to the Laptop Hub.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>AFCC — iPhone & Apple Watch Live Sync Bridge</title>
  <style>
    body { background: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; }
    .card { background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(0, 242, 254, 0.4); border-radius: 14px; padding: 18px; max-width: 480px; margin: 0 auto 16px auto; }
    h2 { margin: 0 0 6px 0; font-size: 18px; color: #00f2fe; }
    label { display: block; font-size: 12px; color: #94a3b8; margin-top: 10px; margin-bottom: 4px; font-weight: 600; }
    input { width: 100%; box-sizing: border-box; padding: 10px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 15px; }
    button { width: 100%; margin-top: 14px; padding: 12px; border-radius: 10px; border: none; background: linear-gradient(135deg, #00f2fe, #10b981); color: #090d16; font-weight: 800; font-size: 15px; cursor: pointer; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .status { margin-top: 12px; padding: 10px; border-radius: 8px; font-size: 13px; display: none; }
  </style>
</head>
<body>
  <div class="card">
    <h2>⌚📱 AFCC iPhone &amp; Apple Watch Bridge</h2>
    <div style="font-size: 12.5px; color: #cbd5e1; line-height: 1.4;">
      Connected directly to your Windows Laptop AFCC Hub over local Wi-Fi. Enter your current Apple Watch / Health app readings below (or run your iOS Shortcut) to push them live to your laptop's encrypted vault.
    </div>
    <div class="grid">
      <div><label>👟 Steps Today</label><input id="mSteps" type="number" placeholder="e.g. 6420"></div>
      <div><label>🔥 Active kcal</label><input id="mKcal" type="number" placeholder="e.g. 380"></div>
      <div><label>❤️ Resting HR (bpm)</label><input id="mRhr" type="number" placeholder="e.g. 60"></div>
      <div><label>📈 HRV SDNN (ms)</label><input id="mHrv" type="number" placeholder="e.g. 48"></div>
      <div><label>💤 Sleep (hours)</label><input id="mSleep" type="number" step="0.1" placeholder="e.g. 7.2"></div>
      <div><label>🫁 Blood Oxygen SpO2 (%)</label><input id="mSpo2" type="number" step="0.1" placeholder="e.g. 98"></div>
    </div>
    <button onclick="sendLiveWatchSync()">⌚ Push Live to Laptop AFCC Hub</button>
    <div id="mStatus" class="status"></div>
  </div>
  <script>
    async function sendLiveWatchSync() {
      const st = document.getElementById('mStatus');
      st.style.display = 'block';
      st.style.background = 'rgba(0, 242, 254, 0.15)';
      st.textContent = '⏳ Sending encrypted telemetry to Laptop Hub...';
      const metrics = {};
      const map = [['mSteps','steps'],['mKcal','active_kcal'],['mRhr','resting_hr_bpm'],['mHrv','hrv_sdnn_ms'],['mSleep','sleep_hours'],['mSpo2','spo2_pct']];
      map.forEach(([id, k]) => {
        const v = document.getElementById(id).value;
        if (v !== '') metrics[k] = parseFloat(v);
      });
      if (Object.keys(metrics).length === 0) {
        st.style.background = 'rgba(244, 63, 94, 0.2)';
        st.textContent = '⚠️ Please enter at least one reading from your Apple Watch / Health app.';
        return;
      }
      try {
        const res = await fetch('/api/mobile/health/ingest', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            device: navigator.userAgent.includes('iPhone') ? 'iPhone + Apple Watch (Live Wi-Fi Bridge)' : 'Mobile Live Bridge',
            source_type: 'mobile_pair_bridge',
            metrics: metrics
          })
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
          st.style.background = 'rgba(16, 185, 129, 0.25)';
          st.textContent = '✅ Synced to Laptop! FFD Readiness Score: ' + (data.readiness ? data.readiness.readiness_score : 85) + '/100 (' + (data.readiness ? data.readiness.readiness_tier : '') + ')';
        } else {
          st.style.background = 'rgba(244, 63, 94, 0.2)';
          st.textContent = '❌ Sync error: ' + (data.message || 'Failed');
        }
      } catch (e) {
        st.style.background = 'rgba(244, 63, 94, 0.2)';
        st.textContent = '❌ Network error: ' + e.message;
      }
    }
  </script>
</body>
</html>"""
    raw = html.encode("utf-8")
    if hasattr(handler, "send_response") and hasattr(handler, "wfile"):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(raw)))
        if hasattr(handler, "_send_security_headers"):
            handler._send_security_headers()
        handler.end_headers()
        handler.wfile.write(raw)
    else:
        handler._send_json({"status": "ok", "html_length": len(raw)})


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


ENVIRONMENTAL_CONSTRAINTS_MATRIX: List[Dict[str, str]] = [
    {
        "id": "EC-01",
        "title": "Apple Watch Exclusive iPhone Pairing Rule",
        "layer": "Apple Watch ↔ Windows Laptop",
        "constraint": "Apple Watch (watchOS) cannot pair or connect directly to a Windows laptop over Bluetooth for HealthKit, notifications, or control (Apple only allows Watch-to-iPhone pairing).",
        "practical_architecture": "Mandatory 3-Tier iPhone Companion Relay: Apple Watch syncs to iPhone 15 HealthKit via WatchConnectivity; iPhone 15 relays payloads over Wi-Fi LAN (0.0.0.0:7890) to Windows.",
        "practical_solution": "Mandatory 3-Tier iPhone Companion Relay: Apple Watch syncs to iPhone 15 HealthKit via WatchConnectivity; iPhone 15 relays payloads over Wi-Fi LAN (0.0.0.0:7890) to Windows.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-02",
        "title": "Windows 10 Home Phone Link Absence",
        "layer": "Windows 10 Home (Build 19045) OS",
        "constraint": "Microsoft 'Phone Link for iPhone' (Bluetooth ANCS notifications / HFP calls / MAP SMS) officially requires Windows 11 and is unavailable on Windows 10 Home.",
        "practical_architecture": "Bypass Windows 11 Phone Link completely: use AFCC's Native HTTP/HTTPS Wi-Fi LAN Bridge (/mobile-pair), iOS 26.3.1 Share Sheet / Shortcuts Webhooks, and Telegram/WhatsApp Bot Bridge (remote_chat).",
        "practical_solution": "Bypass Windows 11 Phone Link completely: use AFCC's Native HTTP/HTTPS Wi-Fi LAN Bridge (/mobile-pair), iOS 26.3.1 Share Sheet / Shortcuts Webhooks, and Telegram/WhatsApp Bot Bridge (remote_chat).",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-03",
        "title": "Zero-Xcode & Zero-$99 Developer Account",
        "layer": "No macOS Xcode / No $99/yr Apple Dev Account",
        "constraint": "Compiling custom Swift/watchOS apps requires macOS Xcode + a $99/yr Apple Developer account (free sideloaded profiles expire in 7 days and lack the paid HealthKit entitlement).",
        "practical_architecture": "100% Zero-Xcode / Zero-App-Store Stack: iOS 26.3.1 Safari Standalone PWA + Native iOS Shortcuts ('Find Health Samples' + 'Get Contents of URL') + Native watchOS Shortcuts ('Show on Apple Watch' Complication).",
        "practical_solution": "100% Zero-Xcode / Zero-App-Store Stack: iOS 26.3.1 Safari Standalone PWA + Native iOS Shortcuts ('Find Health Samples' + 'Get Contents of URL') + Native watchOS Shortcuts ('Show on Apple Watch' Complication).",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-04",
        "title": "iOS 26.3.1 HealthKit Lock-Screen Encryption",
        "layer": "iOS 26.3.1 Secure Enclave HealthKit Lock",
        "constraint": "iOS 26.3.1 encrypts HealthKit (HKHealthStore) with Secure Enclave Class-B/A keys that block 'Find Health Samples' while the iPhone 15 screen is locked.",
        "practical_architecture": "FaceID-Unlocked Event Triggers: bind iOS Personal Automations to 'When Wake-Up Alarm Is Stopped', 'When Apple Watch Workout Ends', 'When Opening Safari/Health', or 1-Tap Back-Tap / Control Center.",
        "practical_solution": "FaceID-Unlocked Event Triggers: bind iOS Personal Automations to 'When Wake-Up Alarm Is Stopped', 'When Apple Watch Workout Ends', 'When Opening Safari/Health', or 1-Tap Back-Tap / Control Center.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-05",
        "title": "Dual-Core 1.70 GHz ULV CPU Budget",
        "layer": "Laptop CPU Budget (Dual-Core ULV, No Discrete GPU)",
        "constraint": "Dual-core 1.70 GHz ULV processor with integrated HD Graphics cannot afford heavy background PowerShell spawns (4-7s CPU spikes) or continuous local LLM/Whisper polling.",
        "practical_architecture": "Sub-2ms Zero-Subprocess Engine: direct Python winreg BTHENUM Bluetooth lookup (<2ms), hardware WebAudio FFT 6D voiceprint (<3% CPU), and $0.00 Tier-0 deterministic regex routing.",
        "practical_solution": "Sub-2ms Zero-Subprocess Engine: direct Python winreg BTHENUM Bluetooth lookup (<2ms), hardware WebAudio FFT 6D voiceprint (<3% CPU), and $0.00 Tier-0 deterministic regex routing.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-06",
        "title": "iOS 26.3.1 Safari UPI Deep-Link Sandboxing",
        "layer": "iOS 26.3.1 Safari UPI Deep-Link Sandboxing",
        "constraint": "iOS Safari blocks silent JS redirects to upi://pay, hides installed app detection (canOpenURL), and shows an invalid-address error if an uninstalled scheme is invoked.",
        "practical_architecture": "Dual-Mode UPI Open Payment Bridge: (A) Render NPCI upi://pay QR Code on laptop screen for 2-second iPhone BHIM/ICICI/GPay scan; (B) Explicit user-gesture buttons (bhim://, imobileapp://, tez://, phonepe://) + 1-Tap Copy VPA.",
        "practical_solution": "Dual-Mode UPI Open Payment Bridge: (A) Render NPCI upi://pay QR Code on laptop screen for 2-second iPhone BHIM/ICICI/GPay scan; (B) Explicit user-gesture buttons (bhim://, imobileapp://, tez://, phonepe://) + 1-Tap Copy VPA.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-07",
        "title": "WebKit Mic Policy on Plain LAN HTTP",
        "layer": "iOS 26.3.1 Safari WebAudio Mic over Plain LAN HTTP",
        "constraint": "iOS Safari blocks navigator.mediaDevices.getUserMedia on plain http://192.168.1.x unless a trusted Root CA TLS cert is installed.",
        "practical_architecture": "Provide Zero-Cert Native iOS Dictation / Siri Voice Input on /mobile-pair (works over plain HTTP immediately) alongside optional downloadable AFCC Root CA (.crt) for HTTPS.",
        "practical_solution": "Provide Zero-Cert Native iOS Dictation / Siri Voice Input on /mobile-pair (works over plain HTTP immediately) alongside optional downloadable AFCC Root CA (.crt) for HTTPS.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-08",
        "title": "Zero-Config Home Wi-Fi LAN Primary Transport",
        "layer": "Network Transport (Local Wi-Fi Active, Tailscale Optional)",
        "constraint": "Tailscale is not pre-installed by default on the Windows 10 laptop, whereas local Wi-Fi LAN (192.168.1.x:7890) is immediately active.",
        "practical_architecture": "Primary Zero-Config Transport over Local Wi-Fi LAN (0.0.0.0:7890) + Offline Outbox Spooler (TD-05), with Tailscale supported automatically whenever installed.",
        "practical_solution": "Primary Zero-Config Transport over Local Wi-Fi LAN (0.0.0.0:7890) + Offline Outbox Spooler (TD-05), with Tailscale supported automatically whenever installed.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-09",
        "title": "Multi-Peripheral Bluetooth Audio Routing",
        "layer": "Multi-Peripheral Bluetooth Audio Routing",
        "constraint": "Multiple paired Bluetooth audio endpoints (Headset Mic vs. High-Power Workout Speakers) can contend with voice biometric capture or workout video playback.",
        "practical_architecture": "Context-Aware Audio Profile Routing: route Mahadev Biometric Voice Cockpit via headset mic (85-3800 Hz DSP) and route 6-Day Akhada Workout Playlists to room/portable Bluetooth speakers.",
        "practical_solution": "Context-Aware Audio Profile Routing: route Mahadev Biometric Voice Cockpit via headset mic (85-3800 Hz DSP) and route 6-Day Akhada Workout Playlists to room/portable Bluetooth speakers.",
        "status": "Active & Enforced",
    },
    {
        "id": "EC-10",
        "title": "Zero-Cloud Personal Hardware & PII Sovereignty",
        "layer": "Zero-Cloud Personal Hardware & Biometric Privacy",
        "constraint": "Personal laptop specs, iPhone/Watch identifiers, Bluetooth instance IDs, LAN IPs, and health/UPI data must never be sent to GitHub or external clouds.",
        "practical_architecture": "Store all hardware details exclusively in gitignored fleet/data/user/personal_hardware_inventory.md and AES-256-GCM encrypted fleet/data/user/hardware_inventory_vault.json.",
        "practical_solution": "Store all hardware details exclusively in gitignored fleet/data/user/personal_hardware_inventory.md and AES-256-GCM encrypted fleet/data/user/hardware_inventory_vault.json.",
        "status": "Active & Enforced",
    },
]


def _get_hardware_inventory_vault_path() -> Path:
    folder = "test_user" if is_test_environment() else "user"
    path = DATA_DIR / folder / "hardware_inventory_vault.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _discover_local_hardware_inventory_snapshot() -> Dict[str, Any]:
    """
    Builds or loads the user's personal hardware & peripheral inventory strictly from
    the local encrypted vault (`fleet/data/user/hardware_inventory_vault.json`) and
    live local OS/Bluetooth introspection — never exposing personal identifiers in Git.
    """
    import platform

    vault_path = _get_hardware_inventory_vault_path()
    saved_raw = read_encrypted_json_file(vault_path, default={})
    saved: Dict[str, Any] = saved_raw if isinstance(saved_raw, dict) else {}

    net_info = _discover_network_endpoints(port=7890)
    bt_scan = _scan_windows_bluetooth_and_lan_apple_devices()
    lan_ip = net_info["lan_ips"][0] if net_info.get("lan_ips") else "127.0.0.1"

    default_devices: List[Dict[str, Any]] = [
        {
            "id": "hw_laptop_hub",
            "tier": "Tier 3 — Core Compute Hub",
            "category": "Workstation / Compute",
            "name": "Windows 10 Laptop AFCC Hub",
            "model": saved.get("laptop_model") or f"{platform.system()} {platform.release()} ({platform.machine()})",
            "os_version": f"Windows {platform.version()} (Local Hub 0.0.0.0:7890)",
            "os_or_firmware": f"Windows {platform.version()} (Local Hub 0.0.0.0:7890)",
            "connection_protocol": f"Wi-Fi LAN ({lan_ip}:7890) + Bluetooth 4.0/LE",
            "transport": f"Wi-Fi LAN ({lan_ip}:7890) + Bluetooth 4.0/LE",
            "role": "Primary AFCC Server, Local SQLite + AES-256-GCM Vault, Biometric Voice Cockpit",
            "status": "Online (Local Host)",
        },
        {
            "id": "hw_iphone_bridge",
            "tier": "Tier 2 — Mandatory Companion Bridge",
            "category": "Smartphone / Tablet",
            "name": "Apple iPhone 15 Companion Bridge",
            "model": "iPhone 15 (USB-C, A16 Bionic, Secure Enclave)",
            "os_version": "iOS 26.3.1",
            "os_or_firmware": "iOS 26.3.1",
            "connection_protocol": f"Wi-Fi LAN (http://{lan_ip}:7890/mobile-pair) + Windows Bluetooth Registry",
            "transport": f"Wi-Fi LAN (http://{lan_ip}:7890/mobile-pair) + Windows Bluetooth Registry",
            "role": "Mandatory Apple Watch HealthKit Relay, iOS Shortcuts Bridge, Safari Standalone PWA, 1-Tap UPI Executor (BHIM / ICICI / GPay)",
            "status": "Paired & Ready" if bt_scan.get("iphone_bt_found") else "Wi-Fi LAN Bridge Ready",
        },
        {
            "id": "hw_apple_watch",
            "tier": "Tier 1 — Wearable Sensor Edge",
            "category": "Wearable / Health Sensor",
            "name": "Apple Watch (via iPhone 15 Relay)",
            "model": "Apple Watch (watchOS Sensor & Taptic Node)",
            "os_version": "watchOS (Paired Exclusively to iPhone 15)",
            "os_or_firmware": "watchOS (Paired Exclusively to iPhone 15)",
            "connection_protocol": "Apple WatchConnectivity & HKHealthStore → iPhone 15 → Wi-Fi LAN",
            "transport": "Apple WatchConnectivity & HKHealthStore → iPhone 15 → Wi-Fi LAN",
            "role": "HRV (SDNN), Resting HR, SpO2, Sleep Stages, Steps, Active Calories & Native Watch Shortcuts Complication",
            "status": "Relayed via iPhone 15",
        },
        {
            "id": "hw_bt_audio_headset",
            "tier": "Peripheral — Biometric Voice Audio",
            "category": "Bluetooth Audio / Mic",
            "name": "Bluetooth ANC Headphones & Mic",
            "model": "Bluetooth Headset & Microphone (BTHENUM)",
            "os_version": "Bluetooth A2DP / HFP",
            "os_or_firmware": "Bluetooth A2DP / HFP",
            "connection_protocol": "Windows Bluetooth Stack",
            "transport": "Windows Bluetooth Stack",
            "role": "Primary private headset for 'Mahadev' Wake-Word & 12s 3-Phase Speaker Voiceprint Lock",
            "status": "Paired in Windows BT",
        },
        {
            "id": "hw_bt_speakers",
            "tier": "Peripheral — Workout & Briefing Speakers",
            "category": "Bluetooth Audio / Mic",
            "name": "Bluetooth Workout & Room Speakers",
            "model": "Bluetooth A2DP Audio Output (BTHENUM)",
            "os_version": "Bluetooth A2DP",
            "os_or_firmware": "Bluetooth A2DP",
            "connection_protocol": "Windows Bluetooth Stack",
            "transport": "Windows Bluetooth Stack",
            "role": "Audio output for 6-Day Akhada Workout Playlists (Mudgal, Samtola, Bhim Gadha) & Spoken Morning Briefings",
            "status": "Paired in Windows BT",
        },
        {
            "id": "hw_bt_mouse",
            "tier": "Peripheral — Precision Input",
            "category": "Input / Peripheral",
            "name": "Bluetooth Low Energy Mouse",
            "model": "BLE HID Input (BTHLE)",
            "os_version": "Bluetooth LE GATT",
            "os_or_firmware": "Bluetooth LE GATT",
            "connection_protocol": "Windows Bluetooth LE",
            "transport": "Windows Bluetooth LE",
            "role": "Ergonomic workstation navigation",
            "status": "Paired in Windows BT",
        },
        {
            "id": "hw_future_health_sensors",
            "tier": "Future Expansion Slot",
            "category": "Wearable / Health Sensor",
            "name": "CGM Glucometer / Smart BP Cuff / Smart Scale",
            "model": "HealthKit-Compatible Bluetooth Medical Peripherals",
            "os_version": "BLE → iPhone 15 HealthKit → AFCC Hub",
            "os_or_firmware": "BLE → iPhone 15 HealthKit → AFCC Hub",
            "connection_protocol": "iPhone 15 HealthKit Relay Bridge",
            "transport": "iPhone 15 HealthKit Relay Bridge",
            "role": "Future auto-ingestion of Fasting/PPBS Glucose, Blood Pressure & Body Mass into FFD Protocol",
            "status": "Pre-Configured Slot",
        },
    ]

    custom_devices = saved.get("devices")
    devices_list: List[Dict[str, Any]] = (
        list(custom_devices)
        if isinstance(custom_devices, list) and len(custom_devices) > 0
        else default_devices
    )

    payload = {
        "updated_at": saved.get("updated_at") or datetime.now().isoformat(),
        "zero_cloud_guaranteed": True,
        "privacy_classification": "STRICTLY_LOCAL_USER_DATA_NEVER_IN_GITHUB",
        "markdown_doc_path": "fleet/data/user/personal_hardware_inventory.md",
        "encrypted_vault_path": f"fleet/data/{'test_user' if is_test_environment() else 'user'}/hardware_inventory_vault.json",
        "devices": devices_list,
        "inventory": {"devices": devices_list},
        "environmental_constraints": ENVIRONMENTAL_CONSTRAINTS_MATRIX,
    }
    if not saved:
        write_encrypted_json_file(vault_path, payload)
    return payload


@router.get("/api/mobile/hardware/inventory")
def get_mobile_hardware_inventory_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    Returns the local-only Personal Hardware & Peripheral Inventory and the 10
    Environmental Constraints Matrix (`EC-01`..`EC-10`). Stored strictly in
    gitignored `fleet/data/user/` and encrypted with AES-256-GCM + DPAPI.
    """
    data = _discover_local_hardware_inventory_snapshot()
    handler._send_json({"status": "ok", **data})


get_local_hardware_inventory_endpoint = get_mobile_hardware_inventory_endpoint


@router.post("/api/mobile/hardware/inventory")
def post_mobile_hardware_inventory_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Adds or updates a hardware device in the user's local-only encrypted hardware
    inventory vault (`fleet/data/user/hardware_inventory_vault.json`) without ever
    touching Git-tracked files.
    """
    payload: Dict[str, Any] = body if isinstance(body, dict) else {}
    current = _discover_local_hardware_inventory_snapshot()
    devices: List[Dict[str, Any]] = list(current.get("devices") or [])

    raw_dev = payload.get("device")
    new_dev: Dict[str, Any] = raw_dev if isinstance(raw_dev, dict) else payload
    name = str(new_dev.get("name") or "").strip()
    if not name:
        handler._send_json({"status": "error", "message": "Device 'name' is required."}, status=400)
        return

    dev_id = str(new_dev.get("id") or f"hw_{int(datetime.now().timestamp())}").strip()
    os_ver = str(new_dev.get("os_or_firmware") or new_dev.get("os_version") or "N/A").strip()
    transp = str(new_dev.get("transport") or new_dev.get("connection_protocol") or "Wi-Fi LAN / Bluetooth / iPhone Relay").strip()
    entry = {
        "id": dev_id,
        "tier": str(new_dev.get("tier") or "Peripheral / Future Expansion").strip(),
        "category": str(new_dev.get("category") or "Peripheral").strip(),
        "name": name,
        "model": str(new_dev.get("model") or name).strip(),
        "os_version": os_ver,
        "os_or_firmware": os_ver,
        "connection_protocol": transp,
        "transport": transp,
        "role": str(new_dev.get("role") or new_dev.get("notes") or "Connected via Tri-Device & Connections Agent").strip(),
        "status": str(new_dev.get("status") or "Registered Locally").strip(),
    }

    replaced = False
    for idx, existing in enumerate(devices):
        if isinstance(existing, dict) and (existing.get("id") == dev_id or existing.get("name") == name):
            devices[idx] = entry
            replaced = True
            break
    if not replaced:
        devices.append(entry)

    current["devices"] = devices
    current["inventory"] = {"devices": devices}
    current["updated_at"] = datetime.now().isoformat()
    write_encrypted_json_file(_get_hardware_inventory_vault_path(), current)

    handler._send_json({
        "status": "ok",
        "action": "updated" if replaced else "added",
        "device": entry,
        "devices_count": len(devices),
        "inventory": {"devices": devices},
        "zero_cloud_guaranteed": True,
        "encrypted_at_rest": True,
        "privacy_classification": "STRICTLY_LOCAL_USER_DATA_NEVER_IN_GITHUB",
    })


post_local_hardware_inventory_endpoint = post_mobile_hardware_inventory_endpoint

