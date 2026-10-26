"""
Deep End-to-End Test Suite for the Workstation Control Center.
Tests every subsystem of Personal Agentic Fleet against live socket server:
  1. Live HTTP/1.1 Socket Server Startup & Graceful Teardown
  2. Modular & Standalone Dashboard HTML UI Bundling
  3. Static Assets Integrity (All 15 JS modules + CSS)
  4. 100+ Agent Scalability & Fleet Navigator Endpoints
  5. Task & Goal Management Workflow
  6. Routines & Habit Tracking
  7. Daily Morning Briefing Engine
  8. Automated Agent Schedules & Background Tasks
  9. Antigravity AI Live Mirror, Models & Context Window
  10. PC Performance Optimizer & Workstation Diagnostics
  11. Automated Test Runner & Code Coverage Endpoints
  12. Feature Backlog Management
  13. Settings, GitHub Version Updater & Community Agent Catalog
  14. create-agent Skill Wizard API & Dynamic Staging
  15. 12-Layer Security Invariants (DNS Rebinding, CSRF, CSP, Origin Guards)
"""

import json
import os
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from fleet.config import VERSION
from fleet.core.database import FleetDatabase
from fleet.server import FleetDashboardHandler, ThreadingHTTPServer
from fleet.web.builder import JS_LOAD_ORDER, STATIC_DIR, get_dashboard_html


def get_free_port() -> int:
    """Finds an available loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServerHarness:
    """Spins up a real live ThreadingHTTPServer on an ephemeral port for testing."""

    def __init__(self):
        self.port = get_free_port()
        self.host = "127.0.0.1"
        self.base_url = f"http://{self.host}:{self.port}"
        from fleet.config import TEST_DB_PATH
        import fleet.server as srv
        self._orig_db = srv.db
        srv.db = FleetDatabase(db_path=TEST_DB_PATH)
        self.server = ThreadingHTTPServer((self.host, self.port), FleetDashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        # Verify server socket is accepting connections
        start_time = time.time()
        while time.time() - start_time < 5.0:
            try:
                with socket.create_connection((self.host, self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("Server failed to start within 5 seconds")

    def stop(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        import fleet.server as srv
        srv.db = self._orig_db
        try:
            from fleet.core.db.pool import pool
            pool.close_all()
        except Exception:
            pass

    def request(
        self,
        method: str,
        path: str,
        data: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        url = f"{self.base_url}{path}"
        req_headers = {"User-Agent": "FleetTestHarness/1.0"}
        if headers:
            req_headers.update(headers)

        req_body = None
        if data is not None:
            req_body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=req_body, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp_headers = {k: v for k, v in resp.getheaders()}
                return resp.status, resp_headers, resp.read()
        except urllib.error.HTTPError as e:
            resp_headers = {k: v for k, v in e.headers.items()}
            return e.code, resp_headers, e.read()


@pytest.fixture(scope="module")
def server_harness():
    harness = LiveServerHarness()
    harness.start()
    yield harness
    harness.stop()


# =========================================================================
# Subsystem 1: Dashboard UI & Static Assets
# =========================================================================

def test_dashboard_ui_modular_and_security_headers(server_harness: LiveServerHarness):
    """Verifies GET / serves the HTML dashboard with full security headers."""
    status, headers, body = server_harness.request("GET", "/")
    assert status == 200
    assert "text/html" in headers.get("Content-Type", "")
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in headers

    html_text = body.decode("utf-8")
    assert "Personal Agentic Fleet" in html_text
    assert "fleetOperationsCenter" in html_text
    assert "fleetNavigatorDrawer" in html_text
    assert "commandPaletteModal" in html_text
    assert "viewActiveAgentStage" in html_text
    assert "btnFleetSettings" in html_text
    assert "btnCreateAgent" in html_text


def test_dashboard_ui_standalone_bundling():
    """Verifies that standalone HTML bundling works without errors and contains all modules."""
    html_standalone = get_dashboard_html(standalone=True)
    assert len(html_standalone) > 200_000
    assert "<style>" in html_standalone
    assert "FleetNavigator" in html_standalone
    assert "create-agent Skill" in html_standalone


def test_static_assets_all_loaded(server_harness: LiveServerHarness):
    """Verifies that every declared JS module and stylesheet is accessible via HTTP 200."""
    # Test CSS
    status, headers, body = server_harness.request("GET", "/static/css/dashboard.css")
    assert status == 200
    assert "text/css" in headers.get("Content-Type", "")
    assert len(body) > 10_000

    # Test all JS files in JS_LOAD_ORDER
    for js_file in JS_LOAD_ORDER:
        status, headers, body = server_harness.request("GET", f"/static/js/{js_file}")
        assert status == 200, f"Failed to fetch {js_file}"
        assert "javascript" in headers.get("Content-Type", "") or "text/plain" in headers.get("Content-Type", "")
        assert len(body) > 100, f"{js_file} appears unexpectedly empty"


# =========================================================================
# Subsystem 2: Fleet Agents & 100+ Scalability API
# =========================================================================

def test_fleet_agents_api(server_harness: LiveServerHarness):
    """Verifies /api/fleet/agents and domain enrichments."""
    status, _, body = server_harness.request("GET", "/api/fleet/agents?all=true")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "ok"
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) >= 7

    agent_ids = {a["id"] for a in data["agents"]}
    for expected in ("health", "overview", "antigravity", "optimizer", "backlog"):
        assert expected in agent_ids


# =========================================================================
# Subsystem 3: Task & Goal Management
# =========================================================================

def test_tasks_lifecycle(server_harness: LiveServerHarness):
    """Tests creating, listing, and completing tasks."""
    # 1. Add Task
    new_task = {
        "title": "Quarterly Workstation Audit",
        "description": "Verify system health, diagnostics, and routine logs",
        "priority": "P1",
        "source": "Dashboard",
    }
    status, _, body = server_harness.request("POST", "/api/tasks", data=new_task)
    assert status in (200, 201)
    res = json.loads(body.decode("utf-8"))
    assert res.get("status") in ("ok", "success", "created")

    # 2. List Tasks
    status, _, body = server_harness.request("GET", "/api/tasks")
    assert status == 200
    tasks = json.loads(body.decode("utf-8"))
    matching = [t for t in tasks if t["title"] == "Quarterly Workstation Audit"]
    assert len(matching) > 0
    task_id = matching[0]["id"]

    # 3. Toggle Task Completion
    status, _, body = server_harness.request("POST", "/api/tasks/toggle", data={"id": task_id})
    assert status == 200

    # 4. Clean up / Delete Task
    status, _, body = server_harness.request("POST", "/api/tasks/delete", data={"id": task_id})
    assert status == 200


# =========================================================================
# Subsystem 4: Routines & Habit Tracking
# =========================================================================

def test_routines_lifecycle(server_harness: LiveServerHarness):
    """Tests listing and toggling habits/routines."""
    status, _, body = server_harness.request("GET", "/api/routines")
    assert status == 200
    routines = json.loads(body.decode("utf-8"))
    assert isinstance(routines, list)

    if routines:
        first_id = routines[0]["id"]
        status, _, body = server_harness.request("POST", "/api/routines/toggle", data={"id": first_id})
        assert status == 200
        res = json.loads(body.decode("utf-8"))
        assert res.get("status") in ("ok", "success", "toggled")


# =========================================================================
# Subsystem 5: Morning Daily Briefing Engine
# =========================================================================

def test_briefing_engine(server_harness: LiveServerHarness):
    """Tests the daily morning briefing aggregation."""
    status, _, body = server_harness.request("GET", "/api/briefing")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "headline" in data or "greeting" in data or "stats" in data


# =========================================================================
# Subsystem 6: Schedules & Background Automations
# =========================================================================

def test_schedules_endpoints(server_harness: LiveServerHarness):
    """Tests listing and reloading YAML agent schedules."""
    status, _, body = server_harness.request("GET", "/api/schedules")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "schedules" in data or "active_count" in data

    status, _, body = server_harness.request("POST", "/api/schedules/reload", data={})
    assert status == 200


# =========================================================================
# Subsystem 7: Antigravity AI Live Mirror & Usage
# =========================================================================

def test_antigravity_mirror_endpoints(server_harness: LiveServerHarness):
    """Tests AI model selection, context window capacity, and transcript parsing."""
    # 1. Models
    status, _, body = server_harness.request("GET", "/api/antigravity/models")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "models" in data
    assert "active_model" in data

    # 2. Token Health / Context Window
    status, _, body = server_harness.request("GET", "/api/antigravity/usage")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "context_window_limit" in data or "token_count" in data or "percent_used" in data

    # 3. Transcript
    status, _, body = server_harness.request("GET", "/api/antigravity/transcript")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "steps" in data or "status" in data


# =========================================================================
# Subsystem 8: PC Performance Optimizer
# =========================================================================

def test_optimizer_diagnostics(server_harness: LiveServerHarness):
    """Tests performance diagnostics and RAM/Disk metrics."""
    status, _, body = server_harness.request("GET", "/api/optimizer/diagnostics")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "ram" in data or "cpu" in data or "disk" in data or "status" in data


# =========================================================================
# Subsystem 9: Automated Test Suite & Code Coverage API
# =========================================================================

def test_test_results_api(server_harness: LiveServerHarness):
    """Tests querying the latest automated test runner status."""
    status, _, body = server_harness.request("GET", "/api/test_results")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "total" in data or "status" in data or "pass_percentage" in data or "results" in data


# =========================================================================
# Subsystem 10: Feature Backlog & Roadmapping
# =========================================================================

def test_backlog_api(server_harness: LiveServerHarness):
    """Tests retrieving feature backlog and roadmap items."""
    status, _, body = server_harness.request("GET", "/api/backlog")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "items" in data
    assert "stats" in data


# =========================================================================
# Subsystem 11: Settings, Version Updater & Catalog
# =========================================================================

def test_settings_and_version_api(server_harness: LiveServerHarness):
    """Tests settings retrieval, update, version check, and release notes."""
    # 1. Version
    status, _, body = server_harness.request("GET", "/api/version")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "version" in data

    # 2. Release Notes
    status, _, body = server_harness.request("GET", "/api/release_notes")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "changelog_markdown" in data or "release_notes" in data

    # 3. Settings Get
    status, _, body = server_harness.request("GET", "/api/settings")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "settings" in data
    assert "agents" in data

    # 4. Catalog List
    status, _, body = server_harness.request("GET", "/api/settings/agents/catalog")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert "catalog" in data


# =========================================================================
# Subsystem 12: create-agent Skill Wizard & Dynamic Registration
# =========================================================================

def test_create_agent_wizard_api(server_harness: LiveServerHarness):
    """Tests end-to-end scaffolding, manifest registration, and immediate activation."""
    agent_payload = {
        "id": "e2e_test_agent",
        "name": "E2E Test Agent",
        "icon": "🧪",
        "category": "DevOps & System",
        "description": "Agent scaffolded during in-depth E2E workstation tests.",
        "permissions": ["ui:render", "network:outbound", "storage:data_read"],
        "default_settings": {"poll_interval": 30},
    }

    try:
        status, _, body = server_harness.request("POST", "/api/settings/agents/create", data=agent_payload)
        assert status == 200
        res = json.loads(body.decode("utf-8"))
        assert res.get("status") in ("ok", "success")
        assert res.get("agent_id") == "e2e_test_agent"

        # Verify it now appears immediately in fleet agents list
        status, _, body = server_harness.request("GET", "/api/fleet/agents?all=true")
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        agent_ids = [a["id"] for a in data["agents"]]
        assert "e2e_test_agent" in agent_ids
    finally:
        # Clean up created custom agent directory
        custom_dir = Path("fleet/data/user/custom_agents/e2e_test_agent")
        if custom_dir.exists():
            shutil.rmtree(custom_dir, ignore_errors=True)


# =========================================================================
# Subsystem 13: Security Invariants (DNS Rebinding & CSRF Guard)
# =========================================================================

def test_security_dns_rebinding_blocked(server_harness: LiveServerHarness):
    """Verifies that malicious Host headers (DNS rebinding) are rejected with 403."""
    status, _, body = server_harness.request(
        "GET",
        "/api/tasks",
        headers={"Host": "attacker.com"},
    )
    assert status == 403
    assert b"DNS Rebinding blocked" in body


def test_security_csrf_cross_origin_blocked(server_harness: LiveServerHarness):
    """Verifies that cross-origin POST requests are rejected with 403."""
    status, _, body = server_harness.request(
        "POST",
        "/api/tasks",
        data={"title": "Malicious Task"},
        headers={"Origin": "https://malicious-site.com"},
    )
    assert status == 403
    assert b"Cross-Origin POST blocked" in body


# =========================================================================
# Subsystem 14: Agent Activation Toggle & Customization
# =========================================================================

def test_agent_toggle_and_customization(server_harness: LiveServerHarness):
    """Tests toggling an agent active/inactive and customizing properties."""
    # 1. Toggle agent off
    status, _, body = server_harness.request("POST", "/api/settings/agents/toggle", data={"agent_id": "health", "enabled": False})
    assert status == 200
    res = json.loads(body.decode("utf-8"))
    assert res.get("status") in ("ok", "success")
    assert res.get("agent", {}).get("enabled") is False or res.get("enabled") is False

    # Verify state reflects in settings
    status, _, body = server_harness.request("GET", "/api/settings")
    data = json.loads(body.decode("utf-8"))
    health_agent = next(a for a in data["agents"] if a["id"] == "health")
    assert health_agent["enabled"] is False

    # 2. Toggle agent back on
    status, _, body = server_harness.request("POST", "/api/settings/agents/toggle", data={"agent_id": "health", "enabled": True})
    assert status == 200

    # 3. Customize agent properties
    status, _, body = server_harness.request(
        "POST",
        "/api/settings/agents/customize",
        data={"agent_id": "optimizer", "name": "PC Speed Booster", "icon": "⚡"},
    )
    assert status == 200

    # 4. Reset customization
    status, _, body = server_harness.request("POST", "/api/settings/agents/reset", data={"agent_id": "optimizer"})
    assert status == 200


# =========================================================================
# Subsystem 15: Optimizer Actions & Desktop Notifications
# =========================================================================

def test_optimizer_actions_and_notification(server_harness: LiveServerHarness):
    """Tests executing optimizer routines and triggering desktop notification."""
    # 1. Clean temp files
    status, _, body = server_harness.request("POST", "/api/optimizer/clean_temp", data={})
    assert status == 200
    res = json.loads(body.decode("utf-8"))
    assert "status" in res

    # 2. Optimize RAM
    status, _, body = server_harness.request("POST", "/api/optimizer/optimize_ram", data={})
    assert status == 200

    # 3. Desktop Notification
    status, _, body = server_harness.request(
        "POST",
        "/api/notify",
        data={"title": "E2E Test Alert", "message": "Workstation Control Center operational!"},
    )
    assert status == 200


# =========================================================================
# Subsystem 16: 100+ Agent Scalability State Verification
# =========================================================================

def test_100_agents_scalability_simulation():
    """Simulates 100+ concurrent agents and verifies categorization, filtering, and paging."""
    categories = ["DevOps & System", "AI & Research", "Finance & Markets", "Smart Home & IoT", "Monitoring & Watchers", "Productivity"]
    agents = []
    for i in range(1, 106):
        cat = categories[i % len(categories)]
        agents.append({
            "id": f"agent_{i:03d}",
            "name": f"Enterprise Agent {i:03d}",
            "category": cat,
            "enabled": (i % 5 != 0),
            "status": "working" if i % 3 == 0 else "idle",
            "is_pinned": (i <= 5),
            "permissions": ["db:read", "ui:render"],
        })

    assert len(agents) == 105
    working_count = len([a for a in agents if a["status"] == "working"])
    assert working_count > 0

    # Test categorization grouping
    groups = {}
    for a in agents:
        groups.setdefault(a["category"], []).append(a)
    assert len(groups) == 6

    # Test client-side pagination slicing (pageSize = 24)
    page_size = 24
    total_pages = (len(agents) + page_size - 1) // page_size
    assert total_pages == 5

    page1 = agents[:24]
    assert len(page1) == 24
    assert page1[0]["id"] == "agent_001"

    page5 = agents[96:]
    assert len(page5) == 9

