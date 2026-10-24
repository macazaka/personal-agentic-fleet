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


@router.post("/api/optimizer/auto_tune")
def post_auto_tune(handler: Any, body: Dict[str, Any]):
    t_res = srv.clean_temp_files()
    d_res = srv.flush_dns_cache()
    p_res = srv.purge_dev_caches()
    r_res = srv.optimize_ram()
    total_reclaimed = round(t_res.get("reclaimed_mb", 0) + p_res.get("reclaimed_mb", 0), 2)
    msg = f"1-Click Complete Tuning finished: Reclaimed {total_reclaimed} MB, flushed DNS, and swept RAM."
    srv.db.log_activity("PCOptimizer", "auto_tune", msg)
    handler._send_json({
        "status": "success",
        "message": msg,
        "clean_temp": t_res,
        "flush_dns": d_res,
        "purge_caches": p_res,
        "optimize_ram": r_res,
        "total_reclaimed_mb": total_reclaimed
    })

