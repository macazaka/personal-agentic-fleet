# 📝 Maintaining Up-to-Date Documentation in Every Commit

To ensure Personal Agentic Fleet's documentation never goes stale or drifts from the underlying code, this repository implements **Continuous Documentation Verification**. Every commit must maintain strict parity between code changes and documentation.

---

## 1. Documentation Verification Invariants

Every commit must satisfy four core documentation invariants:
1. **Zero Dead Links**: All relative markdown links (e.g., `docs/ARCHITECTURE.md`, `INSTALL.md`, `SECURITY.md`) must resolve to active files.
2. **Version Parity**: When `VERSION` is updated in `fleet/config.py`, it must match `pyproject.toml`, `CHANGELOG.md`, `docs/API_REFERENCE.md`, and `README.md`.
3. **Hyperscaler & Model Parity**: If a new model or cloud provider is added to `fleet/core/hyperscalers.py` or `fleet/core/antigravity_mirror.py`, it must be documented in `docs/HYPERSCALERS_AND_DEV_TOOLS.md` and `docs/ARCHITECTURE.md`.
4. **Developer Tool Parity**: If new AI developer tools or CLI bridges are introduced in `fleet/core/dev_tools.py`, instruction files (`.github/copilot-instructions.md`, `CLAUDE.md`, `GEMINI.md`) and `docs/HYPERSCALERS_AND_DEV_TOOLS.md` must be updated.

---

## 2. Automated Documentation Audit in Preflight Gate

The local preflight gate ([`fleet/tools/preflight_gate.py`](../fleet/tools/preflight_gate.py)) verifies the presence and integrity of all documentation files before code can be pushed to GitHub:
- `README.md`
- `SECURITY.md`
- `INSTALL.md`
- `CHANGELOG.md`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/HYPERSCALERS_AND_DEV_TOOLS.md`
- `docs/PREREQUISITES_AND_OS.md`
- `docs/API_REFERENCE.md`
- `docs/DEVELOPER_GUIDE.md`
- docs/CUSTOMIZING_AGENTS.md
- `docs/ROBUSTNESS_BACKLOG.md`
- `docs/ROBUSTNESS_GUIDE.md`
- `docs/DEPLOYMENT_AND_SCENARIOS.md`
- `.github/copilot-instructions.md`
- `CLAUDE.md`
- `GEMINI.md`

If any document is missing or empty, `preflight_gate.py` fails with exit code `1`.

---

## 3. Developer Commit Checklist

Before committing changes:
- [ ] **Code Changes Documented**: If adding an endpoint, add it to `docs/API_REFERENCE.md`. If adding an agent, update `docs/ARCHITECTURE.md` and `docs/DEVELOPER_GUIDE.md`.
- docs/CUSTOMIZING_AGENTS.md
- docs/ROBUSTNESS_BACKLOG.md
- `docs/DEPLOYMENT_AND_SCENARIOS.md`
- [ ] **Security Changes Updated**: If introducing a new security invariant, document it in `docs/SECURITY.md`.
- [ ] **Synchronize AI Instructions**: Run `python -c "from fleet.core.dev_tools import sync_all_developer_tool_instructions; sync_all_developer_tool_instructions()"` to update Copilot, Claude, and Gemini prompt guidelines.
- [ ] **Run Preflight Gate**: Execute `python -m fleet.tools.preflight_gate` to verify that all 130+ tests, the 12-layer security scanner, and documentation audits pass 100%.
