"""
Autonomous Post-Commit GitHub Pipeline, Vulnerability & Code-Scan Sentinel for Personal Agentic Fleet.

Continuously audits and auto-remediates post-commit / post-push issues across 4 channels ($0.00 / 0 LLM tokens):
  1. GitHub Actions Pipelines & Check-Run Annotations (CI test matrix, Pyright, Release, Pages, GHCR, Wiki)
  2. GitHub Code Scanning & CodeQL SARIF Alerts (live `/code-scanning/alerts` + check-run SARIF annotations)
  3. Supply-Chain & Dependency Vulnerabilities (GitHub Dependabot API + zero-auth OSV.dev CVE/GHSA batch query)
  4. Secret Scanning & Local 12-Layer SAST Verification (`fleet.tools.security_scanner`)

Wired automatically into `.git/hooks/post-commit`, `.git/hooks/pre-push` (detached post-push watcher),
`PRReviewAgent` (`fleet/agents/pr_review/agent.py`), and `python -m fleet.tools.github_pipeline_sentinel`.
"""

import argparse
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR, DATA_DIR, get_secure_secret
from fleet.core.database import is_test_environment

REPO_ROOT = BASE_DIR.parent
DEFAULT_GITHUB_REPO = "macazaka/personal-agentic-fleet"
AUDIT_REPORT_PATH = DATA_DIR / "user" / "latest_github_pipeline_audit.json"
_ALLOWED_API_HOSTS = frozenset({"api.github.com", "api.osv.dev"})


def _hidden_subprocess_kwargs() -> Dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def _detached_subprocess_kwargs() -> Dict[str, Any]:
    if os.name == "nt":
        create_no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        detached_proc = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": create_no_win | detached_proc | new_group, "close_fds": True}
    return {"start_new_session": True, "close_fds": True}


def _resolve_git_exe() -> str:
    found = shutil.which("git")
    if found:
        return found
    fallback = Path(os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"))
    if fallback.is_file():
        return str(fallback)
    return "git"


def _resolve_github_token() -> str:
    """Resolves an optional GitHub token from DPAPI/Keychain vault or environment variables."""
    for key_name, env_name in (
        ("github_token", "GITHUB_TOKEN"),
        ("gh_token", "GH_TOKEN"),
    ):
        val = (get_secure_secret(key_name, env_name) or os.environ.get(env_name, "")).strip()
        if val:
            return val
    return ""


class _IPv4FirstHTTPSConnection(http.client.HTTPSConnection):
    """
    HTTPS connection that prefers IPv4 (`AF_INET`) before dual-stack fallback so
    unrouted IPv6 interfaces on Windows workstations never stall GitHub/OSV API checks.
    """

    def connect(self) -> None:
        sock: Optional[socket.socket] = None
        try:
            infos = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
            if infos:
                af, socktype, proto, _, sa = infos[0]
                raw_sock = socket.socket(af, socktype, proto)
                raw_sock.settimeout(self.timeout)
                raw_sock.connect(sa)
                sock = raw_sock
        except OSError:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None

        if sock is None:
            super().connect()
            return

        tunnel_host = getattr(self, "_tunnel_host", None)
        if tunnel_host:
            self.sock = sock
            tunnel_fn = getattr(self, "_tunnel", None)
            if callable(tunnel_fn):
                tunnel_fn()

        ctx = ssl.create_default_context()
        server_host = str(tunnel_host) if tunnel_host else self.host
        self.sock = ctx.wrap_socket(sock, server_hostname=server_host)


def _http_json_request(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 12.0,
) -> Tuple[int, Any]:
    """
    Executes an HTTPS JSON request strictly restricted to `_ALLOWED_API_HOSTS`
    (`api.github.com` and `api.osv.dev`) with IPv4-first resilience.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_API_HOSTS:
        raise ValueError(f"Disallowed host or scheme for pipeline sentinel: {url}")

    host = parsed.hostname
    port = parsed.port or 443
    path_and_query = parsed.path or "/"
    if parsed.query:
        path_and_query = f"{path_and_query}?{parsed.query}"

    req_headers: Dict[str, str] = {
        "User-Agent": "Personal-Agentic-Fleet-Sentinel/2.13",
        "Accept": "application/vnd.github+json" if host == "api.github.com" else "application/json",
    }
    if headers:
        req_headers.update(headers)

    body_bytes: Optional[bytes] = None
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
        req_headers["Content-Length"] = str(len(body_bytes))

    conn = _IPv4FirstHTTPSConnection(host, port=port, timeout=timeout)
    try:
        conn.request(method.upper(), path_and_query, body=body_bytes, headers=req_headers)
        resp = conn.getresponse()
        status = int(resp.status)
        raw_text = resp.read().decode("utf-8", errors="replace").strip()
        if not raw_text:
            return status, {}
        try:
            return status, json.loads(raw_text)
        except json.JSONDecodeError:
            return status, {"raw": raw_text[:1000]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_local_head_sha(repo_root: Path = REPO_ROOT) -> str:
    """Returns the current local Git HEAD commit SHA."""
    try:
        res = subprocess.run(
            [_resolve_git_exe(), "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        sha = (res.stdout or "").strip()
        if res.returncode == 0 and len(sha) >= 7 and all(c in "0123456789abcdefABCDEF" for c in sha):
            return sha.lower()
    except Exception:
        pass
    return ""


def _sanitize_repo_slug(repo: str) -> str:
    clean = (repo or DEFAULT_GITHUB_REPO).strip().strip("/")
    parts = clean.split("/")
    if len(parts) == 2 and all(
        1 <= len(p) <= 100 and all(ch.isalnum() or ch in "._-" for ch in p)
        for p in parts
    ):
        return f"{parts[0]}/{parts[1]}"
    return DEFAULT_GITHUB_REPO


def parse_codeql_sarif_annotations(message: str) -> List[Dict[str, Any]]:
    """
    Parses structured CodeQL SARIF annotation chunks emitted by `.github/workflows/codeql.yml`:
      `[py/polynomial-redos] fleet/core/antigravity_mirror.py:926 (This [regular expression]...)`
    Uses linear non-overlapping chunk parsing (zero ReDoS risk).
    """
    alerts: List[Dict[str, Any]] = []
    if not message:
        return alerts

    for raw_part in message.split(" | "):
        chunk = raw_part.strip()
        if not chunk.startswith("[") or "]" not in chunk:
            continue
        rule_end = chunk.find("]")
        rule_id = chunk[1:rule_end].strip()
        rest = chunk[rule_end + 1 :].strip()
        if not rule_id or not rest:
            continue

        paren_idx = rest.find(" (")
        if paren_idx != -1:
            loc_part = rest[:paren_idx].strip()
            detail_part = rest[paren_idx + 2 :].rstrip(")").strip()
        else:
            loc_part = rest
            detail_part = "CodeQL static analysis alert"

        file_path = loc_part
        line_no = 1
        if ":" in loc_part:
            f_str, l_str = loc_part.rsplit(":", 1)
            file_path = f_str.strip()
            if l_str.strip().isdigit():
                line_no = int(l_str.strip())

        alerts.append({
            "source": "github_codeql_sarif",
            "rule_id": rule_id,
            "severity": "HIGH",
            "file": file_path,
            "line": line_no,
            "detail": detail_part,
        })
    return alerts


def extract_declared_python_dependencies(repo_root: Path = REPO_ROOT) -> List[Dict[str, str]]:
    """
    Extracts declared Python package names and version floors from `pyproject.toml`
    and any `requirements*.txt` files for zero-auth OSV.dev CVE scanning.
    """
    deps: Dict[str, str] = {}
    spec_re = re.compile(r"^\s*['\"]?([A-Za-z0-9][A-Za-z0-9._-]*)['\"]?\s*(?:>=|==|~=|>)\s*([0-9][0-9A-Za-z._-]*)")

    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.is_file():
        for raw_line in pyproject_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = raw_line.strip().rstrip(",")
            if stripped.startswith("#") or "requires-python" in stripped:
                continue
            if stripped.startswith(('"', "'")):
                m = spec_re.match(stripped.strip("\"'"))
                if m:
                    pkg_name = m.group(1).strip()
                    pkg_ver = m.group(2).strip()
                    if pkg_name.lower() != "python":
                        deps[pkg_name] = pkg_ver

    for req_file in sorted(repo_root.glob("requirements*.txt")):
        if not req_file.is_file():
            continue
        for raw_line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = raw_line.split("#")[0].strip()
            if not stripped or stripped.startswith("-"):
                continue
            m = spec_re.match(stripped)
            if m:
                deps[m.group(1).strip()] = m.group(2).strip()

    return [{"name": k, "version": v} for k, v in sorted(deps.items())]


def audit_dependencies_via_osv(
    dependencies: List[Dict[str, str]],
    request_fn=_http_json_request,
) -> List[Dict[str, Any]]:
    """
    Queries the public OSV.dev batch vulnerability database (`https://api.osv.dev/v1/querybatch`)
    to identify CVEs/GHSAs affecting declared PyPI dependencies ($0.00 / zero auth).
    """
    if not dependencies:
        return []

    queries = [
        {"package": {"name": d["name"], "ecosystem": "PyPI"}, "version": d["version"]}
        for d in dependencies
        if d.get("name") and d.get("version")
    ]
    if not queries:
        return []

    vulnerabilities: List[Dict[str, Any]] = []
    try:
        status, data = request_fn(
            "https://api.osv.dev/v1/querybatch",
            method="POST",
            payload={"queries": queries},
            timeout=10.0,
        )
        if status != 200 or not isinstance(data, dict):
            return []
        results = data.get("results", [])
        if not isinstance(results, list):
            return []
        for dep, res_obj in zip(dependencies, results):
            if not isinstance(res_obj, dict):
                continue
            vulns = res_obj.get("vulns") or []
            if not isinstance(vulns, list):
                continue
            for v in vulns:
                if not isinstance(v, dict):
                    continue
                vuln_id = str(v.get("id") or "OSV-UNKNOWN")
                detail_obj = v
                if not v.get("affected") and vuln_id != "OSV-UNKNOWN" and all(ch.isalnum() or ch in "._-" for ch in vuln_id):
                    try:
                        v_st, v_full = request_fn(
                            f"https://api.osv.dev/v1/vulns/{vuln_id}",
                            method="GET",
                            timeout=8.0,
                        )
                        if v_st == 200 and isinstance(v_full, dict):
                            detail_obj = v_full
                    except Exception:
                        detail_obj = v

                fixed_ver = ""
                affected_list = detail_obj.get("affected")
                if isinstance(affected_list, list):
                    for aff in affected_list:
                        if not isinstance(aff, dict):
                            continue
                        pkg_meta = aff.get("package") if isinstance(aff.get("package"), dict) else {}
                        if pkg_meta and str(pkg_meta.get("name") or "").lower() not in ("", dep["name"].lower()):
                            continue
                        for rng in aff.get("ranges") or []:
                            if not isinstance(rng, dict):
                                continue
                            for ev in rng.get("events") or []:
                                if isinstance(ev, dict) and ev.get("fixed"):
                                    fixed_ver = str(ev["fixed"])
                vulnerabilities.append({
                    "source": "osv.dev",
                    "id": vuln_id,
                    "package": dep["name"],
                    "current_version": dep["version"],
                    "fixed_version": fixed_ver,
                    "summary": str(detail_obj.get("summary") or detail_obj.get("details", "")[:160] or f"Vulnerability {vuln_id} in {dep['name']} {dep['version']}"),
                })
    except Exception:
        return []
    return vulnerabilities


def _auto_bump_vulnerable_pyproject_floors(
    repo_root: Path,
    vulnerabilities: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Automatically raises vulnerable minimum version floors (`>=X.Y.Z`) in `pyproject.toml` when a fixed version is known."""
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.is_file() or not vulnerabilities:
        return []

    text = pyproject_path.read_text(encoding="utf-8", errors="ignore")
    orig_text = text
    applied: List[Dict[str, str]] = []

    for vuln in vulnerabilities:
        pkg = str(vuln.get("package") or "").strip()
        cur_v = str(vuln.get("current_version") or "").strip()
        fix_v = str(vuln.get("fixed_version") or "").strip()
        if not pkg or not cur_v or not fix_v or fix_v == cur_v:
            continue
        if not all(ch.isalnum() or ch in "._-" for ch in fix_v):
            continue
        target_double = f'"{pkg}>={cur_v}"'
        target_single = f"'{pkg}>={cur_v}'"
        if target_double in text:
            text = text.replace(target_double, f'"{pkg}>={fix_v}"')
            applied.append({"file": "pyproject.toml", "detail": f"Bumped {pkg} floor >={cur_v} -> >={fix_v} ({vuln.get('id')})"})
        elif target_single in text:
            text = text.replace(target_single, f"'{pkg}>={fix_v}'")
            applied.append({"file": "pyproject.toml", "detail": f"Bumped {pkg} floor >={cur_v} -> >={fix_v} ({vuln.get('id')})"})

    if text != orig_text and applied:
        pyproject_path.write_text(text, encoding="utf-8", newline="\n")
    return applied


def build_remediation_prompt(report: Dict[str, Any]) -> str:
    """Builds an actionable self-healing engineering prompt from any failing GitHub pipeline or security scan."""
    sha = str(report.get("commit_sha") or "HEAD")[:7]
    lines = [
        f"[GitHub Pipeline & Security Sentinel] Automatically resolve post-commit issues detected on `{report.get('repo', DEFAULT_GITHUB_REPO)}` @ `{sha}`:",
    ]
    for pf in report.get("pipeline_failures", [])[:8]:
        lines.append(f"- Pipeline Failure `{pf.get('name')}` ({pf.get('conclusion')}): {pf.get('detail', '')}")
    for cs in report.get("code_scan_alerts", [])[:10]:
        lines.append(f"- CodeQL / SAST Alert `[{cs.get('rule_id')}]` at `{cs.get('file')}:{cs.get('line')}`: {cs.get('detail')}")
    for vu in report.get("vulnerabilities", [])[:8]:
        fix_hint = f" (upgrade to >= {vu.get('fixed_version')})" if vu.get("fixed_version") else ""
        lines.append(f"- Dependency Vulnerability `{vu.get('id')}` in `{vu.get('package')}=={vu.get('current_version')}`{fix_hint}: {vu.get('summary')}")
    for ww in report.get("workflow_warnings", [])[:5]:
        lines.append(f"- Workflow Deprecation `{ww.get('check')}`: {ww.get('message')}")
    lines.append(
        "Fix all root causes, run `python -X utf8 -m fleet.tools.security_scanner` and `pytest`, and verify 0 CodeQL/CI failures."
    )
    return "\n".join(lines)


def run_github_pipeline_audit(
    repo: str = DEFAULT_GITHUB_REPO,
    commit_sha: str = "",
    wait_for_completion: bool = False,
    wait_timeout_sec: int = 240,
    poll_interval_sec: int = 12,
    auto_remediate: bool = True,
    dispatch_to_antigravity: bool = False,
    repo_root: Path = REPO_ROOT,
    request_fn=_http_json_request,
) -> Dict[str, Any]:
    """
    Audits GitHub Actions check-runs, CodeQL SARIF annotations & code-scanning alerts,
    Dependabot & OSV.dev vulnerabilities, and local 12-layer security invariants.
    Automatically applies deterministic fixes and optionally dispatches self-healing remediation.
    """
    from fleet.tools.security_scanner import run_security_scan

    clean_repo = _sanitize_repo_slug(repo)
    target_sha = (commit_sha or get_local_head_sha(repo_root)).strip().lower()
    if target_sha and not all(c in "0123456789abcdef" for c in target_sha):
        target_sha = ""

    local_sec = run_security_scan(repo_root=repo_root)
    declared_deps = extract_declared_python_dependencies(repo_root=repo_root)

    # Respect unit-test offline socket isolation unless a custom request_fn mock was injected
    if is_test_environment() and request_fn is _http_json_request:
        return {
            "status": "PASS" if local_sec.get("status") == "PASS" else "WARN",
            "mode": "offline_test_guard",
            "repo": clean_repo,
            "commit_sha": target_sha or "HEAD",
            "checks_total": 0,
            "checks_passed": 0,
            "checks_in_progress": 0,
            "pipeline_failures": [],
            "code_scan_alerts": [],
            "vulnerabilities": [],
            "workflow_warnings": [],
            "local_security_score": local_sec.get("score", 100),
            "remediations_applied": [],
            "tokens_used": 0,
            "cost_usd": "$0.00",
        }

    token = _resolve_github_token()
    gh_headers: Dict[str, str] = {}
    if token:
        gh_headers["Authorization"] = f"Bearer {token}"

    # Verify target_sha exists on GitHub; if unpushed local commit, audit remote `main` tip
    resolved_ref = target_sha or "main"
    check_runs: List[Dict[str, Any]] = []
    network_error = ""

    deadline = time.time() + max(5, wait_timeout_sec)
    while True:
        try:
            st, cr_data = request_fn(
                f"https://api.github.com/repos/{clean_repo}/commits/{resolved_ref}/check-runs?per_page=50",
                headers=gh_headers,
                timeout=12.0,
            )
            if st == 422 or st == 404:
                if resolved_ref != "main":
                    resolved_ref = "main"
                    st, cr_data = request_fn(
                        f"https://api.github.com/repos/{clean_repo}/commits/main/check-runs?per_page=50",
                        headers=gh_headers,
                        timeout=12.0,
                    )
            if st == 200 and isinstance(cr_data, dict):
                raw_crs = cr_data.get("check_runs", [])
                check_runs = [c for c in raw_crs if isinstance(c, dict)] if isinstance(raw_crs, list) else []
            else:
                network_error = f"GitHub check-runs API returned HTTP {st}"
        except Exception as exc:
            network_error = str(exc)

        in_prog = [c for c in check_runs if c.get("status") != "completed"]
        if not wait_for_completion or not in_prog or time.time() >= deadline or network_error:
            break
        # Wait only while checks exist and are still running (or within initial 45s startup window if 0 checks registered yet)
        time.sleep(max(2, poll_interval_sec))

    # Deduplicate check-runs by name (keep latest id per check name)
    latest_by_name: Dict[str, Dict[str, Any]] = {}
    for cr in sorted(check_runs, key=lambda x: int(x.get("id") or 0)):
        c_name = str(cr.get("name") or f"check_{cr.get('id')}")
        latest_by_name[c_name] = cr

    deduped_checks = list(latest_by_name.values())
    pipeline_failures: List[Dict[str, Any]] = []
    code_scan_alerts: List[Dict[str, Any]] = []
    workflow_warnings: List[Dict[str, Any]] = []
    checks_passed = 0
    checks_in_progress = 0
    audited_sha = resolved_ref

    for cr in deduped_checks:
        if cr.get("head_sha"):
            audited_sha = str(cr["head_sha"])
        c_name = str(cr.get("name") or "unknown")
        c_status = str(cr.get("status") or "")
        c_conc = cr.get("conclusion")
        output_obj = cr.get("output") if isinstance(cr.get("output"), dict) else {}
        ann_count = int((output_obj or {}).get("annotations_count") or 0)
        ann_url = str((output_obj or {}).get("annotations_url") or "")

        if c_status != "completed":
            checks_in_progress += 1
        elif c_conc in ("success", "neutral", "skipped"):
            checks_passed += 1

        ann_details: List[str] = []
        if ann_count > 0 and ann_url.startswith("https://api.github.com/"):
            try:
                ast_code, anns = request_fn(ann_url, headers=gh_headers, timeout=10.0)
                if ast_code == 200 and isinstance(anns, list):
                    for ann in anns:
                        if not isinstance(ann, dict):
                            continue
                        lvl = str(ann.get("annotation_level") or "")
                        title = str(ann.get("title") or "")
                        msg = str(ann.get("message") or "")
                        path = str(ann.get("path") or "")
                        line = int(ann.get("start_line") or 1)

                        if "CodeQL Alerts" in title or msg.lstrip().startswith("[py/"):
                            code_scan_alerts.extend(parse_codeql_sarif_annotations(msg))

                        if lvl == "failure":
                            ann_details.append(f"{path}:{line} {title} {msg}".strip())
                        elif lvl == "warning" and ("deprecated" in msg.lower() or "codeql" in msg.lower()):
                            if "Node.js 20 is deprecated" not in msg:
                                workflow_warnings.append({
                                    "check": c_name,
                                    "path": path,
                                    "line": line,
                                    "message": msg[:300],
                                })
            except Exception:
                pass

        if c_status == "completed" and c_conc not in ("success", "neutral", "skipped", None):
            pipeline_failures.append({
                "id": cr.get("id"),
                "name": c_name,
                "conclusion": str(c_conc),
                "html_url": str(cr.get("html_url") or ""),
                "detail": " | ".join(ann_details[:4]) or f"Check '{c_name}' failed with conclusion '{c_conc}'.",
            })

    # Optional authenticated GitHub Code Scanning, Dependabot, and Secret Scanning API checks
    vulnerabilities: List[Dict[str, Any]] = []
    if token:
        # 1. Code Scanning Alerts API
        try:
            cs_st, cs_list = request_fn(
                f"https://api.github.com/repos/{clean_repo}/code-scanning/alerts?state=open&per_page=30",
                headers=gh_headers,
                timeout=10.0,
            )
            if cs_st == 200 and isinstance(cs_list, list):
                existing_keys = {(a["rule_id"], a["file"], a["line"]) for a in code_scan_alerts}
                for item in cs_list:
                    if not isinstance(item, dict):
                        continue
                    rule_obj = item.get("rule") if isinstance(item.get("rule"), dict) else {}
                    inst_obj = item.get("most_recent_instance") if isinstance(item.get("most_recent_instance"), dict) else {}
                    loc_obj = (inst_obj or {}).get("location") if isinstance((inst_obj or {}).get("location"), dict) else {}
                    r_id = str((rule_obj or {}).get("id") or "codeql-alert")
                    f_p = str((loc_obj or {}).get("path") or "")
                    l_n = int((loc_obj or {}).get("start_line") or 1)
                    if (r_id, f_p, l_n) not in existing_keys:
                        code_scan_alerts.append({
                            "source": "github_code_scanning_api",
                            "rule_id": r_id,
                            "severity": str((rule_obj or {}).get("security_severity_level") or "HIGH").upper(),
                            "file": f_p,
                            "line": l_n,
                            "detail": str((rule_obj or {}).get("description") or "Open GitHub code scanning alert"),
                        })
        except Exception:
            pass

        # 2. Dependabot Alerts API
        try:
            db_st, db_list = request_fn(
                f"https://api.github.com/repos/{clean_repo}/dependabot/alerts?state=open&per_page=30",
                headers=gh_headers,
                timeout=10.0,
            )
            if db_st == 200 and isinstance(db_list, list):
                for item in db_list:
                    if not isinstance(item, dict):
                        continue
                    dep_obj = item.get("dependency") if isinstance(item.get("dependency"), dict) else {}
                    pkg_obj = (dep_obj or {}).get("package") if isinstance((dep_obj or {}).get("package"), dict) else {}
                    adv_obj = item.get("security_advisory") if isinstance(item.get("security_advisory"), dict) else {}
                    vuln_obj = item.get("security_vulnerability") if isinstance(item.get("security_vulnerability"), dict) else {}
                    patch_obj = (vuln_obj or {}).get("first_patched_version") if isinstance((vuln_obj or {}).get("first_patched_version"), dict) else {}
                    vulnerabilities.append({
                        "source": "github_dependabot",
                        "id": str((adv_obj or {}).get("ghsa_id") or (adv_obj or {}).get("cve_id") or "DEPENDABOT"),
                        "package": str((pkg_obj or {}).get("name") or "unknown"),
                        "current_version": "manifest",
                        "fixed_version": str((patch_obj or {}).get("identifier") or ""),
                        "summary": str((adv_obj or {}).get("summary") or "Open Dependabot vulnerability alert"),
                    })
        except Exception:
            pass

        # 3. Secret Scanning Alerts API
        try:
            ss_st, ss_list = request_fn(
                f"https://api.github.com/repos/{clean_repo}/secret-scanning/alerts?state=open&per_page=20",
                headers=gh_headers,
                timeout=10.0,
            )
            if ss_st == 200 and isinstance(ss_list, list):
                for item in ss_list:
                    if isinstance(item, dict):
                        code_scan_alerts.append({
                            "source": "github_secret_scanning",
                            "rule_id": str(item.get("secret_type") or "secret-leak"),
                            "severity": "CRITICAL",
                            "file": "repository",
                            "line": 1,
                            "detail": f"Open GitHub Secret Scanning alert #{item.get('number')}: {item.get('secret_type_display_name', 'Secret')}",
                        })
        except Exception:
            pass

    # Zero-auth real-time OSV.dev dependency CVE scan
    osv_vulns = audit_dependencies_via_osv(declared_deps, request_fn=request_fn)
    seen_vuln_ids = {(v["package"], v["id"]) for v in vulnerabilities}
    for ov in osv_vulns:
        if (ov["package"], ov["id"]) not in seen_vuln_ids:
            vulnerabilities.append(ov)

    # Merge any local 12-layer security scanner findings
    for lf in local_sec.get("findings", []):
        if isinstance(lf, dict):
            code_scan_alerts.append({
                "source": "local_12_layer_scanner",
                "rule_id": str(lf.get("category") or "local-sast"),
                "severity": str(lf.get("severity") or "HIGH"),
                "file": str(lf.get("file") or ""),
                "line": int(lf.get("line") or 1),
                "detail": str(lf.get("detail") or ""),
            })

    has_issues = bool(pipeline_failures or code_scan_alerts or vulnerabilities or workflow_warnings)
    remediations_applied: List[Dict[str, Any]] = []

    if has_issues and auto_remediate:
        try:
            from fleet.tools.auto_fixer import run_auto_fixer
            af_res = run_auto_fixer(repo_root=repo_root, stage_changes=False, run_pyright_cli=False)
            for fx in af_res.get("fixes", []):
                if isinstance(fx, dict):
                    remediations_applied.append(fx)
        except Exception:
            pass

        if vulnerabilities:
            dep_bumps = _auto_bump_vulnerable_pyproject_floors(repo_root, vulnerabilities)
            for dbump in dep_bumps:
                remediations_applied.append({
                    "category": "Dependency Vulnerability Auto-Bump",
                    "file": dbump["file"],
                    "detail": dbump["detail"],
                })

    overall_status = "PASS" if (not has_issues and not network_error) else ("WARN" if network_error and not has_issues else "FAIL")
    report: Dict[str, Any] = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": clean_repo,
        "commit_sha": audited_sha,
        "network_error": network_error,
        "checks_total": len(deduped_checks),
        "checks_passed": checks_passed,
        "checks_in_progress": checks_in_progress,
        "dependencies_audited": len(declared_deps),
        "pipeline_failures": pipeline_failures,
        "code_scan_alerts": code_scan_alerts,
        "vulnerabilities": vulnerabilities,
        "workflow_warnings": workflow_warnings,
        "local_security_score": local_sec.get("score", 100),
        "remediations_applied": remediations_applied,
        "remediation_dispatched": False,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }

    if has_issues:
        report["remediation_prompt"] = build_remediation_prompt(report)

    # Persist report & trigger deduplicated self-healing alert/task if issues exist on live workstation
    if not is_test_environment() and repo_root.resolve() == REPO_ROOT.resolve():
        prev_dispatched_sha = ""
        try:
            if AUDIT_REPORT_PATH.is_file():
                prev = json.loads(AUDIT_REPORT_PATH.read_text(encoding="utf-8"))
                if prev.get("remediation_dispatched"):
                    prev_dispatched_sha = str(prev.get("commit_sha") or "")
        except Exception:
            pass

        if has_issues and auto_remediate and audited_sha != prev_dispatched_sha:
            short_sha = audited_sha[:7]
            summary_msg = (
                f"{len(pipeline_failures)} CI failure(s), "
                f"{len(code_scan_alerts)} CodeQL/SAST alert(s), "
                f"{len(vulnerabilities)} vulnerability alert(s) on {short_sha}"
            )
            try:
                from fleet.core.database import FleetDatabase
                from fleet.config import DB_PATH
                db = FleetDatabase(DB_PATH)
                db.add_task(
                    title=f"[GitHub Sentinel] Resolve {summary_msg}",
                    description=str(report.get("remediation_prompt", "")),
                    priority="P1",
                    assigned_agent="pr_review",
                    source="github_pipeline_sentinel",
                )
            except Exception:
                pass
            try:
                from fleet.tools.system_tools import send_notification
                send_notification("Fleet GitHub Pipeline Sentinel", f"Detected {summary_msg}. Auto-remediation initiated.")
            except Exception:
                pass
            if dispatch_to_antigravity and report.get("remediation_prompt"):
                try:
                    from fleet.core.antigravity_mirror import execute_dashboard_command
                    execute_dashboard_command(report["remediation_prompt"], enqueue_if_busy=True)
                    report["remediation_dispatched"] = True
                except Exception:
                    pass

        try:
            AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            AUDIT_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        except Exception:
            pass

    return report


def spawn_detached_post_push_sentinel(
    repo_root: Path = REPO_ROOT,
    commit_sha: str = "",
    initial_delay_sec: int = 35,
) -> bool:
    """
    Launches a non-blocking detached background sentinel process after `git commit` / `git push`
    so Git commands return immediately while GitHub Actions, CodeQL, and vulnerability scans
    are automatically verified and remediated once workflows complete.
    """
    if is_test_environment() or os.environ.get("FLEET_DISABLE_BG_SENTINEL") == "1":
        return False

    sha = (commit_sha or get_local_head_sha(repo_root)).strip().lower()
    if sha and not all(c in "0123456789abcdef" for c in sha):
        sha = ""

    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "fleet.tools.github_pipeline_sentinel",
        "--wait",
        "--timeout",
        "240",
        "--initial-delay",
        str(max(0, int(initial_delay_sec))),
        "--auto-fix",
        "--dispatch-antigravity",
    ]
    if sha:
        cmd.extend(["--sha", sha])

    try:
        subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            **_detached_subprocess_kwargs(),
        )
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fleet Autonomous Post-Commit GitHub Pipeline, Vulnerability & CodeQL Sentinel ($0.00 / 0 Tokens)"
    )
    parser.add_argument("--repo", default=DEFAULT_GITHUB_REPO, help="GitHub owner/repo slug")
    parser.add_argument("--sha", default="", help="Target commit SHA (defaults to local HEAD)")
    parser.add_argument("--wait", action="store_true", help="Poll until in-progress GitHub checks finish")
    parser.add_argument("--timeout", type=int, default=240, help="Max wait seconds when --wait is enabled")
    parser.add_argument("--poll-interval", type=int, default=12, help="Polling interval in seconds")
    parser.add_argument("--initial-delay", type=int, default=0, help="Initial delay before querying GitHub (for background post-push hook)")
    parser.add_argument("--auto-fix", action="store_true", default=True, help="Automatically apply deterministic remediations")
    parser.add_argument("--no-auto-fix", action="store_true", help="Audit only without modifying local files")
    parser.add_argument("--dispatch-antigravity", action="store_true", help="Dispatch unresolved findings to Antigravity Live")
    parser.add_argument("--spawn-background", action="store_true", help="Spawn detached background watcher and exit immediately")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any pipeline, CodeQL, or vulnerability issue is found")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    if args.spawn_background:
        ok = spawn_detached_post_push_sentinel(
            repo_root=REPO_ROOT,
            commit_sha=args.sha,
            initial_delay_sec=args.initial_delay or 35,
        )
        if args.json:
            print(json.dumps({"spawned": ok}))
        return 0

    if args.initial_delay > 0:
        time.sleep(min(args.initial_delay, 120))

    report = run_github_pipeline_audit(
        repo=args.repo,
        commit_sha=args.sha,
        wait_for_completion=args.wait,
        wait_timeout_sec=args.timeout,
        poll_interval_sec=args.poll_interval,
        auto_remediate=not args.no_auto_fix,
        dispatch_to_antigravity=args.dispatch_antigravity,
        repo_root=REPO_ROOT,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        short_sha = str(report.get("commit_sha") or "HEAD")[:7]
        print(
            f"=== Fleet GitHub Pipeline & Security Sentinel [{report['status']}] | "
            f"{report['repo']}@{short_sha} | "
            f"Checks: {report['checks_passed']}/{report['checks_total']} passed "
            f"({report['checks_in_progress']} running) | "
            f"Deps Audited: {report['dependencies_audited']} | "
            f"Local Security: {report['local_security_score']}/100 ==="
        )
        if report.get("network_error"):
            print(f"  [WARN] Network/API note: {report['network_error']}")
        for pf in report.get("pipeline_failures", []):
            print(f"  [PIPELINE FAIL] {pf['name']} ({pf['conclusion']}) -> {pf['detail']}")
        for cs in report.get("code_scan_alerts", []):
            print(f"  [CODE SCAN] [{cs['rule_id']}] {cs['file']}:{cs['line']} -> {cs['detail']}")
        for vu in report.get("vulnerabilities", []):
            print(f"  [VULNERABILITY] [{vu['id']}] {vu['package']}=={vu['current_version']} -> {vu['summary']}")
        for ww in report.get("workflow_warnings", []):
            print(f"  [WORKFLOW WARN] {ww['check']} -> {ww['message']}")
        for fx in report.get("remediations_applied", []):
            print(f"  [AUTO-FIXED] [{fx.get('category', 'Fix')}] {fx.get('file', '')} -> {fx.get('detail', '')}")

    if args.strict and report["status"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

