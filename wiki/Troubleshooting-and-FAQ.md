# 🔧 Troubleshooting, Diagnostics & Operational Runbooks

> **Release Version**: `v2.9.6` | **Diagnostic Tools**: `python -m fleet.tools.fleet_doctor`, `python -m fleet.tools.auto_fixer`, `python -m fleet.tools.preflight_gate`

This guide provides step-by-step diagnostic and recovery runbooks for common workstation, database, UI, and CI/CD scenarios.

---

## 1. First-Response Automated Diagnostics

Before manual debugging, run the built-in zero-token diagnostic and self-repair tools:

```powershell
# 1. Run the 7-Point Fleet Doctor (checks Python, SQLite WAL, DPAPI Vault, ACLs, Port 7890)
python -m fleet.tools.fleet_doctor

# 2. Run the Zero-Intervention Auto-Fixer (repairs Python AST, HTML/CSS parens, and workflows)
python -m fleet.tools.auto_fixer

# 3. Run the Full Preflight Quality Gate
python -m fleet.tools.preflight_gate
```

---

## 2. Common Operational Scenarios & Resolutions

### Scenario A: Port `7890` Already in Use (`Errno 10048 / EADDRINUSE`)
- **Symptom**: Starting `python -m fleet.app` reports that port `7890` is already bound.
- **Cause**: A background AFCC daemon (`pythonw.exe` or `python.exe`) is already running and serving `http://127.0.0.1:7890`.
- **Resolution**:
  - Open `http://127.0.0.1:7890` directly in your browser, or
  - Launch on an alternate port: `python -m fleet.app --port 7891`.

### Scenario B: SQLite Database Locked (`sqlite3.OperationalError: database is locked`)
- **Symptom**: Concurrent writes timeout during heavy background operations.
- **Automatic Mitigation**: `FleetDatabase` configures `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=15000` (15 seconds), and `AutoHealer` automatically runs `PRAGMA wal_checkpoint(PASSIVE)` when WAL size grows.
- **Manual Recovery**:
  ```powershell
  python -c "from fleet.core.database import FleetDatabase; db = FleetDatabase(); db.optimize_database()"
  ```

### Scenario C: VS Code Problems Tab Reports CSS or Pyright Diagnostics
- **Cause**: Unbalanced parentheses inside inline `style="..."` or `<style>` blocks in HTML templates, or untyped variables in Python modules.
- **Resolution**:
  ```powershell
  python -m fleet.tools.auto_fixer --stage
  ```
  `audit_html_css_diagnostics()` and `run_auto_fixer()` automatically repair unbalanced CSS declarations and verify `0` problems.

### Scenario D: GitHub Wiki Out of Sync with Local `wiki/` Directory
- **Resolution**:
  ```powershell
  python -m fleet.tools.doc_wiki_enhancer
  python -m fleet.tools.sync_wiki
  ```
  This synchronizes all version badges, sidebars, release notes, and deep-dive guides and pushes them directly to `git@github.com:macazaka/personal-agentic-fleet.wiki.git`.

