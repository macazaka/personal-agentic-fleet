"""
Proactive Semantic Release & Version Synchronization Engine for Personal Agentic Fleet.
Automatically determines when a version bump (MAJOR / MINOR / PATCH) is warranted based on
Git commits and staged changes, updates CHANGELOG.md with categorized release notes,
and synchronizes the release version across all repository artifacts:
  - fleet/__init__.py
  - fleet/config.py
  - pyproject.toml
  - fleet/web/templates/dashboard.html
  - README.md
  - CHANGELOG.md
  - wiki/Home.md, wiki/_Footer.md, wiki/_Sidebar.md
  - fleet/data/sbom.cdx.json
Zero external dependencies ($0.00 / 0 LLM tokens).
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR

REPO_ROOT = BASE_DIR.parent


def _hidden_subprocess_kwargs() -> Dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def _git_exe() -> str:
    git_bin = shutil.which("git") or "git"
    fallback_git = Path(os.path.expanduser(r"~\AppData\Local\Programs\Git\cmd\git.exe"))
    if fallback_git.is_file():
        git_bin = str(fallback_git)
    return git_bin


def parse_semver(v_str: str) -> Tuple[int, int, int]:
    """Parses 'v2.5.0' or '2.5.0' into a (major, minor, patch) integer tuple."""
    cleaned = v_str.strip().lstrip("vV")
    parts = [int(p) for p in re.findall(r"\d+", cleaned)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2])


def format_semver(parts: Tuple[int, int, int]) -> str:
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def bump_semver(v_str: str, level: str) -> str:
    """Bumps a semantic version string by 'major', 'minor', or 'patch'."""
    major, minor, patch = parse_semver(v_str)
    lvl = level.strip().lower()
    if lvl == "major":
        return f"{major + 1}.0.0"
    if lvl == "minor":
        return f"{major}.{minor + 1}.0"
    if lvl == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return format_semver((major, minor, patch))


def get_current_configured_version(repo_root: Path = REPO_ROOT) -> str:
    """Reads the currently configured VERSION from fleet/config.py or fleet/__init__.py."""
    cfg_path = repo_root / "fleet" / "config.py"
    if cfg_path.is_file():
        m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', cfg_path.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1).strip()
    init_path = repo_root / "fleet" / "__init__.py"
    if init_path.is_file():
        m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_path.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1).strip()
    return "2.5.0"


def get_head_committed_version(repo_root: Path = REPO_ROOT) -> str:
    """Returns the semantic version committed in Git HEAD (e.g. '2.8.2'), or '' if unavailable."""
    if not (repo_root / ".git").exists():
        return ""
    try:
        res = subprocess.run(
            [_git_exe(), "-C", str(repo_root), "show", "HEAD:fleet/__init__.py"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        if res.returncode == 0 and res.stdout:
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', res.stdout)
            if m:
                return format_semver(parse_semver(m.group(1).strip()))
    except Exception:
        pass
    return ""


def get_latest_git_tag(repo_root: Path = REPO_ROOT) -> str:
    """Returns the highest semantic version tag (e.g. 'v2.5.0') in the repository."""
    try:
        # Ensure any version already committed in HEAD is tagged locally so tags never lag behind HEAD releases
        head_ver = get_head_committed_version(repo_root)
        res = subprocess.run(
            [_git_exe(), "-C", str(repo_root), "tag", "-l", "v*.*.*"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        tags: List[str] = []
        if res.returncode == 0 and res.stdout.strip():
            tags = [t.strip() for t in res.stdout.splitlines() if re.match(r"^v\d+\.\d+\.\d+$", t.strip())]
        if head_ver:
            head_tag = f"v{head_ver}"
            if head_tag not in tags and (not tags or parse_semver(head_tag) > max(parse_semver(t) for t in tags)):
                if ensure_git_tag(repo_root, head_ver):
                    tags.append(head_tag)
        if tags:
            tags.sort(key=parse_semver)
            return tags[-1]
    except Exception:
        pass
    return ""


def get_commits_since_tag(repo_root: Path = REPO_ROOT, tag: str = "") -> List[Dict[str, str]]:
    """Returns commits since `tag` (or last 30 commits if no tag exists)."""
    rev_range = f"{tag}..HEAD" if tag else "-n 30"
    cmd = [_git_exe(), "-C", str(repo_root), "log"]
    if tag:
        cmd.append(rev_range)
    else:
        cmd.extend(["-n", "30"])
    cmd.append("--pretty=format:%h|%s")
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        commits: List[Dict[str, str]] = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                if "|" in line:
                    sha, subj = line.split("|", 1)
                    commits.append({"sha": sha.strip(), "subject": subj.strip()})
        return commits
    except Exception:
        return []


def get_staged_or_modified_files(repo_root: Path = REPO_ROOT) -> List[str]:
    """Returns list of staged or modified file paths relative to repo_root."""
    try:
        res = subprocess.run(
            [_git_exe(), "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        files: List[str] = []
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if len(line) > 3:
                    files.append(line[3:].strip().replace("\\", "/"))
        return files
    except Exception:
        return []


def determine_bump_level(commits: List[Dict[str, str]], changed_files: Optional[List[str]] = None) -> str:
    """
    Determines semantic version bump level ('major', 'minor', 'patch', or 'none')
    based on Conventional Commits and modified files since the last release tag.
    """
    changed = changed_files or []
    has_minor = False
    has_patch = False

    for c in commits:
        subj = c.get("subject", "").strip()
        if "BREAKING CHANGE" in subj or re.match(r"^[a-z]+(\([^)]+\))?!:", subj):
            return "major"
        if re.match(r"^feat(\([^)]+\))?:", subj, re.I):
            has_minor = True
        elif re.match(r"^(fix|security|perf|refactor)(\([^)]+\))?:", subj, re.I):
            has_patch = True

    for f in changed:
        if f.startswith("fleet/agents/") and f.endswith("manifest.json"):
            has_minor = True
        elif f.startswith(("fleet/", ".github/workflows/")) and f.endswith((".py", ".html", ".js", ".css", ".yml")):
            has_patch = True

    if has_minor:
        return "minor"
    if has_patch:
        return "patch"
    return "none"


def synthesize_changelog_section(
    version: str,
    commits: List[Dict[str, str]],
    release_date: Optional[str] = None,
) -> str:
    """
    Synthesizes a Keep-a-Changelog compliant markdown section (`## [X.Y.Z] - YYYY-MM-DD`)
    grouped into Added, Security, Fixed, and Documentation & Maintenance.
    """
    date_str = release_date or datetime.now().strftime("%Y-%m-%d")
    added: List[str] = []
    security: List[str] = []
    fixed: List[str] = []
    docs_maint: List[str] = []

    seen_subjects = set()
    for c in commits:
        subj = c.get("subject", "").strip()
        if not subj or subj.lower().startswith("merge "):
            continue
        # Clean conventional prefix for readability while keeping scope
        m = re.match(r"^([a-zA-Z]+)(?:\(([^)]+)\))?!?:\s*(.+)$", subj)
        if m:
            ctype = m.group(1).lower()
            scope = m.group(2) or ""
            desc = m.group(3).strip()
            formatted = f"**{scope.upper() if len(scope) <= 3 else scope.replace('-', ' ').title()}**: {desc[0].upper() + desc[1:]}" if scope else (desc[0].upper() + desc[1:])
        else:
            ctype = "other"
            formatted = subj[0].upper() + subj[1:]

        if not formatted.endswith("."):
            formatted += "."

        norm_key = formatted.lower()
        if norm_key in seen_subjects:
            continue
        seen_subjects.add(norm_key)

        if ctype == "feat":
            added.append(f"- {formatted}")
        elif ctype == "security" or "codeql" in subj.lower() or "security" in subj.lower():
            security.append(f"- {formatted}")
        elif ctype in ("fix", "perf", "refactor"):
            fixed.append(f"- {formatted}")
        else:
            docs_maint.append(f"- {formatted}")

    if not (added or security or fixed or docs_maint):
        fixed.append("- Proactive release synchronization, static type verification, and documentation maintenance.")

    lines = [f"## [{version}] - {date_str}", ""]
    if added:
        lines.append("### Added")
        lines.extend(added)
        lines.append("")
    if security:
        lines.append("### Security")
        lines.extend(security)
        lines.append("")
    if fixed:
        lines.append("### Fixed")
        lines.extend(fixed)
        lines.append("")
    if docs_maint:
        lines.append("### Documentation & Maintenance")
        lines.extend(docs_maint)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def update_changelog(
    repo_root: Path,
    version: str,
    commits: List[Dict[str, str]],
    release_date: Optional[str] = None,
) -> bool:
    """
    Inserts or updates the `## [version]` section in CHANGELOG.md.
    Returns True if CHANGELOG.md was modified.
    """
    changelog_path = repo_root / "CHANGELOG.md"
    if not changelog_path.is_file():
        return False

    content = changelog_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
    new_section = synthesize_changelog_section(version, commits, release_date=release_date)

    # Check if `## [version]` already exists in CHANGELOG.md
    existing_pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(?:.*?\n)*?(?=^---\n\n## \[|^## \[|\Z)",
        re.M,
    )
    if existing_pattern.search(content):
        updated = existing_pattern.sub(new_section + "\n", content, count=1)
    else:
        # Insert before the first `## [` heading
        first_ver_match = re.search(r"^## \[\d+\.\d+\.\d+\]", content, re.M)
        if first_ver_match:
            idx = first_ver_match.start()
            updated = content[:idx] + new_section + "\n---\n\n" + content[idx:]
        else:
            updated = content.rstrip() + "\n\n---\n\n" + new_section

    if updated != content:
        changelog_path.write_text(updated, encoding="utf-8", newline="\n")
        return True
    return False


def sync_version_everywhere(repo_root: Path = REPO_ROOT, target_version: str = "2.6.0") -> List[Dict[str, Any]]:
    """
    Synchronizes `target_version` across all code, package, UI, README, Wiki, and SBOM files.
    """
    updates: List[Dict[str, Any]] = []
    clean_ver = format_semver(parse_semver(target_version))

    # 1. fleet/__init__.py
    init_path = repo_root / "fleet" / "__init__.py"
    if init_path.is_file():
        txt = init_path.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r'(__version__\s*=\s*["\'])[^"\']+(["\'])', rf"\g<1>{clean_ver}\2", txt)
        if new_txt != txt:
            init_path.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "fleet/__init__.py", "detail": f"Updated __version__ to {clean_ver}"})

    # 2. fleet/config.py
    cfg_path = repo_root / "fleet" / "config.py"
    if cfg_path.is_file():
        txt = cfg_path.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r'(VERSION\s*=\s*["\'])[^"\']+(["\'])', rf"\g<1>{clean_ver}\2", txt)
        if new_txt != txt:
            cfg_path.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "fleet/config.py", "detail": f"Updated VERSION to {clean_ver}"})

    # 3. pyproject.toml
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.is_file():
        txt = pyproject_path.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r'^(version\s*=\s*["\'])[^"\']+(["\'])', rf"\g<1>{clean_ver}\2", txt, count=1, flags=re.M)
        if new_txt != txt:
            pyproject_path.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "pyproject.toml", "detail": f"Updated package version to {clean_ver}"})

    # 4. fleet/web/templates/dashboard.html
    dash_path = repo_root / "fleet" / "web" / "templates" / "dashboard.html"
    if dash_path.is_file():
        txt = dash_path.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(
            r'(<span id="fleetHeaderVerBadge">)v[^<]+(</span>)',
            rf"\g<1>v{clean_ver}\2",
            txt,
        )
        new_txt = re.sub(
            r'(id="currentReleaseVerLabel">Current Release:\s*)v[^<]+(</div>)',
            rf"\g<1>v{clean_ver}\2",
            new_txt,
        )
        if new_txt != txt:
            dash_path.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "fleet/web/templates/dashboard.html", "detail": f"Synchronized UI version badges to v{clean_ver}"})

    # 5. README.md release badge
    readme_path = repo_root / "README.md"
    if readme_path.is_file():
        txt = readme_path.read_text(encoding="utf-8", errors="ignore")
        badge_md = f"[![Release: v{clean_ver}](https://img.shields.io/badge/Release-v{clean_ver}-00b4d8.svg)](CHANGELOG.md)"
        if "img.shields.io/badge/Release-v" in txt:
            new_txt = re.sub(
                r"\[!\[Release:\s*v[^\]]+\]\(https://img\.shields\.io/badge/Release-v[^)]+\)\]\(CHANGELOG\.md\)",
                badge_md,
                txt,
            )
        else:
            # Insert right before Python badge
            new_txt = txt.replace(
                "[![Python](https://img.shields.io/badge/Python-",
                badge_md + "\n[![Python](https://img.shields.io/badge/Python-",
                1,
            )
        if new_txt != txt:
            readme_path.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "README.md", "detail": f"Synchronized README release badge to v{clean_ver}"})

    # 6. wiki/_Footer.md & wiki/_Sidebar.md & wiki/Home.md
    wiki_footer = repo_root / "wiki" / "_Footer.md"
    if wiki_footer.is_file():
        txt = wiki_footer.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r"Personal Agentic Fleet v\d+\.\d+\.\d+", f"Personal Agentic Fleet v{clean_ver}", txt)
        if new_txt != txt:
            wiki_footer.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "wiki/_Footer.md", "detail": f"Synchronized Wiki footer version to v{clean_ver}"})

    wiki_home = repo_root / "wiki" / "Home.md"
    if wiki_home.is_file():
        txt = wiki_home.read_text(encoding="utf-8", errors="ignore")
        w_badge = f"[![Release: v{clean_ver}](https://img.shields.io/badge/Release-v{clean_ver}-00b4d8.svg)](Release-Notes)"
        if "img.shields.io/badge/Release-v" in txt:
            new_txt = re.sub(
                r"\[!\[Release:\s*v[^\]]+\]\(https://img\.shields\.io/badge/Release-v[^)]+\)\]\([^)]+\)",
                w_badge,
                txt,
            )
        else:
            new_txt = txt.replace(
                "[![Python](https://img.shields.io/badge/Python-",
                w_badge + "\n[![Python](https://img.shields.io/badge/Python-",
                1,
            )
        if new_txt != txt:
            wiki_home.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "wiki/Home.md", "detail": f"Synchronized Wiki Home release badge to v{clean_ver}"})

    # 6b. wiki/_Sidebar.md
    wiki_sidebar = repo_root / "wiki" / "_Sidebar.md"
    if wiki_sidebar.is_file():
        txt = wiki_sidebar.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r'(\- \*\*Release:\*\* `v)\d+\.\d+\.\d+(`)', rf"\g<1>{clean_ver}\2", txt)
        if new_txt != txt:
            wiki_sidebar.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "wiki/_Sidebar.md", "detail": f"Synchronized Wiki sidebar release version to v{clean_ver}"})

    # 6c. wiki/Release-Notes.md
    wiki_rel_notes = repo_root / "wiki" / "Release-Notes.md"
    if wiki_rel_notes.is_file():
        txt = wiki_rel_notes.read_text(encoding="utf-8", errors="ignore")
        new_txt = re.sub(r'(# Release Notes & Version History \(Current: `v)\d+\.\d+\.\d+(`\))', rf"\g<1>{clean_ver}\2", txt)
        if new_txt != txt:
            wiki_rel_notes.write_text(new_txt, encoding="utf-8", newline="\n")
            updates.append({"file": "wiki/Release-Notes.md", "detail": f"Synchronized Wiki Release Notes header to v{clean_ver}"})

    # 6d. wiki/CLI-and-Automation-Tools.md & all wiki/*.md Release Version headers
    wiki_dir = repo_root / "wiki"
    if wiki_dir.is_dir():
        for wfile in sorted(wiki_dir.glob("*.md")):
            txt = wfile.read_text(encoding="utf-8", errors="ignore")
            new_txt = re.sub(
                r'(# Unified Fleet CLI & Proactive Automation Tools \(`v)\d+\.\d+\.\d+(`\))',
                rf"\g<1>{clean_ver}\2",
                txt,
            )
            new_txt = re.sub(
                r'(\*\*Release Version\*\*:\s*`v)\d+\.\d+\.\d+(`)',
                rf"\g<1>{clean_ver}\2",
                new_txt,
            )
            if new_txt != txt:
                wfile.write_text(new_txt, encoding="utf-8", newline="\n")
                updates.append({"file": f"wiki/{wfile.name}", "detail": f"Synchronized Wiki page release version to v{clean_ver}"})

    # 7. Update CycloneDX SBOM version
    sbom_path = repo_root / "fleet" / "data" / "sbom.cdx.json"
    if sbom_path.is_file():
        try:
            sbom_data = json.loads(sbom_path.read_text(encoding="utf-8"))
            comp_ver = sbom_data.get("metadata", {}).get("component", {}).get("version")
            if comp_ver != clean_ver:
                sbom_data.setdefault("metadata", {}).setdefault("component", {})["version"] = clean_ver
                for comp in sbom_data.get("components", []):
                    if comp.get("type") == "library":
                        comp["version"] = clean_ver
                sbom_path.write_text(json.dumps(sbom_data, indent=2) + "\n", encoding="utf-8", newline="\n")
                updates.append({"file": "fleet/data/sbom.cdx.json", "detail": f"Synchronized SBOM component version to {clean_ver}"})
        except Exception:
            pass

    return updates


def ensure_git_tag(repo_root: Path = REPO_ROOT, version: str = "") -> bool:
    """Creates local Git tag `v{version}` if it does not already exist."""
    clean_ver = format_semver(parse_semver(version or get_current_configured_version(repo_root)))
    tag_name = f"v{clean_ver}"
    try:
        chk = subprocess.run(
            [_git_exe(), "-C", str(repo_root), "rev-parse", "-q", "--verify", f"refs/tags/{tag_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        if chk.returncode == 0:
            return False
        cr = subprocess.run(
            [_git_exe(), "-C", str(repo_root), "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            **_hidden_subprocess_kwargs(),
        )
        return cr.returncode == 0
    except Exception:
        return False


def ensure_workstation_version_parity(repo_root: Path = REPO_ROOT, target_version: str = "2.6.0") -> bool:
    """
    Ensures the local Agentic Fleet Control Center (AFCC) (`http://127.0.0.1:7890`) and any mirror
    workspace stay in 100% version parity with GitHub Releases.
    If the running AFCC reports an older in-memory version, stops and restarts it
    silently in the background so `/api/version` and `/api/status` immediately match `target_version`.
    """
    clean_ver = format_semver(parse_semver(target_version))
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return False

    # 1. Sync sibling drive mirror workspace if present and different from repo_root
    try:
        rel_parts = repo_root.resolve().parts[1:]
        if rel_parts:
            c_mirror = Path("C:\\").joinpath(*rel_parts)
            if c_mirror.is_dir() and c_mirror.resolve() != repo_root.resolve():
                sync_version_everywhere(c_mirror, clean_ver)
    except Exception:
        pass

    # 2. Check live Agentic Fleet Control Center (AFCC) at http://127.0.0.1:7890/api/version
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:7890/api/version", timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                live_ver = str(data.get("version", "")).strip()
                if live_ver and live_ver != clean_ver:
                    from fleet.cli import cmd_stop
                    cmd_stop(argparse.Namespace())
                    pythonw = Path(sys.executable).with_name("pythonw.exe")
                    exe = str(pythonw) if pythonw.is_file() else sys.executable
                    app_script = repo_root / "fleet" / "app.py"
                    if app_script.is_file():
                        subprocess.Popen(
                            [exe, str(app_script), "--no-browser"],
                            cwd=str(repo_root),
                            **_hidden_subprocess_kwargs(),
                        )
                        return True
    except Exception:
        pass
    return False


def run_proactive_release_check(
    repo_root: Path = REPO_ROOT,
    force_bump: Optional[str] = None,
    create_tag: bool = False,
) -> Dict[str, Any]:
    """
    Proactively evaluates whether the release version should be bumped or synchronized:
      - Compares current configured version against the latest Git tag (e.g. v2.5.0).
      - If commits or staged changes since the latest tag warrant a bump (and current_version <= latest_tag),
        automatically bumps the version (MAJOR / MINOR / PATCH).
      - Updates CHANGELOG.md and synchronizes the version across all repository files.
    """
    current_ver = get_current_configured_version(repo_root)
    latest_tag = get_latest_git_tag(repo_root)
    commits = get_commits_since_tag(repo_root, latest_tag)
    changed_files = get_staged_or_modified_files(repo_root)

    target_ver = current_ver
    bump_applied = "none"

    if force_bump and force_bump.lower() in ("major", "minor", "patch"):
        bump_applied = force_bump.lower()
        base_ver = latest_tag.lstrip("v") if latest_tag and parse_semver(latest_tag) > parse_semver(current_ver) else current_ver
        target_ver = bump_semver(base_ver, bump_applied)
    else:
        # Automatic proactive mode:
        # 1. If local version is behind the latest Git tag, sync up to latest_tag immediately.
        # 2. If local version equals latest_tag and a new feature (minor) or breaking change (major)
        #    landed since latest_tag, bump automatically so release.yml publishes the new GitHub Release.
        if latest_tag:
            if parse_semver(current_ver) < parse_semver(latest_tag):
                target_ver = format_semver(parse_semver(latest_tag))
                bump_applied = "sync_to_tag"
            elif parse_semver(current_ver) == parse_semver(latest_tag):
                auto_level = determine_bump_level(commits, changed_files)
                if auto_level in ("major", "minor", "patch"):
                    bump_applied = auto_level
                    target_ver = bump_semver(latest_tag, auto_level)
        elif not latest_tag and commits:
            target_ver = current_ver

    updates = sync_version_everywhere(repo_root, target_ver)

    # Update CHANGELOG.md if we bumped or if target_ver is newer than latest_tag
    if bump_applied != "none" or (latest_tag and parse_semver(target_ver) > parse_semver(latest_tag)) or not latest_tag:
        if commits or bump_applied != "none":
            if update_changelog(repo_root, target_ver, commits):
                updates.append({
                    "file": "CHANGELOG.md",
                    "detail": f"Synthesized/updated release notes for [{target_ver}] ({len(commits)} commit(s) since {latest_tag or 'initial'}).",
                })

    tag_created = False
    if create_tag:
        tag_created = ensure_git_tag(repo_root, target_ver)

    workstation_restarted = False
    if repo_root.resolve() == REPO_ROOT.resolve():
        workstation_restarted = ensure_workstation_version_parity(repo_root, target_ver)

    return {
        "status": "PASS",
        "previous_version": current_ver,
        "latest_git_tag": latest_tag or "none",
        "active_version": target_ver,
        "bump_applied": bump_applied,
        "commits_since_tag": len(commits),
        "tag_created": tag_created,
        "workstation_restarted": workstation_restarted,
        "updates_count": len(updates),
        "updates": updates,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fleet Proactive Semantic Release & Version Synchronization Engine ($0.00 / 0 Tokens)"
    )
    parser.add_argument(
        "--bump",
        choices=["auto", "patch", "minor", "major"],
        default="auto",
        help="Version bump mode (default: auto)",
    )
    parser.add_argument("--set-version", type=str, default="", help="Explicitly set version X.Y.Z")
    parser.add_argument("--tag", action="store_true", help="Create annotated Git tag vX.Y.Z")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    if args.set_version:
        clean_v = format_semver(parse_semver(args.set_version))
        latest_tag = get_latest_git_tag(REPO_ROOT)
        commits = get_commits_since_tag(REPO_ROOT, latest_tag)
        updates = sync_version_everywhere(REPO_ROOT, clean_v)
        if update_changelog(REPO_ROOT, clean_v, commits):
            updates.append({"file": "CHANGELOG.md", "detail": f"Updated release section [{clean_v}]"})
        tag_created = ensure_git_tag(REPO_ROOT, clean_v) if args.tag else False
        report = {
            "status": "PASS",
            "previous_version": get_current_configured_version(REPO_ROOT),
            "latest_git_tag": latest_tag or "none",
            "active_version": clean_v,
            "bump_applied": "explicit",
            "commits_since_tag": len(commits),
            "tag_created": tag_created,
            "updates_count": len(updates),
            "updates": updates,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        }
    else:
        force = None if args.bump == "auto" else args.bump
        report = run_proactive_release_check(repo_root=REPO_ROOT, force_bump=force, create_tag=args.tag)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"=== Fleet Proactive Release Manager [{report['status']}] | "
            f"Version: v{report['active_version']} (Bump: {report['bump_applied']}, Last Tag: {report['latest_git_tag']}) ==="
        )
        for u in report["updates"]:
            print(f"  [SYNCED] {u['file']} -> {u['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

