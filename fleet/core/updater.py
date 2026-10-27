"""
GitHub Version Checking, Native Notifications & 1-Click Update Engine
for Personal Agentic Fleet.
Checks GitHub Releases/Tags on workstation startup, notifies the user
via native desktop notifications, and enables downloading updates ($0.00 / 0 tokens).
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any, Dict, Optional, Tuple
import urllib.request

from fleet import __version__ as CURRENT_VERSION
from fleet.config import get_live_version
from fleet.tools.system_tools import send_notification

logger = logging.getLogger("fleet.updater")

GITHUB_REPO = "macazaka/personal-agentic-fleet"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RAW_INIT_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/fleet/__init__.py"


def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Converts a version string like 'v2.5.1' or '2.5.0' into an integer tuple (2, 5, 0)."""
    cleaned = v_str.strip().lstrip("v").lstrip("V")
    parts = []
    for token in re.split(r"[.\-_]", cleaned):
        if token.isdigit():
            parts.append(int(token))
        else:
            break
    return tuple(parts) if parts else (0, 0, 0)


def check_github_for_updates(timeout_sec: float = 4.0) -> Dict[str, Any]:
    """
    Checks GitHub Releases API (and raw repo fallback) for the latest release tag.
    Compares against the currently running Fleet version.
    Zero external dependencies ($0.00 / 0 tokens).
    """
    global CURRENT_VERSION
    CURRENT_VERSION = get_live_version()
    latest_ver_str = CURRENT_VERSION
    release_name = f"Personal Agentic Fleet v{CURRENT_VERSION}"
    release_notes = "You are currently running the latest official version."
    html_url = f"https://github.com/{GITHUB_REPO}/releases"
    zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
    published_at = datetime.now().isoformat()
    fetch_success = False

    # 1. Try GitHub Releases API
    try:
        req = urllib.request.Request(
            RELEASES_API_URL,
            headers={
                "User-Agent": "Personal-Agentic-Fleet-Updater",
                "Accept": "application/vnd.github.v3+json",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                tag_name = data.get("tag_name", "").strip()
                if tag_name:
                    latest_ver_str = tag_name.lstrip("v")
                    release_name = data.get("name") or f"Release {tag_name}"
                    release_notes = data.get("body") or "New capabilities, bug fixes, and performance improvements."
                    html_url = data.get("html_url") or html_url
                    zip_url = data.get("zipball_url") or zip_url
                    published_at = data.get("published_at") or published_at
                    fetch_success = True
    except Exception as e:
        logger.debug(f"[Updater] GitHub Releases API check bypassed: {e}")

    # 2. Fallback to raw __init__.py on main branch if releases API is empty/rate-limited
    if not fetch_success:
        try:
            req_raw = urllib.request.Request(
                RAW_INIT_URL,
                headers={"User-Agent": "Personal-Agentic-Fleet-Updater"}
            )
            with urllib.request.urlopen(req_raw, timeout=timeout_sec) as resp_raw:
                if resp_raw.status == 200:
                    raw_text = resp_raw.read().decode("utf-8")
                    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', raw_text)
                    if m:
                        latest_ver_str = m.group(1).strip()
                        release_name = f"Personal Agentic Fleet v{latest_ver_str}"
                        release_notes = "Latest version on GitHub main branch."
                        fetch_success = True
        except Exception as e:
            logger.debug(f"[Updater] GitHub raw version check bypassed: {e}")

    cur_tuple = parse_version_tuple(CURRENT_VERSION)
    latest_tuple = parse_version_tuple(latest_ver_str)
    update_available = latest_tuple > cur_tuple

    return {
        "status": "success" if fetch_success else "offline",
        "current_version": CURRENT_VERSION,
        "latest_version": latest_ver_str,
        "update_available": update_available,
        "release_name": release_name,
        "release_notes": release_notes,
        "html_url": html_url,
        "download_zip_url": zip_url,
        "published_at": published_at,
        "checked_at": datetime.now().isoformat(),
    }


def download_and_apply_update(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Downloads and applies the latest updates from GitHub.
    Uses 'git pull origin main --ff-only' if git is configured,
    or downloads the source zipball directly.
    """
    root = repo_root or Path(__file__).resolve().parent.parent.parent

    # If running inside a git working directory
    if (root / ".git").is_dir():
        try:
            res = subprocess.run(
                ["git", "pull", "origin", "main", "--ff-only"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            out = (res.stdout or res.stderr or "").strip()
            if res.returncode == 0:
                is_updated = "Already up to date" not in out
                return {
                    "status": "success",
                    "mode": "git_pull",
                    "message": "Successfully pulled latest version from GitHub." if is_updated else "Already up to date.",
                    "details": out,
                    "restart_required": is_updated,
                }
            else:
                return {
                    "status": "error",
                    "mode": "git_pull",
                    "message": f"Git pull failed: {out}",
                    "details": out,
                }
        except Exception as e:
            logger.warning(f"[Updater] git pull failed: {e}")

    # Fallback zipball download
    updates_dir = root / "fleet" / "data" / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    target_zip = updates_dir / f"fleet_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    try:
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
        urllib.request.urlretrieve(zip_url, str(target_zip))
        return {
            "status": "success",
            "mode": "zip_download",
            "message": f"Downloaded latest release zipball to {target_zip.name}.",
            "target_file": str(target_zip),
            "restart_required": True,
        }
    except Exception as e:
        return {
            "status": "error",
            "mode": "zip_download",
            "message": f"Failed to download release zipball: {e}",
        }


def check_and_notify_on_startup(db: Any = None) -> None:
    """
    Runs in a non-blocking background daemon thread upon Control Center launch.
    Checks GitHub for a new version and dispatches an OS toast notification
    if a newer release is detected.
    """
    try:
        res = check_github_for_updates(timeout_sec=5.0)
        if res.get("update_available"):
            latest_ver = res.get("latest_version")
            title = f"⚡ Personal Agentic Fleet v{latest_ver} Available"
            msg = f"A new version of Personal Agentic Fleet is ready on GitHub. Open Settings to upgrade."
            send_notification(title, msg)

            if db and hasattr(db, "log_activity"):
                try:
                    db.log_activity("FleetUpdater", "update_available", f"New release v{latest_ver} detected on GitHub.")
                except Exception:
                    pass
            logger.info(f"[Updater] New version v{latest_ver} detected on GitHub and user notified.")
    except Exception as e:
        logger.debug(f"[Updater] Background startup update check completed with notice: {e}")


def start_startup_update_check(db: Any = None) -> threading.Thread:
    """Launches the background startup update checker daemon thread."""
    t = threading.Thread(
        target=check_and_notify_on_startup,
        args=(db,),
        daemon=True,
        name="FleetStartupUpdateChecker"
    )
    t.start()
    return t

