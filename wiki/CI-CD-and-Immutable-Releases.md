# 🚀 CI/CD Pipelines, GitHub Actions & Immutable Releases Deep-Dive

> **Release Version**: `v2.10.0` | **Workflows**: `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `.github/workflows/security.yml`, `.github/workflows/codeql.yml` | **Local Tools**: `fleet/tools/release_manager.py`, `fleet/tools/auto_fixer.py`

Personal Agentic Fleet enforces a zero-regression, cryptographically verifiable release and Continuous Integration architecture across both **local Git hooks** and **GitHub Actions cloud runners**.

---

## 1. GitHub Actions Workflow Matrix (`.github/workflows/`)

| Workflow File | Trigger Events | Runner Image & Node Runtime | Key Verification & Build Steps |
| :--- | :--- | :--- | :--- |
| **`release.yml`** | `push` to tags `v*.*.*` or `workflow_dispatch` | `ubuntu-24.04` + `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` | • Immutable Release Pre-Existence Guard (`gh release view`)<br>• CycloneDX v1.5 SBOM generation (`sbom.cdx.json`)<br>• Python Wheel (`.whl`) & Source Distribution (`.tar.gz`) build<br>• Cryptographic `SHA256SUMS.txt` generation<br>• Atomic `gh release create` publishing |
| **`ci.yml`** | `push` & `pull_request` on `main` | 9-Matrix (`ubuntu-24.04`, `windows-latest`, `macos-latest` × Python `3.10`, `3.11`, `3.12`) | • Fleet Doctor 7-point check<br>• 12-Layer Security Scanner (`100/100`)<br>• Agent package isolation & manifest verification<br>• Full `pytest` unit test suite (`415+` tests) |
| **`security.yml`** | `push`, `pull_request`, and daily cron (`0 6 * * *`) | `ubuntu-24.04` + Node 24 | • 12-Layer SAST & Secret Audit<br>• CycloneDX SBOM drift check<br>• Dependency & license compliance audit |
| **`codeql.yml`** | `push`, `pull_request`, and weekly scan | `ubuntu-24.04` + Node 24 | • GitHub CodeQL semantic code analysis for Python & Actions |

---

## 2. Immutable GitHub Release Architecture (`release.yml`)

Repositories with **GitHub Immutable Releases** enabled reject any attempt to overwrite or delete assets on an existing release tag (`Validation Failed: Cannot delete asset from an immutable release`).

To guarantee 100% reliability under Immutable Releases:
1. **Pre-Flight Tag Existence Check (`check_release`)**:
   ```bash
   if gh release view "$TAG" --repo "${{ github.repository }}" >/dev/null 2>&1; then
     echo "exists=true" >> "$GITHUB_OUTPUT"
   else
     echo "exists=false" >> "$GITHUB_OUTPUT"
   fi
   ```
2. **Idempotent Skip on Existing Immutable Tag**: If `steps.check_release.outputs.exists == 'true'`, the workflow logs a clean notice and exits `0` without attempting to mutate locked assets.
3. **Atomic Single-Transaction Creation**: For new tags, `gh release create "$TAG" dist/* sbom.cdx.json SHA256SUMS.txt` uploads all distribution artifacts in a single atomic creation call rather than using `softprops/action-gh-release` (which attempts a delete-then-reupload cycle).

---

## 3. Proactive Workflow Auditing (`audit_github_workflows`)

`fleet/tools/auto_fixer.py` (`audit_github_workflows()`) proactively inspects `.github/workflows/*.yml` on every commit to enforce:
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` in the top-level `env:` block (eliminating Node.js 20 deprecation warnings).
- Explicit `ubuntu-24.04` runner pinning instead of unpinned `ubuntu-latest` labels.
- Absence of `softprops/action-gh-release` on immutable-release repositories.

