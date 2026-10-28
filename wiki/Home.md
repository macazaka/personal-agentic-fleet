# ⚡ Personal Agentic Fleet Documentation Wiki

Welcome to the official **Personal Agentic Fleet Technical Encyclopedia & Operations Wiki**!

[![Release: v2.9.7](https://img.shields.io/badge/Release-v2.9.7-00b4d8.svg)](Release-Notes)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Security: 100/100 PASS](https://img.shields.io/badge/Security%20Audit-100%2F100%20%5B12%20Layers%5D-brightgreen.svg)](Security-Model)
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)](Architecture)
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First%20DPAPI-teal.svg)](Security-Model)
[![Hyperscalers](https://img.shields.io/badge/Hyperscalers-Google%20%7C%20Azure%20%7C%20AWS%20%7C%20Claude%20%7C%20Ollama-purple.svg)](Hyperscalers-Token-Optimizer-and-Scheduler)
[![Windows: 10 / 11](https://img.shields.io/badge/Windows-10%20%7C%2011%20(64--bit)-0078D6.svg?logo=windows)](Installation-and-Quick-Start)
[![macOS: Universal](https://img.shields.io/badge/macOS-Apple%20Silicon%20%7C%20Intel-black.svg?logo=apple)](Installation-and-Quick-Start)
[![Linux: Native](https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch-orange.svg?logo=linux)](Linux-and-Quick-Start)

> **Two-Tier Progressive Disclosure Documentation Architecture**:
> - **Repository [`README.md`](https://github.com/macazaka/personal-agentic-fleet/blob/main/README.md)**: Executive overview, 60-second installation, OS compatibility matrix, and quick-reference links.
> - **GitHub Wiki (17 Deep-Dive Guides)**: Exhaustive subsystem internals, mathematical formulas (`PhysicalBrain`, BM25 RAG, Fuzzy Jaccard/Trigram cache, AWS SigV4 HMAC-SHA256), 8-table SQLite WAL schemas, 6-Day Mudgal/Samtola/Bhim Gadha Akhada conditioning protocols, and operational runbooks—automatically synchronized with every release tag (`v2.8.6`).

---

## 📚 Complete 17-Page Wiki Deep-Dive Directory

### 🧠 Core Architecture, Cognitive Science & Zero-Token Engine
| Wiki Guide | Deep-Dive Technical Scope |
| :--- | :--- |
| **[[Architecture]]** | Multi-threaded HTTP/1.1 & RFC 7233 server, `ApiRouter` O(1) dispatch, `ScopedDatabaseProxy` least-privilege ACLs, and complete 8-table SQLite 3 WAL relational schema (`fleet_memory.db`). |
| **[[Cognitive-Fleet-Mind]]** | 4-Layer Gestalt (`PhysicalBrain`, `ConsciousExecutive`, `SubconsciousMind`, `FleetSoul`), Win32 PSAPI `WorkingMemorySnapshot`, `SelfCritiqueEngine` equations, and the **0–100 Cognitive Harmony Index**. |
| **[[Hyperscalers-Token-Optimizer-and-Scheduler]]** | **8-Layer Zero-Token Optimizer** (Tier 0 Intent Router, 35-page FFD BM25 RAG, Fuzzy Jaccard/Trigram Cache, AST Code Minifier), **Universal Hyperscaler Gateway** (pure-stdlib AWS SigV4, Gemini, Azure, Claude, Ollama), **AI Dev Tools Bridge**, and **`schedules.yaml` Cron/Interval Scheduler**. |

### 🖥️ Desktop Experience (AFCC) & Plug-and-Play Agents
| Wiki Guide | Deep-Dive Technical Scope |
| :--- | :--- |
| **[[AFCC-and-UI-Features]]** | **Agentic Fleet Control Center (AFCC)**, **6 scalable layouts** (`sidebar_dock`, `command_deck`, `launchpad_grid`, `compact_tabs`, `split_ops`, `zen_focus`), **6 themes**, `#viewHealth` DOM scoping, zero-scrollbar CSS engine, and Spotlight (`Ctrl+K`). |
| **[[Built-in-Agents]]** | Complete reference for all **7 built-in agents**: **Health & Wellness** (6-Day Mudgal/Samtola/Bhim Gadha Split + FFD Protocols + HTTP 206 video streaming), **Overview**, **PC Optimizer** (Win32 PSAPI), **Antigravity Mirror**, **Gmail 5-Folder Classifier**, **Backlog**, and **Mind**. |
| **[[Customizing-Agents]]** | Per-agent runtime customization (display name, icon, tab order, default landing tab, hyperscaler provider/model override, custom prompt, and `schedules.yaml` cron expressions). |
| **[[Agent-Development-Guide]]** | Masterclass in building isolated agents via the **4-Step Visual Wizard (`+`)**, `create-agent` Skill, CLI generator (`fleet create-agent`), `manifest.json` contracts, and unit testing. |
| **[[UX-Roadmap-and-Feature-Backlog]]** | Prioritized 10-feature **UX & Agent-Simplicity Roadmap (`UX-01` – `UX-10`)**: Zero-Code Agent Studio Skill, Autonomous Process Discovery Agent (`process_discovery`), Multi-Agent Playbooks, and Universal Omnibar. |

### ⚙️ Security, Robustness, CI/CD & Operations
| Wiki Guide | Deep-Dive Technical Scope |
| :--- | :--- |
| **[[Installation-and-Quick-Start]]** | Step-by-step setup across Windows 10/11, macOS, and Linux, `bootstrap.ps1`, DPAPI vault initialization, and background daemon installation. |
| **[[Security-Model]]** | **12-Layer Automated Security & Privacy Scanner**, hardware-bound Windows DPAPI (`crypt32.dll`) + HMAC-SHA256 encryption, NTFS `icacls` hardening, and CycloneDX v1.5 SBOM provenance. |
| **[[Robustness-and-Self-Healing]]** | **7-Pillar Native Robustness Architecture**: Erlang-style thread supervisors, Windows Job Objects / POSIX `rlimit`, circuit breakers, `AutoHealer` log remediation, and forensic crash dumps. |
| **[[API-Reference]]** | Complete REST API endpoint catalog, Server-Sent Events (`/api/events`), FastMCP tool schemas, and HTTP 206 video streaming headers. |
| **[[CLI-and-Automation-Tools]]** | All 24+ `fleet.tools.*` automation modules, VS Code HTML/CSS/Pyright pre-commit auto-fixer, `release_manager.py`, `doc_wiki_enhancer.py`, and `sync_wiki.py`. |
| **[[CI-CD-and-Immutable-Releases]]** | GitHub Actions workflows (`release.yml`, `ci.yml`, `security.yml`, `codeql.yml`), immutable release pre-existence guards, `ubuntu-24.04` runner pinning, and Node.js 24 compliance. |
| **[[Proactive-CI-and-Release-Pipeline]]** | End-to-end local-to-cloud release pipeline, semantic version inference, and automated Wiki publication. |
| **[[Linux-and-Cross-Platform-Support]]** | Native OS integration matrix across Windows (`Kernel32`/`PSAPI`/`DPAPI`), macOS (`Keychain`/`sysctl`/`LaunchAgents`), and Linux (`SecretService`/`/proc`/`systemd`). |
| **[[Troubleshooting-and-FAQ]]** | Diagnostic runbooks for port conflicts, database locks, DPAPI vault migration, GitHub Actions immutable releases, and `fleet doctor`. |
| **[[Release-Notes]]** | Complete semantic version history and categorized changelog notes (synchronized with `CHANGELOG.md` at `v2.8.6`). |

<!-- AUTO-LATEST-RELEASE:START -->
## 🆕 Latest Release Highlights (`v2.9.7`)

> **Live Codebase Inventory**: `7` Built-In Agents • `109` REST API Endpoints • `31` Core Microkernel Modules • `19` Automation Tools • `428` Passing Unit Tests (`$0.00` Token Spend) — See **[[Release-Notes]]**

### Fixed
- Proactive release synchronization, static type verification, and documentation maintenance.
<!-- AUTO-LATEST-RELEASE:END -->
