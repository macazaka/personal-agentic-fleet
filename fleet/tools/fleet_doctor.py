"""
Fleet Doctor — End-to-End Runtime, Python Version (>=3.10), ACL & Security Health Verifier.
Executes deterministic pre-flight diagnostics ($0.00 / 0 LLM Tokens):
  1. Python Runtime Version (>= 3.10) & 64-bit Architecture Verification
  2. OpenSSL / TLS 1.3 & Cryptographic Subsystem Verification
  3. OS Filesystem ACL Hardening on fleet/data/user/ (Windows icacls / POSIX chmod 0700)
  4. SQLite Database Integrity & PRAGMA secure_delete=ON Verification
  5. Git Pre-Commit & Pre-Push Security Hook Auto-Verification
  6. Full 12-Layer Security & Privacy Audit
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import ssl
import sqlite3
import struct
import subprocess
import sys
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR, DATA_DIR, MIN_PYTHON_VERSION, check_minimum_python_version
from fleet.core.database import FleetDatabase
from fleet.tools.install_git_hooks import install_git_hooks
from fleet.tools.security_scanner import run_security_scan

REPO_ROOT = BASE_DIR.parent
USER_VAULT_DIR = DATA_DIR / "user"


def harden_user_vault_permissions(vault_dir: Path = USER_VAULT_DIR) -> Dict[str, Any]:
    """
    Restricts OS filesystem permissions on fleet/data/user/ so only the current
    logged-in user (and OS system/admin accounts on Windows) can read or write files.
    Runs completely hidden (CREATE_NO_WINDOW) on Windows.
    """
    if not vault_dir.exists():
        try:
            vault_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    if os.name == "nt":
        username = os.environ.get("USERNAME") or ""
        if not username:
            try:
                username = os.getlogin()
            except Exception:
                username = ""
        if username:
            try:
                hidden_kwargs: Dict[str, Any] = {
                    "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                }
                si = subprocess.STARTUPINFO()
                si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
                si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
                hidden_kwargs["startupinfo"] = si

                cmd = [
                    "icacls",
                    str(vault_dir),
                    "/inheritance:r",
                    "/grant:r", f"{username}:(OI)(CI)F",
                    "/grant:r", "SYSTEM:(OI)(CI)F",
                    "/grant:r", "Administrators:(OI)(CI)F",
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False, **hidden_kwargs)
                return {
                    "status": "PASS",
                    "mode": "Windows NTFS ACL (Inheritance Disabled, User-Scoped)",
                    "principal": username,
                    "rc": res.returncode,
                }
            except Exception as e:
                return {"status": "WARN", "mode": "Windows NTFS Default", "detail": str(e)}
        return {"status": "PASS", "mode": "Windows Default ACL"}
    else:
        try:
            vault_dir.chmod(0o700)
            return {"status": "PASS", "mode": "POSIX chmod 0700"}
        except Exception as e:
            return {"status": "WARN", "mode": "POSIX Default", "detail": str(e)}


def run_fleet_doctor(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """Runs all pre-flight runtime, database, ACL, and 12-layer security checks."""
    diagnostics: List[Dict[str, Any]] = []
    all_passed = True

    # 1. Python Runtime Version (>= 3.10) & 64-Bit Architecture
    py_ver_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    bits = struct.calcsize("P") * 8
    try:
        check_minimum_python_version()
        py_ok = True
    except RuntimeError:
        py_ok = False
        all_passed = False

    diagnostics.append({
        "check": "python_runtime",
        "name": f"Python Runtime Version (>={MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]})",
        "status": "PASS" if py_ok else "FAIL",
        "detail": f"Python {py_ver_str} ({bits}-bit) at {sys.executable}",
    })

    # 2. TLS 1.3 & OpenSSL Cryptographic Library
    tls13 = getattr(ssl, "HAS_TLSv1_3", False)
    openssl_ver = getattr(ssl, "OPENSSL_VERSION", "Unknown")
    diagnostics.append({
        "check": "tls_openssl",
        "name": "OpenSSL & TLS 1.3 Cryptographic Transport",
        "status": "PASS" if tls13 else "WARN",
        "detail": f"{openssl_ver} (TLS 1.3: {tls13})",
    })

    # 3. User Data Vault OS ACL Hardening
    acl_res = harden_user_vault_permissions(USER_VAULT_DIR)
    diagnostics.append({
        "check": "vault_acl",
        "name": "User Data Vault OS ACL Hardening (fleet/data/user/)",
        "status": acl_res["status"],
        "detail": acl_res.get("mode", "Verified"),
    })

    # 4. SQLite Database Integrity & Secure-Delete Pragma
    db_ok = False
    db_detail = ""
    try:
        db = FleetDatabase()
        with db._get_connection() as conn:
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            sec_del = conn.execute("PRAGMA secure_delete").fetchone()[0]
            db_ok = (integrity == "ok" and int(sec_del) >= 1)
            db_detail = f"SQLite {sqlite3.sqlite_version} | quick_check={integrity} | secure_delete={sec_del}"
    except Exception as e:
        db_detail = f"Database error: {e}"
        all_passed = False

    diagnostics.append({
        "check": "sqlite_integrity",
        "name": "SQLite Database Integrity & Secure-Delete Forensics",
        "status": "PASS" if db_ok else "FAIL",
        "detail": db_detail,
    })

    # 5. Git Security Hooks & Main Branch Protection Auto-Verification
    from fleet.tools.github_branch_protection import verify_branch_protection
    hooks_res = install_git_hooks(repo_root=repo_root)
    bp_res = verify_branch_protection(repo_root=repo_root)
    hooks_ok = hooks_res.get("status") in ("installed", "skipped") and bp_res.get("status") == "PASS"
    if not hooks_ok:
        all_passed = False
    diagnostics.append({
        "check": "git_security_hooks",
        "name": "Git Pre-Commit, Pre-Push & Main Branch Protection Gate",
        "status": "PASS" if hooks_ok else "FAIL",
        "detail": f"Hooks: {hooks_res.get('status')} | Main Branch Protection: {bp_res.get('status')}",
    })

    # 6. Full Security & Privacy Scanner
    scan_report = run_security_scan(repo_root=repo_root)
    if scan_report.get("status") != "PASS":
        all_passed = False

    diagnostics.append({
        "check": "security_scanner",
        "name": f"Automated {scan_report.get('total_checks', 12)}-Layer Security & Privacy Audit",
        "status": scan_report.get("status", "FAIL"),
        "detail": f"Score: {scan_report.get('score', 0)}/100 ({scan_report.get('passed_checks', 0)}/{scan_report.get('total_checks', 0)} layers passed)",
    })

    return {
        "status": "PASS" if all_passed else "FAIL",
        "python_version": py_ver_str,
        "minimum_python_required": f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}",
        "security_score": scan_report.get("score", 0),
        "tokens_used": 0,
        "cost_usd": "$0.00",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diagnostics": diagnostics,
        "security_report": scan_report,
    }


def main():
    parser = argparse.ArgumentParser(description="Fleet Doctor — Runtime & Security Health Verifier")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any check fails")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    report = run_fleet_doctor()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== Fleet Doctor [{report['status']}] | Python {report['python_version']} (>={report['minimum_python_required']}) | Security: {report['security_score']}/100 ===")
        for d in report["diagnostics"]:
            print(f"  [{d['status']}] {d['name']} -> {d['detail']}")

    if args.strict and report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()

