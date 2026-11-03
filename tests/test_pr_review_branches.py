"""
Unit tests for PRReviewAgent unmerged branch governance, author attribution,
diffstat/change inspection, conflict detection, and interactive branch actions.
"""

from pathlib import Path
import subprocess
from typing import List
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
    res = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=full_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
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
    keygen = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_file), "-q"],
        capture_output=True,
        text=True,
        check=False,
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



