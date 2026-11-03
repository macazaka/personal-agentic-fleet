"""
GitHub Version Checking, Native Notifications & 1-Click Update Engine
for Personal Agentic Fleet.
Checks GitHub Releases/Tags on workstation startup, notifies the user
via native desktop notifications, and enables downloading updates ($0.00 / 0 tokens).
"""

from datetime import datetime
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
import threading
import time
from typing import Any, Dict, Optional, Tuple
import urllib.request

from fleet import __version__ as CURRENT_VERSION
from fleet.config import DATA_DIR, get_live_version
from fleet.tools.system_tools import send_notification

logger = logging.getLogger("fleet.updater")

GITHUB_REPO = "macazaka/personal-agentic-fleet"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TAGS_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags?per_page=10"
RAW_INIT_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/fleet/__init__.py"
LATEST_VERSION_CACHE_FILE = DATA_DIR / "user" / "latest_version_check.json"

_LAST_CHECK_CACHE: Dict[str, Any] = {}
_LAST_CHECK_TS: float = 0.0


def _build_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class _IPv4FirstHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection preferring IPv4 first so unrouted Windows IPv6 interfaces never stall GitHub update checks."""

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


def _urlopen_ipv4_first(req: urllib.request.Request, timeout: float = 4.0):
    if os.environ.get("FLEET_TEST_MODE") == "1" or "pytest" in sys.modules:
        return urllib.request.urlopen(req, timeout=timeout)
    opener = urllib.request.build_opener(_IPv4FirstHTTPSHandler(context=_build_tls_context()))
    return opener.open(req, timeout=timeout)


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
        with _urlopen_ipv4_first(req, timeout=timeout_sec) as resp:
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

    # 2. Check raw __init__.py on main branch (catches newly pushed releases before Actions finishes building assets)
    if not fetch_success or os.environ.get("FLEET_TEST_MODE") != "1":
        try:
            req_raw = urllib.request.Request(
                RAW_INIT_URL,
                headers={"User-Agent": "Personal-Agentic-Fleet-Updater"}
            )
            with _urlopen_ipv4_first(req_raw, timeout=timeout_sec) as resp_raw:
                if resp_raw.status == 200:
                    raw_text = resp_raw.read().decode("utf-8")
                    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', raw_text)
                    if m:
                        raw_ver = m.group(1).strip()
                        if parse_version_tuple(raw_ver) > parse_version_tuple(latest_ver_str) or not fetch_success:
                            latest_ver_str = raw_ver
                            release_name = f"Personal Agentic Fleet v{latest_ver_str}"
                            release_notes = "Latest version on GitHub main branch."
                        fetch_success = True
        except Exception as e:
            logger.debug(f"[Updater] GitHub raw version check bypassed: {e}")

    cur_tuple = parse_version_tuple(CURRENT_VERSION)
    latest_tuple = parse_version_tuple(latest_ver_str)
    update_available = latest_tuple > cur_tuple

    result = {
        "status": "success" if fetch_success else "offline",
        "current_version": CURRENT_VERSION,
        "latest_version": latest_ver_str,
        "update_available": update_available,
        "up_to_date": not update_available,
        "release_name": release_name,
        "release_notes": release_notes,
        "html_url": html_url,
        "download_zip_url": zip_url,
        "published_at": published_at,
        "checked_at": datetime.now().isoformat(),
    }
    global _LAST_CHECK_CACHE, _LAST_CHECK_TS
    _LAST_CHECK_CACHE = result
    _LAST_CHECK_TS = time.time()
    if os.environ.get("FLEET_TEST_MODE") != "1" and "pytest" not in sys.modules:
        try:
            LATEST_VERSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            LATEST_VERSION_CACHE_FILE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    return result


def get_cached_version_check(max_age_sec: float = 300.0) -> Dict[str, Any]:
    """Returns the most recent version check result without blocking if checked within `max_age_sec`."""
    live_ver = get_live_version()
    if _LAST_CHECK_CACHE and (time.time() - _LAST_CHECK_TS) < max_age_sec:
        cached = dict(_LAST_CHECK_CACHE)
        cached["current_version"] = live_ver
        cached["update_available"] = parse_version_tuple(str(cached.get("latest_version") or live_ver)) > parse_version_tuple(live_ver)
        cached["up_to_date"] = not cached["update_available"]
        return cached
    if LATEST_VERSION_CACHE_FILE.is_file():
        try:
            data = json.loads(LATEST_VERSION_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["current_version"] = live_ver
                data["update_available"] = parse_version_tuple(str(data.get("latest_version") or live_ver)) > parse_version_tuple(live_ver)
                data["up_to_date"] = not data["update_available"]
                return data
        except Exception:
            pass
    return {
        "status": "cached",
        "current_version": live_ver,
        "latest_version": live_ver,
        "update_available": False,
        "up_to_date": True,
        "checked_at": datetime.now().isoformat(),
    }


def ensure_latest_version_before_launch(
    repo_root: Optional[Path] = None,
    auto_apply: bool = True,
    timeout_sec: float = 3.5,
) -> Dict[str, Any]:
    """
    Automatically verifies before/during AFCC launch whether a newer version is available
    on a sibling workspace drive or on GitHub (`origin/main` / Releases), and pulls/applies
    it automatically when `auto_apply=True` so AFCC always launches the latest version.
    """
    root = (repo_root or Path(__file__).resolve().parent.parent.parent).resolve()
    local_ver_before = get_live_version()
    upgraded = False
    upgrade_source = "none"

    if os.environ.get("FLEET_TEST_MODE") == "1" or "pytest" in sys.modules:
        return {
            "status": "skipped_test",
            "version_before": local_ver_before,
            "version_after": local_ver_before,
            "upgraded": False,
            "up_to_date": True,
        }

    # 1. Check sibling drive workspace parity (Z: <-> C:)
    try:
        rel_parts = root.parts[1:]
        if rel_parts:
            cur_drive = root.drive.upper()
            sibling_drive = "Z:\\" if cur_drive.startswith("C") else "C:\\"
            sibling_root = Path(sibling_drive).joinpath(*rel_parts)
            sibling_init = sibling_root / "fleet" / "__init__.py"
            if sibling_init.is_file():
                s_txt = sibling_init.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', s_txt)
                if m:
                    sibling_ver = m.group(1).strip()
                    if parse_version_tuple(sibling_ver) > parse_version_tuple(local_ver_before) and auto_apply:
                        subprocess.run(
                            ["git", "-C", str(root), "fetch", str(sibling_root), "HEAD"],
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                        subprocess.run(
                            ["git", "-C", str(root), "merge", "--ff-only", "FETCH_HEAD"],
                            capture_output=True,
                            timeout=10,
                            check=False,
                        )
                        upgraded = True
                        upgrade_source = f"sibling_workspace ({sibling_drive})"
    except Exception:
        pass

    # 2. Check GitHub Releases & main branch for newer version
    check_res = check_github_for_updates(timeout_sec=timeout_sec)
    latest_remote_ver = str(check_res.get("latest_version") or local_ver_before)
    if check_res.get("update_available") and auto_apply:
        pull_res = download_and_apply_update(repo_root=root)
        if pull_res.get("status") == "success" and pull_res.get("restart_required"):
            upgraded = True
            upgrade_source = "github_origin_main"
            check_res = check_github_for_updates(timeout_sec=timeout_sec)

    local_ver_after = get_live_version()
    return {
        "status": check_res.get("status", "success"),
        "version_before": local_ver_before,
        "version_after": local_ver_after,
        "latest_version": latest_remote_ver,
        "upgraded": upgraded or (parse_version_tuple(local_ver_after) > parse_version_tuple(local_ver_before)),
        "upgrade_source": upgrade_source,
        "update_available": parse_version_tuple(latest_remote_ver) > parse_version_tuple(local_ver_after),
        "up_to_date": parse_version_tuple(local_ver_after) >= parse_version_tuple(latest_remote_ver),
        "checked_at": check_res.get("checked_at", datetime.now().isoformat()),
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

