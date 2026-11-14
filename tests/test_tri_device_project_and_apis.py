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


def test_mobile_health_ingest_and_watch_complication_endpoints(isolated_db, monkeypatch):
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
