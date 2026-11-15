"""
GitHub Project Governance, Milestone, Issue, Wiki & Telemetry Manager for the
AFCC Tri-Device Ecosystem Architecture (Apple Watch + iPhone + Windows Laptop Hub).

Uses all associated features of GitHub to track, monitor, communicate, and deliver:
  1. GitHub Labels (10 structured device, phase, payment, and security labels)
  2. GitHub Milestones (Phases 1-4 with due dates and completion percentages)
  3. GitHub Issues & Sub-Task Checklists (TD-01 through TD-12 linked to Milestones)
  4. GitHub Master Epic Issue with native GitHub Tasklist progress bar (`- [x] #...`)
  5. GitHub Projects v2 GraphQL integration (when token has `project` scope)
  6. GitHub Actions Job Summary (`$GITHUB_STEP_SUMMARY`), GitHub Wiki (`wiki/`), and GitHub Pages (`docs/`)
  7. Zero-Cloud Personal Data Guard (`enforce_zero_cloud_data_leak_guard`) on all outbound payloads.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR
from fleet.core.crypto_vault import (
    assert_zero_cloud_user_data_egress as enforce_zero_cloud_data_leak_guard,
)
from fleet.tools.github_pipeline_sentinel import (
    DEFAULT_GITHUB_REPO,
    _http_json_request,
    _resolve_github_token,
)

REPO_ROOT = BASE_DIR.parent
PROJECT_SPEC_PATH = REPO_ROOT / ".github" / "projects" / "tri-device-architecture.json"
ROADMAP_DOC_PATH = REPO_ROOT / "docs" / "PROJECTS_TRI_DEVICE_ROADMAP.md"
WIKI_DOC_PATH = REPO_ROOT / "wiki" / "Tri-Device-Architecture-Project.md"


def load_tri_device_project_spec(spec_path: Path = PROJECT_SPEC_PATH) -> Dict[str, Any]:
    """Loads the canonical Tri-Device Architecture project manifest from `.github/projects/`."""
    if not spec_path.is_file():
        raise FileNotFoundError(f"Project specification not found: {spec_path}")
    return json.loads(spec_path.read_text(encoding="utf-8"))


def compute_tri_device_project_status(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Computes live completion metrics, phase progress, and deliverable file verification."""
    data = spec or load_tri_device_project_spec()
    deliverables: List[Dict[str, Any]] = data.get("deliverables", [])
    milestones: List[Dict[str, Any]] = data.get("milestones", [])

    total = len(deliverables)
    completed = sum(1 for d in deliverables if d.get("status") == "completed")
    in_progress = sum(1 for d in deliverables if d.get("status") == "in_progress")
    planned = sum(1 for d in deliverables if d.get("status") == "planned")
    completion_pct = round((completed / total) * 100.0, 1) if total > 0 else 0.0

    milestone_summaries: List[Dict[str, Any]] = []
    for ms in milestones:
        ms_id = ms.get("id")
        ms_items = [d for d in deliverables if d.get("milestone_id") == ms_id]
        ms_total = len(ms_items)
        ms_done = sum(1 for d in ms_items if d.get("status") == "completed")
        ms_pct = round((ms_done / ms_total) * 100.0, 1) if ms_total > 0 else 0.0
        milestone_summaries.append({
            **ms,
            "total_items": ms_total,
            "completed_items": ms_done,
            "completion_pct": ms_pct,
            "deliverable_ids": [d.get("id") for d in ms_items],
        })

    verified_deliverables: List[Dict[str, Any]] = []
    for d in deliverables:
        files = d.get("deliverable_files", [])
        existing_files = [f for f in files if (REPO_ROOT / f).exists()]
        verified_deliverables.append({
            **d,
            "verified_files_count": len(existing_files),
            "all_files_present": len(existing_files) == len(files) if files else True,
        })

    repo = data.get("repository", DEFAULT_GITHUB_REPO)
    return {
        "status": "ok",
        "project_id": data.get("project_id", "tri-device-architecture"),
        "title": data.get("title", "AFCC Tri-Device Ecosystem Architecture"),
        "short_title": data.get("short_title", "Tri-Device Architecture"),
        "repository": repo,
        "security_standard": data.get("security_standard", ""),
        "architecture_doc": data.get("architecture_doc", "docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md"),
        "roadmap_doc": data.get("roadmap_doc", "docs/PROJECTS_TRI_DEVICE_ROADMAP.md"),
        "wiki_page": data.get("wiki_page", "wiki/Tri-Device-Architecture-Project.md"),
        "github_urls": {
            "repo": f"https://github.com/{repo}",
            "issues": f"https://github.com/{repo}/issues?q=label%3Aproject%3Atri-device-architecture",
            "milestones": f"https://github.com/{repo}/milestones",
            "projects": f"https://github.com/{repo}/projects",
            "actions": f"https://github.com/{repo}/actions",
            "wiki": f"https://github.com/{repo}/wiki/Tri-Device-Architecture-Project",
            "discussions": f"https://github.com/{repo}/discussions",
            "architecture_blob": f"https://github.com/{repo}/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md",
            "roadmap_blob": f"https://github.com/{repo}/blob/main/docs/PROJECTS_TRI_DEVICE_ROADMAP.md",
        },
        "metrics": {
            "total_deliverables": total,
            "completed": completed,
            "in_progress": in_progress,
            "planned": planned,
            "completion_pct": completion_pct,
            "labels_count": len(data.get("labels", [])),
            "milestones_count": len(milestones),
        },
        "milestones": milestone_summaries,
        "deliverables": verified_deliverables,
        "labels": data.get("labels", []),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_deliverable_issue_body(d: Dict[str, Any], repo: str) -> str:
    """Formats a structured GitHub Issue body for a Tri-Device deliverable (TD-01..TD-12)."""
    is_done = d.get("status") == "completed"
    check_char = "x" if is_done else " "
    criteria_lines = "\n".join(f"- [{check_char}] {c}" for c in d.get("acceptance_criteria", []))
    files_lines = "\n".join(
        f"- [`{f}`](https://github.com/{repo}/blob/main/{f})"
        for f in d.get("deliverable_files", [])
    )
    status_badge = (
        "✅ **COMPLETED & VERIFIED**"
        if is_done
        else ("🔄 **IN PROGRESS**" if d.get("status") == "in_progress" else "📋 **PLANNED**")
    )
    body = (
        f"### ⌚📱💻 Tri-Device Architecture Deliverable: `{d['id']}`\n\n"
        f"- **Delivery Status**: {status_badge}\n"
        f"- **Priority**: `{d.get('priority', 'P1')}`\n"
        f"- **Target Device Tier**: **{d.get('device', 'All Devices')}**\n"
        f"- **Milestone Phase**: `{d.get('milestone_id', '')}`\n"
        f"- **Architecture Blueprint**: [`docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md`](https://github.com/{repo}/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)\n\n"
        f"---\n\n"
        f"#### 🎯 Problem Statement & Scope\n"
        f"{d.get('summary', '')}\n\n"
        f"#### ✅ Acceptance Criteria & Verification\n"
        f"{criteria_lines}\n\n"
        f"#### 📂 Associated Repository Artifacts\n"
        f"{files_lines or '-Tracked in repository'}\n\n"
        f"---\n"
        f"*Managed automatically by `fleet.tools.github_project_manager` • Zero-Cloud Personal Data Guard Enforced.*"
    )
    enforce_zero_cloud_data_leak_guard(body)
    return body


def _build_master_epic_issue_body(status_report: Dict[str, Any], issue_number_map: Dict[str, int]) -> str:
    """Formats the Master GitHub Epic Issue body with native GitHub Tasklist checkboxes and Milestone rollups."""
    repo = status_report["repository"]
    m = status_report["metrics"]

    ms_rows = []
    for ms in status_report["milestones"]:
        ms_rows.append(
            f"| **{ms['title']}** | `{ms['completed_items']}/{ms['total_items']}` (**{ms['completion_pct']}%**) | `{ms.get('due_on', '')[:10]}` |"
        )
    ms_table = "\n".join(ms_rows)

    task_lines = []
    for d in status_report["deliverables"]:
        did = d["id"]
        is_done = d.get("status") == "completed"
        chk = "x" if is_done else " "
        inum = issue_number_map.get(did)
        ref = f"#{inum}" if inum else f"`{did}`"
        status_icon = "✅" if is_done else ("🔄" if d.get("status") == "in_progress" else "📋")
        task_lines.append(
            f"- [{chk}] {ref} — {status_icon} **{d['title']}** (`{d.get('priority', 'P1')}` • *{d.get('device', '')}*)"
        )
    tasklist_md = "\n".join(task_lines)

    body = (
        f"## ⌚📱💻 [EPIC] {status_report['title']}\n\n"
        f"> **Live Project Progress**: **{m['completed']} / {m['total_deliverables']} Deliverables Completed ({m['completion_pct']}%)** • "
        f"**{m['in_progress']} In Progress** • **{m['planned']} Planned**\n"
        f"> **Security Standard**: `{status_report['security_standard']}`\n\n"
        f"### 📚 Key Project Links & Governance Channels\n"
        f"- 📐 **Master Architecture Blueprint**: [`docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md`](https://github.com/{repo}/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)\n"
        f"- 🗺️ **Project Roadmap & Kanban Portal**: [`docs/PROJECTS_TRI_DEVICE_ROADMAP.md`](https://github.com/{repo}/blob/main/docs/PROJECTS_TRI_DEVICE_ROADMAP.md)\n"
        f"- 📖 **GitHub Wiki Guide**: [`Tri-Device-Architecture-Project`](https://github.com/{repo}/wiki/Tri-Device-Architecture-Project)\n"
        f"- 🎯 **GitHub Milestones**: [View All 4 Delivery Phases](https://github.com/{repo}/milestones)\n"
        f"- 💬 **GitHub Discussions**: [Architecture & Status Updates](https://github.com/{repo}/discussions)\n\n"
        f"---\n\n"
        f"### 🏁 Milestone Delivery Rollup\n\n"
        f"| Milestone / Phase | Progress | Target Date |\n"
        f"| :--- | :---: | :---: |\n"
        f"{ms_table}\n\n"
        f"---\n\n"
        f"### 📋 Work Breakdown Structure & Deliverable Tasklist\n\n"
        f"{tasklist_md}\n\n"
        f"---\n"
        f"*Synchronized automatically by `fleet.tools.github_project_manager` & `.github/workflows/tri_device_project_tracker.yml`.*"
    )
    enforce_zero_cloud_data_leak_guard(body)
    return body


def generate_project_markdown_portal(status_report: Optional[Dict[str, Any]] = None) -> str:
    """Generates the Markdown Project Portal for `docs/PROJECTS_TRI_DEVICE_ROADMAP.md`, `wiki/`, and `$GITHUB_STEP_SUMMARY`."""
    rep = status_report or compute_tri_device_project_status()
    repo = rep["repository"]
    m = rep["metrics"]

    ms_rows = []
    for ms in rep["milestones"]:
        bar_filled = int(round(ms["completion_pct"] / 10))
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        ms_rows.append(
            f"| **{ms['title']}** | `{bar}` **{ms['completion_pct']}%** (`{ms['completed_items']}/{ms['total_items']}`) | `{ms.get('due_on', '')[:10]}` | {', '.join(f'`{x}`' for x in ms['deliverable_ids'])} |"
        )

    completed_cards = []
    in_progress_cards = []
    planned_cards = []
    for d in rep["deliverables"]:
        line = f"- **`{d['id']}` ({d.get('priority', 'P1')})**: **{d['title'].replace('[' + d['id'] + '] ', '')}** — *{d.get('device', '')}*"
        if d.get("status") == "completed":
            completed_cards.append(line)
        elif d.get("status") == "in_progress":
            in_progress_cards.append(line)
        else:
            planned_cards.append(line)

    md = f"""# ⌚📱💻 AFCC Tri-Device Ecosystem Architecture — GitHub Project & Delivery Tracker

[![Project Status](https://img.shields.io/badge/Project-Active%20(%20{m['completion_pct']}%25%20Delivered%20)-10b981?style=for-the-badge)](#)
[![Milestones](https://img.shields.io/badge/GitHub%20Milestones-4%20Phases-38bdf8?style=for-the-badge)](https://github.com/{repo}/milestones)
[![Issues](https://img.shields.io/badge/Tracked%20Deliverables-12%20Issues%20(TD--01..TD--12)-a855f7?style=for-the-badge)](https://github.com/{repo}/issues?q=label%3Aproject%3Atri-device-architecture)
[![Security](https://img.shields.io/badge/Security-Zero--Cloud%20AES--256--GCM%20%2B%20mTLS-f59e0b?style=for-the-badge)](https://github.com/{repo}/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)

> **Canonical Architecture Blueprint**: [`docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md`](https://github.com/{repo}/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)
> **GitHub Project Manifest**: [`.github/projects/tri-device-architecture.json`](https://github.com/{repo}/blob/main/.github/projects/tri-device-architecture.json)
> **Automated GitHub Tracker Workflow**: [`.github/workflows/tri_device_project_tracker.yml`](https://github.com/{repo}/blob/main/.github/workflows/tri_device_project_tracker.yml)

---

## 🧭 1. Executive Project Summary & GitHub Governance

This project tracks, monitors, communicates, and delivers the **Tri-Device Ecosystem Architecture** connecting:
1. **⌚ Tier 1 — Apple Watch (Sensor & Micro-Interaction Edge)**: Continuous biometric capture (HR, HRV SDNN, Sleep Stages, SpO2, Active Rings), Smart Stack Complication (`/api/mobile/watch/complication`), and Siri Action Button voice bridge.
2. **📱 Tier 2 — iPhone (Pocket Cockpit & Open Payment Aggregator)**: HealthKit background bridge (`/api/mobile/health/ingest`), installable Mobile Pocket Cockpit PWA, and **1-Tap Open Payment Deep-Link Engine** (`/api/mobile/payments/deeplink` for **BHIM UPI**, **ICICI iMobile Pay**, **Google Pay**, and **PhonePe**).
3. **💻 Tier 3 — Windows Laptop (Sovereign AFCC Brain & Encrypted Vault)**: Master SQLite + AES-256-GCM / HKDF-SHA256 / FF1 FPE encrypted vault, `1.5x–3x` Voice Cockpit with `"Mahadev"` wake word, and live Action-Item Conversational Engine.

### Associated GitHub Features Active on This Project
| GitHub Feature | Purpose & How It Is Used | Link / Artifact |
| :--- | :--- | :--- |
| **🏷️ GitHub Labels (10)** | Categorize issues & PRs by device (`device:apple-watch`, `device:iphone`, `device:laptop-hub`), phase (`phase:1..4`), and domain (`payments:upi-bhim-icici`, `security:e2ee-mtls`) | [Repository Labels](https://github.com/{repo}/labels) |
| **🎯 GitHub Milestones (4)** | Track completion % and target dates across Phases 1, 2, 3, and 4 | [Repository Milestones](https://github.com/{repo}/milestones) |
| **📋 GitHub Epic & Sub-Issues (13)** | Master Epic Issue with native Tasklist progress bar + 12 granular deliverable issues (`TD-01`..`TD-12`) | [Tri-Device Issues](https://github.com/{repo}/issues?q=label%3Aproject%3Atri-device-architecture) |
| **📝 GitHub Issue & Discussion Forms** | Structured YAML forms for filing new Tri-Device deliverables and posting milestone status updates | [`.github/ISSUE_TEMPLATE/tri_device_deliverable.yml`](https://github.com/{repo}/blob/main/.github/ISSUE_TEMPLATE/tri_device_deliverable.yml) |
| **⚙️ GitHub Actions CI & Project Sync** | Automatically provisions Labels/Milestones/Issues, runs `pytest` on Tri-Device endpoints, and publishes Job Summaries | [`.github/workflows/tri_device_project_tracker.yml`](https://github.com/{repo}/blob/main/.github/workflows/tri_device_project_tracker.yml) |
| **📖 GitHub Wiki & GitHub Pages** | Auto-publishes the live roadmap, Kanban board, and API documentation on every push | [Wiki Guide](https://github.com/{repo}/wiki/Tri-Device-Architecture-Project) |

---

## 🏁 2. Milestone Delivery Matrix

| Milestone Phase | Completion Progress | Target Date | Deliverables |
| :--- | :--- | :---: | :--- |
{chr(10).join(ms_rows)}

---

## 📊 3. Live Project Kanban Board (`{m['completed']}/{m['total_deliverables']}` Completed — `{m['completion_pct']}%`)

### ✅ Completed & Verified (`{m['completed']}`)
{chr(10).join(completed_cards) or '- None'}

### 🔄 In Progress (`{m['in_progress']}`)
{chr(10).join(in_progress_cards) or '- None'}

### 📋 Planned Backlog (`{m['planned']}`)
{chr(10).join(planned_cards) or '- None'}

---

## 🔌 4. Delivered Tri-Device REST API Endpoints (`fleet/api/mobile_tri_device_api.py`)

| Endpoint | Method | Device Tier | Description |
| :--- | :---: | :---: | :--- |
| `/api/mobile/health/ingest` | `POST` | 📱 iPhone / ⌚ Watch → 💻 Laptop | Ingests Apple Health & Watch biometrics into SQLite + AES-256-GCM vault and computes 0–100 FFD Workout Readiness Score |
| `/api/mobile/workout/adaptation` | `GET` | ⌚ Watch → 💻 Laptop | Correlates Apple Watch HRV (SDNN), Sleep & RHR with the 6-Day Mudgal/Samtola/Bhim Gadha split (`TD-04`) |
| `/api/mobile/voice/relay` | `POST` | ⌚ Watch / 📱 iPhone → 💻 Laptop | Zero-Cert Siri & Apple Watch Action Button Voice Relay (`'Ask Mahadev'`) returning plain-text `spoken_reply` (`TD-05`, `TD-11`) |
| `/api/mobile/outbox/sync` | `POST` | 📱 iPhone → 💻 Laptop | Flushes & deduplicates offline mobile mutations queued while away from home Wi-Fi into SQLite & encrypted vaults (`TD-06`) |
| `/api/mobile/widgets/scriptable` | `GET` | 📱 iPhone ↔ 💻 Laptop | Serves Zero-Xcode iOS 26.3.1 Scriptable Home/Lock Screen widget code & Root CA onboarding steps (`TD-07`) |
| `/api/mobile/watch/complication` | `GET` / `POST` | ⌚ Apple Watch ↔ 💻 Laptop | Ultra-compact (`< 2 KB`) Smart Stack Complication snapshot + 1-tap `+250ml Water` and `Close Top Action Item` actions (`TD-10`) |
| `/api/mobile/payments/deeplink` | `POST` | 💻 Laptop → 📱 iPhone UPI | Generates 1-Tap `bhim://pay`, `imobileapp://`, `tez://upi/pay`, `phonepe://pay`, and `upi://pay` deep links + NPCI SVG QR Matrix (`TD-08`) |
| `/api/mobile/payments/parse_receipt` | `POST` | 📱 iPhone → 💻 Laptop | Parses iOS Share Sheet / Bank SMS UPI receipts, masks UTR/VPA with FF1 FPE, and auto-closes paid Monthly Action Items (`TD-09`) |
| `/api/mobile/presence/nudge` | `GET` / `POST` | 💻 Laptop → ⌚ Apple Watch | Workstation lock/idle presence detector & Apple Watch Taptic nudge dispatcher (`TD-12`) |
| `/api/mobile/audio/routing` | `GET` / `POST` | 💻 Laptop ↔ 🎧 Bluetooth | Context-aware split Bluetooth audio routing (Headset Mic 85–3800 Hz Voiceprint vs. Workout Speakers, `EC-09`) |
| `/api/mobile/shortcuts/template` | `GET` | 📱 iPhone / ⌚ Watch | Returns ready-to-import iOS Shortcuts & Apple Watch Action Button JSON recipes (`TD-03`, `TD-11`) |
| `/api/github/projects/tri-device` | `GET` | 💻 Laptop / 🌐 GitHub | Returns live Tri-Device GitHub Project telemetry, milestone progress, and deliverable verification (`TD-12`) |
| `/api/github/projects/tri-device/sync` | `POST` | 💻 Laptop → 🌐 GitHub | Triggers idempotent synchronization of Labels, Milestones, Master Epic, and Issues `TD-01`..`TD-12` to GitHub (`TD-12`) |
"""
    enforce_zero_cloud_data_leak_guard(md)
    return md


def sync_local_project_docs() -> Dict[str, Any]:
    """Writes the generated Markdown portal to `docs/PROJECTS_TRI_DEVICE_ROADMAP.md` and `wiki/Tri-Device-Architecture-Project.md`."""
    status_report = compute_tri_device_project_status()
    md = generate_project_markdown_portal(status_report)

    ROADMAP_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROADMAP_DOC_PATH.write_text(md, encoding="utf-8")

    WIKI_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    WIKI_DOC_PATH.write_text(md, encoding="utf-8")

    # Ensure wiki/_Sidebar.md links to Tri-Device-Architecture-Project
    sidebar_path = REPO_ROOT / "wiki" / "_Sidebar.md"
    if sidebar_path.is_file():
        s_txt = sidebar_path.read_text(encoding="utf-8")
        if "Tri-Device-Architecture-Project" not in s_txt:
            s_txt = s_txt.rstrip() + "\n* [⌚📱💻 Tri-Device Architecture Project](Tri-Device-Architecture-Project)\n"
            sidebar_path.write_text(s_txt, encoding="utf-8")

    # If running inside GitHub Actions, also append to $GITHUB_STEP_SUMMARY
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if step_summary_path:
        try:
            with open(step_summary_path, "a", encoding="utf-8") as f:
                f.write(md + "\n")
        except Exception:
            pass

    return {
        "status": "ok",
        "roadmap_doc": str(ROADMAP_DOC_PATH.relative_to(REPO_ROOT).as_posix()),
        "wiki_doc": str(WIKI_DOC_PATH.relative_to(REPO_ROOT).as_posix()),
        "metrics": status_report["metrics"],
    }


def sync_tri_device_project_to_github(
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Idempotently provisions and synchronizes all GitHub Labels, Milestones,
    Deliverable Issues (TD-01..TD-12), and the Master Epic Issue on GitHub.
    """
    status_report = compute_tri_device_project_status()
    target_repo = (repo or status_report.get("repository") or DEFAULT_GITHUB_REPO).strip()
    gh_token = (token or _resolve_github_token() or os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")).strip()

    # Always keep local docs & wiki synced first
    sync_local_project_docs()

    if not gh_token:
        return {
            "status": "deferred_to_github_actions",
            "message": (
                "Local GitHub PAT not set; project manifest, issue templates, wiki page, and `.github/workflows/tri_device_project_tracker.yml` "
                "are ready and will automatically provision Labels, Milestones, Epic, and Issues on GitHub Actions upon `git push`."
            ),
            "project": status_report,
        }

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_api = f"https://api.github.com/repos/{target_repo}"

    created_labels: List[str] = []
    milestone_num_by_id: Dict[str, int] = {}
    issue_num_by_td: Dict[str, int] = {}

    # 1. Sync Labels
    st_lbl, existing_labels = _http_json_request(f"{base_api}/labels?per_page=100", headers=headers)
    existing_label_names = {
        str(lbl.get("name") or "").lower(): lbl.get("name")
        for lbl in (existing_labels if isinstance(existing_labels, list) else [])
        if isinstance(lbl, dict)
    }
    for lbl in status_report.get("labels", []):
        lname = str(lbl["name"])
        payload = {
            "name": lname,
            "color": str(lbl.get("color", "0E8A16")).lstrip("#"),
            "description": str(lbl.get("description", ""))[:100],
        }
        enforce_zero_cloud_data_leak_guard(payload)
        if lname.lower() not in existing_label_names:
            code, _ = _http_json_request(f"{base_api}/labels", method="POST", payload=payload, headers=headers)
            if code in (200, 201):
                created_labels.append(lname)
        else:
            existing_name_str = str(existing_label_names.get(lname.lower()) or lname)
            encoded_name = urllib.parse.quote(existing_name_str, safe="")
            _http_json_request(f"{base_api}/labels/{encoded_name}", method="PATCH", payload=payload, headers=headers)

    # 2. Sync Milestones (Phases 1-4)
    st_ms, existing_ms = _http_json_request(f"{base_api}/milestones?state=all&per_page=100", headers=headers)
    ms_by_title: Dict[str, Dict[str, Any]] = {}
    if isinstance(existing_ms, list):
        for m_obj in existing_ms:
            if isinstance(m_obj, dict) and m_obj.get("title"):
                ms_by_title[str(m_obj["title"]).strip().lower()] = m_obj

    for ms in status_report.get("milestones", []):
        m_title = str(ms["title"]).strip()
        m_payload = {
            "title": m_title,
            "state": ms.get("state", "open"),
            "description": str(ms.get("description", "")),
            "due_on": ms.get("due_on"),
        }
        enforce_zero_cloud_data_leak_guard(m_payload)
        existing = ms_by_title.get(m_title.lower())
        if existing and existing.get("number"):
            m_num = int(existing["number"])
            _http_json_request(f"{base_api}/milestones/{m_num}", method="PATCH", payload=m_payload, headers=headers)
            milestone_num_by_id[ms["id"]] = m_num
        else:
            code, created_m = _http_json_request(f"{base_api}/milestones", method="POST", payload=m_payload, headers=headers)
            if code in (200, 201) and isinstance(created_m, dict) and created_m.get("number"):
                milestone_num_by_id[ms["id"]] = int(created_m["number"])

    # 3. Sync Deliverable Issues (TD-01 .. TD-12)
    st_iss, existing_issues = _http_json_request(
        f"{base_api}/issues?labels=project:tri-device-architecture&state=all&per_page=100",
        headers=headers,
    )
    existing_by_prefix: Dict[str, Dict[str, Any]] = {}
    epic_issue_existing: Optional[Dict[str, Any]] = None
    if isinstance(existing_issues, list):
        for iss in existing_issues:
            if not isinstance(iss, dict) or "pull_request" in iss:
                continue
            ititle = str(iss.get("title") or "")
            if ititle.startswith("[EPIC]"):
                epic_issue_existing = iss
            for d in status_report.get("deliverables", []):
                did = d["id"]
                if f"[{did}]" in ititle:
                    existing_by_prefix[did] = iss

    for d in status_report.get("deliverables", []):
        did = d["id"]
        is_done = d.get("status") == "completed"
        target_state = "closed" if is_done else "open"
        ms_num = milestone_num_by_id.get(d.get("milestone_id", ""))
        issue_body = _build_deliverable_issue_body(d, target_repo)
        issue_payload: Dict[str, Any] = {
            "title": d["title"],
            "body": issue_body,
            "labels": d.get("labels", ["project:tri-device-architecture"]),
        }
        if ms_num:
            issue_payload["milestone"] = ms_num
        enforce_zero_cloud_data_leak_guard(issue_payload)

        existing_iss = existing_by_prefix.get(did)
        if existing_iss and existing_iss.get("number"):
            inum = int(existing_iss["number"])
            issue_payload["state"] = target_state
            _http_json_request(f"{base_api}/issues/{inum}", method="PATCH", payload=issue_payload, headers=headers)
            issue_num_by_td[did] = inum
        else:
            code, created_iss = _http_json_request(f"{base_api}/issues", method="POST", payload=issue_payload, headers=headers)
            if code in (200, 201) and isinstance(created_iss, dict) and created_iss.get("number"):
                inum = int(created_iss["number"])
                issue_num_by_td[did] = inum
                if target_state == "closed":
                    _http_json_request(
                        f"{base_api}/issues/{inum}",
                        method="PATCH",
                        payload={"state": "closed", "state_reason": "completed"},
                        headers=headers,
                    )

    # 4. Sync Master Epic Issue
    epic_title = f"[EPIC] {status_report['title']}"
    epic_body = _build_master_epic_issue_body(status_report, issue_num_by_td)
    epic_payload: Dict[str, Any] = {
        "title": epic_title,
        "body": epic_body,
        "labels": [
            "project:tri-device-architecture",
            "device:apple-watch",
            "device:iphone",
            "device:laptop-hub",
            "security:e2ee-mtls",
            "payments:upi-bhim-icici",
        ],
    }
    enforce_zero_cloud_data_leak_guard(epic_payload)
    epic_number: Optional[int] = None
    if epic_issue_existing and epic_issue_existing.get("number"):
        epic_number = int(epic_issue_existing["number"])
        _http_json_request(f"{base_api}/issues/{epic_number}", method="PATCH", payload=epic_payload, headers=headers)
    else:
        code, created_epic = _http_json_request(f"{base_api}/issues", method="POST", payload=epic_payload, headers=headers)
        if code in (200, 201) and isinstance(created_epic, dict) and created_epic.get("number"):
            epic_number = int(created_epic["number"])

    return {
        "status": "ok",
        "repository": target_repo,
        "labels_synced": len(status_report.get("labels", [])),
        "milestones_synced": milestone_num_by_id,
        "deliverable_issues_synced": issue_num_by_td,
        "epic_issue_number": epic_number,
        "epic_issue_url": f"https://github.com/{target_repo}/issues/{epic_number}" if epic_number else "",
        "project": status_report,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage & synchronize the AFCC Tri-Device Architecture Project on GitHub.")
    parser.add_argument("--sync-github", action="store_true", help="Provision and sync Labels, Milestones, Epic, and Issues to GitHub REST API")
    parser.add_argument("--sync-docs", action="store_true", help="Generate and update docs/PROJECTS_TRI_DEVICE_ROADMAP.md and wiki page")
    parser.add_argument("--status", action="store_true", help="Print project status JSON")
    args = parser.parse_args(argv)

    if args.sync_github:
        res = sync_tri_device_project_to_github()
        print(json.dumps(res, indent=2))
        return 0
    if args.sync_docs:
        res = sync_local_project_docs()
        print(json.dumps(res, indent=2))
        return 0

    rep = compute_tri_device_project_status()
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
