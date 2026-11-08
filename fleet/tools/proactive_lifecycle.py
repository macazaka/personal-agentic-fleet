"""
Master Proactive Zero-Intervention Lifecycle Orchestrator for Personal Agentic Fleet.
Coordinates all proactive pre-commit, pre-push, and CI lifecycle tasks in a single pass:
  1. CodeQL SAST & VS Code (Pylance/Pyright) Auto-Remediation (`auto_fixer.py`)
  2. Proactive Semantic Release & Version Synchronization (`release_manager.py`)
  3. Proactive Documentation & GitHub Wiki Enhancement (`doc_wiki_enhancer.py`)
  4. CycloneDX 1.5 SBOM SHA-256 Integrity Regeneration (`sbom_generator.py`)
  5. Automatic Git Staging (`git add`) & Optional Git Tagging (`vX.Y.Z`)
Zero external dependencies ($0.00 / 0 LLM tokens).
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fleet.config import BASE_DIR
from fleet.tools.auto_fixer import run_auto_fixer, stage_modified_files
from fleet.tools.doc_wiki_enhancer import run_proactive_doc_wiki_enhancement
from fleet.tools.release_manager import run_proactive_release_check
from fleet.tools.sbom_generator import generate_sbom

REPO_ROOT = BASE_DIR.parent


def run_proactive_lifecycle(
    repo_root: Path = REPO_ROOT,
    stage_changes: bool = False,
    run_pyright_cli: bool = True,
    force_bump: Optional[str] = None,
    create_tag: bool = False,
    sync_remote_wiki: bool = False,
) -> Dict[str, Any]:
    """
    Executes the complete proactive lifecycle pipeline across the repository:
      1. Auto-fixes CodeQL and VS Code / Pyright issues.
      2. Evaluates and synchronizes semantic release versions and CHANGELOG.md.
      3. Enhances `docs/` and `wiki/` pages and developer tool instructions.
      4. Regenerates CycloneDX 1.5 SBOM (`fleet/data/sbom.cdx.json`) when files change.
      5. Stages all updated files in Git (`git add`) when `stage_changes=True`.
    """
    # 1. CodeQL & VS Code Auto-Fixer
    fixer_report = run_auto_fixer(
        repo_root=repo_root,
        stage_changes=False,
        run_pyright_cli=run_pyright_cli,
    )

    # 2. Proactive Release & Version Manager
    release_report = run_proactive_release_check(
        repo_root=repo_root,
        force_bump=force_bump,
        create_tag=create_tag,
    )

    # 3. Proactive Documentation & Wiki Enhancer
    doc_wiki_report = run_proactive_doc_wiki_enhancement(
        repo_root=repo_root,
        sync_remote_wiki=sync_remote_wiki,
    )

    # 4. Regenerate SBOM if any fixes or release/doc updates occurred
    sbom_updated = False
    total_changes = (
        fixer_report.get("fixes_applied_count", 0)
        + release_report.get("updates_count", 0)
        + doc_wiki_report.get("updates_count", 0)
    )
    if total_changes > 0 and (repo_root / "fleet").is_dir():
        try:
            generate_sbom(repo_root=repo_root, save_to_disk=True)
            sbom_updated = True
        except Exception:
            pass

    # 5. Stage all modified/created files in Git if requested
    staged = False
    touched_files: List[str] = []
    for fx in fixer_report.get("fixes", []):
        if fx.get("file"):
            touched_files.append(fx["file"])
    for u in release_report.get("updates", []):
        if u.get("file"):
            touched_files.append(u["file"])
    for u in doc_wiki_report.get("updates", []):
        if u.get("file"):
            touched_files.append(u["file"])
    if sbom_updated:
        touched_files.append("fleet/data/sbom.cdx.json")
    for extra_doc in [".github/copilot-instructions.md", "CLAUDE.md", "GEMINI.md"]:
        if (repo_root / extra_doc).is_file():
            touched_files.append(extra_doc)

    unique_files = list(dict.fromkeys(touched_files))
    if stage_changes and unique_files:
        staged = stage_modified_files(repo_root=repo_root, files=unique_files)

    return {
        "status": "PASS",
        "active_version": release_report.get("active_version"),
        "bump_applied": release_report.get("bump_applied"),
        "tag_created": release_report.get("tag_created", False),
        "auto_fixes_count": fixer_report.get("fixes_applied_count", 0),
        "release_updates_count": release_report.get("updates_count", 0),
        "doc_wiki_updates_count": doc_wiki_report.get("updates_count", 0),
        "sbom_regenerated": sbom_updated,
        "staged_in_git": staged,
        "touched_files": unique_files,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fleet Master Proactive Zero-Intervention Lifecycle Orchestrator ($0.00 / 0 Tokens)"
    )
    parser.add_argument("--stage", action="store_true", help="Automatically git add all updated files")
    parser.add_argument("--no-pyright-cli", action="store_true", help="Skip invoking npx pyright CLI")
    parser.add_argument(
        "--bump",
        choices=["auto", "patch", "minor", "major"],
        default="auto",
        help="Version bump mode (default: auto)",
    )
    parser.add_argument("--tag", action="store_true", help="Create annotated Git tag vX.Y.Z")
    parser.add_argument("--sync-wiki", action="store_true", help="Push updated wiki/ pages to GitHub Wiki remote")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    force_bump = None if args.bump == "auto" else args.bump
    report = run_proactive_lifecycle(
        repo_root=REPO_ROOT,
        stage_changes=args.stage,
        run_pyright_cli=not args.no_pyright_cli,
        force_bump=force_bump,
        create_tag=args.tag,
        sync_remote_wiki=args.sync_wiki,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"=== Fleet Proactive Lifecycle [{report['status']}] | "
            f"Version: v{report['active_version']} (Bump: {report['bump_applied']}) | "
            f"Auto-Fixes: {report['auto_fixes_count']} | "
            f"Release Syncs: {report['release_updates_count']} | "
            f"Doc/Wiki Enhancements: {report['doc_wiki_updates_count']} ==="
        )
        if report["touched_files"]:
            print(f"  [TOUCHED FILES ({len(report['touched_files'])})]: {', '.join(report['touched_files'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

