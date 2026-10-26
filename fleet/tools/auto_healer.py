"""
CLI Command & Autonomous Log Diagnostics Tool for Personal Agentic Fleet.
Usage:
    python -m fleet.tools.auto_healer
    python -m fleet.tools.auto_healer --history
    python -m fleet.tools.auto_healer --json
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure fleet package is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fleet.core.auto_healer import (
    get_auto_improvements_history,
    run_proactive_log_scan_and_heal,
)
from fleet.core.database import FleetDatabase


def main():
    parser = argparse.ArgumentParser(
        description="Personal Agentic Fleet Proactive Log Scanner & Autonomous Self-Healer."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON analysis and improvements report",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Display historical auto-improvements ledger",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max history records to display (default: 20)",
    )
    args = parser.parse_args()

    db = FleetDatabase()

    if args.history:
        history = get_auto_improvements_history(limit=args.limit, db=db)
        if args.json:
            print(json.dumps(history, indent=2, ensure_ascii=False))
        else:
            print("=" * 70)
            print(f"  AUTONOMOUS IMPROVEMENTS LEDGER (Last {len(history)} Events)")
            print("=" * 70)
            if not history:
                print("  No autonomous improvements recorded yet.")
            for h in history:
                ts = h.get("created_at", "N/A")
                status = h.get("status", "APPLIED")
                itype = h.get("issue_type", "GENERAL")
                action = h.get("action_taken", "")
                print(f"[{ts}] [{status}] [{itype}] {action}")
            print("=" * 70)
        return

    # Execute proactive log scan and auto-healing
    report = run_proactive_log_scan_and_heal(db=db)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=" * 70)
        print("  PROACTIVE LOG SCAN & AUTONOMOUS IMPROVEMENTS REPORT")
        print("=" * 70)
        print(f"  Scan ID:              {report['scan_id']}")
        print(f"  Timestamp:            {report['timestamp']}")
        print(f"  Health Status:        {report['status']} ({report['system_health_index']}/100.0)")
        print(f"  Logs Analyzed:        {report['logs_analyzed_count']}")
        print(f"  Issues Detected:      {report['issues_detected_count']}")
        print(f"  Improvements Applied: {report['improvements_applied_count']}")
        print("-" * 70)

        if report["findings"]:
            print("  ISSUES DETECTED:")
            for f in report["findings"]:
                print(f"    • [{f['severity']}] {f['title']}: {f['description']}")
            print("-" * 70)

        if report["improvements"]:
            print("  AUTOMATIC IMPROVEMENTS EXECUTED:")
            for imp in report["improvements"]:
                print(f"    ✓ [{imp['status']}] [{imp['issue_type']}] {imp['action_taken']}")
        else:
            print("  No improvements required; system logs and telemetry in prime condition.")
        print("=" * 70)


if __name__ == "__main__":
    main()
