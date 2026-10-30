"""
End-to-End Verification Suite for Zero-Code Agent Studio Phase 5:
Intelligent Document Ingestion & LLM Tracking Extraction
1. Pure-stdlib zero-dependency parsers for .pdf (FlateDecode + Tj/TJ), .docx, .xlsx, .csv, .ics, and .eml (with nested PDF attachment).
2. Insurance Policy PDF extraction via configured LLM (HyperscalerGateway / Antigravity) AND deterministic $0.00 offline fallback + isolated User Data Vault storage.
3. Multi-scenario extraction across 8 real-world domains (Insurance, Contracts/SaaS, Invoices/Tax, Medical Lab/Rx out-of-range biomarkers, Travel/Visa, Warranties/AMC, Syllabi/Certs, Investments/FD).
4. Creation-time document upload (`POST /api/studio/documents/analyze` -> `POST /api/settings/agents/create` seeding `initial_document` + `initial_records`).
5. Inside-agent `document_vault` runtime upload (`POST /api/fleet/agents/<id>/documents/extract` review -> `POST .../documents/commit` & `auto_commit=True`).
6. Antigravity MCP tool `fleet_extract_document_to_agent` and path-traversal / size / empty-payload security guards.
"""

from __future__ import annotations

import base64
from datetime import date, timedelta
from email.message import EmailMessage
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile
import zlib

import pytest

from fleet.api.router import ApiRouter
from fleet.api.settings_api import (
    analyze_studio_document_endpoint,
    create_new_agent_endpoint,
    get_studio_blueprints_endpoint,
)
from fleet.core.agent_studio import SUPPORTED_UI_BLOCKS
from fleet.core.database import FleetDatabase
import fleet.core.document_extractor as doc_ext
from fleet.core.document_extractor import (
    DOCUMENT_SCENARIO_PROFILES,
    extract_tracking_items_from_document,
    parse_uploaded_document,
    sanitize_upload_filename,
)
import fleet.core.playbook_engine as pb_engine
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
from fleet.mcp_server import fleet_extract_document_to_agent
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

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        + f"4 0 obj << /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
        + compressed
        + b"\nendstream\nendobj\n%%EOF\n"
    )
    return pdf


def _build_minimal_docx(paragraphs: list[str]) -> bytes:
    """Builds a valid in-memory .docx ZIP archive with word/document.xml."""
    p_xml = "".join(
        f"<w:p><w:r><w:t>{p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</w:t></w:r></w:p>"
        for p in paragraphs
    )
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{p_xml}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def _build_minimal_xlsx(rows: list[list[str]]) -> bytes:
    """Builds a valid in-memory .xlsx ZIP archive with sharedStrings.xml and sheet1.xml."""
    shared: list[str] = []
    str_to_idx: dict[str, int] = {}
    for row in rows:
        for cell in row:
            if cell not in str_to_idx:
                str_to_idx[cell] = len(shared)
                shared.append(cell)

    si_xml = "".join(f"<si><t>{s}</t></si>" for s in shared)
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{si_xml}</sst>"
    )

    row_xml_parts = []
    for r_idx, row in enumerate(rows, start=1):
        cells_xml = []
        for c_idx, cell in enumerate(row):
            col_letter = chr(ord("A") + c_idx)
            s_idx = str_to_idx[cell]
            cells_xml.append(f'<c r="{col_letter}{r_idx}" t="s"><v>{s_idx}</v></c>')
        row_xml_parts.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_xml_parts)}</sheetData></worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml", sst_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


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
def studio_p5_env(tmp_path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    db = FleetDatabase(tmp_path / "test_studio_phase5.db")
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
        patch.object(registry, "_get_overrides_file", return_value=overrides_file),
        patch.object(scheduler, "_get_overrides_file", return_value=sched_overrides),
        patch.object(srv, "db", db),
        patch.object(srv, "agent_registry", registry),
        patch("fleet.core.scheduler.get_fleet_scheduler", return_value=scheduler),
        patch("fleet.tools.system_tools.send_notification"),
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
        }
    pb_engine._TEST_PLAYBOOKS_MEMORY = None


def test_phase5_multiformat_zero_dependency_parsers(studio_p5_env):
    # 1. PDF with FlateDecode stream
    pdf_bytes = _build_minimal_flate_pdf([
        "HDFC ERGO Comprehensive Motor Insurance Policy",
        "Policy No: POL-2026-88412",
        "Expiry Date: 2026-11-20",
        "Total Premium: Rs. 16,450.00",
    ])
    parsed_pdf = parse_uploaded_document(
        filename="car_policy.pdf",
        content_base64=base64.b64encode(pdf_bytes).decode("ascii"),
    )
    assert parsed_pdf["extension"] == ".pdf"
    assert "POL-2026-88412" in parsed_pdf["extracted_text"]
    assert "2026-11-20" in parsed_pdf["extracted_text"]

    # 2. DOCX contract
    docx_bytes = _build_minimal_docx([
        "Master SaaS Subscription Agreement - Acme Cloud Enterprise",
        "Renewal Date: 2026-12-15",
        "Annual Contract Value: $4,800.00",
    ])
    parsed_docx = parse_uploaded_document(
        filename="acme_msa.docx",
        content_base64=base64.b64encode(docx_bytes).decode("ascii"),
    )
    assert parsed_docx["extension"] == ".docx"
    assert "Acme Cloud Enterprise" in parsed_docx["extracted_text"]
    assert "2026-12-15" in parsed_docx["extracted_text"]

    # 3. XLSX warranty sheet
    xlsx_bytes = _build_minimal_xlsx([
        ["Product", "Warranty Expiry", "Purchase Price", "Serial Number"],
        ["MacBook Pro M4 Max", "2027-03-18", "289000", "SN-MBP-9941"],
        ["LG OLED C4 TV", "2026-11-10", "134990", "SN-LG-4410"],
    ])
    parsed_xlsx = parse_uploaded_document(
        filename="home_warranties.xlsx",
        content_base64=base64.b64encode(xlsx_bytes).decode("ascii"),
    )
    assert parsed_xlsx["extension"] == ".xlsx"
    assert "MacBook Pro M4 Max" in parsed_xlsx["extracted_text"]
    assert "SN-MBP-9941" in parsed_xlsx["extracted_text"]

    # 4. CSV milestones
    csv_text = "Milestone,Due Date,Weight\nMidterm Distributed Systems Exam,2026-11-14,30\nFinal Capstone Submission,2026-12-08,45\n"
    parsed_csv = parse_uploaded_document(filename="cs541_syllabus.csv", text_content=csv_text)
    assert "Midterm Distributed Systems Exam" in parsed_csv["extracted_text"]

    # 5. ICS travel itinerary
    ics_text = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        "SUMMARY:Flight SQ-503 BLR to SIN\n"
        "DTSTART:20261119T063000Z\n"
        "LOCATION:Kempegowda International Airport T2\n"
        "DESCRIPTION:Booking Ref PNR-77K9Q\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )
    parsed_ics = parse_uploaded_document(filename="singapore_trip.ics", text_content=ics_text)
    assert "Flight SQ-503 BLR to SIN" in parsed_ics["extracted_text"]
    assert "2026-11-19" in parsed_ics["extracted_text"]

    # 6. EML email with nested PDF attachment
    msg = EmailMessage()
    msg["Subject"] = "Your Renewed Motor Insurance Policy Schedule"
    msg["From"] = "policies@hdfcergo.example.com"
    msg["To"] = "user@example.com"
    msg.set_content("Please find attached your renewed motor insurance policy document.")
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename="attached_policy.pdf")
    parsed_eml = parse_uploaded_document(
        filename="policy_email.eml",
        content_base64=base64.b64encode(msg.as_bytes()).decode("ascii"),
    )
    assert "Your Renewed Motor Insurance Policy Schedule" in parsed_eml["extracted_text"]
    assert "POL-2026-88412" in parsed_eml["extracted_text"]


def test_phase5_insurance_policy_pdf_llm_and_deterministic_extraction(studio_p5_env):
    target_expiry = (date.today() + timedelta(days=11)).isoformat()
    pdf_bytes = _build_minimal_flate_pdf([
        "ICICI Lombard Comprehensive Car Insurance Policy",
        "Insured Vehicle: KA-01-MJ-7788 (Hyundai Creta SX)",
        "Policy Number: IL-3001/2998877/00/000",
        f"Policy Expiry Date: {target_expiry}",
        "Gross Annual Premium: INR 21,750.00",
        "IDV Sum Insured: INR 12,50,000",
    ])
    b64_pdf = base64.b64encode(pdf_bytes).decode("ascii")

    # Mode A: Mocked Antigravity / Hyperscaler LLM returning schema-aligned JSON
    mock_llm_json = json.dumps({
        "document_summary": f"ICICI Lombard comprehensive car policy for KA-01-MJ-7788 expiring on {target_expiry}.",
        "detected_scenario": "insurance_policy",
        "items": [
            {
                "title": "Hyundai Creta KA-01-MJ-7788 Motor Policy Renewal",
                "due_date": target_expiry,
                "numeric_value": 21750.0,
                "status": "ok",
                "extra_fields": {
                    "policy_number": "IL-3001/2998877/00/000",
                    "insurer": "ICICI Lombard",
                    "vehicle_reg": "KA-01-MJ-7788",
                },
            }
        ],
    })
    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
        mock_complete.return_value = {
            "text": f"```json\n{mock_llm_json}\n```",
            "provider": "Google Antigravity (Native CLI)",
            "model": "gemini-3.8-flash-low",
            "tokens_used": 412,
        }
        res_llm = extract_tracking_items_from_document(
            filename="creta_insurance_2026.pdf",
            content_base64=b64_pdf,
            agent_id="car_insurance_guard",
            agent_name="Car Insurance Guard",
            provider="antigravity",
            model="gemini-3.8-flash-low",
        )

    assert res_llm["status"] == "ok"
    assert res_llm["detected_scenario"] == "insurance_policy"
    assert res_llm["engine_used"] == "Google Antigravity (Native CLI)"
    assert res_llm["model_used"] == "gemini-3.8-flash-low"
    assert res_llm["items_count"] == 1
    item = res_llm["items"][0]
    assert item["title"] == "Hyundai Creta KA-01-MJ-7788 Motor Policy Renewal"
    assert item["due_date"] == target_expiry
    assert item["numeric_value"] == 21750.0
    assert item["extra_fields"]["policy_number"] == "IL-3001/2998877/00/000"
    assert item["extra_fields"]["source_document"] == "creta_insurance_2026.pdf"

    # Verify isolated User Data Vault storage
    vault_rel = res_llm["vault"]["vault_rel_path"]
    assert "user/agent_docs/car_insurance_guard/" in vault_rel
    vault_abs = studio_p5_env["data_dir"] / Path(vault_rel.replace("fleet/data/", ""))
    assert (studio_p5_env["data_dir"] / "user" / "agent_docs" / "car_insurance_guard").exists()

    # Mode B: Offline Deterministic $0.00 Fallback
    res_det = extract_tracking_items_from_document(
        filename="creta_insurance_2026.pdf",
        content_base64=b64_pdf,
        agent_id="car_insurance_guard",
        provider="deterministic",
    )
    assert res_det["status"] == "ok"
    assert res_det["detected_scenario"] == "insurance_policy"
    assert res_det["items_count"] >= 1
    det_item = res_det["items"][0]
    assert det_item["due_date"] == target_expiry
    assert det_item["numeric_value"] == 21750.0
    assert "IL-3001/2998877/00/000" in json.dumps(det_item["extra_fields"])


def test_phase5_multi_domain_scenarios_lab_contract_syllabus_travel_fd(studio_p5_env):
    assert len(DOCUMENT_SCENARIO_PROFILES) == 8

    # 1. Medical Lab Report with out-of-range biomarkers
    lab_text = (
        "Diagnostic Clinical Biochemistry Report\n"
        "Patient: Jordan Taylor | Follow-up Date: 2026-11-28\n"
        "HbA1c : 6.9 % [4.0 - 5.6]\n"
        "Fasting Glucose : 94 mg/dL [70 - 100]\n"
        "Triglycerides : 228 mg/dL [40 - 150]\n"
    )
    res_lab = extract_tracking_items_from_document(
        filename="annual_blood_panel.txt",
        text_content=lab_text,
        provider="deterministic",
    )
    assert res_lab["detected_scenario"] == "medical_lab_rx"
    titles_joined = " | ".join(it["title"] for it in res_lab["items"])
    assert "HbA1c" in titles_joined
    assert "Triglycerides" in titles_joined

    # 2. Multi-row Academic Syllabus / Certification CSV
    syllabus_csv = (
        "Assignment,Due Date,Points\n"
        "AWS Solutions Architect Pro Renewal Exam,2026-11-18,100\n"
        "System Design Architecture Paper,2026-12-03,50\n"
    )
    res_syl = extract_tracking_items_from_document(
        filename="cert_and_course_schedule.csv",
        text_content=syllabus_csv,
        provider="deterministic",
    )
    assert res_syl["detected_scenario"] == "syllabus_project_cert"
    assert res_syl["items_count"] == 2
    assert res_syl["items"][0]["due_date"] == "2026-11-18"

    # 3. Fixed Deposit / Bond Maturity Certificate
    fd_text = (
        "SBI Term Fixed Deposit Receipt\n"
        "FD Account No: FD-77889911\n"
        "Maturity Date: 2027-01-25\n"
        "Maturity Value: INR 5,42,800.00\n"
        "Interest Rate: 7.35% p.a.\n"
    )
    res_fd = extract_tracking_items_from_document(
        filename="sbi_fd_receipt.txt",
        text_content=fd_text,
        provider="deterministic",
    )
    assert res_fd["detected_scenario"] == "investment_fd_bond"
    assert res_fd["items"][0]["due_date"] == "2027-01-25"
    assert res_fd["items"][0]["numeric_value"] == 542800.0


def test_phase5_studio_creation_workflow_from_uploaded_document(studio_p5_env):
    db = studio_p5_env["db"]
    registry = studio_p5_env["registry"]

    # 1. Verify GET /api/studio/blueprints exposes 11 UI blocks (including document_vault) & 8 document scenarios
    assert "document_vault" in SUPPORTED_UI_BLOCKS
    h_bp = _make_mock_handler()
    get_studio_blueprints_endpoint(h_bp, {})
    bp_data = h_bp._captured["json"]
    assert bp_data["total"] == 6  # Backwards compatibility preserved
    assert any(b["id"] == "document_vault" for b in bp_data["supported_ui_blocks"])
    assert len(bp_data["document_scenarios"]) == 8

    # 2. Step 1: Upload Insurance Policy PDF to POST /api/studio/documents/analyze
    due_soon = (date.today() + timedelta(days=9)).isoformat()
    policy_pdf = _build_minimal_flate_pdf([
        "Bajaj Allianz Two-Wheeler Package Policy",
        "Policy Number: BA-TW-55443322",
        f"Expiry Date: {due_soon}",
        "Total Premium: INR 3,420.00",
    ])
    h_an = _make_mock_handler()
    analyze_studio_document_endpoint(
        h_an,
        {
            "filename": "bike_policy_2026.pdf",
            "content_base64": base64.b64encode(policy_pdf).decode("ascii"),
            "provider": "deterministic",
        },
    )
    assert h_an._captured["status"] == 200
    an_payload = h_an._captured["json"]
    assert an_payload["status"] == "ok"
    spec = an_payload["spec"]
    extraction = an_payload["extraction"]

    assert "document_vault" in spec["ui_blocks"]
    assert "_doc_vault_card" in spec["panel_html"]
    assert extraction["detected_scenario"] == "insurance_policy"
    assert extraction["items_count"] >= 1

    # 3. Launch new agent via POST /api/settings/agents/create with pre-staged `initial_document` + `initial_records`
    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            **spec,
            "id": "bike_policy_sentinel",
            "run_immediately": True,
            "initial_document": {
                "filename": extraction["filename"],
                "detected_scenario": extraction["detected_scenario"],
                "scenario_title": extraction["scenario_profile"]["title"],
                "document_summary": extraction["document_summary"],
                "engine_used": extraction["engine_used"],
                "model_used": extraction["model_used"],
                "items_count": len(extraction["items"]),
            },
            "initial_records": extraction["items"],
        },
    )
    assert h_create._captured["status"] == 200
    created_resp = h_create._captured["json"]
    assert created_resp["status"] == "success"
    assert created_resp["agent_id"] == "bike_policy_sentinel"
    assert created_resp["seeded_records_count"] >= 1

    agent = registry.get_agent("bike_policy_sentinel")
    assert agent is not None
    state = db.get_custom_agent_dashboard_state("bike_policy_sentinel", manifest=agent.get_ui_manifest())
    assert state["kpis"]["total_entries"] >= 1
    assert state["kpis"]["documents_count"] == 1
    assert state["kpis"]["due_soon"] >= 1
    assert state["entries"][0]["data"]["source_document"] == "bike_policy_2026.pdf"


def test_phase5_inside_agent_document_upload_review_commit_and_autocommit(studio_p5_env):
    router = studio_p5_env["router"]
    db = studio_p5_env["db"]

    # Create a Contract & Renewal Sentinel agent
    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "contract_vault_agent",
            "name": "Contract & Lease Sentinel",
            "icon": "📑",
            "category": "Finance",
            "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "countdown_cards", "history_table"],
            "run_immediately": False,
        },
    )
    assert h_create._captured["status"] == 200

    # 1. Interactive Extract (auto_commit=False)
    lease_due = (date.today() + timedelta(days=14)).isoformat()
    lease_docx = _build_minimal_docx([
        "Residential Apartment Lease Renewal Addendum",
        "Contract Reference: LEASE-BLR-402",
        f"Renewal Notice Deadline: {lease_due}",
        "Monthly Rent Amount: INR 48,000.00",
    ])
    h_ext = _make_mock_handler()
    dispatched = router.dispatch_post(
        h_ext,
        "/api/fleet/agents/contract_vault_agent/documents/extract",
        {
            "filename": "apartment_lease_402.docx",
            "content_base64": base64.b64encode(lease_docx).decode("ascii"),
            "auto_commit": False,
            "provider": "deterministic",
        },
    )
    assert dispatched is True
    assert h_ext._captured["status"] == 200
    ext_resp = h_ext._captured["json"]
    assert ext_resp["status"] == "success"
    assert ext_resp["auto_committed"] is False
    assert ext_resp["committed_count"] == 0
    assert ext_resp["state"]["kpis"]["documents_count"] == 1
    assert ext_resp["state"]["kpis"]["total_entries"] == 0
    assert len(ext_resp["extraction"]["items"]) >= 1

    # 2. User edits title & commits selected items via POST /documents/commit
    candidate = dict(ext_resp["extraction"]["items"][0])
    candidate["title"] = "Apt 402 Lease Renewal Notice (Edited)"
    candidate["numeric_value"] = 48500.0

    h_com = _make_mock_handler()
    router.dispatch_post(
        h_com,
        "/api/fleet/agents/contract_vault_agent/documents/commit",
        {
            "doc_record_id": ext_resp["doc_record_id"],
            "source_document": "apartment_lease_402.docx",
            "items": [candidate],
        },
    )
    assert h_com._captured["status"] == 200
    com_resp = h_com._captured["json"]
    assert com_resp["committed_count"] == 1
    assert com_resp["state"]["kpis"]["total_entries"] == 1
    assert com_resp["state"]["entries"][0]["title"] == "Apt 402 Lease Renewal Notice (Edited)"
    assert com_resp["state"]["entries"][0]["numeric_value"] == 48500.0
    assert com_resp["state"]["entries"][0]["data"]["source_document"] == "apartment_lease_402.docx"

    # 3. Auto-Commit Upload (auto_commit=True)
    saas_pdf = _build_minimal_flate_pdf([
        "Cloudflare Pro Annual Invoice & Subscription Renewal",
        "Invoice No: INV-CF-9012",
        "Due Date: 2026-12-01",
        "Amount Due: $240.00",
    ])
    h_auto = _make_mock_handler()
    router.dispatch_post(
        h_auto,
        "/api/fleet/agents/contract_vault_agent/documents/extract",
        {
            "filename": "cloudflare_renewal.pdf",
            "content_base64": base64.b64encode(saas_pdf).decode("ascii"),
            "auto_commit": True,
            "provider": "deterministic",
        },
    )
    assert h_auto._captured["status"] == 200
    auto_resp = h_auto._captured["json"]
    assert auto_resp["auto_committed"] is True
    assert auto_resp["committed_count"] >= 1
    st_final = db.get_custom_agent_dashboard_state("contract_vault_agent")
    assert st_final["kpis"]["documents_count"] == 2
    assert st_final["kpis"]["total_entries"] >= 2


def test_phase5_mcp_tool_extract_document_to_agent_and_security_guards(studio_p5_env):
    router = studio_p5_env["router"]
    tmp_path = studio_p5_env["tmp_path"]

    # Create custom agent
    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            "id": "mcp_policy_tracker",
            "name": "MCP Policy Tracker",
            "icon": "🛡️",
            "intelligence_mode": "deterministic",
            "run_immediately": False,
        },
    )
    assert h_create._captured["status"] == 200

    # Write a real PDF file on disk and ingest via MCP tool `fleet_extract_document_to_agent`
    local_pdf = tmp_path / "health_floater_2026.pdf"
    local_pdf.write_bytes(
        _build_minimal_flate_pdf([
            "Star Health Family Floater Policy",
            "Policy No: SH-FF-9001122",
            "Renewal Date: 2026-12-22",
            "Annual Premium: INR 28,900.00",
        ])
    )
    mcp_res_raw = fleet_extract_document_to_agent(
        agent_id="mcp_policy_tracker",
        file_path=str(local_pdf),
        extraction_hint="Extract health policy renewal date and annual premium",
        auto_commit=True,
    )
    mcp_res = json.loads(mcp_res_raw)
    assert mcp_res["status"] == "success"
    assert mcp_res["committed_count"] >= 1
    assert mcp_res["kpis"]["total_entries"] >= 1
    assert mcp_res["kpis"]["documents_count"] == 1

    # Security guards: path traversal filename sanitization & empty upload rejection
    assert sanitize_upload_filename("../../etc/passwd") == "passwd.txt"
    assert sanitize_upload_filename("..\\..\\secret\\my policy 2026.PDF") == "my_policy_2026.pdf"

    h_bad = _make_mock_handler()
    router.dispatch_post(
        h_bad,
        "/api/fleet/agents/mcp_policy_tracker/documents/extract",
        {"filename": "empty.pdf", "content_base64": ""},
    )
    assert h_bad._captured["status"] == 400
    assert h_bad._captured["json"]["status"] == "error"
