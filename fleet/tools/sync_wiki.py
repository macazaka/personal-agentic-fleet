"""
GitHub Wiki Synchronization Utility for Personal Agentic Fleet.
Syncs all markdown documentation from the local `wiki/` directory to
the GitHub repository's dedicated Wiki Git repository:
  git@github.com:macazaka/personal-agentic-fleet.wiki.git
"""

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Dict, Any

from fleet.config import BASE_DIR

PROJECT_ROOT = BASE_DIR.parent
WIKI_SOURCE_DIR = PROJECT_ROOT / "wiki"
DEFAULT_WIKI_REMOTE = "git@github.com:macazaka/personal-agentic-fleet.wiki.git"


def _remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def sync_github_wiki(remote_url: str = DEFAULT_WIKI_REMOTE, dry_run: bool = False) -> Dict[str, Any]:
    """
    Synchronizes local `wiki/` markdown files to GitHub Wiki git repository.
    """
    if not WIKI_SOURCE_DIR.is_dir():
        return {
            "status": "error",
            "message": f"Wiki source directory not found: {WIKI_SOURCE_DIR}"
        }

    wiki_files = list(WIKI_SOURCE_DIR.glob("*.md"))
    if not wiki_files:
        return {
            "status": "error",
            "message": "No markdown files found in wiki source directory."
        }

    print(f"=== Personal Agentic Fleet — GitHub Wiki Synchronizer ===")
    print(f"Source Directory: {WIKI_SOURCE_DIR} ({len(wiki_files)} pages)")
    print(f"Target Remote:    {remote_url}")

    if dry_run:
        print("[DRY-RUN] Verified files to sync:")
        for wf in sorted(wiki_files):
            print(f"  - {wf.name}")
        return {"status": "dry_run", "files_count": len(wiki_files)}

    # Temporary staging directory for wiki clone
    staging_dir = PROJECT_ROOT / "fleet" / "data" / "user" / "wiki_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, onerror=_remove_readonly)
    staging_dir.parent.mkdir(parents=True, exist_ok=True)

    # 1. Attempt to clone existing wiki repository
    print(f"Cloning wiki repository from {remote_url}...")
    res_clone = subprocess.run(
        ["git", "clone", remote_url, str(staging_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    if res_clone.returncode != 0:
        err_msg = res_clone.stderr.strip()
        print(f"[-] Clone failed: {err_msg}")
        print("\n[IMPORTANT ACTION REQUIRED]")
        print("GitHub provisions the wiki git repository ONLY after the first page is created.")
        print("Please visit: https://github.com/macazaka/personal-agentic-fleet/wiki")
        print("Click the green 'Create the first page' button (saving the default Home page).")
        print("Once initialized on GitHub, re-run this tool to publish all 11 wiki pages.\n")
        return {
            "status": "pending_first_page",
            "remote": remote_url,
            "action_url": "https://github.com/macazaka/personal-agentic-fleet/wiki",
            "message": "Wiki repository not yet provisioned on GitHub. Create first page via Web UI to unlock."
        }

    # 2. Copy all files from wiki/ to staging_dir
    print(f"Syncing {len(wiki_files)} pages to wiki staging...")
    for wf in wiki_files:
        dest = staging_dir / wf.name
        shutil.copy2(wf, dest)
        print(f"  + Synced {wf.name}")

    # 3. Commit and push
    subprocess.run(["git", "config", "user.name", "Personal Agentic Fleet Bot"], cwd=str(staging_dir), check=False)
    subprocess.run(["git", "config", "user.email", "fleet@local.internal"], cwd=str(staging_dir), check=False)
    subprocess.run(["git", "add", "."], cwd=str(staging_dir), check=True)

    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(staging_dir), capture_output=True, text=True)
    if not status_res.stdout.strip():
        print("[OK] Wiki is already up to date. Zero changes required.")
        shutil.rmtree(staging_dir, onerror=_remove_readonly)
        return {"status": "up_to_date", "files_synced": len(wiki_files)}

    subprocess.run(["git", "commit", "-m", "docs(wiki): update documentation pages from main repository"], cwd=str(staging_dir), check=True)
    
    print("Pushing updates to GitHub Wiki...")
    push_res = subprocess.run(["git", "push", "origin", "master"], cwd=str(staging_dir), capture_output=True, text=True)
    if push_res.returncode != 0:
        # Some wikis use 'main' instead of 'master'
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=str(staging_dir), capture_output=True, text=True)

    shutil.rmtree(staging_dir, onerror=_remove_readonly)

    if push_res.returncode == 0:
        print("[ALL PASS] GitHub Wiki successfully synchronized!")
        return {"status": "success", "files_synced": len(wiki_files)}
    else:
        print(f"[-] Push failed: {push_res.stderr}")
        return {"status": "error", "error": push_res.stderr}


def main():
    parser = argparse.ArgumentParser(description="Synchronize Personal Agentic Fleet Wiki with GitHub")
    parser.add_argument("--remote", default=DEFAULT_WIKI_REMOTE, help="Target GitHub Wiki Git URL")
    parser.add_argument("--dry-run", action="store_true", help="List files to sync without pushing")
    args = parser.parse_args()

    res = sync_github_wiki(remote_url=args.remote, dry_run=args.dry_run)
    if res.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
