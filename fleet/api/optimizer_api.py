"""
PC Optimizer API endpoints for Personal Agentic Fleet.
"""

from typing import Any, Dict
import urllib.parse
from fleet.api.router import router
import fleet.server as srv


@router.get("/api/optimizer/diagnostics")
def get_diagnostics(handler: Any, parsed_url: urllib.parse.ParseResult):
    data = srv.get_pc_performance_diagnostics()
    handler._send_json(data)


@router.post("/api/optimizer/clean_temp")
def post_clean_temp(handler: Any, body: Dict[str, Any]):
    res = srv.clean_temp_files()
    srv.db.log_activity("PCOptimizer", "clean_temp", res.get("message", "Cleaned temporary files"))
    handler._send_json(res)


@router.post("/api/optimizer/flush_dns")
def post_flush_dns(handler: Any, body: Dict[str, Any]):
    res = srv.flush_dns_cache()
    srv.db.log_activity("PCOptimizer", "flush_dns", res.get("message", "Flushed DNS resolver cache"))
    handler._send_json(res)


@router.post("/api/optimizer/purge_caches")
def post_purge_caches(handler: Any, body: Dict[str, Any]):
    res = srv.purge_dev_caches()
    srv.db.log_activity("PCOptimizer", "purge_caches", res.get("message", "Purged development caches"))
    handler._send_json(res)


@router.post("/api/optimizer/optimize_ram")
def post_optimize_ram(handler: Any, body: Dict[str, Any]):
    res = srv.optimize_ram()
    srv.db.log_activity("PCOptimizer", "optimize_ram", res.get("message", "Optimized RAM working sets"))
    handler._send_json(res)


@router.post("/api/optimizer/open_startup")
def post_open_startup(handler: Any, body: Dict[str, Any]):
    res = srv.open_startup_settings()
    srv.db.log_activity("PCOptimizer", "open_startup", "Opened Windows Startup Apps Settings")
    handler._send_json(res)


@router.get("/api/optimizer/upgrades")
def get_upgrades(handler: Any, parsed_url: urllib.parse.ParseResult):
    qs = urllib.parse.parse_qs(parsed_url.query or "")
    force_refresh = str((qs.get("refresh") or ["false"])[0]).lower() in ("1", "true", "yes")
    res = srv.check_os_and_software_upgrades(force_refresh=force_refresh)
    handler._send_json(res)


@router.post("/api/optimizer/upgrades/run")
def post_run_upgrades(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    mode = str(payload.get("mode") or "auto_manage").strip().lower()
    dry_run = bool(payload.get("dry_run", False))
    if mode in ("install_specific", "packages") or payload.get("package_ids"):
        pkg_ids = payload.get("package_ids")
        if isinstance(pkg_ids, str):
            pkg_ids = [x.strip() for x in pkg_ids.split(",") if x.strip()]
        res = srv.install_software_upgrades(
            package_ids=pkg_ids if isinstance(pkg_ids, list) else [],
            upgrade_all=bool(payload.get("upgrade_all", False)),
            include_os=bool(payload.get("include_os", False)),
            dry_run=dry_run,
        )
    else:
        res = srv.run_automatic_upgrade_manager(
            force_scan=bool(payload.get("force_scan", True)),
            dry_run=dry_run,
        )
    srv.db.log_activity("PCOptimizer", "manage_upgrades", res.get("message", "Executed OS & software upgrade manager"))
    handler._send_json(res)


@router.post("/api/optimizer/upgrades/policy")
def post_upgrade_policy(handler: Any, body: Dict[str, Any]):
    payload = body if isinstance(body, dict) else {}
    policy = srv.set_upgrade_policy(payload)
    srv.db.log_activity("PCOptimizer", "upgrade_policy", "Updated autonomous OS & software upgrade policy")
    handler._send_json({
        "status": "success",
        "policy": policy,
        "message": "Autonomous OS & Software Upgrade policy updated.",
    })


@router.post("/api/optimizer/auto_tune")
def post_auto_tune(handler: Any, body: Dict[str, Any]):
    t_res = srv.clean_temp_files()
    d_res = srv.flush_dns_cache()
    p_res = srv.purge_dev_caches()
    r_res = srv.optimize_ram()
    u_res = srv.run_automatic_upgrade_manager(force_scan=False, dry_run=False)
    total_reclaimed = round(t_res.get("reclaimed_mb", 0) + p_res.get("reclaimed_mb", 0), 2)
    upg_cnt = int(u_res.get("upgraded_count") or 0)
    upg_note = f", auto-upgraded {upg_cnt} package(s)" if upg_cnt > 0 else ", verified OS & software upgrades"
    msg = f"1-Click Complete Tuning finished: Reclaimed {total_reclaimed} MB, flushed DNS, swept RAM{upg_note}."
    srv.db.log_activity("PCOptimizer", "auto_tune", msg)
    handler._send_json({
        "status": "success",
        "message": msg,
        "clean_temp": t_res,
        "flush_dns": d_res,
        "purge_caches": p_res,
        "optimize_ram": r_res,
        "upgrades": u_res,
        "total_reclaimed_mb": total_reclaimed,
    })

