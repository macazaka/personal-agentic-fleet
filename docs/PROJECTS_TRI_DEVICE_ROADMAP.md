# ⌚📱💻 AFCC Tri-Device Ecosystem Architecture — GitHub Project & Delivery Tracker

[![Project Status](https://img.shields.io/badge/Project-Active%20(%20100.0%25%20Delivered%20)-10b981?style=for-the-badge)](#)
[![Milestones](https://img.shields.io/badge/GitHub%20Milestones-4%20Phases-38bdf8?style=for-the-badge)](https://github.com/macazaka/personal-agentic-fleet/milestones)
[![Issues](https://img.shields.io/badge/Tracked%20Deliverables-12%20Issues%20(TD--01..TD--12)-a855f7?style=for-the-badge)](https://github.com/macazaka/personal-agentic-fleet/issues?q=label%3Aproject%3Atri-device-architecture)
[![Security](https://img.shields.io/badge/Security-Zero--Cloud%20AES--256--GCM%20%2B%20mTLS-f59e0b?style=for-the-badge)](https://github.com/macazaka/personal-agentic-fleet/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)

> **Canonical Architecture Blueprint**: [`docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md`](https://github.com/macazaka/personal-agentic-fleet/blob/main/docs/APPLE_ECOSYSTEM_IPHONE_WATCH_AFCC_ARCHITECTURE.md)
> **GitHub Project Manifest**: [`.github/projects/tri-device-architecture.json`](https://github.com/macazaka/personal-agentic-fleet/blob/main/.github/projects/tri-device-architecture.json)
> **Automated GitHub Tracker Workflow**: [`.github/workflows/tri_device_project_tracker.yml`](https://github.com/macazaka/personal-agentic-fleet/blob/main/.github/workflows/tri_device_project_tracker.yml)

---

## 🧭 1. Executive Project Summary & GitHub Governance

This project tracks, monitors, communicates, and delivers the **Tri-Device Ecosystem Architecture** connecting:
1. **⌚ Tier 1 — Apple Watch (Sensor & Micro-Interaction Edge)**: Continuous biometric capture (HR, HRV SDNN, Sleep Stages, SpO2, Active Rings), Smart Stack Complication (`/api/mobile/watch/complication`), and Siri Action Button voice bridge.
2. **📱 Tier 2 — iPhone (Pocket Cockpit & Open Payment Aggregator)**: HealthKit background bridge (`/api/mobile/health/ingest`), installable Mobile Pocket Cockpit PWA, and **1-Tap Open Payment Deep-Link Engine** (`/api/mobile/payments/deeplink` for **BHIM UPI**, **ICICI iMobile Pay**, **Google Pay**, and **PhonePe**).
3. **💻 Tier 3 — Windows Laptop (Sovereign AFCC Brain & Encrypted Vault)**: Master SQLite + AES-256-GCM / HKDF-SHA256 / FF1 FPE encrypted vault, `1.5x–3x` Voice Cockpit with `"Mahadev"` wake word, and live Action-Item Conversational Engine.

### Associated GitHub Features Active on This Project
| GitHub Feature | Purpose & How It Is Used | Link / Artifact |
| :--- | :--- | :--- |
| **🏷️ GitHub Labels (10)** | Categorize issues & PRs by device (`device:apple-watch`, `device:iphone`, `device:laptop-hub`), phase (`phase:1..4`), and domain (`payments:upi-bhim-icici`, `security:e2ee-mtls`) | [Repository Labels](https://github.com/macazaka/personal-agentic-fleet/labels) |
| **🎯 GitHub Milestones (4)** | Track completion % and target dates across Phases 1, 2, 3, and 4 | [Repository Milestones](https://github.com/macazaka/personal-agentic-fleet/milestones) |
| **📋 GitHub Epic & Sub-Issues (13)** | Master Epic Issue with native Tasklist progress bar + 12 granular deliverable issues (`TD-01`..`TD-12`) | [Tri-Device Issues](https://github.com/macazaka/personal-agentic-fleet/issues?q=label%3Aproject%3Atri-device-architecture) |
| **📝 GitHub Issue & Discussion Forms** | Structured YAML forms for filing new Tri-Device deliverables and posting milestone status updates | [`.github/ISSUE_TEMPLATE/tri_device_deliverable.yml`](https://github.com/macazaka/personal-agentic-fleet/blob/main/.github/ISSUE_TEMPLATE/tri_device_deliverable.yml) |
| **⚙️ GitHub Actions CI & Project Sync** | Automatically provisions Labels/Milestones/Issues, runs `pytest` on Tri-Device endpoints, and publishes Job Summaries | [`.github/workflows/tri_device_project_tracker.yml`](https://github.com/macazaka/personal-agentic-fleet/blob/main/.github/workflows/tri_device_project_tracker.yml) |
| **📖 GitHub Wiki & GitHub Pages** | Auto-publishes the live roadmap, Kanban board, and API documentation on every push | [Wiki Guide](https://github.com/macazaka/personal-agentic-fleet/wiki/Tri-Device-Architecture-Project) |

---

## 🏁 2. Milestone Delivery Matrix

| Milestone Phase | Completion Progress | Target Date | Deliverables |
| :--- | :--- | :---: | :--- |
| **Phase 1: Encrypted Apple Watch & iPhone HealthKit Bridge** | `██████████` **100.0%** (`4/4`) | `2026-11-30` | `TD-01`, `TD-02`, `TD-03`, `TD-04` |
| **Phase 2: iPhone Pocket Cockpit PWA & High-Speed Voice Relay** | `██████████` **100.0%** (`3/3`) | `2026-12-15` | `TD-05`, `TD-06`, `TD-07` |
| **Phase 3: 1-Tap Open Payment Deep-Link Engine (BHIM / ICICI / UPI)** | `██████████` **100.0%** (`2/2`) | `2026-12-31` | `TD-08`, `TD-09` |
| **Phase 4: Apple Watch Smart Stack Complication & Siri AppIntents** | `██████████` **100.0%** (`3/3`) | `2027-01-15` | `TD-10`, `TD-11`, `TD-12` |

---

## 📊 3. Live Project Kanban Board (`12/12` Completed — `100.0%`)

### ✅ Completed & Verified (`12`)
- **`TD-01` (P0)**: **Tri-Device System Architecture & Zero-Cloud Threat Model Blueprint** — *All Devices (Watch • iPhone • Laptop)*
- **`TD-02` (P0)**: **Encrypted Apple Health & Watch Biometric Ingestion API (/api/mobile/health/ingest)** — *Laptop Hub + iPhone Bridge*
- **`TD-03` (P1)**: **iOS 26.3.1 FaceID-Unlocked Shortcuts & Health Auto Export Sync Recipe** — *iPhone*
- **`TD-04` (P1)**: **Watch HRV, Sleep & Resting HR Auto-Adaptation for 6-Day Mudgal/Samtola/Bhim Gadha Split** — *Apple Watch + Laptop Hub*
- **`TD-05` (P1)**: **Mobile-Responsive AFCC Pocket Cockpit PWA & Home Screen Web App Manifest** — *iPhone*
- **`TD-06` (P0)**: **High-Speed Voice Cockpit (1.5x-3x Speed, 'Mahadev' Wake Word & Live Action-Item Conversation)** — *Laptop Hub + iPhone + Watch*
- **`TD-07` (P2)**: **Tailscale WireGuard Mesh, iOS Scriptable Widgets & Local Root CA (afcc_root_ca.crt) Trust Onboarding** — *iPhone + Laptop Hub*
- **`TD-08` (P0)**: **1-Tap Open Payment Deep-Link Engine (BHIM UPI, ICICI iMobile, GPay, PhonePe) & SVG QR Matrix** — *iPhone + Laptop Hub*
- **`TD-09` (P1)**: **Automated Post-Payment Action-Item Closure & Receipt Reference Audit Log** — *iPhone + Laptop Hub*
- **`TD-10` (P1)**: **Apple Watch Smart Stack Complication & WidgetKit Snapshot API (/api/mobile/watch/complication)** — *Apple Watch*
- **`TD-11` (P2)**: **Apple Watch Action Button & Siri AppIntents Voice Bridge ('Ask Mahadev')** — *Apple Watch + iPhone*
- **`TD-12` (P0)**: **Automated GitHub Project Governance, CI Verification Gate & Zero-Cloud Telemetry Sync** — *GitHub + Laptop Hub*

### 🔄 In Progress (`0`)
- None

### 📋 Planned Backlog (`0`)
- None

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
