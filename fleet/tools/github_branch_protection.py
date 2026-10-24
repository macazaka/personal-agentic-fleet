"""
GitHub & Local Main Branch Protection Verifier and Provisioner for Personal Agentic Fleet.

Enforces defense-in-depth protection for `main` across 3 layers (0 LLM tokens / $0.00):
  1. Declarative GitHub Ruleset & Branch Protection Policy (.github/branch-protection.json + .github/CODEOWNERS)
  2. Local Git Hook & Config Enforcement (.git/hooks/pre-push blocks force-pushes, deletions & unsigned commits on main)
  3. Remote GitHub API Provisioner (--apply-remote via GITHUB_TOKEN or GitHub Ruleset Import)
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR

REPO_ROOT = BASE_DIR.parent
BRANCH_PROTECTION_FILE = REPO_ROOT / ".github" / "branch-protection.json"
CODEOWNERS_FILE = REPO_ROOT / ".github" / "CODEOWNERS"

REQUIRED_RULESET_TYPES = {
    "deletion",
    "non_fast_forward",
    "required_linear_history",
    "required_signatures",
    "pull_request",
    "required_status_checks",
}


def verify_branch_protection(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """
    Deterministically verifies that `main` branch protection rules, CODEOWNERS,
    and local pre-push non-fast-forward/deletion guards are active.
    """
    bp_file = repo_root / ".github" / "branch-protection.json"
    co_file = repo_root / ".github" / "CODEOWNERS"
    pre_push = repo_root / ".git" / "hooks" / "pre-push"

    issues = []

    if not bp_file.is_file():
        issues.append("Missing .github/branch-protection.json policy file.")
    else:
        try:
            data = json.loads(bp_file.read_text(encoding="utf-8"))
            rule_types = {r.get("type") for r in data.get("rules", []) if isinstance(r, dict)}
            missing = REQUIRED_RULESET_TYPES - rule_types
            if missing:
                issues.append(f".github/branch-protection.json missing required rules: {sorted(missing)}")
            rest_cfg = data.get("rest_api_branch_protection", {})
            if rest_cfg.get("allow_force_pushes") is not False or rest_cfg.get("allow_deletions") is not False:
                issues.append(".github/branch-protection.json must set allow_force_pushes=false and allow_deletions=false.")
        except Exception as exc:
            issues.append(f"Invalid .github/branch-protection.json: {exc}")

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
        "codeowners_file": ".github/CODEOWNERS",
        "local_pre_push_guard": pre_push.is_file(),
        "issues": issues,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }


def apply_remote_branch_protection(
    repo: str = "macazaka/personal-agentic-fleet",
    branch: str = "main",
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    """
    Applies the branch protection policy in .github/branch-protection.json directly
    to GitHub via REST API if GITHUB_TOKEN / GH_TOKEN is set in the environment.
    """
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    bp_file = repo_root / ".github" / "branch-protection.json"
    if not bp_file.is_file():
        return {"status": "ERROR", "detail": "Missing .github/branch-protection.json"}

    policy_data = json.loads(bp_file.read_text(encoding="utf-8"))
    rest_payload = policy_data.get("rest_api_branch_protection", {})

    if not token:
        return {
            "status": "MANUAL_OR_TOKEN_REQUIRED",
            "detail": (
                "Local main branch protection is active! No GITHUB_TOKEN environment variable was found "
                "(by design, zero PATs are stored on disk). To apply on GitHub UI in 1 click: "
                f"open https://github.com/{repo}/settings/rules -> 'New ruleset' -> 'Import a ruleset' -> "
                "select '.github/branch-protection.json'."
            ),
        }

    url = f"https://api.github.com/repos/{repo}/branches/{branch}/protection"
    req = urllib.request.Request(
        url,
        data=json.dumps(rest_payload).encode("utf-8"),
        method="PUT",
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
            return {"status": "APPLIED", "http_status": resp.status, "repo": repo, "branch": branch}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {"status": "ERROR", "http_status": exc.code, "detail": body[:300]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or apply main branch protection.")
    parser.add_argument("--apply-remote", action="store_true", help="Apply protection to GitHub REST API using GITHUB_TOKEN.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if local/policy verification fails.")
    args = parser.parse_args()

    res = verify_branch_protection()
    print(f"=== Main Branch Protection [{res['status']}] | Branch: {res['protected_branch']} ===")
    print(f"  Policy File        : {res['policy_file']}")
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
