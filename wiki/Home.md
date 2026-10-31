# ⚡ Personal Agentic Fleet Documentation Wiki

Welcome to the official **Personal Agentic Fleet Technical Encyclopedia & Operations Wiki**!

[![Release: v2.13.1](https://img.shields.io/badge/Release-v2.13.1-00b4d8.svg)](Release-Notes)
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
## 🆕 Latest Release Highlights (`v2.13.1`)

> **Live Codebase Inventory**: `7` Built-In Agents • `123` REST API Endpoints • `33` Core Microkernel Modules • `20` Automation Tools • `480` Passing Unit Tests (`$0.00` Token Spend) — See **[[Release-Notes]]**

### Added
- **Autonomous Post-Commit GitHub Pipeline, Vulnerability & CodeQL Sentinel (`fleet/tools/github_pipeline_sentinel.py`, `fleet/tools/install_git_hooks.py`, `fleet/agents/pr_review/agent.py`)**:
  - Automatically audits GitHub Actions check-runs, CodeQL SARIF annotations & `/code-scanning/alerts`, GitHub Dependabot & live zero-auth OSV.dev CVE/GHSA advisories (`https://api.osv.dev/v1/querybatch`), and Secret Scanning + local 12-layer SAST checks after every commit and push (`post-commit` & `pre-push` detached background sentinel) and every 30 minutes via `PRReviewAgent` (`GET` / `POST /api/pr_review/pipeline_audit`).
  - Automatically applies deterministic fixes (`auto_fixer.py` + `pyproject.toml` vulnerable dependency floor auto-bumping) and logs/dispatches self-healing remediation tasks to Antigravity Live whenever a remote pipeline or security check fails.
- **Expanded Pre-Commit CodeQL ReDoS & Workflow Deprecation Guards (`fleet/tools/security_scanner.py`, `fleet/tools/auto_fixer.py`)**:
  - Added proactive SAST detection for overlapping polynomial ReDoS regex quantifiers (`CWE-1333`) and deprecated `github/codeql-action@v3` references (with automatic `@v3` -> `@v4` upgrade in `auto_fixer.py`).

### Security
- **Eliminated All GitHub CodeQL Alerts & Dependency Advisories (`fleet/core/antigravity_mirror.py`, `fleet/core/hyperscalers.py`, `pyproject.toml`)**:
  - Replaced overlapping regex path extraction in `extract_task_fingerprint()` with a linear `O(N)` zero-regex token parser (`0` `py/polynomial-redos` alerts).
  - Hardened `_normalize_agy_cli_model()` and `_call_antigravity_cli()` / `_run_agy_cli_turn()` so user prompts are piped strictly over `stdin` (`--input-format text`) with untainted constant/allowlisted `argv` flags (`0` `py/command-line-injection` alerts).
  - Bumped dev dependency floor `pytest>=9.0.3` in `pyproject.toml` to remediate `GHSA-6w46-j5rx-g56g` / `PYSEC-2026-1845`.

### Fixed
- **GitHub Actions Workflow Hygiene (`.github/workflows/codeql.yml`, `.github/workflows/pages.yml`)**:
  - Upgraded `github/codeql-action/init` and `github/codeql-action/analyze` from `@v3` to `@v4`, and added a Pages enablement API pre-check in `pages.yml` to prevent `configure-pages` failure annotations when GitHub Pages is not enabled.
<!-- AUTO-LATEST-RELEASE:END -->
