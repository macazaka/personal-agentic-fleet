"""
Unit tests for PRReviewAgent unmerged branch governance, author attribution,
diffstat/change inspection, conflict detection, and interactive branch actions.
"""

from pathlib import Path
import subprocess
from typing import Any, Dict, List
from unittest.mock import patch

from fleet.agents.pr_review.agent import PRReviewAgent, _is_safe_branch_name


def _git(repo: Path, args: List[str], author_name: str = "Alice Dev", author_email: str = "alice@example.com") -> str:
    env_vars = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    }
    import os

    full_env = os.environ.copy()
    full_env.update(env_vars)
    hidden_kw: Dict[str, Any] = {}
    if os.name == "nt":
        hidden_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        if hasattr(subprocess, "STARTUPINFO"):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
            si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            hidden_kw["startupinfo"] = si
    res = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=full_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        **hidden_kw,
    )
    return res.stdout.strip()


def _init_temp_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, ["init", "-b", "main"])
    _git(repo, ["config", "user.name", "Alice Dev"])
    _git(repo, ["config", "user.email", "alice@example.com"])

    readme = repo / "README.md"
    readme.write_text("# Sample Repo\nInitial line\n", encoding="utf-8")
    _git(repo, ["add", "README.md"])
    _git(repo, ["commit", "-m", "chore: initial commit on main"])
    return repo


def test_safe_branch_name_validation():
    assert _is_safe_branch_name("feat/new-branch-1")
    assert _is_safe_branch_name("bugfix/issue_42.1")
    assert not _is_safe_branch_name("")
    assert not _is_safe_branch_name("--upload-pack=evil")
    assert not _is_safe_branch_name("feat/../secret")
    assert not _is_safe_branch_name("branch.lock")


def test_audit_unmerged_branches_extracts_authors_and_changes(tmp_path: Path):
    repo = _init_temp_git_repo(tmp_path)

    # Create feature branch with 2 commits by two different authors
    _git(repo, ["checkout", "-b", "feat/security-gate"])
    tool_dir = repo / "fleet" / "tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    scanner_file = tool_dir / "scanner.py"
    scanner_file.write_text("def scan():\n    return True\n", encoding="utf-8")
    _git(
        repo,
        ["add", "fleet/tools/scanner.py"],
        author_name="Alice Dev",
        author_email="alice@example.com",
    )
    _git(
        repo,
        ["commit", "-m", "feat: add security gate scanner"],
        author_name="Alice Dev",
        author_email="alice@example.com",
    )

    test_dir = repo / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_scanner.py"
    test_file.write_text("def test_scan():\n    assert True\n", encoding="utf-8")
    _git(
        repo,
        ["add", "tests/test_scanner.py"],
        author_name="Bob Reviewer",
        author_email="bob@example.com",
    )
    _git(
        repo,
        ["commit", "-m", "test: add unit tests for scanner"],
        author_name="Bob Reviewer",
        author_email="bob@example.com",
    )

    # Return to main
    _git(repo, ["checkout", "main"])

    agent = PRReviewAgent(repo_root=repo)
    report = agent.audit_unmerged_branches(repo_root=repo)

    assert report["status"] == "SUCCESS"
    assert report["base_branch"] == "main"
    assert report["unmerged_count"] == 1

    branch_info = report["unmerged_branches"][0]
    assert branch_info["branch"] == "feat/security-gate"
    assert branch_info["ahead_count"] == 2
    assert branch_info["behind_count"] == 0
    assert branch_info["can_clean_merge"] is True
    assert branch_info["merge_status"] == "CLEAN"
    assert branch_info["latest_author_name"] == "Bob Reviewer"
    assert branch_info["latest_author_email"] == "bob@example.com"
    assert branch_info["files_changed_count"] == 2
    assert branch_info["insertions"] == 4
    assert branch_info["deletions"] == 0

    author_names = {a["name"] for a in branch_info["authors"]}
    assert author_names == {"Alice Dev", "Bob Reviewer"}
    assert "DevOps & Security Tools" in branch_info["change_categories"]
    assert "Unit Tests" in branch_info["change_categories"]


def test_execute_branch_actions_diff_merge_and_delete(tmp_path: Path):
    repo = _init_temp_git_repo(tmp_path)

    # Create a branch via execute_branch_action('create_branch') from dirty working tree
    ui_dir = repo / "fleet" / "web"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "widget.js").write_text("console.log('ready');\n", encoding="utf-8")

    agent = PRReviewAgent(repo_root=repo)
    create_res = agent.execute_branch_action(
        action="create_branch",
        branch="feat/ui-widget",
        payload={
            "new_branch": "feat/ui-widget",
            "commit_message": "feat: add interactive widget",
            "switch_back_to_main": True,
        },
        repo_root=repo,
    )
    assert create_res["status"] == "ok"
    assert create_res["branches"]["unmerged_count"] == 1

    # Inspect diff
    diff_res = agent.execute_branch_action(
        action="diff",
        branch="feat/ui-widget",
        repo_root=repo,
    )
    assert diff_res["status"] == "ok"
    assert "+console.log('ready');" in diff_res["diff"]
    assert diff_res["branch_info"]["ahead_count"] == 1

    # Dispatch review to Antigravity Live (mocking bridge)
    with patch("fleet.server.execute_dashboard_command") as mock_cmd:
        rev_res = agent.execute_branch_action(
            action="review_in_antigravity",
            branch="feat/ui-widget",
            repo_root=repo,
        )
        assert rev_res["status"] == "ok"
        assert rev_res["dispatched"] is True
        assert mock_cmd.called

    # Merge branch into main and clean up
    merge_res = agent.execute_branch_action(
        action="merge",
        branch="feat/ui-widget",
        payload={"delete_after_merge": True},
        repo_root=repo,
    )
    assert merge_res["status"] == "ok"
    assert merge_res["branches"]["unmerged_count"] == 0
    assert (repo / "fleet" / "web" / "widget.js").exists()

    # Ensure deleting protected main branch is blocked
    del_main = agent.execute_branch_action(
        action="delete_branch",
        branch="main",
        repo_root=repo,
    )
    assert del_main["status"] == "error"


def test_signed_git_tag_creation_and_hook_verification(tmp_path: Path):
    from fleet.tools.install_git_hooks import install_git_hooks
    from fleet.tools.release_manager import ensure_git_tag, verify_git_tag_signed

    repo = _init_temp_git_repo(tmp_path)

    # Generate an isolated temporary Ed25519 SSH signing key for deterministic cross-platform testing
    key_file = tmp_path / "test_signing_ed25519"
    pub_file = tmp_path / "test_signing_ed25519.pub"
    import os
    hidden_kw: Dict[str, Any] = (
        {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if os.name == "nt" else {}
    )
    keygen = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_file), "-q"],
        capture_output=True,
        text=True,
        check=False,
        **hidden_kw,
    )
    assert keygen.returncode == 0 and pub_file.is_file()

    _git(repo, ["config", "gpg.format", "ssh"])
    _git(repo, ["config", "user.signingkey", str(pub_file)])

    # 1. Create an explicitly unsigned annotated tag and verify verify_git_tag_signed returns False
    _git(repo, ["tag", "--no-sign", "-a", "v1.0.0", "-m", "Unsigned release v1.0.0"])
    assert verify_git_tag_signed(repo, "v1.0.0") is False

    # 2. ensure_git_tag upgrades the unsigned local tag to a cryptographically signed annotated tag
    assert ensure_git_tag(repo, "1.0.0") is True
    assert verify_git_tag_signed(repo, "v1.0.0") is True

    # 3. Calling ensure_git_tag again on an already-signed tag is a no-op (returns False)
    assert ensure_git_tag(repo, "1.0.0") is False

    # 4. Creating a brand-new version tag creates a cryptographically signed annotated tag immediately
    assert ensure_git_tag(repo, "1.1.0") is True
    assert verify_git_tag_signed(repo, "v1.1.0") is True

    # 5. Verify install_git_hooks configures tag.gpgSign and installs pre-push/post-commit tag signing guards
    hook_res = install_git_hooks(repo_root=repo)
    assert hook_res["status"] == "installed"
    assert _git(repo, ["config", "--bool", "tag.gpgSign"]) == "true"
    pre_push_txt = (repo / ".git" / "hooks" / "pre-push").read_text(encoding="utf-8")
    post_commit_txt = (repo / ".git" / "hooks" / "post-commit").read_text(encoding="utf-8")
    assert "Tag Protection: Unsigned tag" in pre_push_txt
    assert "ensure_git_tag" in post_commit_txt


def test_startup_latest_version_verification_and_cache():
    from fleet.core.updater import (
        ensure_latest_version_before_launch,
        get_cached_version_check,
        parse_version_tuple,
    )

    assert parse_version_tuple("v2.13.4") > parse_version_tuple("2.13.3")
    sync_res = ensure_latest_version_before_launch(auto_apply=False)
    assert "version_after" in sync_res
    assert "up_to_date" in sync_res

    cached = get_cached_version_check()
    assert "current_version" in cached
    assert "latest_version" in cached
    assert "up_to_date" in cached


def test_proactive_auto_fixer_and_post_commit_timeout_sentinel(tmp_path: Path):
    from fleet.daemon import FleetDaemon
    from fleet.tools.auto_fixer import (
        audit_vscode_workspace_problems,
        fix_codeql_and_security_issues,
        fix_html_and_template_problems,
    )

    repo = _init_temp_git_repo(tmp_path)
    py_dir = repo / "fleet" / "agents" / "demo"
    ui_dir = py_dir / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create a Python file with .netloc.endswith('github.com') and an HTML panel with a button missing title=""
    py_fp = py_dir / "agent.py"
    py_fp.write_text(
        "import urllib.parse\n"
        "def check(url: str) -> bool:\n"
        "    parsed = urllib.parse.urlparse(url)\n"
        "    if not parsed.netloc.endswith('github.com'):\n"
        "        return False\n"
        "    return True\n",
        encoding="utf-8",
    )
    html_fp = ui_dir / "panel.html"
    html_fp.write_text(
        '<div><button class="btn-secondary" onclick="doWork()">Run Action</button></div>\n',
        encoding="utf-8",
    )
    _git(repo, ["add", "."])
    _git(repo, ["commit", "-m", "chore: test fixtures"])

    # Audit detects missing button tooltip before fix
    pre_audit = audit_vscode_workspace_problems(repo_root=repo)
    assert any(p.get("code") == "missing-button-tooltip" for p in pre_audit.get("problems", []))

    # Auto-fixer repairs both CodeQL URL check and HTML button tooltip
    sec_fixes = fix_codeql_and_security_issues(repo_root=repo)
    html_fixes = fix_html_and_template_problems(repo_root=repo)
    assert len(sec_fixes) >= 1
    assert len(html_fixes) >= 1
    assert 'parsed.hostname not in ("api.github.com", "github.com")' in py_fp.read_text(encoding="utf-8")
    assert 'title="Run Action"' in html_fp.read_text(encoding="utf-8")

    post_audit = audit_vscode_workspace_problems(repo_root=repo)
    assert not any(p.get("code") == "missing-button-tooltip" for p in post_audit.get("problems", []))

    # 2. Verify FleetDaemon.run_post_commit_timeout_sentinel_check triggers background sentinel when HEAD is unaudited
    daemon = FleetDaemon()
    with patch("fleet.tools.github_pipeline_sentinel.get_local_head_sha", return_value="abcdef1234567890"):
        with patch("fleet.tools.github_pipeline_sentinel.spawn_detached_post_push_sentinel", return_value=True) as mock_spawn:
            daemon.run_post_commit_timeout_sentinel_check()
            assert mock_spawn.called
            assert daemon.last_sentinel_triggered_sha == "abcdef1234567890"


def test_pr_review_5_pillar_governance_hub_and_actions(tmp_path: Path):
    repo = _init_temp_git_repo(tmp_path)
    wiki_dir = repo / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "Home.md").write_text(
        "# Home\n"
        "QUESTION: How should contributors configure SSH tag signing on Windows?\n",
        encoding="utf-8",
    )
    _git(repo, ["add", "."])
    _git(repo, ["commit", "-m", "docs: add wiki page with question"])

    agent = PRReviewAgent(repo_root=repo)

    def _fake_gh_api(url: str, method: str = "GET", payload=None, timeout: int = 8):
        if "/code-scanning/alerts" in url and method == "GET":
            return 200, [
                {
                    "number": 7,
                    "rule": {"id": "py/sql-injection", "security_severity_level": "high", "description": "SQL query built from user input"},
                    "most_recent_instance": {"location": {"path": "fleet/demo.py", "start_line": 42}},
                    "created_at": "2026-11-03T10:00:00Z",
                    "html_url": "https://github.com/macazaka/personal-agentic-fleet/security/code-scanning/7",
                }
            ]
        if "/dependabot/alerts" in url and method == "GET":
            return 200, [
                {
                    "number": 3,
                    "dependency": {"package": {"name": "urllib3"}, "manifest_path": "pyproject.toml"},
                    "security_advisory": {"ghsa_id": "GHSA-1234", "severity": "medium", "summary": "Redirect header issue"},
                    "security_vulnerability": {"first_patched_version": {"identifier": "2.2.2"}},
                    "created_at": "2026-11-03T11:00:00Z",
                }
            ]
        if "/discussions" in url and method == "GET":
            return 200, [
                {
                    "number": 12,
                    "title": "RFC: Multi-workspace agent sync",
                    "state": "open",
                    "user": {"login": "alice-dev"},
                    "category": {"name": "Ideas", "is_answerable": True},
                    "answer_chosen_at": None,
                    "comments": 0,
                    "upvote_count": 4,
                    "updated_at": "2026-11-03T12:00:00Z",
                    "body": "Should we support syncing custom agents across two drives?",
                }
            ]
        if "/issues" in url and method == "GET":
            return 200, [
                {
                    "number": 19,
                    "title": "Bug: Wiki sidebar link formatting",
                    "user": {"login": "bob-qa"},
                    "labels": [{"name": "bug", "color": "d73a4a"}, {"name": "wiki", "color": "a2eeef"}],
                    "assignees": [],
                    "comments": 0,
                    "updated_at": "2026-11-03T13:00:00Z",
                    "body": "In the Wiki page _Sidebar.md, check anchor links.",
                },
                {
                    "number": 20,
                    "title": "PR disguised as issue in GitHub API",
                    "pull_request": {"url": "https://api.github.com/..."},
                },
            ]
        if "/comments" in url and method == "GET":
            return 200, [
                {
                    "id": 501,
                    "user": {"login": "reviewer1"},
                    "commit_id": "4af49935efa6407e",
                    "path": "fleet/server.py",
                    "line": 88,
                    "body": "Great CSP header addition!",
                    "created_at": "2026-11-03T14:00:00Z",
                }
            ]
        if "/notifications" in url and method == "GET":
            return 200, [
                {
                    "id": "9901",
                    "reason": "mention",
                    "unread": True,
                    "repository": {"full_name": "macazaka/personal-agentic-fleet"},
                    "subject": {"type": "Issue", "title": "Bug: Wiki sidebar link formatting"},
                    "updated_at": "2026-11-03T14:30:00Z",
                }
            ]
        return 200, {"number": 25, "html_url": "https://github.com/macazaka/personal-agentic-fleet/issues/25"}

    with patch.dict(PRReviewAgent.audit_governance_hub.__globals__, {"_github_api_request": _fake_gh_api}):
        hub = agent.audit_governance_hub(repo_root=repo)
        assert hub["status"] == "OK"
        # 1. Security & Quality
        assert hub["security_and_quality"]["codeql_count"] == 1
        assert hub["security_and_quality"]["dependabot_count"] == 1
        # 2. Open Discussions
        assert hub["discussions"]["open_count"] == 1
        assert hub["discussions"]["unanswered_count"] == 1
        assert hub["discussions"]["discussions"][0]["author"] == "alice-dev"
        # 3. Wiki Page Comments (1 inline QUESTION + 1 Wiki-labeled GitHub Issue)
        assert hub["wiki_feedback"]["comments_needing_answer_count"] == 2
        assert hub["wiki_feedback"]["total_wiki_pages"] == 1
        # 4. Reported Issues (excludes PR #20, includes Issue #19)
        assert hub["reported_issues"]["open_github_issues_count"] == 1
        assert hub["reported_issues"]["github_issues"][0]["number"] == 19
        # 5. Other Governance (Commit comments, PR review comments, unread mentions)
        assert hub["other_governance"]["commit_and_pr_comments_count"] == 2
        assert hub["other_governance"]["unread_notifications_count"] == 1

        # Verify governance actions (create_issue, comment_issue, comment_discussion, address_in_antigravity)
        c_iss = agent.execute_governance_action("create_issue", {"title": "New Bug", "body": "Details"})
        assert c_iss["status"] == "ok"
        assert c_iss["issue_number"] == 25

        c_disc = agent.execute_governance_action("comment_discussion", {"discussion_number": 12, "body": "Answered!"})
        assert c_disc["status"] == "ok"

        with patch("fleet.server.execute_dashboard_command") as mock_ag:
            ag_res = agent.execute_governance_action(
                "address_in_antigravity",
                {
                    "item_type": "Wiki Question",
                    "title": "SSH tag signing on Windows",
                    "author": "alice-dev",
                    "detail": "Explain gpg.format=ssh",
                    "file": "wiki/Home.md",
                },
            )
            assert ag_res["status"] == "ok"
            assert ag_res["dispatched"] is True
            assert mock_ag.called





