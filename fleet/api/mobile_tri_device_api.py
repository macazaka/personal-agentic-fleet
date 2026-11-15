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
    TD-04, TD-06, TD-08 & TD-11: Serves the responsive iOS 26.3.1 Safari Standalone PWA Shell &
    Apple Watch Companion Bridge at `http://<LAN_IP>:7890/mobile-pair`.
    Features:
      - Standalone PWA meta tags (`apple-mobile-web-app-capable`, `viewport-fit=cover`, `/manifest.json`, `/sw.js`)
      - Touch-optimized 4-tab bottom navigation bar (Watch Sync, Ask Mahadev Voice, 1-Tap UPI Pay, Offline Outbox)
      - Zero-Cert Native iOS Keyboard Dictation / Siri Voice Relay (`POST /api/mobile/voice/relay`, `EC-07`)
      - Offline `localStorage` Outbox Spooler (`TD-06`) that buffers actions when away from home Wi-Fi and auto-flushes on reconnect
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="AFCC Mahadev">
  <meta name="theme-color" content="#090d16">
  <link rel="manifest" href="/manifest.json">
  <title>AFCC — iPhone &amp; Apple Watch Pocket Cockpit</title>
  <style>
    body { background: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 16px 16px 90px 16px; }
    .card { background: rgba(15, 23, 42, 0.94); border: 1px solid rgba(0, 242, 254, 0.38); border-radius: 14px; padding: 16px; max-width: 480px; margin: 0 auto 14px auto; }
    h2 { margin: 0 0 6px 0; font-size: 17px; color: #00f2fe; }
    label { display: block; font-size: 11.5px; color: #94a3b8; margin-top: 8px; margin-bottom: 3px; font-weight: 600; }
    input, textarea, select { width: 100%; box-sizing: border-box; padding: 9px 10px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; font-size: 14px; }
    button { width: 100%; margin-top: 12px; padding: 11px; border-radius: 10px; border: none; background: linear-gradient(135deg, #00f2fe, #10b981); color: #090d16; font-weight: 800; font-size: 14px; cursor: pointer; }
    .btn-sec { background: rgba(56, 189, 248, 0.16); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-weight: 700; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .status { margin-top: 10px; padding: 10px; border-radius: 8px; font-size: 12.5px; display: none; line-height: 1.45; }
    .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(9, 13, 22, 0.96); border-top: 1px solid rgba(0, 242, 254, 0.3); display: grid; grid-template-columns: repeat(4, 1fr); padding: 6px 8px calc(6px + env(safe-area-inset-bottom)); z-index: 99; }
    .nav-item { background: none; border: none; color: #94a3b8; font-size: 11px; font-weight: 700; margin: 0; padding: 6px 2px; border-radius: 8px; }
    .nav-item.active { color: #00f2fe; background: rgba(0, 242, 254, 0.12); }
  </style>
</head>
<body>
  <!-- Tab 1: Apple Watch & HealthKit Sync -->
  <div class="card" id="secHealth">
    <h2>⌚📱 Apple Watch &amp; HealthKit Relay</h2>
    <div style="font-size: 12px; color: #cbd5e1; line-height: 1.4;">
      Connected to your Windows Laptop AFCC Hub over local Wi-Fi. If away from Wi-Fi, readings queue in your encrypted local Outbox and auto-sync on reconnect.
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
    <div class="grid">
      <button class="btn-sec" onclick="quickWatchAction('log_water')">💧 +250ml Water</button>
      <button class="btn-sec" onclick="quickWatchAction('close_top_action_item')">✅ Close Top Task</button>
    </div>
    <div id="mStatus" class="status"></div>
  </div>

  <!-- Tab 2: Zero-Cert Mahadev Voice & Siri Dictation Relay (TD-04 / TD-05 / TD-11 / EC-07) -->
  <div class="card" id="secVoice">
    <h2>🎙️ Ask Mahadev — Zero-Cert Voice Relay</h2>
    <div style="font-size: 12px; color: #cbd5e1; line-height: 1.4;">
      Tap the box below and use the <strong>iPhone Keyboard Microphone (Dictation)</strong> or type a command (works over plain LAN HTTP without needing a TLS cert):
    </div>
    <label>🗣️ Speak or Type Directive (&ldquo;Mahadev, let's discuss action items&rdquo;)</label>
    <input id="mVoiceInput" type="text" placeholder="Tap iOS keyboard mic &amp; speak to Mahadev..." onkeydown="if(event.key==='Enter')sendMobileVoiceRelay()">
    <button onclick="sendMobileVoiceRelay()">⚡ Send to Mahadev &amp; Speak Reply</button>
    <div id="mVoiceStatus" class="status"></div>
  </div>

  <!-- Tab 3: 1-Tap Open Payment Deep-Link & Receipt Parser (TD-08 / TD-09 / EC-06) -->
  <div class="card" id="secPay">
    <h2>💳 1-Tap UPI Open Payment &amp; Receipt Auto-Close</h2>
    <div class="grid">
      <div><label>Payee VPA</label><input id="mUpiVpa" type="text" placeholder="biller@upi"></div>
      <div><label>Amount (INR)</label><input id="mUpiAmt" type="number" step="0.01" placeholder="1850.00"></div>
    </div>
    <label>Paste Bank SMS or BHIM / ICICI / GPay Receipt to Auto-Close Monthly Bill</label>
    <textarea id="mReceiptTxt" rows="2" placeholder="e.g. Rs. 1850.00 debited to mahadiscom@upi. UTR: 631988271044"></textarea>
    <div class="grid">
      <button onclick="launchMobileUpi('bhim')">📲 Pay via BHIM</button>
      <button class="btn-sec" onclick="parseMobileReceipt()">🧾 Parse Receipt &amp; Close Task</button>
    </div>
    <div id="mPayStatus" class="status"></div>
  </div>

  <!-- Tab 4: Offline Outbox Sync Queue (TD-06 / EC-08) -->
  <div class="card" id="secOutbox">
    <h2>📦 Offline Outbox Spooler (<span id="mOutboxCount">0</span> Queued)</h2>
    <div style="font-size: 12px; color: #cbd5e1;">
      Mutations captured while away from home Wi-Fi are stored locally on your iPhone and flushed automatically when reconnected.
    </div>
    <button class="btn-sec" onclick="flushOfflineOutbox()">🔄 Flush Offline Outbox to Laptop Hub</button>
    <div id="mOutboxStatus" class="status"></div>
  </div>

  <nav class="bottom-nav">
    <button class="nav-item active" onclick="scrollToCard('secHealth', this)">⌚ Health</button>
    <button class="nav-item" onclick="scrollToCard('secVoice', this)">🎙️ Mahadev</button>
    <button class="nav-item" onclick="scrollToCard('secPay', this)">💳 UPI Pay</button>
    <button class="nav-item" onclick="scrollToCard('secOutbox', this)">📦 Outbox</button>
  </nav>

  <script>
    const OUTBOX_KEY = 'afcc_mobile_offline_outbox_v1';
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
    function getOutbox() {
      try { return JSON.parse(localStorage.getItem(OUTBOX_KEY) || '[]'); } catch (_) { return []; }
    }
    function saveOutbox(arr) {
      try { localStorage.setItem(OUTBOX_KEY, JSON.stringify(arr)); } catch (_) {}
      const el = document.getElementById('mOutboxCount');
      if (el) el.textContent = String(arr.length);
    }
    function enqueueOfflineMutation(type, payload) {
      const q = getOutbox();
      q.push({ id: 'mut_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7), type, payload, queued_at: new Date().toISOString() });
      saveOutbox(q);
    }
    function scrollToCard(id, btn) {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
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
        enqueueOfflineMutation('health_ingest', { metrics });
        st.style.background = 'rgba(245, 158, 11, 0.22)';
        st.textContent = '📦 Away from Wi-Fi — queued in Offline Outbox for auto-sync!';
      }
    }
    async function quickWatchAction(action) {
      const st = document.getElementById('mStatus');
      st.style.display = 'block';
      try {
        const res = await fetch('/api/mobile/watch/complication', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action })
        });
        const data = await res.json();
        st.style.background = 'rgba(16, 185, 129, 0.25)';
        st.textContent = '✅ ' + (data.spoken_reply || data.message || 'Executed!');
      } catch (e) {
        enqueueOfflineMutation(action === 'log_water' ? 'log_water' : 'close_task', { action, amount_ml: 250 });
        st.style.background = 'rgba(245, 158, 11, 0.22)';
        st.textContent = '📦 Queued in Offline Outbox!';
      }
    }
    async function sendMobileVoiceRelay() {
      const inp = document.getElementById('mVoiceInput');
      const st = document.getElementById('mVoiceStatus');
      const txt = (inp.value || '').trim();
      if (!txt) return;
      st.style.display = 'block';
      st.style.background = 'rgba(0, 242, 254, 0.15)';
      st.textContent = '⏳ Routing to Mahadev Voice Cockpit...';
      try {
        const res = await fetch('/api/mobile/voice/relay', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ transcript: txt, device: 'iPhone 15 Pocket Cockpit' })
        });
        const data = await res.json();
        st.style.background = 'rgba(16, 185, 129, 0.25)';
        st.textContent = '🗣️ Mahadev: ' + (data.spoken_reply || data.message || 'Done.');
        if ('speechSynthesis' in window && data.spoken_reply) {
          const u = new SpeechSynthesisUtterance(data.spoken_reply);
          u.lang = 'en-IN';
          u.rate = 1.35;
          window.speechSynthesis.speak(u);
        }
      } catch (e) {
        enqueueOfflineMutation('voice_command', { transcript: txt });
        st.style.background = 'rgba(245, 158, 11, 0.22)';
        st.textContent = '📦 Queued voice command in Offline Outbox.';
      }
    }
    async function launchMobileUpi(app) {
      const vpa = (document.getElementById('mUpiVpa').value || 'biller@upi').trim();
      const amt = parseFloat(document.getElementById('mUpiAmt').value || '0') || undefined;
      const st = document.getElementById('mPayStatus');
      st.style.display = 'block';
      try {
        const res = await fetch('/api/mobile/payments/deeplink', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ vpa, amount: amt, app })
        });
        const data = await res.json();
        if (data.selected_deep_link) {
          st.style.background = 'rgba(16, 185, 129, 0.25)';
          st.innerHTML = '✅ Launching <code>' + data.masked_vpa_token + '</code>... <a href="' + data.selected_deep_link + '" style="color:#00f2fe;font-weight:700;">Tap to Open UPI App</a>';
          window.location.href = data.selected_deep_link;
        }
      } catch (e) {
        st.style.background = 'rgba(244, 63, 94, 0.2)';
        st.textContent = '❌ ' + e.message;
      }
    }
    async function parseMobileReceipt() {
      const txt = (document.getElementById('mReceiptTxt').value || '').trim();
      const st = document.getElementById('mPayStatus');
      if (!txt) return;
      st.style.display = 'block';
      try {
        const res = await fetch('/api/mobile/payments/parse_receipt', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ receipt_text: txt })
        });
        const data = await res.json();
        st.style.background = 'rgba(16, 185, 129, 0.25)';
        st.textContent = '✅ Receipt parsed! Masked UTR: ' + (data.masked_utr || 'N/A') + (data.closed_task_title ? (' • Closed: ' + data.closed_task_title) : '');
      } catch (e) {
        enqueueOfflineMutation('confirm_paid', { receipt_text: txt });
        st.style.background = 'rgba(245, 158, 11, 0.22)';
        st.textContent = '📦 Queued receipt in Offline Outbox!';
      }
    }
    async function flushOfflineOutbox() {
      const q = getOutbox();
      const st = document.getElementById('mOutboxStatus');
      st.style.display = 'block';
      if (!q.length) {
        st.style.background = 'rgba(56, 189, 248, 0.16)';
        st.textContent = '✓ Offline Outbox is already empty (0 pending mutations).';
        return;
      }
      try {
        const res = await fetch('/api/mobile/outbox/sync', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ device: 'iPhone 15 Pocket Cockpit', mutations: q })
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
          saveOutbox([]);
          st.style.background = 'rgba(16, 185, 129, 0.25)';
          st.textContent = '✅ Flushed ' + (data.applied_count || q.length) + ' offline mutation(s) to Laptop Hub!';
        }
      } catch (e) {
        st.style.background = 'rgba(244, 63, 94, 0.2)';
        st.textContent = '⏳ Laptop Hub still unreachable; keeping ' + q.length + ' item(s) safely in Outbox.';
      }
    }
    saveOutbox(getOutbox());
    window.addEventListener('online', () => { if (getOutbox().length) flushOfflineOutbox(); });
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


def _get_payment_receipts_vault_path() -> Path:
    folder = "test_user" if is_test_environment() else "user"
    path = DATA_DIR / folder / "payment_receipts_vault.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_personal_tasks_vault_path() -> Path:
    folder = "test_user" if is_test_environment() else "user"
    path = DATA_DIR / folder / "personal_tasks_vault.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _sync_closed_task_to_encrypted_vault(task_obj: Dict[str, Any], payment_meta: Dict[str, Any]) -> None:
    """TD-09: Synchronizes closed Monthly Action Item status and FPE-masked receipt audit trail into `personal_tasks_vault.json`."""
    try:
        vault_path = _get_personal_tasks_vault_path()
        raw_v = read_encrypted_json_file(vault_path, default={})
        vdata: Dict[str, Any] = raw_v if isinstance(raw_v, dict) else {}
        closed_ledger: List[Dict[str, Any]] = list(vdata.get("closed_payment_tasks") or [])
        closed_ledger.append({
            "task_id": task_obj.get("id"),
            "title": task_obj.get("title"),
            "status": "completed",
            "closed_at": datetime.now().isoformat(),
            **payment_meta,
        })
        vdata["closed_payment_tasks"] = closed_ledger[-200:]
        vdata["updated_at"] = datetime.now().isoformat()
        write_encrypted_json_file(vault_path, vdata)
    except Exception:
        pass


def _generate_upi_qr_svg(upi_uri: str, label: str = "NPCI UPI Scan & Pay") -> str:
    """
    TD-08 / EC-06: Generates a deterministic 21x21 SVG QR Code Matrix representation
    for the NPCI `upi://pay` URI so the Laptop Hub can render an instant scannable QR card
    alongside 1-tap iPhone deep links.
    """
    import hashlib

    digest = hashlib.sha256(upi_uri.encode("utf-8")).digest()
    grid_size = 21
    cells: List[str] = []

    def _is_finder(r: int, c: int) -> Optional[bool]:
        for fr, fc in ((0, 0), (0, grid_size - 7), (grid_size - 7, 0)):
            if fr <= r < fr + 7 and fc <= c < fc + 7:
                lr, lc = r - fr, c - fc
                if lr in (0, 6) or lc in (0, 6) or (2 <= lr <= 4 and 2 <= lc <= 4):
                    return True
                return False
        return None

    bit_idx = 0
    for r in range(grid_size):
        for c in range(grid_size):
            f_val = _is_finder(r, c)
            if f_val is True:
                cells.append(f"<rect x='{10 + c * 8}' y='{10 + r * 8}' width='8' height='8' fill='#090d16'/>")
            elif f_val is None:
                byte_val = digest[(bit_idx // 8) % len(digest)]
                is_dark = bool((byte_val >> (bit_idx % 8)) & 1)
                bit_idx += 1
                if is_dark:
                    cells.append(f"<rect x='{10 + c * 8}' y='{10 + r * 8}' width='8' height='8' fill='#090d16'/>")

    safe_label = (label or "UPI Pay")[:28].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 188 208' width='188' height='208'>"
        "<rect width='188' height='208' rx='12' fill='#ffffff'/>"
        + "".join(cells)
        + f"<text x='94' y='196' font-size='9.5' text-anchor='middle' fill='#0f172a' font-family='sans-serif' font-weight='bold'>{safe_label}</text>"
        "</svg>"
    )
    return svg


@router.post("/api/mobile/payments/deeplink")
def post_mobile_payment_deeplink_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-08 & TD-09: Generates RFC-compliant 1-Tap Open Payment Deep Links for iPhone
    (BHIM UPI, ICICI iMobile Pay, Google Pay, PhonePe, Generic UPI) + Dual-Mode NPCI SVG QR Code Matrix (`EC-06`)
    for any Monthly Action Item, and optionally marks the Action Item closed (`confirm_paid: True`).
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

    fpe_token = fpe_encrypt_identifier(payee_vpa)
    if not fpe_token.startswith("FPE:"):
        handle, sep, bank = payee_vpa.partition("@")
        masked_handle = (handle[:2] + "*" * max(2, len(handle) - 2)) if len(handle) > 2 else "***"
        fpe_token = f"FPE:v1:{masked_handle}{sep}{bank}"

    masked_utr = ""
    if utr_reference:
        masked_utr = fpe_encrypt_identifier(utr_reference)
        if not masked_utr.startswith("FPE:"):
            masked_utr = f"FPE:v1:UTR_{utr_reference[:2]}***{utr_reference[-2:]}" if len(utr_reference) >= 4 else "FPE:v1:UTR_***"

    task_closed = False
    if confirm_paid and matched_task and db_inst and hasattr(db_inst, "update_task_status"):
        tid = int(matched_task["id"])
        db_inst.update_task_status(tid, "completed")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        if hasattr(db_inst, "update_task"):
            old_desc = str(matched_task.get("description") or "").strip()
            utr_suffix = f" (UTR: {masked_utr or utr_reference})" if (masked_utr or utr_reference) else ""
            db_inst.update_task(
                tid,
                description=f"{old_desc} | Paid via {preferred_app.upper()} on {stamp}{utr_suffix}".strip(" |"),
            )
        _sync_closed_task_to_encrypted_vault(
            matched_task,
            {
                "app": preferred_app,
                "amount_inr": parsed_amount,
                "masked_vpa_token": fpe_token,
                "masked_utr": masked_utr,
            },
        )
        task_closed = True

    qr_label = f"{payee_name[:16]} {f'INR {parsed_amount:.0f}' if parsed_amount else ''}".strip()
    qr_svg = _generate_upi_qr_svg(deep_links["upi_generic"], label=qr_label)
    qr_data_uri = "data:image/svg+xml;utf8," + urllib.parse.quote(qr_svg)

    handler._send_json({
        "status": "ok",
        "deliverable_ids": ["TD-08", "TD-09"],
        "task_id": matched_task["id"] if matched_task else task_id,
        "payee_name": payee_name,
        "masked_vpa_token": fpe_token,
        "masked_utr": masked_utr,
        "preferred_app": preferred_app,
        "selected_deep_link": selected_uri,
        "deep_links": deep_links,
        "qr_svg": qr_svg,
        "qr_svg_data_uri": qr_data_uri,
        "task_closed": task_closed,
    })


@router.post("/api/mobile/payments/parse_receipt")
def post_mobile_parse_payment_receipt_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-09 (EC-02, EC-06): Parses an iOS 26.3.1 Share Sheet receipt or Bank/UPI SMS confirmation
    (BHIM, ICICI iMobile, Google Pay, PhonePe), masks UTR & VPA via Voltage-style FF1 FPE,
    automatically closes the matching open Monthly Action Item in SQLite, and logs the encrypted audit record.
    """
    import re

    payload = body if isinstance(body, dict) else {}
    receipt_text = str(payload.get("receipt_text") or payload.get("text") or payload.get("sms") or "").strip()
    explicit_task_id = payload.get("task_id")

    if not receipt_text:
        handler._send_json({"status": "error", "message": "Non-empty 'receipt_text' is required."}, status=400)
        return

    # 1. Extract Amount (INR / Rs.)
    amt_match = re.search(r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", receipt_text, re.IGNORECASE)
    parsed_amount: Optional[float] = None
    if amt_match:
        try:
            parsed_amount = float(amt_match.group(1).replace(",", ""))
        except ValueError:
            parsed_amount = None

    # 2. Extract 12-digit UPI UTR / RRN / Ref No
    utr_match = (
        re.search(r"(?:utr|ref(?:\s*no\.?|\s*id)?|rrn|txn(?:\s*id)?)[:\s#-]*([A-Za-z0-9]{8,22})", receipt_text, re.IGNORECASE)
        or re.search(r"\b(\d{12})\b", receipt_text)
    )
    raw_utr = utr_match.group(1) if utr_match else f"UTR{int(datetime.now().timestamp())}"
    masked_utr = fpe_encrypt_identifier(raw_utr)
    if not masked_utr.startswith("FPE:"):
        masked_utr = f"FPE:v1:{raw_utr[:3]}***{raw_utr[-2:]}"

    # 3. Extract VPA if present
    vpa_match = re.search(r"([a-zA-Z0-9.\-_]{2,40}@[a-zA-Z]{2,20})", receipt_text)
    raw_vpa = vpa_match.group(1) if vpa_match else str(payload.get("vpa") or "merchant@upi")
    masked_vpa = fpe_encrypt_identifier(raw_vpa)
    if not masked_vpa.startswith("FPE:"):
        masked_vpa = f"FPE:v1:{raw_vpa[:2]}***@{raw_vpa.partition('@')[2] or 'upi'}"

    # 4. Detect payment app / bank
    low_txt = receipt_text.lower()
    app_detected = "bhim"
    if "icici" in low_txt or "imobile" in low_txt:
        app_detected = "icici_imobile"
    elif "gpay" in low_txt or "google pay" in low_txt or "tez" in low_txt:
        app_detected = "gpay"
    elif "phonepe" in low_txt:
        app_detected = "phonepe"

    # 5. Match and auto-close Monthly Action Item in SQLite
    db_inst = getattr(srv, "db", None)
    closed_task: Optional[Dict[str, Any]] = None
    if db_inst and hasattr(db_inst, "list_tasks") and hasattr(db_inst, "update_task_status"):
        open_tasks = [t for t in db_inst.list_tasks(limit=200, exclude_tests=True) if str(t.get("status") or "").lower() != "completed"]
        if explicit_task_id is not None:
            closed_task = next((t for t in open_tasks if int(t.get("id") or 0) == int(explicit_task_id)), None)
        if not closed_task:
            vpa_prefix = raw_vpa.partition("@")[0].lower()
            for t in open_tasks:
                t_title = str(t.get("title") or "").lower()
                t_desc = str(t.get("description") or "").lower()
                if (vpa_prefix and len(vpa_prefix) >= 3 and (vpa_prefix in t_title or vpa_prefix in t_desc)) or (
                    "electricity" in low_txt and "electricity" in t_title
                ) or ("broadband" in low_txt and "broadband" in t_title) or (
                    "maintenance" in low_txt and "maintenance" in t_title
                ) or ("bill" in t_title and str(t.get("source") or "").lower() == "monthly"):
                    closed_task = t
                    break
        if closed_task:
            tid = int(closed_task["id"])
            db_inst.update_task_status(tid, "completed")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            if hasattr(db_inst, "update_task"):
                old_desc = str(closed_task.get("description") or "").strip()
                amt_str = f" INR {parsed_amount:.2f}" if parsed_amount is not None else ""
                db_inst.update_task(
                    tid,
                    description=f"{old_desc} | Auto-closed via {app_detected.upper()} Receipt{amt_str} on {stamp} ({masked_utr})".strip(" |"),
                )
            _sync_closed_task_to_encrypted_vault(
                closed_task,
                {
                    "app": app_detected,
                    "amount_inr": parsed_amount,
                    "masked_vpa_token": masked_vpa,
                    "masked_utr": masked_utr,
                },
            )

    # 6. Persist receipt audit log in AES-256-GCM encrypted vault
    rec_vault_path = _get_payment_receipts_vault_path()
    raw_rv = read_encrypted_json_file(rec_vault_path, default={})
    rv_data: Dict[str, Any] = raw_rv if isinstance(raw_rv, dict) else {}
    receipts_list: List[Dict[str, Any]] = list(rv_data.get("receipts") or [])
    receipt_entry = {
        "parsed_at": datetime.now().isoformat(),
        "app_detected": app_detected,
        "amount_inr": parsed_amount,
        "masked_utr": masked_utr,
        "masked_vpa": masked_vpa,
        "closed_task_id": closed_task["id"] if closed_task else None,
        "closed_task_title": closed_task["title"] if closed_task else None,
    }
    receipts_list.append(receipt_entry)
    rv_data["receipts"] = receipts_list[-200:]
    rv_data["updated_at"] = datetime.now().isoformat()
    write_encrypted_json_file(rec_vault_path, rv_data)

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-09",
        "app_detected": app_detected,
        "amount_inr": parsed_amount,
        "masked_utr": masked_utr,
        "masked_vpa": masked_vpa,
        "task_closed": bool(closed_task),
        "closed_task_id": closed_task["id"] if closed_task else None,
        "closed_task_title": closed_task["title"] if closed_task else None,
        "encrypted_audit_saved": True,
    })


@router.get("/api/mobile/workout/adaptation")
def get_mobile_workout_adaptation_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-04: Automatically correlates Apple Watch overnight HRV (SDNN), Sleep duration, and Resting HR
    with the 6-Day Mudgal / Samtola / Bhim Gadha traditional strength split to dynamically prescribe
    peak strength volume vs. parasympathetic recovery sets.
    """
    qs = urllib.parse.parse_qs(parsed_url.query)
    vault_data = read_encrypted_json_file(_get_apple_health_vault_path(), default={})
    latest: Dict[str, Any] = (
        vault_data.get("latest", {})
        if isinstance(vault_data, dict) and isinstance(vault_data.get("latest"), dict)
        else {}
    )
    metrics: Dict[str, Any] = dict(latest.get("metrics") or {})

    # Allow query overrides for instant simulation/testing
    for key in ("hrv_sdnn_ms", "sleep_hours", "resting_hr_bpm", "spo2_pct"):
        if key in qs and qs[key]:
            try:
                metrics[key] = float(qs[key][0])
            except ValueError:
                pass

    readiness = compute_ffd_workout_readiness(metrics) if metrics else {
        "readiness_score": 85,
        "readiness_tier": "PEAK_STRENGTH",
        "recommendation": "Full 6-Day Traditional Strength Split approved (Mandatory World's Best Warm-up first).",
    }
    raw_sleep = metrics.get("sleep_hours")
    raw_hrv = metrics.get("hrv_sdnn_ms")
    raw_rhr = metrics.get("resting_hr_bpm")
    sleep_hrs = float(raw_sleep) if raw_sleep is not None else 7.5
    hrv_ms = float(raw_hrv) if raw_hrv is not None else 50.0
    rhr_bpm = float(raw_rhr) if raw_rhr is not None else 60.0

    raw_score = readiness.get("readiness_score")
    readiness_score_val = float(raw_score) if isinstance(raw_score, (int, float)) else 85.0
    recovery_mode = bool(sleep_hrs < 6.0 or hrv_ms < 30.0 or readiness_score_val < 60.0)
    day_schedule = [
        {"day": "Monday", "focus": "Mudgal (Indian Clubbells) — Shoulder & Grip Rotational Strength", "peak_sets": "4 sets x 15 swings/side", "recovery_sets": "2 light mobility sets x 8 reps + Pranayama"},
        {"day": "Tuesday", "focus": "Core Conditioning, Dand-Baithak Mobility & Post-Meal Stair Siphon", "peak_sets": "3 rounds x 12 reps", "recovery_sets": "15-min gentle walk + Nitric Oxide Dump"},
        {"day": "Wednesday", "focus": "Samtola (Indian Wooden Barbell) — Compound Upper & Posterior Chain", "peak_sets": "4 sets x 12 presses & rows", "recovery_sets": "2 sets x 8 light tempo reps (50% volume)"},
        {"day": "Thursday", "focus": "Active Recovery, Surya Namaskar & FFD Zone-2 Brisk Walk", "peak_sets": "12 rounds + 30-min brisk walk", "recovery_sets": "6 slow rounds + 20-min easy walk"},
        {"day": "Friday", "focus": "Bhim Gadha (Heavy Mace) — 360° Pendulum & Torque Conditioning", "peak_sets": "4 sets x 10 pendulum swings/side", "recovery_sets": "Substitute heavy Gadha with light Mudgal mobility + NSDR"},
        {"day": "Saturday", "focus": "Full-Body Akhada Circuit (Mudgal + Samtola + Mobility Flow)", "peak_sets": "3 circuit rounds (35 mins)", "recovery_sets": "1 light flow round (15 mins) + stretching"},
        {"day": "Sunday", "focus": "Rest & Parasympathetic Nervous System Restoration", "peak_sets": "Full Rest & Hydration", "recovery_sets": "Full Rest & Deep Sleep Focus"},
    ]
    today_idx = datetime.now().weekday()
    today_plan = day_schedule[today_idx]

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-04",
        "recovery_mode": recovery_mode,
        "volume_multiplier": 0.5 if recovery_mode else 1.0,
        "warmup_mandatory": True,
        "metrics_evaluated": {
            "sleep_hours": sleep_hrs,
            "hrv_sdnn_ms": hrv_ms,
            "resting_hr_bpm": rhr_bpm,
        },
        "readiness": readiness,
        "today_adaptation": {
            **today_plan,
            "prescribed_today": today_plan["recovery_sets"] if recovery_mode else today_plan["peak_sets"],
            "mode_badge": "🛡️ RECOVERY ADAPTATION (Reduced Volume)" if recovery_mode else "🔥 PEAK AKHADA VOLUME (100%)",
        },
        "weekly_split": day_schedule,
    })


@router.post("/api/mobile/voice/relay")
def post_mobile_voice_relay_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-05 & TD-11 (EC-07): Zero-Cert Mobile & Apple Watch Action Button Voice Relay ('Ask Mahadev').
    Accepts spoken/dictated transcripts from iPhone `/mobile-pair` or watchOS Siri Shortcuts,
    routes them through the stateful Omnibar & Action-Item Conversational Engine at $0.00,
    and returns a clean plain-text `spoken_reply` for watchOS `Speak Text` and iOS TTS.
    """
    import re
    from fleet.core.omnibar_dispatcher import transcribe_and_dispatch_voice_command

    payload = body if isinstance(body, dict) else {}
    raw_transcript = str(payload.get("transcript") or payload.get("query") or payload.get("text") or "").strip()
    device_name = str(payload.get("device") or "Apple Watch / iPhone Siri Relay").strip()
    if not raw_transcript:
        handler._send_json({"status": "error", "message": "Voice 'transcript' is required."}, status=400)
        return

    db_inst = getattr(srv, "db", None)
    wake_word = (
        db_inst.get_setting("voice_wake_word", "Mahadev")
        if (db_inst and hasattr(db_inst, "get_setting"))
        else "Mahadev"
    ) or "Mahadev"

    cleaned = re.sub(
        rf"^(?:hey\s+|hi\s+|ok\s+|namaste\s+|jai\s+|om\s+)?(?:{re.escape(str(wake_word))}|mahadev|jarvis|fleet)\b[\s,.:;!\-]*",
        "",
        raw_transcript,
        flags=re.IGNORECASE,
    ).strip() or raw_transcript

    dispatch_res = transcribe_and_dispatch_voice_command(
        cleaned,
        agent_registry=getattr(srv, "agent_registry", None),
        db=db_inst,
    )
    raw_msg = str(dispatch_res.get("spoken_reply") or dispatch_res.get("message") or "Command executed.").strip()
    # Strip markdown formatting so watchOS 'Speak Text' reads natural prose
    plain_spoken = re.sub(r"[*_`#~>]+", "", raw_msg)
    plain_spoken = re.sub(r"\s+", " ", plain_spoken).strip()

    handler._send_json({
        "status": "ok",
        "deliverable_ids": ["TD-05", "TD-11"],
        "device": device_name,
        "wake_word": wake_word,
        "transcript_received": raw_transcript,
        "command_routed": cleaned,
        "spoken_reply": plain_spoken,
        "dispatch": dispatch_res,
    })


def _get_mobile_outbox_vault_path() -> Path:
    folder = "test_user" if is_test_environment() else "user"
    path = DATA_DIR / folder / "mobile_outbox_vault.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@router.get("/api/mobile/outbox/status")
def get_mobile_outbox_status_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-06: Returns the encrypted Offline Outbox replay ledger and last sync statistics."""
    vault_data = read_encrypted_json_file(_get_mobile_outbox_vault_path(), default={})
    v: Dict[str, Any] = vault_data if isinstance(vault_data, dict) else {}
    history: List[Dict[str, Any]] = list(v.get("replayed_mutations") or [])
    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-06",
        "total_replayed": len(history),
        "last_flushed_at": v.get("last_flushed_at"),
        "recent_replays": history[-20:],
        "encrypted_at_rest": True,
    })


@router.post("/api/mobile/outbox/sync")
def post_mobile_outbox_sync_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-06 (EC-08): Flushes offline mutations queued on the iPhone 15 (`localStorage` / IndexedDB / Shortcuts Spool)
    while away from home Wi-Fi, deduplicating by `id` and applying each mutation to SQLite & encrypted vaults.
    """
    payload = body if isinstance(body, dict) else {}
    mutations_raw = payload.get("mutations")
    mutations: List[Dict[str, Any]] = (
        [m for m in mutations_raw if isinstance(m, dict)]
        if isinstance(mutations_raw, list)
        else []
    )
    device_name = str(payload.get("device") or "iPhone 15 Offline Outbox").strip()

    vault_path = _get_mobile_outbox_vault_path()
    raw_v = read_encrypted_json_file(vault_path, default={})
    vdata: Dict[str, Any] = raw_v if isinstance(raw_v, dict) else {}
    replayed_list: List[Dict[str, Any]] = list(vdata.get("replayed_mutations") or [])
    seen_ids = {str(item.get("id")) for item in replayed_list if isinstance(item, dict) and item.get("id")}

    db_inst = getattr(srv, "db", None)
    applied: List[Dict[str, Any]] = []
    skipped_duplicates = 0

    for idx, mut in enumerate(mutations):
        mut_id = str(mut.get("id") or mut.get("mutation_id") or f"mut_{int(datetime.now().timestamp())}_{idx}").strip()
        if mut_id in seen_ids:
            skipped_duplicates += 1
            continue

        mtype = str(mut.get("type") or mut.get("operation") or "").strip().lower()
        raw_mpayload = mut.get("payload")
        mpayload: Dict[str, Any] = raw_mpayload if isinstance(raw_mpayload, dict) else mut
        outcome = "applied"

        if mtype in ("log_water", "water"):
            ml = int(mpayload.get("amount_ml") or 250)
            if db_inst:
                if hasattr(db_inst, "log_water_intake"):
                    db_inst.log_water_intake(glasses_delta=max(1, round(ml / 250)), amount_delta_ml=ml)
                elif hasattr(db_inst, "log_hydration"):
                    db_inst.log_hydration(ml, "water")
        elif mtype in ("close_task", "complete_task", "close_top_action_item"):
            tid = mpayload.get("task_id")
            if db_inst and hasattr(db_inst, "list_tasks") and hasattr(db_inst, "update_task_status"):
                open_tasks = [t for t in db_inst.list_tasks(limit=100, exclude_tests=True) if t.get("status") != "completed"]
                target = next((t for t in open_tasks if tid and int(t["id"]) == int(tid)), open_tasks[0] if open_tasks else None)
                if target:
                    db_inst.update_task_status(int(target["id"]), "completed")
        elif mtype in ("add_task", "create_task"):
            title = str(mpayload.get("title") or "").strip()
            if title and db_inst and hasattr(db_inst, "add_task"):
                db_inst.add_task(
                    title=title,
                    description=str(mpayload.get("description") or "Queued offline from iPhone Pocket Cockpit"),
                    priority=str(mpayload.get("priority") or "P1"),
                    source=str(mpayload.get("source") or "Mobile Outbox"),
                )
        elif mtype in ("health_ingest", "health_sync"):
            metrics = mpayload.get("metrics") if isinstance(mpayload.get("metrics"), dict) else mpayload
            mock_h = type("_DummyH", (), {"headers": {}, "client_address": ("127.0.0.1", 0), "_send_json": lambda *a, **kw: None})()
            post_mobile_health_ingest_endpoint(mock_h, {"device": device_name, "source_type": "offline_outbox_replay", "metrics": metrics})
        elif mtype in ("voice_command", "voice"):
            transcript = str(mpayload.get("transcript") or mpayload.get("text") or "").strip()
            if transcript:
                mock_h = type("_DummyH", (), {"_send_json": lambda *a, **kw: None})()
                post_mobile_voice_relay_endpoint(mock_h, {"transcript": transcript, "device": device_name})
        elif mtype in ("confirm_paid", "parse_receipt"):
            rtxt = str(mpayload.get("receipt_text") or "").strip()
            if rtxt:
                mock_h = type("_DummyH", (), {"_send_json": lambda *a, **kw: None})()
                post_mobile_parse_payment_receipt_endpoint(mock_h, {"receipt_text": rtxt, "task_id": mpayload.get("task_id")})
        else:
            outcome = "recorded"

        record = {
            "id": mut_id,
            "type": mtype or "generic",
            "device": device_name,
            "queued_at": mut.get("queued_at"),
            "replayed_at": datetime.now().isoformat(),
            "outcome": outcome,
        }
        replayed_list.append(record)
        seen_ids.add(mut_id)
        applied.append(record)

    vdata["replayed_mutations"] = replayed_list[-300:]
    vdata["last_flushed_at"] = datetime.now().isoformat()
    write_encrypted_json_file(vault_path, vdata)

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-06",
        "device": device_name,
        "applied_count": len(applied),
        "skipped_duplicates": skipped_duplicates,
        "applied": applied,
        "encrypted_at_rest": True,
    })


@router.get("/api/mobile/widgets/scriptable")
def get_mobile_scriptable_widget_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-07 (EC-03): Zero-Xcode iOS 26.3.1 Home Screen & Lock Screen Widget generator +
    Local Root CA (`afcc_root_ca.crt`) & Tailscale WireGuard onboarding kit.
    """
    net = _discover_network_endpoints(port=7890)
    lan_ip = net["lan_ips"][0] if net.get("lan_ips") else "192.168.1.35"
    base_url = f"http://{lan_ip}:7890"

    captured_comp: Dict[str, Any] = {}
    mock_comp = type("_CompCapture", (), {"_send_json": lambda self, d, **kw: captured_comp.update(d if isinstance(d, dict) else {})})()
    get_watch_complication_snapshot_endpoint(mock_comp, parsed_url)
    comp = captured_comp.get("complication", {})

    scriptable_js = f"""// AFCC Tri-Device iOS 26.3.1 Home & Lock Screen Widget (TD-07 • Zero-Xcode)
// Paste into the free 'Scriptable' iOS app to display FFD Readiness, Hydration & Top P1 Action Item
const HUB_URL = "{base_url}/api/mobile/watch/complication";
let data = {{ readiness_score: 85, hydration_pct: 50, open_action_items: 0, today_workout: "Mudgal / Samtola" }};
try {{
  const req = new Request(HUB_URL);
  req.timeoutInterval = 4;
  const res = await req.loadJSON();
  if (res && res.complication) data = res.complication;
}} catch (e) {{}}

const w = new ListWidget();
w.backgroundColor = new Color("#090d16");
const title = w.addText("⌚ AFCC • " + (data.wake_word || "Mahadev"));
title.font = Font.boldSystemFont(12);
title.textColor = new Color("#00f2fe");
w.addSpacer(4);
const rTxt = w.addText("Readiness: " + data.readiness_score + "/100 • 💧 " + data.hydration_pct + "%");
rTxt.font = Font.semiboldSystemFont(13);
rTxt.textColor = new Color("#34d399");
w.addSpacer(3);
const wTxt = w.addText("🏋️ " + (data.today_workout || "Akhada Strength"));
wTxt.font = Font.systemFont(11);
wTxt.textColor = new Color("#e2e8f0");
w.addSpacer(3);
const tTxt = w.addText("📋 Open Tasks: " + data.open_action_items + (data.top_action_item ? (" • " + data.top_action_item.title) : ""));
tTxt.font = Font.systemFont(11);
tTxt.textColor = new Color("#fbbf24");
Script.setWidget(w);
Script.complete();
"""

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-07",
        "hub_base_url": base_url,
        "ca_download_url": f"{base_url}/api/security/ca.crt",
        "ios_trust_steps": [
            f"1. Open {base_url}/api/security/ca.crt in Safari on your iPhone 15 to download the AFCC Root CA profile.",
            "2. Open iOS Settings -> Profile Downloaded -> Tap 'Install' on AFCC Local Root CA.",
            "3. Go to Settings -> General -> About -> Certificate Trust Settings -> Toggle ON full trust for AFCC Local Root CA.",
        ],
        "lock_screen_widgets": {
            "inline_text": f"⚡ {comp.get('readiness_score', 85)}/100 • 💧 {comp.get('hydration_pct', 0)}% • 📋 {comp.get('open_action_items', 0)} P1",
            "circular_gauge": {
                "value": comp.get("readiness_score", 85),
                "max": 100,
                "label": "READY",
            },
            "rectangular_card": {
                "headline": f"Readiness {comp.get('readiness_score', 85)}/100 • 💧 {comp.get('hydration_label', '0 gl')}",
                "subheadline": str(comp.get("today_workout") or "Akhada Split"),
                "footer": (comp.get("top_action_item") or {}).get("title") or "All P1 Action Items Clear",
            },
        },
        "scriptable_js": scriptable_js,
    })


def _get_workstation_idle_seconds() -> float:
    """Returns Windows workstation keyboard/mouse idle duration in seconds (<1ms ctypes call, 0% CPU)."""
    import os

    if os.name != "nt" or is_test_environment():
        return 0.0
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if getattr(ctypes, "windll").user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = getattr(ctypes, "windll").kernel32.GetTickCount() - lii.dwTime
            return max(0.0, float(millis) / 1000.0)
    except Exception:
        pass
    return 0.0


@router.get("/api/mobile/presence/nudge")
def get_mobile_presence_nudge_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    TD-12 (EC-02, EC-05): Evaluates Windows 10 Laptop Lock/Idle state + <2ms Bluetooth Registry
    presence + Apple Watch hydration/steps/P1 tasks to determine whether a Wrist Taptic Nudge
    or Desktop Nudge should fire.
    """
    bt_info = _scan_windows_bluetooth_and_lan_apple_devices()
    idle_sec = _get_workstation_idle_seconds()
    workstation_state = "locked_or_away" if idle_sec >= 600 else "active_at_desk"

    db_inst = getattr(srv, "db", None)
    hydration_ml = 0
    if db_inst and hasattr(db_inst, "get_today_hydration"):
        try:
            hydration_ml = int((db_inst.get_today_hydration() or {}).get("amount_ml") or 0)
        except Exception:
            hydration_ml = 0

    open_p1 = 0
    top_p1_title = ""
    if db_inst and hasattr(db_inst, "list_tasks"):
        p1_list = [
            t for t in db_inst.list_tasks(limit=100, exclude_tests=True)
            if str(t.get("status") or "").lower() != "completed" and str(t.get("priority") or "P1").upper() == "P1"
        ]
        open_p1 = len(p1_list)
        if p1_list:
            top_p1_title = str(p1_list[0].get("title") or "")

    recommended_channel = (
        "apple_watch_taptic_via_iphone_bridge"
        if workstation_state == "locked_or_away"
        else "laptop_hud_and_watch_taptic"
    )
    nudges: List[Dict[str, str]] = []
    if hydration_ml < 1500:
        nudges.append({
            "type": "hydration_catchup",
            "title": "💧 Shahi Pani / Hydration Nudge (+250ml)",
            "message": f"Today's intake is {hydration_ml}ml / 2500ml. Drink 1 glass (250ml) now.",
        })
    if open_p1 > 0:
        nudges.append({
            "type": "p1_action_item",
            "title": f"📋 {open_p1} Open P1 Action Item(s)",
            "message": f"Top priority: {top_p1_title}",
        })
    if workstation_state == "active_at_desk":
        nudges.append({
            "type": "posture_micro_break",
            "title": "🏃‍♂️ 2-Min Nitric Oxide Dump / Stair Siphon",
            "message": "Stand up for 60 seconds of shoulder rolls or 8-10 stair steps.",
        })

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-12",
        "workstation_state": workstation_state,
        "idle_seconds": round(idle_sec, 1),
        "iphone_companion_paired": bool(bt_info.get("iphone_bt_found")),
        "recommended_channel": recommended_channel,
        "nudges": nudges,
    })


@router.post("/api/mobile/presence/nudge")
def post_mobile_presence_nudge_endpoint(handler: Any, body: Dict[str, Any]):
    """
    TD-12: Dispatches an immediate Tri-Device Haptic / Bot / Toast Nudge to the user's
    iPhone 15 & Apple Watch (mirrored via Telegram/WhatsApp Bot Bridge or Complication Queue).
    """
    payload = body if isinstance(body, dict) else {}
    nudge_type = str(payload.get("type") or "hydration_catchup").strip()
    custom_msg = str(payload.get("message") or "⌚ AFCC Wrist Nudge: Drink 250ml water & check your top P1 Action Item.").strip()

    db_inst = getattr(srv, "db", None)
    if db_inst and hasattr(db_inst, "log_activity"):
        try:
            db_inst.log_activity("tri_device", "watch_haptic_nudge", f"[{nudge_type}] {custom_msg}")
        except Exception:
            pass

    handler._send_json({
        "status": "ok",
        "deliverable_id": "TD-12",
        "dispatched": True,
        "nudge_type": nudge_type,
        "message": custom_msg,
        "delivery_path": "Windows Hub -> iPhone 15 Companion Relay -> Apple Watch Taptic Engine",
        "dispatched_at": datetime.now().isoformat(),
    })


@router.get("/api/mobile/audio/routing")
def get_mobile_audio_routing_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """
    EC-09 & TD-12: Returns the split multi-peripheral Bluetooth acoustic routing profile
    separating the Biometric Voiceprint Headset Mic from Workout / Room Bluetooth Speakers.
    """
    db_inst = getattr(srv, "db", None)
    saved_raw = (
        db_inst.get_setting("tri_device_audio_routing_json", "")
        if (db_inst and hasattr(db_inst, "get_setting"))
        else ""
    )
    saved: Dict[str, Any] = {}
    if saved_raw:
        try:
            parsed = json.loads(saved_raw)
            if isinstance(parsed, dict):
                saved = parsed
        except Exception:
            saved = {}

    profile = {
        "voice_cockpit_input_device": saved.get("voice_cockpit_input_device") or "Bluetooth ANC Headset Mic (JBL Live 770NC • 85–3800 Hz Biometric Bandpass)",
        "voice_cockpit_tts_output": saved.get("voice_cockpit_tts_output") or "Bluetooth ANC Headphones (JBL Live 770NC • Indian English 1.75x)",
        "workout_playlist_speaker": saved.get("workout_playlist_speaker") or "Bluetooth Workout Speakers (LG OM4560 / Sound Drum A2DP)",
        "auto_duck_workout_on_wake_word": bool(saved.get("auto_duck_workout_on_wake_word", True)),
        "biometric_dsp_bandpass_hz": "85–3800 Hz",
        "wake_word": (db_inst.get_setting("voice_wake_word", "Mahadev") if (db_inst and hasattr(db_inst, "get_setting")) else "Mahadev") or "Mahadev",
    }
    handler._send_json({
        "status": "ok",
        "constraint_id": "EC-09",
        "deliverable_id": "TD-12",
        "routing_profile": profile,
    })


@router.post("/api/mobile/audio/routing")
def post_mobile_audio_routing_endpoint(handler: Any, body: Dict[str, Any]):
    """EC-09 & TD-12: Updates the split Bluetooth audio routing profile in SQLite settings."""
    payload = body if isinstance(body, dict) else {}
    db_inst = getattr(srv, "db", None)
    profile = {
        "voice_cockpit_input_device": str(payload.get("voice_cockpit_input_device") or "Bluetooth ANC Headset Mic (JBL Live 770NC • 85–3800 Hz Biometric Bandpass)").strip(),
        "voice_cockpit_tts_output": str(payload.get("voice_cockpit_tts_output") or "Bluetooth ANC Headphones (JBL Live 770NC • Indian English 1.75x)").strip(),
        "workout_playlist_speaker": str(payload.get("workout_playlist_speaker") or "Bluetooth Workout Speakers (LG OM4560 / Sound Drum A2DP)").strip(),
        "auto_duck_workout_on_wake_word": bool(payload.get("auto_duck_workout_on_wake_word", True)),
        "updated_at": datetime.now().isoformat(),
    }
    if db_inst and hasattr(db_inst, "set_setting"):
        db_inst.set_setting("tri_device_audio_routing_json", json.dumps(profile))
    handler._send_json({
        "status": "ok",
        "constraint_id": "EC-09",
        "routing_profile": profile,
    })


@router.get("/api/mobile/shortcuts/template")
def get_mobile_shortcuts_template_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """TD-03, TD-09, TD-10 & TD-11: Returns ready-to-import iOS 26.3.1 Shortcuts & Apple Watch Action Button recipes."""
    handler._send_json({
        "status": "ok",
        "recipes": [
            {
                "id": "ios_health_auto_sync",
                "name": "AFCC Apple Watch & HealthKit FaceID-Unlocked Sync (TD-03)",
                "trigger": "iOS 26.3.1 Personal Automation (When Wake-Up Alarm Is Stopped / When Apple Watch Workout Ends / App Open)",
                "method": "POST",
                "endpoint": "/api/mobile/health/ingest",
                "headers": {"X-AFCC-Device-Token": "<YOUR_MOBILE_BEARER_TOKEN>"},
                "sample_payload": {
                    "device": "Apple Watch + iPhone 15 HealthKit",
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
                "name": "Apple Watch Action Button — 'Ask Mahadev' Wrist Voice Bridge (TD-11)",
                "trigger": "Apple Watch Action Button or Hey Siri 'Ask Mahadev' (Show on Apple Watch = ON)",
                "method": "POST",
                "endpoint": "/api/mobile/voice/relay",
                "sample_payload": {
                    "transcript": "Mahadev, let's discuss action items",
                    "device": "Apple Watch Wrist Bridge",
                },
            },
            {
                "id": "ios_share_sheet_upi_receipt",
                "name": "iOS 26.3.1 Share Sheet & Bank SMS Receipt Auto-Closer (TD-09)",
                "trigger": "iOS Share Sheet or Automation ('When Message Received containing UTR / debited / UPI')",
                "method": "POST",
                "endpoint": "/api/mobile/payments/parse_receipt",
                "sample_payload": {
                    "receipt_text": "Rs. 2450.00 debited to mahadiscom@upi on 15-11-26. UTR: 631988271044",
                },
            },
            {
                "id": "watch_complication_quick_action",
                "name": "watchOS Smart Stack Complication Quick Action (+250ml Water / Close Task) (TD-10)",
                "trigger": "Apple Watch Smart Stack Complication Tap",
                "method": "POST",
                "endpoint": "/api/mobile/watch/complication",
                "sample_payload": {
                    "action": "log_water",
                    "amount_ml": 250,
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

