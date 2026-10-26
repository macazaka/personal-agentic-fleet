"""
Local Web Dashboard Server for Personal Agentic Fleet.
Zero-dependency HTTP server using Python standard library (http.server).
Serves a sleek modern single-page dashboard with:
  - Daily Morning Briefing
  - Task & Goal Board
  - Routine & Habits Checklist
  - Email Intelligence (5 Folders: Meetings, Respond, Note, FYI, Ignore)
  - Fleet Activity Stream & Native Windows Notifications
Modular Architecture:
  - Frontend UI assets: fleet/web/ (templates, css, js)
  - API endpoints: fleet/api/ (tasks, health, email, backlog, optimizer, antigravity, system)
  - Persistent storage: fleet/core/database.py (domain mixins in fleet/core/db/)
"""

from __future__ import annotations
import base64
import json
from typing import Any, Dict, List, Optional
import mimetypes
import os
from pathlib import Path
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fleet.config import CHANGELOG_PATH, VERSION
from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.core.event_bus import FleetEvent, bus
from fleet.core.antigravity_mirror import (
    AGENT_STATE,
    AVAILABLE_MODELS,
    UPLOADS_DIR,
    execute_dashboard_command,
    fast_track_queue,
    get_active_model,
    get_active_transcript_path,
    get_agent_status,
    get_available_models,
    get_llm_usage_details,
    get_max_parallel_agents,
    get_parallel_agents,
    get_token_health,
    handle_token_exhaustion,
    parse_transcript,
    resume_token_exhaustion,
    save_uploaded_image,
    set_active_model,
    set_max_parallel_agents,
)
from fleet.tools.system_tools import get_disk_usage, send_windows_notification
from fleet.core.optimizer import (
    clean_temp_files,
    flush_dns_cache,
    get_pc_performance_diagnostics,
    open_startup_settings,
    optimize_ram,
    purge_dev_caches,
)
from fleet.web.builder import STATIC_DIR, get_dashboard_html



PORT = 7890
db = FleetDatabase()
briefing_engine = BriefingEngine(db)

# Backwards-compatible standalone HTML_PAGE export for external consumers & offline tests
HTML_PAGE = get_dashboard_html(standalone=True)


# Import API route registry & Agent Registry
import fleet.api
from fleet.api.router import router
from fleet.config import load_fleet_config
from fleet.core.registry import AgentRegistry

fleet_config = load_fleet_config()
agent_registry = AgentRegistry(config=fleet_config, event_bus=bus)
agent_registry.discover_and_load()
agent_registry.register_all_routes(router)


MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB request body ceiling (DoS protection)
ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
}


class FleetDashboardHandler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def finish(self):
        try:
            super().finish()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _send_security_headers(self, set_session_cookie: bool = False):
        """Attach comprehensive HTTP hardening, CSP, and Cross-Origin Isolation headers."""
        from fleet.core.session_auth import get_session_cookie_header
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https:; media-src 'self' blob: data:; connect-src 'self' http://127.0.0.1:7890 http://localhost:7890; object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
        )
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if set_session_cookie:
            self.send_header("Set-Cookie", get_session_cookie_header())
        origin = self.headers.get("Origin", "") if hasattr(self, "headers") and self.headers else ""
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{PORT}")

    def _send_json(self, data: Any, status: int = 200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self._send_security_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        pass  # Suppress default noisy console logs; events routed via event bus

    def _read_json(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0 or content_len > MAX_PAYLOAD_BYTES:
            return {}
        post_data = self.rfile.read(content_len).decode("utf-8", errors="replace")
        try:
            return json.loads(post_data)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        from fleet.core.session_auth import validate_request_security
        ok, reason = validate_request_security(getattr(self, "headers", None), "GET", ALLOWED_ORIGINS)
        if not ok:
            self._send_json({"error": reason, "status": "blocked"}, 403)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
        # 1. Main HTML Dashboard
        if path == "/" or path == "/index.html":
            # Serve modular dashboard linking to /static/ assets
            body = get_dashboard_html(standalone=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_security_headers(set_session_cookie=True)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        elif path == "/api/briefing":
            data = briefing_engine.generate_daily_briefing()
            self._send_json(data)

        elif path == "/api/tasks":
            tasks = db.list_tasks()
            self._send_json(tasks)

        elif path == "/api/backlog":
            query = urllib.parse.parse_qs(parsed.query)
            status_filter = query.get("status", [None])[0]
            cat_filter = query.get("category", [None])[0]
            ver_filter = query.get("target_version", [None])[0]
            items = db.list_feature_backlog_items(status=status_filter, category=cat_filter, target_version=ver_filter)
            stats = db.get_feature_backlog_stats()
            self._send_json({"items": items, "stats": stats})

        elif path == "/api/routines":
            routines = db.list_routines()
            self._send_json(routines)

        elif path == "/api/emails":
            # Fetches latest email classification preview via Deterministic Event Bus (incremental caching)
            query = urllib.parse.parse_qs(parsed.query)
            force = query.get("force_refresh", ["false"])[0].lower() in ("true", "1")
            res = bus.dispatch(FleetEvent(
                sender="WebDashboard",
                target="email",
                action="CLASSIFY_RECENT",
                payload={"dry_run": True, "force_refresh": force}
            ))
            if res["status"] == "success":
                self._send_json(res["data"])
            else:
                self._send_json({"error": res.get("message")}, 500)

        elif path == "/api/emails/body":
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            q_params = parse_qs(parsed_url.query)
            msg_id = q_params.get("id", [""])[0]
            from fleet.integrations.gmail_client import gmail_manager
            res = gmail_manager.get_email_full_body(msg_id)
            self._send_json(res)

        elif path == "/api/health/summary":
            data = db.get_health_dashboard_summary()
            self._send_json(data)

        elif path == "/api/health/water":
            data = db.get_today_hydration()
            self._send_json(data)

        elif path == "/api/health/medications":
            data = db.list_medications()
            self._send_json(data)

        elif path == "/api/health/trends":
            query = urllib.parse.parse_qs(parsed.query)
            metric = query.get("metric", ["water_ml"])[0]
            days = int(query.get("days", [7])[0])
            data = db.get_health_trends(metric_type=metric, days=days)
            self._send_json(data)

        elif path == "/api/logs":
            logs = db.get_recent_activities(limit=15)
            self._send_json(logs)

        elif path == "/api/status":
            disk = get_disk_usage("C:")
            self._send_json({
                "status": "online",
                "version": VERSION,
                "time": datetime.now().isoformat(),
                "disk": disk
            })

        elif path == "/api/version":
            self._send_json({
                "version": VERSION,
                "name": "Personal Agentic Fleet",
                "release_date": "2026-10-14",
                "status": "operational"
            })

        elif path == "/api/release_notes":
            notes = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else "No release notes available."
            self._send_json({
                "version": VERSION,
                "changelog_markdown": notes
            })

        elif path == "/api/antigravity/transcript":
            query = urllib.parse.parse_qs(parsed.query)
            limit = int(query.get("limit", [50])[0])
            since_step = int(query.get("since_step", [-1])[0])
            since_val = since_step if since_step >= 0 else None
            data = parse_transcript(limit=limit, since_step=since_val)
            self._send_json(data)

        elif path == "/api/antigravity/models":
            self._send_json({
                "models": get_available_models(),
                "active_model": get_active_model(),
            })

        elif path == "/api/antigravity/usage":
            self._send_json(get_llm_usage_details())

        elif path == "/api/antigravity/tokens":
            query = urllib.parse.parse_qs(parsed.query)
            sim = query.get("simulate", [None])[0]
            self._send_json(get_token_health(simulated_status=sim))

        elif path == "/api/antigravity/queue":
            self._send_json(get_agent_status())

        elif path.startswith("/api/antigravity/media/"):
            raw_fname = path[len("/api/antigravity/media/"):]
            filename = os.path.basename(urllib.parse.unquote(raw_fname))
            media_path = None
            if filename:
                candidate = UPLOADS_DIR / filename
                if candidate.is_file():
                    media_path = candidate
                else:
                    t_path = get_active_transcript_path()
                    if t_path:
                        brain_dir = t_path.parents[2]
                        for c in [brain_dir / ".user_uploaded" / filename, brain_dir / filename]:
                            if c.is_file():
                                media_path = c
                                break
            if media_path and media_path.is_file():
                content_type = mimetypes.guess_type(str(media_path))[0] or "image/png"
                data = media_path.read_bytes()
        # 2. Static Assets (/static/css/*, /static/js/*)
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = (STATIC_DIR / rel_path).resolve()
            # Security guard against directory traversal
            if file_path.is_file() and str(file_path).startswith(str(STATIC_DIR)):
                if file_path.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif file_path.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                else:
                    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                data = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self._send_security_headers()
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)
                return
            else:
                self.send_error(404, "Media file not found")
                self.send_error(404, "Static asset not found")
                return

        elif path == "/api/test_results":
            latest = db.get_latest_test_run()
            if not latest:
                from fleet.tools.test_runner import RESULTS_FILE
                if RESULTS_FILE.exists():
                    try:
                        latest = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        pass
            self._send_json(latest or {
                "pass_pct": 100.0,
                "total_tests": 0,
                "passed_tests": 0,
                "coverage_pct": 0.0,
                "status": "PASS",
                "timestamp": "-"
            })

        elif path == "/api/optimizer/diagnostics":
            data = get_pc_performance_diagnostics()
            self._send_json(data)

        else:
            # 3. Dispatch to Domain API Routers
            handled = router.dispatch_get(self, path, parsed)
            if not handled:
                self.send_error(404, "Not Found")

    def do_POST(self):
        from fleet.core.session_auth import validate_request_security
        ok, reason = validate_request_security(getattr(self, "headers", None), "POST", ALLOWED_ORIGINS)
        if not ok:
            self._send_json({"error": reason, "status": "blocked"}, 403)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/antigravity/command":
            cmd = body.get("command", "")
            images = body.get("images", [])
            model = body.get("model", None)
            res = execute_dashboard_command(cmd, images=images, model=model)
            self._send_json(res)

        elif path == "/api/antigravity/models":
            model_name = body.get("model", "")
            success = set_active_model(model_name)
            self._send_json({
                "status": "success" if success else "error",
                "model": get_active_model()
            })

        elif path == "/api/antigravity/upload":
            filename = body.get("filename", "")
            b64_data = body.get("data", "")
            if not b64_data and "base64" in body:
                b64_data = body.get("base64", "")
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_data)
                res = save_uploaded_image(filename or "uploaded_image.png", raw_bytes)
                self._send_json({"status": "success", "file": res})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 400)

        elif path == "/api/antigravity/queue/cancel":
            queue_id = body.get("id")
            if queue_id is not None:
                cancelled = db.cancel_queued_chat_message(queue_id)
                self._send_json({"status": "success" if cancelled else "failed", "cancelled": cancelled})
            else:
                self._send_json({"status": "error", "message": "Missing queue id"}, 400)

        elif path == "/api/antigravity/tokens/resume":
            fallback_model = body.get("fallback_model")
            res = resume_token_exhaustion(fallback_model=fallback_model)
            self._send_json(res)

        elif path == "/api/antigravity/fast_track":
            res = fast_track_queue()
            self._send_json(res)

        elif path == "/api/antigravity/parallel_limit":
            limit = int(body.get("limit", 4))
            updated = set_max_parallel_agents(limit)
            self._send_json({"status": "success", "max_parallel_agents": updated})

        elif path == "/api/antigravity/tokens/simulate":
            sim_status = body.get("status", "exhausted")  # "exhausted", "warning", or "clear"
            if sim_status == "clear":
                db.set_setting("token_exhaustion_override", "")
                AGENT_STATE["status"] = "idle"
                self._send_json({"status": "cleared", "override": ""})
            else:
                db.set_setting("token_exhaustion_override", sim_status)
                if sim_status == "exhausted":
                    handle_token_exhaustion(reason=body.get("reason", "Simulated token exhaustion"))
                self._send_json({"status": "simulated", "override": sim_status})

        elif path == "/api/backlog":
            title = body.get("title", "").strip()
            if not title:
                self._send_json({"error": "Title required"}, 400)
                return
            desc = body.get("description", "")
            cat = body.get("category", "Core")
            priority = body.get("priority", "P2")
            status = body.get("status", "Idea")
            ver = body.get("target_version", "v1.4.0")
            item_id = db.add_feature_backlog_item(title=title, description=desc, category=cat, priority=priority, status=status, target_version=ver)
            db.log_activity("User", "backlog_add", f"Added backlog feature: {title} ({priority})")
            self._send_json({"status": "created", "id": item_id})

        elif path == "/api/backlog/update":
            item_id = body.get("id")
            if not item_id:
                self._send_json({"error": "Item ID required"}, 400)
                return
            up_data = {k: v for k, v in body.items() if k != "id"}
            ok = db.update_feature_backlog_item(item_id, **up_data)
            self._send_json({"status": "updated" if ok else "not_found", "success": ok})

        elif path == "/api/backlog/delete":
            item_id = body.get("id")
            if not item_id:
                self._send_json({"error": "Item ID required"}, 400)
                return
            ok = db.delete_feature_backlog_item(item_id)
            self._send_json({"status": "deleted" if ok else "not_found", "success": ok})

        elif path == "/api/tasks":
            title = body.get("title", "").strip()
            description = body.get("description", "").strip()
            priority = body.get("priority", "P2")
            source = body.get("source", "Dashboard").strip() or "Dashboard"
            if not title:
                self._send_json({"error": "Title required"}, 400)
                return
            if not description:
                self._send_json({"error": "Description required"}, 400)
                return
            task_id = db.add_task(title, description=description, priority=priority, source=source)
            self._send_json({"id": task_id, "status": "created"})

        elif path == "/api/tasks/toggle":
            task_id = body.get("id")
            tasks = db.list_tasks()
            task = next((t for t in tasks if t["id"] == task_id), None)
            if not task:
                self._send_json({"error": "Not found"}, 404)
                return
            new_status = "completed" if task["status"] != "completed" else "pending"
            db.update_task_status(task_id, new_status)
            self._send_json({"status": "updated", "new_status": new_status})

        elif path == "/api/tasks/delete":
            task_id = body.get("id")
            db.delete_task(task_id)
            self._send_json({"status": "deleted"})

        elif path == "/api/routines/toggle":
            routine_id = body.get("id")
            db.toggle_routine(routine_id)
            self._send_json({"status": "toggled"})

        elif path == "/api/emails/sync":
            auto_archive = body.get("auto_archive_ignore", False)
            force_refresh = body.get("force_refresh", False)
            res = bus.dispatch(FleetEvent(
                sender="WebDashboard",
                target="email",
                action="CLASSIFY_RECENT",
                payload={"dry_run": False, "auto_archive_ignore": auto_archive, "force_refresh": force_refresh}
            ))
            if res["status"] == "success":
                self._send_json(res["data"])
            else:
                self._send_json({"error": res.get("message")}, 500)

        elif path == "/api/health/water":
            delta_glasses = int(body.get("delta_glasses", 1))
            delta_ml = int(body.get("delta_ml", 250))
            res = db.log_water_intake(glasses_delta=delta_glasses, amount_delta_ml=delta_ml)
            self._send_json({"status": "success", "hydration": res})

        elif path == "/api/health/water/goal":
            goal_ml = int(body.get("goal_ml", 2500))
            res = db.set_hydration_goal(goal_ml=goal_ml)
            self._send_json({"status": "success", "hydration": res})

        elif path == "/api/health/medications":
            name = body.get("name", "").strip()
            if not name:
                self._send_json({"error": "Medication name required"}, 400)
                return
            dosage = body.get("dosage", "")
            time_val = body.get("schedule_time", "09:00")
            freq = body.get("frequency", "Daily")
            instructions = body.get("instructions", "")
            med_id = db.add_medication(name=name, dosage=dosage, schedule_time=time_val, frequency=freq, instructions=instructions)
            self._send_json({"status": "created", "id": med_id})

        elif path == "/api/health/medications/toggle":
            med_id = body.get("id")
            if not med_id:
                self._send_json({"error": "Medication ID required"}, 400)
                return
            taken = db.toggle_medication_today(med_id)
            self._send_json({"status": "toggled", "taken": taken})

        elif path == "/api/health/medications/delete":
            med_id = body.get("id")
            if not med_id:
                self._send_json({"error": "Medication ID required"}, 400)
                return
            deleted = db.delete_medication(med_id)
            self._send_json({"status": "deleted", "deleted": deleted})

        elif path == "/api/health/metrics/log":
            m_type = body.get("metric_type", "").strip()
            val = float(body.get("value", 0.0))
            unit = body.get("unit", "")
            notes = body.get("notes", "")
            mid = db.log_health_metric(metric_type=m_type, value=val, unit=unit, notes=notes)
            self._send_json({"status": "logged", "id": mid})

        elif path == "/api/emails/unsubscribe":
            msg_id = body.get("id")
            if not msg_id:
                self._send_json({"error": "Missing email id"}, 400)
                return
            res = bus.dispatch(FleetEvent(
                sender="WebDashboard",
                target="email",
                action="UNSUBSCRIBE",
                payload={
                    "message_id": msg_id,
                    "url": body.get("url"),
                    "type": body.get("type", "http"),
                    "sender": body.get("sender", ""),
                    "subject": body.get("subject", "")
                }
            ))
            if res["status"] == "success":
                self._send_json(res["data"])
            else:
                self._send_json({"error": res.get("message")}, 500)

        elif path == "/api/notify":
            title = body.get("title", "Personal Agentic Fleet")
            message = body.get("message", "Notification from your fleet")
            success = send_windows_notification(title, message)
            db.log_activity("Notifier", "windows_toast", f"Sent Windows Toast: {title} - {message}")
            self._send_json({"status": "sent", "success": success})

        elif path == "/api/run_tests":
            from fleet.tools.test_runner import run_test_suite_isolated
            results = run_test_suite_isolated(db)
            self._send_json({"status": "success", "results": results})

        elif path == "/api/optimizer/clean_temp":
            res = clean_temp_files()
            db.log_activity("PCOptimizer", "clean_temp", res.get("message", "Cleaned temporary files"))
            self._send_json(res)

        elif path == "/api/optimizer/flush_dns":
            res = flush_dns_cache()
            db.log_activity("PCOptimizer", "flush_dns", res.get("message", "Flushed DNS resolver cache"))
            self._send_json(res)

        elif path == "/api/optimizer/purge_caches":
            res = purge_dev_caches()
            db.log_activity("PCOptimizer", "purge_caches", res.get("message", "Purged development caches"))
            self._send_json(res)

        elif path == "/api/optimizer/optimize_ram":
            res = optimize_ram()
            db.log_activity("PCOptimizer", "optimize_ram", res.get("message", "Optimized RAM working sets"))
            self._send_json(res)

        elif path == "/api/optimizer/open_startup":
            res = open_startup_settings()
            db.log_activity("PCOptimizer", "open_startup", "Opened Windows Startup Apps Settings")
            self._send_json(res)

        elif path == "/api/optimizer/auto_tune":
            t_res = clean_temp_files()
            d_res = flush_dns_cache()
            p_res = purge_dev_caches()
            r_res = optimize_ram()
            total_reclaimed = round(t_res.get("reclaimed_mb", 0) + p_res.get("reclaimed_mb", 0), 2)
            msg = f"1-Click Complete Tuning finished: Reclaimed {total_reclaimed} MB, flushed DNS, and swept RAM."
            db.log_activity("PCOptimizer", "auto_tune", msg)
            self._send_json({
                "status": "success",
                "message": msg,
                "reclaimed_mb": total_reclaimed,
                "temp": t_res,
                "dns": d_res,
                "caches": p_res,
                "ram": r_res
            })

        else:
            # Dispatch to Domain API Routers
            handled = router.dispatch_post(self, path, body)
            if not handled:
                self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Silence standard HTTP access logging in console for clean terminal output
        return


class RobustThreadingHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that suppresses client disconnection socket noise."""
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc_type, exc_val, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        super().handle_error(request, client_address)


def start_server(port: int = PORT):
    """Starts the Personal Agentic Fleet Dashboard server."""
    agent_registry.startup_all()
    server = RobustThreadingHTTPServer(("127.0.0.1", port), FleetDashboardHandler)
    print(f"Personal Agentic Fleet Dashboard running at: http://127.0.0.1:{port}")
    print(f"🚀 Fleet Dashboard running at: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        agent_registry.shutdown_all()
        server.server_close()


if __name__ == "__main__":
    start_server()
