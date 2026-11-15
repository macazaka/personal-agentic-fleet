"""
Unit & Integration Tests for the AFCC Tri-Device Ecosystem Architecture Project
(Apple Watch • iPhone • Windows Laptop Hub) and GitHub Project Governance Engine.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import urllib.parse

import pytest

from fleet.core.database import FleetDatabase


@pytest.fixture
def isolated_db(tmp_path):
    db_file = tmp_path / "test_tri_device.db"
    return FleetDatabase(db_path=db_file)


def test_tri_device_project_manifest_and_docs_sync():
    from fleet.tools.github_project_manager import (
        ROADMAP_DOC_PATH,
        WIKI_DOC_PATH,
        compute_tri_device_project_status,
        load_tri_device_project_spec,
        sync_local_project_docs,
    )

    spec = load_tri_device_project_spec()
    assert spec["project_id"] == "tri-device-architecture"
    assert len(spec["labels"]) == 10
    assert len(spec["milestones"]) == 4
    assert len(spec["deliverables"]) == 12

    doc_res = sync_local_project_docs()
    assert doc_res["status"] == "ok"
    assert ROADMAP_DOC_PATH.is_file()
    assert WIKI_DOC_PATH.is_file()

    status = compute_tri_device_project_status()
    assert status["metrics"]["total_deliverables"] == 12
    assert status["metrics"]["completed"] >= 6
    assert status["metrics"]["completion_pct"] >= 50.0
    for d in status["deliverables"]:
        assert d["all_files_present"] is True, f"Missing deliverable files for {d['id']}"


def test_tri_device_github_api_sync_provisioning():
    from fleet.tools.github_project_manager import sync_tri_device_project_to_github

    counter = {"ms": 1, "iss": 100}

    def fake_http_json(url, method="GET", payload=None, headers=None, timeout=12.0):
        p = payload if isinstance(payload, dict) else {}
        if method == "GET" and "/labels" in url:
            return 200, []
        if method == "POST" and "/labels" in url:
            return 201, {"name": p.get("name", "")}
        if method == "GET" and "/milestones" in url:
            return 200, []
        if method == "POST" and "/milestones" in url:
            num = counter["ms"]
            counter["ms"] += 1
            return 201, {"number": num, "title": p.get("title", "")}
        if method == "GET" and "/issues" in url:
            return 200, []
        if method == "POST" and "/issues" in url:
            num = counter["iss"]
            counter["iss"] += 1
            return 201, {"number": num, "title": p.get("title", "")}
        if method == "PATCH":
            return 200, {"status": "patched"}
        return 200, {}

    with patch("fleet.tools.github_project_manager._http_json_request", side_effect=fake_http_json):
        res = sync_tri_device_project_to_github(repo="macazaka/personal-agentic-fleet", token="ghs_test_token_123")
        assert res["status"] == "ok"
        assert res["labels_synced"] == 10
        assert len(res["milestones_synced"]) == 4
        assert len(res["deliverable_issues_synced"]) == 12
        assert res["epic_issue_number"] == 112
        assert "https://github.com/macazaka/personal-agentic-fleet/issues/112" == res["epic_issue_url"]


def test_mobile_health_ingest_and_watch_complication_endpoints(isolated_db, monkeypatch, tmp_path):
    import fleet.api.mobile_tri_device_api as mapi
    import fleet.server as srv
    from fleet.api.mobile_tri_device_api import (
        get_github_tri_device_project_endpoint,
        get_mobile_shortcuts_template_endpoint,
        get_watch_complication_snapshot_endpoint,
        post_mobile_health_ingest_endpoint,
        post_mobile_payment_deeplink_endpoint,
        post_watch_complication_quick_action_endpoint,
    )

    monkeypatch.setattr(srv, "db", isolated_db)
    monkeypatch.setattr(mapi, "_get_apple_health_vault_path", lambda: tmp_path / "test_vault2.json")

    # 1. Seed a Monthly Action Item
    tid = isolated_db.add_task(
        title="Monthly — Pay Electricity Bill",
        description="Pay MSEB monthly electricity bill",
        priority="P1",
        source="Monthly",
    )
    assert tid > 0

    # 2. Test TD-02: POST /api/mobile/health/ingest
    h_ingest = MagicMock()
    post_mobile_health_ingest_endpoint(
        h_ingest,
        {
            "device": "Apple Watch Ultra + iPhone 16 Pro",
            "source_type": "apple_health_export",
            "metrics": {
                "steps": 9250,
                "active_kcal": 540,
                "resting_hr_bpm": 56,
                "hrv_sdnn_ms": 58,
                "sleep_hours": 7.6,
                "spo2_pct": 98.5,
                "water_ml": 500,
            },
        },
    )
    ingest_res = h_ingest._send_json.call_args[0][0]
    assert ingest_res["status"] == "ok"
    assert ingest_res["encrypted_at_rest"] is True
    assert ingest_res["readiness"]["readiness_score"] >= 90
    assert ingest_res["readiness"]["readiness_tier"] == "PEAK_STRENGTH"

    # 3. Test TD-10: GET /api/mobile/watch/complication
    h_comp = MagicMock()
    get_watch_complication_snapshot_endpoint(h_comp, urllib.parse.urlparse("/api/mobile/watch/complication"))
    comp_res = h_comp._send_json.call_args[0][0]
    assert comp_res["status"] == "ok"
    assert comp_res["complication"]["open_action_items"] >= 1
    assert comp_res["complication"]["hydration_pct"] >= 20
    assert comp_res["complication"]["readiness_score"] >= 90

    # 4. Test TD-10 Quick Action: +250ml Water from Watch
    h_watch_water = MagicMock()
    post_watch_complication_quick_action_endpoint(h_watch_water, {"action": "log_water", "amount_ml": 250})
    assert h_watch_water._send_json.call_args[0][0]["logged_ml"] == 250

    # 5. Test TD-08 & TD-09: POST /api/mobile/payments/deeplink (BHIM / ICICI / UPI + Auto-Close)
    h_pay = MagicMock()
    post_mobile_payment_deeplink_endpoint(
        h_pay,
        {
            "task_id": tid,
            "vpa": "mahadiscom@upi",
            "amount": 1850.00,
            "app": "bhim",
            "confirm_paid": True,
        },
    )
    pay_res = h_pay._send_json.call_args[0][0]
    assert pay_res["status"] == "ok"
    assert pay_res["selected_deep_link"].startswith("bhim://pay?")
    assert "imobileapp://upi/pay?" in pay_res["deep_links"]["icici_imobile"]
    assert pay_res["task_closed"] is True
    assert pay_res["masked_vpa_token"].startswith("FPE:")

    # 6. Test TD-03 / TD-11 & TD-12 endpoints
    h_short = MagicMock()
    get_mobile_shortcuts_template_endpoint(h_short, urllib.parse.urlparse("/api/mobile/shortcuts/template"))
    assert len(h_short._send_json.call_args[0][0]["recipes"]) >= 2

    h_proj = MagicMock()
    get_github_tri_device_project_endpoint(h_proj, urllib.parse.urlparse("/api/github/projects/tri-device"))
    assert h_proj._send_json.call_args[0][0]["project_id"] == "tri-device-architecture"


def test_tri_device_backlog_sync_and_phase1_gateway_pwa_endpoints(isolated_db, monkeypatch, tmp_path):
    import fleet.api.mobile_tri_device_api as mapi
    import fleet.server as srv
    from fleet.api.mobile_tri_device_api import (
        get_local_root_ca_certificate_endpoint,
        get_mobile_gateway_status_endpoint,
        get_mobile_health_status_endpoint,
        get_mobile_pair_bridge_page_endpoint,
        get_pwa_manifest_endpoint,
        get_pwa_service_worker_endpoint,
        post_import_apple_health_export_endpoint,
        post_mobile_gateway_token_endpoint,
        post_mobile_payment_deeplink_endpoint,
        post_verify_and_sync_apple_watch_endpoint,
    )
    from fleet.core.db.backlog import TRI_DEVICE_BACKLOG_ITEMS
    from fleet.core.session_auth import validate_request_security

    monkeypatch.setattr(srv, "db", isolated_db)
    monkeypatch.setattr(mapi, "_get_apple_health_vault_path", lambda: tmp_path / "test_vault2.json")

    # 1. Verify all 12 Tri-Device Architecture items (TD-01..TD-12) are in feature_backlog
    #    and Phase 1 (TD-01, TD-02, TD-03) are marked Completed
    assert len(TRI_DEVICE_BACKLOG_ITEMS) == 12
    isolated_db.sync_ux_roadmap_backlog()
    v218_items = isolated_db.list_feature_backlog_items(target_version="v2.18.0")
    assert len(v218_items) == 12
    phase1_items = [i for i in v218_items if any(code in i["title"] for code in ("[TD-01]", "[TD-02]", "[TD-03]"))]
    assert len(phase1_items) == 3
    assert all(i["status"] == "Completed" for i in phase1_items)

    # 2. Test TD-01: Mobile Gateway Status, Bearer Token & Tailscale / Private LAN / Token Auth
    h_gw = MagicMock()
    get_mobile_gateway_status_endpoint(h_gw, urllib.parse.urlparse("/api/mobile/gateway/status"))
    gw_res = h_gw._send_json.call_args[0][0]
    assert gw_res["status"] == "ok"
    assert gw_res["deliverable_id"] == "TD-01"
    assert gw_res["pwa"]["standalone_ready"] is True

    h_tok = MagicMock()
    post_mobile_gateway_token_endpoint(h_tok, {"rotate": False})
    tok_res = h_tok._send_json.call_args[0][0]
    assert tok_res["status"] == "ok"
    bearer = tok_res["bearer_token"]
    assert bearer.startswith("afcc_mob_")

    # Verify validate_request_security accepts Tailscale CGNAT host, Private RFC-1918 LAN IP, and Bearer Token while blocking evil.com
    ok_ts, _ = validate_request_security({"Host": "100.101.102.103:7890", "Origin": "https://100.101.102.103:7890"}, "POST", {"http://127.0.0.1:7890"})
    assert ok_ts is True
    ok_lan, _ = validate_request_security({"Host": "192.168.1.35:7890", "Origin": "http://192.168.1.35:7890"}, "POST", {"http://127.0.0.1:7890"})
    assert ok_lan is True
    ok_tok, _ = validate_request_security({"Host": "192.168.1.50:7890", "X-AFCC-Mobile-Token": bearer}, "POST", {"http://127.0.0.1:7890"})
    assert ok_tok is True
    ok_evil, _ = validate_request_security({"Host": "evil.com"}, "GET", {"http://127.0.0.1:7890"})
    assert ok_evil is False

    # 3. Test TD-01: Local Root CA download (/api/security/ca.crt)
    h_ca = MagicMock(spec=["_send_json"])
    get_local_root_ca_certificate_endpoint(h_ca, urllib.parse.urlparse("/api/security/ca.crt"))
    ca_res = h_ca._send_json.call_args[0][0]
    assert ca_res["status"] == "ok"
    assert "BEGIN CERTIFICATE" in ca_res["pem"]

    # 4. Test TD-02: GET /api/mobile/health/status before any real sync -> synced == False
    h_hstat = MagicMock()
    get_mobile_health_status_endpoint(h_hstat, urllib.parse.urlparse("/api/mobile/health/status"))
    hstat_res = h_hstat._send_json.call_args[0][0]
    assert hstat_res["status"] == "ok"
    assert hstat_res["deliverable_id"] == "TD-02"
    assert hstat_res["synced"] is False
    assert hstat_res["readiness"]["readiness_tier"] == "AWAITING_WATCH_SYNC"

    # 5. Test Step-by-Step Apple Watch Hardware & Network Verification before real sync
    h_ver = MagicMock()
    post_verify_and_sync_apple_watch_endpoint(h_ver, {})
    ver_res = h_ver._send_json.call_args[0][0]
    assert ver_res["status"] == "ok"
    assert ver_res["real_sync_verified"] is False
    assert len(ver_res["steps"]) == 5
    assert ver_res["steps"][0]["step"] == 1
    assert ver_res["steps"][4]["step"] == 5

    # 6. Test importing a real Apple Health export.xml snippet -> real_sync_verified becomes True!
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <HealthData>
      <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" unit="ms" value="61.5" />
      <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" value="55" />
      <Record type="HKQuantityTypeIdentifierOxygenSaturation" unit="%" value="0.985" />
      <Record type="HKQuantityTypeIdentifierStepCount" unit="count" value="8420" />
      <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" unit="kcal" value="490" />
    </HealthData>
    """
    h_imp = MagicMock()
    post_import_apple_health_export_endpoint(h_imp, {"filename": "export.xml", "content": sample_xml})
    imp_res = h_imp._send_json.call_args[0][0]
    assert imp_res["status"] == "ok"
    assert imp_res["is_real_device_sync"] is True
    assert imp_res["readiness"]["readiness_score"] >= 85

    # Re-run Step-by-Step Verification -> now real_sync_verified is True!
    h_ver2 = MagicMock()
    post_verify_and_sync_apple_watch_endpoint(h_ver2, {})
    ver_res2 = h_ver2._send_json.call_args[0][0]
    assert ver_res2["real_sync_verified"] is True
    assert ver_res2["steps"][4]["status"] == "pass"

    # 7. Test GET /mobile-pair bridge page
    h_pair = MagicMock(spec=["_send_json"])
    get_mobile_pair_bridge_page_endpoint(h_pair, urllib.parse.urlparse("/mobile-pair"))
    pair_res = h_pair._send_json.call_args[0][0]
    assert pair_res["status"] == "ok"
    assert pair_res["html_length"] > 500

    # 8. Test TD-03: GET /manifest.json & GET /sw.js
    h_man = MagicMock()
    get_pwa_manifest_endpoint(h_man, urllib.parse.urlparse("/manifest.json"))
    man_res = h_man._send_json.call_args[0][0]
    assert man_res["display"] == "standalone"
    assert len(man_res["shortcuts"]) >= 3

    h_sw = MagicMock(spec=["_send_json"])
    get_pwa_service_worker_endpoint(h_sw, urllib.parse.urlparse("/sw.js"))
    sw_res = h_sw._send_json.call_args[0][0]
    assert sw_res["status"] == "ok"
    assert "afcc-tri-device-shell" in sw_res["script"]

    # 9. Test Payment Guardrail (> max_single_payment_inr without 2FA confirmation)
    h_guard = MagicMock()
    post_mobile_payment_deeplink_endpoint(
        h_guard,
        {
            "vpa": "vendor@upi",
            "amount": 350000.0,
            "max_single_payment_inr": 200000.0,
            "human_otp_2fa_confirmed": False,
        },
    )
    guard_res = h_guard._send_json.call_args[0][0]
    assert guard_res["status"] == "requires_2fa_approval"


def test_tri_device_dedicated_agent_and_iphone_companion_relay(isolated_db):
    from fleet.agents.tri_device.agent import TriDeviceConnectionAgent
    from fleet.core.registry import AgentRegistry
    from fleet.web.builder import get_dashboard_html

    agent = TriDeviceConnectionAgent(db=isolated_db)
    assert agent.id == "tri_device"
    manifest = agent.get_ui_manifest()
    assert manifest["category"] == "Connection Agents"
    task_res = agent.execute_task("verify_and_sync")
    assert task_res["status"] == "success"
    assert "Apple Watch pairs exclusively with a compatible iPhone" in task_res["architecture_rule"]

    reg = AgentRegistry(config={}, db=isolated_db)
    reg.discover_and_load()
    assert "tri_device" in reg.agents

    html = get_dashboard_html(standalone=False)
    assert 'id="tabBtnTriDevice"' in html
    assert 'id="viewTriDevice"' in html
    idx_view_tri = html.index('id="viewTriDevice"')
    idx_hub_card = html.index('id="triDeviceHealthHubCard"')
    assert idx_hub_card > idx_view_tri
    assert 'id="triDeviceLocalHardwareInventoryCard"' in html
    assert 'id="triDeviceConstraintsMatrixCard"' in html


def test_environmental_constraints_and_local_hardware_inventory(isolated_db, monkeypatch, tmp_path):
    import fleet.api.mobile_tri_device_api as mapi
    from fleet.api.mobile_tri_device_api import (
        ENVIRONMENTAL_CONSTRAINTS_MATRIX,
        get_local_hardware_inventory_endpoint,
        post_local_hardware_inventory_endpoint,
    )
    from fleet.core.db.backlog import TRI_DEVICE_BACKLOG_ITEMS

    monkeypatch.setattr(mapi, "_get_hardware_inventory_vault_path", lambda: tmp_path / "test_hw_vault.json")

    # 1. Verify all 10 environmental constraints (EC-01 .. EC-10) are defined
    assert len(ENVIRONMENTAL_CONSTRAINTS_MATRIX) == 10
    ec_ids = [c["id"] for c in ENVIRONMENTAL_CONSTRAINTS_MATRIX]
    assert ec_ids == [f"EC-{i:02d}" for i in range(1, 11)]

    # 2. Verify GET /api/mobile/hardware/inventory returns local-only encrypted inventory & constraints
    h_get = MagicMock()
    get_local_hardware_inventory_endpoint(h_get, urllib.parse.urlparse("/api/mobile/hardware/inventory"))
    get_res = h_get._send_json.call_args[0][0]
    assert get_res["status"] == "ok"
    assert get_res["zero_cloud_guaranteed"] is True
    assert len(get_res["environmental_constraints"]) == 10
    assert len(get_res["inventory"]["devices"]) >= 3

    # 3. Verify POST /api/mobile/hardware/inventory adds a new future hardware device into the local encrypted vault
    h_post = MagicMock()
    post_local_hardware_inventory_endpoint(
        h_post,
        {
            "name": "Omron Evolv BLE Blood Pressure Monitor",
            "category": "Wearable / Health Sensor",
            "os_or_firmware": "BLE 5.0",
            "transport": "Paired to iPhone 15 (Apple Health) -> Wi-Fi LAN",
            "role": "Automated BP & Pulse ingestion via iOS 26.3.1 HealthKit",
        },
    )
    post_res = h_post._send_json.call_args[0][0]
    assert post_res["status"] == "ok"
    assert post_res["zero_cloud_guaranteed"] is True
    names = [d["name"] for d in post_res["inventory"]["devices"]]
    assert "Omron Evolv BLE Blood Pressure Monitor" in names

    # 4. Verify TD-01..TD-12 backlog items reference the practical environmental constraints
    isolated_db.sync_ux_roadmap_backlog()
    assert len(TRI_DEVICE_BACKLOG_ITEMS) == 12
    for item in TRI_DEVICE_BACKLOG_ITEMS:
        assert "EC-" in item["description"], f"Missing EC constraint reference in {item['title']}"

    # 5. Verify Windows Firewall LAN status detection & 1-click fix endpoint
    from fleet.api.mobile_tri_device_api import (
        _check_windows_firewall_lan_status,
        post_fix_windows_firewall_for_mobile_bridge_endpoint,
        post_open_windows_wifi_or_firewall_settings_endpoint,
    )

    fw_st = _check_windows_firewall_lan_status()
    assert "blocked_on_public_wifi" in fw_st
    assert "python_exe" in fw_st

    h_fw = MagicMock()
    post_fix_windows_firewall_for_mobile_bridge_endpoint(h_fw, {})
    fw_res = h_fw._send_json.call_args[0][0]
    assert fw_res["status"] == "ok"
    assert "New-NetFirewallRule" in fw_res["powershell_command"]

    h_wifi = MagicMock()
    post_open_windows_wifi_or_firewall_settings_endpoint(h_wifi, {"target": "wifi"})
    assert h_wifi._send_json.call_args[0][0]["status"] == "ok"


def test_all_tri_device_backlog_items_td01_to_td12_completed_and_endpoints(isolated_db, monkeypatch, tmp_path):
    import fleet.api.mobile_tri_device_api as mapi
    import fleet.server as srv
    from fleet.api.mobile_tri_device_api import (
        get_mobile_audio_routing_endpoint,
        get_mobile_outbox_status_endpoint,
        get_mobile_presence_nudge_endpoint,
        get_mobile_scriptable_widget_endpoint,
        get_mobile_workout_adaptation_endpoint,
        post_mobile_audio_routing_endpoint,
        post_mobile_health_ingest_endpoint,
        post_mobile_outbox_sync_endpoint,
        post_mobile_parse_payment_receipt_endpoint,
        post_mobile_payment_deeplink_endpoint,
        post_mobile_presence_nudge_endpoint,
        post_mobile_voice_relay_endpoint,
    )
    from fleet.core.agent_studio import generate_agent_evolution_suggestions
    from fleet.core.db.backlog import TRI_DEVICE_BACKLOG_ITEMS
    from fleet.tools.github_project_manager import compute_tri_device_project_status

    monkeypatch.setattr(srv, "db", isolated_db)
    monkeypatch.setattr(mapi, "_get_apple_health_vault_path", lambda: tmp_path / "test_health_vault.json")
    monkeypatch.setattr(mapi, "_get_mobile_outbox_vault_path", lambda: tmp_path / "test_outbox_vault.json")
    monkeypatch.setattr(mapi, "_get_payment_receipts_vault_path", lambda: tmp_path / "test_receipts_vault.json")
    monkeypatch.setattr(mapi, "_get_personal_tasks_vault_path", lambda: tmp_path / "test_tasks_vault.json")
    monkeypatch.setattr(mapi, "_get_hardware_inventory_vault_path", lambda: tmp_path / "test_hw_vault2.json")

    # 1. Verify all 12 backlog items (TD-01..TD-12) are Completed (100%)
    assert len(TRI_DEVICE_BACKLOG_ITEMS) == 12
    assert all(item["status"] == "Completed" for item in TRI_DEVICE_BACKLOG_ITEMS)
    isolated_db.sync_ux_roadmap_backlog()
    v218_items = isolated_db.list_feature_backlog_items(target_version="v2.18.0")
    assert len(v218_items) == 12
    assert all(i["status"] == "Completed" for i in v218_items)

    proj_status = compute_tri_device_project_status()
    assert proj_status["metrics"]["completed"] == 12
    assert proj_status["metrics"]["completion_pct"] == 100.0

    # 2. TD-04: 6-Day Akhada HRV/Sleep Workout Adaptation (Peak vs Recovery Mode)
    h_ing_peak = MagicMock()
    post_mobile_health_ingest_endpoint(
        h_ing_peak,
        {"device": "Apple Watch", "metrics": {"hrv_sdnn_ms": 58, "sleep_hours": 7.5, "resting_hr_bpm": 54}},
    )
    h_adapt1 = MagicMock()
    get_mobile_workout_adaptation_endpoint(h_adapt1, urllib.parse.urlparse("/api/mobile/workout/adaptation"))
    adapt1 = h_adapt1._send_json.call_args[0][0]
    assert adapt1["status"] == "ok"
    assert adapt1["deliverable_id"] == "TD-04"
    assert adapt1["recovery_mode"] is False
    assert adapt1["volume_multiplier"] == 1.0

    # Simulate low sleep (< 6.0 hrs) and low HRV (< 30 ms) -> auto-switches to 50% Recovery Mode
    h_ing_low = MagicMock()
    post_mobile_health_ingest_endpoint(
        h_ing_low,
        {"device": "Apple Watch", "metrics": {"hrv_sdnn_ms": 24, "sleep_hours": 5.2, "resting_hr_bpm": 68}},
    )
    h_adapt2 = MagicMock()
    get_mobile_workout_adaptation_endpoint(h_adapt2, urllib.parse.urlparse("/api/mobile/workout/adaptation"))
    adapt2 = h_adapt2._send_json.call_args[0][0]
    assert adapt2["recovery_mode"] is True
    assert adapt2["volume_multiplier"] == 0.5
    assert "RECOVERY" in adapt2["today_adaptation"]["mode_badge"]
    assert adapt2["today_adaptation"]["prescribed_today"] == adapt2["today_adaptation"]["recovery_sets"]

    # 3. TD-05 & TD-11: Zero-Cert Mobile & Watch Action Button Voice Relay
    h_voice = MagicMock()
    post_mobile_voice_relay_endpoint(
        h_voice,
        {"transcript": "Mahadev let's discuss action items", "device": "watch_action_button"},
    )
    voice_res = h_voice._send_json.call_args[0][0]
    assert voice_res["status"] == "ok"
    assert voice_res["deliverable_ids"] == ["TD-05", "TD-11"]
    assert len(voice_res["spoken_reply"]) > 5

    # 4. TD-06: Offline Mobile Outbox Sync & Idempotent Deduplication
    h_out_sync = MagicMock()
    mutations = [
        {"id": "mut-001", "type": "log_water", "payload": {"amount_ml": 250}},
        {"id": "mut-002", "type": "add_task", "payload": {"title": "Mobile Offline Task", "priority": "P1"}},
    ]
    post_mobile_outbox_sync_endpoint(h_out_sync, {"mutations": mutations})
    sync1 = h_out_sync._send_json.call_args[0][0]
    assert sync1["status"] == "ok"
    assert sync1["applied_count"] == 2
    assert sync1["skipped_duplicates"] == 0

    # Replay the exact same mutation IDs -> 100% deduplicated!
    h_out_sync2 = MagicMock()
    post_mobile_outbox_sync_endpoint(h_out_sync2, {"mutations": mutations})
    sync2 = h_out_sync2._send_json.call_args[0][0]
    assert sync2["applied_count"] == 0
    assert sync2["skipped_duplicates"] == 2

    h_out_stat = MagicMock()
    get_mobile_outbox_status_endpoint(h_out_stat, urllib.parse.urlparse("/api/mobile/outbox/status"))
    assert h_out_stat._send_json.call_args[0][0]["total_replayed"] >= 2

    # 5. TD-07: iOS 26.3.1 Scriptable Widget Generator
    h_wid = MagicMock()
    get_mobile_scriptable_widget_endpoint(h_wid, urllib.parse.urlparse("/api/mobile/widgets/scriptable"))
    wid_res = h_wid._send_json.call_args[0][0]
    assert wid_res["status"] == "ok"
    assert wid_res["deliverable_id"] == "TD-07"
    assert "ListWidget" in wid_res["scriptable_js"]
    assert "inline_text" in wid_res["lock_screen_widgets"]

    # 6. TD-08 & TD-09: Dual-Mode UPI SVG QR & Share-Sheet / SMS Receipt Parser with FPE Masking
    bill_tid = isolated_db.add_task(
        title="Monthly — BESCOM Electricity Utility",
        description="Monthly power bill",
        priority="P1",
        source="Monthly",
    )
    h_qr = MagicMock()
    post_mobile_payment_deeplink_endpoint(
        h_qr,
        {"task_id": bill_tid, "vpa": "bescom@upi", "amount": 2450.0, "confirm_paid": False},
    )
    qr_res = h_qr._send_json.call_args[0][0]
    assert "<svg" in qr_res["qr_svg"]
    assert qr_res["qr_svg_data_uri"].startswith("data:image/svg+xml;utf8,")

    h_rcpt = MagicMock()
    post_mobile_parse_payment_receipt_endpoint(
        h_rcpt,
        {
            "receipt_text": "Paid Rs. 2,450.00 to bescom@upi via BHIM UPI. UTR: 412398765432",
            "task_id": bill_tid,
        },
    )
    rcpt_res = h_rcpt._send_json.call_args[0][0]
    assert rcpt_res["status"] == "ok"
    assert rcpt_res["deliverable_id"] == "TD-09"
    assert rcpt_res["amount_inr"] == 2450.0
    assert rcpt_res["masked_utr"].startswith("FPE:")
    assert rcpt_res["closed_task_id"] == bill_tid

    # 7. TD-12 & EC-09: Workstation Presence / Taptic Nudge & Split Bluetooth Audio Routing
    h_pres_get = MagicMock()
    get_mobile_presence_nudge_endpoint(h_pres_get, urllib.parse.urlparse("/api/mobile/presence/nudge"))
    assert h_pres_get._send_json.call_args[0][0]["deliverable_id"] == "TD-12"

    h_pres_post = MagicMock()
    post_mobile_presence_nudge_endpoint(h_pres_post, {"type": "hydration_catchup", "message": "Time for water!"})
    assert h_pres_post._send_json.call_args[0][0]["status"] == "ok"

    h_aud_post = MagicMock()
    post_mobile_audio_routing_endpoint(
        h_aud_post,
        {
            "voice_cockpit_input_device": "JBL Live 770NC Headset",
            "workout_playlist_speaker": "LG OM4560 Akhada Speaker",
            "auto_duck_workout_on_wake_word": True,
        },
    )
    assert h_aud_post._send_json.call_args[0][0]["routing_profile"]["voice_cockpit_input_device"] == "JBL Live 770NC Headset"

    h_aud_get = MagicMock()
    get_mobile_audio_routing_endpoint(h_aud_get, urllib.parse.urlparse("/api/mobile/audio/routing"))
    assert h_aud_get._send_json.call_args[0][0]["routing_profile"]["workout_playlist_speaker"] == "LG OM4560 Akhada Speaker"

    # 8. Agent Studio 10-Way Evolution Suggestions for tri_device
    evo = generate_agent_evolution_suggestions({"id": "tri_device", "name": "Tri-Device Ecosystem & Hardware Hub"})
    assert len(evo["suggestions"]) == 10






