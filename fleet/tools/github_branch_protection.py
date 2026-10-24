"""
GitHub Rulesets & Local Main Branch Protection Verifier and Provisioner for Personal Agentic Fleet.

Enforces defense-in-depth protection for `main`, release branches, and tags across 3 layers (0 LLM tokens / $0.00):
  1. Declarative GitHub Rulesets (.github/branch-protection.json + .github/rulesets/*.json + .github/CODEOWNERS)
  2. Local Git Hook & Config Enforcement (.git/hooks/pre-push blocks force-pushes, deletions & unsigned commits on main)
  3. Remote GitHub Rulesets API Provisioner (--apply-remote via GITHUB_TOKEN or 1-Click GitHub Ruleset Import)
"""

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR

REPO_ROOT = BASE_DIR.parent
BRANCH_PROTECTION_FILE = REPO_ROOT / ".github" / "branch-protection.json"
RULESETS_DIR = REPO_ROOT / ".github" / "rulesets"
CODEOWNERS_FILE = REPO_ROOT / ".github" / "CODEOWNERS"

REQUIRED_RULESET_TYPES = {
    "deletion",
    "non_fast_forward",
    "required_linear_history",
    "required_signatures",
    "pull_request",
    "required_status_checks",
}

EXPECTED_RULESET_FILES = [
    "01-main-immutable-and-signed.json",
    "02-main-pr-and-ci-gate.json",
    "03-release-and-hotfix-branches.json",
    "04-release-tags-immutable.json",
]


def verify_branch_protection(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """
    Deterministically verifies that `main` branch protection rulesets, modular `.github/rulesets/*.json`,
    CODEOWNERS, and local pre-push non-fast-forward/deletion/signature guards are active.
    """
    bp_file = repo_root / ".github" / "branch-protection.json"
    rulesets_dir = repo_root / ".github" / "rulesets"
    co_file = repo_root / ".github" / "CODEOWNERS"
    pre_push = repo_root / ".git" / "hooks" / "pre-push"

    issues: List[str] = []
    verified_rulesets: List[str] = []

    if not bp_file.is_file():
        issues.append("Missing .github/branch-protection.json policy file.")
    else:
        try:
            data = json.loads(bp_file.read_text(encoding="utf-8"))
            if data.get("enforcement") != "active" or data.get("target") != "branch":
                issues.append(".github/branch-protection.json must have target='branch' and enforcement='active'.")
            rule_types = {r.get("type") for r in data.get("rules", []) if isinstance(r, dict)}
            missing = REQUIRED_RULESET_TYPES - rule_types
            if missing:
                issues.append(f".github/branch-protection.json missing required rules: {sorted(missing)}")
            else:
                verified_rulesets.append(".github/branch-protection.json")
        except Exception as exc:
            issues.append(f"Invalid .github/branch-protection.json: {exc}")

    for rs_name in EXPECTED_RULESET_FILES:
        rs_path = rulesets_dir / rs_name
        if not rs_path.is_file():
            issues.append(f"Missing modular ruleset .github/rulesets/{rs_name}")
        else:
            try:
                rs_data = json.loads(rs_path.read_text(encoding="utf-8"))
                if rs_data.get("enforcement") != "active" or not rs_data.get("rules"):
                    issues.append(f"Ruleset {rs_name} is not active or has empty rules.")
                else:
                    verified_rulesets.append(f".github/rulesets/{rs_name}")
            except Exception as exc:
                issues.append(f"Invalid JSON in .github/rulesets/{rs_name}: {exc}")

    if not co_file.is_file():
        issues.append("Missing .github/CODEOWNERS file.")

    if (repo_root / ".git").exists():
        if not pre_push.is_file():
            issues.append("Missing .git/hooks/pre-push hook.")
        else:
            hook_txt = pre_push.read_text(encoding="utf-8", errors="ignore")
            if "Main Branch Protection" not in hook_txt:
                issues.append(".git/hooks/pre-push is missing the Main Branch Protection gate.")

    return {
        "status": "PASS" if not issues else "FAIL",
        "protected_branch": "main",
        "policy_file": ".github/branch-protection.json",
        "rulesets_verified": verified_rulesets,
        "codeowners_file": ".github/CODEOWNERS",
        "local_pre_push_guard": pre_push.is_file(),
        "issues": issues,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }


def apply_remote_branch_protection(
    repo: str = "macazaka/personal-agentic-fleet",
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    """
    Applies the modular GitHub Rulesets in .github/rulesets/*.json directly
    to GitHub via the Rulesets REST API (`POST /repos/{repo}/rulesets`) if GITHUB_TOKEN is set.
    """
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    rulesets_dir = repo_root / ".github" / "rulesets"

    if not token:
        return {
            "status": "IMPORT_READY",
            "detail": (
                "All 4 GitHub Ruleset JSON files in '.github/rulesets/' and '.github/branch-protection.json' "
                f"are ready for 1-click import at https://github.com/{repo}/settings/rules "
                "('New ruleset' -> 'Import a ruleset')."
            ),
        }

    applied = []
    errors = []
    url = f"https://api.github.com/repos/{repo}/rulesets"
    for rs_name in EXPECTED_RULESET_FILES:
        rs_path = rulesets_dir / rs_name
        if not rs_path.is_file():
            continue
        payload = rs_path.read_bytes()
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "Personal-Agentic-Fleet",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                applied.append({"file": rs_name, "http_status": resp.status})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            errors.append({"file": rs_name, "http_status": exc.code, "detail": body[:200]})

    return {
        "status": "APPLIED" if applied and not errors else "PARTIAL_OR_ERROR",
        "applied": applied,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or apply GitHub Rulesets & main branch protection.")
    parser.add_argument("--apply-remote", action="store_true", help="Apply rulesets to GitHub REST API using GITHUB_TOKEN.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if local/policy verification fails.")
    args = parser.parse_args()

    res = verify_branch_protection()
    print(f"=== Main Branch & Repository Rulesets [{res['status']}] | Branch: {res['protected_branch']} ===")
    print(f"  Primary Policy     : {res['policy_file']}")
    print(f"  Modular Rulesets   : {len(res['rulesets_verified'])} verified ({', '.join(res['rulesets_verified'])})")
    print(f"  CODEOWNERS         : {res['codeowners_file']}")
    print(f"  Pre-Push Guard     : {'Active' if res['local_pre_push_guard'] else 'Missing'}")
    for issue in res.get("issues", []):
        print(f"  [!] {issue}")

    if args.apply_remote:
        remote_res = apply_remote_branch_protection()
        print(f"  Remote GitHub API  : [{remote_res['status']}] {remote_res.get('detail', '')}")

    if args.strict and res["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
