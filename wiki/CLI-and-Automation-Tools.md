# Unified Fleet CLI & Proactive Automation Tools (`v2.9.6`)

Personal Agentic Fleet provides a complete zero-token (`$0.00`) command-line interface and proactive automation suite that keeps code quality, release versions, security invariants, documentation, and the GitHub Wiki continuously synchronized.

---

## 1. Unified `fleet` Command-Line Interface

Run via `fleet <command>`, `python -m fleet <command>`, or `.\fleet.bat <command>`:

| Subcommand | Description |
| :--- | :--- |
| `fleet start [--port 7890]` | Launch the Agentic Fleet Control Center (AFCC) and background daemon. |
| `fleet status` | Display live runtime, version, task, routine, and security status. |
| `fleet doctor` | Run the 7-point Fleet Doctor diagnostic and vault ACL hardening check. |
| `fleet scan` | Execute the 12-Layer Deterministic Security & Privacy Scanner. |
| `fleet fix [--stage]` | Run the zero-intervention VS Code (Pylance/Pyright/HTML/CSS) & GitHub CodeQL auto-fixer. |
| `fleet release [--bump auto\|patch\|minor\|major]` | Proactively bump/sync release versions and update `CHANGELOG.md`. |
| `fleet docs [--sync-wiki]` | Proactively enhance documentation and synchronize `wiki/` pages. |
| `fleet mind [--dream] [--evolve]` | Inspect the 4-Layer Cognitive Fleet Mind & Harmony Index. |
| `fleet test` | Execute the full unit test suite with zero network/token usage. |
| `fleet briefing` | Generate the deterministic daily morning briefing. |
| `fleet tasks` / `add-task` / `complete-task` | List, create, and complete priority tasks from the terminal. |
| `fleet routines` / `toggle-routine` | Inspect and toggle daily habit routines. |
| `fleet create-agent` | Scaffold a new isolated agent package with `manifest.json` contract. |
| `fleet sync-wiki` | Push local `wiki/` pages to the live GitHub Wiki repository (`personal-agentic-fleet.wiki.git`). |
| `fleet sbom` | Generate the CycloneDX 1.5 Software Bill of Materials (`sbom.cdx.json`). |

---

## 2. Two-Tier Documentation & Release Synchronization Architecture

Personal Agentic Fleet enforces a strict **Two-Tier Progressive Disclosure Model** across `README.md`, `docs/*.md`, and `wiki/*.md`:
- **Tier 1 (`README.md`)**: Executive summary, OS compatibility table, 60-second installation, auto-synchronized What's New release box, and direct deep-dive links into the live GitHub Wiki.
- **Tier 2 (`wiki/*.md` — 21 Deep-Dive Guides)**: Exhaustive subsystem specifications, mathematical formulas, SQL schemas, live AST-introspected REST API inventories, and operational runbooks.
- **Automated Version Parity (`release_manager.py` & `doc_wiki_enhancer.py`)**: On every commit and release tag, `run_proactive_release_check()` and `run_proactive_doc_wiki_enhancement()` synchronize the exact semantic version (`v2.9.6`) across `fleet/__init__.py`, `fleet/config.py`, `pyproject.toml`, `dashboard.html`, `README.md`, `CHANGELOG.md`, `wiki/Home.md`, `wiki/_Sidebar.md`, `wiki/_Footer.md`, `wiki/Release-Notes.md`, and all deep-dive Wiki headers.

---

## 3. Proactive Pre-Commit Diagnostic & Auto-Fixer Engine (`fleet/tools/auto_fixer.py`)

Executed automatically on every `git commit` before code is staged:
1. **AST CodeQL & Static Analysis Remediation**: Scans Python ASTs for unused imports, bare `except:` blocks, unquoted subprocess paths, and `newline='\n'` file-write consistency.
2. **HTML/CSS VS Code Diagnostic Gate (`audit_html_css_diagnostics`)**: Validates balanced parentheses `()`, braces `{}`, and string quotes inside every `<style>` block and inline `style="..."` attribute across `dashboard.html` and `fleet/agents/*/ui/panel.html`, preventing `css-rparentexpected` diagnostics.
3. **GitHub Actions Workflow Validator (`audit_github_workflows`)**: Audits `.github/workflows/*.yml` for Node.js 24 readiness (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'`), pinned `ubuntu-24.04` runners, and immutable release tag safety.
4. **Pyright Static Type Verification**: Runs `pyright` across `fleet/` and `tests/` enforcing `0 errors, 0 warnings`.

---

## 4. Proactive Automation Modules (`19` Tools)

| Python Module | Source File | Purpose |
| :--- | :--- | :--- |
| `fleet.tools.auto_fixer` | [`fleet/tools/auto_fixer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/auto_fixer.py) | Autonomous Zero-Intervention Auto-Fixer for VS Code (Pylance/Pyright) & GitHub CodeQL Issues. |
| `fleet.tools.auto_healer` | [`fleet/tools/auto_healer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/auto_healer.py) | CLI Command & Autonomous Log Diagnostics Tool for Personal Agentic Fleet. |
| `fleet.tools.ci_runner` | [`fleet/tools/ci_runner.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/ci_runner.py) | CI Test Runner & Annotation Generator for Personal Agentic Fleet. |
| `fleet.tools.crash_reporter` | [`fleet/tools/crash_reporter.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/crash_reporter.py) | Global Crash Reporter & Sanitized Diagnostic Dump Engine for Personal Agentic Fleet. |
| `fleet.tools.create_agent` | [`fleet/tools/create_agent.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/create_agent.py) | Fleet Agent Scaffolder CLI (fleet.tools.create_agent). |
| `fleet.tools.doc_wiki_enhancer` | [`fleet/tools/doc_wiki_enhancer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/doc_wiki_enhancer.py) | Proactive Documentation & GitHub Wiki Enhancement Engine for Personal Agentic Fleet. |
| `fleet.tools.fleet_doctor` | [`fleet/tools/fleet_doctor.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/fleet_doctor.py) | Fleet Doctor — End-to-End Runtime, Python Version (>=3.10), ACL & Security Health Verifier. |
| `fleet.tools.fleet_mind` | [`fleet/tools/fleet_mind.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/fleet_mind.py) | Fleet Mind CLI — Command-line introspection & trigger for the 4 cognitive layers. |
| `fleet.tools.github_branch_protection` | [`fleet/tools/github_branch_protection.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/github_branch_protection.py) | GitHub Rulesets & Local Main Branch Protection Verifier and Provisioner for Personal Agentic Fleet. |
| `fleet.tools.install_git_hooks` | [`fleet/tools/install_git_hooks.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/install_git_hooks.py) | Git Pre-Commit & Pre-Push Security & CI Quality Gate Installer for Personal Agentic Fleet. |
| `fleet.tools.install_service` | [`fleet/tools/install_service.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/install_service.py) | Workstation Service Daemonization Installer for Personal Agentic Fleet. |
| `fleet.tools.preflight_gate` | [`fleet/tools/preflight_gate.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/preflight_gate.py) | Pre-Push Quality Gate and Preflight Verifier for Personal Agentic Fleet. |
| `fleet.tools.proactive_lifecycle` | [`fleet/tools/proactive_lifecycle.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/proactive_lifecycle.py) | Master Proactive Zero-Intervention Lifecycle Orchestrator for Personal Agentic Fleet. |
| `fleet.tools.release_manager` | [`fleet/tools/release_manager.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/release_manager.py) | Proactive Semantic Release & Version Synchronization Engine for Personal Agentic Fleet. |
| `fleet.tools.sbom_generator` | [`fleet/tools/sbom_generator.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/sbom_generator.py) | CycloneDX v1.5 Software Bill of Materials (SBOM) & Cryptographic Integrity Generator. |
| `fleet.tools.security_scanner` | [`fleet/tools/security_scanner.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/security_scanner.py) | Automated Zero-Token Security, Secret, PII & SAST Scanner for Personal Agentic Fleet. |
| `fleet.tools.sync_wiki` | [`fleet/tools/sync_wiki.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/sync_wiki.py) | GitHub Wiki Synchronization Utility for Personal Agentic Fleet. |
| `fleet.tools.system_tools` | [`fleet/tools/system_tools.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/system_tools.py) | System and OS integration tools for Windows, macOS, and Linux. |
| `fleet.tools.test_runner` | [`fleet/tools/test_runner.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/tools/test_runner.py) | Automated Test Runner & Coverage Engine for Personal Agentic Fleet. |

---

## 5. Isolated Agent Packages (`7` Built-In Agents)

| Agent ID | Display Name & Version | Capability Permissions | Description |
| :--- | :--- | :--- | :--- |
| `antigravity` | **Antigravity Live** (`v1.8.0`) | `db:read, db:write, event_bus:publish, ui:render` | Real-time Antigravity agent mirror, token health vault, and parallel subagent telemetry. |
| `backlog` | **Feature Backlog** (`v1.8.0`) | `db:read, db:write, ui:render` | Product roadmap and feature backlog management. |
| `gmail` | **Gmail Intelligence** (`v1.8.0`) | `db:read, db:write, network:gmail_oauth, event_bus:publish, event_bus:subscribe, ui:render` | 5-folder deterministic email classifier and 1-click unsubscribe engine. |
| `health` | **Health & Wellness** (`v1.8.0`) | `db:read, db:write, filesystem:videos, event_bus:publish, ui:render` | FFD Diabetes Reversal, 6-Day Mudgal/Samtola/Bhim Gadha Strength Split, and Video Vault. |
| `optimizer` | **PC Optimizer** (`v1.8.0`) | `db:read, db:write, filesystem:temp, system:diagnostics, ui:render` | Windows PC diagnostics, temp file cleanup, DNS flush, and RAM working-set optimization. |
| `overview` | **Overview** (`v1.8.0`) | `db:read, db:write, event_bus:publish, event_bus:subscribe, ui:render` | Daily Morning Briefing, Task & Goal Board, Routine Checklist, and Automated Test Suite. |
| `pr_review` | **Admin PR Review & CI Quality Gate** (`v1.0.0`) | `db:read, db:write, event_bus:publish, event_bus:subscribe, network:github_api, ui:render` | Admin-only GitHub Pull Request auditor, CI health monitor, and Dependabot automation. |
