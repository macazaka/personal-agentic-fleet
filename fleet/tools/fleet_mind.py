"""
Fleet Mind CLI — Command-line introspection & trigger for the 4 cognitive layers.
Brain, Consciousness, Subconsciousness, and Soul.
Deterministic, zero-token ($0.00) operation.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fleet.config import DB_PATH
from fleet.core.database import FleetDatabase
from fleet.core.mind import fleet_mind


def format_status_text(state: Dict[str, Any]) -> str:
    layers = state.get("layers", {})
    brain = layers.get("brain", {})
    cons = layers.get("consciousness", {})
    subc = layers.get("subconsciousness", {})
    soul = layers.get("soul", {})
    harmony = state.get("cognitive_harmony_index", 100.0)
    overall = state.get("overall_state", "COHERENT")

    lines = [
        "=" * 68,
        f"  🧠 PERSONAL AGENTIC FLEET — COGNITIVE MIND STATUS",
        "=" * 68,
        f"  Harmonic Index : {harmony}/100 [{overall}]",
        f"  Timestamp      : {state.get('timestamp', '-')}",
        "-" * 68,
        "  1. BRAIN (Physical & Neurological Substrate):",
        f"     • Health Score   : {brain.get('health_score', 100.0)}%",
        f"     • Synapses Fired : {brain.get('synapses_fired', 0)}",
        f"     • Memory (RAM)   : {brain.get('working_memory', {}).get('rss_mb', 0.0)} MB | {brain.get('working_memory', {}).get('threads', 0)} threads",
        f"     • Epistemic DB   : {brain.get('epistemic_memory', {}).get('database_size_bytes', 0)} bytes ({brain.get('epistemic_memory', {}).get('activities_count', 0)} logs, {brain.get('epistemic_memory', {}).get('tasks_count', 0)} tasks)",
        "-" * 68,
        "  2. CONSCIOUSNESS (Executive Focus & Meta-Critique):",
        f"     • Active State   : {cons.get('executive_attention', {}).get('state', 'AWARE')}",
        f"     • Focused Agent  : {cons.get('executive_attention', {}).get('active_agent', 'None')}",
        f"     • Current Goal   : {cons.get('executive_attention', {}).get('current_goal', 'None')}",
        f"     • Total Critiques: {cons.get('meta_critique_vitals', {}).get('total_critiques_logged', 0)}",
        f"     • Average Quality: {cons.get('meta_critique_vitals', {}).get('average_quality_score', 100.0)}/100",
        "-" * 68,
        "  3. SUBCONSCIOUSNESS (Memory Consolidation & Dreaming):",
        f"     • State          : {subc.get('subconscious_state', 'DORMANT')}",
        f"     • Insights Stored: {subc.get('insights_stored', 0)}",
        f"     • Last Dream     : {subc.get('last_dream_timestamp', 'Never')}",
        "-" * 68,
        "  4. SOUL (Teleological Purpose & Moral Compass):",
        f"     • Alignment Score: {soul.get('latest_audit', {}).get('alignment_score', 100.0) if soul.get('latest_audit') else 100.0}/100",
        f"     • Generation     : Gen {soul.get('evolution_metrics', {}).get('current_generation', 1)}",
        f"     • Tenets Count   : {len(soul.get('core_tenets', []))} inviolable tenets",
        "=" * 68,
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Fleet Cognitive Mind Diagnostic & Control Tool")
    parser.add_argument("--status", action="store_true", help="Print holistic cognitive mind status")
    parser.add_argument("--dream", action="store_true", help="Trigger an immediate subconscious dream cycle")
    parser.add_argument("--soul", action="store_true", help="Run a teleological soul alignment audit")
    parser.add_argument("--heal", action="store_true", help="Trigger autonomic self-healing reflex arc")
    parser.add_argument("--improve", action="store_true", help="Execute evolutionary self-improvement")
    parser.add_argument("--critique", nargs=2, metavar=("AGENT", "ACTION"), help="Evaluate an agent action")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data")

    args = parser.parse_args()
    db = FleetDatabase(db_path=DB_PATH)
    fleet_mind.set_db(db)

    # Default to status if no specific action provided
    if not (args.status or args.dream or args.soul or args.heal or args.improve or args.critique):
        args.status = True

    if args.dream:
        result = fleet_mind.dream(max_activities=200)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("🌙 Subconscious Dream Cycle Completed:")
            print(f"  Cycle ID     : {result.get('cycle_id')}")
            print(f"  Consolidated : {result.get('events_consolidated', 0)} events in {result.get('duration_sec', 0)}s")
            print(f"  Insights     : {result.get('insights_synthesized_count', 0)}")
            print(f"  Remediations : {result.get('autonomic_remediations_count', 0)}")
            for ins in result.get("insights", []):
                print(f"    • [{ins.get('insight_type')}] {ins.get('title')}: {ins.get('description')}")
        return 0

    if args.soul:
        audit = fleet_mind.audit_soul()
        if args.json:
            print(json.dumps(audit.to_dict(), indent=2))
        else:
            print("🧭 Fleet Soul Alignment Audit Completed:")
            print(f"  Score     : {audit.alignment_score}/100 [{audit.status}]")
            print(f"  Violations: {len(audit.violations)}")
            for v in audit.violations:
                print(f"    - {v}")
            print(f"  Recommendations:")
            for r in audit.evolutionary_recommendations:
                print(f"    • {r}")
        return 0

    if args.heal:
        res = fleet_mind.heal()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("🩺 Autonomic Self-Healing Reflex Executed:")
            print(f"  Status   : {res.get('status')}")
            print(f"  Anomalies: {len(res.get('anomalies_detected', []))}")
            print(f"  Repairs  : {len(res.get('auto_repairs_applied', []))}")
        return 0

    if args.improve:
        res = fleet_mind.self_improve()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("🌱 Evolutionary Self-Improvement Cycle Completed:")
            print(f"  Generation : {res.get('generation')}")
            print(f"  Enhancements: {len(res.get('enhancements', []))}")
            for enh in res.get('enhancements', []):
                print(f"    • {enh}")
        return 0

    if args.critique:
        agent, action = args.critique
        res = fleet_mind.critique(agent=agent, action=action, input_payload={}, output_result={"status": "ok"})
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print("👁️ Conscious Meta-Critique Evaluation:")
            print(f"  Score  : {res.score}/100 [{'PASS' if res.passed else 'FAIL'}]")
            print(f"  Notes  : {res.notes}")
        return 0

    if args.status:
        state = fleet_mind.get_holistic_state()
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print(format_status_text(state))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
