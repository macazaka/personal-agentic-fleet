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
    if parsed.scheme != "https" or not parsed.netloc.endswith("github.com"):
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
    opener = urllib.request.build_opener(_IPv4FirstHTTPSHandler(context=_build_tls_context()))
    try:
        with opener.open(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
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
            prs = self.audit_pull_requests()
            ci = self.check_ci_status()
            open_prs_list = prs.get("prs", []) if isinstance(prs, dict) else []
            branches = self.audit_unmerged_branches(
                fetch_remote=fetch_remote,
                open_prs=open_prs_list,
            )
            handler._send_json({
                "status": "ok",
                "prs": prs,
                "ci": ci,
                "branches": branches,
            })

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
            ],
        }
