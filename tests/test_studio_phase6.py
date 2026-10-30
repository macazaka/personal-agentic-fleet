"""
End-to-End Verification Suite for Zero-Code Agent Studio Phase 6:
1. Watched Drop-Folder (`fleet/data/user/inbox/<agent_id>/`) & EventBus Email Payload Auto-Ingestion + SHA-256 Deduplication.
2. 12th Declarative UI Block: Grounded In-Agent Q&A & Natural-Language Command Chat (`agent_chat` + `@mcp.tool` `fleet_ask_custom_agent`).
3. Smart Recurring Cycle & 1-Click Renewal Roll-Forward (`monthly`, `quarterly`, `semi_annual`, `annual` + `cycle_history` trend archival).
4. Configurable Outbound Action Hooks (`auto_create_task` with P1/P2 deduplication, `desktop_toast`, `markdown_report`, `emit_followup_event`).
5. 1-Click Multi-Agent Squad Blueprints (`GET /api/studio/blueprints` + `POST /api/studio/squads/deploy`).
"""

from __future__ import annotations

import base64
from datetime import date, timedelta
import json
from pathlib import Path
import urllib.parse
from unittest.mock import MagicMock, patch
import zlib

import pytest

from fleet.api.router import ApiRouter
from fleet.api.settings_api import (
    create_new_agent_endpoint,
    deploy_agent_squad_endpoint,
    evolve_custom_agent_endpoint,
    get_studio_blueprints_endpoint,
)
from fleet.core.agent_studio import SUPPORTED_UI_BLOCKS, synthesize_agent_from_prompt
from fleet.core.database import FleetDatabase
import fleet.core.document_extractor as doc_ext
import fleet.core.playbook_engine as pb_engine
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
import fleet.core.studio_phase6 as p6_mod
from fleet.core.studio_phase6 import get_agent_inbox_dir
from fleet.mcp_server import fleet_ask_custom_agent
import fleet.server as srv


def _build_minimal_flate_pdf(lines: list[str]) -> bytes:
    """Builds a valid binary PDF containing a zlib-compressed /FlateDecode text stream."""
    ops = ["BT", "/F1 12 Tf", "50 750 Td"]
    for idx, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx > 0:
            ops.append("0 -16 Td")
        ops.append(f"({escaped}) Tj")
    ops.append("ET")
    content_stream = "\n".join(ops).encode("latin-1")
    compressed = zlib.compress(content_stream)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        + f"4 0 obj << /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
        + compressed
        + b"\nendstream\nendobj\n%%EOF\n"
    )


def _make_mock_handler() -> MagicMock:
    handler = MagicMock()
    captured: dict = {}

    def _send_json(data, status=200):
        captured["status"] = status
        captured["json"] = data

    handler._send_json.side_effect = _send_json
    handler._captured = captured
    return handler


@pytest.fixture
def studio_p6_env(tmp_path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    db = FleetDatabase(tmp_path / "test_studio_phase6.db")
    custom_dir = tmp_path / "custom_agents"
    custom_dir.mkdir(parents=True, exist_ok=True)
    isolated_data_dir = tmp_path / "fleet_data"
    isolated_data_dir.mkdir(parents=True, exist_ok=True)

    overrides_file = tmp_path / "agent_overrides.json"
    sched_yaml = tmp_path / "schedules.yaml"
    sched_yaml.write_text("schedules: []\n", encoding="utf-8")
    sched_overrides = tmp_path / "schedule_overrides.json"

    registry = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=custom_dir,
        db=db,
    )
    with patch.object(registry, "_get_overrides_file", return_value=overrides_file):
        registry.discover_and_load()

    scheduler = FleetScheduler(config_dir=tmp_path, db=db, registry=registry)
    router = ApiRouter()
    registry.register_all_routes(router)

    with (
        patch.object(doc_ext, "DATA_DIR", isolated_data_dir),
        patch.object(p6_mod, "DATA_DIR", isolated_data_dir),
        patch.object(registry, "_get_overrides_file", return_value=overrides_file),
        patch.object(scheduler, "_get_overrides_file", return_value=sched_overrides),
        patch.object(srv, "db", db),
        patch.object(srv, "agent_registry", registry),
        patch("fleet.core.scheduler.get_fleet_scheduler", return_value=scheduler),
        patch("fleet.tools.system_tools.send_notification") as mock_notify,
    ):
        scheduler.reload()
        yield {
            "db": db,
            "registry": registry,
            "scheduler": scheduler,
            "router": router,
            "custom_dir": custom_dir,
            "data_dir": isolated_data_dir,
            "tmp_path": tmp_path,
            "mock_notify": mock_notify,
        }
    pb_engine._TEST_PLAYBOOKS_MEMORY = None


def test_phase6_watched_inbox_auto_ingestion_dedup_and_eventbus_handoff(studio_p6_env):
    registry = studio_p6_env["registry"]
    router = studio_p6_env["router"]
    data_dir = studio_p6_env["data_dir"]

    # Path-traversal confinement check on inbox directory resolver
    confined = get_agent_inbox_dir("auto_policy_watcher", custom_subfolder="../../../escape_attempt")
    assert confined.resolve().is_relative_to((data_dir / "user" / "inbox").resolve())

    # Create custom agent with auto_ingest_inbox=True and default_recurrence="annual"
    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "auto_policy_watcher",
            "name": "Auto Policy Inbox Watcher",
            "icon": "🛡️",
            "category": "Finance",
            "intelligence_mode": "deterministic",
            "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "agent_chat", "history_table"],
            "auto_ingest_inbox": True,
            "default_recurrence": "annual",
        },
    )
    assert h_create._captured["status"] == 200
    inbox_dir = get_agent_inbox_dir("auto_policy_watcher")
    assert inbox_dir.is_dir()

    # Drop a policy PDF into the watched inbox folder
    exp_iso = (date.today() + timedelta(days=12)).isoformat()
    pdf_bytes = _build_minimal_flate_pdf([
        "ICICI Lombard Comprehensive Motor Policy",
        "Policy No: IL-2026-77321",
        f"Expiry Date: {exp_iso}",
        "Annual Premium: Rs. 19,250.00",
    ])
    dropped_pdf = inbox_dir / "icici_motor_2026.pdf"
    dropped_pdf.write_bytes(pdf_bytes)

    # Trigger manual /documents/scan_inbox endpoint
    h_scan = _make_mock_handler()
    assert router.dispatch_post(
        h_scan,
        "/api/fleet/agents/auto_policy_watcher/documents/scan_inbox",
        {},
    ) is True
    assert h_scan._captured["status"] == 200
    scan_payload = h_scan._captured["json"]
    assert scan_payload["scan"]["ingested_documents_count"] == 1
    assert scan_payload["scan"]["committed_items_count"] >= 1
    assert not dropped_pdf.exists()
    assert any((inbox_dir / "processed").iterdir())

    entries = scan_payload["state"]["entries"]
    assert len(entries) >= 1
    assert entries[0]["data"].get("recurrence") == "annual"
    assert entries[0]["data"].get("ingestion_source") == "watched_inbox"

    # Drop identical PDF again -> SHA-256 deduplication must skip without duplicating entries
    dup_pdf = inbox_dir / "icici_motor_copy.pdf"
    dup_pdf.write_bytes(pdf_bytes)
    h_dup = _make_mock_handler()
    router.dispatch_post(
        h_dup,
        "/api/fleet/agents/auto_policy_watcher/documents/scan_inbox",
        {},
    )
    assert h_dup._captured["json"]["scan"]["ingested_documents_count"] == 0
    assert h_dup._captured["json"]["scan"]["skipped_duplicates"] == 1
    assert len(h_dup._captured["json"]["state"]["entries"]) == len(entries)

    # EventBus `gmail.paper_trail_detected` payload handoff during execute_task()
    agent = registry.get_agent("auto_policy_watcher")
    due_bill = (date.today() + timedelta(days=9)).isoformat()
    run_res = agent.execute_task(
        "run_check",
        payload={
            "subject": "Broadband Fiber Renewal Invoice #INV-9092",
            "body": f"Fiber Gigabit Plan Renewal\nDue Date: {due_bill}\nTotal Amount: Rs. 1,499.00",
        },
    )
    assert run_res["status"] == "success"
    assert run_res["metrics"]["inbox_ingested_docs"] == 1
    assert run_res["metrics"]["inbox_committed_items"] >= 1


def test_phase6_grounded_agent_chat_rag_mutations_and_mcp_tool(studio_p6_env):
    router = studio_p6_env["router"]
    db = studio_p6_env["db"]

    # Verify 12th UI block registration & prompt auto-synthesis
    assert "agent_chat" in SUPPORTED_UI_BLOCKS
    assert len(SUPPORTED_UI_BLOCKS) == 12
    synth = synthesize_agent_from_prompt(
        "Create an insurance policy tracker where I can upload PDFs and ask questions in chat",
        use_llm=False,
    )
    assert "document_vault" in synth["ui_blocks"]
    assert "agent_chat" in synth["ui_blocks"]
    assert synth["default_recurrence"] == "annual"

    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "policy_qa_sentinel",
            "name": "Policy Q&A Sentinel",
            "icon": "💬",
            "category": "Finance",
            "intelligence_mode": "deterministic",
            "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "agent_chat", "history_table"],
            "default_recurrence": "annual",
        },
    )
    assert h_create._captured["status"] == 200
    panel_html = (studio_p6_env["custom_dir"] / "policy_qa_sentinel" / "ui" / "panel.html").read_text(encoding="utf-8")
    assert "policy_qa_sentinel_chat_card" in panel_html
    assert "sendAgentChat" in panel_html

    # Upload a policy PDF with specific clause details into the agent's vault
    policy_pdf = _build_minimal_flate_pdf([
        "Tata AIG Auto Secure Motor Policy",
        "Policy No: TAIG-992811",
        "Expiry Date: 2027-01-15",
        "Premium Amount: Rs. 21,400.00",
        "Roadside Assistance Hotline: 1800-266-7780",
        "Zero Depreciation IDV Cover: Rs. 12,80,000",
    ])
    h_ext = _make_mock_handler()
    router.dispatch_post(
        h_ext,
        "/api/fleet/agents/policy_qa_sentinel/documents/extract",
        {
            "filename": "tata_aig_policy.pdf",
            "content_base64": base64.b64encode(policy_pdf).decode("ascii"),
            "auto_commit": True,
        },
    )
    assert h_ext._captured["status"] == 200

    # 1. Grounded RAG Q&A retrieving details from vaulted PDF text
    h_q = _make_mock_handler()
    router.dispatch_post(
        h_q,
        "/api/fleet/agents/policy_qa_sentinel/chat",
        {"message": "What is my Roadside Assistance Hotline and IDV Cover?"},
    )
    assert h_q._captured["status"] == 200
    ans_payload = h_q._captured["json"]
    assert "1800-266-7780" in ans_payload["answer"] or "12,80,000" in ans_payload["answer"]
    assert len(ans_payload["state"]["chat_history"]) == 1

    # 2. Natural-language ADD command
    h_add = _make_mock_handler()
    router.dispatch_post(
        h_add,
        "/api/fleet/agents/policy_qa_sentinel/chat",
        {"message": "add Home Fire Policy due 2026-12-20 for 9500"},
    )
    assert h_add._captured["status"] == 200
    assert h_add._captured["json"]["mutation"] == "add"
    home_entry = next(e for e in h_add._captured["json"]["state"]["entries"] if "Home Fire Policy" in e["title"])
    assert home_entry["due_date"] == "2026-12-20"
    assert float(home_entry["numeric_value"]) == 9500.0

    # 3. Natural-language RENEW command via MCP tool `fleet_ask_custom_agent`
    mcp_raw = fleet_ask_custom_agent("policy_qa_sentinel", "renew Home Fire Policy annual for 9900")
    mcp_res = json.loads(mcp_raw)
    assert mcp_res["status"] == "success"
    assert mcp_res["mutation"] == "renew"
    assert "2027-12-20" in mcp_res["answer"]
    assert mcp_res["kpis"]["renewals_count"] == 1

    # 4. Natural-language COMPLETE command
    h_done = _make_mock_handler()
    router.dispatch_post(
        h_done,
        "/api/fleet/agents/policy_qa_sentinel/chat",
        {"message": "complete Home Fire Policy"},
    )
    assert h_done._captured["json"]["mutation"] == "complete"
    st = db.get_custom_agent_dashboard_state("policy_qa_sentinel")
    updated_home = next(e for e in st["entries"] if "Home Fire Policy" in e["title"])
    assert updated_home["status"] == "completed"


def test_phase6_smart_recurring_cycle_roll_forward(studio_p6_env):
    router = studio_p6_env["router"]
    db = studio_p6_env["db"]

    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "recurring_bills_guard",
            "name": "Recurring Bills Guard",
            "icon": "🔄",
            "category": "Finance",
            "default_recurrence": "monthly",
        },
    )
    assert h_create._captured["status"] == 200

    # Future month-end date (Jan 31 -> Feb 28/29 calendar clamp verification)
    next_year = date.today().year + 1
    jan_end = f"{next_year}-01-31"
    rec_id = db.add_custom_agent_record(
        agent_id="recurring_bills_guard",
        title="Cloud Hosting Subscription",
        record_type="entry",
        data={"recurrence": "monthly"},
        status="warning",
        due_date=jan_end,
        numeric_value=2400.0,
    )

    h_renew = _make_mock_handler()
    router.dispatch_post(
        h_renew,
        "/api/fleet/agents/recurring_bills_guard/records/renew",
        {"record_id": rec_id, "cycle": "monthly", "numeric_value": 2550.0},
    )
    assert h_renew._captured["status"] == 200
    ren = h_renew._captured["json"]["renewed"]
    assert ren["previous_due_date"] == jan_end
    assert ren["next_due_date"].startswith(f"{next_year}-02-2")
    assert ren["numeric_value"] == 2550.0
    assert ren["renewal_count"] == 1

    state = h_renew._captured["json"]["state"]
    assert state["kpis"]["renewals_count"] == 1
    assert len(state["cycle_history"]) == 1
    assert state["cycle_history"][0]["numeric_value"] == 2400.0
    assert state["entries"][0]["status"] == "ok"


def test_phase6_outbound_action_hooks_execution(studio_p6_env):
    registry = studio_p6_env["registry"]
    db = studio_p6_env["db"]
    data_dir = studio_p6_env["data_dir"]
    mock_notify = studio_p6_env["mock_notify"]

    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "compliance_hook_sentinel",
            "name": "Compliance Hook Sentinel",
            "icon": "📋",
            "category": "Finance",
            "intelligence_mode": "deterministic",
            "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
            "outbound_actions": ["auto_create_task", "desktop_toast", "markdown_report", "emit_followup_event"],
        },
    )
    assert h_create._captured["status"] == 200
    mock_notify.reset_mock()

    agent = registry.get_agent("compliance_hook_sentinel")
    mock_bus = MagicMock()
    agent.event_bus = mock_bus

    # Seed 1 overdue item (P1) and 1 due-soon item (P2)
    db.add_custom_agent_record(
        agent_id="compliance_hook_sentinel",
        title="Car Insurance Renewal",
        record_type="entry",
        due_date=(date.today() - timedelta(days=2)).isoformat(),
        numeric_value=16500.0,
    )
    db.add_custom_agent_record(
        agent_id="compliance_hook_sentinel",
        title="Health Policy Top-Up",
        record_type="entry",
        due_date=(date.today() + timedelta(days=6)).isoformat(),
        numeric_value=8200.0,
    )

    res1 = agent.execute_task("run_check")
    assert res1["health_status"] == "warning"
    executed = res1["metrics"]["outbound_actions_executed"]
    assert "auto_create_task(2)" in executed
    assert "desktop_toast" in executed
    assert "markdown_report" in executed
    assert "emit_followup_event" in executed

    # Verify deduplicated P1 & P2 tasks in main Fleet tasks queue
    pending_tasks = [
        t for t in db.list_tasks(status="pending", limit=50)
        if t.get("assigned_agent") == "compliance_hook_sentinel"
    ]
    assert len(pending_tasks) == 2
    priorities = {t["priority"] for t in pending_tasks}
    assert priorities == {"P1", "P2"}

    # Re-running must NOT create duplicate pending tasks
    res2 = agent.execute_task("run_check")
    pending_after = [
        t for t in db.list_tasks(status="pending", limit=50)
        if t.get("assigned_agent") == "compliance_hook_sentinel"
    ]
    assert len(pending_after) == 2
    assert not any(x.startswith("auto_create_task") for x in res2["metrics"].get("outbound_actions_executed", []))

    # Verify Markdown report written strictly inside isolated DATA_DIR / "user" / "reports"
    report_fp = data_dir / "user" / "reports" / "compliance_hook_sentinel_latest.md"
    assert report_fp.is_file()
    md_text = report_fp.read_text(encoding="utf-8")
    assert "Car Insurance Renewal" in md_text
    assert "Health Policy Top-Up" in md_text

    # Verify EventBus follow-up signal & evolve persistence
    published_topics = [c.args[0] for c in mock_bus.publish.call_args_list]
    assert "studio.followup_requested" in published_topics

    h_evolve = _make_mock_handler()
    evolve_custom_agent_endpoint(
        h_evolve,
        {
            "id": "compliance_hook_sentinel",
            "outbound_actions": ["markdown_report"],
            "default_recurrence": "quarterly",
        },
    )
    assert h_evolve._captured["status"] == 200
    assert h_evolve._captured["json"]["manifest"]["outbound_actions"] == ["markdown_report"]
    assert h_evolve._captured["json"]["manifest"]["default_recurrence"] == "quarterly"


def test_phase6_multi_agent_squad_blueprints_and_1click_deploy(studio_p6_env):
    registry = studio_p6_env["registry"]
    scheduler = studio_p6_env["scheduler"]

    h_bp = _make_mock_handler()
    get_studio_blueprints_endpoint(h_bp, urllib.parse.urlparse("/api/studio/blueprints"))
    assert h_bp._captured["status"] == 200
    bp_json = h_bp._captured["json"]
    assert bp_json["total"] == 6  # Backwards-compatible starter count
    assert len(bp_json["squad_blueprints"]) == 3
    assert len(bp_json["supported_outbound_actions"]) == 4

    # Deploy 3-agent Personal CFO & Policy Squad in 1 click
    h_dep = _make_mock_handler()
    deploy_agent_squad_endpoint(h_dep, {"squad_id": "personal_cfo_compliance_squad"})
    assert h_dep._captured["status"] == 200
    dep_json = h_dep._captured["json"]
    assert dep_json["status"] == "success"
    assert dep_json["deployed_count"] == 3
    deployed_ids = [a["id"] for a in dep_json["agents"]]
    assert deployed_ids == ["cfo_doc_ingestor", "cfo_renewal_guard", "cfo_spend_analyst"]

    for aid in deployed_ids:
        assert registry.get_agent(aid) is not None
    sched_ids = {s["id"] for s in scheduler.get_schedules()}
    assert "cfo_doc_ingestor_scan_and_audit_docs" in sched_ids
    assert "cfo_renewal_guard_check_upcoming_renewals" in sched_ids
    assert "cfo_spend_analyst_synthesize_spend_digest" in sched_ids

    # Second deploy must resolve collision-safe suffixed IDs cleanly
    h_dep2 = _make_mock_handler()
    deploy_agent_squad_endpoint(h_dep2, {"squad_id": "personal_cfo_compliance_squad"})
    assert h_dep2._captured["status"] == 200
    assert [a["id"] for a in h_dep2._captured["json"]["agents"]] == [
        "cfo_doc_ingestor_2",
        "cfo_renewal_guard_2",
        "cfo_spend_analyst_2",
    ]


def test_phase6_grounded_rag_structured_markdown_and_deduplicated_formatting(studio_p6_env):
    router = studio_p6_env["router"]
    db = studio_p6_env["db"]
    data_dir = studio_p6_env["data_dir"]

    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "acko_format_sentinel",
            "name": "Acko Format Sentinel",
            "icon": "🛡️",
            "category": "Finance",
            "intelligence_mode": "deterministic",
            "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "agent_chat", "history_table"],
            "default_recurrence": "annual",
        },
    )
    assert h_create._captured["status"] == 200

    # Insert record with duplicate canonical alias keys matching real extraction payloads
    db.add_custom_agent_record(
        agent_id="acko_format_sentinel",
        title="Acko General Insurance — Welcome KINDUZ, (TS08EN7944)",
        record_type="entry",
        due_date="2026-12-12",
        numeric_value=5632.0,
        data={
            "policy_number": "DCCR10453014513/00",
            "insurer": "Acko General Insurance",
            "invoice_number": "DCCR10453014513/00",
            "reference_code": "DCCR10453014513/00",
            "counterparty": "Acko General Insurance",
            "asset": "TS08EN7944",
            "recurrence": "annual",
        },
    )

    # Create a multi-section vaulted document with timestamp/hash prefix and clause after char 1500
    vault_dir = data_dir / "user" / "agent_docs" / "acko_format_sentinel"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_file = vault_dir / "20261030_235339_148a5b0db0_Acko-20261030-policy.txt"
    filler_lines = [f"Standard Policy Schedule Section {i}: Motor Comprehensive Terms" for i in range(45)]
    doc_text = "\n".join([
        "Your car insurance policy",
        "document is here",
        "Policy Number: DCCR10453014513/00",
        *filler_lines,
        "Add-On Coverage: Engine Protect Cover — Included (Hydrostatic Lock & Oil Leakage Covered)",
    ])
    vault_file.write_text(doc_text, encoding="utf-8")

    # Ask "Do the policy protect engine?" -> must find deep Engine Protect clause, clean filename,
    # deduplicate DCCR10453014513/00, and emit structured multi-line Markdown headings & bullets
    h_q = _make_mock_handler()
    router.dispatch_post(
        h_q,
        "/api/fleet/agents/acko_format_sentinel/chat",
        {"message": "Do the policy protect engine?"},
    )
    assert h_q._captured["status"] == 200
    ans = h_q._captured["json"]["answer"]

    assert "### 📄 Vaulted Document Findings" in ans
    assert "Engine Protect Cover — Included" in ans
    assert "20261030_235339_148a5b0db0_" not in ans
    assert "`Acko-20261030-policy.txt`" in ans
    assert "document is here" not in ans

    # Record section uses clean bullets and prints DCCR10453014513/00 only once per record (not 3x!)
    assert "### 📋 Matching Tracked Records" in ans
    record_section = ans.split("### 📋 Matching Tracked Records", 1)[1]
    assert record_section.count("DCCR10453014513/00") == 1
    assert "\n- **" in ans
