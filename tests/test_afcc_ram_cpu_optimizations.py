"""Comprehensive unit tests for [PERF-01]..[PERF-10] AFCC RAM & CPU optimizations."""

import gzip
import io
import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

from fleet.app import acquire_single_instance_lock, release_single_instance_lock
from fleet.core import antigravity_mirror as ag_mirror
from fleet.core import briefing as briefing_mod
from fleet.core import optimizer as opt_mod
from fleet.core.briefing import BriefingEngine, get_briefing_cache_stats, invalidate_briefing_cache
from fleet.core.database import FleetDatabase
from fleet.core.db.backlog import AFCC_RAM_CPU_OPTIMIZATION_BACKLOG_ITEMS, ALL_CANONICAL_BACKLOG_ITEMS
from fleet.core.db.base import clear_verified_schema_cache, get_schema_cache_stats
from fleet.core.db.pool import SQLiteConnectionPool
from fleet.daemon import FleetDaemon
from fleet.server import (
    FleetDashboardHandler,
    RobustThreadingHTTPServer,
    get_process_resource_telemetry,
)
from fleet.web import builder as web_builder


WEB_JS_DIR = Path(__file__).resolve().parent.parent / "fleet" / "web" / "static" / "js"


def _make_handler(method: str, path: str, headers: dict | None = None, body_dict: dict | None = None):
    body_bytes = json.dumps(body_dict).encode("utf-8") if body_dict is not None else b""
    handler = FleetDashboardHandler.__new__(FleetDashboardHandler)
    handler.rfile = io.BytesIO(body_bytes)
    handler.wfile = io.BytesIO()
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    base_headers = {"Content-Length": str(len(body_bytes)), "Content-Type": "application/json"}
    if headers:
        base_headers.update(headers)
    handler.headers = base_headers
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 54321)
    handler.close_connection = False
    return handler, handler.wfile


def _split_http_response(raw_bytes: bytes):
    head, _, body = raw_bytes.partition(b"\r\n\r\n")
    lines = head.decode("utf-8", errors="replace").split("\r\n")
    status_line = lines[0] if lines else ""
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status_line, headers, body


def test_perf_backlog_items_registered(tmp_path):
    """[PERF-01]..[PERF-10] All 10 critical RAM/CPU optimization items exist in canonical backlog and sync cleanly."""
    assert len(AFCC_RAM_CPU_OPTIMIZATION_BACKLOG_ITEMS) == 10
    titles = [item["title"] for item in AFCC_RAM_CPU_OPTIMIZATION_BACKLOG_ITEMS]
    for idx in range(1, 11):
        prefix = f"[PERF-{idx:02d}]"
        matched = [item for item in AFCC_RAM_CPU_OPTIMIZATION_BACKLOG_ITEMS if item["title"].startswith(prefix)]
        assert len(matched) == 1, f"Missing canonical item {prefix}"
        assert matched[0]["priority"] == "P1"
        assert matched[0]["status"] == "Completed"
        assert matched[0]["title"] in {i["title"] for i in ALL_CANONICAL_BACKLOG_ITEMS}

    db = FleetDatabase(db_path=tmp_path / "perf_backlog.db")
    db.sync_ux_roadmap_backlog()
    stored = {item["title"]: item for item in db.list_feature_backlog_items()}
    for t in titles:
        assert t in stored
        assert stored[t]["status"] == "Completed"


def test_perf01_perf02_frontend_visibility_polling_and_signature_diff():
    """[PERF-01] & [PERF-02] Frontend pauses on hidden tabs, uses single-flight lock, defers hidden tabs, and diffs signatures."""
    app_js = (WEB_JS_DIR / "app.js").read_text(encoding="utf-8")
    core_js = (WEB_JS_DIR / "core.js").read_text(encoding="utf-8")
    briefing_js = (WEB_JS_DIR / "briefing.js").read_text(encoding="utf-8")
    tasks_js = (WEB_JS_DIR / "tasks.js").read_text(encoding="utf-8")
    routines_js = (WEB_JS_DIR / "routines.js").read_text(encoding="utf-8")
    schedules_js = (WEB_JS_DIR / "schedules.js").read_text(encoding="utf-8")
    backlog_js = (WEB_JS_DIR / "backlog.js").read_text(encoding="utf-8")

    # PERF-01: visibility-aware single-flight polling & deferred hidden-tab hydration
    assert "document.hidden" in app_js
    assert "_afccPollInFlight" in app_js
    assert "visibilitychange" in app_js
    assert "15000" in app_js
    boot_block = app_js.split("document.addEventListener('DOMContentLoaded'")[1].split("setInterval(")[0]
    assert "fetchBacklog()" not in boot_block
    assert "fetchOptimizerDiagnostics()" not in boot_block
    assert "fetchHealthDashboard()" not in boot_block
    assert "fetchExerciseVideos()" not in boot_block

    # core.js tab switcher pauses when hidden & lazily hydrates exercise videos when opening Health
    assert "if (document.hidden) return;" in core_js
    assert "_exerciseVideosHydrated" in core_js
    assert "_triPollTicks > 300" in backlog_js

    # PERF-02: payload signature diffing across main polling panels
    assert "window._afccHasPayloadChanged" in core_js
    assert "_afccHasPayloadChanged('logs'" in core_js
    assert "_afccHasPayloadChanged('briefing'" in briefing_js
    assert "_afccHasPayloadChanged('routines'" in routines_js
    assert "_afccHasPayloadChanged('schedules'" in schedules_js
    assert "_afccHasPayloadChanged('tasks'" in tasks_js


def test_perf03_sqlite_pool_bounded_pragmas_and_dead_thread_pruning(tmp_path):
    """[PERF-03] SQLite pool caps RAM PRAGMAs, skips redundant SELECT 1, prunes dead threads, and memoizes schema checks."""
    db_file = tmp_path / "perf03.db"
    pool = SQLiteConnectionPool(timeout=5.0, probe_ttl_sec=15.0)

    conn1 = pool.get_connection(db_file)
    cache_sz = conn1.execute("PRAGMA cache_size").fetchone()[0]
    journal_mode = str(conn1.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    assert cache_sz == -4096
    assert journal_mode == "wal"

    # Repeat checkout on same thread within probe_ttl skips SELECT 1
    conn2 = pool.get_connection(db_file)
    assert conn2 is conn1
    stats_mid = pool.get_pool_stats()
    assert stats_mid["skipped_health_probes"] >= 1

    # Spawn short-lived worker thread, verify connection added then pruned cleanly after exit
    done = threading.Event()

    def _worker():
        c = pool.get_connection(db_file)
        c.execute("CREATE TABLE IF NOT EXISTS t_perf (id INT)")
        c.commit()
        done.set()

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=5.0)
    assert done.is_set()

    pruned = pool.prune_dead_thread_connections()
    assert pruned >= 1
    assert pool.get_pool_stats()["active_connections"] == 1
    pool.close_all()

    # Verify BaseDatabase memoizes schema checks after initial creation
    clear_verified_schema_cache()
    db_inst = FleetDatabase(db_path=tmp_path / "schema_memo.db")
    before = get_schema_cache_stats()["schema_checks_skipped"]
    db_inst.list_tasks(limit=5)
    db_inst.list_routines()
    after = get_schema_cache_stats()["schema_checks_skipped"]
    assert after >= before + 2


def test_perf04_lazy_html_builder_cache_etag_304_and_gzip():
    """[PERF-04] Modular HTML builder caches by mtime, static handler returns gzip & ETag 304, JSON gzips conditionally."""
    import fleet.server as srv

    # 1. Lazy HTML_PAGE still resolves when accessed
    assert "Personal Agentic Fleet" in srv.HTML_PAGE

    # 2. Modular HTML builder caches across back-to-back calls
    web_builder.invalidate_builder_cache()
    h1 = web_builder.get_dashboard_html(standalone=False)
    stats1 = web_builder.get_builder_cache_stats()
    h2 = web_builder.get_dashboard_html(standalone=False)
    stats2 = web_builder.get_builder_cache_stats()
    assert h1 == h2
    assert stats2["hits"] >= stats1["hits"] + 1

    # 3. Static asset returns ETag + gzip and honors If-None-Match -> 304 Not Modified
    h_gz, out_gz = _make_handler("GET", "/static/js/app.js", headers={"Accept-Encoding": "gzip, deflate"})
    h_gz.do_GET()
    st_gz, hdr_gz, body_gz = _split_http_response(out_gz.getvalue())
    assert "200 OK" in st_gz
    assert hdr_gz.get("content-encoding") == "gzip"
    assert hdr_gz.get("etag")
    decompressed = gzip.decompress(body_gz).decode("utf-8")
    assert "runAfccPollTick" in decompressed

    h_304, out_304 = _make_handler("GET", "/static/js/app.js", headers={"If-None-Match": hdr_gz["etag"]})
    h_304.do_GET()
    st_304, hdr_304, body_304 = _split_http_response(out_304.getvalue())
    assert "304" in st_304
    assert body_304 == b""
    assert hdr_304.get("etag") == hdr_gz["etag"]

    # 4. _send_json sends gzip >= 2KB when Accept-Encoding includes gzip, plain JSON otherwise
    large_payload = {"items": [{"idx": i, "text": "x" * 60} for i in range(60)]}
    h_jg, out_jg = _make_handler("GET", "/api/test", headers={"Accept-Encoding": "gzip"})
    h_jg._send_json(large_payload)
    _, hdr_jg, body_jg = _split_http_response(out_jg.getvalue())
    assert hdr_jg.get("content-encoding") == "gzip"
    assert json.loads(gzip.decompress(body_jg).decode("utf-8")) == large_payload

    h_jp, out_jp = _make_handler("GET", "/api/test")
    h_jp._send_json(large_payload)
    _, hdr_jp, body_jp = _split_http_response(out_jp.getvalue())
    assert "content-encoding" not in hdr_jp
    assert json.loads(body_jp.decode("utf-8")) == large_payload


def test_perf05_bounded_http_thread_pool_and_sse_heartbeat():
    """[PERF-05] RobustThreadingHTTPServer uses a bounded ThreadPoolExecutor and 25s production SSE heartbeat."""
    srv = RobustThreadingHTTPServer(("127.0.0.1", 0), FleetDashboardHandler)
    try:
        assert srv._executor is not None
        assert 4 <= srv.max_workers <= 32
        assert srv._executor._max_workers == srv.max_workers
    finally:
        srv.server_close()
    assert srv._executor is None

    server_src = (Path(__file__).resolve().parent.parent / "fleet" / "server.py").read_text(encoding="utf-8")
    assert 'timeout = 0.2 if getattr(self, "_sse_test_mode", False) else 25.0' in server_src


def test_perf06_optimizer_and_briefing_ttl_caching_and_invalidation(tmp_path):
    """[PERF-06] Optimizer & Briefing TTL caches avoid repeated scans when enabled and invalidate immediately on writes."""
    opt_mod.invalidate_optimizer_diag_cache()
    calls = {"mem": 0, "temp": 0}

    def fake_mem():
        calls["mem"] += 1
        return {"total_gb": 16.0, "avail_gb": 8.0, "used_gb": 8.0, "percent_used": 50}

    def fake_temp():
        calls["temp"] += 1
        return {"size_mb": 12.0, "file_count": 5, "temp_path": str(tmp_path)}

    with (
        patch.object(opt_mod, "get_memory_status", side_effect=fake_mem),
        patch.object(opt_mod, "get_disk_usage", return_value={"percent_used": 45, "free_gb": 100.0}),
        patch.object(opt_mod, "get_temp_bloat_info", side_effect=fake_temp),
        patch.object(opt_mod, "get_dev_cache_info", return_value={"dir_count": 0, "size_mb": 0.0, "file_count": 0}),
        patch.object(opt_mod, "get_startup_apps", return_value=[]),
        patch.object(opt_mod, "get_top_processes", return_value=[]),
        patch.object(
            opt_mod,
            "check_os_and_software_upgrades",
            return_value={"total_pending_count": 0, "security_critical_count": 0, "os_info": {}},
        ),
    ):
        opt_mod.get_pc_performance_diagnostics(use_cache=True)
        opt_mod.get_pc_performance_diagnostics(use_cache=True)
        assert calls["mem"] == 1
        assert calls["temp"] == 1

        opt_mod.invalidate_optimizer_diag_cache()
        opt_mod.get_pc_performance_diagnostics(use_cache=True)
        assert calls["mem"] == 2
        assert calls["temp"] == 2

    # BriefingEngine TTL caching & invalidation
    invalidate_briefing_cache()
    db = FleetDatabase(db_path=tmp_path / "briefing_cache.db")
    engine = BriefingEngine(db)
    b1 = engine.generate_daily_briefing(use_cache=True)
    hits_before = get_briefing_cache_stats()["hits"]
    b2 = engine.generate_daily_briefing(use_cache=True)
    hits_after = get_briefing_cache_stats()["hits"]
    assert b1["headline"] == b2["headline"]
    assert hits_after == hits_before + 1

    invalidate_briefing_cache()
    assert get_briefing_cache_stats()["entries"] == 0


def test_perf07_single_instance_mutex_blocks_duplicate():
    """[PERF-07] OS single-instance lock prevents duplicate process launch and allows re-acquisition after release."""
    unique_lock = f"Local\\AFCC_UnitTest_Mutex_{os.getpid()}_{time.monotonic_ns()}"
    acquired1, handle1 = acquire_single_instance_lock(unique_lock)
    try:
        assert acquired1 is True
        acquired2, handle2 = acquire_single_instance_lock(unique_lock)
        assert acquired2 is False
        assert handle2 is None
    finally:
        release_single_instance_lock(handle1)

    acquired3, handle3 = acquire_single_instance_lock(unique_lock)
    try:
        assert acquired3 is True
    finally:
        release_single_instance_lock(handle3)


def test_perf08_transcript_delta_unchanged_fast_path(tmp_path):
    """[PERF-08] parse_transcript(since_step=latest) hits O(1) unchanged fast path and antigravity.js caps DOM at 80."""
    conv_dir = tmp_path / "conv_perf08" / ".system_generated" / "logs"
    conv_dir.mkdir(parents=True, exist_ok=True)
    t_path = conv_dir / "transcript.jsonl"
    steps = [
        {"step_index": 1, "type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "<USER_REQUEST>\nHello\n</USER_REQUEST>", "created_at": "2026-11-20T10:00:00Z"},
        {"step_index": 2, "type": "PLANNER_RESPONSE", "source": "MODEL", "content": "Hi there!", "thinking": "", "tool_calls": [], "created_at": "2026-11-20T10:00:01Z"},
    ]
    t_path.write_text("\n".join(json.dumps(s) for s in steps) + "\n", encoding="utf-8")

    saved_cache = dict(ag_mirror._TRANSCRIPT_MEM_CACHE)
    try:
        ag_mirror._TRANSCRIPT_MEM_CACHE.update({
            "path": None, "mtime_ns": -1, "size": -1, "first_sig": b"", "tail_only": False, "raw_steps": [], "line_count": 0
        })
        with patch.object(ag_mirror, "get_active_transcript_path", return_value=t_path):
            full_res = ag_mirror.parse_transcript(limit=80)
            assert full_res["status"] == "success"
            assert full_res["latest_step"] == 2
            assert len(full_res["messages"]) == 2
            assert full_res["unchanged"] is False

            before_hits = ag_mirror.get_transcript_cache_stats()["delta_unchanged_hits"]
            delta_res = ag_mirror.parse_transcript(limit=80, since_step=2)
            assert delta_res["status"] == "success"
            assert delta_res["unchanged"] is True
            assert delta_res["latest_step"] == 2
            assert delta_res["messages"] == []
            assert ag_mirror.get_transcript_cache_stats()["delta_unchanged_hits"] == before_hits + 1
    finally:
        ag_mirror._TRANSCRIPT_MEM_CACHE.clear()
        ag_mirror._TRANSCRIPT_MEM_CACHE.update(saved_cache)

    ag_js = (WEB_JS_DIR / "antigravity.js").read_text(encoding="utf-8")
    assert "since_step=" in ag_js
    assert "MAX_TRANSCRIPT_DOM_MESSAGES = 80" in ag_js
    assert "data.unchanged" in ag_js


def test_perf09_daemon_shared_db_deferral_and_working_set_trim():
    """[PERF-09] FleetDaemon reuses self.db, defers heavy pulses under RAM pressure cleanly, and trims idle working set."""
    daemon = FleetDaemon()
    assert daemon._get_db() is daemon.db

    with (
        patch.object(opt_mod, "get_memory_status", return_value={"percent_used": 91.5, "avail_gb": 1.2}),
        patch.object(daemon, "_is_battery_power_low", return_value=False),
    ):
        assert daemon._should_defer_heavy_pulse("unit_test_pulse", ram_threshold_pct=85.0, max_deferrals=3) is True
        assert daemon._should_defer_heavy_pulse("unit_test_pulse", ram_threshold_pct=85.0, max_deferrals=3) is True
        assert daemon._should_defer_heavy_pulse("unit_test_pulse", ram_threshold_pct=85.0, max_deferrals=3) is True
        # 4th call bypasses deferral to guarantee zero starvation
        assert daemon._should_defer_heavy_pulse("unit_test_pulse", ram_threshold_pct=85.0, max_deferrals=3) is False

    trim_res = daemon._trim_idle_working_set()
    assert "gc_collected" in trim_res
    assert "pruned_connections" in trim_res


def test_perf10_resource_telemetry_endpoint():
    """[PERF-10] GET /api/diagnostics/resources reports bounded cache stats, process RSS MB, threads, and SQLite pool metrics."""
    telemetry = get_process_resource_telemetry()
    assert telemetry["status"] == "ok"
    assert telemetry["process_rss_mb"] >= 0
    assert telemetry["active_threads"] >= 1
    assert "sqlite_pool" in telemetry
    assert "http_cache" in telemetry
    assert "optimizer_cache" in telemetry
    assert "briefing_cache" in telemetry
    assert "transcript_cache" in telemetry

    h, out = _make_handler("GET", "/api/diagnostics/resources")
    h.do_GET()
    status_line, _, body = _split_http_response(out.getvalue())
    assert "200 OK" in status_line
    parsed = json.loads(body.decode("utf-8"))
    assert parsed["status"] == "ok"
    assert "http_pool_max_workers" in parsed
