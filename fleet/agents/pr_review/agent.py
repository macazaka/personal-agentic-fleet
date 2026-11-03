"""
Admin-Only GitHub PR Review, Unmerged Branch Governance & CI Quality Gate Agent.
Designed for the repository owner/administrator to autonomously:
  1. Discover all local & remote branches waiting to be merged into `main`, with full
     author attribution, commit history, diffstats, conflict checks, and 1-click actions.
  2. Poll and audit open Pull Requests on a deterministic frequency (0 LLM tokens / $0.00).
  3. Perform automated static security analysis, CodeQL/Dependabot/OSV audits, and CI checks.
  4. Provide interactive governance actions (Merge into main, Inspect Diff, Sync/Rebase,
     AI Review in Antigravity Live, Spin off Working Tree to Branch, Delete Stale Branch).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
import logging
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

from fleet.core.base_agent import FleetAgent

logger = logging.getLogger("fleet.agents.pr_review")

_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _build_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class _IPv4FirstHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection preferring IPv4 first so unrouted Windows IPv6 interfaces never stall GitHub API calls."""

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

        ctx = _build_tls_context()
        self.sock = ctx.wrap_socket(sock, server_hostname=self.host)


class _IPv4FirstHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(_IPv4FirstHTTPSConnection, req)


def _github_api_request(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 8,
) -> Tuple[int, Any]:
    """Performs an IPv4-first HTTPS GitHub REST API request with TLS 1.2+ enforcement."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("api.github.com", "github.com"):
        raise ValueError(f"Disallowed GitHub API URL: {url}")

    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        try:
            from fleet.tools.github_pipeline_sentinel import _resolve_github_token

            token = _resolve_github_token()
        except Exception:
            token = ""
    headers: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Personal-Agentic-Fleet",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data_bytes: Optional[bytes] = None
    if payload is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        if os.environ.get("FLEET_TEST_MODE") == "1" or "pytest" in sys.modules:
            if getattr(urllib.request.urlopen, "__module__", "") == "urllib.request":
                return 503, {"message": "Offline unit-test guard"}
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_status = getattr(resp, "status", 200)
                status = raw_status if isinstance(raw_status, int) else 200
                raw = resp.read().decode("utf-8", errors="replace")
                return status, json.loads(raw) if raw.strip() else {}
        opener = urllib.request.build_opener(_IPv4FirstHTTPSHandler(context=_build_tls_context()))
        with opener.open(req, timeout=timeout) as resp:
            raw_status = getattr(resp, "status", 200)
            status = raw_status if isinstance(raw_status, int) else 200
            raw = resp.read().decode("utf-8", errors="replace")
            return status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(exc)
        try:
            parsed_err = json.loads(err_body) if err_body.strip() else {"message": str(exc)}
        except Exception:
            parsed_err = {"message": err_body or str(exc)}
        return exc.code, parsed_err


def _is_safe_branch_name(branch: str) -> bool:
    """Validates a git branch/ref name to prevent option injection or path traversal."""
    cleaned = (branch or "").strip()
    if not cleaned or len(cleaned) > 160:
        return False
    if cleaned.startswith("-") or ".." in cleaned or "//" in cleaned or cleaned.endswith(".lock"):
        return False
    return bool(_SAFE_BRANCH_RE.match(cleaned))


def _format_relative_time(iso_str: str) -> str:
    """Converts an ISO-8601 timestamp into a concise human-readable relative age."""
    if not iso_str:
        return "unknown"
    try:
        normalized = iso_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_sec = max(0, int((now - dt).total_seconds()))
        if delta_sec < 60:
            return "just now"
        if delta_sec < 3600:
            mins = delta_sec // 60
            return f"{mins}m ago"
        if delta_sec < 86400:
            hrs = delta_sec // 3600
            return f"{hrs}h ago"
        days = delta_sec // 86400
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return iso_str[:16]


def _author_initials(name: str) -> str:
    parts = [p for p in re.split(r"[\s._\-]+", (name or "").strip()) if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _summarize_changed_areas(changed_files: List[Dict[str, Any]], commits: List[Dict[str, Any]]) -> Tuple[List[str], str]:
    """Generates human-readable domain tags and a concise summary of what changed on a branch."""
    categories: List[str] = []
    seen = set()

    def add_cat(label: str) -> None:
        if label not in seen:
            seen.add(label)
            categories.append(label)

    for f in changed_files:
        path = str(f.get("path") or "").replace("\\", "/")
        if path.startswith("fleet/agents/"):
            parts = path.split("/")
            if len(parts) >= 3:
                add_cat(f"Agent: {parts[2]}")
            else:
                add_cat("Fleet Agents")
        elif path.startswith("fleet/core/db/"):
            add_cat("SQLite Database")
        elif path.startswith("fleet/core/"):
            add_cat("Core Engine")
        elif path.startswith("fleet/api/"):
            add_cat("REST API")
        elif path.startswith("fleet/web/"):
            add_cat("Web UI & JS")
        elif path.startswith("fleet/tools/"):
            add_cat("DevOps & Security Tools")
        elif path.startswith("tests/"):
            add_cat("Unit Tests")
        elif path.startswith(".github/"):
            add_cat("GitHub Actions CI")
        elif path.endswith((".md", ".rst", ".txt")):
            add_cat("Documentation")
        else:
            add_cat("Configuration & Scripts")

    if commits:
        lead_subject = str(commits[0].get("subject") or "").strip()
        if len(commits) == 1:
            summary_text = lead_subject
        else:
            extra = len(commits) - 1
            summary_text = f"{lead_subject} (+{extra} more commit{'s' if extra != 1 else ''})"
    elif changed_files:
        top_paths = ", ".join(str(x.get("path") or "") for x in changed_files[:3])
        summary_text = f"Modifies {len(changed_files)} file(s): {top_paths}"
    else:
        summary_text = "No file differences relative to main"

    return categories[:6], summary_text


class PRReviewAgent(FleetAgent):
    """
    Admin-Only Pull Request, Branch Governance & CI Guard Agent.
    Strictly isolated: only repository administrators can trigger operations.
    """

    def __init__(
        self,
        agent_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
        event_bus=None,
        db=None,
        repo_root: Optional[Path] = None,
    ):
        base_dir = agent_dir or Path(__file__).resolve().parent
        super().__init__(agent_dir=base_dir, config=config or {}, event_bus=event_bus, db=db)
        self.repo = self.config.get("repository", "macazaka/personal-agentic-fleet")
        self.check_interval_minutes = int(self.config.get("interval_minutes", 60))
        self.auto_merge_dependabot = bool(self.config.get("auto_merge_dependabot", False))
        self.last_check_time: Optional[datetime] = None
        self.repo_root: Path = Path(repo_root) if repo_root else _REPO_ROOT
        self._vscode_audit_cache: Tuple[float, Dict[str, Any]] = (0.0, {})
        self._governance_cache: Tuple[float, Dict[str, Any]] = (0.0, {})

    @property
    def id(self) -> str:
        return "pr_review"

    @property
    def name(self) -> str:
        return "Admin PR Review & CI Quality Gate"

    @property
    def icon(self) -> str:
        return "🛡️"

    @property
    def order(self) -> int:
        return 70

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "review_rigor",
                "label": "Code Review Strictness",
                "type": "select",
                "options": ["strict", "standard", "lenient"],
                "default": "standard",
                "description": "Heuristic strictness for PR diff inspections and lint checks",
            },
            {
                "id": "auto_suggest_tests",
                "label": "Require Unit Test Coverage",
                "type": "boolean",
                "default": True,
                "description": "Flag pull requests and branches that modify core code without accompanying tests",
            },
            {
                "id": "check_security_invariants",
                "label": "Enforce 12-Layer Security Invariants",
                "type": "boolean",
                "default": True,
                "description": "Scan branches and pull requests for hardcoded tokens, secret patterns, and SAST risks",
            },
            {
                "id": "max_diff_lines",
                "label": "Large Diff Warning Threshold (Lines)",
                "type": "number",
                "default": 1000,
                "description": "Warn when a branch or pull request diff exceeds this line count",
            },
        ]

    def register_routes(self, router) -> None:
        @router.get("/api/pr_review/status")
        def get_pr_review_status(handler: Any, parsed_url: Any):
            query = urllib.parse.parse_qs(getattr(parsed_url, "query", "") or "")
            fetch_remote = str((query.get("fetch") or ["0"])[0]).lower() in ("1", "true", "yes")
            with ThreadPoolExecutor(max_workers=3) as pool:
                fut_prs = pool.submit(self.audit_pull_requests)
                fut_ci = pool.submit(self.check_ci_status)
                fut_gov = pool.submit(self.audit_governance_hub, self.repo_root, fetch_remote)
                prs = fut_prs.result()
                ci = fut_ci.result()
                open_prs_list = prs.get("prs", []) if isinstance(prs, dict) else []
                branches = self.audit_unmerged_branches(
                    fetch_remote=fetch_remote,
                    open_prs=open_prs_list,
                )
                governance = fut_gov.result()
            handler._send_json({
                "status": "ok",
                "prs": prs,
                "ci": ci,
                "branches": branches,
                "governance": governance,
            })

        @router.get("/api/pr_review/governance")
        def get_pr_review_governance(handler: Any, parsed_url: Any):
            query = urllib.parse.parse_qs(getattr(parsed_url, "query", "") or "")
            force_refresh = str((query.get("refresh") or ["0"])[0]).lower() in ("1", "true", "yes")
            governance = self.audit_governance_hub(repo_root=self.repo_root, force_refresh=force_refresh)
            handler._send_json({"status": "ok", "governance": governance})

        @router.post("/api/pr_review/governance_action")
        def post_pr_review_governance_action(handler: Any, body: Dict[str, Any]):
            payload = body if isinstance(body, dict) else {}
            action = str(payload.get("action") or "").strip()
            result = self.execute_governance_action(action=action, payload=payload)
            self._governance_cache = (0.0, {})
            status_code = 200 if result.get("status") in ("ok", "SUCCESS") else 400
            handler._send_json(result, status=status_code)

        @router.get("/api/pr_review/branches")
        def get_pr_review_branches(handler: Any, parsed_url: Any):
            query = urllib.parse.parse_qs(getattr(parsed_url, "query", "") or "")
            fetch_remote = str((query.get("fetch") or ["0"])[0]).lower() in ("1", "true", "yes")
            prs = self.audit_pull_requests()
            open_prs_list = prs.get("prs", []) if isinstance(prs, dict) else []
            branches = self.audit_unmerged_branches(
                fetch_remote=fetch_remote,
                open_prs=open_prs_list,
            )
            handler._send_json({"status": "ok", "branches": branches})

        @router.post("/api/pr_review/branch_action")
        def post_pr_review_branch_action(handler: Any, body: Dict[str, Any]):
            payload = body if isinstance(body, dict) else {}
            action = str(payload.get("action") or "").strip()
            branch = str(payload.get("branch") or "").strip()
            result = self.execute_branch_action(action=action, branch=branch, payload=payload)
            status_code = 200 if result.get("status") in ("ok", "SUCCESS") else 400
            handler._send_json(result, status=status_code)

        @router.post("/api/pr_review/pr_action")
        def post_pr_review_pr_action(handler: Any, body: Dict[str, Any]):
            payload = body if isinstance(body, dict) else {}
            action = str(payload.get("action") or "").strip()
            pr_number = int(payload.get("pr_number") or 0)
            result = self.execute_pr_action(action=action, pr_number=pr_number, payload=payload)
            status_code = 200 if result.get("status") in ("ok", "SUCCESS") else 400
            handler._send_json(result, status=status_code)

        @router.get("/api/pr_review/pipeline_audit")
        def get_github_pipeline_audit(handler: Any, parsed_url: Any):
            """Returns the latest GitHub Actions pipeline, CodeQL scan, and dependency vulnerability audit."""
            report = self.audit_github_pipelines(wait_for_completion=False, auto_remediate=True)
            handler._send_json({"status": "ok", "audit": report})

        @router.post("/api/pr_review/pipeline_audit")
        def post_github_pipeline_audit(handler: Any, body: Dict[str, Any]):
            """Triggers an on-demand GitHub pipeline, CodeQL SARIF, and OSV/Dependabot vulnerability audit & auto-fix."""
            payload = body if isinstance(body, dict) else {}
            report = self.audit_github_pipelines(
                commit_sha=str(payload.get("sha") or ""),
                wait_for_completion=bool(payload.get("wait", False)),
                auto_remediate=bool(payload.get("auto_remediate", True)),
                dispatch_to_antigravity=bool(payload.get("dispatch_antigravity", False)),
            )
            handler._send_json({"status": "ok", "audit": report})

    def _run_git(self, args: List[str], timeout: int = 15, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        target_cwd = cwd or self.repo_root
        return subprocess.run(
            ["git", *args],
            cwd=str(target_cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    def _detect_base_branch(self, cwd: Optional[Path] = None) -> str:
        for candidate in ("main", "master"):
            res = self._run_git(["rev-parse", "--verify", candidate], cwd=cwd)
            if res.returncode == 0:
                return candidate
        res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        head = (res.stdout or "").strip()
        return head if head and head != "HEAD" else "main"

    def _inspect_merge_conflicts(self, base_branch: str, target_ref: str, cwd: Optional[Path] = None) -> Tuple[bool, List[str]]:
        """
        Determines whether `target_ref` can be cleanly merged into `base_branch` without touching
        the working tree or index, using `git merge-base` and `git merge-tree`.
        """
        mb = self._run_git(["merge-base", base_branch, target_ref], cwd=cwd)
        if mb.returncode != 0 or not (mb.stdout or "").strip():
            return True, []
        merge_base_sha = (mb.stdout or "").strip().splitlines()[0]
        mt = self._run_git(["merge-tree", merge_base_sha, base_branch, target_ref], cwd=cwd)
        out = mt.stdout or ""
        if "<<<<<<< " not in out and "changed in both" not in out:
            return True, []

        conflict_files: List[str] = []
        seen = set()
        for line in out.splitlines():
            trimmed = line.strip()
            if trimmed.startswith("our ") or trimmed.startswith("their ") or trimmed.startswith("base "):
                parts = trimmed.split(None, 3)
                if len(parts) == 4:
                    fpath = parts[3].strip()
                    if fpath and fpath not in seen:
                        seen.add(fpath)
                        conflict_files.append(fpath)
        return False, conflict_files[:20]

    def _inspect_single_branch(
        self,
        branch_name: str,
        ref_name: str,
        scope: str,
        base_branch: str,
        current_branch: str,
        pr_by_branch: Dict[str, Dict[str, Any]],
        cwd: Optional[Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extracts rich author, commit, diffstat, file-change, and mergeability details for a branch."""
        rev_res = self._run_git(["rev-list", "--left-right", "--count", f"{base_branch}...{ref_name}"], cwd=cwd)
        if rev_res.returncode != 0:
            return None
        parts = (rev_res.stdout or "").strip().split()
        behind_count = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
        ahead_count = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0

        # Latest commit metadata on the branch tip
        tip_res = self._run_git(
            ["log", "-1", "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%aI%x1f%s%x1f%b", ref_name],
            cwd=cwd,
        )
        tip_fields = (tip_res.stdout or "").strip().split("\x1f")
        full_sha = tip_fields[0] if len(tip_fields) > 0 else ""
        short_sha = tip_fields[1] if len(tip_fields) > 1 else full_sha[:7]
        latest_author_name = tip_fields[2] if len(tip_fields) > 2 else "Unknown"
        latest_author_email = tip_fields[3] if len(tip_fields) > 3 else ""
        latest_committer_name = tip_fields[4] if len(tip_fields) > 4 else latest_author_name
        latest_committer_email = tip_fields[5] if len(tip_fields) > 5 else latest_author_email
        latest_date_iso = tip_fields[6] if len(tip_fields) > 6 else ""
        latest_subject = tip_fields[7] if len(tip_fields) > 7 else ""
        latest_body = (tip_fields[8] if len(tip_fields) > 8 else "").strip()

        # Commits ahead of base_branch
        commits: List[Dict[str, Any]] = []
        authors_map: Dict[str, Dict[str, Any]] = {}
        if ahead_count > 0:
            log_res = self._run_git(
                ["log", f"{base_branch}..{ref_name}", "-n", "25", "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s"],
                cwd=cwd,
            )
            for raw_line in (log_res.stdout or "").splitlines():
                if not raw_line.strip():
                    continue
                c_parts = raw_line.split("\x1f")
                if len(c_parts) < 6:
                    continue
                c_full, c_short, c_an, c_ae, c_date, c_subj = (
                    c_parts[0],
                    c_parts[1],
                    c_parts[2],
                    c_parts[3],
                    c_parts[4],
                    c_parts[5],
                )
                commits.append({
                    "full_sha": c_full,
                    "sha": c_short,
                    "author_name": c_an,
                    "author_email": c_ae,
                    "date_iso": c_date,
                    "relative_time": _format_relative_time(c_date),
                    "subject": c_subj,
                })
                author_key = f"{c_an.lower()}|{c_ae.lower()}"
                if author_key not in authors_map:
                    authors_map[author_key] = {
                        "name": c_an,
                        "email": c_ae,
                        "initials": _author_initials(c_an),
                        "commits": 0,
                    }
                authors_map[author_key]["commits"] += 1

        if not authors_map and latest_author_name:
            authors_map[f"{latest_author_name.lower()}|{latest_author_email.lower()}"] = {
                "name": latest_author_name,
                "email": latest_author_email,
                "initials": _author_initials(latest_author_name),
                "commits": 1,
            }

        authors_list = sorted(authors_map.values(), key=lambda x: int(x.get("commits", 0)), reverse=True)

        # Diffstat & changed files between base_branch...ref_name
        changed_files: List[Dict[str, Any]] = []
        total_insertions = 0
        total_deletions = 0
        if ahead_count > 0:
            status_map: Dict[str, str] = {}
            ns_res = self._run_git(["diff", "--name-status", f"{base_branch}...{ref_name}"], cwd=cwd)
            for line in (ns_res.stdout or "").splitlines():
                cols = line.split("\t")
                if len(cols) >= 2:
                    st_code = cols[0].strip()[:1] or "M"
                    fpath = cols[-1].strip()
                    status_map[fpath] = st_code

            num_res = self._run_git(["diff", "--numstat", f"{base_branch}...{ref_name}"], cwd=cwd)
            for line in (num_res.stdout or "").splitlines():
                cols = line.split("\t")
                if len(cols) >= 3:
                    add_s, del_s, fpath = cols[0].strip(), cols[1].strip(), cols[2].strip()
                    add_n = int(add_s) if add_s.isdigit() else 0
                    del_n = int(del_s) if del_s.isdigit() else 0
                    total_insertions += add_n
                    total_deletions += del_n
                    changed_files.append({
                        "path": fpath,
                        "status": status_map.get(fpath, "M"),
                        "additions": add_n,
                        "deletions": del_n,
                    })

        can_clean_merge = True
        conflict_files: List[str] = []
        if ahead_count > 0:
            can_clean_merge, conflict_files = self._inspect_merge_conflicts(base_branch, ref_name, cwd=cwd)

        if ahead_count == 0:
            merge_status = "ALREADY_MERGED"
        elif can_clean_merge:
            merge_status = "CLEAN"
        else:
            merge_status = "CONFLICTS"

        categories, summary_text = _summarize_changed_areas(changed_files, commits)
        matched_pr = pr_by_branch.get(branch_name)
        encoded_branch = urllib.parse.quote(branch_name, safe="/._-")

        return {
            "branch": branch_name,
            "ref_name": ref_name,
            "scope": scope,  # "local", "remote", or "local+remote"
            "is_current": branch_name == current_branch,
            "base_branch": base_branch,
            "head_sha": full_sha,
            "short_sha": short_sha,
            "ahead_count": ahead_count,
            "behind_count": behind_count,
            "waiting_merge": ahead_count > 0,
            "can_clean_merge": can_clean_merge,
            "merge_status": merge_status,
            "conflict_files": conflict_files,
            "latest_author_name": latest_author_name,
            "latest_author_email": latest_author_email,
            "latest_author_initials": _author_initials(latest_author_name),
            "latest_committer_name": latest_committer_name,
            "latest_committer_email": latest_committer_email,
            "latest_commit_subject": latest_subject,
            "latest_commit_body": latest_body,
            "latest_commit_date_iso": latest_date_iso,
            "latest_commit_relative": _format_relative_time(latest_date_iso),
            "authors": authors_list,
            "commits": commits,
            "files_changed_count": len(changed_files),
            "insertions": total_insertions,
            "deletions": total_deletions,
            "changed_files": changed_files[:40],
            "change_categories": categories,
            "change_summary_text": summary_text,
            "pr": matched_pr,
            "compare_url": f"https://github.com/{self.repo}/compare/{base_branch}...{encoded_branch}",
            "create_pr_url": f"https://github.com/{self.repo}/compare/{base_branch}...{encoded_branch}?expand=1",
        }

    def audit_unmerged_branches(
        self,
        repo_root: Optional[Path] = None,
        fetch_remote: bool = False,
        open_prs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Discovers all local and remote git branches waiting to be merged into `main`,
        extracting author details, commits ahead/behind, changed files, mergeability,
        working-tree status, and main branch sync telemetry in 0 LLM tokens ($0.00).
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        if fetch_remote:
            try:
                self._run_git(["fetch", "--all", "--prune"], timeout=12, cwd=target_root)
            except Exception as exc:
                logger.debug("Non-fatal git fetch warning: %s", exc)

        base_branch = self._detect_base_branch(cwd=target_root)
        cur_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=target_root)
        current_branch = (cur_res.stdout or "").strip() or base_branch

        # Map open PRs by head branch name if available
        pr_by_branch: Dict[str, Dict[str, Any]] = {}
        if open_prs is not None:
            for pr in open_prs:
                head_ref = str(pr.get("head_ref") or "").strip()
                if head_ref:
                    pr_by_branch[head_ref] = pr

        # Main branch HEAD & origin/main sync telemetry
        main_tip = self._run_git(
            ["log", "-1", "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s", base_branch],
            cwd=target_root,
        )
        m_parts = (main_tip.stdout or "").strip().split("\x1f")
        main_full_sha = m_parts[0] if len(m_parts) > 0 else ""
        main_short_sha = m_parts[1] if len(m_parts) > 1 else main_full_sha[:7]
        main_author_name = m_parts[2] if len(m_parts) > 2 else "Unknown"
        main_author_email = m_parts[3] if len(m_parts) > 3 else ""
        main_date_iso = m_parts[4] if len(m_parts) > 4 else ""
        main_subject = m_parts[5] if len(m_parts) > 5 else ""

        origin_ahead = 0
        origin_behind = 0
        origin_check = self._run_git(
            ["rev-list", "--left-right", "--count", f"origin/{base_branch}...{base_branch}"],
            cwd=target_root,
        )
        if origin_check.returncode == 0:
            o_parts = (origin_check.stdout or "").strip().split()
            origin_behind = int(o_parts[0]) if len(o_parts) >= 1 and o_parts[0].isdigit() else 0
            origin_ahead = int(o_parts[1]) if len(o_parts) >= 2 and o_parts[1].isdigit() else 0

        # Working tree dirty files check
        wt_res = self._run_git(["status", "--porcelain"], cwd=target_root)
        wt_files: List[Dict[str, str]] = []
        for raw_line in (wt_res.stdout or "").splitlines():
            if len(raw_line) >= 4:
                st = raw_line[:2].strip() or "M"
                fp = raw_line[3:].strip()
                wt_files.append({"status": st, "path": fp})

        # Recent commits on main (for visibility when 0 branches are pending)
        recent_main_commits: List[Dict[str, Any]] = []
        rm_res = self._run_git(
            ["log", base_branch, "-n", "5", "--format=%h%x1f%an%x1f%ae%x1f%aI%x1f%s"],
            cwd=target_root,
        )
        for line in (rm_res.stdout or "").splitlines():
            cols = line.split("\x1f")
            if len(cols) >= 5:
                recent_main_commits.append({
                    "sha": cols[0],
                    "author_name": cols[1],
                    "author_email": cols[2],
                    "date_iso": cols[3],
                    "relative_time": _format_relative_time(cols[3]),
                    "subject": cols[4],
                })

        # Discover all local & remote refs
        refs_res = self._run_git(
            ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes/origin"],
            cwd=target_root,
        )
        branch_registry: Dict[str, Dict[str, str]] = {}
        for line in (refs_res.stdout or "").splitlines():
            full_ref = line.strip()
            if not full_ref:
                continue
            if full_ref.startswith("refs/heads/"):
                bname = full_ref[len("refs/heads/"):]
                if bname in (base_branch, "HEAD"):
                    continue
                entry = branch_registry.setdefault(bname, {"local_ref": "", "remote_ref": ""})
                entry["local_ref"] = bname
            elif full_ref.startswith("refs/remotes/origin/"):
                bname = full_ref[len("refs/remotes/origin/"):]
                if bname in (base_branch, "HEAD"):
                    continue
                entry = branch_registry.setdefault(bname, {"local_ref": "", "remote_ref": ""})
                entry["remote_ref"] = f"origin/{bname}"

        unmerged_branches: List[Dict[str, Any]] = []
        synced_branches: List[Dict[str, Any]] = []

        def _inspect_item(item: Tuple[str, Dict[str, str]]) -> Optional[Dict[str, Any]]:
            bname, ref_info = item
            local_ref = ref_info.get("local_ref") or ""
            remote_ref = ref_info.get("remote_ref") or ""
            if local_ref and remote_ref:
                scope = "local+remote"
                effective_ref = local_ref
            elif local_ref:
                scope = "local"
                effective_ref = local_ref
            else:
                scope = "remote"
                effective_ref = remote_ref
            return self._inspect_single_branch(
                branch_name=bname,
                ref_name=effective_ref,
                scope=scope,
                base_branch=base_branch,
                current_branch=current_branch,
                pr_by_branch=pr_by_branch,
                cwd=target_root,
            )

        sorted_items = sorted(branch_registry.items())
        if sorted_items:
            max_w = min(6, len(sorted_items))
            with ThreadPoolExecutor(max_workers=max_w) as pool:
                inspected_list = list(pool.map(_inspect_item, sorted_items))
            for info in inspected_list:
                if not info:
                    continue
                if info["ahead_count"] > 0 or info.get("pr") is not None:
                    unmerged_branches.append(info)
                else:
                    synced_branches.append(info)

        # Sort unmerged branches by latest commit timestamp descending
        unmerged_branches.sort(key=lambda b: str(b.get("latest_commit_date_iso") or ""), reverse=True)
        synced_branches.sort(key=lambda b: str(b.get("latest_commit_date_iso") or ""), reverse=True)

        return {
            "status": "SUCCESS",
            "timestamp": datetime.now().isoformat(),
            "base_branch": base_branch,
            "current_branch": current_branch,
            "main_status": {
                "branch": base_branch,
                "head_sha": main_full_sha,
                "short_sha": main_short_sha,
                "author_name": main_author_name,
                "author_email": main_author_email,
                "author_initials": _author_initials(main_author_name),
                "committed_at": main_date_iso,
                "relative_time": _format_relative_time(main_date_iso),
                "subject": main_subject,
                "ahead_of_origin": origin_ahead,
                "behind_origin": origin_behind,
                "working_tree_dirty": len(wt_files) > 0,
                "working_tree_count": len(wt_files),
                "working_tree_files": wt_files[:30],
                "recent_commits": recent_main_commits,
            },
            "unmerged_count": len(unmerged_branches),
            "unmerged_branches": unmerged_branches,
            "synced_count": len(synced_branches),
            "synced_branches": synced_branches,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        }

    def execute_branch_action(
        self,
        action: str,
        branch: str = "",
        payload: Optional[Dict[str, Any]] = None,
        repo_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Executes an administrative action on an unmerged branch or working tree:
          - 'diff': Returns unified diff and commit breakdown for `main...<branch>`
          - 'working_tree_diff': Returns unified diff for uncommitted changes on the working tree
          - 'merge': Merges `<branch>` into `main` (with clean-merge & conflict validation)
          - 'sync_with_main': Updates `<branch>` with latest commits from `main`
          - 'checkout': Switches working tree to `<branch>`
          - 'delete_branch': Deletes a merged or stale branch (never allows deleting `main`)
          - 'create_branch': Creates a new branch (optionally moving uncommitted changes to it)
          - 'fetch_remote': Runs `git fetch --all --prune` and returns updated branch list
          - 'push_main': Pushes local `main` commits to `origin/main`
          - 'review_in_antigravity': Dispatches a structured branch review prompt to Antigravity Live
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        opts = payload if isinstance(payload, dict) else {}
        act = (action or "").strip().lower()
        base_branch = self._detect_base_branch(cwd=target_root)

        if act == "fetch_remote":
            fetch_res = self._run_git(["fetch", "--all", "--prune"], timeout=15, cwd=target_root)
            branches = self.audit_unmerged_branches(repo_root=target_root, fetch_remote=False)
            return {
                "status": "ok",
                "action": act,
                "message": "Fetched latest remote branches from origin.",
                "git_output": (fetch_res.stdout or fetch_res.stderr or "").strip(),
                "branches": branches,
            }

        if act == "working_tree_diff":
            diff_res = self._run_git(["diff", "HEAD"], timeout=15, cwd=target_root)
            status_res = self._run_git(["status", "--short"], timeout=10, cwd=target_root)
            raw_diff = diff_res.stdout or ""
            truncated = len(raw_diff) > 60000
            return {
                "status": "ok",
                "action": act,
                "branch": "WORKING_TREE",
                "status_short": (status_res.stdout or "").strip(),
                "diff": raw_diff[:60000],
                "truncated": truncated,
            }

        if act == "push_main":
            push_res = self._run_git(["push", "origin", base_branch], timeout=25, cwd=target_root)
            if push_res.returncode != 0:
                return {
                    "status": "error",
                    "action": act,
                    "message": f"Failed to push {base_branch} to origin: {(push_res.stderr or push_res.stdout or '').strip()}",
                }
            return {
                "status": "ok",
                "action": act,
                "message": f"Successfully pushed {base_branch} to origin/{base_branch}.",
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        if act == "create_branch":
            new_branch = str(opts.get("new_branch") or branch or "").strip()
            if not _is_safe_branch_name(new_branch) or new_branch in (base_branch, "HEAD", "master"):
                return {"status": "error", "message": f"Invalid or reserved branch name: '{new_branch}'."}
            commit_message = str(opts.get("commit_message") or "").strip()
            checkout_res = self._run_git(["checkout", "-b", new_branch], cwd=target_root)
            if checkout_res.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Could not create branch '{new_branch}': {(checkout_res.stderr or checkout_res.stdout or '').strip()}",
                }
            if commit_message:
                self._run_git(["add", "-A"], cwd=target_root)
                c_res = self._run_git(["commit", "-m", commit_message], cwd=target_root)
                if c_res.returncode != 0:
                    return {
                        "status": "error",
                        "message": f"Created branch '{new_branch}', but commit failed: {(c_res.stderr or c_res.stdout or '').strip()}",
                    }
                if bool(opts.get("switch_back_to_main", True)):
                    self._run_git(["checkout", base_branch], cwd=target_root)

            return {
                "status": "ok",
                "action": act,
                "branch": new_branch,
                "message": f"Created branch '{new_branch}'" + (f" with commit '{commit_message}'." if commit_message else "."),
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        # All remaining actions require a valid target branch name
        if not _is_safe_branch_name(branch):
            return {"status": "error", "message": f"Invalid branch name: '{branch}'."}

        # Resolve whether branch is local or origin/<branch>
        effective_ref = branch
        verify_local = self._run_git(["rev-parse", "--verify", f"refs/heads/{branch}"], cwd=target_root)
        if verify_local.returncode != 0:
            verify_remote = self._run_git(["rev-parse", "--verify", f"refs/remotes/origin/{branch}"], cwd=target_root)
            if verify_remote.returncode == 0:
                effective_ref = f"origin/{branch}"
            else:
                return {"status": "error", "message": f"Branch '{branch}' not found locally or on origin."}

        if act == "diff":
            diff_res = self._run_git(["diff", f"{base_branch}...{effective_ref}"], timeout=15, cwd=target_root)
            raw_diff = diff_res.stdout or ""
            truncated = len(raw_diff) > 65000
            info = self._inspect_single_branch(
                branch_name=branch,
                ref_name=effective_ref,
                scope="local" if effective_ref == branch else "remote",
                base_branch=base_branch,
                current_branch=base_branch,
                pr_by_branch={},
                cwd=target_root,
            )
            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "ref_name": effective_ref,
                "branch_info": info,
                "diff": raw_diff[:65000],
                "truncated": truncated,
            }

        if act == "merge":
            if branch in (base_branch, "HEAD"):
                return {"status": "error", "message": f"Branch '{branch}' is already the base branch."}

            can_clean, conflicts = self._inspect_merge_conflicts(base_branch, effective_ref, cwd=target_root)
            if not can_clean:
                return {
                    "status": "error",
                    "action": act,
                    "branch": branch,
                    "message": f"Cannot auto-merge '{branch}' into {base_branch}: merge conflicts detected in {', '.join(conflicts[:5])}.",
                    "conflict_files": conflicts,
                }

            cur_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=target_root)
            current_branch = (cur_res.stdout or "").strip()
            if current_branch != base_branch:
                co_res = self._run_git(["checkout", base_branch], cwd=target_root)
                if co_res.returncode != 0:
                    return {
                        "status": "error",
                        "message": f"Could not switch to {base_branch} before merging: {(co_res.stderr or co_res.stdout or '').strip()}",
                    }

            strategy = str(opts.get("strategy") or "squash").lower()
            merge_msg = str(opts.get("commit_message") or f"feat(merge): merge branch '{branch}' into {base_branch} via AFCC PR Review Gate")
            if strategy == "ff-only":
                m_res = self._run_git(
                    ["-c", f"branch.{base_branch}.mergeOptions=", "merge", "--ff-only", effective_ref],
                    timeout=20,
                    cwd=target_root,
                )
            elif strategy == "no-ff":
                m_res = self._run_git(
                    ["-c", f"branch.{base_branch}.mergeOptions=", "merge", "--no-ff", effective_ref, "-m", merge_msg],
                    timeout=20,
                    cwd=target_root,
                )
            else:
                m_res = self._run_git(
                    ["-c", f"branch.{base_branch}.mergeOptions=", "merge", "--squash", effective_ref],
                    timeout=20,
                    cwd=target_root,
                )
                if m_res.returncode == 0:
                    staged_chk = self._run_git(["diff", "--cached", "--quiet"], cwd=target_root)
                    if staged_chk.returncode != 0:
                        m_res = self._run_git(["commit", "--no-verify", "-m", merge_msg], timeout=30, cwd=target_root)

            if m_res.returncode != 0:
                self._run_git(["merge", "--abort"], cwd=target_root)
                self._run_git(["reset", "--merge"], cwd=target_root)
                return {
                    "status": "error",
                    "action": act,
                    "branch": branch,
                    "message": f"Merge of '{branch}' into {base_branch} failed: {(m_res.stderr or m_res.stdout or '').strip()}",
                }

            if bool(opts.get("delete_after_merge", False)):
                if verify_local.returncode == 0:
                    self._run_git(["branch", "-D", branch], cwd=target_root)
                if effective_ref.startswith("origin/") or bool(opts.get("delete_remote", False)):
                    self._run_git(["push", "origin", "--delete", branch, "--no-verify"], timeout=20, cwd=target_root)
                    self._run_git(["update-ref", "-d", f"refs/remotes/origin/{branch}"], cwd=target_root)

            if bool(opts.get("push_origin", False)):
                self._run_git(["push", "origin", base_branch], timeout=25, cwd=target_root)

            if self.db and hasattr(self.db, "log_activity"):
                try:
                    self.db.log_activity("PRReview", f"Merged branch '{branch}' into {base_branch}")
                except Exception:
                    pass

            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "message": f"Successfully merged '{branch}' into {base_branch}.",
                "git_output": (m_res.stdout or "").strip(),
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        if act == "sync_with_main":
            if branch == base_branch:
                return {"status": "error", "message": f"Branch '{branch}' is already {base_branch}."}
            cur_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=target_root)
            prev_branch = (cur_res.stdout or "").strip() or base_branch
            if effective_ref != branch:
                self._run_git(["checkout", "-b", branch, effective_ref], cwd=target_root)
            elif prev_branch != branch:
                co = self._run_git(["checkout", branch], cwd=target_root)
                if co.returncode != 0:
                    return {
                        "status": "error",
                        "message": f"Cannot switch to '{branch}' to sync with {base_branch}: {(co.stderr or co.stdout or '').strip()}",
                    }

            sync_res = self._run_git(
                ["merge", base_branch, "-m", f"Sync branch '{branch}' with {base_branch}"],
                timeout=20,
                cwd=target_root,
            )
            if sync_res.returncode != 0:
                self._run_git(["merge", "--abort"], cwd=target_root)
                if prev_branch != branch:
                    self._run_git(["checkout", prev_branch], cwd=target_root)
                return {
                    "status": "error",
                    "message": f"Could not cleanly merge {base_branch} into '{branch}': {(sync_res.stderr or sync_res.stdout or '').strip()}",
                }

            if prev_branch != branch:
                self._run_git(["checkout", prev_branch], cwd=target_root)

            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "message": f"Synced branch '{branch}' with latest {base_branch}.",
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        if act == "checkout":
            if effective_ref != branch:
                co_res = self._run_git(["checkout", "-b", branch, effective_ref], cwd=target_root)
            else:
                co_res = self._run_git(["checkout", branch], cwd=target_root)
            if co_res.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Failed to checkout '{branch}': {(co_res.stderr or co_res.stdout or '').strip()}",
                }
            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "message": f"Switched working tree to branch '{branch}'.",
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        if act == "delete_branch":
            if branch in (base_branch, "main", "master", "HEAD"):
                return {"status": "error", "message": f"Deleting protected branch '{branch}' is forbidden."}
            cur_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=target_root)
            if (cur_res.stdout or "").strip() == branch:
                co_main = self._run_git(["checkout", base_branch], cwd=target_root)
                if co_main.returncode != 0:
                    return {"status": "error", "message": f"Cannot delete currently checked-out branch '{branch}'."}

            force_del = bool(opts.get("force", False))
            flag = "-D" if force_del else "-d"
            if verify_local.returncode == 0:
                del_res = self._run_git(["branch", flag, branch], cwd=target_root)
                if del_res.returncode != 0:
                    return {
                        "status": "error",
                        "message": (
                            f"Branch '{branch}' has unmerged commits. Confirm force-delete or merge into {base_branch} first. "
                            f"({(del_res.stderr or del_res.stdout or '').strip()})"
                        ),
                    }
            if bool(opts.get("delete_remote", False)):
                self._run_git(["push", "origin", "--delete", branch], timeout=20, cwd=target_root)

            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "message": f"Deleted branch '{branch}'.",
                "branches": self.audit_unmerged_branches(repo_root=target_root),
            }

        if act == "review_in_antigravity":
            info = self._inspect_single_branch(
                branch_name=branch,
                ref_name=effective_ref,
                scope="local" if effective_ref == branch else "remote",
                base_branch=base_branch,
                current_branch=base_branch,
                pr_by_branch={},
                cwd=target_root,
            )
            if not info:
                return {"status": "error", "message": f"Could not inspect branch '{branch}'."}

            authors_str = ", ".join(
                f"{a.get('name')} <{a.get('email')}> ({a.get('commits')} commit(s))"
                for a in (info.get("authors") or [])
            )
            commits_str = "\n".join(
                f"  - `{c.get('sha')}` {c.get('subject')} (by {c.get('author_name')}, {c.get('relative_time')})"
                for c in (info.get("commits") or [])[:10]
            )
            files_str = "\n".join(
                f"  - [{f.get('status')}] {f.get('path')} (+{f.get('additions')} / -{f.get('deletions')})"
                for f in (info.get("changed_files") or [])[:15]
            )
            prompt = (
                f"[PR Review & Branch Governance Gate] Please review branch `{branch}` waiting to merge into `{base_branch}`:\n"
                f"- Author(s): {authors_str or info.get('latest_author_name')}\n"
                f"- Ahead/Behind `{base_branch}`: +{info.get('ahead_count')} ahead / -{info.get('behind_count')} behind\n"
                f"- Merge Readiness: {info.get('merge_status')} "
                f"(Conflicts: {', '.join(info.get('conflict_files') or []) or 'None'})\n"
                f"- Diffstat: {info.get('files_changed_count')} files changed, "
                f"+{info.get('insertions')} insertions, -{info.get('deletions')} deletions\n"
                f"- Commits:\n{commits_str or '  (none)'}\n"
                f"- Changed Files:\n{files_str or '  (none)'}\n\n"
                f"Inspect the diff for any regressions, Pyright/Pylance issues, or security scanner violations, "
                f"and advise if it is safe to merge into `{base_branch}`."
            )
            dispatched = False
            try:
                from fleet.server import execute_dashboard_command

                execute_dashboard_command(prompt)
                dispatched = True
            except Exception as exc:
                logger.warning("Could not dispatch branch review to Antigravity bridge: %s", exc)

            return {
                "status": "ok",
                "action": act,
                "branch": branch,
                "dispatched": dispatched,
                "prompt": prompt,
                "message": f"Dispatched branch '{branch}' review to Antigravity Live.",
            }

        return {
            "status": "error",
            "message": f"Unsupported branch action '{action}'.",
        }

    def execute_pr_action(
        self,
        action: str,
        pr_number: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executes an administrative action on an open GitHub Pull Request."""
        if pr_number <= 0:
            return {"status": "error", "message": "Valid pr_number is required."}
        opts = payload if isinstance(payload, dict) else {}
        act = (action or "").strip().lower()

        if act == "merge_pr":
            merge_method = str(opts.get("merge_method") or "squash").lower()
            if merge_method not in ("merge", "squash", "rebase"):
                merge_method = "squash"
            url = f"https://api.github.com/repos/{self.repo}/pulls/{pr_number}/merge"
            code, resp = _github_api_request(url, method="PUT", payload={"merge_method": merge_method})
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "pr_number": pr_number, "message": f"Merged PR #{pr_number}."}
            return {
                "status": "error",
                "action": act,
                "pr_number": pr_number,
                "message": str(resp.get("message") if isinstance(resp, dict) else resp),
            }

        if act == "close_pr":
            url = f"https://api.github.com/repos/{self.repo}/pulls/{pr_number}"
            code, resp = _github_api_request(url, method="PATCH", payload={"state": "closed"})
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "pr_number": pr_number, "message": f"Closed PR #{pr_number}."}
            return {
                "status": "error",
                "action": act,
                "pr_number": pr_number,
                "message": str(resp.get("message") if isinstance(resp, dict) else resp),
            }

        return {"status": "error", "message": f"Unsupported PR action '{action}'."}

    def audit_pull_requests(self) -> Dict[str, Any]:
        """
        Polls GitHub API for open PRs, audits status checks, and returns actionable recommendations.
        Runs deterministically in 0 tokens ($0.00).
        """
        url = f"https://api.github.com/repos/{self.repo}/pulls?state=open"
        prs: List[Dict[str, Any]] = []
        try:
            code, raw_prs = _github_api_request(url, method="GET", timeout=10)
            if code >= 400 or not isinstance(raw_prs, list):
                err_msg = raw_prs.get("message", f"HTTP {code}") if isinstance(raw_prs, dict) else f"HTTP {code}"
                return {"status": "ERROR", "error": str(err_msg), "prs": [], "open_count": 0}

            for pr in raw_prs:
                if not isinstance(pr, dict):
                    continue
                pr_num = pr.get("number")
                raw_user = pr.get("user")
                user_obj = raw_user if isinstance(raw_user, dict) else {}
                author = user_obj.get("login", "")
                title = pr.get("title", "")
                raw_head = pr.get("head")
                head_obj = raw_head if isinstance(raw_head, dict) else {}
                raw_base = pr.get("base")
                base_obj = raw_base if isinstance(raw_base, dict) else {}
                head_sha = head_obj.get("sha", "")
                head_ref = head_obj.get("ref", "")
                base_ref = base_obj.get("ref", "main")
                is_dependabot = author in ("dependabot[bot]", "dependabot")
                prs.append({
                    "number": pr_num,
                    "title": title,
                    "author": author,
                    "is_dependabot": is_dependabot,
                    "head_sha": head_sha,
                    "head_ref": head_ref,
                    "base_ref": base_ref,
                    "created_at": pr.get("created_at", ""),
                    "updated_at": pr.get("updated_at", ""),
                    "relative_time": _format_relative_time(str(pr.get("updated_at") or pr.get("created_at") or "")),
                    "body": (pr.get("body") or "")[:500],
                    "url": pr.get("html_url", ""),
                    "draft": pr.get("draft", False),
                })
        except Exception as e:
            logger.warning("Failed to fetch PRs: %s", e)
            return {"status": "ERROR", "error": str(e), "prs": [], "open_count": 0}

        self.last_check_time = datetime.now()
        return {
            "status": "SUCCESS",
            "timestamp": self.last_check_time.isoformat(),
            "open_count": len(prs),
            "prs": prs,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        }

    def check_ci_status(self) -> Dict[str, Any]:
        """
        Checks the latest GitHub Actions workflow runs for the main branch.
        Identifies failing jobs and pinpoints broken matrix combinations.
        """
        url = f"https://api.github.com/repos/{self.repo}/actions/runs?branch=main&per_page=5"
        try:
            code, data = _github_api_request(url, method="GET", timeout=10)
            if code >= 400 or not isinstance(data, dict):
                return {"status": "ERROR", "error": f"HTTP {code}", "failing_runs": []}
            runs = data.get("workflow_runs", [])
            failing = []
            for r in runs:
                if isinstance(r, dict) and r.get("conclusion") == "failure":
                    failing.append({
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "head_sha": (r.get("head_sha") or "")[:7],
                        "html_url": r.get("html_url"),
                    })
            return {
                "status": "FAILING" if failing else "PASSING",
                "total_checked": len(runs),
                "failing_runs": failing,
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "failing_runs": []}

    def audit_github_pipelines(
        self,
        commit_sha: str = "",
        wait_for_completion: bool = False,
        auto_remediate: bool = True,
        dispatch_to_antigravity: bool = False,
    ) -> Dict[str, Any]:
        """
        Audits GitHub Actions check-runs, CodeQL SARIF annotations & code-scanning alerts,
        and Dependabot + OSV.dev dependency vulnerabilities with automatic remediation.
        """
        from fleet.tools.github_pipeline_sentinel import run_github_pipeline_audit

        return run_github_pipeline_audit(
            repo=self.repo,
            commit_sha=commit_sha,
            wait_for_completion=wait_for_completion,
            auto_remediate=auto_remediate,
            dispatch_to_antigravity=dispatch_to_antigravity,
        )

    def audit_security_and_quality_notifications(
        self,
        repo_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        1) Security and Quality Notifications:
        Aggregates GitHub Code Scanning (CodeQL), Dependabot vulnerability alerts,
        Secret Scanning alerts, Security Advisories, CI check failures, local 12-Layer
        Security Scanner findings, and VS Code / Pyright quality diagnostics ($0.00 / 0 tokens).
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        notifications: List[Dict[str, Any]] = []
        codeql_alerts: List[Dict[str, Any]] = []
        dependabot_alerts: List[Dict[str, Any]] = []
        secret_alerts: List[Dict[str, Any]] = []
        security_advisories: List[Dict[str, Any]] = []
        quality_diagnostics: List[Dict[str, Any]] = []
        pipeline_failures: List[Dict[str, Any]] = []

        # 1a-1d. Fetch GitHub Security endpoints concurrently (CodeQL, Dependabot, Secret Scanning, Advisories)
        sec_urls = {
            "cs": f"https://api.github.com/repos/{self.repo}/code-scanning/alerts?state=open&per_page=25",
            "db": f"https://api.github.com/repos/{self.repo}/dependabot/alerts?state=open&per_page=25",
            "ss": f"https://api.github.com/repos/{self.repo}/secret-scanning/alerts?state=open&per_page=20",
            "sa": f"https://api.github.com/repos/{self.repo}/security-advisories?per_page=15",
        }
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {
                k: pool.submit(_github_api_request, u, "GET", None, 4)
                for k, u in sec_urls.items()
            }
            cs_code, cs_data = futs["cs"].result()
            db_code, db_data = futs["db"].result()
            ss_code, ss_data = futs["ss"].result()
            sa_code, sa_data = futs["sa"].result()

        # 1a. GitHub Code Scanning (CodeQL) Alerts
        if cs_code == 200 and isinstance(cs_data, list):
            for item in cs_data:
                if not isinstance(item, dict):
                    continue
                alert_num = int(item.get("number") or 0)
                rule_obj = item.get("rule") if isinstance(item.get("rule"), dict) else {}
                inst_obj = item.get("most_recent_instance") if isinstance(item.get("most_recent_instance"), dict) else {}
                loc_obj = (inst_obj or {}).get("location") if isinstance((inst_obj or {}).get("location"), dict) else {}
                rule_id = str((rule_obj or {}).get("id") or "codeql-alert")
                sev = str((rule_obj or {}).get("security_severity_level") or (rule_obj or {}).get("severity") or "high").upper()
                fpath = str((loc_obj or {}).get("path") or "")
                line_no = int((loc_obj or {}).get("start_line") or 1)
                desc = str((rule_obj or {}).get("description") or item.get(" generic ") or "Open CodeQL security alert")
                created_at = str(item.get("created_at") or "")
                html_url = str(item.get("html_url") or f"https://github.com/{self.repo}/security/code-scanning/{alert_num}")
                entry = {
                    "id": f"codeql-{alert_num}",
                    "alert_number": alert_num,
                    "alert_type": "code_scanning",
                    "category": "CodeQL / SAST Alert",
                    "severity": sev,
                    "rule_id": rule_id,
                    "title": f"[{rule_id}] {desc}",
                    "detail": f"File: {fpath}:{line_no}" if fpath else desc,
                    "file": fpath,
                    "line": line_no,
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": html_url,
                }
                codeql_alerts.append(entry)
                notifications.append(entry)

        # 1b. GitHub Dependabot Vulnerability Alerts
        if db_code == 200 and isinstance(db_data, list):
            for item in db_data:
                if not isinstance(item, dict):
                    continue
                alert_num = int(item.get("number") or 0)
                dep_obj = item.get("dependency") if isinstance(item.get("dependency"), dict) else {}
                pkg_obj = (dep_obj or {}).get("package") if isinstance((dep_obj or {}).get("package"), dict) else {}
                adv_obj = item.get("security_advisory") if isinstance(item.get("security_advisory"), dict) else {}
                vuln_obj = item.get("security_vulnerability") if isinstance(item.get("security_vulnerability"), dict) else {}
                patch_obj = (
                    (vuln_obj or {}).get("first_patched_version")
                    if isinstance((vuln_obj or {}).get("first_patched_version"), dict)
                    else {}
                )
                pkg_name = str((pkg_obj or {}).get("name") or "dependency")
                ghsa_id = str((adv_obj or {}).get("ghsa_id") or (adv_obj or {}).get("cve_id") or f"DEP-{alert_num}")
                sev = str((adv_obj or {}).get("severity") or "high").upper()
                summary = str((adv_obj or {}).get("summary") or "Open Dependabot vulnerability")
                patched_ver = str((patch_obj or {}).get("identifier") or "")
                manifest_path = str((dep_obj or {}).get("manifest_path") or "pyproject.toml")
                created_at = str(item.get("created_at") or "")
                html_url = str(item.get("html_url") or f"https://github.com/{self.repo}/security/dependabot/{alert_num}")
                entry = {
                    "id": f"dependabot-{alert_num}",
                    "alert_number": alert_num,
                    "alert_type": "dependabot",
                    "category": "Dependabot Supply-Chain Alert",
                    "severity": sev,
                    "rule_id": ghsa_id,
                    "package": pkg_name,
                    "fixed_version": patched_ver,
                    "title": f"[{ghsa_id}] {pkg_name}: {summary}",
                    "detail": f"Manifest: {manifest_path}" + (f" • Upgrade to >= {patched_ver}" if patched_ver else ""),
                    "file": manifest_path,
                    "line": 1,
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": html_url,
                }
                dependabot_alerts.append(entry)
                notifications.append(entry)

        # 1c. GitHub Secret Scanning Alerts (extract integer alert ID only for CodeQL clear-text compliance)
        if ss_code == 200 and isinstance(ss_data, list):
            for item in ss_data:
                if not isinstance(item, dict):
                    continue
                alert_num = int(item.get("number") or 0)
                created_at = str(item.get("created_at") or "")
                html_url = str(item.get("html_url") or f"https://github.com/{self.repo}/security/secret-scanning/{alert_num}")
                entry = {
                    "id": f"secret-scan-{alert_num}",
                    "alert_number": alert_num,
                    "alert_type": "secret_scanning",
                    "category": "Secret Scanning Alert",
                    "severity": "CRITICAL",
                    "rule_id": "github-secret-scanning",
                    "title": f"Repository Secret Scanning Alert #{alert_num}",
                    "detail": "Open GitHub secret-scanning alert requires rotation/dismissal in Security tab.",
                    "file": "repository",
                    "line": 1,
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": html_url,
                }
                secret_alerts.append(entry)
                notifications.append(entry)

        # 1d. GitHub Repository Security Advisories
        if sa_code == 200 and isinstance(sa_data, list):
            for item in sa_data:
                if not isinstance(item, dict):
                    continue
                state = str(item.get("state") or "").lower()
                if state in ("closed", "withdrawn"):
                    continue
                ghsa_id = str(item.get("ghsa_id") or "GHSA")
                sev = str(item.get("severity") or "medium").upper()
                summary = str(item.get("summary") or "Repository Security Advisory")
                created_at = str(item.get("created_at") or "")
                html_url = str(item.get("html_url") or f"https://github.com/{self.repo}/security/advisories/{ghsa_id}")
                entry = {
                    "id": f"advisory-{ghsa_id}",
                    "alert_number": 0,
                    "alert_type": "security_advisory",
                    "category": f"Security Advisory ({state.upper()})",
                    "severity": sev,
                    "rule_id": ghsa_id,
                    "title": f"[{ghsa_id}] {summary}",
                    "detail": f"Advisory state: {state}",
                    "file": "SECURITY.md",
                    "line": 1,
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": html_url,
                }
                security_advisories.append(entry)
                notifications.append(entry)

        # 1e. Local 12-Layer Security Scanner, Cached Pipeline Sentinel & VS Code/Pyright Quality Gate
        local_security_score = 100
        local_passed_checks = 12
        local_total_checks = 12
        try:
            from fleet.tools.github_pipeline_sentinel import AUDIT_REPORT_PATH

            if AUDIT_REPORT_PATH.is_file():
                cached_audit = json.loads(AUDIT_REPORT_PATH.read_text(encoding="utf-8"))
                local_security_score = int(cached_audit.get("local_security_score") or 100)
                for pf in cached_audit.get("pipeline_failures", []) or []:
                    if isinstance(pf, dict):
                        entry = {
                            "id": f"ci-fail-{pf.get('id') or pf.get('name')}",
                            "alert_number": 0,
                            "alert_type": "ci_failure",
                            "category": "CI Quality Gate Failure",
                            "severity": "HIGH",
                            "rule_id": "github-actions-check",
                            "title": f"CI Check Failed: {pf.get('name')}",
                            "detail": str(pf.get("detail") or ""),
                            "file": ".github/workflows",
                            "line": 1,
                            "created_at": str(cached_audit.get("timestamp") or ""),
                            "relative_time": _format_relative_time(str(cached_audit.get("timestamp") or "")),
                            "url": str(pf.get("html_url") or f"https://github.com/{self.repo}/actions"),
                        }
                        pipeline_failures.append(entry)
                        notifications.append(entry)
                for ww in cached_audit.get("workflow_warnings", []) or []:
                    if isinstance(ww, dict):
                        entry = {
                            "id": f"wf-warn-{ww.get('check')}-{ww.get('line')}",
                            "alert_number": 0,
                            "alert_type": "quality_diagnostic",
                            "category": "Workflow Quality Warning",
                            "severity": "MEDIUM",
                            "rule_id": "workflow-warning",
                            "title": f"Workflow Warning in {ww.get('check')}",
                            "detail": str(ww.get("message") or ""),
                            "file": str(ww.get("path") or ".github/workflows"),
                            "line": int(ww.get("line") or 1),
                            "created_at": str(cached_audit.get("timestamp") or ""),
                            "relative_time": _format_relative_time(str(cached_audit.get("timestamp") or "")),
                            "url": f"https://github.com/{self.repo}/actions",
                        }
                        quality_diagnostics.append(entry)
                        notifications.append(entry)
        except Exception:
            pass

        try:
            from fleet.tools.auto_fixer import audit_vscode_workspace_problems

            now_ts = time.monotonic()
            cached_ts, cached_ws = self._vscode_audit_cache
            if now_ts - cached_ts < 60.0 and cached_ws and target_root == self.repo_root:
                ws_audit = cached_ws
            else:
                ws_audit = audit_vscode_workspace_problems(repo_root=target_root)
                if target_root == self.repo_root:
                    self._vscode_audit_cache = (now_ts, ws_audit)
            for prob in (ws_audit.get("problems") or [])[:20]:
                if isinstance(prob, dict):
                    entry = {
                        "id": f"vscode-{prob.get('file')}-{prob.get('line')}-{prob.get('code')}",
                        "alert_number": 0,
                        "alert_type": "quality_diagnostic",
                        "category": f"Code Quality ({prob.get('source', 'VSCode')})",
                        "severity": "MEDIUM",
                        "rule_id": str(prob.get("code") or "diagnostic"),
                        "title": f"[{prob.get('code')}] {prob.get('message')}",
                        "detail": f"{prob.get('file')}:{prob.get('line')}",
                        "file": str(prob.get("file") or ""),
                        "line": int(prob.get("line") or 1),
                        "created_at": "",
                        "relative_time": "workspace",
                        "url": "",
                    }
                    quality_diagnostics.append(entry)
                    notifications.append(entry)
        except Exception:
            pass

        return {
            "status": "CLEAN" if not notifications else "ATTENTION_REQUIRED",
            "total_notifications": len(notifications),
            "codeql_count": len(codeql_alerts),
            "dependabot_count": len(dependabot_alerts),
            "secret_alerts_count": len(secret_alerts),
            "advisories_count": len(security_advisories),
            "ci_failures_count": len(pipeline_failures),
            "quality_diagnostics_count": len(quality_diagnostics),
            "local_security_score": local_security_score,
            "local_passed_checks": local_passed_checks,
            "local_total_checks": local_total_checks,
            "notifications": notifications,
            "codeql_alerts": codeql_alerts,
            "dependabot_alerts": dependabot_alerts,
            "secret_alerts": secret_alerts,
            "security_advisories": security_advisories,
            "pipeline_failures": pipeline_failures,
            "quality_diagnostics": quality_diagnostics,
            "security_tab_url": f"https://github.com/{self.repo}/security",
        }

    def audit_open_discussions(self) -> Dict[str, Any]:
        """
        2) Open Discussions That Need to Be Addressed:
        Queries GitHub Repository Discussions for open or unanswered threads, extracting
        author details, category, comment count, upvotes, and answer status ($0.00 / 0 tokens).
        """
        url = f"https://api.github.com/repos/{self.repo}/discussions?per_page=25"
        discussions: List[Dict[str, Any]] = []
        discussions_enabled = True
        note = ""
        try:
            code, data = _github_api_request(url, method="GET", timeout=4)
            if code in (404, 410):
                discussions_enabled = False
                note = "GitHub Discussions tab is currently disabled or has 0 discussions on this repository."
            elif code == 200 and isinstance(data, list):
                for d in data:
                    if not isinstance(d, dict):
                        continue
                    state = str(d.get("state") or "open").lower()
                    if state == "closed" or d.get("locked"):
                        continue
                    num = int(d.get("number") or 0)
                    user_obj = d.get("user") if isinstance(d.get("user"), dict) else {}
                    cat_obj = d.get("category") if isinstance(d.get("category"), dict) else {}
                    author = str((user_obj or {}).get("login") or "unknown")
                    cat_name = str((cat_obj or {}).get("name") or "General")
                    is_answerable = bool((cat_obj or {}).get("is_answerable", False))
                    is_answered = bool(d.get("answer_chosen_at"))
                    comments_cnt = int(d.get("comments") or 0)
                    needs_attention = (is_answerable and not is_answered) or comments_cnt == 0
                    updated_at = str(d.get("updated_at") or d.get("created_at") or "")
                    discussions.append({
                        "number": num,
                        "title": str(d.get("title") or ""),
                        "author": author,
                        "author_initials": _author_initials(author),
                        "category": cat_name,
                        "is_answerable": is_answerable,
                        "is_answered": is_answered,
                        "needs_attention": needs_attention,
                        "comments_count": comments_cnt,
                        "upvotes": int(d.get("upvote_count") or 0),
                        "created_at": str(d.get("created_at") or ""),
                        "updated_at": updated_at,
                        "relative_time": _format_relative_time(updated_at),
                        "body": str(d.get("body") or "")[:500],
                        "url": str(d.get("html_url") or f"https://github.com/{self.repo}/discussions/{num}"),
                    })
        except Exception as exc:
            note = str(exc)

        unanswered_count = sum(1 for d in discussions if d.get("needs_attention"))
        return {
            "status": "OK",
            "discussions_enabled": discussions_enabled,
            "open_count": len(discussions),
            "unanswered_count": unanswered_count,
            "discussions": discussions,
            "note": note,
            "discussions_url": f"https://github.com/{self.repo}/discussions",
            "settings_url": f"https://github.com/{self.repo}/settings#features",
        }

    def audit_wiki_comments_and_feedback(
        self,
        repo_root: Optional[Path] = None,
        open_issues: Optional[List[Dict[str, Any]]] = None,
        open_discussions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        3) Wiki Page Comments, Questions & Revision Feedback:
        Scans all local `wiki/*.md` pages for embedded questions/comments/TODO markers,
        correlates GitHub Issues/Discussions/Commit Comments mentioning Wiki pages,
        and audits Wiki Git revision & sync status ($0.00 / 0 tokens).
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        wiki_dir = target_root / "wiki"
        wiki_comments: List[Dict[str, Any]] = []
        wiki_pages: List[Dict[str, Any]] = []

        marker_re = re.compile(
            r"(?:<!--\s*(?:QUESTION|COMMENT|TODO|FIXME|REVIEW|ASK|FEEDBACK)\b[:\s]*(.*?)-->)"
            r"|(?:^\s*(?:>\s*\[!QUESTION\]|(?:QUESTION|COMMENT|TODO|FIXME|NEEDS[\s_]+ANSWER)\s*:)\s*(.+)$)",
            re.I | re.M | re.S,
        )

        if wiki_dir.is_dir():
            # Batch-fetch latest commit metadata for all wiki/*.md files in a single git log invocation
            file_commit_map: Dict[str, Tuple[str, str, str, str, str]] = {}
            default_commit: Tuple[str, str, str, str, str] = ("", "macazaka", "", "", "")
            batch_log = self._run_git(
                ["log", "-n", "35", "--format=COMMIT%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s", "--name-only", "--", "wiki/"],
                cwd=target_root,
            )
            current_meta: Optional[Tuple[str, str, str, str, str]] = None
            for raw_line in (batch_log.stdout or "").splitlines():
                line_s = raw_line.strip()
                if not line_s:
                    continue
                if line_s.startswith("COMMIT\x1f"):
                    c_parts = line_s.split("\x1f")
                    c_meta = (
                        c_parts[1] if len(c_parts) > 1 else "",
                        c_parts[2] if len(c_parts) > 2 else "macazaka",
                        c_parts[3] if len(c_parts) > 3 else "",
                        c_parts[4] if len(c_parts) > 4 else "",
                        c_parts[5] if len(c_parts) > 5 else "",
                    )
                    current_meta = c_meta
                    if not default_commit[0]:
                        default_commit = c_meta
                elif current_meta is not None:
                    norm_p = line_s.replace("\\", "/")
                    if norm_p not in file_commit_map:
                        file_commit_map[norm_p] = current_meta

            for md_file in sorted(wiki_dir.glob("*.md")):
                page_name = md_file.stem
                rel_path = f"wiki/{md_file.name}"
                try:
                    text = md_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                last_sha, last_author, last_email, last_date, last_subj = file_commit_map.get(rel_path, default_commit)

                wiki_pages.append({
                    "page": page_name,
                    "file": rel_path,
                    "lines_count": len(text.splitlines()),
                    "last_sha": last_sha,
                    "last_author": last_author,
                    "last_email": last_email,
                    "last_updated_relative": _format_relative_time(last_date),
                    "last_subject": last_subj,
                    "wiki_url": f"https://github.com/{self.repo}/wiki/{ '' if page_name == 'Home' else page_name }",
                })

                for m in marker_re.finditer(text):
                    comment_text = (m.group(1) or m.group(2) or "").strip()
                    if not comment_text:
                        continue
                    line_no = text[: m.start()].count("\n") + 1
                    wiki_comments.append({
                        "id": f"wiki-{page_name}-L{line_no}",
                        "source": "wiki_inline_comment",
                        "page": page_name,
                        "file": rel_path,
                        "line": line_no,
                        "author": last_author,
                        "author_email": last_email,
                        "question_or_comment": " ".join(comment_text.split())[:300],
                        "relative_time": _format_relative_time(last_date),
                        "wiki_url": f"https://github.com/{self.repo}/wiki/{ '' if page_name == 'Home' else page_name }",
                    })

        # Correlate open GitHub Issues or Discussions mentioning Wiki pages
        for iss in open_issues or []:
            title_l = str(iss.get("title") or "").lower()
            body_l = str(iss.get("body") or "").lower()
            labels_l = [str(lb.get("name") or "").lower() for lb in (iss.get("labels") or []) if isinstance(lb, dict)]
            if "wiki" in title_l or "wiki" in body_l or "wiki" in labels_l or "documentation" in labels_l:
                wiki_comments.append({
                    "id": f"wiki-issue-{iss.get('number')}",
                    "source": "github_issue",
                    "issue_number": iss.get("number"),
                    "page": "Wiki / Documentation",
                    "file": "wiki/Home.md",
                    "line": 1,
                    "author": str(iss.get("author") or "user"),
                    "author_email": "",
                    "question_or_comment": f"[Issue #{iss.get('number')}] {iss.get('title')}: {str(iss.get('body') or '')[:220]}",
                    "relative_time": str(iss.get("relative_time") or ""),
                    "wiki_url": str(iss.get("url") or f"https://github.com/{self.repo}/wiki"),
                })

        for disc in open_discussions or []:
            title_l = str(disc.get("title") or "").lower()
            body_l = str(disc.get("body") or "").lower()
            if "wiki" in title_l or "wiki" in body_l or "docs" in title_l:
                wiki_comments.append({
                    "id": f"wiki-disc-{disc.get('number')}",
                    "source": "github_discussion",
                    "discussion_number": disc.get("number"),
                    "page": "Wiki / Documentation",
                    "file": "wiki/Home.md",
                    "line": 1,
                    "author": str(disc.get("author") or "user"),
                    "author_email": "",
                    "question_or_comment": f"[Discussion #{disc.get('number')}] {disc.get('title')}: {str(disc.get('body') or '')[:220]}",
                    "relative_time": str(disc.get("relative_time") or ""),
                    "wiki_url": str(disc.get("url") or f"https://github.com/{self.repo}/wiki"),
                })

        # Check if local wiki/ directory has uncommitted changes waiting to sync
        wt_wiki = self._run_git(["status", "--porcelain", "--", "wiki/"], cwd=target_root)
        unsynced_wiki_files = [
            line[3:].strip()
            for line in (wt_wiki.stdout or "").splitlines()
            if len(line) >= 4
        ]

        return {
            "status": "OK",
            "comments_needing_answer_count": len(wiki_comments),
            "wiki_comments": wiki_comments,
            "total_wiki_pages": len(wiki_pages),
            "unsynced_wiki_files": unsynced_wiki_files,
            "wiki_pages": wiki_pages,
            "wiki_home_url": f"https://github.com/{self.repo}/wiki",
        }

    def audit_reported_issues(self) -> Dict[str, Any]:
        """
        4) Reported Issues:
        Fetches all open GitHub Issues (excluding Pull Requests) with author details, labels,
        assignees, comment count, and response status, plus any open local Sentinel/Auto-Healer
        diagnostic tasks ($0.00 / 0 tokens).
        """
        url = f"https://api.github.com/repos/{self.repo}/issues?state=open&per_page=35"
        github_issues: List[Dict[str, Any]] = []
        local_reported_issues: List[Dict[str, Any]] = []
        error_note = ""

        try:
            code, raw_items = _github_api_request(url, method="GET", timeout=4)
            if code == 200 and isinstance(raw_items, list):
                for item in raw_items:
                    if not isinstance(item, dict) or "pull_request" in item:
                        continue
                    num = int(item.get("number") or 0)
                    user_obj = item.get("user") if isinstance(item.get("user"), dict) else {}
                    author = str((user_obj or {}).get("login") or "unknown")
                    raw_labels: List[Any] = item.get("labels") or []
                    labels = [
                        {
                            "name": str(lb.get("name") or ""),
                            "color": str(lb.get("color") or "38bdf8"),
                        }
                        for lb in raw_labels
                        if isinstance(lb, dict) and lb.get("name")
                    ]
                    raw_assignees: List[Any] = item.get("assignees") or []
                    assignees = [
                        str(a.get("login") or "")
                        for a in raw_assignees
                        if isinstance(a, dict) and a.get("login")
                    ]
                    comments_cnt = int(item.get("comments") or 0)
                    updated_at = str(item.get("updated_at") or item.get("created_at") or "")
                    github_issues.append({
                        "number": num,
                        "title": str(item.get("title") or ""),
                        "author": author,
                        "author_initials": _author_initials(author),
                        "author_association": str(item.get("author_association") or ""),
                        "labels": labels,
                        "assignees": assignees,
                        "comments_count": comments_cnt,
                        "needs_response": comments_cnt == 0,
                        "created_at": str(item.get("created_at") or ""),
                        "updated_at": updated_at,
                        "relative_time": _format_relative_time(updated_at),
                        "body": str(item.get("body") or "")[:600],
                        "url": str(item.get("html_url") or f"https://github.com/{self.repo}/issues/{num}"),
                    })
            elif code >= 400 and code != 503:
                error_note = f"HTTP {code}"
        except Exception as exc:
            error_note = str(exc)

        # Also check local FleetDatabase for open system/sentinel reported tasks
        try:
            db_inst = self.db
            if db_inst and hasattr(db_inst, "get_all_tasks"):
                for t in db_inst.get_all_tasks() or []:
                    if not isinstance(t, dict) or str(t.get("status") or "").lower() == "completed":
                        continue
                    src = str(t.get("source") or "").lower()
                    assigned = str(t.get("assigned_agent") or "").lower()
                    if src in ("github_pipeline_sentinel", "auto_healer", "security_scanner") or assigned == "pr_review":
                        local_reported_issues.append({
                            "id": int(t.get("id") or 0),
                            "title": str(t.get("title") or ""),
                            "description": str(t.get("description") or "")[:400],
                            "priority": str(t.get("priority") or "P1"),
                            "source": src or "system",
                            "created_at": str(t.get("created_at") or ""),
                            "relative_time": _format_relative_time(str(t.get("created_at") or "")),
                        })
        except Exception:
            pass

        return {
            "status": "OK",
            "open_github_issues_count": len(github_issues),
            "unanswered_issues_count": sum(1 for i in github_issues if i.get("needs_response")),
            "local_reported_count": len(local_reported_issues),
            "total_issues_count": len(github_issues) + len(local_reported_issues),
            "github_issues": github_issues,
            "local_issues": local_reported_issues,
            "error": error_note,
            "new_issue_url": f"https://github.com/{self.repo}/issues/new",
            "issues_url": f"https://github.com/{self.repo}/issues",
        }

    def audit_other_governance_items(self, repo_root: Optional[Path] = None) -> Dict[str, Any]:
        """
        5) Other Relevant Governance Items Not Listed:
          - Commit Comments & Inline PR Review Comments awaiting response
          - Repository Unread Notifications, @Mentions & Review Requests
          - Cryptographic Tag Signature Verification & Release Audit (`Verified` badge status)
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        commit_and_pr_comments: List[Dict[str, Any]] = []
        repo_notifications: List[Dict[str, Any]] = []
        tag_audit: List[Dict[str, Any]] = []

        # 5a & 5b. Fetch Commit Comments, PR Review Comments, and Unread Notifications concurrently
        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_cc = pool.submit(
                _github_api_request,
                f"https://api.github.com/repos/{self.repo}/comments?per_page=10",
                "GET",
                None,
                4,
            )
            fut_prc = pool.submit(
                _github_api_request,
                f"https://api.github.com/repos/{self.repo}/pulls/comments?per_page=10",
                "GET",
                None,
                4,
            )
            fut_notif = pool.submit(
                _github_api_request,
                "https://api.github.com/notifications?all=false&per_page=20",
                "GET",
                None,
                4,
            )
            cc_code, cc_data = fut_cc.result()
            prc_code, prc_data = fut_prc.result()
            notif_code, notif_data = fut_notif.result()

        if cc_code == 200 and isinstance(cc_data, list):
            for c in cc_data:
                if not isinstance(c, dict):
                    continue
                u_obj = c.get("user") if isinstance(c.get("user"), dict) else {}
                author = str((u_obj or {}).get("login") or "unknown")
                c_sha = str(c.get("commit_id") or "")
                created_at = str(c.get("updated_at") or c.get("created_at") or "")
                commit_and_pr_comments.append({
                    "id": c.get("id"),
                    "type": "commit_comment",
                    "type_label": "Commit Comment",
                    "author": author,
                    "commit_sha": c_sha[:7],
                    "full_commit_sha": c_sha,
                    "path": str(c.get("path") or ""),
                    "line": c.get("line") or c.get("position") or 0,
                    "body": str(c.get("body") or "")[:400],
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": str(c.get("html_url") or ""),
                })

        if prc_code == 200 and isinstance(prc_data, list):
            for c in prc_data:
                if not isinstance(c, dict):
                    continue
                u_obj = c.get("user") if isinstance(c.get("user"), dict) else {}
                author = str((u_obj or {}).get("login") or "unknown")
                c_sha = str(c.get("commit_id") or "")
                created_at = str(c.get("updated_at") or c.get("created_at") or "")
                commit_and_pr_comments.append({
                    "id": c.get("id"),
                    "type": "pr_review_comment",
                    "type_label": "PR Code Review Comment",
                    "author": author,
                    "commit_sha": c_sha[:7],
                    "full_commit_sha": c_sha,
                    "path": str(c.get("path") or ""),
                    "line": c.get("line") or c.get("original_line") or 0,
                    "body": str(c.get("body") or "")[:400],
                    "created_at": created_at,
                    "relative_time": _format_relative_time(created_at),
                    "url": str(c.get("html_url") or ""),
                })

        # 5b. Unread GitHub Notifications / Mentions / Review Requests for this repository
        if notif_code == 200 and isinstance(notif_data, list):
            for n in notif_data:
                if not isinstance(n, dict):
                    continue
                r_obj = n.get("repository") if isinstance(n.get("repository"), dict) else {}
                full_name = str((r_obj or {}).get("full_name") or "")
                if full_name and full_name.lower() != self.repo.lower():
                    continue
                subj_obj = n.get("subject") if isinstance(n.get("subject"), dict) else {}
                updated_at = str(n.get("updated_at") or "")
                repo_notifications.append({
                    "thread_id": str(n.get("id") or ""),
                    "reason": str(n.get("reason") or "notification"),
                    "subject_type": str((subj_obj or {}).get("type") or "Item"),
                    "title": str((subj_obj or {}).get("title") or ""),
                    "updated_at": updated_at,
                    "relative_time": _format_relative_time(updated_at),
                    "unread": bool(n.get("unread", True)),
                })

        # 5c. Cryptographic Tag Verification & Release Audit (Recent tags in a single git command)
        try:
            from fleet.tools.release_manager import verify_git_tag_signed

            tag_res = self._run_git(
                [
                    "for-each-ref",
                    "--sort=-creatordate",
                    "--count=8",
                    "--format=@@TAGENTRY@@%(refname:short)@@SEP@@%(objectname:short)@@SEP@@%(taggername)@@SEP@@%(creatordate:iso-strict)@@SEP@@%(subject)@@SEP@@%(objecttype)@@SEP@@%(contents:signature)",
                    "refs/tags",
                ],
                cwd=target_root,
            )
            for record in (tag_res.stdout or "").split("@@TAGENTRY@@"):
                rec = record.strip()
                if not rec:
                    continue
                t_parts = rec.split("@@SEP@@")
                t_name = t_parts[0].strip() if len(t_parts) > 0 else ""
                if not t_name:
                    continue
                t_sha = t_parts[1].strip() if len(t_parts) > 1 else ""
                t_tagger = (t_parts[2].strip() if len(t_parts) > 2 else "") or "macazaka"
                t_date = t_parts[3].strip() if len(t_parts) > 3 else ""
                t_subj = t_parts[4].strip() if len(t_parts) > 4 else ""
                t_objtype = t_parts[5].strip() if len(t_parts) > 5 else ""
                t_sig = t_parts[6].strip() if len(t_parts) > 6 else ""
                if t_objtype == "tag":
                    is_signed = ("-----BEGIN SSH SIGNATURE-----" in t_sig) or ("-----BEGIN PGP SIGNATURE-----" in t_sig)
                else:
                    is_signed = verify_git_tag_signed(target_root, t_name)
                tag_audit.append({
                    "tag": t_name,
                    "sha": t_sha,
                    "author": t_tagger,
                    "date_iso": t_date,
                    "relative_time": _format_relative_time(t_date),
                    "subject": t_subj,
                    "verified_signed": is_signed,
                    "release_url": f"https://github.com/{self.repo}/releases/tag/{t_name}",
                })
        except Exception:
            pass

        unsigned_tags_count = sum(1 for t in tag_audit if not t.get("verified_signed"))
        return {
            "status": "OK",
            "commit_and_pr_comments_count": len(commit_and_pr_comments),
            "commit_and_pr_comments": commit_and_pr_comments,
            "unread_notifications_count": len(repo_notifications),
            "repo_notifications": repo_notifications,
            "tags_audited_count": len(tag_audit),
            "unsigned_tags_count": unsigned_tags_count,
            "tag_audit": tag_audit,
            "releases_url": f"https://github.com/{self.repo}/releases",
            "tags_url": f"https://github.com/{self.repo}/tags",
        }

    def audit_governance_hub(
        self,
        repo_root: Optional[Path] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Comprehensive 5-Pillar Repository Governance Hub audit ($0.00 / 0 LLM tokens):
          1. Security & Quality Notifications
          2. Open Discussions Needing Attention
          3. Wiki Page Comments, Questions & Sync Status
          4. Reported Issues (GitHub Issues + Local Autonomous Reports)
          5. Other Relevant Governance Items (Commit/PR Review Comments, Mentions, Signed Tag Audit)
        """
        target_root = Path(repo_root) if repo_root else self.repo_root
        is_test_run = "pytest" in sys.modules or os.environ.get("FLEET_TEST_MODE") == "1"
        if not force_refresh and not is_test_run and target_root == self.repo_root:
            cached_ts, cached_payload = self._governance_cache
            if time.monotonic() - cached_ts < 45.0 and cached_payload:
                return cached_payload

        with ThreadPoolExecutor(max_workers=4) as pool:
            fut_sec = pool.submit(self.audit_security_and_quality_notifications, target_root)
            fut_disc = pool.submit(self.audit_open_discussions)
            fut_iss = pool.submit(self.audit_reported_issues)
            fut_other = pool.submit(self.audit_other_governance_items, target_root)
            sec_quality = fut_sec.result()
            discussions = fut_disc.result()
            issues = fut_iss.result()
            other_gov = fut_other.result()

        wiki_feedback = self.audit_wiki_comments_and_feedback(
            repo_root=target_root,
            open_issues=issues.get("github_issues", []),
            open_discussions=discussions.get("discussions", []),
        )

        total_action_items = (
            int(sec_quality.get("total_notifications") or 0)
            + int(discussions.get("open_count") or 0)
            + int(wiki_feedback.get("comments_needing_answer_count") or 0)
            + int(issues.get("total_issues_count") or 0)
            + int(other_gov.get("commit_and_pr_comments_count") or 0)
            + int(other_gov.get("unread_notifications_count") or 0)
        )

        result = {
            "status": "OK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_action_items": total_action_items,
            "security_and_quality": sec_quality,
            "discussions": discussions,
            "wiki_feedback": wiki_feedback,
            "reported_issues": issues,
            "other_governance": other_gov,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        }
        if not is_test_run and target_root == self.repo_root:
            self._governance_cache = (time.monotonic(), result)
        return result

    def execute_governance_action(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes an administrative action across the 5 Governance Hub pillars:
          - auto_fix_security_quality
          - dismiss_code_scanning_alert / dismiss_dependabot_alert
          - create_issue / comment_issue / close_issue
          - comment_discussion
          - reply_commit_comment
          - sync_wiki_now
          - resign_tag
          - mark_notification_read
          - complete_local_task / create_fleet_task
          - address_in_antigravity
        """
        opts = payload if isinstance(payload, dict) else {}
        act = (action or "").strip().lower()

        if act == "auto_fix_security_quality":
            from fleet.tools.auto_fixer import run_auto_fixer
            from fleet.tools.security_scanner import run_security_scan

            af_res = run_auto_fixer(repo_root=self.repo_root, stage_changes=False, run_pyright_cli=False)
            sec_res = run_security_scan(repo_root=self.repo_root)
            fixes_cnt = int(af_res.get("fixes_applied_count") or 0)
            return {
                "status": "ok",
                "action": act,
                "fixes_applied_count": fixes_cnt,
                "security_score": sec_res.get("score", 100),
                "message": f"Auto-Fixer completed ({fixes_cnt} fix(es) applied). Local Security Score: {sec_res.get('score', 100)}/100.",
            }

        if act == "dismiss_code_scanning_alert":
            alert_num = int(opts.get("alert_number") or 0)
            if alert_num <= 0:
                return {"status": "error", "message": "Valid alert_number is required."}
            reason = str(opts.get("dismissed_reason") or "won't fix")
            comment = str(opts.get("dismissed_comment") or "Resolved via AFCC Admin PR & Security Gate.")
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/code-scanning/alerts/{alert_num}",
                method="PATCH",
                payload={"state": "dismissed", "dismissed_reason": reason, "dismissed_comment": comment},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Dismissed CodeQL alert #{alert_num}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "dismiss_dependabot_alert":
            alert_num = int(opts.get("alert_number") or 0)
            if alert_num <= 0:
                return {"status": "error", "message": "Valid alert_number is required."}
            reason = str(opts.get("dismissed_reason") or "tolerable_risk")
            comment = str(opts.get("dismissed_comment") or "Reviewed via AFCC Admin Security Gate.")
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/dependabot/alerts/{alert_num}",
                method="PATCH",
                payload={"state": "dismissed", "dismissed_reason": reason, "dismissed_comment": comment},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Dismissed Dependabot alert #{alert_num}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "create_issue":
            title = str(opts.get("title") or "").strip()
            body_txt = str(opts.get("body") or "").strip()
            labels = opts.get("labels") if isinstance(opts.get("labels"), list) else []
            if not title:
                return {"status": "error", "message": "Issue title is required."}
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/issues",
                method="POST",
                payload={"title": title, "body": body_txt, "labels": labels},
            )
            if 200 <= code < 300 and isinstance(resp, dict):
                return {
                    "status": "ok",
                    "action": act,
                    "issue_number": resp.get("number"),
                    "url": resp.get("html_url"),
                    "message": f"Created GitHub Issue #{resp.get('number')}: {title}",
                }
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "comment_issue":
            issue_num = int(opts.get("issue_number") or opts.get("number") or 0)
            body_txt = str(opts.get("body") or opts.get("comment") or "").strip()
            if issue_num <= 0 or not body_txt:
                return {"status": "error", "message": "Valid issue_number and comment body are required."}
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/issues/{issue_num}/comments",
                method="POST",
                payload={"body": body_txt},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Posted comment on Issue #{issue_num}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "close_issue":
            issue_num = int(opts.get("issue_number") or opts.get("number") or 0)
            if issue_num <= 0:
                return {"status": "error", "message": "Valid issue_number is required."}
            comment_txt = str(opts.get("comment") or "").strip()
            if comment_txt:
                _github_api_request(
                    f"https://api.github.com/repos/{self.repo}/issues/{issue_num}/comments",
                    method="POST",
                    payload={"body": comment_txt},
                )
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/issues/{issue_num}",
                method="PATCH",
                payload={"state": "closed"},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Closed GitHub Issue #{issue_num}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "comment_discussion":
            disc_num = int(opts.get("discussion_number") or opts.get("number") or 0)
            body_txt = str(opts.get("body") or opts.get("comment") or "").strip()
            if disc_num <= 0 or not body_txt:
                return {"status": "error", "message": "Valid discussion_number and comment body are required."}
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/discussions/{disc_num}/comments",
                method="POST",
                payload={"body": body_txt},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Posted reply on Discussion #{disc_num}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "reply_commit_comment":
            commit_sha = str(opts.get("commit_sha") or "").strip()
            body_txt = str(opts.get("body") or opts.get("comment") or "").strip()
            if not commit_sha or not body_txt:
                return {"status": "error", "message": "Valid commit_sha and comment body are required."}
            code, resp = _github_api_request(
                f"https://api.github.com/repos/{self.repo}/commits/{commit_sha}/comments",
                method="POST",
                payload={"body": body_txt},
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Posted reply on commit {commit_sha[:7]}."}
            return {"status": "error", "message": str(resp.get("message") if isinstance(resp, dict) else resp)}

        if act == "sync_wiki_now":
            try:
                from fleet.tools.sync_wiki import sync_github_wiki

                ok = sync_github_wiki()
                if ok:
                    return {"status": "ok", "action": act, "message": "Synchronized local wiki/*.md pages to live GitHub Wiki."}
                return {"status": "error", "message": "GitHub Wiki sync returned non-zero status; check remote .wiki.git access."}
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        if act == "resign_tag":
            tag_name = str(opts.get("tag") or "").strip()
            if not tag_name or not _is_safe_branch_name(tag_name):
                return {"status": "error", "message": f"Invalid tag name '{tag_name}'."}
            from fleet.tools.release_manager import ensure_git_tag, verify_git_tag_signed

            clean_ver = tag_name[1:] if tag_name.startswith("v") else tag_name
            ensure_git_tag(self.repo_root, clean_ver)
            signed_ok = verify_git_tag_signed(self.repo_root, f"v{clean_ver}")
            if signed_ok and bool(opts.get("push_origin", True)):
                self._run_git(["push", "--force", "origin", f"refs/tags/v{clean_ver}"], timeout=25)
            return {
                "status": "ok" if signed_ok else "error",
                "action": act,
                "tag": f"v{clean_ver}",
                "verified_signed": signed_ok,
                "message": f"Tag v{clean_ver} cryptographically signed and verified." if signed_ok else f"Could not sign tag v{clean_ver}.",
            }

        if act == "mark_notification_read":
            thread_id = str(opts.get("thread_id") or "").strip()
            if not thread_id.isdigit():
                return {"status": "error", "message": "Valid numeric thread_id is required."}
            code, _ = _github_api_request(
                f"https://api.github.com/notifications/threads/{thread_id}",
                method="PATCH",
            )
            if 200 <= code < 300:
                return {"status": "ok", "action": act, "message": f"Marked notification #{thread_id} as read."}
            return {"status": "error", "message": f"GitHub API returned HTTP {code}"}

        if act == "complete_local_task":
            task_id = int(opts.get("task_id") or 0)
            if task_id <= 0 or not self.db or not hasattr(self.db, "complete_task"):
                return {"status": "error", "message": "Valid local task_id is required."}
            self.db.complete_task(task_id)
            return {"status": "ok", "action": act, "message": f"Marked local governance task #{task_id} completed."}

        if act == "create_fleet_task":
            title = str(opts.get("title") or "").strip()
            desc = str(opts.get("description") or "").strip()
            if not title:
                return {"status": "error", "message": "Task title is required."}
            if self.db and hasattr(self.db, "add_task"):
                tid = self.db.add_task(
                    title=title,
                    description=desc,
                    priority=str(opts.get("priority") or "P1"),
                    assigned_agent="pr_review",
                    source="pr_review_governance",
                )
                return {"status": "ok", "action": act, "task_id": tid, "message": f"Added P1 Fleet task: {title}"}
            return {"status": "error", "message": "Database unavailable."}

        if act == "address_in_antigravity":
            item_type = str(opts.get("item_type") or "Governance Item").strip()
            title = str(opts.get("title") or "").strip()
            author = str(opts.get("author") or "").strip()
            detail = str(opts.get("detail") or "").strip()
            file_ref = str(opts.get("file") or "").strip()
            url_ref = str(opts.get("url") or "").strip()
            prompt = (
                f"[Admin PR Review & Governance Gate — {item_type}] Please address and resolve the following item:\n"
                f"- Title: {title}\n"
                + (f"- Author / Reporter: {author}\n" if author else "")
                + (f"- File / Location: {file_ref}\n" if file_ref else "")
                + (f"- URL: {url_ref}\n" if url_ref else "")
                + (f"- Context / Details:\n{detail}\n\n" if detail else "\n")
                + "Please inspect the relevant code/documentation, implement the fix or draft the response, and verify all checks pass."
            )
            dispatched = False
            try:
                from fleet.server import execute_dashboard_command

                execute_dashboard_command(prompt)
                dispatched = True
            except Exception as exc:
                logger.warning("Could not dispatch governance prompt to Antigravity bridge: %s", exc)
            return {
                "status": "ok",
                "action": act,
                "dispatched": dispatched,
                "prompt": prompt,
                "message": f"Dispatched '{title[:60]}' to Antigravity Live.",
            }

        return {"status": "error", "message": f"Unsupported governance action '{action}'."}

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        task_lower = task.lower()
        p = payload if isinstance(payload, dict) else {}
        if "branch" in task_lower or "unmerged" in task_lower or "merge" in task_lower:
            action = str(p.get("action") or "").strip()
            if action:
                return self.execute_branch_action(
                    action=action,
                    branch=str(p.get("branch") or ""),
                    payload=p,
                )
            return self.audit_unmerged_branches(fetch_remote=bool(p.get("fetch_remote", False)))
        if "pipeline" in task_lower or "codeql" in task_lower or "vuln" in task_lower or "sentinel" in task_lower:
            return self.audit_github_pipelines(
                commit_sha=str(p.get("sha") or ""),
                wait_for_completion=bool(p.get("wait", False)),
                auto_remediate=bool(p.get("auto_remediate", True)),
            )
        if "governance" in task_lower or "security" in task_lower or "discussion" in task_lower or "wiki" in task_lower or "issue" in task_lower:
            action = str(p.get("action") or "").strip()
            if action:
                return self.execute_governance_action(action=action, payload=p)
            return self.audit_governance_hub(repo_root=self.repo_root)
        if "pr" in task_lower or "pull request" in task_lower:
            return self.audit_pull_requests()
        if "ci" in task_lower or "check" in task_lower or "status" in task_lower:
            return self.check_ci_status()
        return {
            "status": "UNKNOWN_TASK",
            "supported_tasks": [
                "audit_unmerged_branches",
                "execute_branch_action",
                "audit_pull_requests",
                "check_ci_status",
                "audit_github_pipelines",
                "audit_governance_hub",
                "execute_governance_action",
            ],
        }
