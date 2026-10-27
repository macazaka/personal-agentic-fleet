"""
System, Briefing, Notifications & Test Runner API endpoints for Personal Agentic Fleet.
"""

from datetime import datetime
import json
from typing import Any, Dict
import urllib.parse

from fleet.api.router import router
from fleet.config import CHANGELOG_PATH, VERSION, get_live_release_date, get_live_version
import fleet.server as srv


@router.get("/api/briefing")
def get_briefing(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.briefing_engine.generate_daily_briefing()
    handler._send_json(data)


@router.get("/api/logs")
def get_logs(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [15])[0])
    logs = srv.db.get_recent_activities(limit=limit)
    handler._send_json(logs)


@router.get("/api/status")
def get_status(handler: Any, parsed_url: urllib.parse.ParseResult):
    live_ver = get_live_version()
    disk = srv.get_disk_usage("C:")
    handler._send_json({
        "status": "online",
        "version": live_ver,
        "time": datetime.now().isoformat(),
        "disk": disk
    })


@router.get("/api/version")
def get_version(handler: Any, parsed_url: urllib.parse.ParseResult):
    live_ver = get_live_version()
    handler._send_json({
        "version": live_ver,
        "name": "Personal Agentic Fleet",
        "release_date": get_live_release_date(),
        "status": "operational"
    })


@router.get("/api/release_notes")
def get_release_notes(handler: Any, parsed_url: urllib.parse.ParseResult):
    live_ver = get_live_version()
    notes = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else "No release notes available."
    handler._send_json({
        "version": live_ver,
        "changelog_markdown": notes
    })


@router.post("/api/notify")
def post_notify(handler: Any, body: Dict[str, Any]):
    title = body.get("title", "Personal Agentic Fleet")
    message = body.get("message", "Notification from your fleet")
    success = srv.send_windows_notification(title, message)
    srv.db.log_activity("Notifier", "windows_toast", f"Sent Windows Toast: {title} - {message}")
    handler._send_json({"status": "sent", "success": success})


@router.get("/api/test_results")
def get_test_results(handler: Any, parsed_url: urllib.parse.ParseResult):
    latest = srv.db.get_latest_test_run()
    if not latest:
        from fleet.tools.test_runner import RESULTS_FILE
        if RESULTS_FILE.exists():
            try:
                latest = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
    handler._send_json(latest or {
        "pass_pct": 100.0,
        "total_tests": 0,
        "passed_tests": 0,
        "coverage_pct": 0.0,
        "status": "PASS",
        "timestamp": "-"
    })


@router.post("/api/run_tests")
def post_run_tests(handler: Any, body: Dict[str, Any]):
    from fleet.tools.test_runner import run_test_suite_isolated
    results = run_test_suite_isolated(srv.db)
    handler._send_json({"status": "success", "results": results})


@router.get("/api/security/scan")
def get_security_scan(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.tools.security_scanner import SCAN_REPORT_FILE, run_security_scan
    query = urllib.parse.parse_qs(parsed_url.query)
    refresh = query.get("refresh", ["false"])[0].lower() in ("true", "1")
    if not refresh and SCAN_REPORT_FILE.exists():
        try:
            report = json.loads(SCAN_REPORT_FILE.read_text(encoding="utf-8"))
            handler._send_json(report)
            return
        except Exception:
            pass
    report = run_security_scan()
    handler._send_json(report)


@router.post("/api/security/scan")
def post_security_scan(handler: Any, body: Dict[str, Any]):
    from fleet.tools.security_scanner import run_security_scan
    report = run_security_scan()
    srv.db.log_activity(
        "SecurityScanner",
        "security_scan",
        f"Security Scan completed: Score {report.get('score', 0)}/100 ({report.get('status', 'UNKNOWN')})"
    )
    handler._send_json({"status": "success", "report": report})


@router.get("/api/security/sbom")
def get_security_sbom(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.tools.sbom_generator import SBOM_FILE, generate_sbom
    query = urllib.parse.parse_qs(parsed_url.query)
    refresh = query.get("refresh", ["false"])[0].lower() in ("true", "1")
    if not refresh and SBOM_FILE.exists():
        try:
            sbom = json.loads(SBOM_FILE.read_text(encoding="utf-8"))
            handler._send_json(sbom)
            return
        except Exception:
            pass
    sbom = generate_sbom()
    handler._send_json(sbom)


@router.get("/api/security/token_stats")
def get_security_token_stats(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.core.token_optimizer import get_token_optimization_stats
    handler._send_json(get_token_optimization_stats())


@router.get("/api/security/doctor")
def get_security_doctor(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.tools.fleet_doctor import run_fleet_doctor
    handler._send_json(run_fleet_doctor())


@router.get("/api/diagnostics/log-analysis")
def get_log_analysis(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.core.auto_healer import get_latest_scan_report, run_proactive_log_scan_and_heal
    report = get_latest_scan_report()
    if not report:
        report = run_proactive_log_scan_and_heal(db=srv.db)
    handler._send_json({"status": "success", "report": report})


@router.post("/api/diagnostics/log-analysis/run")
def post_log_analysis_run(handler: Any, body: Dict[str, Any]):
    from fleet.core.auto_healer import run_proactive_log_scan_and_heal
    report = run_proactive_log_scan_and_heal(db=srv.db)
    handler._send_json({"status": "success", "report": report})


@router.get("/api/diagnostics/auto-improvements")
def get_auto_improvements(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.core.auto_healer import get_auto_improvements_history
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [50])[0])
    history = get_auto_improvements_history(limit=limit, db=srv.db)
    stats = srv.db.get_auto_improvements_stats() if hasattr(srv.db, "get_auto_improvements_stats") else {}
    handler._send_json({"status": "success", "improvements": history, "stats": stats, "count": len(history)})


# --- Cognitive Fleet Mind Routes ---

@router.get("/api/mind/status")
def get_mind_status(handler: Any, parsed_url: urllib.parse.ParseResult):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    handler._send_json(fleet_mind.get_holistic_state())


@router.get("/api/mind/insights")
def get_mind_insights(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [30])[0])
    insights = srv.db.list_dream_insights(limit=limit) if hasattr(srv.db, "list_dream_insights") else []
    handler._send_json({"status": "success", "insights": insights, "count": len(insights)})


@router.get("/api/mind/critiques")
def get_mind_critiques(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [30])[0])
    critiques = srv.db.list_critiques(limit=limit) if hasattr(srv.db, "list_critiques") else []
    handler._send_json({"status": "success", "critiques": critiques, "count": len(critiques)})


@router.get("/api/mind/soul/audits")
def get_mind_soul_audits(handler: Any, parsed_url: urllib.parse.ParseResult):
    query = urllib.parse.parse_qs(parsed_url.query)
    limit = int(query.get("limit", [10])[0])
    audits = srv.db.list_soul_audits(limit=limit) if hasattr(srv.db, "list_soul_audits") else []
    handler._send_json({"status": "success", "audits": audits, "count": len(audits)})


@router.post("/api/mind/critique")
def post_mind_critique(handler: Any, body: Dict[str, Any]):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    agent = body.get("agent", "FleetAgent")
    action = body.get("action", "custom_action")
    input_payload = body.get("input", {})
    output_result = body.get("result", {})
    critique = fleet_mind.critique(agent=agent, action=action, input_payload=input_payload, output_result=output_result)
    handler._send_json({"status": "success", "critique": critique.to_dict()})


@router.post("/api/mind/dream")
def post_mind_dream(handler: Any, body: Dict[str, Any]):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    max_activities = int(body.get("max_activities", 200))
    insight = fleet_mind.dream(max_activities=max_activities)
    handler._send_json({"status": "success", "insight": insight})


@router.post("/api/mind/soul/audit")
def post_mind_soul_audit(handler: Any, body: Dict[str, Any]):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    audit = fleet_mind.audit_soul()
    handler._send_json({"status": "success", "audit": audit.to_dict()})


@router.post("/api/mind/self_improve")
def post_mind_self_improve(handler: Any, body: Dict[str, Any]):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    res = fleet_mind.self_improve()
    handler._send_json(res)


@router.post("/api/mind/heal")
def post_mind_heal(handler: Any, body: Dict[str, Any]):
    from fleet.core.mind import fleet_mind
    fleet_mind.set_db(srv.db)
    res = fleet_mind.heal()
    handler._send_json(res)


