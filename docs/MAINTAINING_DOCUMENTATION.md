# 📝 Maintaining Up-to-Date Documentation, Releases & Wiki in Every Commit

To ensure Personal Agentic Fleet's release numbers, documentation, and GitHub Wiki never go stale or drift from the underlying code, this repository implements **Proactive Continuous Release, Documentation & Wiki Synchronization** (`$0.00 / 0 LLM tokens`).

---

## 1. Core Documentation & Release Invariants

Every commit and push automatically enforces five core invariants:
1. **Zero Dead Links**: All relative markdown links across `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `docs/*.md`, and `wiki/*.md` must resolve to active files.
2. **Proactive Semantic Version Parity (`v2.8.3`)**: `fleet.tools.release_manager` automatically evaluates Conventional Commits (`feat:`, `fix:`, `security:`, `BREAKING CHANGE`) since the last Git tag, bumps the semantic version at relevant times, synthesizes categorized release notes in `CHANGELOG.md`, and synchronizes the version across `fleet/__init__.py`, `fleet/config.py`, `pyproject.toml`, `fleet/web/templates/dashboard.html`, `README.md`, `wiki/`, and `fleet/data/sbom.cdx.json`.
3. **Proactive Documentation & Wiki Enhancement**: `fleet.tools.doc_wiki_enhancer` introspects live agents (`fleet/agents/*/manifest.json`), CLI subcommands (`fleet/cli.py`), automation tools (`fleet/tools/*.py`), and test counts to keep `docs/` and `wiki/` (`_Sidebar.md`, `_Footer.md`, `Home.md`, `Release-Notes.md`, `CLI-and-Automation-Tools.md`) continuously updated.
4. **Hyperscaler & Developer Tool Parity**: `sync_all_developer_tool_instructions()` synchronizes `.github/copilot-instructions.md`, `CLAUDE.md`, and `GEMINI.md`.
5. **Zero VS Code & CodeQL Diagnostics**: `fleet.tools.auto_fixer` automatically repairs static type and SAST issues prior to every commit.

---

## 2. Proactive Lifecycle Automation Scripts

| Script / Module | Role in Proactive Pipeline |
| :--- | :--- |
| `python -m fleet.tools.proactive_lifecycle` | Master orchestrator running Auto-Fixer, Release Manager, Doc/Wiki Enhancer, and SBOM Generator before every commit/push. |
| `python -m fleet.tools.release_manager` | Semantic version auto-bumper, `CHANGELOG.md` synthesizer, and 8-file version synchronizer. |
| `python -m fleet.tools.doc_wiki_enhancer` | Live codebase introspector updating `docs/` and `wiki/` pages automatically. |
| `python -m fleet.tools.auto_fixer` | Zero-intervention VS Code (Pylance/Pyright) and GitHub CodeQL SAST auto-remediator. |
| `python -m fleet.tools.preflight_gate` | 6-stage pre-push gate verifying Fleet Doctor, 12-Layer Security (`100/100`), Agent Isolation, Docs/Wiki links, Pyright (`0 errors`), and all `415+` unit tests. |
| `python -m fleet.tools.sync_wiki` | Synchronizes `wiki/*.md` to `macazaka/personal-agentic-fleet.wiki.git`. |

---

## 3. Verified Documentation Corpus

The local preflight gate ([`fleet/tools/preflight_gate.py`](../fleet/tools/preflight_gate.py)) verifies the presence and link integrity of all documentation files:
- `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/HYPERSCALERS_AND_DEV_TOOLS.md`, `docs/PREREQUISITES_AND_OS.md`
- `docs/API_REFERENCE.md`, `docs/DEVELOPER_GUIDE.md`, `docs/AGENT_DEVELOPMENT_GUIDE.md`, `docs/CUSTOMIZING_AGENTS.md`
- `docs/MAINTAINING_DOCUMENTATION.md`, `docs/ROBUSTNESS_BACKLOG.md`, `docs/ROBUSTNESS_GUIDE.md`, `docs/DEPLOYMENT_AND_SCENARIOS.md`
- `wiki/Home.md`, `wiki/Release-Notes.md`, `wiki/CLI-and-Automation-Tools.md`, `wiki/_Sidebar.md`, `wiki/_Footer.md`
