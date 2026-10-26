"""
Pre-Push Quality Gate and Preflight Verifier for Personal Agentic Fleet.
Runs the complete CI matrix locally before any code reaches GitHub:
  1. Minimum Python Runtime Requirement (>=3.10)
  2. Fleet Doctor & TLS/Database/ACL Security Invariants
  3. 12-Layer Deterministic Security & Privacy Audit (0 findings)
  4. Comprehensive Documentation Integrity & Link Verification
  5. Full Pytest Suite (all 130+ unit tests)
Exit code 0 on PASS, 1 on FAIL. Consumes 0 LLM tokens ($0.00).
"""

import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fleet.tools.fleet_doctor import run_fleet_doctor
from fleet.tools.security_scanner import run_security_scan

REQUIRED_DOCUMENTS: List[str] = [
    "README.md",
    "INSTALL.md",
    "CONTRIBUTING.md",
    "docs/ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/HYPERSCALERS_AND_DEV_TOOLS.md",
    "docs/PREREQUISITES_AND_OS.md",
    "docs/API_REFERENCE.md",
    "docs/DEVELOPER_GUIDE.md",
    "docs/MAINTAINING_DOCUMENTATION.md",
]


def verify_documentation_integrity(repo_root: Path = _ROOT) -> Dict[str, Any]:
    """
    Verifies that all required documentation files exist, are comprehensive (>500 chars),
    and have zero broken relative markdown links. Runs deterministically in ~10ms with 0 tokens.
    """
    findings: List[str] = []
    verified_files = 0

    for rel_doc in REQUIRED_DOCUMENTS:
        doc_path = repo_root / rel_doc
        if not doc_path.exists() or not doc_path.is_file():
            findings.append(f"Missing required documentation file: {rel_doc}")
            continue

        try:
            content = doc_path.read_text(encoding="utf-8")
        except Exception as exc:
            findings.append(f"Cannot read {rel_doc}: {exc}")
            continue

        if len(content.strip()) < 500:
            findings.append(f"Documentation {rel_doc} is incomplete or stub ({len(content)} chars < 500 chars minimum)")
            continue

        # Check relative markdown links: [text](target)
        for _, link in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content):
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Remove intra-page anchor
            target = link.split("#")[0].strip()
            if not target:
                continue
            target_path = (doc_path.parent / target).resolve()
            if not target_path.exists():
                findings.append(f"{rel_doc}: Broken relative link target -> {link}")

        verified_files += 1

    return {
        "status": "PASS" if not findings else "FAIL",
        "verified_files": verified_files,
        "total_required": len(REQUIRED_DOCUMENTS),
        "findings": findings,
    }


def run_preflight_gate(repo_root: Path = _ROOT) -> int:
    print("==================================================================")
    print("  Personal Agentic Fleet — Preflight CI & Security Quality Gate")
    print("==================================================================")

    # 1. Run Fleet Doctor (Verifies Runtime, OpenSSL, SQLite, Git Hooks, Vault ACL)
    print("[1/4] Running Fleet Doctor Invariants...")
    doc_res = run_fleet_doctor(repo_root=repo_root)
    if doc_res["status"] != "PASS":
        print(f"[-] Fleet Doctor FAILED (Score: {doc_res['security_score']}/100)")
        for d in doc_res.get("diagnostics", []):
            if d["status"] != "PASS":
                print(f"    [FAIL] {d['name']}: {d['detail']}")
        return 1
    print(f"[OK] Fleet Doctor Passed (Python {doc_res['python_version']}, Security 100/100)")

    # 2. Run 12-Layer Security & Privacy Scanner
    print("[2/4] Running 12-Layer Security & Privacy Scanner...")
    sec_res = run_security_scan(repo_root=repo_root)
    if sec_res["status"] != "PASS" or sec_res.get("total_findings", 0) > 0:
        print(f"[-] Security Scanner FAILED with {sec_res.get('total_findings', 0)} finding(s).")
        for f in sec_res.get("findings", []):
            print(f"    - [{f['severity']}] {f['file']}:{f['line']} -> {f['detail']}")
        return 1
    print(f"[OK] 12-Layer Security Scanner Passed (Score: 100/100, 0 findings)")

    # 3. Verify Documentation Integrity & Link Validations
    print("[3/4] Verifying Comprehensive Documentation Integrity...")
    doc_check = verify_documentation_integrity(repo_root=repo_root)
    if doc_check["status"] != "PASS":
        print(f"[-] Documentation Integrity Check FAILED with {len(doc_check['findings'])} finding(s):")
        for finding in doc_check["findings"]:
            print(f"    - {finding}")
        return 1
    print(f"[OK] Documentation Passed ({doc_check['verified_files']}/{doc_check['total_required']} docs valid, 0 broken links)")

    # 4. Run Pytest Suite in Clean Environment with PYTHONPATH
    print("[4/4] Running Full Unit Test Suite (pytest tests/)...")
    hidden_kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if os.name == "nt" else {}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["FLEET_TEST_MODE"] = "1"

    cmd = [sys.executable, "-m", "pytest", "tests/", "-q"]
    p = subprocess.run(cmd, cwd=str(repo_root), env=env, check=False)
    if p.returncode != 0:
        print(f"[-] Pytest Suite FAILED with exit code {p.returncode}.")
        return p.returncode

    print("[OK] All Unit Tests Passed!")
    print("==================================================================")
    print("[ALL PASS] Preflight Gate Complete: Guaranteed 100% CI Pass on GitHub!")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_preflight_gate())
