"""
Phase 5: Intelligent Document Ingestion & LLM Tracking Extraction Engine.

Enables both the Zero-Code Agent Studio (creation-time blueprint & seed extraction)
and live Custom Agents (`document_vault` UI block & MCP tool) to ingest real-world
documents (.pdf, .docx, .xlsx, .csv, .tsv, .eml, .ics, .html, .txt, .md, .json,
and scanned images .png/.jpg/.jpeg/.webp) and extract structured tracking items
using the agent's configured / available LLM (Multimodal Gemini/Claude/OpenAI,
Antigravity CLI `agy`, HyperscalerGateway, plus a deterministic $0.00 fallback).

Zero mandatory external dependencies (pure Python stdlib + optional pypdf fast-path).
All persisted uploads are strictly isolated inside `fleet/data/user/agent_docs/`.
"""

from __future__ import annotations

import base64
import csv
from datetime import date, datetime
import email
from email import policy as email_policy
import hashlib
from html.parser import HTMLParser
import io
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib

from fleet.config import DATA_DIR, get_secure_secret

logger = logging.getLogger("fleet.core.document_extractor")

MAX_DOCUMENT_BYTES = 12 * 1024 * 1024  # 12 MB raw document ceiling
MAX_UNCOMPRESSED_ZIP_BYTES = 25 * 1024 * 1024  # 25 MB zip-bomb ceiling for .docx/.xlsx
MAX_EXTRACTED_TEXT_CHARS = 48_000
MAX_MULTI_ATTACHMENTS = 10  # Max attachments analyzed together in Agent Creation Workflow

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".csv", ".tsv", ".txt", ".md",
    ".json", ".yaml", ".yml", ".eml", ".ics", ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".webp",
}

VISUAL_MEDIA_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

# 8 Real-World Document-to-Tracking Domain Profiles
DOCUMENT_SCENARIO_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "insurance_policy",
        "title": "Insurance & Vehicle Policy",
        "icon": "🛡️",
        "category": "Finance",
        "default_agent_name": "Insurance & Policy Sentinel",
        "keywords": [
            "insurance", "policy", "insurer", "insured", "premium", "sum insured",
            "idv", "nominee", "coverage", "deductible", "endorsement", "motor",
            "health policy", "term plan", "puc", "registration", "claim",
        ],
        "extraction_focus": (
            "Extract each insurance policy, rider, or compliance renewal: policy name & insurer, "
            "policy/certificate number, expiry/renewal due date (YYYY-MM-DD), annual premium or sum insured, "
            "insured asset/member, and claim helpline or grace period."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Policy / Coverage Name", "type": "text", "placeholder": "e.g. HDFC Ergo Comprehensive Car Policy"},
            {"key": "due_date", "label": "Expiry / Renewal Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Annual Premium", "type": "number", "placeholder": "18500"},
            {"key": "policy_number", "label": "Policy / Reg No.", "type": "text", "placeholder": "POL-2026-88912"},
            {"key": "insurer", "label": "Insurer / Provider", "type": "text", "placeholder": "e.g. HDFC Ergo / ICICI Lombard"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "kanban_board", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "contract_subscription",
        "title": "Contracts, Leases & SaaS Renewals",
        "icon": "📑",
        "category": "Finance",
        "default_agent_name": "Contract & Lease Renewal Guard",
        "keywords": [
            "agreement", "contract", "lease", "landlord", "tenant", "msa", "sow",
            "subscription", "auto-renew", "notice period", "termination", "retainer",
            "nda", "license", "domain", "ssl",
        ],
        "extraction_focus": (
            "Extract contract renewal dates, auto-renewal opt-out notice deadlines, rental/lease escalations, "
            "and SLA obligations with contract value, counterparty name, and cancellation terms."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Agreement / Vendor", "type": "text", "placeholder": "e.g. Office Lease / Datadog Enterprise MSA"},
            {"key": "due_date", "label": "Renewal / Notice Deadline", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Contract Value", "type": "number", "placeholder": "45000"},
            {"key": "counterparty", "label": "Counterparty / Owner", "type": "text", "placeholder": "e.g. Acme Properties"},
            {"key": "target_url", "label": "Portal / Doc Link", "type": "url", "placeholder": "https://vendor.example.com"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "kanban_board", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "invoice_bill_tax",
        "title": "Invoices, Bills, Loans & Tax Filings",
        "icon": "🧾",
        "category": "Finance",
        "default_agent_name": "Invoice, Bill & Tax Tracker",
        "keywords": [
            "invoice", "bill", "amount due", "payment due", "tax", "gst", "tds",
            "challan", "emi", "installment", "statement", "credit card", "utility",
            "electricity", "broadband", "balance due",
        ],
        "extraction_focus": (
            "Extract payable invoices, EMI installments, tax filing deadlines, and utility bills: "
            "payee/biller & invoice number, payment due date (YYYY-MM-DD), total amount due, and account reference."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Biller / Invoice Item", "type": "text", "placeholder": "e.g. AWS Cloud Invoice #INV-9042"},
            {"key": "due_date", "label": "Payment Due Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Amount Due", "type": "number", "placeholder": "4250"},
            {"key": "invoice_number", "label": "Invoice / Account #", "type": "text", "placeholder": "INV-9042"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "sparkline_chart", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "medical_lab_rx",
        "title": "Medical Lab Reports & Prescriptions",
        "icon": "🩺",
        "category": "Health",
        "default_agent_name": "Clinical Lab & Rx Follow-Up Coach",
        "keywords": [
            "hemoglobin", "hba1c", "glucose", "cholesterol", "triglycerides", "thyroid",
            "tsh", "vitamin", "creatinine", "egfr", "sgpt", "prescription", "dosage",
            "tablet", "capsule", "mg/dl", "ref interval", "biological reference", "pathology",
            "diagnostic", "blood test", "refill",
        ],
        "extraction_focus": (
            "Extract out-of-range or key clinical biomarkers, prescribed medications, refill dates, "
            "and recommended follow-up tests: biomarker/medication name, next review/refill date (YYYY-MM-DD), "
            "measured numeric reading or dosage, and biological reference range / clinical flag."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Biomarker / Medication", "type": "text", "placeholder": "e.g. HbA1c / Vitamin D3 Follow-Up"},
            {"key": "due_date", "label": "Next Test / Refill Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Measured Value / Dose", "type": "number", "placeholder": "7.1"},
            {"key": "reference_note", "label": "Ref Range / Regimen", "type": "text", "placeholder": "Ref < 5.7% | Morning pre-meal"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "sparkline_chart", "habit_checklist", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "travel_id_visa",
        "title": "Travel Itineraries, Passports & Visas",
        "icon": "✈️",
        "category": "Productivity",
        "default_agent_name": "Travel, Visa & ID Vault",
        "keywords": [
            "passport", "visa", "flight", "airline", "boarding", "pnr", "itinerary",
            "hotel", "check-in", "departure", "arrival", "terminal", "driving licence",
            "immigration", "booking", "reservation",
        ],
        "extraction_focus": (
            "Extract flight/train legs, hotel check-ins, visa validity deadlines, and passport/ID expirations: "
            "trip leg or document title, departure/check-in/expiry date (YYYY-MM-DD), ticket/fee cost, and PNR/document number."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Document / Trip Segment", "type": "text", "placeholder": "e.g. Schengen Visa / Flight AI-505 BLR-DEL"},
            {"key": "due_date", "label": "Travel / Expiry Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Cost / Fee", "type": "number", "placeholder": "8500"},
            {"key": "reference_code", "label": "PNR / Passport / Doc #", "type": "text", "placeholder": "PNR-X7K92"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "kanban_board", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "warranty_asset_amc",
        "title": "Warranties, Hardware & Service AMC",
        "icon": "🛠️",
        "category": "Utility",
        "default_agent_name": "Asset Warranty & Service Tracker",
        "keywords": [
            "warranty", "serial number", "serial no", "imei", "amc", "appliance",
            "service due", "maintenance", "purchase date", "model no", "receipt",
            "hardware", "laptop", "router", "odometer",
        ],
        "extraction_focus": (
            "Extract purchased hardware/appliances, warranty expiration dates, and scheduled AMC/maintenance "
            "milestones: product/asset name, warranty/service due date (YYYY-MM-DD), purchase price, and serial/model number."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Asset / Appliance Name", "type": "text", "placeholder": "e.g. ThinkPad X1 Carbon Gen 12"},
            {"key": "due_date", "label": "Warranty / Service Expiry", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Purchase Value", "type": "number", "placeholder": "145000"},
            {"key": "serial_number", "label": "Serial / Model / Vendor", "type": "text", "placeholder": "SN-PF4X9921"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "syllabus_project_cert",
        "title": "Syllabi, Certifications & Project Milestones",
        "icon": "🎓",
        "category": "Knowledge",
        "default_agent_name": "Milestone, Exam & Certification Tracker",
        "keywords": [
            "syllabus", "assignment", "exam", "midterm", "certification", "milestone",
            "deliverable", "deadline", "sprint", "course", "lecture", "curriculum",
            "rfp", "submission", "credits",
        ],
        "extraction_focus": (
            "Extract all deliverables, exam dates, certification renewals, and project milestones: "
            "milestone/exam title, due/exam date (YYYY-MM-DD), weightage/points/fee, and deliverable notes."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Milestone / Exam / Cert", "type": "text", "placeholder": "e.g. GCP Professional Architect Renewal"},
            {"key": "due_date", "label": "Submission / Exam Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Weight % / Fee / Points", "type": "number", "placeholder": "25"},
            {"key": "notes", "label": "Topic / Owner / Scope", "type": "text", "placeholder": "Modules 1-6"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "kanban_board", "habit_checklist", "ai_insight_card", "history_table",
        ],
    },
    {
        "id": "investment_fd_bond",
        "title": "Fixed Deposits, Bonds & Investments",
        "icon": "📈",
        "category": "Finance",
        "default_agent_name": "Deposit, Bond & Maturity Sentinel",
        "keywords": [
            "fixed deposit", "maturity date", "maturity amount", "principal", "interest rate",
            "bond", "debenture", "isin", "sip", "mutual fund", "folio", "dividend",
            "treasury", "yield", "tenure",
        ],
        "extraction_focus": (
            "Extract fixed deposits, bonds, SIP schedules, and maturity instruments: "
            "instrument/bank & FD/folio number, maturity/payout date (YYYY-MM-DD), maturity or principal amount, and interest rate %."
        ),
        "recommended_fields": [
            {"key": "title", "label": "Instrument / Deposit", "type": "text", "placeholder": "e.g. SBI Tax-Saver FD #FD-77210"},
            {"key": "due_date", "label": "Maturity / Payout Date", "type": "date", "placeholder": "YYYY-MM-DD"},
            {"key": "numeric_value", "label": "Maturity / Principal Value", "type": "number", "placeholder": "250000"},
            {"key": "yield_notes", "label": "Interest Rate / Folio", "type": "text", "placeholder": "7.35% p.a. | Auto-renew off"},
        ],
        "recommended_blocks": [
            "alert_banner", "kpi_row", "document_vault", "quick_capture_bar",
            "countdown_cards", "sparkline_chart", "ai_insight_card", "history_table",
        ],
    },
]


def get_document_scenario_profiles() -> List[Dict[str, Any]]:
    """Returns copy of supported document-to-tracking scenario profiles."""
    return [dict(p) for p in DOCUMENT_SCENARIO_PROFILES]


def sanitize_upload_filename(filename: str) -> str:
    """Sanitizes a user-supplied filename, preventing path traversal and control chars."""
    normalized = str(filename or "document.txt").replace("\\", "/")
    raw_name = normalized.rsplit("/", 1)[-1]
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name)
    clean = re.sub(r"_+", "_", clean).strip("._")
    if not clean:
        clean = "document.txt"
    if "." not in clean:
        clean = f"{clean}.txt"
    stem, ext = clean.rsplit(".", 1)
    return f"{stem[:84]}.{ext.lower()[:11]}"


def decode_document_payload(
    filename: str = "",
    content_base64: str = "",
    text_content: str = "",
) -> Tuple[str, bytes, str]:
    """
    Decodes either a base64 document payload (including `data:...;base64,...` URIs)
    or plain text content into `(safe_filename, raw_bytes, ext)`.
    """
    safe_name = sanitize_upload_filename(filename or ("pasted_notes.txt" if text_content else "document.txt"))
    ext = Path(safe_name).suffix.lower()

    if content_base64 and content_base64.strip():
        b64_str = content_base64.strip()
        if "," in b64_str and b64_str.lower().startswith("data:"):
            header, b64_str = b64_str.split(",", 1)
            if not filename:
                m_mime = re.search(r"data:([a-zA-Z0-9.+/-]+)", header)
                if m_mime:
                    mime = m_mime.group(1).lower()
                    mime_ext = {
                        "application/pdf": ".pdf",
                        "image/png": ".png",
                        "image/jpeg": ".jpg",
                        "image/webp": ".webp",
                        "text/csv": ".csv",
                        "text/html": ".html",
                        "text/calendar": ".ics",
                    }.get(mime, ".txt")
                    safe_name = f"uploaded_document{mime_ext}"
                    ext = mime_ext
        raw_bytes = base64.b64decode(b64_str, validate=False)
    elif text_content and text_content.strip():
        raw_bytes = text_content.encode("utf-8")
    else:
        raise ValueError("No document content provided (expected 'content_base64' or 'text_content').")

    if len(raw_bytes) == 0:
        raise ValueError("Uploaded document is empty.")
    if len(raw_bytes) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Document exceeds maximum allowed size of {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB.")

    # Auto-detect PDF/ZIP/PNG/JPEG magic headers if extension is generic
    if raw_bytes.startswith(b"%PDF-"):
        ext = ".pdf"
    elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = ".png"
    elif raw_bytes.startswith(b"\xff\xd8\xff"):
        ext = ".jpg"

    return safe_name, raw_bytes, ext


def save_agent_document_to_vault(agent_id: str, safe_filename: str, raw_bytes: bytes) -> Dict[str, Any]:
    """
    Persists the uploaded document inside the isolated User Data Vault:
    `fleet/data/user/agent_docs/<clean_agent_id>/<ts>_<sha10>_<safe_filename>`.
    """
    clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", (agent_id or "studio_staging").strip()) or "studio_staging"
    clean_name = sanitize_upload_filename(safe_filename)
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    vault_dir = DATA_DIR / "user" / "agent_docs" / clean_agent
    vault_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{stamp}_{sha256_hex[:10]}_{clean_name}"
    dest = vault_dir / stored_name
    dest.write_bytes(raw_bytes)

    rel_vault_path = f"user/agent_docs/{clean_agent}/{stored_name}"
    return {
        "filename": clean_name,
        "stored_name": stored_name,
        "vault_rel_path": rel_vault_path,
        "size_bytes": len(raw_bytes),
        "sha256": sha256_hex,
    }


_VAULT_STORED_PREFIX_RE = re.compile(r"^\d{8}_\d{6}_[0-9a-fA-F]{10}_(.+)$")


def load_vaulted_documents_for_agent(
    agent_id: str,
    db_doc_records: Optional[List[Dict[str, Any]]] = None,
    target_doc_record_id: int = 0,
) -> List[Dict[str, Any]]:
    """
    Loads previously vaulted documents for `agent_id` strictly confined within
    `fleet/data/user/agent_docs/<clean_agent>/`, deduplicating by SHA-256 hash.
    Falls back to scanning the agent's vault directory on disk when SQLite document
    pills were dismissed.
    """
    clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", (agent_id or "").strip())
    if not clean_agent:
        return []

    allowed_root = (DATA_DIR / "user" / "agent_docs").resolve()
    agent_vault_dir = (allowed_root / clean_agent).resolve()
    try:
        agent_vault_dir.relative_to(allowed_root)
    except ValueError:
        return []

    loaded: List[Dict[str, Any]] = []
    seen_sha: set[str] = set()

    def _try_add_file(fpath: Path, display_name: str = "", rec_id: int = 0) -> None:
        if len(loaded) >= MAX_MULTI_ATTACHMENTS:
            return
        try:
            resolved = fpath.resolve()
            resolved.relative_to(allowed_root)
            if not resolved.is_file():
                return
            raw_bytes = resolved.read_bytes()
            if not raw_bytes or len(raw_bytes) > MAX_DOCUMENT_BYTES:
                return
            sha_hex = hashlib.sha256(raw_bytes).hexdigest()
            if sha_hex in seen_sha:
                return
            seen_sha.add(sha_hex)
            fname = display_name.strip() if display_name else ""
            if not fname:
                m_pref = _VAULT_STORED_PREFIX_RE.match(resolved.name)
                fname = m_pref.group(1) if m_pref else resolved.name
            clean_fname = sanitize_upload_filename(fname)
            rel_posix = resolved.relative_to(DATA_DIR.resolve()).as_posix()
            loaded.append({
                "filename": clean_fname,
                "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
                "doc_record_id": int(rec_id or 0),
                "existing_vault_info": {
                    "filename": clean_fname,
                    "stored_name": resolved.name,
                    "vault_rel_path": rel_posix,
                    "size_bytes": len(raw_bytes),
                    "sha256": sha_hex,
                },
            })
        except Exception:
            return

    for rec in (db_doc_records or []):
        if not isinstance(rec, dict):
            continue
        rec_id = int(rec.get("id") or 0)
        if target_doc_record_id > 0 and rec_id != target_doc_record_id:
            continue
        raw_meta = rec.get("data")
        meta: Dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        vrel = str(meta.get("vault_rel_path") or "").strip().lstrip("/\\")
        disp_name = str(meta.get("filename") or rec.get("title") or "").strip()
        candidate: Optional[Path] = None
        if vrel:
            cand = (DATA_DIR / vrel).resolve()
            try:
                cand.relative_to(allowed_root)
                if cand.is_file():
                    candidate = cand
            except ValueError:
                candidate = None
        if candidate is None and disp_name and agent_vault_dir.is_dir():
            safe_disp = sanitize_upload_filename(disp_name)
            matches = sorted(
                agent_vault_dir.glob(f"*_{safe_disp}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                candidate = matches[0]
        if candidate is not None:
            _try_add_file(candidate, display_name=disp_name, rec_id=rec_id)

    if not loaded and target_doc_record_id == 0 and agent_vault_dir.is_dir():
        disk_files = sorted(
            (p for p in agent_vault_dir.iterdir() if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in disk_files:
            _try_add_file(p)

    return loaded


# ---------------------------------------------------------------------------
# Pure-Stdlib Multi-Format Text & Table Extractors
# ---------------------------------------------------------------------------

class _SemanticHTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any):
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg"):
            self._skip_depth += 1
        elif t in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"):
            self._chunks.append("\n")
        elif t in ("td", "th"):
            self._chunks.append(" | ")

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif t in ("p", "div", "tr", "li", "table"):
            self._chunks.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        lines = [re.sub(r"[ \t]+", " ", ln).strip(" |") for ln in raw.splitlines()]
        return "\n".join(ln for ln in lines if ln)


def _decode_bytes_smart(raw_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(enc)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _safe_zip_members(zf: zipfile.ZipFile) -> None:
    total = sum(info.file_size for info in zf.infolist())
    if total > MAX_UNCOMPRESSED_ZIP_BYTES:
        raise ValueError("Compressed office archive exceeds safe uncompressed size limit.")


def _extract_docx_text(raw_bytes: bytes) -> str:
    """Pure-stdlib .docx paragraph & table extractor using zipfile + ElementTree."""
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        _safe_zip_members(zf)
        names = zf.namelist()
        ordered_xmls = (
            sorted(n for n in names if n.startswith("word/header") and n.endswith(".xml"))
            + ([n for n in ("word/document.xml",) if n in names])
            + sorted(n for n in names if n.startswith("word/footer") and n.endswith(".xml"))
        )
        blocks: List[str] = []
        for xml_name in ordered_xmls:
            xml_bytes = zf.read(xml_name)
            root = ET.fromstring(xml_bytes)
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                if tag == "p":
                    texts = [node.text for node in elem.iter() if node.tag.split("}")[-1] == "t" and node.text]
                    line = "".join(texts).strip()
                    if line:
                        blocks.append(line)
        return "\n".join(blocks)


def _extract_xlsx_text(raw_bytes: bytes) -> str:
    """Pure-stdlib .xlsx sharedStrings + worksheet cell extractor."""
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        _safe_zip_members(zf)
        names = zf.namelist()
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in names:
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.iter():
                if si.tag.split("}")[-1] == "si":
                    parts = [n.text for n in si.iter() if n.tag.split("}")[-1] == "t" and n.text]
                    shared_strings.append("".join(parts))

        sheets = sorted(n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        lines: List[str] = []
        for idx, sheet_name in enumerate(sheets, 1):
            if len(sheets) > 1:
                lines.append(f"--- Sheet {idx} ---")
            s_root = ET.fromstring(zf.read(sheet_name))
            for row in s_root.iter():
                if row.tag.split("}")[-1] != "row":
                    continue
                vals: List[str] = []
                for cell in row:
                    if cell.tag.split("}")[-1] != "c":
                        continue
                    c_type = cell.attrib.get("t", "")
                    v_text = ""
                    for child in cell:
                        ctag = child.tag.split("}")[-1]
                        if ctag == "v" and child.text is not None:
                            v_text = child.text.strip()
                        elif ctag == "is":
                            t_parts = [n.text for n in child.iter() if n.tag.split("}")[-1] == "t" and n.text]
                            v_text = "".join(t_parts).strip()
                    if c_type == "s" and v_text.isdigit():
                        s_idx = int(v_text)
                        if 0 <= s_idx < len(shared_strings):
                            v_text = shared_strings[s_idx]
                    if v_text:
                        vals.append(v_text)
                if vals:
                    lines.append(" | ".join(vals))
        return "\n".join(lines)


def _decode_pdf_literal_string(raw_inner: bytes) -> str:
    """Decodes a PDF literal string `(...)` handling octal escapes and UTF-16BE BOM."""
    out = bytearray()
    i = 0
    n = len(raw_inner)
    while i < n:
        b = raw_inner[i]
        if b == 0x5C and i + 1 < n:  # backslash
            nxt = raw_inner[i + 1]
            if 0x30 <= nxt <= 0x37:  # octal \ddd
                oct_digits = bytes([nxt])
                i += 2
                for _ in range(2):
                    if i < n and 0x30 <= raw_inner[i] <= 0x37:
                        oct_digits += bytes([raw_inner[i]])
                        i += 1
                    else:
                        break
                out.append(int(oct_digits, 8) & 0xFF)
                continue
            esc_map = {
                ord("n"): 10, ord("r"): 13, ord("t"): 9,
                ord("b"): 8, ord("f"): 12, ord("("): 40,
                ord(")"): 41, ord("\\"): 92,
            }
            if nxt in esc_map:
                out.append(esc_map[nxt])
                i += 2
                continue
            if nxt in (10, 13):  # line continuation
                i += 2
                continue
            out.append(nxt)
            i += 2
        else:
            out.append(b)
            i += 1

    b_data = bytes(out)
    if b_data.startswith(b"\xfe\xff"):
        return b_data[2:].decode("utf-16-be", errors="ignore")
    return b_data.decode("latin-1", errors="ignore")


def _parse_tounicode_cmap(stream_text: str) -> Dict[int, str]:
    """Parses PDF /ToUnicode CMap `beginbfchar` and `beginbfrange` mappings."""
    cmap: Dict[int, str] = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", stream_text, flags=re.S):
        for src_hex, dst_hex in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            try:
                code = int(src_hex, 16)
                dst_bytes = bytes.fromhex(dst_hex)
                cmap[code] = dst_bytes.decode("utf-16-be", errors="ignore")
            except Exception:
                continue
    for block in re.findall(r"beginbfrange(.*?)endbfrange", stream_text, flags=re.S):
        for start_h, end_h, target_h in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            try:
                s_code = int(start_h, 16)
                e_code = int(end_h, 16)
                t_val = int(target_h, 16)
                if e_code - s_code <= 512:
                    for offset in range(e_code - s_code + 1):
                        cmap[s_code + offset] = chr(t_val + offset)
            except Exception:
                continue
    return cmap


def _extract_pdf_Literals_from_content(
    stream_bytes: bytes,
    cmap: Dict[int, str],
    font_cmaps: Optional[Dict[str, Dict[int, str]]] = None,
) -> List[str]:
    """Extracts readable lines from a decompressed PDF content stream (`BT ... ET`, `Tf`, `Tj`, `TJ`)."""
    text_latin = stream_bytes.decode("latin-1", errors="ignore")
    if "BT" not in text_latin and "Tj" not in text_latin and "TJ" not in text_latin:
        return []

    lines: List[str] = []
    bt_blocks = re.findall(r"BT\b(.*?)\bET", text_latin, flags=re.S)
    if bt_blocks:
        targets = bt_blocks
    elif len(stream_bytes) <= 262144 and ("Tj" in text_latin or "TJ" in text_latin):
        targets = [text_latin]
    else:
        return []

    token_re = re.compile(
        r"/(?P<font>[A-Za-z0-9_+-]+)\s+-?[\d.]+\s+Tf"
        r"|\[(?P<arr>[^\]]*)\]\s*TJ"
        r"|\((?P<lit>(?:\\.|[^\\()])*)\)\s*(?:Tj|'|\")"
        r"|<(?P<hex>[0-9A-Fa-f\s]+)>\s*Tj"
        r"|(?P<nl>\bT\*|\bTd\b|\bTD\b|\bTm\b)",
        flags=re.S,
    )

    active_cmap = cmap
    for blk in targets:
        cur: List[str] = []
        for m in token_re.finditer(blk):
            if m.group("font"):
                if font_cmaps and m.group("font") in font_cmaps:
                    active_cmap = font_cmaps[m.group("font")]
                else:
                    active_cmap = cmap
            elif m.group("nl"):
                joined = "".join(cur).strip()
                if joined:
                    lines.append(joined)
                cur = []
            elif m.group("lit") is not None:
                s = _decode_pdf_literal_string(m.group("lit").encode("latin-1", errors="ignore"))
                if s:
                    cur.append(s)
            elif m.group("hex") is not None:
                hx = re.sub(r"\s+", "", m.group("hex"))
                s = _decode_pdf_hex_string(hx, active_cmap)
                if s:
                    cur.append(s)
            elif m.group("arr") is not None:
                arr_body = m.group("arr")
                for sub in re.finditer(r"\((?P<slit>(?:\\.|[^\\()])*)\)|<(?P<shex>[0-9A-Fa-f\s]+)>|(?P<kern>-?\d+(?:\.\d+)?)", arr_body):
                    if sub.group("slit") is not None:
                        cur.append(_decode_pdf_literal_string(sub.group("slit").encode("latin-1", errors="ignore")))
                    elif sub.group("shex") is not None:
                        cur.append(_decode_pdf_hex_string(re.sub(r"\s+", "", sub.group("shex")), active_cmap))
                    elif sub.group("kern") is not None:
                        try:
                            if float(sub.group("kern")) < -120:
                                cur.append(" ")
                        except ValueError:
                            pass
        tail = "".join(cur).strip()
        if tail:
            lines.append(tail)

    return lines


def _decode_pdf_hex_string(hex_str: str, cmap: Dict[int, str]) -> str:
    if not hex_str:
        return ""
    if len(hex_str) % 2 == 1:
        hex_str += "0"
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="ignore")
    if cmap:
        # Try 2-byte big-endian glyph IDs first if even length, else 1-byte
        if len(raw) % 2 == 0:
            chars_2b = []
            hit_2b = 0
            for idx in range(0, len(raw), 2):
                code = (raw[idx] << 8) | raw[idx + 1]
                if code in cmap:
                    chars_2b.append(cmap[code])
                    hit_2b += 1
                elif 32 <= code <= 126:
                    chars_2b.append(chr(code))
            if hit_2b > 0:
                return "".join(chars_2b)
        chars_1b = [cmap.get(b, chr(b) if 32 <= b <= 126 else "") for b in raw]
        if any(b in cmap for b in raw):
            return "".join(chars_1b)
    return raw.decode("latin-1", errors="ignore")


_PDF_NON_TEXT_STREAM_RE = re.compile(
    rb"/Subtype\s*/(?:Image|Type1C|CIDFontType0C|OpenType|Form)\b"
    rb"|/Length1\s+\d+"
    rb"|/Type\s*/(?:Metadata|XRef)\b"
    rb"|/(?:DCTDecode|JPXDecode|CCITTFaxDecode|JBIG2Decode)\b",
)


def _extract_pdf_text(raw_bytes: bytes) -> str:
    """
    Extracts readable text from a PDF document.
    Uses `pypdf` if available in the environment; otherwise executes a pure-stdlib
    object-aware FlateDecode + per-font `/ToUnicode` CMap + PDF text operator (`Tf`/`Tj`/`TJ`)
    extractor that skips binary image/font streams for sub-second extraction on large PDFs.
    """
    # Optional fast-path if pypdf is installed
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = [p.extract_text() or "" for p in reader.pages[:40]]
        joined = "\n".join(p.strip() for p in pages if p.strip())
        if len(joined) >= 20:
            return joined
    except Exception:
        pass

    obj_headers: Dict[int, bytes] = {}
    obj_streams: Dict[int, bytes] = {}
    has_indirect_objs = False

    for m_obj in re.finditer(rb"(\d+)\s+\d+\s+obj\b(.*?)endobj", raw_bytes, flags=re.S):
        has_indirect_objs = True
        onum = int(m_obj.group(1))
        body = m_obj.group(2)
        sm = re.search(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", body, flags=re.S)
        if sm:
            hdr = sm.group(1)
            sraw = sm.group(2)
            obj_headers[onum] = hdr
            # Skip binary image bitmaps, raw TrueType/CFF font binaries, XRef & XML metadata streams
            if _PDF_NON_TEXT_STREAM_RE.search(hdr) and b"/Subtype /Form" not in hdr and b"/Subtype/Form" not in hdr:
                continue
            dec: Optional[bytes] = None
            for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
                try:
                    dec = zlib.decompress(sraw, wbits)
                    break
                except Exception:
                    continue
            obj_streams[onum] = dec if dec is not None else sraw
        else:
            obj_headers[onum] = body

    extracted_lines: List[str] = []
    global_cmap: Dict[int, str] = {}

    if has_indirect_objs and obj_streams:
        cmaps_by_obj: Dict[int, Dict[int, str]] = {}
        for onum, sdata in obj_streams.items():
            s_txt = sdata.decode("latin-1", errors="ignore")
            if "beginbfchar" in s_txt or "beginbfrange" in s_txt:
                cm = _parse_tounicode_cmap(s_txt)
                if cm:
                    cmaps_by_obj[onum] = cm
                    global_cmap.update(cm)

        font_obj_to_cmap: Dict[int, Dict[int, str]] = {}
        for onum, hdr in obj_headers.items():
            m_tu = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", hdr)
            if m_tu:
                tu_obj = int(m_tu.group(1))
                if tu_obj in cmaps_by_obj:
                    font_obj_to_cmap[onum] = cmaps_by_obj[tu_obj]

        fname_to_cmap: Dict[str, Dict[int, str]] = {}
        for _onum, hdr in obj_headers.items():
            for fm in re.finditer(rb"/([A-Za-z0-9_+-]+)\s+(\d+)\s+\d+\s+R", hdr):
                fobj = int(fm.group(2))
                if fobj in font_obj_to_cmap:
                    fname_to_cmap[fm.group(1).decode("latin-1", errors="ignore")] = font_obj_to_cmap[fobj]

        for onum in sorted(obj_streams.keys()):
            if onum in cmaps_by_obj:
                continue
            extracted_lines.extend(
                _extract_pdf_Literals_from_content(
                    obj_streams[onum],
                    global_cmap,
                    font_cmaps=fname_to_cmap,
                )
            )

    # Fallback for minimal/synthetic PDFs without indirect `obj ... endobj` wrappers
    if not extracted_lines:
        decompressed_streams: List[bytes] = []
        for m in re.finditer(rb"(?:<<(?P<hdr>[^>]*?)>>\s*)?stream\r?\n(?P<chunk>.*?)\r?\nendstream", raw_bytes, flags=re.S):
            hdr = m.group("hdr") or b""
            if hdr and _PDF_NON_TEXT_STREAM_RE.search(hdr) and b"Form" not in hdr:
                continue
            chunk = m.group("chunk")
            dec = None
            for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
                try:
                    dec = zlib.decompress(chunk, wbits)
                    break
                except Exception:
                    continue
            stream_data = dec if dec is not None else chunk
            decompressed_streams.append(stream_data)
            s_txt = stream_data.decode("latin-1", errors="ignore")
            if "beginbfchar" in s_txt or "beginbfrange" in s_txt:
                global_cmap.update(_parse_tounicode_cmap(s_txt))

        for s_bytes in decompressed_streams:
            extracted_lines.extend(_extract_pdf_Literals_from_content(s_bytes, global_cmap))

        if not extracted_lines:
            extracted_lines.extend(_extract_pdf_Literals_from_content(raw_bytes, global_cmap))

    cleaned = [re.sub(r"[ \t]+", " ", ln).strip() for ln in extracted_lines]
    cleaned = [ln for ln in cleaned if ln and any(ch.isalnum() for ch in ln)]
    return "\n".join(cleaned)


def _extract_csv_text(raw_bytes: bytes, delimiter: str = ",") -> str:
    txt = _decode_bytes_smart(raw_bytes)
    reader = csv.reader(io.StringIO(txt), delimiter=delimiter)
    rows: List[str] = []
    for idx, row in enumerate(reader):
        cells = [c.strip() for c in row if c is not None]
        if any(cells):
            prefix = "HEADERS: " if idx == 0 else f"ROW {idx}: "
            rows.append(prefix + " | ".join(cells))
        if idx >= 400:
            break
    return "\n".join(rows)


def _extract_ics_text(raw_bytes: bytes) -> str:
    txt = _decode_bytes_smart(raw_bytes)
    unfolded = re.sub(r"\r?\n[ \t]", "", txt)
    events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, flags=re.S | re.I)
    out: List[str] = []
    for idx, ev in enumerate(events, 1):
        def _field(name: str) -> str:
            m = re.search(rf"^{name}(?:;[^:]*)?:(.*)$", ev, flags=re.M | re.I)
            return m.group(1).strip() if m else ""

        summary = _field("SUMMARY")
        dtstart = _field("DTSTART")
        dtend = _field("DTEND")
        loc = _field("LOCATION")
        desc = _field("DESCRIPTION").replace("\\n", " ")
        m_dt = re.match(r"(\d{4})(\d{2})(\d{2})", dtstart)
        iso_dt = f"{m_dt.group(1)}-{m_dt.group(2)}-{m_dt.group(3)}" if m_dt else dtstart
        out.append(
            f"EVENT {idx}: {summary} | Date: {iso_dt} | End: {dtend} | Location: {loc} | Details: {desc}".strip()
        )
    return "\n".join(out) if out else txt


def _extract_eml_text(raw_bytes: bytes, depth: int = 0) -> str:
    msg = email.message_from_bytes(raw_bytes, policy=email_policy.default)
    parts_out: List[str] = []
    for hdr in ("Subject", "From", "To", "Date"):
        if msg.get(hdr):
            parts_out.append(f"{hdr}: {msg.get(hdr)}")
    parts_out.append("")

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get_content_disposition() or "")
            fname = part.get_filename()
            if fname and depth < 2:
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)) and payload and len(payload) <= MAX_DOCUMENT_BYTES:
                    sub_info = parse_uploaded_document(filename=fname, content_bytes=bytes(payload))
                    if sub_info.get("extracted_text"):
                        parts_out.append(f"\n--- Attachment: {fname} ---\n{sub_info['extracted_text']}")
                continue
            if disp == "attachment":
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)) and payload:
                    parts_out.append(_decode_bytes_smart(bytes(payload)))
            elif ctype == "text/html":
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)) and payload:
                    parser = _SemanticHTMLTextExtractor()
                    parser.feed(_decode_bytes_smart(bytes(payload)))
                    parts_out.append(parser.get_text())
    else:
        raw_payload = msg.get_payload(decode=True)
        payload_bytes = bytes(raw_payload) if isinstance(raw_payload, (bytes, bytearray)) and raw_payload else raw_bytes
        if msg.get_content_type() == "text/html":
            parser = _SemanticHTMLTextExtractor()
            parser.feed(_decode_bytes_smart(payload_bytes))
            parts_out.append(parser.get_text())
        else:
            parts_out.append(_decode_bytes_smart(payload_bytes))
    return "\n".join(p for p in parts_out if p is not None).strip()


def parse_uploaded_document(
    filename: str = "",
    content_base64: str = "",
    text_content: str = "",
    content_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Universal zero-dependency document parser returning extracted text, format metadata,
    and multimodal flags for downstream LLM & deterministic tracking extraction.
    """
    if content_bytes is not None:
        safe_name = sanitize_upload_filename(filename or "document.bin")
        raw_bytes = content_bytes
        ext = Path(safe_name).suffix.lower()
        if raw_bytes.startswith(b"%PDF-"):
            ext = ".pdf"
    else:
        safe_name, raw_bytes, ext = decode_document_payload(
            filename=filename,
            content_base64=content_base64,
            text_content=text_content,
        )

    is_visual_media = ext in VISUAL_MEDIA_MIME_MAP
    mime_type = VISUAL_MEDIA_MIME_MAP.get(ext, "application/pdf" if ext == ".pdf" else "text/plain")
    extracted_text = ""
    parser_used = "utf8_text"

    try:
        if is_visual_media:
            parser_used = "multimodal_image"
            extracted_text = ""
        elif ext == ".pdf":
            parser_used = "pdf_stream_extractor"
            extracted_text = _extract_pdf_text(raw_bytes)
        elif ext == ".docx":
            parser_used = "docx_xml_extractor"
            extracted_text = _extract_docx_text(raw_bytes)
        elif ext == ".xlsx":
            parser_used = "xlsx_xml_extractor"
            extracted_text = _extract_xlsx_text(raw_bytes)
        elif ext == ".csv":
            parser_used = "csv_table_extractor"
            extracted_text = _extract_csv_text(raw_bytes, delimiter=",")
        elif ext == ".tsv":
            parser_used = "tsv_table_extractor"
            extracted_text = _extract_csv_text(raw_bytes, delimiter="\t")
        elif ext == ".ics":
            parser_used = "ics_calendar_extractor"
            extracted_text = _extract_ics_text(raw_bytes)
        elif ext == ".eml":
            parser_used = "eml_mime_extractor"
            extracted_text = _extract_eml_text(raw_bytes)
        elif ext in (".html", ".htm"):
            parser_used = "html_semantic_extractor"
            hp = _SemanticHTMLTextExtractor()
            hp.feed(_decode_bytes_smart(raw_bytes))
            extracted_text = hp.get_text()
        elif ext == ".json":
            parser_used = "json_structured_extractor"
            raw_str = _decode_bytes_smart(raw_bytes)
            try:
                extracted_text = json.dumps(json.loads(raw_str), indent=2, ensure_ascii=False)
            except Exception:
                extracted_text = raw_str
        else:
            parser_used = "plain_text_extractor"
            extracted_text = _decode_bytes_smart(raw_bytes)
    except Exception as exc:
        logger.warning(f"Format-specific parser failed for '{safe_name}' ({ext}): {exc}")
        if not is_visual_media:
            extracted_text = _decode_bytes_smart(raw_bytes)

    extracted_text = extracted_text.strip()[:MAX_EXTRACTED_TEXT_CHARS]
    return {
        "filename": safe_name,
        "extension": ext,
        "mime_type": mime_type,
        "size_bytes": len(raw_bytes),
        "raw_bytes": raw_bytes,
        "is_visual_media": is_visual_media,
        "parser_used": parser_used,
        "extracted_text": extracted_text,
        "char_count": len(extracted_text),
    }


# ---------------------------------------------------------------------------
# Scenario Detection, Date/Number Normalization & LLM/Deterministic Extraction
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def normalize_extracted_date(raw_val: Any) -> str:
    """Normalizes common date representations into ISO `YYYY-MM-DD` (or returns `""`)."""
    s = str(raw_val or "").strip()
    if not s:
        return ""

    # 1. ISO YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", s)
    if m_iso:
        try:
            dt = date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            return dt.isoformat()
        except ValueError:
            pass

    # 2. DD Mon YYYY or DDth Nov 27 or DD-MMM-YYYY or DD Month, YYYY
    m_dmy_mon = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-/,.]+([A-Za-z]{3,9})\.?[\s\-/,.]+(20\d{2}|\d{2})\b",
        s,
        flags=re.I,
    )
    if m_dmy_mon:
        mon = _MONTH_MAP.get(m_dmy_mon.group(2).lower())
        yr = int(m_dmy_mon.group(3))
        if yr < 100:
            yr += 2000
        if mon:
            try:
                return date(yr, mon, int(m_dmy_mon.group(1))).isoformat()
            except ValueError:
                pass

    # 3. Month DD, YYYY
    m_mdy_mon = re.search(
        r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b",
        s,
    )
    if m_mdy_mon:
        mon = _MONTH_MAP.get(m_mdy_mon.group(1).lower())
        if mon:
            try:
                return date(int(m_mdy_mon.group(3)), mon, int(m_mdy_mon.group(2))).isoformat()
            except ValueError:
                pass

    # 4. DD/MM/YYYY or DD-MM-YYYY (with MM/DD/YYYY fallback if second group > 12)
    m_slash = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", s)
    if m_slash:
        a, b, yr = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
        for day_cand, mon_cand in ((a, b), (b, a)):
            try:
                return date(yr, mon_cand, day_cand).isoformat()
            except ValueError:
                continue

    return ""


def normalize_extracted_number(raw_val: Any) -> float:
    """Extracts a clean float from currency/metric strings like `Rs. 18,450.50` or `$1,200`."""
    if isinstance(raw_val, (int, float)):
        return round(float(raw_val), 2)
    s = str(raw_val or "").strip()
    if not s:
        return 0.0
    cleaned = s.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not m:
        return 0.0
    try:
        return round(float(m.group(0)), 2)
    except ValueError:
        return 0.0


def detect_document_scenario(
    filename: str = "",
    raw_text: str = "",
    agent_context: str = "",
) -> Dict[str, Any]:
    """Scores the document and agent context against the 8 domain extraction profiles."""
    haystack = f"{filename}\n{agent_context}\n{raw_text[:8000]}".lower()
    best_profile = DOCUMENT_SCENARIO_PROFILES[0]
    best_score = -1
    for prof in DOCUMENT_SCENARIO_PROFILES:
        score = 0
        for kw in prof["keywords"]:
            if kw in haystack:
                score += 3 if kw in agent_context.lower() or kw in filename.lower() else 2
        if score > best_score:
            best_score = score
            best_profile = prof
    return dict(best_profile)


def _build_llm_extraction_prompt(
    filename: str,
    extracted_text: str,
    scenario: Dict[str, Any],
    agent_name: str = "",
    agent_description: str = "",
    agent_system_prompt: str = "",
    fields: Optional[List[Dict[str, Any]]] = None,
    extraction_hint: str = "",
    include_blueprint_suggestion: bool = False,
) -> Tuple[str, str]:
    """Constructs system instruction and structured JSON extraction prompt for the LLM."""
    today_iso = date.today().isoformat()
    eff_fields = fields or scenario.get("recommended_fields") or []
    fields_spec_lines = [
        f'- "{f.get("key")}" ({f.get("type", "text")}): {f.get("label", f.get("key"))}'
        for f in eff_fields
        if isinstance(f, dict) and f.get("key")
    ]
    fields_block = "\n".join(fields_spec_lines) or '- "title" (text)\n- "due_date" (date)\n- "numeric_value" (number)'

    sys_inst = (
        "You are an expert Document Intelligence & Structured Tracking Extractor inside the "
        "Personal Agentic Fleet Control Center. Extract accurate, actionable items for ongoing "
        "tracking (renewals, expiries, due dates, biomarkers, milestones, warranties, obligations) "
        "and return STRICT valid JSON only (no markdown prose outside JSON)."
    )

    blueprint_schema_note = ""
    if include_blueprint_suggestion:
        blueprint_schema_note = (
            '  "suggested_agent": {\n'
            '    "name": "Concise 2-4 word Agent Name",\n'
            '    "icon": "Single emoji",\n'
            '    "category": "Finance | Health | Productivity | Knowledge | Monitoring | DevOps | System | Utility",\n'
            '    "description": "1-sentence operational goal tailored to this document type",\n'
            '    "fields": [{"key": "snake_case", "label": "Human Label", "type": "text|date|number|url", "placeholder": "..."}]\n'
            "  },\n"
        )

    user_prompt = (
        f"Current Date: {today_iso}\n"
        f"Source Document Filename: {filename}\n"
        f"Detected Domain Scenario: {scenario.get('title')} ({scenario.get('id')})\n"
        f"Target Agent: {agent_name or scenario.get('default_agent_name')}\n"
        f"Agent Purpose: {agent_description or scenario.get('extraction_focus')}\n"
    )
    if agent_system_prompt:
        user_prompt += f"Agent Custom Directive: {agent_system_prompt}\n"
    if extraction_hint:
        user_prompt += f"User Extraction Focus / Hint: {extraction_hint}\n"

    user_prompt += (
        f"\nAgent Tracked Schema Fields:\n{fields_block}\n\n"
        f"Domain Extraction Guidance:\n{scenario.get('extraction_focus')}\n\n"
        "Return ONLY a JSON object matching this exact structure:\n"
        "{\n"
        '  "document_summary": "Concise 1-2 sentence executive summary of key facts in the document",\n'
        f'  "detected_scenario": "{scenario.get("id")}",\n'
        f"{blueprint_schema_note}"
        '  "items": [\n'
        "    {\n"
        '      "title": "Clear actionable item name (e.g. HDFC Ergo Car Policy #POL-9921 - KA01AB1234)",\n'
        '      "due_date": "YYYY-MM-DD (expiry, renewal, payment due, exam, or next review date; empty string if none)",\n'
        '      "numeric_value": 0.0,\n'
        '      "confidence": "high",\n'
        '      "extra_fields": {\n'
        '        "<any additional schema field keys from above>": "extracted value"\n'
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )
    if extracted_text:
        user_prompt += f"\n--- BEGIN DOCUMENT CONTENT ---\n{extracted_text[:28000]}\n--- END DOCUMENT CONTENT ---\n"
    else:
        user_prompt += "\nInspect the attached document/image directly and extract all trackable items.\n"

    return sys_inst, user_prompt


def _try_multimodal_direct_llm(
    raw_bytes: bytes,
    mime_type: str,
    sys_inst: str,
    user_prompt: str,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Sends raw PDF or Image bytes directly to Gemini Multimodal (`inlineData`) or
    Anthropic Claude (`document` / `image`) when direct API keys are configured.
    Ideal for scanned policy PDFs, photos of receipts/prescriptions, and complex tables.
    """
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return None

    b64_data = base64.b64encode(raw_bytes).decode("ascii")

    # 1. Google Gemini Direct REST API (supports both image/* and application/pdf inlineData)
    gemini_key = get_secure_secret("GEMINI_API_KEY") or get_secure_secret("GOOGLE_API_KEY")
    if gemini_key:
        try:
            eff_model = model if (model and "gemini" in model.lower() and "argon" not in model.lower() and "3.8" not in model.lower()) else "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{eff_model}:generateContent?key={gemini_key}"
            payload: Dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": sys_inst}]},
                "contents": [
                    {
                        "parts": [
                            {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                            {"text": user_prompt},
                        ]
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                txt = data["candidates"][0]["content"]["parts"][0]["text"]
                tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 0) or 0)
                return {
                    "status": "SUCCESS",
                    "provider": "Google Gemini Multimodal",
                    "model": eff_model,
                    "tokens_used": tokens,
                    "text": txt,
                }
        except Exception as exc:
            logger.debug(f"Gemini multimodal direct call skipped/fell back: {exc}")

    # 2. Anthropic Claude Messages API (supports image/* and application/pdf)
    anthropic_key = get_secure_secret("ANTHROPIC_API_KEY")
    if anthropic_key and (mime_type.startswith("image/") or mime_type == "application/pdf"):
        try:
            block_type = "document" if mime_type == "application/pdf" else "image"
            payload = {
                "model": "claude-3-5-sonnet-latest",
                "max_tokens": 2048,
                "system": sys_inst,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": block_type,
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": b64_data,
                                },
                            },
                            {"type": "text", "text": user_prompt},
                        ],
                    }
                ],
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                txt = data["content"][0]["text"]
                usage = data.get("usage", {})
                tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
                return {
                    "status": "SUCCESS",
                    "provider": "Anthropic Claude Multimodal",
                    "model": "claude-3-5-sonnet-latest",
                    "tokens_used": tokens,
                    "text": txt,
                }
        except Exception as exc:
            logger.debug(f"Claude multimodal direct call skipped/fell back: {exc}")

    return None


import os


def _parse_llm_extraction_json(raw_response: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses the JSON object returned by an LLM even if wrapped in code fences."""
    if not raw_response or not isinstance(raw_response, str):
        return None
    cleaned = raw_response.strip()
    m_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S)
    if m_fence:
        cleaned = m_fence.group(1).strip()
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and (
            isinstance(parsed.get("items"), list)
            or isinstance(parsed.get("suggested_agent"), dict)
            or isinstance(parsed.get("workflow_guidance"), dict)
        ):
            if not isinstance(parsed.get("items"), list):
                parsed["items"] = []
            return parsed
    except Exception:
        pass
    return None


def _normalize_extracted_items(
    raw_items: List[Dict[str, Any]],
    source_filename: str,
    scenario_id: str,
    fields: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Normalizes LLM or deterministic items against the agent's typed fields schema."""
    eff_fields = fields or []
    date_keys = [f["key"] for f in eff_fields if isinstance(f, dict) and f.get("type") == "date" and f.get("key")]
    num_keys = [f["key"] for f in eff_fields if isinstance(f, dict) and f.get("type") == "number" and f.get("key")]
    url_keys = [f["key"] for f in eff_fields if isinstance(f, dict) and f.get("type") == "url" and f.get("key")]
    extra_schema_keys = [
        f["key"]
        for f in eff_fields
        if isinstance(f, dict)
        and f.get("key")
        and f.get("key") not in ("title", "due_date", "numeric_value")
    ]

    normalized: List[Dict[str, Any]] = []
    seen_sigs = set()

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        raw_extra = raw.get("extra_fields")
        extra_in: Dict[str, Any] = dict(raw_extra) if isinstance(raw_extra, dict) else {}
        for k, v in raw.items():
            if k not in ("title", "due_date", "numeric_value", "confidence", "extra_fields", "status") and v not in (None, ""):
                extra_in.setdefault(k, v)

        title = str(
            raw.get("title")
            or raw.get("name")
            or raw.get("item")
            or extra_in.get("policy_name")
            or ""
        ).strip()
        if not title:
            continue

        due_candidates = [raw.get("due_date"), *[extra_in.get(k) for k in date_keys]]
        due_iso = ""
        for cand in due_candidates:
            due_iso = normalize_extracted_date(cand)
            if due_iso:
                break

        num_candidates = [raw.get("numeric_value"), *[extra_in.get(k) for k in num_keys]]
        num_val = 0.0
        for cand in num_candidates:
            if cand not in (None, "", 0, 0.0):
                num_val = normalize_extracted_number(cand)
                if num_val != 0.0:
                    break

        cleaned_extra: Dict[str, Any] = {
            "source_document": source_filename,
            "scenario": scenario_id,
        }
        for k in extra_schema_keys:
            if k in extra_in and extra_in[k] not in (None, ""):
                cleaned_extra[k] = str(extra_in[k]).strip()[:200]
        for k, v in extra_in.items():
            if k not in ("title", "due_date", "numeric_value") and v not in (None, "") and k not in cleaned_extra:
                cleaned_extra[str(k)[:48]] = str(v).strip()[:200]
        for uk in url_keys:
            if cleaned_extra.get(uk) and "target_url" not in cleaned_extra:
                cleaned_extra["target_url"] = cleaned_extra[uk]

        sig = (title.lower(), due_iso, num_val)
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)

        normalized.append({
            "title": title[:160],
            "due_date": due_iso,
            "numeric_value": num_val,
            "status": "ok",
            "confidence": str(raw.get("confidence") or "high").lower(),
            "extra_fields": cleaned_extra,
        })

    return normalized[:50]


# ---------------------------------------------------------------------------
# High-Precision Deterministic $0.00 Multi-Scenario Fallback Extractor
# ---------------------------------------------------------------------------

_EXPIRY_LABEL_RE = re.compile(
    r"(?:expiry\s*date|expiration\s*date|valid\s*(?:till|until|upto|through)|renewal\s*date|"
    r"policy\s*end\s*date|due\s*date|payment\s*due|maturity\s*date|next\s*(?:review|refill|service|test)|"
    r"submission\s*date|exam\s*date|departure(?:\s*date)?|check-?in(?:\s*date)?|end\s*date)"
    r"\s*[:\-–]?\s*([^\n|]{4,44})",
    flags=re.I,
)

_INSURANCE_PERIOD_TO_RE = re.compile(
    r"(?:period\s*of\s*(?:own\s*damage\s*|third\s*party\s*)?insurance|own\s*damage\s*(?:policy\s*)?period|"
    r"policy\s*period|coverage\s*period|validity|policy\s*validity)"
    r"[\s\S]{0,120}?(?:\b(?:to|till|until|upto)\b|\s[-–]\s)\s*(?:midnight\s*(?:of|on)\s*|23:59(?:\s*hrs)?\s*(?:on)?\s*)?"
    r"(\d{1,2}(?:st|nd|rd|th)?[\s\-/,.]+[A-Za-z]{3,9}\.?[\s\-/,.]+(?:20\d{2}|\d{2})|20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d{2})",
    flags=re.I,
)

_MIDNIGHT_EXPIRY_RE = re.compile(
    r"(?:midnight\s*(?:of|on)|23:59(?:\s*hrs)?\s*(?:on|of))\s*"
    r"([0-9]{1,2}[\s\-/,]+[A-Za-z]{3,9}[\s\-/,]+20\d{2}|20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+20\d{2})",
    flags=re.I,
)

_KNOWN_INSURER_BRAND_RE = re.compile(
    r"\b(Acko\s+General\s+Insurance|ACKO\s+Technology|Acko|HDFC\s+ERGO|ICICI\s+Lombard|Bajaj\s+Allianz|"
    r"Star\s+Health|Niva\s+Bupa|Care\s+Health|Tata\s+AIG|Go\s+Digit|Digit\s+Insurance|"
    r"New\s+India\s+Assurance|United\s+India\s+Insurance|Oriental\s+Insurance|National\s+Insurance|"
    r"SBI\s+General|Kotak\s+Mahindra\s+General|Reliance\s+General|Aditya\s+Birla\s+Health|"
    r"Life\s+Insurance\s+Corporation|LIC\s+of\s+India|Max\s+Bupa|ManipalCigna|Royal\s+Sundaram|Chola\s+MS)\b",
    flags=re.I,
)

_INDIAN_VEHICLE_REG_RE = re.compile(
    r"\b([A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4})\b"
)

_AMOUNT_LABEL_RE = re.compile(
    r"(?:total\s*premium|annual\s*premium|net\s*premium|premium\s*(?:amount|payable)|"
    r"amount\s*(?:due|payable)|total\s*(?:amount|due|payable)|balance\s*due|maturity\s*(?:amount|value)|"
    r"contract\s*value|monthly\s*rent|sum\s*insured|idv|purchase\s*price|grand\s*total|fare|fee)"
    r"\s*(?:\([^)]*\))?\s*[:\-–]?\s*(?:INR|Rs\.?|USD|\$|EUR|€|₹)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
    flags=re.I,
)

_REF_NUMBER_RE = re.compile(
    r"(?:policy\s*(?:no|number|#)|invoice\s*(?:no|number|#)|contract\s*(?:no|id|#)|"
    r"pnr|booking\s*(?:id|ref)|passport\s*(?:no|number)|serial\s*(?:no|number)|"
    r"fd\s*(?:no|number)|account\s*(?:no|number))"
    r"\s*[:\-–#]?\s*([A-Z0-9][A-Z0-9\-/]{3,28})",
    flags=re.I,
)

_INSURER_OR_VENDOR_RE = re.compile(
    r"(?:insurer|insurance\s*company|provider|underwriter|vendor|biller|payee|landlord|airline|hospital|lab|bank|issuer)"
    r"\s*[:\-–]?\s*([A-Za-z0-9 &.,()\-]{3,60})",
    flags=re.I,
)

_VEHICLE_OR_ASSET_RE = re.compile(
    r"(?:vehicle\s*(?:reg(?:istration)?|no)|registration\s*(?:no|number)|insured\s*(?:asset|member|name)|patient\s*name|asset|product|model)"
    r"\s*[:\-–]?\s*([A-Za-z0-9 \-./()]{3,55})",
    flags=re.I,
)


def _deterministic_extract_tracking_items(
    extracted_text: str,
    filename: str,
    scenario: Dict[str, Any],
    fields: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Zero-token ($0.00) multi-scenario document extractor.
    Handles tabular documents (CSV/XLSX/Markdown/Pipe tables), ICS calendar feeds,
    clinical lab report biomarker lines, multi-section policies/syllabi, and key-value documents.
    """
    text = (extracted_text or "").strip()
    stem_title = Path(filename).stem.replace("_", " ").replace("-", " ").strip().title() or "Uploaded Document"
    items: List[Dict[str, Any]] = []

    if not text:
        return {
            "document_summary": f"Uploaded '{filename}' ({scenario.get('title')}). Configure a Multimodal LLM key (Gemini / Claude) to OCR visual image scans.",
            "detected_scenario": scenario["id"],
            "items": [],
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 1. ICS Calendar Events (`EVENT N: Summary | Date: YYYY-MM-DD ...`)
    for ln in lines:
        m_ev = re.match(r"^EVENT\s+\d+:\s*(.+?)\s*\|\s*Date:\s*([0-9\-]+)(?:\s*\|\s*(.*))?$", ln)
        if m_ev:
            ev_title = m_ev.group(1).strip()
            ev_date = normalize_extracted_date(m_ev.group(2))
            rest = m_ev.group(3) or ""
            items.append({
                "title": ev_title,
                "due_date": ev_date,
                "numeric_value": normalize_extracted_number(rest),
                "confidence": "high",
                "extra_fields": {"notes": rest[:140]} if rest else {},
            })

    # 2. Structured Pipe / CSV / XLSX Table Rows (`HEADERS: ...` / `ROW N: ...` or `Col1 | Col2 | Col3`)
    if not items:
        header_cols: List[str] = []
        for ln in lines:
            if ln.startswith("HEADERS:"):
                header_cols = [c.strip().lower() for c in ln[len("HEADERS:"):].split("|")]
                continue
            row_body = ln[ln.find(":") + 1:].strip() if re.match(r"^ROW\s+\d+:", ln) else (ln if ln.count("|") >= 2 else "")
            if not row_body:
                continue
            cells = [c.strip() for c in row_body.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            # Skip markdown separator rows like `--- | ---`
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            if not header_cols and any(h in cells[0].lower() for h in ("name", "title", "policy", "item", "test", "parameter", "milestone")):
                header_cols = [c.lower() for c in cells]
                continue

            row_title = cells[0]
            row_date = ""
            row_num = 0.0
            row_extra: Dict[str, Any] = {}
            for idx_c, cell_val in enumerate(cells[1:], 1):
                col_name = header_cols[idx_c] if idx_c < len(header_cols) else f"col_{idx_c}"
                cand_dt = normalize_extracted_date(cell_val)
                if cand_dt and not row_date:
                    row_date = cand_dt
                elif row_num == 0.0 and re.search(r"\d", cell_val) and not cand_dt:
                    # Avoid treating pure policy IDs like POL-2026-991 as currency amounts
                    if not re.match(r"^[A-Z]{2,}[-/][A-Z0-9\-/]+$", cell_val, flags=re.I):
                        row_num = normalize_extracted_number(cell_val)
                        if any(flag in col_name for flag in ("ref", "range", "status", "flag", "insurer", "policy", "no")):
                            row_extra[re.sub(r"[^a-z0-9_]", "_", col_name).strip("_") or f"detail_{idx_c}"] = cell_val
                else:
                    clean_k = re.sub(r"[^a-z0-9_]", "_", col_name).strip("_") or f"detail_{idx_c}"
                    row_extra[clean_k] = cell_val
            if row_title and (row_date or row_num != 0.0 or row_extra):
                items.append({
                    "title": row_title,
                    "due_date": row_date,
                    "numeric_value": row_num,
                    "confidence": "high",
                    "extra_fields": row_extra,
                })

    # 3. Clinical Lab Report Biomarker Lines (e.g. `HbA1c: 7.1 % (Ref: < 5.7) - High / Diabetic`)
    if not items and scenario["id"] == "medical_lab_rx":
        next_review_m = _EXPIRY_LABEL_RE.search(text)
        default_review_dt = normalize_extracted_date(next_review_m.group(1)) if next_review_m else ""
        lab_re = re.compile(
            r"^([A-Za-z][A-Za-z0-9 /()\-]{2,38}?)\s*[:\-–|]\s*(\d+(?:\.\d+)?)\s*"
            r"(mg/dL|ng/mL|pg/mL|U/L|mL/min|%|µIU/mL|mmol/L|g/dL)?(.*)$",
            flags=re.I,
        )
        for ln in lines:
            m_lab = lab_re.match(ln)
            if not m_lab:
                continue
            marker = m_lab.group(1).strip()
            if marker.lower() in ("date", "age", "page", "phone", "time", "id"):
                continue
            val = normalize_extracted_number(m_lab.group(2))
            unit = (m_lab.group(3) or "").strip()
            tail = (m_lab.group(4) or "").strip(" -|:,")
            is_flagged = any(
                w in tail.lower() or w in ln.lower()
                for w in ("high", "low", "elevated", "diabetic", "prediabetes", "abnormal", "borderline", "deficient", "positive")
            )
            if is_flagged or unit:
                items.append({
                    "title": f"{marker} ({val} {unit})".strip(),
                    "due_date": default_review_dt,
                    "numeric_value": val,
                    "confidence": "high" if is_flagged else "medium",
                    "extra_fields": {
                        "reference_note": f"{unit} {tail}".strip()[:160],
                        "clinical_flag": "Attention" if is_flagged else "Tracked",
                    },
                })

    # 4. Multi-bullet / Multi-milestone lines with embedded dates (Syllabi, SOWs, Explicit Bulleted Policy Lists)
    single_certificate_scenarios = {"insurance_policy", "invoice_receipt", "warranty_asset", "financial_fd_bond"}
    is_single_cert_doc = scenario["id"] in single_certificate_scenarios and bool(
        _REF_NUMBER_RE.search(text) or _INSURANCE_PERIOD_TO_RE.search(text) or len(lines) > 25
    )
    if not items:
        dated_lines: List[Dict[str, Any]] = []
        for ln in lines:
            if len(ln) > 220:
                continue
            # Inside a single insurance certificate / invoice / warranty PDF, only treat explicit bulleted list items
            # as multi-item rows so certificate metadata lines (Issue Date, Receipt Date, Registration Date) don't fragment it.
            if is_single_cert_doc and not re.match(r"^(?:[\-*•]|\d{1,2}[.)])\s+", ln):
                continue
            # Skip pure metadata label lines like "Expiry Date: 2027-04-15" (handled cleanly by Document Key-Value Synthesis below)
            if re.match(
                r"^(?:policy\s*(?:end|start|expiry)?\s*date|expiry\s*date|expiration\s*date|valid\s*(?:till|until|upto)|"
                r"renewal\s*date|due\s*date|payment\s*due|maturity\s*date|issue\s*date|invoice\s*date|date\s*of\s*\w+)\s*[:\-–]",
                ln,
                flags=re.I,
            ):
                continue
            dt_iso = normalize_extracted_date(ln)
            if not dt_iso:
                continue
            # Clean out the date substring to inspect the remaining label
            label_part = re.sub(
                r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}|"
                r"\d{1,2}[\s\-/,]+[A-Za-z]{3,9}[\s\-/,]+20\d{2}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+20\d{2})\b",
                "",
                ln,
            )
            label_part = re.sub(r"\b(?:due|on|by|expires?|valid\s*till|expiry|date)\b\s*[:\-–]?", "", label_part, flags=re.I)
            amt_m = re.search(r"(?:INR|Rs\.?|USD|\$|EUR|€|₹)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", label_part, flags=re.I)
            amt_val = normalize_extracted_number(amt_m.group(1)) if amt_m else 0.0
            if amt_m:
                label_part = (label_part[:amt_m.start()] + label_part[amt_m.end():]).strip()
            clean_lbl = re.sub(r"^[\-*•\d.)\s]+", "", label_part).strip(" -–:|,()")
            if len(clean_lbl) >= 4:
                dated_lines.append({
                    "title": clean_lbl[:140],
                    "due_date": dt_iso,
                    "numeric_value": amt_val,
                    "confidence": "high",
                    "extra_fields": {},
                })
        if len(dated_lines) >= 2:
            items.extend(dated_lines)

    # 5. Primary Document Key-Value Synthesis (Single Policy / Contract / Invoice / Warranty / FD PDF)
    if not items:
        due_iso = ""
        for rx_exp in (_INSURANCE_PERIOD_TO_RE, _EXPIRY_LABEL_RE, _MIDNIGHT_EXPIRY_RE):
            for m_exp in rx_exp.finditer(text):
                cand_iso = normalize_extracted_date(m_exp.group(1))
                if cand_iso and cand_iso > due_iso:
                    due_iso = cand_iso
            if due_iso:
                break
        if not due_iso:
            # Fallback: pick the latest future/valid date mentioned in the document
            all_dates: List[str] = []
            for ln in lines[:160]:
                d_cand = normalize_extracted_date(ln)
                if d_cand:
                    all_dates.append(d_cand)
            if all_dates:
                due_iso = sorted(all_dates)[-1]

        m_amt = _AMOUNT_LABEL_RE.search(text)
        num_val = normalize_extracted_number(m_amt.group(1)) if m_amt else 0.0
        if num_val == 0.0:
            m_curr = re.search(r"(?:INR|Rs\.?|USD|\$|EUR|€|₹)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text, flags=re.I)
            if m_curr:
                num_val = normalize_extracted_number(m_curr.group(1))

        m_ref = _REF_NUMBER_RE.search(text)
        ref_no = m_ref.group(1).strip() if m_ref else ""

        m_brand = _KNOWN_INSURER_BRAND_RE.search(text[:4000])
        m_vendor = _INSURER_OR_VENDOR_RE.search(text)
        vendor = ""
        if m_brand:
            raw_b = re.sub(r"\s+", " ", m_brand.group(1)).strip()
            vendor = "Acko General Insurance" if raw_b.lower().startswith("acko") else raw_b
        elif m_vendor:
            cand_v = m_vendor.group(1).strip(" .,-|")
            if len(cand_v) <= 48 and not any(sw in cand_v.lower() for sw in ("gstin", "address", "email", "phone", "irda")):
                vendor = cand_v

        m_reg = _INDIAN_VEHICLE_REG_RE.search(text[:6000]) if scenario["id"] == "insurance_policy" else None
        m_asset = _VEHICLE_OR_ASSET_RE.search(text)
        asset = ""
        if m_reg:
            asset = re.sub(r"\s+", "-", m_reg.group(1).strip().upper())
        elif m_asset:
            cand_a = m_asset.group(1).strip(" .,-|")
            if 2 <= len(cand_a) <= 42:
                asset = cand_a

        # Infer specific Car / Bike / Health policy label when scenario is insurance_policy
        headline = ""
        if scenario["id"] == "insurance_policy":
            low_head = text[:4500].lower()
            if any(k in low_head for k in ("two wheeler", "two-wheeler", "bike", "motorcycle", "scooter")):
                headline = "Two-Wheeler / Bike Insurance Policy"
            elif any(k in low_head for k in ("private car", "four wheeler", "motor car", "passenger car", "comprehensive car", "own damage policy")):
                headline = "Private Car Insurance Policy"
            elif any(k in low_head for k in ("health insurance", "mediclaim", "hospitalization", "sum insured", "floater")):
                headline = "Health Insurance Policy"
        if not headline:
            for ln in lines[:8]:
                if 5 <= len(ln) <= 85 and not ln.lower().startswith(("date:", "page ", "from:", "to:")):
                    headline = ln
                    break

        title_parts = [p for p in (vendor, headline or stem_title) if p]
        if len(title_parts) == 2 and title_parts[0].lower() in title_parts[1].lower():
            base_title = title_parts[1]
        else:
            base_title = " — ".join(title_parts) if title_parts else stem_title
        if asset and asset.lower() not in base_title.lower():
            base_title = f"{base_title} ({asset})"
        elif ref_no and ref_no.lower() not in base_title.lower():
            base_title = f"{base_title} [{ref_no}]"

        extra: Dict[str, Any] = {}
        if ref_no:
            extra["policy_number"] = ref_no
            extra["invoice_number"] = ref_no
            extra["reference_code"] = ref_no
        if vendor:
            extra["insurer"] = vendor
            extra["counterparty"] = vendor
        if asset:
            extra["asset"] = asset

        items.append({
            "title": base_title[:150],
            "due_date": due_iso,
            "numeric_value": num_val,
            "confidence": "high" if (due_iso or num_val > 0) else "medium",
            "extra_fields": extra,
        })

    norm_items = _normalize_extracted_items(items, filename, scenario["id"], fields=fields)
    summary_bits = [f"Extracted {len(norm_items)} trackable item{'s' if len(norm_items) != 1 else ''} from '{filename}' ({scenario['title']})."]
    if norm_items and norm_items[0].get("due_date"):
        summary_bits.append(f"Primary due/expiry date: {norm_items[0]['due_date']}.")
    if norm_items and norm_items[0].get("numeric_value"):
        summary_bits.append(f"Primary value: {norm_items[0]['numeric_value']:,.2f}.")

    return {
        "document_summary": " ".join(summary_bits),
        "detected_scenario": scenario["id"],
        "items": norm_items,
    }


# ---------------------------------------------------------------------------
# Main Public Entrypoints: Runtime Agent Extraction & Studio Creation Analysis
# ---------------------------------------------------------------------------

def extract_tracking_items_from_document(
    filename: str = "",
    content_base64: str = "",
    text_content: str = "",
    agent_id: str = "",
    agent_name: str = "",
    agent_description: str = "",
    agent_system_prompt: str = "",
    fields: Optional[List[Dict[str, Any]]] = None,
    provider: str = "auto",
    model: Optional[str] = None,
    extraction_hint: str = "",
    persist_to_vault: bool = True,
    include_blueprint_suggestion: bool = False,
    existing_vault_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    End-to-end document ingestion & LLM extraction pipeline:
    1. Safely decodes & parses `.pdf`, `.docx`, `.xlsx`, `.csv`, `.eml`, `.ics`, `.html`, `.txt`, or images.
    2. Persists original file inside `fleet/data/user/agent_docs/<agent_id>/` when `persist_to_vault=True`.
    3. Detects the best domain scenario profile (Insurance, Contract, Invoice, Lab/Rx, Travel/Visa, Warranty, Syllabus, FD/Bond).
    4. Invokes Multimodal LLM (for images/scanned PDFs) or HyperscalerGateway / Antigravity LLM with schema-aware JSON extraction.
    5. Gracefully falls back to deterministic multi-scenario extraction when offline so extraction never fails.
    """
    parsed_doc = parse_uploaded_document(
        filename=filename,
        content_base64=content_base64,
        text_content=text_content,
    )
    safe_name = parsed_doc["filename"]
    raw_bytes = parsed_doc["raw_bytes"]
    extracted_text = parsed_doc["extracted_text"]
    is_visual = parsed_doc["is_visual_media"]
    mime_type = parsed_doc["mime_type"]

    vault_info: Optional[Dict[str, Any]] = dict(existing_vault_info) if isinstance(existing_vault_info, dict) else None
    if persist_to_vault and vault_info is None:
        try:
            vault_info = save_agent_document_to_vault(agent_id or "studio_staging", safe_name, raw_bytes)
        except Exception as exc:
            logger.warning(f"Could not save document to vault: {exc}")

    agent_ctx = f"{agent_name} {agent_description} {agent_system_prompt} {extraction_hint}"
    scenario = detect_document_scenario(filename=safe_name, raw_text=extracted_text, agent_context=agent_ctx)
    eff_fields = fields if fields else scenario.get("recommended_fields")

    sys_inst, llm_prompt = _build_llm_extraction_prompt(
        filename=safe_name,
        extracted_text=extracted_text,
        scenario=scenario,
        agent_name=agent_name,
        agent_description=agent_description,
        agent_system_prompt=agent_system_prompt,
        fields=eff_fields,
        extraction_hint=extraction_hint,
        include_blueprint_suggestion=include_blueprint_suggestion,
    )

    llm_parsed: Optional[Dict[str, Any]] = None
    engine_used = "tier0_deterministic_extractor"
    model_used = "deterministic-$0.00"
    tokens_used = 0

    # Layer 1: Direct Multimodal Vision/PDF LLM for scanned PDFs or images
    if is_visual or (parsed_doc["extension"] == ".pdf" and len(extracted_text) < 120):
        mm_res = _try_multimodal_direct_llm(
            raw_bytes=raw_bytes,
            mime_type=mime_type,
            sys_inst=sys_inst,
            user_prompt=llm_prompt,
            model=model,
        )
        if mm_res and mm_res.get("text"):
            llm_parsed = _parse_llm_extraction_json(mm_res["text"])
            if llm_parsed:
                engine_used = str(mm_res.get("provider") or "multimodal_llm")
                model_used = str(mm_res.get("model") or model or "multimodal")
                tokens_used = int(mm_res.get("tokens_used", 0) or 0)

    # Layer 2: Configured / Available Antigravity or Hyperscaler LLM Gateway
    if llm_parsed is None and extracted_text and (provider or "auto").lower() != "deterministic":
        try:
            from fleet.core.hyperscalers import HyperscalerGateway
            gw = HyperscalerGateway()
            gw_res = gw.complete(
                prompt=llm_prompt,
                provider=provider or "auto",
                model=model or None,
                system_instruction=sys_inst,
                max_tokens=2048,
                allow_tier0=False,
                max_prompt_chars=34000,
            )
            prov_name = str(gw_res.get("provider") or "")
            if "heuristic" not in prov_name.lower() and gw_res.get("text"):
                cand = _parse_llm_extraction_json(str(gw_res["text"]))
                if cand and cand.get("items"):
                    llm_parsed = cand
                    engine_used = prov_name or "HyperscalerGateway"
                    model_used = str(gw_res.get("model") or model or "llm")
                    tokens_used = int(gw_res.get("tokens_used", 0) or 0)
        except Exception as exc:
            logger.debug(f"Hyperscaler LLM document extraction fell back to deterministic parser: {exc}")

    # Layer 3: Deterministic Multi-Scenario Extraction (or hybrid merge if LLM returned 0 items)
    if llm_parsed and llm_parsed.get("items"):
        norm_items = _normalize_extracted_items(
            llm_parsed["items"],
            source_filename=safe_name,
            scenario_id=str(llm_parsed.get("detected_scenario") or scenario["id"]),
            fields=eff_fields,
        )
        doc_summary = str(llm_parsed.get("document_summary") or f"Extracted {len(norm_items)} tracking items from {safe_name}.").strip()
        suggested_agent = llm_parsed.get("suggested_agent") if isinstance(llm_parsed.get("suggested_agent"), dict) else None
    else:
        det = _deterministic_extract_tracking_items(
            extracted_text=extracted_text,
            filename=safe_name,
            scenario=scenario,
            fields=eff_fields,
        )
        norm_items = det["items"]
        doc_summary = det["document_summary"]
        suggested_agent = None

    return {
        "status": "ok",
        "filename": safe_name,
        "extension": parsed_doc["extension"],
        "size_bytes": parsed_doc["size_bytes"],
        "char_count": parsed_doc["char_count"],
        "parser_used": parsed_doc["parser_used"],
        "engine_used": engine_used,
        "model_used": model_used,
        "tokens_used": tokens_used,
        "detected_scenario": scenario["id"],
        "scenario_profile": {
            "id": scenario["id"],
            "title": scenario["title"],
            "icon": scenario["icon"],
            "category": scenario["category"],
        },
        "document_summary": doc_summary,
        "items": norm_items,
        "items_count": len(norm_items),
        "suggested_agent": suggested_agent,
        "vault": vault_info,
        "text_preview": extracted_text[:600],
    }


def extract_tracking_items_from_documents_batch(
    documents: List[Dict[str, Any]],
    agent_id: str = "",
    agent_name: str = "",
    agent_description: str = "",
    agent_system_prompt: str = "",
    fields: Optional[List[Dict[str, Any]]] = None,
    provider: str = "auto",
    model: Optional[str] = None,
    extraction_hint: str = "",
    persist_to_vault: bool = True,
) -> List[Dict[str, Any]]:
    """
    Extracts structured tracking items across 1..10 documents in a single batched LLM call
    (instead of N sequential CLI spawns), falling back deterministically per attachment so
    every document contributes clean tracking items rapidly.
    """
    if len(documents) <= 1:
        if not documents:
            return []
        d0 = documents[0]
        return [
            extract_tracking_items_from_document(
                filename=str(d0.get("filename") or ""),
                content_base64=str(d0.get("content_base64") or ""),
                text_content=str(d0.get("text_content") or ""),
                agent_id=agent_id,
                agent_name=agent_name,
                agent_description=agent_description,
                agent_system_prompt=agent_system_prompt,
                fields=fields,
                provider=provider,
                model=model,
                extraction_hint=extraction_hint,
                persist_to_vault=persist_to_vault,
                existing_vault_info=d0.get("existing_vault_info") if isinstance(d0.get("existing_vault_info"), dict) else None,
            )
        ]

    agent_ctx = f"{agent_name} {agent_description} {agent_system_prompt} {extraction_hint}"
    prepared: List[Dict[str, Any]] = []
    for d_in in documents[:MAX_MULTI_ATTACHMENTS]:
        parsed_doc = parse_uploaded_document(
            filename=str(d_in.get("filename") or ""),
            content_base64=str(d_in.get("content_base64") or ""),
            text_content=str(d_in.get("text_content") or ""),
        )
        safe_name = parsed_doc["filename"]
        raw_bytes = parsed_doc["raw_bytes"]
        extracted_text = parsed_doc["extracted_text"]
        vault_info: Optional[Dict[str, Any]] = (
            dict(d_in["existing_vault_info"])
            if isinstance(d_in.get("existing_vault_info"), dict)
            else None
        )
        if persist_to_vault and vault_info is None:
            try:
                vault_info = save_agent_document_to_vault(agent_id or "studio_staging", safe_name, raw_bytes)
            except Exception as exc:
                logger.warning(f"Could not save document to vault: {exc}")
        scenario = detect_document_scenario(filename=safe_name, raw_text=extracted_text, agent_context=agent_ctx)
        eff_fields = fields if fields else scenario.get("recommended_fields")
        det_res = _deterministic_extract_tracking_items(
            extracted_text=extracted_text,
            filename=safe_name,
            scenario=scenario,
            fields=eff_fields,
        )
        prepared.append({
            "input": d_in,
            "parsed_doc": parsed_doc,
            "safe_name": safe_name,
            "extracted_text": extracted_text,
            "vault_info": vault_info,
            "scenario": scenario,
            "eff_fields": eff_fields,
            "det": det_res,
        })

    batch_llm_items_by_doc: Dict[str, List[Dict[str, Any]]] = {}
    batch_summaries_by_doc: Dict[str, str] = {}
    engine_used = "tier0_deterministic_extractor"
    model_used = "deterministic-$0.00"
    tokens_used = 0

    has_text_docs = any(bool(p["extracted_text"]) for p in prepared)
    if has_text_docs and (provider or "auto").lower() != "deterministic":
        try:
            from fleet.core.hyperscalers import HyperscalerGateway
            today_iso = date.today().isoformat()
            eff_schema = fields or prepared[0]["eff_fields"] or []
            fields_block = "\n".join(
                f'- "{f.get("key")}" ({f.get("type", "text")}): {f.get("label", f.get("key"))}'
                for f in eff_schema
                if isinstance(f, dict) and f.get("key")
            ) or '- "title" (text)\n- "due_date" (date)\n- "numeric_value" (number)'
            per_doc_budget = max(3200, 30000 // max(1, len(prepared)))

            sys_inst = (
                "You are an expert Multi-Document Tracking Extractor inside the Personal Agentic Fleet "
                "Control Center. Extract actionable tracking items (renewals, expiries, premiums, policy/ref numbers, "
                "due dates, obligations) across ALL provided attachments and return STRICT valid JSON only."
            )
            prompt_lines = [
                f"Current Date: {today_iso}",
                f"Target Agent: {agent_name or agent_id}",
                f"Agent Purpose: {agent_description}",
            ]
            if agent_system_prompt:
                prompt_lines.append(f"Agent Directive: {agent_system_prompt}")
            if extraction_hint:
                prompt_lines.append(f"User Extraction Focus / Hint: {extraction_hint}")
            prompt_lines.append(
                f"\nAgent Tracked Schema Fields:\n{fields_block}\n\n"
                "Return ONLY a JSON object with this structure:\n"
                "{\n"
                '  "per_document_summaries": [{"filename": "exact_filename", "summary": "1-sentence summary"}],\n'
                '  "items": [\n'
                "    {\n"
                '      "source_document": "exact_filename",\n'
                '      "title": "Actionable item title",\n'
                '      "due_date": "YYYY-MM-DD or empty string",\n'
                '      "numeric_value": 0.0,\n'
                '      "confidence": "high",\n'
                '      "extra_fields": {"<schema_field_key>": "extracted value"}\n'
                "    }\n"
                "  ]\n"
                "}\n"
            )
            for idx, p in enumerate(prepared, start=1):
                prompt_lines.append(
                    f"\n=== ATTACHMENT {idx} of {len(prepared)}: {p['safe_name']} ({p['scenario']['title']}) ===\n"
                    f"{p['extracted_text'][:per_doc_budget]}\n"
                    f"=== END ATTACHMENT {idx} ==="
                )
            gw = HyperscalerGateway()
            gw_res = gw.complete(
                prompt="\n".join(prompt_lines),
                provider=provider or "auto",
                model=model or None,
                system_instruction=sys_inst,
                max_tokens=3072,
                allow_tier0=False,
                max_prompt_chars=42000,
            )
            prov_name = str(gw_res.get("provider") or "")
            if "heuristic" not in prov_name.lower() and gw_res.get("text"):
                cand = _parse_llm_extraction_json(str(gw_res["text"]))
                if cand and isinstance(cand.get("items"), list) and cand["items"]:
                    engine_used = prov_name or "HyperscalerGateway"
                    model_used = str(gw_res.get("model") or model or "llm")
                    tokens_used = int(gw_res.get("tokens_used", 0) or 0)
                    known_names = [p["safe_name"] for p in prepared]
                    for s_entry in (cand.get("per_document_summaries") or []):
                        if isinstance(s_entry, dict) and s_entry.get("filename") and s_entry.get("summary"):
                            batch_summaries_by_doc[str(s_entry["filename"]).strip()] = str(s_entry["summary"]).strip()
                    for raw_it in cand["items"]:
                        if not isinstance(raw_it, dict):
                            continue
                        raw_src = str(
                            raw_it.get("source_document")
                            or (raw_it.get("extra_fields") or {}).get("source_document")
                            or ""
                        ).strip()
                        matched_name = ""
                        for kn in known_names:
                            if raw_src and (raw_src.lower() == kn.lower() or raw_src.lower() in kn.lower() or kn.lower() in raw_src.lower()):
                                matched_name = kn
                                break
                        if not matched_name:
                            matched_name = known_names[0]
                        batch_llm_items_by_doc.setdefault(matched_name, []).append(raw_it)
        except Exception as exc:
            logger.debug(f"Batched multi-doc LLM extraction fell back to deterministic parser: {exc}")

    results: List[Dict[str, Any]] = []
    per_doc_tokens = tokens_used // max(1, len(prepared)) if tokens_used else 0
    for p in prepared:
        sname = p["safe_name"]
        scen = p["scenario"]
        pdoc = p["parsed_doc"]
        llm_doc_items = batch_llm_items_by_doc.get(sname) or []
        if llm_doc_items:
            norm_items = _normalize_extracted_items(
                llm_doc_items,
                source_filename=sname,
                scenario_id=scen["id"],
                fields=p["eff_fields"],
            )
            doc_summary = batch_summaries_by_doc.get(sname) or p["det"]["document_summary"]
            doc_engine = engine_used
            doc_model = model_used
        else:
            norm_items = p["det"]["items"]
            doc_summary = p["det"]["document_summary"]
            doc_engine = engine_used if engine_used != "tier0_deterministic_extractor" and sname in batch_summaries_by_doc else "tier0_deterministic_extractor"
            doc_model = model_used if doc_engine != "tier0_deterministic_extractor" else "deterministic-$0.00"

        results.append({
            "status": "ok",
            "filename": sname,
            "extension": pdoc["extension"],
            "size_bytes": pdoc["size_bytes"],
            "char_count": pdoc["char_count"],
            "parser_used": pdoc["parser_used"],
            "engine_used": doc_engine,
            "model_used": doc_model,
            "tokens_used": per_doc_tokens,
            "detected_scenario": scen["id"],
            "scenario_profile": {
                "id": scen["id"],
                "title": scen["title"],
                "icon": scen["icon"],
                "category": scen["category"],
            },
            "document_summary": doc_summary,
            "items": norm_items,
            "items_count": len(norm_items),
            "suggested_agent": None,
            "vault": p["vault_info"],
            "text_preview": p["extracted_text"][:600],
        })
    return results


def promote_staged_document_to_agent_vault(vault_rel_path: str, target_agent_id: str) -> str:
    """
    Promotes a staged attachment from `user/agent_docs/studio_staging/<stored_name>`
    into the newly created agent's isolated vault `user/agent_docs/<clean_agent_id>/<stored_name>`,
    strictly confined inside `DATA_DIR / "user" / "agent_docs"`.
    """
    import shutil

    rel_str = str(vault_rel_path or "").strip().replace("\\", "/").lstrip("/")
    if rel_str.startswith("fleet/data/"):
        rel_str = rel_str[len("fleet/data/"):]
    if not rel_str:
        return ""

    vault_root = (DATA_DIR / "user" / "agent_docs").resolve()
    vault_root.mkdir(parents=True, exist_ok=True)
    src_candidate = (DATA_DIR / rel_str).resolve()
    try:
        src_candidate.relative_to(vault_root)
    except ValueError:
        return ""
    if not src_candidate.is_file():
        return ""

    clean_agent = re.sub(r"[^a-zA-Z0-9_-]", "_", (target_agent_id or "custom_agent").strip()) or "custom_agent"
    dest_dir = (vault_root / clean_agent).resolve()
    try:
        dest_dir.relative_to(vault_root)
    except ValueError:
        return ""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / sanitize_upload_filename(src_candidate.name)
    if src_candidate != dest_file:
        shutil.copy2(src_candidate, dest_file)
    return f"user/agent_docs/{clean_agent}/{dest_file.name}"


def resolve_afcc_connected_llm(
    provider: str = "auto",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolves the active LLM provider and model that AFCC is currently connected to
    (reading persisted AFCC AI settings, configured Hyperscaler providers, and Antigravity CLI).
    """
    req_prov = str(provider or "").strip()
    req_model = str(model or "").strip()

    saved_provider = "auto"
    saved_model = ""
    try:
        import fleet.server as srv
        if getattr(srv, "db", None) is not None and hasattr(srv.db, "get_all_settings"):
            db_settings = srv.db.get_all_settings() or {}
            saved_provider = str(db_settings.get("default_provider") or "auto").strip() or "auto"
            saved_model = str(db_settings.get("default_model") or "").strip()
    except Exception:
        pass

    eff_provider = req_prov if (req_prov and req_prov.lower() != "auto") else saved_provider
    eff_model = req_model or saved_model or None

    configured_providers: List[Dict[str, str]] = []
    active_provider_name = "Tier-0 Deterministic ($0.00 Offline)"
    is_live_llm = False
    try:
        from fleet.core.hyperscalers import HyperscalerGateway
        all_provs = HyperscalerGateway.list_available_providers()
        for p in all_provs:
            if p.get("is_configured"):
                configured_providers.append({
                    "id": str(p["id"]),
                    "name": str(p["name"]),
                    "default_model": str(p.get("default_model") or ""),
                    "auth_method": str(p.get("auth_method") or "api_key"),
                })
        if eff_provider.lower() == "deterministic":
            active_provider_name = "Tier-0 Deterministic ($0.00)"
        elif eff_provider.lower() == "auto":
            if configured_providers:
                top = configured_providers[0]
                active_provider_name = top["name"]
                if not eff_model:
                    eff_model = top["default_model"] or None
                is_live_llm = True
        else:
            matched = next((p for p in configured_providers if p["id"].lower() == eff_provider.lower()), None)
            if matched:
                active_provider_name = matched["name"]
                if not eff_model:
                    eff_model = matched["default_model"] or None
                is_live_llm = True
            else:
                active_provider_name = eff_provider
    except Exception:
        pass

    return {
        "provider": eff_provider or "auto",
        "model": eff_model or "gemini-3.8-flash-low",
        "active_provider_name": active_provider_name,
        "is_live_llm": is_live_llm,
        "configured_providers": configured_providers,
    }


def _try_multimodal_multi_attachment_llm(
    parsed_docs: List[Dict[str, Any]],
    sys_inst: str,
    user_prompt: str,
    provider: str = "auto",
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Sends multiple PDF and/or Image attachments simultaneously to AFCC's connected
    Multimodal LLM (Google Gemini `inlineData`, Anthropic Claude `document`/`image`,
    or OpenAI Vision `image_url`) alongside the unified multi-document analysis prompt.
    """
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return None
    if str(provider or "").strip().lower() == "deterministic":
        return None

    prov_low = str(provider or "auto").strip().lower()
    visual_or_pdf = [
        d for d in parsed_docs
        if d.get("is_visual_media") or d.get("extension") == ".pdf"
    ]
    if not visual_or_pdf:
        return None

    # 1. Google Gemini Multimodal (supports multiple PDF + Image inlineData blocks in one call)
    gemini_key = get_secure_secret("GEMINI_API_KEY") or get_secure_secret("GOOGLE_API_KEY")
    if gemini_key and prov_low in ("auto", "google", "gemini"):
        try:
            eff_model = (
                model
                if (model and "gemini" in model.lower() and "argon" not in model.lower() and "3.8" not in model.lower())
                else "gemini-2.0-flash"
            )
            parts: List[Dict[str, Any]] = []
            for d in visual_or_pdf[:6]:
                parts.append({
                    "inlineData": {
                        "mimeType": d["mime_type"],
                        "data": base64.b64encode(d["raw_bytes"]).decode("ascii"),
                    }
                })
            parts.append({"text": user_prompt})
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{eff_model}:generateContent?key={gemini_key}"
            payload: Dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": sys_inst}]},
                "contents": [{"parts": parts}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                txt = data["candidates"][0]["content"]["parts"][0]["text"]
                tokens = int(data.get("usageMetadata", {}).get("totalTokenCount", 0) or 0)
                return {
                    "status": "SUCCESS",
                    "provider": "Google Gemini Multimodal",
                    "model": eff_model,
                    "tokens_used": tokens,
                    "text": txt,
                }
        except Exception as exc:
            logger.debug("Multi-attachment Gemini multimodal call fell back: %s", exc)

    # 2. Anthropic Claude Multimodal (supports multiple PDF document + image blocks in one call)
    anthropic_key = get_secure_secret("ANTHROPIC_API_KEY")
    if anthropic_key and prov_low in ("auto", "anthropic", "claude"):
        try:
            content_blocks: List[Dict[str, Any]] = []
            for d in visual_or_pdf[:6]:
                mtype = d["mime_type"]
                if not (mtype.startswith("image/") or mtype == "application/pdf"):
                    continue
                btype = "document" if mtype == "application/pdf" else "image"
                content_blocks.append({
                    "type": btype,
                    "source": {
                        "type": "base64",
                        "media_type": mtype,
                        "data": base64.b64encode(d["raw_bytes"]).decode("ascii"),
                    },
                })
            if content_blocks:
                content_blocks.append({"type": "text", "text": user_prompt})
                payload = {
                    "model": "claude-3-5-sonnet-latest",
                    "max_tokens": 3072,
                    "system": sys_inst,
                    "messages": [{"role": "user", "content": content_blocks}],
                }
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    txt = data["content"][0]["text"]
                    usage = data.get("usage", {})
                    tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
                    return {
                        "status": "SUCCESS",
                        "provider": "Anthropic Claude Multimodal",
                        "model": "claude-3-5-sonnet-latest",
                        "tokens_used": tokens,
                        "text": txt,
                    }
        except Exception as exc:
            logger.debug("Multi-attachment Claude multimodal call fell back: %s", exc)

    # 3. OpenAI GPT-4o Vision (when image attachments are present)
    openai_key = get_secure_secret("OPENAI_API_KEY")
    image_only = [d for d in visual_or_pdf if d.get("is_visual_media")]
    if openai_key and image_only and prov_low in ("auto", "openai"):
        try:
            eff_oai_model = model if (model and ("gpt-4o" in model.lower() or "o1" in model.lower())) else "gpt-4o-mini"
            user_content: List[Dict[str, Any]] = [{"type": "text", "text": user_prompt}]
            for d in image_only[:6]:
                b64_img = base64.b64encode(d["raw_bytes"]).decode("ascii")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{d['mime_type']};base64,{b64_img}"},
                })
            payload = {
                "model": eff_oai_model,
                "max_tokens": 3072,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": sys_inst},
                    {"role": "user", "content": user_content},
                ],
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                txt = data["choices"][0]["message"]["content"]
                tokens = int(data.get("usage", {}).get("total_tokens", 0) or 0)
                return {
                    "status": "SUCCESS",
                    "provider": "OpenAI Multimodal Vision",
                    "model": eff_oai_model,
                    "tokens_used": tokens,
                    "text": txt,
                }
        except Exception as exc:
            logger.debug("Multi-attachment OpenAI vision call fell back: %s", exc)

    return None


def _merge_multi_scenario_fields_and_blocks(
    scenarios: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Merges typed schema fields and declarative UI blocks across multiple detected document scenarios
    so a multi-attachment upload produces a cohesive, non-redundant cross-document blueprint.
    """
    if not scenarios:
        scenarios = [DOCUMENT_SCENARIO_PROFILES[0]]

    primary = scenarios[0]
    merged_fields: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    # Keep primary scenario's core 3 fields first (`title`, `due_date`, `numeric_value`)
    for f in primary.get("recommended_fields") or []:
        k = str(f.get("key") or "")
        if k and k not in seen_keys:
            merged_fields.append(dict(f))
            seen_keys.add(k)
            if len(merged_fields) >= 4 and len(scenarios) > 1:
                break

    # Generalize labels when multiple distinct domains are combined
    if len(scenarios) > 1:
        domain_titles = " / ".join(s["title"].split(",")[0].split("&")[0].strip() for s in scenarios[:3])
        for mf in merged_fields:
            if mf["key"] == "title":
                mf["label"] = f"Tracked Item ({domain_titles})"[:42]
            elif mf["key"] == "due_date":
                mf["label"] = "Due / Renewal / Review Date"
            elif mf["key"] == "numeric_value":
                mf["label"] = "Amount / Metric Value"

    # Pull 1 high-signal domain-specific extra field from each secondary scenario (up to 5 fields total)
    for sec in scenarios[1:]:
        for f in sec.get("recommended_fields") or []:
            k = str(f.get("key") or "")
            if k and k not in seen_keys and len(merged_fields) < 5:
                merged_fields.append(dict(f))
                seen_keys.add(k)
                break

    # Merge recommended UI blocks in logical dashboard flow order
    canonical_order = [
        "alert_banner",
        "kpi_row",
        "document_vault",
        "quick_capture_bar",
        "countdown_cards",
        "kanban_board",
        "sparkline_chart",
        "habit_checklist",
        "ai_insight_card",
        "agent_chat",
        "history_table",
        "status_timeline",
    ]
    wanted: set[str] = {"document_vault", "agent_chat", "alert_banner", "kpi_row", "history_table"}
    for sc in scenarios:
        for blk in sc.get("recommended_blocks") or []:
            wanted.add(blk)
    merged_blocks = [b for b in canonical_order if b in wanted]
    return merged_fields, merged_blocks


def _build_multi_doc_llm_workflow_prompt(
    doc_contexts: List[Dict[str, Any]],
    unique_scenarios: List[Dict[str, Any]],
    merged_fields: List[Dict[str, Any]],
    user_prompt: str = "",
) -> Tuple[str, str]:
    """
    Builds the holistic Multi-Attachment Analysis & Guided Agent Creation prompt
    for AFCC's connected LLM.
    """
    today_iso = date.today().isoformat()
    doc_count = len(doc_contexts)
    per_doc_budget = max(3200, 30000 // max(1, doc_count))

    fields_spec = "\n".join(
        f'- "{f.get("key")}" ({f.get("type", "text")}): {f.get("label", f.get("key"))}'
        for f in merged_fields
    )
    scen_summary = ", ".join(f"{s['title']} ({s['id']})" for s in unique_scenarios)

    sys_inst = (
        "You are the Lead Agent Architect & Multi-Document Intelligence Engine inside the "
        "Agentic Fleet Control Center (AFCC). The user has uploaded one or more attachments "
        "to guide the creation of a new autonomous custom agent.\n"
        "Analyze ALL uploaded documents holistically, extract every actionable tracking item across "
        "all attachments, design the optimal unified agent blueprint (schema fields, UI widgets, "
        "permissions, recurrence cycle, EventBus triggers, and proactive alert hooks), and generate "
        "step-by-step workflow guidance explaining your architectural decisions.\n"
        "Return STRICT valid JSON only (no markdown commentary outside the JSON object)."
    )

    prompt_parts = [
        f"Current Date: {today_iso}",
        f"Total Uploaded Attachments: {doc_count}",
        f"Detected Domain Profiles Across Attachments: {scen_summary}",
    ]
    if user_prompt and user_prompt.strip():
        prompt_parts.append(f"User Goal / Hint: {user_prompt.strip()}")

    prompt_parts.append(
        "\nAFCC Capabilities Available to Configure:\n"
        "- UI Blocks: alert_banner, kpi_row, document_vault, quick_capture_bar, countdown_cards, "
        "kanban_board, sparkline_chart, ai_insight_card, agent_chat, history_table, habit_checklist, status_timeline\n"
        "- Sandbox Permissions: db:read, db:write, ui:render, event_bus:publish, network:outbound, system:diagnostics\n"
        "- Recurrence Cycles: none, monthly, quarterly, semi_annual, annual\n"
        "- Outbound Alert Hooks: auto_create_task, desktop_toast, markdown_report, emit_followup_event\n"
        "- EventBus Triggers: overview.morning_briefing, gmail.paper_trail_detected, health.workout_completed, agent.alert\n"
        f"\nCandidate Unified Schema Fields:\n{fields_spec}\n"
    )

    prompt_parts.append(
        "Return ONLY a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "cross_document_summary": "1-3 sentence cohesive executive summary connecting all uploaded attachments",\n'
        '  "per_document_summaries": [\n'
        '    {"filename": "exact_filename", "detected_scenario": "scenario_id", "summary": "1-sentence takeaway"}\n'
        "  ],\n"
        '  "suggested_agent": {\n'
        '    "name": "Concise 2-5 word Agent Name tailored to the attachments",\n'
        '    "icon": "Single emoji",\n'
        '    "category": "Finance | Health | Productivity | Knowledge | Monitoring | DevOps | System | Utility",\n'
        '    "archetype": "tracker | http_watcher | llm_analyst | habit_coach",\n'
        '    "description": "1-sentence operational mission tailored to all uploaded attachments",\n'
        '    "fields": [{"key": "snake_case", "label": "Human Label", "type": "text|date|number|url", "placeholder": "..."}],\n'
        '    "ui_blocks": ["alert_banner", "kpi_row", "document_vault", "quick_capture_bar", "countdown_cards", "agent_chat", "history_table"],\n'
        '    "permissions": ["db:read", "db:write", "ui:render", "event_bus:publish"],\n'
        '    "schedule_cadence": "daily_morning | hourly | every_30_min | manual_only",\n'
        '    "default_recurrence": "none | monthly | quarterly | semi_annual | annual",\n'
        '    "outbound_actions": ["auto_create_task", "desktop_toast"],\n'
        '    "event_triggers": ["gmail.paper_trail_detected"],\n'
        '    "system_prompt": "Custom operational directive tailored to monitoring these documents"\n'
        "  },\n"
        '  "workflow_guidance": {\n'
        '    "headline": "Short headline describing how the attachments shaped this agent",\n'
        '    "rationale": "1-2 sentences explaining why these fields, widgets, recurrence, and alert hooks were chosen",\n'
        '    "urgent_findings": ["Any overdue item, <=30d deadline, abnormal biomarker, or key obligation spotted in the attachments"],\n'
        '    "step_guidance": {\n'
        '      "step_1": "Guidance for Step 1 (Identity & Domain)",\n'
        '      "step_2": "Guidance for Step 2 (Sandbox Permissions)",\n'
        '      "step_3": "Guidance for Step 3 (Unified Schema, Recurrence, Hooks & UI Blocks)",\n'
        '      "step_4": "Guidance for Step 4 (Dry-Run & Pre-Seeded Activation)"\n'
        "    }\n"
        "  },\n"
        '  "items": [\n'
        "    {\n"
        '      "source_document": "exact_filename_of_attachment",\n'
        '      "title": "Actionable tracked item title",\n'
        '      "due_date": "YYYY-MM-DD or empty string",\n'
        '      "numeric_value": 0.0,\n'
        '      "confidence": "high",\n'
        '      "extra_fields": {"<schema_field_key>": "extracted value"}\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    for idx, dc in enumerate(doc_contexts, 1):
        txt = dc["parsed"]["extracted_text"]
        scen = dc["scenario"]
        header = (
            f"\n=== ATTACHMENT {idx} of {doc_count}: {dc['filename']} "
            f"(Format: {dc['parsed']['extension']} | Detected Domain: {scen['title']} [{scen['id']}]) ==="
        )
        if txt:
            prompt_parts.append(f"{header}\n{txt[:per_doc_budget]}\n=== END ATTACHMENT {idx} ===")
        else:
            prompt_parts.append(
                f"{header}\n[Visual/Scanned Attachment — inspect attached multimodal image/PDF bytes directly]\n=== END ATTACHMENT {idx} ==="
            )

    return sys_inst, "\n".join(prompt_parts)


def _infer_default_recurrence_from_scenarios_and_items(
    scenarios: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
) -> str:
    scen_ids = {s["id"] for s in scenarios}
    hay = " ".join(str(it.get("title") or "") for it in items).lower()
    if any(w in hay for w in ("monthly", "rent", "emi", "electricity", "broadband", "utility")):
        return "monthly"
    if "medical_lab_rx" in scen_ids or any(w in hay for w in ("quarterly", "hba1c", "biomarker")):
        return "quarterly"
    if scen_ids & {"insurance_policy", "contract_subscription", "warranty_asset_amc", "investment_fd_bond"}:
        return "annual"
    if "invoice_bill_tax" in scen_ids:
        return "monthly"
    return "none"


def _compute_document_findings_and_workflow_guidance(
    doc_results: List[Dict[str, Any]],
    all_items: List[Dict[str, Any]],
    unique_scenarios: List[Dict[str, Any]],
    spec: Dict[str, Any],
    llm_guidance: Optional[Dict[str, Any]],
    engine_used: str,
    model_used: str,
) -> Dict[str, Any]:
    """
    Synthesizes actionable step-by-step workflow guidance, urgent findings discovered inside
    the attachments, and 1-click guided decision chips across Wizard Steps 1..4.
    """
    today = date.today()
    overdue_hits: List[str] = []
    due_soon_hits: List[str] = []
    clinical_hits: List[str] = []
    has_urls = False
    total_numeric = 0.0

    for it in all_items:
        val = float(it.get("numeric_value") or 0.0)
        total_numeric += val
        raw_extra_it = it.get("extra_fields")
        extra: Dict[str, Any] = raw_extra_it if isinstance(raw_extra_it, dict) else {}
        if any(str(v).startswith(("http://", "https://")) for v in extra.values()):
            has_urls = True
        if str(extra.get("clinical_flag") or "").lower() == "attention":
            clinical_hits.append(f"{it['title']} ({extra.get('reference_note', 'flagged')})")
        due_s = str(it.get("due_date") or "").strip()
        if due_s:
            try:
                dt = date.fromisoformat(due_s[:10])
                delta = (dt - today).days
                if delta < 0:
                    overdue_hits.append(f"{it['title']} ({abs(delta)}d overdue — {due_s})")
                elif delta <= 30:
                    due_soon_hits.append(f"{it['title']} (in {delta}d — {due_s})")
            except ValueError:
                pass

    urgent_findings: List[str] = []
    if isinstance(llm_guidance, dict) and isinstance(llm_guidance.get("urgent_findings"), list):
        for uf in llm_guidance["urgent_findings"][:4]:
            if uf and str(uf).strip():
                urgent_findings.append(str(uf).strip())

    if overdue_hits and not any("overdue" in u.lower() for u in urgent_findings):
        urgent_findings.append(
            f"Overdue obligation detected: {', '.join(overdue_hits[:2])} — auto-enabled Priority Fleet Task & Toast Alert hooks."
        )
    if due_soon_hits and not any("due" in u.lower() or "expir" in u.lower() for u in urgent_findings):
        urgent_findings.append(
            f"Upcoming <=30-day deadline spotted: {', '.join(due_soon_hits[:2])} — enabled 15-Day Countdown Cards & proactive reminders."
        )
    if clinical_hits and not any("biomarker" in u.lower() or "clinical" in u.lower() for u in urgent_findings):
        urgent_findings.append(
            f"Out-of-range clinical markers detected ({', '.join(clinical_hits[:2])}) — enabled Sparkline Trend & Follow-Up Countdown tracking."
        )
    if len(doc_results) > 1 and total_numeric > 0 and len(urgent_findings) < 4:
        urgent_findings.append(
            f"Aggregated {len(all_items)} trackable item(s) across {len(doc_results)} attachments (combined numeric total: {total_numeric:,.2f})."
        )

    domain_counts: Dict[str, int] = {}
    for dr in doc_results:
        sid = dr["detected_scenario"]
        domain_counts[sid] = domain_counts.get(sid, 0) + 1

    detected_domains = [
        {
            "id": sc["id"],
            "title": sc["title"],
            "icon": sc["icon"],
            "category": sc["category"],
            "count": domain_counts.get(sc["id"], 1),
        }
        for sc in unique_scenarios
    ]
    is_multi_domain = len(unique_scenarios) > 1
    doc_word = f"{len(doc_results)} attachment{'s' if len(doc_results) != 1 else ''}"
    domain_names = " + ".join(d["title"] for d in detected_domains[:3])

    default_headline = (
        f"Multi-Domain Blueprint guided by {doc_word} ({domain_names})"
        if is_multi_domain
        else f"{unique_scenarios[0]['title']} Blueprint guided by {doc_word}"
    )
    default_rationale = (
        f"Analyzed {', '.join(d['filename'] for d in doc_results[:4])}"
        + (f" (+{len(doc_results) - 4} more)" if len(doc_results) > 4 else "")
        + f" via {model_used or engine_used}: unified {len(spec.get('fields') or [])} typed SQLite fields, "
        f"{len(spec.get('ui_blocks') or [])} live widgets (including Document Vault & Grounded RAG Chat), "
        f"recurrence '{spec.get('default_recurrence', 'none')}', and {len(all_items)} pre-staged tracking item(s)."
    )

    llm_steps = (llm_guidance or {}).get("step_guidance") if isinstance(llm_guidance, dict) else {}
    llm_steps = llm_steps if isinstance(llm_steps, dict) else {}

    step_guidance = {
        "step_1": str(
            llm_steps.get("step_1")
            or f"Step 1 (Identity): Named '{spec['name']}' ({spec['icon']} {spec['category']}) to cover {domain_names} across {doc_word}."
        ),
        "step_2": str(
            llm_steps.get("step_2")
            or f"Step 2 (Permissions): Configured least-privilege sandbox [{', '.join(spec.get('permissions') or [])}] based on document data & alert hooks."
        ),
        "step_3": str(
            llm_steps.get("step_3")
            or (
                f"Step 3 (Schema, AI & Hooks): Synthesized {len(spec.get('fields') or [])} unified fields "
                f"({', '.join(f['label'] for f in (spec.get('fields') or [])[:4])}), recurrence '{spec.get('default_recurrence', 'none')}', "
                f"watched drop-folder auto-ingestion, and {len(spec.get('ui_blocks') or [])} live widgets."
            )
        ),
        "step_4": str(
            llm_steps.get("step_4")
            or (
                f"Step 4 (Preview & Launch): Ready to vault {doc_word} into fleet/data/user/agent_docs/{spec['agent_id']}/ "
                f"and pre-seed {len(all_items)} extracted record(s) into SQLite on activation."
            )
        ),
    }

    # Interactive 1-Click Guided Workflow Decisions tailored to current spec gaps & document signals
    guided_actions: List[Dict[str, Any]] = []
    cur_blocks = set(spec.get("ui_blocks") or [])
    cur_hooks = set(spec.get("outbound_actions") or [])
    cur_triggers = set(spec.get("event_triggers") or [])
    cur_perms = set(spec.get("permissions") or [])

    if "gmail.paper_trail_detected" not in cur_triggers:
        guided_actions.append({
            "id": "guide_email_trigger",
            "label": "📧 + Auto-Ingest Incoming Paper-Trail Emails",
            "description": "Triggers this agent automatically whenever Gmail classifies a new policy, invoice, or receipt email.",
            "add_event_triggers": ["gmail.paper_trail_detected"],
        })
    if "markdown_report" not in cur_hooks:
        guided_actions.append({
            "id": "guide_md_digest",
            "label": "📝 + Export Automated Markdown Executive Digest",
            "description": "Writes an updated Markdown summary report to fleet/data/user/reports/ after each scheduled check.",
            "add_outbound_actions": ["markdown_report"],
        })
    if "kanban_board" not in cur_blocks:
        guided_actions.append({
            "id": "guide_kanban",
            "label": "🗂️ + Add 3-Stage Kanban Triage Board",
            "description": "Organizes extracted items into Active / Due Soon / Completed workflow columns.",
            "add_blocks": ["kanban_board"],
        })
    if "sparkline_chart" not in cur_blocks:
        guided_actions.append({
            "id": "guide_sparkline",
            "label": "📈 + Add Longitudinal Cost & Metric Sparkline",
            "description": "Charts numeric values and multi-cycle renewal history trends in pure SVG.",
            "add_blocks": ["sparkline_chart"],
        })
    if has_urls and "network:outbound" not in cur_perms:
        guided_actions.append({
            "id": "guide_url_probe",
            "label": "🌐 + Enable Live Portal / Endpoint URL Probing",
            "description": "URLs were detected in your attachments — grant network:outbound to probe live endpoints.",
            "add_permissions": ["network:outbound"],
        })
    if spec.get("default_recurrence", "none") == "none":
        guided_actions.append({
            "id": "guide_annual_cycle",
            "label": "🔄 + Set Annual Renewal Roll-Forward Cycle",
            "description": "Enables 1-click annual due-date roll-forward with historical cycle archiving.",
            "set_recurrence": "annual",
        })

    return {
        "headline": str((llm_guidance or {}).get("headline") or default_headline),
        "rationale": str((llm_guidance or {}).get("rationale") or default_rationale),
        "attachments_count": len(doc_results),
        "is_multi_domain": is_multi_domain,
        "detected_domains": detected_domains,
        "urgent_findings": urgent_findings,
        "overdue_count": len(overdue_hits),
        "due_soon_count": len(due_soon_hits),
        "total_numeric_value": round(total_numeric, 2),
        "step_guidance": step_guidance,
        "guided_actions": guided_actions[:5],
    }


def analyze_multiple_documents_for_studio_creation(
    documents: List[Dict[str, Any]],
    user_prompt: str = "",
    custom_id: Optional[str] = None,
    provider: str = "auto",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Multi-Attachment LLM-Guided Agent Creation Engine for Step 1 of Zero-Code Agent Studio:
    1. Accepts 1..MAX_MULTI_ATTACHMENTS attachments (`.pdf`, `.docx`, `.xlsx`, `.csv`, `.eml`,
       `.ics`, `.html`, `.txt`, `.md`, `.json`, and images `.png`/`.jpg`/`.jpeg`/`.webp`).
    2. Connects to AFCC's active LLM (Multimodal Gemini/Claude/OpenAI + `HyperscalerGateway` /
       Antigravity CLI, with deterministic $0.00 fallback) to holistically analyze ALL documents.
    3. Synthesizes a cross-document v2.0 Agent Blueprint (merging typed fields, UI widgets,
       permissions, recurrence cycle, EventBus triggers, and proactive outbound alert hooks).
    4. Produces step-by-step `workflow_guidance` across Steps 1..4 + pre-staged tracking items
       across every uploaded attachment.
    """
    from fleet.core.agent_studio import (
        SUPPORTED_EVENT_TRIGGERS,
        SUPPORTED_UI_BLOCKS,
        _normalize_fields,
        generate_custom_agent_code,
        render_declarative_ui_blocks,
        synthesize_agent_from_prompt,
    )
    from fleet.core.studio_phase6 import SUPPORTED_OUTBOUND_ACTIONS, SUPPORTED_RECURRENCE_CYCLES

    if not isinstance(documents, list) or len(documents) == 0:
        raise ValueError("At least one document attachment is required.")
    if len(documents) > MAX_MULTI_ATTACHMENTS:
        raise ValueError(f"Maximum {MAX_MULTI_ATTACHMENTS} attachments can be analyzed per batch.")

    llm_conn = resolve_afcc_connected_llm(provider=provider, model=model)
    eff_provider = str(provider or llm_conn["provider"] or "auto").strip()
    eff_model = str(model or llm_conn["model"] or "").strip() or None

    # Step 1: Parse, stage in vault, scenario-profile, and deterministically baseline each attachment
    doc_contexts: List[Dict[str, Any]] = []
    unique_scenarios: List[Dict[str, Any]] = []
    seen_scen_ids: set[str] = set()
    used_filenames: set[str] = set()

    for idx, raw_doc in enumerate(documents, 1):
        if not isinstance(raw_doc, dict):
            continue
        fname_in = str(raw_doc.get("filename") or f"attachment_{idx}.txt")
        b64_in = str(raw_doc.get("content_base64") or "")
        txt_in = str(raw_doc.get("text_content") or "")

        parsed = parse_uploaded_document(
            filename=fname_in,
            content_base64=b64_in,
            text_content=txt_in,
        )
        safe_name = parsed["filename"]
        if safe_name in used_filenames:
            stem, ext = safe_name.rsplit(".", 1) if "." in safe_name else (safe_name, "txt")
            safe_name = f"{stem}_{idx}.{ext}"
            parsed["filename"] = safe_name
        used_filenames.add(safe_name)

        vault_info: Optional[Dict[str, Any]] = None
        try:
            vault_info = save_agent_document_to_vault("studio_staging", safe_name, parsed["raw_bytes"])
        except Exception as exc:
            logger.warning("Could not stage attachment '%s' to vault: %s", safe_name, exc)

        scen = detect_document_scenario(
            filename=safe_name,
            raw_text=parsed["extracted_text"],
            agent_context=user_prompt,
        )
        if scen["id"] not in seen_scen_ids:
            unique_scenarios.append(scen)
            seen_scen_ids.add(scen["id"])

        det_baseline = _deterministic_extract_tracking_items(
            extracted_text=parsed["extracted_text"],
            filename=safe_name,
            scenario=scen,
            fields=scen.get("recommended_fields"),
        )
        doc_contexts.append({
            "filename": safe_name,
            "parsed": parsed,
            "vault": vault_info,
            "scenario": scen,
            "det_baseline": det_baseline,
        })

    if not doc_contexts:
        raise ValueError("No valid document attachments provided.")

    merged_fields, merged_blocks = _merge_multi_scenario_fields_and_blocks(unique_scenarios)

    # Step 2: Invoke AFCC's Connected LLM holistically across all attachments
    sys_inst, multi_prompt = _build_multi_doc_llm_workflow_prompt(
        doc_contexts=doc_contexts,
        unique_scenarios=unique_scenarios,
        merged_fields=merged_fields,
        user_prompt=user_prompt,
    )

    llm_parsed: Optional[Dict[str, Any]] = None
    engine_used = "tier0_deterministic_extractor"
    model_used = "deterministic-$0.00"
    tokens_used = 0

    needs_multimodal = any(
        dc["parsed"]["is_visual_media"]
        or (dc["parsed"]["extension"] == ".pdf" and len(dc["parsed"]["extracted_text"]) < 120)
        for dc in doc_contexts
    )
    if needs_multimodal:
        mm_res = _try_multimodal_multi_attachment_llm(
            parsed_docs=[dc["parsed"] for dc in doc_contexts],
            sys_inst=sys_inst,
            user_prompt=multi_prompt,
            provider=eff_provider,
            model=eff_model,
        )
        if mm_res and mm_res.get("text"):
            llm_parsed = _parse_llm_extraction_json(mm_res["text"])
            if llm_parsed:
                engine_used = str(mm_res.get("provider") or "multimodal_llm")
                model_used = str(mm_res.get("model") or eff_model or "multimodal")
                tokens_used = int(mm_res.get("tokens_used", 0) or 0)

    has_any_text = any(bool(dc["parsed"]["extracted_text"]) for dc in doc_contexts)
    if llm_parsed is None and has_any_text and eff_provider.lower() != "deterministic":
        try:
            from fleet.core.hyperscalers import HyperscalerGateway
            gw = HyperscalerGateway()
            gw_res = gw.complete(
                prompt=multi_prompt,
                provider=eff_provider or "auto",
                model=eff_model,
                system_instruction=sys_inst,
                max_tokens=3072,
                allow_tier0=False,
                max_prompt_chars=42000,
            )
            prov_name = str(gw_res.get("provider") or "")
            if "heuristic" not in prov_name.lower() and gw_res.get("text"):
                cand = _parse_llm_extraction_json(str(gw_res["text"]))
                if cand:
                    llm_parsed = cand
                    engine_used = prov_name or "HyperscalerGateway"
                    model_used = str(gw_res.get("model") or eff_model or "llm")
                    tokens_used = int(gw_res.get("tokens_used", 0) or 0)
        except Exception as exc:
            logger.debug("Multi-document Hyperscaler LLM analysis fell back to deterministic engine: %s", exc)

    # Step 3: Reconcile LLM Blueprint + Items with Per-Document Completeness Guarantees
    primary_scen = unique_scenarios[0]
    llm_sug = (llm_parsed or {}).get("suggested_agent") if isinstance((llm_parsed or {}).get("suggested_agent"), dict) else {}
    llm_sug = llm_sug or {}
    llm_guidance = (llm_parsed or {}).get("workflow_guidance") if isinstance((llm_parsed or {}).get("workflow_guidance"), dict) else None

    raw_fields = (
        llm_sug.get("fields")
        if isinstance(llm_sug.get("fields"), list) and len(llm_sug.get("fields") or []) >= 2
        else merged_fields
    )
    final_fields = _normalize_fields(raw_fields)

    valid_filenames = [dc["filename"] for dc in doc_contexts]
    scen_by_filename = {dc["filename"]: dc["scenario"]["id"] for dc in doc_contexts}

    all_items: List[Dict[str, Any]] = []
    items_by_doc: Dict[str, List[Dict[str, Any]]] = {fn: [] for fn in valid_filenames}

    if llm_parsed and isinstance(llm_parsed.get("items"), list) and llm_parsed["items"]:
        grouped_raw: Dict[str, List[Dict[str, Any]]] = {fn: [] for fn in valid_filenames}
        for raw_it in llm_parsed["items"]:
            if not isinstance(raw_it, dict):
                continue
            raw_src = str(
                raw_it.get("source_document")
                or (raw_it.get("extra_fields") or {}).get("source_document")
                or ""
            ).strip()
            matched_fn = ""
            if raw_src in grouped_raw:
                matched_fn = raw_src
            elif raw_src:
                low_src = raw_src.lower()
                matched_fn = next(
                    (fn for fn in valid_filenames if low_src in fn.lower() or Path(fn).stem.lower() in low_src),
                    "",
                )
            if not matched_fn:
                matched_fn = valid_filenames[0]
            grouped_raw[matched_fn].append(raw_it)

        for fn in valid_filenames:
            if grouped_raw[fn]:
                norm_for_doc = _normalize_extracted_items(
                    grouped_raw[fn],
                    source_filename=fn,
                    scenario_id=scen_by_filename[fn],
                    fields=final_fields,
                )
                items_by_doc[fn].extend(norm_for_doc)

    # Backfill any attachment that had 0 LLM items (or all attachments in deterministic mode)
    for dc in doc_contexts:
        fn = dc["filename"]
        if not items_by_doc[fn]:
            det_norm = _normalize_extracted_items(
                dc["det_baseline"]["items"],
                source_filename=fn,
                scenario_id=dc["scenario"]["id"],
                fields=final_fields,
            )
            items_by_doc[fn].extend(det_norm)
        all_items.extend(items_by_doc[fn])

    # Build per-document summary entries
    llm_per_doc_map: Dict[str, str] = {}
    if llm_parsed and isinstance(llm_parsed.get("per_document_summaries"), list):
        for pds in llm_parsed["per_document_summaries"]:
            if isinstance(pds, dict) and pds.get("filename") and pds.get("summary"):
                llm_per_doc_map[str(pds["filename"]).strip()] = str(pds["summary"]).strip()

    doc_results: List[Dict[str, Any]] = []
    for dc in doc_contexts:
        fn = dc["filename"]
        scen = dc["scenario"]
        doc_items = items_by_doc[fn]
        doc_sum = (
            llm_per_doc_map.get(fn)
            or (str(llm_parsed.get("document_summary")).strip() if (llm_parsed and len(doc_contexts) == 1 and llm_parsed.get("document_summary")) else "")
            or dc["det_baseline"]["document_summary"]
        )
        doc_results.append({
            "filename": fn,
            "extension": dc["parsed"]["extension"],
            "size_bytes": dc["parsed"]["size_bytes"],
            "char_count": dc["parsed"]["char_count"],
            "parser_used": dc["parsed"]["parser_used"],
            "detected_scenario": scen["id"],
            "scenario_profile": {
                "id": scen["id"],
                "title": scen["title"],
                "icon": scen["icon"],
                "category": scen["category"],
            },
            "document_summary": doc_sum,
            "engine_used": engine_used,
            "model_used": model_used,
            "items_count": len(doc_items),
            "items": doc_items,
            "vault": dc["vault"],
        })

    # Step 4: Synthesize & Act on Blueprint Configuration Based on All Attachments
    if len(unique_scenarios) > 1 and not llm_sug.get("name") and not (user_prompt and user_prompt.strip()):
        short_domains = " & ".join(
            s["title"].split(",")[0].split("&")[0].strip() for s in unique_scenarios[:2]
        )
        default_multi_name = f"{short_domains} Hub"[:48]
    else:
        default_multi_name = str(llm_sug.get("name") or primary_scen["default_agent_name"])[:48]

    synth_prompt = (
        user_prompt.strip()
        if user_prompt and user_prompt.strip()
        else (
            f"Create an agent called '{default_multi_name}' to track items across "
            f"{len(doc_results)} uploaded {', '.join(s['title'] for s in unique_scenarios[:3])} documents "
            f"every morning at 08:30 and alert me 15 days before due or expiry dates"
        )
    )

    valid_ui_block_ids = set(SUPPORTED_UI_BLOCKS.keys())
    req_blocks = [
        str(b) for b in (llm_sug.get("ui_blocks") or merged_blocks)
        if str(b) in valid_ui_block_ids
    ] or list(merged_blocks)
    for mandatory_blk in ("document_vault", "agent_chat"):
        if mandatory_blk not in req_blocks:
            req_blocks.insert(2 if len(req_blocks) >= 2 else len(req_blocks), mandatory_blk)

    spec = synthesize_agent_from_prompt(
        prompt=synth_prompt,
        custom_id=custom_id,
        requested_blocks=req_blocks,
        use_llm=False,
    )

    if llm_sug.get("name") and not (user_prompt and "called" in user_prompt.lower()):
        spec["name"] = str(llm_sug["name"]).strip()[:48]
    elif not user_prompt.strip():
        spec["name"] = default_multi_name

    if not custom_id:
        slug = re.sub(r"[^a-z0-9_]", "_", spec["name"].lower())
        slug = re.sub(r"_+", "_", slug).strip("_")
        if slug:
            spec["agent_id"] = slug[:42]

    spec["icon"] = str(llm_sug.get("icon") or primary_scen["icon"])[:4]
    spec["category"] = str(llm_sug.get("category") or primary_scen["category"])
    if llm_sug.get("archetype") in ("tracker", "http_watcher", "llm_analyst", "habit_coach"):
        spec["archetype"] = str(llm_sug["archetype"])

    file_list_preview = ", ".join(d["filename"] for d in doc_results[:3]) + (
        f" +{len(doc_results) - 3} more" if len(doc_results) > 3 else ""
    )
    spec["description"] = str(
        llm_sug.get("description")
        or (
            f"Tracks {', '.join(s['title'].lower() for s in unique_scenarios[:2])} records, deadlines, "
            f"and documents ({file_list_preview})."
        )
    )[:240]
    spec["fields"] = final_fields
    spec["ui_blocks"] = [b for b in req_blocks if b in valid_ui_block_ids]

    # Configure recurrence cycle, watched drop-folder, EventBus triggers, and proactive outbound hooks
    inferred_rec = str(llm_sug.get("default_recurrence") or "").strip().lower()
    if inferred_rec not in SUPPORTED_RECURRENCE_CYCLES:
        inferred_rec = _infer_default_recurrence_from_scenarios_and_items(unique_scenarios, all_items)
    spec["default_recurrence"] = inferred_rec
    spec["auto_ingest_inbox"] = True

    allowed_hook_ids = {a["id"] for a in SUPPORTED_OUTBOUND_ACTIONS}
    hooks: List[str] = [
        str(h) for h in (llm_sug.get("outbound_actions") or [])
        if str(h) in allowed_hook_ids
    ]
    today = date.today()
    has_urgent_dates = False
    for it in all_items:
        ds = str(it.get("due_date") or "").strip()
        if ds:
            try:
                if (date.fromisoformat(ds[:10]) - today).days <= 30:
                    has_urgent_dates = True
                    break
            except ValueError:
                pass
    if not hooks:
        hooks.append("auto_create_task")
        if has_urgent_dates:
            hooks.append("desktop_toast")
        if len(doc_results) >= 2:
            hooks.append("markdown_report")
    elif has_urgent_dates and "auto_create_task" not in hooks:
        hooks.insert(0, "auto_create_task")
    spec["outbound_actions"] = list(dict.fromkeys(hooks))

    allowed_trigger_ids = set(SUPPORTED_EVENT_TRIGGERS.keys())
    triggers: List[str] = [
        str(t) for t in (llm_sug.get("event_triggers") or spec.get("event_triggers") or [])
        if str(t) in allowed_trigger_ids
    ]
    scen_ids = {s["id"] for s in unique_scenarios}
    has_eml = any(d["extension"] == ".eml" for d in doc_results)
    if (
        has_eml
        or (scen_ids & {"insurance_policy", "contract_subscription", "invoice_bill_tax", "travel_id_visa"})
    ) and "gmail.paper_trail_detected" not in triggers:
        triggers.append("gmail.paper_trail_detected")
    spec["event_triggers"] = list(dict.fromkeys(triggers))

    # Ensure sandbox permissions match chosen hooks & widgets
    perms = list(dict.fromkeys([
        *(spec.get("permissions") or ["db:read", "db:write", "ui:render"]),
        *(
            [p for p in (llm_sug.get("permissions") or []) if p in ("db:read", "db:write", "ui:render", "event_bus:publish", "network:outbound", "system:diagnostics")]
        ),
    ]))
    if ("desktop_toast" in spec["outbound_actions"] or "emit_followup_event" in spec["outbound_actions"] or has_urgent_dates) and "event_bus:publish" not in perms:
        perms.append("event_bus:publish")
    spec["permissions"] = perms

    focus_directives = " ".join(s["extraction_focus"] for s in unique_scenarios[:3])
    spec["system_prompt"] = str(
        llm_sug.get("system_prompt")
        or (
            f"You are {spec['name']} ({spec['icon']}), synthesized from {len(doc_results)} uploaded document(s) "
            f"({file_list_preview}). {focus_directives} "
            "Highlight overdue or <=15-day upcoming items, answer grounded questions over vaulted documents, "
            "and summarize newly ingested attachments with concrete action steps."
        )
    )[:900]

    # Re-render declarative panel_html & agent_py so all updated fields, blocks, and IDs stay in sync
    spec["panel_html"] = render_declarative_ui_blocks(
        agent_id=spec["agent_id"],
        name=spec["name"],
        icon=spec["icon"],
        description=spec["description"],
        permissions=spec["permissions"],
        ui_blocks=spec["ui_blocks"],
        routine_task=spec["routine_task"],
        schedule_display=spec["schedule"]["display"],
        fields=spec["fields"],
        checklist_items=spec.get("checklist_items"),
        intelligence_mode=spec.get("intelligence_mode", "hybrid"),
    )
    spec["agent_py"] = generate_custom_agent_code(
        agent_id=spec["agent_id"],
        name=spec["name"],
        icon=spec["icon"],
        description=spec["description"],
        archetype=spec["archetype"],
        routine_task=spec["routine_task"],
        intelligence_mode=spec.get("intelligence_mode", "hybrid"),
    )

    cross_summary = str(
        (llm_parsed or {}).get("cross_document_summary")
        or (llm_parsed or {}).get("document_summary")
        or (
            doc_results[0]["document_summary"]
            if len(doc_results) == 1
            else (
                f"Analyzed {len(doc_results)} attachments ({file_list_preview}) across "
                f"{', '.join(s['title'] for s in unique_scenarios)}: extracted {len(all_items)} "
                f"structured tracking item(s) ready for launch."
            )
        )
    ).strip()

    workflow_guidance = _compute_document_findings_and_workflow_guidance(
        doc_results=doc_results,
        all_items=all_items,
        unique_scenarios=unique_scenarios,
        spec=spec,
        llm_guidance=llm_guidance,
        engine_used=engine_used,
        model_used=model_used,
    )

    combined_label = (
        doc_results[0]["filename"]
        if len(doc_results) == 1
        else f"{len(doc_results)} attachments ({file_list_preview})"
    )

    return {
        "status": "ok",
        "attachments_count": len(doc_results),
        "connected_llm": {
            **llm_conn,
            "engine_used": engine_used,
            "model_used": model_used,
            "tokens_used": tokens_used,
        },
        "spec": spec,
        "documents": doc_results,
        "workflow_guidance": workflow_guidance,
        "extraction": {
            "filename": combined_label,
            "attachments_count": len(doc_results),
            "detected_scenario": primary_scen["id"],
            "scenario_profile": {
                "id": primary_scen["id"],
                "title": (
                    primary_scen["title"]
                    if len(unique_scenarios) == 1
                    else f"{len(unique_scenarios)} Domains ({' + '.join(s['icon'] + ' ' + s['title'].split(',')[0] for s in unique_scenarios[:3])})"
                ),
                "icon": primary_scen["icon"],
                "category": primary_scen["category"],
            },
            "document_summary": cross_summary,
            "engine_used": engine_used,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "items": all_items[:100],
            "items_count": len(all_items[:100]),
            "vault": doc_results[0]["vault"],
        },
    }


def analyze_document_for_studio_creation(
    filename: str = "",
    content_base64: str = "",
    text_content: str = "",
    user_prompt: str = "",
    custom_id: Optional[str] = None,
    provider: str = "auto",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single-document convenience wrapper around `analyze_multiple_documents_for_studio_creation`,
    preserving 100% backward compatibility while returning enriched `documents` & `workflow_guidance`.
    """
    return analyze_multiple_documents_for_studio_creation(
        documents=[
            {
                "filename": filename,
                "content_base64": content_base64,
                "text_content": text_content,
            }
        ],
        user_prompt=user_prompt,
        custom_id=custom_id,
        provider=provider,
        model=model,
    )
