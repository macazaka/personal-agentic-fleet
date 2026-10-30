"""
End-to-End Verification Suite for Multi-Attachment LLM-Guided Agent Creation Workflow:
1. Connected AFCC LLM resolution (`resolve_afcc_connected_llm`) honoring SQLite settings (`default_provider`, `default_model`) & `GET /api/studio/blueprints`.
2. Holistic multi-attachment analysis via `POST /api/studio/documents/analyze` with AFCC's connected `HyperscalerGateway` (`max_prompt_chars=42000`), cross-document synthesis, and per-attachment item completeness backfilling.
3. Multi-domain cross-scenario synthesis (e.g. Medical Lab Report + Overdue Invoice with URL + Device Warranty), merged typed schema fields, urgent findings (`overdue`, `<=30d`, clinical biomarkers), auto-activated outbound hooks, `step_guidance` (Steps 1..4), and `guided_actions`.
4. End-to-end `POST /api/settings/agents/create` with `initial_documents` + `initial_records`: vault promotion from `studio_staging` into `user/agent_docs/<agent_id>/`, path-confinement security check, `doc_record_id` linkage, and immediate Phase 6 `agent_chat` grounded RAG Q&A across all uploaded attachments.
5. MCP tool `fleet_create_agent_from_documents` (`auto_create=False` & `auto_create=True`) and `MAX_MULTI_ATTACHMENTS` validation guard.
"""

from __future__ import annotations

import base64
from datetime import date, timedelta
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
from fleet.core.database import FleetDatabase
import fleet.core.document_extractor as doc_ext
from fleet.core.document_extractor import (
    MAX_MULTI_ATTACHMENTS,
    promote_staged_document_to_agent_vault,
    resolve_afcc_connected_llm,
)
import fleet.core.playbook_engine as pb_engine
from fleet.core.registry import AgentRegistry
from fleet.core.scheduler import FleetScheduler
import fleet.core.studio_phase6 as p6_mod
from fleet.mcp_server import fleet_create_agent_from_documents
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
def multi_doc_env(tmp_path):
    pb_engine._TEST_PLAYBOOKS_MEMORY = None
    db = FleetDatabase(tmp_path / "test_multi_doc_studio.db")
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


def test_multi_doc_connected_llm_resolution_and_blueprints_exposure(multi_doc_env):
    db = multi_doc_env["db"]
    db.set_setting("default_provider", "anthropic")
    db.set_setting("default_model", "claude-3-7-sonnet-latest")

    conn = resolve_afcc_connected_llm(provider="auto")
    assert conn["provider"] == "anthropic"
    assert conn["model"] == "claude-3-7-sonnet-latest"

    import urllib.parse
    h_bp = _make_mock_handler()
    get_studio_blueprints_endpoint(h_bp, urllib.parse.urlparse("/api/studio/blueprints"))
    assert h_bp._captured["status"] == 200
    bp_json = h_bp._captured["json"]
    assert "connected_llm" in bp_json
    assert bp_json["connected_llm"]["provider"] == "anthropic"
    assert bp_json["connected_llm"]["model"] == "claude-3-7-sonnet-latest"


def test_multi_attachment_llm_holistic_analysis_and_per_doc_backfill(multi_doc_env):
    exp_car = (date.today() + timedelta(days=14)).isoformat()
    exp_home = (date.today() + timedelta(days=65)).isoformat()
    exp_bike = (date.today() + timedelta(days=22)).isoformat()

    pdf_bytes = _build_minimal_flate_pdf([
        "MOTOR INSURANCE POLICY SCHEDULE",
        "Policy Number: POL-CAR-9981",
        "Insurer: HDFC ERGO General Insurance",
        "Insured Vehicle: Hyundai Creta KA-01-MN-4455",
        f"Expiry Date: {exp_car}",
        "Annual Premium: 18500.00",
    ])
    docx_bytes = _build_minimal_docx([
        "HOME SHIELD COMPREHENSIVE INSURANCE POLICY",
        "Policy No: POL-HOME-4420",
        "Provider: ICICI Lombard",
        f"Renewal Due Date: {exp_home}",
        "Total Premium: 12400.00",
    ])
    csv_text = (
        "title,policy_number,due_date,numeric_value\n"
        f"Royal Enfield Classic 350 Policy,POL-BIKE-7712,{exp_bike},4200.00\n"
    )

    mock_llm_response = {
        "cross_document_summary": (
            "Unified 3 family motor and home insurance schedules (HDFC ERGO Car, ICICI Lombard Home, "
            "and Royal Enfield Two-Wheeler) with 2 renewals due within 30 days."
        ),
        "per_document_summaries": [
            {
                "filename": "car_policy.pdf",
                "detected_scenario": "insurance_policy",
                "summary": f"Hyundai Creta motor policy POL-CAR-9981 expiring {exp_car}.",
            },
            {
                "filename": "home_policy.docx",
                "detected_scenario": "insurance_policy",
                "summary": f"Home Shield policy POL-HOME-4420 renewing {exp_home}.",
            },
        ],
        "suggested_agent": {
            "name": "Family Motor & Home Policy Guard",
            "icon": "🛡️",
            "category": "Finance",
            "archetype": "tracker",
            "description": "Monitors car, bike, and home insurance renewals across 3 policy attachments.",
            "fields": [
                {"key": "title", "label": "Policy / Asset", "type": "text", "placeholder": "e.g. Car Policy"},
                {"key": "policy_number", "label": "Policy Number", "type": "text", "placeholder": "POL-..."},
                {"key": "insurer_provider", "label": "Insurer", "type": "text", "placeholder": "HDFC ERGO"},
                {"key": "due_date", "label": "Expiry Date", "type": "date", "placeholder": "YYYY-MM-DD"},
                {"key": "numeric_value", "label": "Annual Premium", "type": "number", "placeholder": "0.00"},
            ],
            "ui_blocks": [
                "alert_banner",
                "kpi_row",
                "document_vault",
                "quick_capture_bar",
                "countdown_cards",
                "agent_chat",
                "history_table",
            ],
            "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],
            "schedule_cadence": "daily_morning",
            "default_recurrence": "annual",
            "outbound_actions": ["auto_create_task", "desktop_toast", "markdown_report"],
            "event_triggers": ["gmail.paper_trail_detected"],
            "system_prompt": "Track all 3 motor and home insurance policies and alert 15 days prior to expiry.",
        },
        "workflow_guidance": {
            "headline": "Unified Family Insurance Sentinel from 3 Attachments",
            "rationale": "Combined PDF, DOCX, and CSV policy schedules into an annual roll-forward tracker.",
            "urgent_findings": [
                f"Hyundai Creta policy POL-CAR-9981 expires in 14 days ({exp_car}) — enabled urgent toast & P1 task hooks."
            ],
            "step_guidance": {
                "step_1": "Step 1: Named 'Family Motor & Home Policy Guard' for your 3 uploaded policies.",
                "step_2": "Step 2: Enabled event_bus:publish alongside SQLite read/write for urgent 14-day expiry alerts.",
                "step_3": "Step 3: Configured 5 policy fields, annual recurrence, and Gmail paper-trail auto-ingestion.",
                "step_4": "Step 4: Ready to vault 3 attachments and seed all extracted policy items.",
            },
        },
        # Intentionally omit bike_renewals.csv item here to verify per-attachment deterministic backfill!
        "items": [
            {
                "source_document": "car_policy.pdf",
                "title": "Hyundai Creta Motor Insurance (KA-01-MN-4455)",
                "due_date": exp_car,
                "numeric_value": 18500.0,
                "confidence": "high",
                "extra_fields": {
                    "policy_number": "POL-CAR-9981",
                    "insurer_provider": "HDFC ERGO",
                },
            },
            {
                "source_document": "home_policy.docx",
                "title": "ICICI Lombard Home Shield Policy",
                "due_date": exp_home,
                "numeric_value": 12400.0,
                "confidence": "high",
                "extra_fields": {
                    "policy_number": "POL-HOME-4420",
                    "insurer_provider": "ICICI Lombard",
                },
            },
        ],
    }

    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
        mock_complete.return_value = {
            "status": "SUCCESS",
            "provider": "Google Gemini API",
            "model": "gemini-2.5-flash",
            "tokens_used": 940,
            "text": json.dumps(mock_llm_response),
        }

        h_an = _make_mock_handler()
        analyze_studio_document_endpoint(
            h_an,
            {
                "documents": [
                    {
                        "filename": "car_policy.pdf",
                        "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                    {
                        "filename": "home_policy.docx",
                        "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
                    },
                    {
                        "filename": "bike_renewals.csv",
                        "text_content": csv_text,
                    },
                ],
                "provider": "google",
            },
        )

    assert h_an._captured["status"] == 200
    res = h_an._captured["json"]

    # Confirm HyperscalerGateway was invoked with expanded max_prompt_chars=42000 containing all 3 attachments
    assert mock_complete.called
    call_kwargs = mock_complete.call_args.kwargs
    assert call_kwargs["max_prompt_chars"] == 42000
    assert "ATTACHMENT 1 of 3: car_policy.pdf" in call_kwargs["prompt"]
    assert "ATTACHMENT 2 of 3: home_policy.docx" in call_kwargs["prompt"]
    assert "ATTACHMENT 3 of 3: bike_renewals.csv" in call_kwargs["prompt"]

    assert res["attachments_count"] == 3
    assert len(res["documents"]) == 3
    assert res["connected_llm"]["engine_used"] == "Google Gemini API"
    assert res["connected_llm"]["model_used"] == "gemini-2.5-flash"

    spec = res["spec"]
    assert spec["name"] == "Family Motor & Home Policy Guard"
    assert spec["default_recurrence"] == "annual"
    assert spec["auto_ingest_inbox"] is True
    assert "document_vault" in spec["ui_blocks"]
    assert "agent_chat" in spec["ui_blocks"]
    assert "auto_create_task" in spec["outbound_actions"]
    assert "desktop_toast" in spec["outbound_actions"]
    assert "gmail.paper_trail_detected" in spec["event_triggers"]

    # Verify all 3 documents contributed items (2 from LLM + 1 backfilled from bike_renewals.csv!)
    items = res["extraction"]["items"]
    assert len(items) >= 3
    sources = {it["extra_fields"]["source_document"] for it in items}
    assert {"car_policy.pdf", "home_policy.docx", "bike_renewals.csv"}.issubset(sources)

    guidance = res["workflow_guidance"]
    assert guidance["headline"] == "Unified Family Insurance Sentinel from 3 Attachments"
    assert set(guidance["step_guidance"].keys()) == {"step_1", "step_2", "step_3", "step_4"}
    assert len(guidance["urgent_findings"]) >= 1


def test_multi_domain_cross_scenario_urgent_findings_and_guided_actions(multi_doc_env):
    overdue_dt = (date.today() - timedelta(days=5)).isoformat()
    soon_dt = (date.today() + timedelta(days=10)).isoformat()
    warranty_dt = (date.today() + timedelta(days=19)).isoformat()

    lab_report = (
        "DIAGNOSTIC PATHOLOGY LAB REPORT\n"
        f"Follow-Up Test Due Date: {soon_dt}\n"
        "HbA1c: 7.4 % (Reference Range: 4.0 - 5.6 %) [HIGH]\n"
        "LDL Cholesterol: 162 mg/dL (Reference Range: 0 - 100 mg/dL) [ABNORMAL]\n"
    )
    overdue_invoice = (
        "TAX INVOICE & BILLING STATEMENT\n"
        "Invoice No: INV-2026-8841\n"
        "Vendor: City Specialty Clinic\n"
        f"Payment Due Date: {overdue_dt}\n"
        "Amount Payable: 3850.00\n"
        "Payment Portal: https://pay.cityclinic.example/invoices/8841\n"
    )
    warranty_docx = _build_minimal_docx([
        "EXTENDED WARRANTY & AMC CERTIFICATE",
        "Product: ResMed AirSense 11 CPAP Unit",
        "Serial Number: SN-RM-99201",
        f"Warranty Expiry Date: {warranty_dt}",
        "Purchase Value: 64000.00",
    ])

    h_an = _make_mock_handler()
    analyze_studio_document_endpoint(
        h_an,
        {
            "documents": [
                {"filename": "blood_panel_report.txt", "text_content": lab_report},
                {"filename": "clinic_invoice_8841.txt", "text_content": overdue_invoice},
                {
                    "filename": "cpap_warranty.docx",
                    "content_base64": base64.b64encode(warranty_docx).decode("ascii"),
                },
            ],
            "provider": "deterministic",
        },
    )

    assert h_an._captured["status"] == 200
    res = h_an._captured["json"]
    assert res["attachments_count"] == 3

    guidance = res["workflow_guidance"]
    assert guidance["is_multi_domain"] is True
    assert len(guidance["detected_domains"]) >= 2
    assert guidance["overdue_count"] >= 1
    assert guidance["due_soon_count"] >= 1

    urgent_joined = " ".join(guidance["urgent_findings"]).lower()
    assert "overdue" in urgent_joined
    assert "deadline" in urgent_joined or "clinical" in urgent_joined

    # Because overdue / <=30d items exist, spec must auto-act with proactive alert hooks + event_bus:publish
    spec = res["spec"]
    assert "auto_create_task" in spec["outbound_actions"]
    assert "desktop_toast" in spec["outbound_actions"]
    assert "event_bus:publish" in spec["permissions"]
    assert len(spec["fields"]) >= 4


def test_end_to_end_multi_doc_agent_creation_vault_promotion_and_grounded_rag_chat(multi_doc_env):
    router = multi_doc_env["router"]
    registry = multi_doc_env["registry"]
    data_dir = multi_doc_env["data_dir"]

    # Security confinement check: path traversal outside user/agent_docs must return ""
    escaped = promote_staged_document_to_agent_vault("../../outside_secret.txt", "safe_agent")
    assert escaped == ""

    due_1 = (date.today() + timedelta(days=18)).isoformat()
    due_2 = (date.today() + timedelta(days=45)).isoformat()

    doc_a = (
        "CLOUD HOSTING ENTERPRISE AGREEMENT\n"
        "Contract ID: MSA-AWS-2026\n"
        "Support Escalation Pin: PIN-7749-OMEGA\n"
        f"Renewal Date: {due_1}\n"
        "Annual Commitment: 24000.00\n"
    )
    doc_b = (
        "DOMAIN & SSL RENEWAL SCHEDULE\n"
        "Primary Domain: api.fleetcontrol.example\n"
        "DNS Registrar Secret Code: REG-ALPHA-5521\n"
        f"Expiry Date: {due_2}\n"
        "Renewal Fee: 1850.00\n"
    )

    h_an = _make_mock_handler()
    analyze_studio_document_endpoint(
        h_an,
        {
            "documents": [
                {"filename": "aws_enterprise_msa.txt", "text_content": doc_a},
                {"filename": "domain_ssl_schedule.txt", "text_content": doc_b},
            ],
            "provider": "deterministic",
        },
    )
    assert h_an._captured["status"] == 200
    analyzed = h_an._captured["json"]
    spec = analyzed["spec"]

    # Simulate frontend submitCreateAgentWizard sending initial_documents + initial_records
    initial_documents = [
        {
            "filename": d["filename"],
            "detected_scenario": d["detected_scenario"],
            "scenario_title": d["scenario_profile"]["title"],
            "scenario_icon": d["scenario_profile"]["icon"],
            "document_summary": d["document_summary"],
            "engine_used": d["engine_used"],
            "model_used": d["model_used"],
            "items_count": d["items_count"],
            "vault_rel_path": d["vault"]["vault_rel_path"],
            "sha256": d["vault"]["sha256"],
        }
        for d in analyzed["documents"]
    ]

    h_create = _make_mock_handler()
    create_new_agent_endpoint(
        h_create,
        {
            **spec,
            "id": "infra_contracts_hub",
            "name": "Infra Contracts & Domains Hub",
            "intelligence_mode": "deterministic",
            "initial_documents": initial_documents,
            "initial_records": analyzed["extraction"]["items"],
            "run_immediately": True,
        },
    )
    assert h_create._captured["status"] == 200
    created = h_create._captured["json"]
    assert created["agent_id"] == "infra_contracts_hub"
    assert created["seeded_documents_count"] == 2
    assert created["seeded_records_count"] >= 2

    # Register dynamic routes for the newly created agent
    registry.register_all_routes(router)

    # Verify both staged attachments were promoted into user/agent_docs/infra_contracts_hub/
    promoted_dir = data_dir / "user" / "agent_docs" / "infra_contracts_hub"
    assert promoted_dir.is_dir()
    promoted_files = list(promoted_dir.iterdir())
    assert len(promoted_files) == 2

    # Inspect live agent state
    db = multi_doc_env["db"]
    agent = registry.get_agent("infra_contracts_hub")
    assert agent is not None
    state = db.get_custom_agent_dashboard_state("infra_contracts_hub", manifest=agent.get_ui_manifest())
    assert state["kpis"]["documents_count"] == 2
    assert len(state["documents"]) == 2
    entries = state.get("entries") or []
    assert len(entries) >= 2
    for rec in entries:
        assert rec["data"].get("source_document") in ("aws_enterprise_msa.txt", "domain_ssl_schedule.txt")
        assert int(rec["data"].get("doc_record_id") or 0) > 0

    # Ask grounded RAG question over the promoted multi-attachment vault via Phase 6 agent_chat!
    h_chat = _make_mock_handler()
    assert router.dispatch_post(
        h_chat,
        "/api/fleet/agents/infra_contracts_hub/chat",
        {"message": "What is the Support Escalation Pin and DNS Registrar Secret Code in my documents?"},
    )
    assert h_chat._captured["status"] == 200
    chat_res = h_chat._captured["json"]
    # Grounded RAG snippet retrieval must read the promoted vaulted files directly
    assert "PIN-7749-OMEGA" in chat_res["answer"] or "REG-ALPHA-5521" in chat_res["answer"]


def test_mcp_create_agent_from_documents_and_attachment_limit_guard(multi_doc_env):
    tmp_path = multi_doc_env["tmp_path"]

    f1 = tmp_path / "fd_certificate_sbi.txt"
    f1.write_text(
        "FIXED DEPOSIT RECEIPT\nBank: State Bank of India\nFD Account: FD-88012\n"
        f"Maturity Date: {(date.today() + timedelta(days=25)).isoformat()}\nMaturity Amount: 150000.00\n",
        encoding="utf-8",
    )
    f2 = tmp_path / "bond_allotment_rbi.txt"
    f2.write_text(
        "SOVEREIGN GOLD BOND CERTIFICATE\nIssuer: Reserve Bank of India\nCertificate: SGB-2026-09\n"
        f"Maturity Date: {(date.today() + timedelta(days=120)).isoformat()}\nPrincipal Value: 75000.00\n",
        encoding="utf-8",
    )

    # 1. Preview-only mode (auto_create=False)
    preview_raw = fleet_create_agent_from_documents(
        file_paths=[str(f1), str(f2)],
        provider="deterministic",
        auto_create=False,
    )
    preview_data = json.loads(preview_raw)
    assert preview_data["status"] == "analyzed"
    assert preview_data["attachments_count"] == 2
    assert "workflow_guidance" in preview_data

    # 2. Full creation mode (auto_create=True)
    create_raw = fleet_create_agent_from_documents(
        file_paths=[str(f1), str(f2)],
        custom_id="mcp_wealth_vault",
        provider="deterministic",
        auto_create=True,
    )
    create_data = json.loads(create_raw)
    assert create_data["status"] == "success"
    assert create_data["agent_id"] == "mcp_wealth_vault"
    assert create_data["seeded_documents_count"] == 2
    assert create_data["seeded_records_count"] >= 2

    # 3. Enforce MAX_MULTI_ATTACHMENTS guard on HTTP endpoint
    too_many = [
        {"filename": f"doc_{i}.txt", "text_content": f"Item {i} due 2026-12-01 amount 100"}
        for i in range(MAX_MULTI_ATTACHMENTS + 1)
    ]
    h_err = _make_mock_handler()
    analyze_studio_document_endpoint(h_err, {"documents": too_many, "provider": "deterministic"})
    assert h_err._captured["status"] == 400
    assert str(MAX_MULTI_ATTACHMENTS) in h_err._captured["json"]["message"]


def test_live_server_registry_db_wiring_and_winerror_206_long_prompt_guard(multi_doc_env):
    """
    Regression test for:
    1. 'Database unavailable' inside live agent Document Upload & AI Tracking Extractor when AgentRegistry
       was initialized without explicit db= (now wired in fleet.server AND auto-resolved via _resolve_db()).
    2. Inside-agent multi-file extraction (`POST /api/fleet/agents/<id>/documents/extract` with `documents=[...]`).
    3. Windows CreateProcessW [WinError 206] command-line length overflow (>27,000 chars) in _call_antigravity_cli.
    """
    assert srv.agent_registry.db is not None

    tmp_path = multi_doc_env["tmp_path"]
    db = multi_doc_env["db"]
    no_db_custom_dir = tmp_path / "custom_no_explicit_db"
    no_db_custom_dir.mkdir(parents=True, exist_ok=True)
    overrides_f = tmp_path / "no_db_overrides.json"

    # Instantiate AgentRegistry with db=None while srv.db is active — _resolve_db() must bind srv.db
    reg_no_db = AgentRegistry(
        agents_dir=Path(__file__).parent.parent / "fleet" / "agents",
        custom_agents_dir=no_db_custom_dir,
        db=None,
    )
    with patch.object(reg_no_db, "_get_overrides_file", return_value=overrides_f):
        reg_no_db.create_custom_agent(
            agent_id="acko_policy_tracker",
            name="Acko Insurance Tracker",
            icon="🛡️",
            ui_blocks=["alert_banner", "kpi_row", "document_vault", "agent_chat", "history_table"],
            intelligence_mode="deterministic",
        )
        local_router = ApiRouter()
        reg_no_db.register_all_routes(local_router)

        acko_pdf = _build_minimal_flate_pdf([
            "ACKO GENERAL INSURANCE MOTOR POLICY",
            "Policy Number: ACKO-2026-377F2",
            f"Expiry Date: {(date.today() + timedelta(days=28)).isoformat()}",
            "Total Premium: 8950.00",
        ])
        addon_txt = "Zero Dep Addon Policy: ACKO-ZD-991\nRenewal Date: 2027-01-19\nPremium: 1450.00\n"

        # Single-file extraction (exact flow from user screenshot)
        h_single = _make_mock_handler()
        assert local_router.dispatch_post(
            h_single,
            "/api/fleet/agents/acko_policy_tracker/documents/extract",
            {
                "filename": "Acko-20261030-377f2-0565288d3bbd.pdf",
                "content_base64": base64.b64encode(acko_pdf).decode("ascii"),
                "auto_commit": False,
            },
        )
        assert h_single._captured["status"] == 200
        assert h_single._captured["json"]["status"] == "success"
        assert h_single._captured["json"]["extraction"]["items_count"] >= 1

        # Multi-file extraction inside the live agent's Document Vault
        h_multi = _make_mock_handler()
        assert local_router.dispatch_post(
            h_multi,
            "/api/fleet/agents/acko_policy_tracker/documents/extract",
            {
                "documents": [
                    {
                        "filename": "Acko-Motor.pdf",
                        "content_base64": base64.b64encode(acko_pdf).decode("ascii"),
                    },
                    {
                        "filename": "Acko-ZeroDep-Addon.txt",
                        "text_content": addon_txt,
                    },
                ],
                "auto_commit": True,
            },
        )
        assert h_multi._captured["status"] == 200
        assert h_multi._captured["json"]["attachments_count"] == 2
        assert h_multi._captured["json"]["committed_count"] >= 2
        assert db.get_custom_agent_dashboard_state("acko_policy_tracker")["kpis"]["documents_count"] == 3

    # Verify _call_antigravity_cli pipes oversized prompts via stdin on Windows instead of overflowing CreateProcessW
    from fleet.core.hyperscalers import HyperscalerGateway
    gw = HyperscalerGateway()
    huge_prompt = "Policy clause line with \"quoted JSON fields\" for extraction.\n" * 700  # >42,000 chars
    mock_proc = MagicMock(returncode=0, stdout=json.dumps({"response": '{"items": []}', "usage": {"total_tokens": 55}}), stderr="")
    with (
        patch("fleet.core.hyperscalers._get_antigravity_cli_path", return_value="C:/fake/agy.exe"),
        patch("fleet.core.hyperscalers.os.name", "nt"),
        patch("fleet.core.hyperscalers.subprocess.run", return_value=mock_proc) as mock_run,
    ):
        cli_res = gw._call_antigravity_cli(huge_prompt, model="gemini-3.8-flash-high", sys_inst="Return JSON.")
        assert cli_res["status"] == "SUCCESS"
        called_cmd = mock_run.call_args.args[0]
        # Command line itself must remain compact (<1,000 chars) while full prompt is piped via `input=`
        assert sum(len(part) for part in called_cmd) < 1000
        assert mock_run.call_args.kwargs.get("input") is not None


def test_car_bike_health_sentinel_acko_pdf_binary_image_skip_and_deep_build_seeding(multi_doc_env):
    """
    Regression test for Car Bike Health Sentinel (`car_bike_health_sentinel`):
    1. Multi-object PDFs containing embedded `/Subtype /Image` binary streams with fake `(PIXEL_GARBAGE)`
       bytes and Acko-style ordinal 2-digit year `Validity: 15th Nov 26 - 14th Nov 27` extract cleanly
       into 1 policy record (`due_date == "2027-11-14"`, `insurer == "Acko General Insurance"`) without
       binary image noise.
    2. Creating `car_bike_health_sentinel` via `POST /api/studio/deep_build` promotes all staged documents
       and seeds `initial_records` so `TRACKED ITEMS` starts populated immediately.
    """
    import zlib
    from fleet.api.settings_api import analyze_studio_document_endpoint, deep_build_agent_studio_endpoint

    db = multi_doc_env["db"]

    text_stream = zlib.compress(
        b"BT /F1 11 Tf "
        b"(ACKO General Insurance Limited) Tj T* "
        b"(Private Car Package Policy) Tj T* "
        b"(Policy Number: ACKO-CAR-2026-8812) Tj T* "
        b"(Registration Number: KA-01-MJ-4421) Tj T* "
        b"(Validity: 15th Nov 26 - 14th Nov 27) Tj T* "
        b"(Total Premium: Rs. 14,850.00) Tj T* "
        b"(Issued on: 30th Oct 26) Tj "
        b"ET"
    )
    fake_image_stream = zlib.compress(b"BT (BINARY_IMAGE_NOISE_999999) Tj ET " * 400)
    multi_obj_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Page /Contents 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Length " + str(len(text_stream)).encode() + b" /Filter /FlateDecode >>\nstream\n"
        + text_stream + b"\nendstream\nendobj\n"
        b"3 0 obj\n<< /Type /XObject /Subtype /Image /Filter /FlateDecode /Length "
        + str(len(fake_image_stream)).encode() + b" >>\nstream\n"
        + fake_image_stream + b"\nendstream\nendobj\n%%EOF"
    )

    h_analyze = _make_mock_handler()
    analyze_studio_document_endpoint(
        h_analyze,
        {
            "documents": [
                {
                    "filename": "Acko-20261030-377f2637-692b-4612-8edd-0565288d3bbd.pdf",
                    "content_base64": base64.b64encode(multi_obj_pdf).decode("ascii"),
                },
                {
                    "filename": "Acko-Bike-TwoWheeler.txt",
                    "text_content": (
                        "ACKO General Insurance\n"
                        "Two Wheeler Policy Number: ACKO-BIKE-2026-5501\n"
                        "Validity: 10th Nov 26 - 9th Nov 29\n"
                        "Net Premium: Rs. 3,420.00\n"
                    ),
                },
            ],
            "provider": "deterministic",
            "prompt": "Create Car Bike Health Sentinel to track car, bike, and health insurance renewals",
        },
    )
    assert h_analyze._captured["status"] == 200
    analyzed = h_analyze._captured["json"]
    assert analyzed["attachments_count"] == 2
    ext_items = analyzed["extraction"]["items"]
    assert len(ext_items) == 2
    items_by_src = {it["extra_fields"]["source_document"]: it for it in ext_items}
    car_item = items_by_src["Acko-20261030-377f2637-692b-4612-8edd-0565288d3bbd.pdf"]
    bike_item = items_by_src["Acko-Bike-TwoWheeler.txt"]
    assert "BINARY_IMAGE_NOISE" not in car_item["title"]
    assert car_item["due_date"] == "2027-11-14"
    assert car_item["numeric_value"] == 14850.0
    assert car_item["extra_fields"]["insurer"] == "Acko General Insurance"
    assert bike_item["due_date"] == "2029-11-09"
    assert bike_item["numeric_value"] == 3420.0

    # Deploy via `POST /api/studio/deep_build` and verify initial_documents & initial_records are seeded
    spec = dict(analyzed["spec"])
    spec["id"] = "car_bike_health_sentinel"
    spec["name"] = "Car Bike Health Sentinel"
    h_deep = _make_mock_handler()
    with patch("fleet.server.execute_dashboard_command", return_value={"status": "queued"}, create=True):
        deep_build_agent_studio_endpoint(
            h_deep,
            {
                "spec": spec,
                "scaffold_first": True,
                "is_evolve": False,
                "initial_documents": [
                    {
                        "filename": d["filename"],
                        "detected_scenario": d["detected_scenario"],
                        "document_summary": d["document_summary"],
                        "items_count": d["items_count"],
                        "vault_rel_path": d["vault"]["vault_rel_path"],
                        "sha256": d["vault"]["sha256"],
                    }
                    for d in analyzed["documents"]
                ],
                "initial_records": ext_items,
            },
        )
    assert h_deep._captured["status"] == 200
    deep_json = h_deep._captured["json"]
    assert deep_json["seeded_documents_count"] == 2
    assert deep_json["seeded_records_count"] == 2
    dash_state = db.get_custom_agent_dashboard_state("car_bike_health_sentinel")
    assert dash_state["kpis"]["documents_count"] == 2
    assert len(dash_state["entries"]) == 2


def test_deep_build_bypasses_tier0_rag_and_tail_seeks_large_transcript_fast(multi_doc_env, tmp_path):
    import time
    from fleet.api.settings_api import deep_build_agent_studio_endpoint
    from fleet.core.agent_studio import build_antigravity_deep_build_prompt
    from fleet.core.antigravity_mirror import (
        ACTIVE_PARALLEL_AGENTS,
        AGENT_STATE,
        _TRANSCRIPT_MEM_CACHE,
        append_transcript_turn,
        execute_dashboard_command,
        parse_transcript,
        sync_agent_state,
    )
    from fleet.core.token_optimizer import query_local_knowledge_base

    # 1. Verify Tier-0 local FAQ RAG never hijacks Antigravity IDE / Deep-Build engineering briefs
    deep_spec = {
        "id": "insurance_policy_sentinel",
        "name": "Insurance & Policy Sentinel",
        "category": "Health & Lifestyle",
        "archetype": "tracker",
        "intelligence_mode": "hybrid",
        "schedule": {"display": "Monday at 09:00"},
    }
    deep_prompt = build_antigravity_deep_build_prompt(deep_spec)
    assert "Antigravity" in deep_prompt or "fleet/data/user/custom_agents" in deep_prompt
    assert query_local_knowledge_base(deep_prompt) is None
    assert query_local_knowledge_base("Deep-build custom agent in Antigravity IDE") is None
    # Legitimate FFD step-climbing query still hits local knowledge base
    ffd_hit = query_local_knowledge_base("How to do Antigravity step climbing after meal?")
    assert ffd_hit is not None
    assert ffd_hit["doc_id"] == "ffd_antigravity_nod"

    # 2. Verify O(1) tail seek on a >2.6 MB transcript.jsonl completes in < 150 ms
    brain_logs = tmp_path / "pytest_user" / ".gemini" / "antigravity" / "brain" / "sess-large" / ".system_generated" / "logs"
    brain_logs.mkdir(parents=True, exist_ok=True)
    t_file = brain_logs / "transcript.jsonl"
    filler = "x" * 900
    with open(t_file, "w", encoding="utf-8") as f:
        for idx in range(1, 2601):
            f.write(
                json.dumps({
                    "step_index": idx,
                    "source": "USER_EXPLICIT" if idx % 2 == 1 else "MODEL",
                    "type": "USER_INPUT" if idx % 2 == 1 else "PLANNER_RESPONSE",
                    "created_at": "2026-10-30T17:00:00Z",
                    "content": f"Turn {idx} {filler}",
                }) + "\n"
            )
    assert t_file.stat().st_size > 2_500_000

    _TRANSCRIPT_MEM_CACHE["path"] = None
    _TRANSCRIPT_MEM_CACHE["mtime_ns"] = -1
    _TRANSCRIPT_MEM_CACHE["size"] = -1
    with patch.dict("os.environ", {"USERPROFILE": str(tmp_path / "pytest_user")}):
        t0 = time.perf_counter()
        next_step = append_transcript_turn("USER_INPUT", "<USER_REQUEST>Deep-build test</USER_REQUEST>")
        append_ms = (time.perf_counter() - t0) * 1000.0
        assert next_step == 2601
        assert append_ms < 250.0

        t1 = time.perf_counter()
        parsed = parse_transcript(limit=40)
        parse_ms = (time.perf_counter() - t1) * 1000.0
        assert parsed["status"] == "success"
        assert parsed["latest_step"] == 2601
        assert len(parsed["messages"]) == 40
        assert parse_ms < 250.0

        # Incremental append read should pick up step 2602 immediately
        step_2602 = append_transcript_turn("PLANNER_RESPONSE", "Deep-build worker launched", source="MODEL")
        assert step_2602 == 2602
        parsed_inc = parse_transcript(limit=40)
        assert parsed_inc["latest_step"] == 2602
        assert parsed_inc["messages"][-1]["text"] == "Deep-build worker launched"

    # 3. Verify execute_dashboard_command(bypass_tier0=True) dispatches worker instead of returning local_knowledge_rag
    ACTIVE_PARALLEL_AGENTS.clear()
    AGENT_STATE["status"] = "idle"
    sync_agent_state()
    with patch("fleet.core.antigravity_mirror._spawn_parallel_agent_worker", return_value="Agent-1") as mock_spawn:
        with patch.dict("os.environ", {"USERPROFILE": str(tmp_path / "pytest_user")}):
            disp = execute_dashboard_command(deep_prompt, images=[], model="gemini-3.8-flash-high", bypass_tier0=True)
    assert mock_spawn.called
    assert disp["status"] == "success"
    assert disp["type"] in ("agent_dispatched", "note_logged")

    # 4. Verify deep_build_agent_studio_endpoint passes bypass_tier0=True AND supports legacy 3-arg mocks
    captured_kwargs = {}

    def _modern_exec(cmd_text, images=None, model=None, bypass_tier0=False):
        captured_kwargs["bypass_tier0"] = bypass_tier0
        return {"status": "success", "type": "agent_dispatched"}

    h_modern = _make_mock_handler()
    with patch("fleet.server.execute_dashboard_command", side_effect=_modern_exec, create=True):
        deep_build_agent_studio_endpoint(h_modern, {"spec": deep_spec, "scaffold_first": False})
    assert h_modern._captured["status"] == 200
    assert captured_kwargs.get("bypass_tier0") is True

    def _legacy_exec(cmd_text, images=None, model=None):
        return {"status": "queued"}

    h_legacy = _make_mock_handler()
    with patch("fleet.server.execute_dashboard_command", side_effect=_legacy_exec, create=True):
        deep_build_agent_studio_endpoint(h_legacy, {"spec": deep_spec, "scaffold_first": False})
    assert h_legacy._captured["status"] == 200
    assert h_legacy._captured["json"]["dispatch"]["status"] == "queued"


def test_extract_items_button_vault_reextract_batched_llm_and_toast_wiring(multi_doc_env):
    router = multi_doc_env["router"]
    registry = multi_doc_env["registry"]
    db = multi_doc_env["db"]

    registry.create_custom_agent(
        agent_id="insurance_policy_sentinel",
        name="Insurance & Policy Sentinel",
        icon="🛡️",
        category="Finance",
        archetype="tracker",
        intelligence_mode="hybrid",
        ui_blocks=["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "history_table"],
    )

    # 1. Seed 2 vaulted policy documents via deterministic extraction first (simulating Studio creation)
    h_init = _make_mock_handler()
    router.dispatch_post(
        h_init,
        "/api/fleet/agents/insurance_policy_sentinel/documents/extract",
        {
            "provider": "deterministic",
            "documents": [
                {
                    "filename": "Acko-Car-Policy-1.txt",
                    "text_content": (
                        "ACKO GENERAL INSURANCE\n"
                        "Private Car Insurance Policy\n"
                        "Policy Number: DCAR00991122\n"
                        "Validity: 15th Nov 26 - 14th Nov 27\n"
                        "Total Premium Paid: Rs. 15,200\n"
                    ),
                },
                {
                    "filename": "Acko-Bike-Policy-2.txt",
                    "text_content": (
                        "ACKO GENERAL INSURANCE\n"
                        "Two Wheeler Insurance Policy\n"
                        "Policy Number: DBIK00884411\n"
                        "Validity: 10th Dec 26 - 09th Dec 27\n"
                        "Total Premium Paid: Rs. 2,850\n"
                    ),
                },
            ],
        },
    )
    assert h_init._captured["status"] == 200
    init_json = h_init._captured["json"]
    assert init_json["attachments_count"] == 2
    assert len(init_json["state"]["documents"]) == 2
    assert init_json["state"]["documents"][0]["data"]["model_used"] == "deterministic-$0.00"

    # 2. Clicking 'Extract Items' with no new file chosen triggers reextract_vault=True in a SINGLE batched LLM call
    mock_batch_llm = {
        "per_document_summaries": [
            {"filename": "Acko-Car-Policy-1.txt", "summary": "Acko car policy expiring 2027-11-14."},
            {"filename": "Acko-Bike-Policy-2.txt", "summary": "Acko bike policy expiring 2027-12-09."},
        ],
        "items": [
            {
                "source_document": "Acko-Car-Policy-1.txt",
                "title": "Acko Private Car Policy #DCAR00991122",
                "due_date": "2027-11-14",
                "numeric_value": 15200.0,
                "extra_fields": {"policy_number": "DCAR00991122", "insurer": "Acko General Insurance"},
            },
            {
                "source_document": "Acko-Bike-Policy-2.txt",
                "title": "Acko Two-Wheeler Policy #DBIK00884411",
                "due_date": "2027-12-09",
                "numeric_value": 2850.0,
                "extra_fields": {"policy_number": "DBIK00884411", "insurer": "Acko General Insurance"},
            },
        ],
    }

    h_re = _make_mock_handler()
    with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_gw:
        mock_gw.return_value = {
            "status": "SUCCESS",
            "provider": "Google Antigravity CLI",
            "model": "gemini-3.8-flash-high",
            "tokens_used": 620,
            "text": json.dumps(mock_batch_llm),
        }
        router.dispatch_post(
            h_re,
            "/api/fleet/agents/insurance_policy_sentinel/documents/extract",
            {
                "reextract_vault": True,
                "extraction_hint": "extract expiry date, premium & policy #",
                "auto_commit": False,
            },
        )
        # Must invoke LLM once in batch rather than twice serially
        assert mock_gw.call_count == 1

    assert h_re._captured["status"] == 200
    re_json = h_re._captured["json"]
    assert re_json["attachments_count"] == 2
    assert re_json["extraction"]["items_count"] == 2
    assert re_json["extraction"]["model_used"] == "gemini-3.8-flash-high"
    # Existing document pills must be updated in-place (still 2 pills, not 4!)
    assert len(re_json["state"]["documents"]) == 2
    assert all(d["data"]["model_used"] == "gemini-3.8-flash-high" for d in re_json["state"]["documents"])

    # 3. Even if document pills were dismissed from SQLite, reextract_vault recovers files from agent's disk vault
    for d in list(re_json["state"]["documents"]):
        db.delete_custom_agent_record("insurance_policy_sentinel", int(d["id"]))
    assert len(db.get_custom_agent_dashboard_state("insurance_policy_sentinel")["documents"]) == 0

    h_disk = _make_mock_handler()
    router.dispatch_post(
        h_disk,
        "/api/fleet/agents/insurance_policy_sentinel/documents/extract",
        {"reextract_vault": True, "provider": "deterministic"},
    )
    assert h_disk._captured["status"] == 200
    assert h_disk._captured["json"]["attachments_count"] == 2
    assert h_disk._captured["json"]["extraction"]["items_count"] == 2

    # 4. Verify frontend create_agent.js defines global showFleetToast and reextractVaultDocuments
    js_src = (Path(__file__).resolve().parent.parent / "fleet" / "web" / "static" / "js" / "create_agent.js").read_text(encoding="utf-8")
    assert "function showFleetToast(" in js_src
    assert "window.showFleetToast = showFleetToast;" in js_src
    assert "reextractVaultDocuments(" in js_src




