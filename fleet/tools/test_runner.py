"""
Automated Test Runner & Coverage Engine for Personal Agentic Fleet.
Executes pytest with coverage measurement at Tier 0 (0 Tokens / $0.00).
Persists test metrics into FleetDatabase and latest_test_results.json.
"""

import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import coverage
import pytest

from fleet.config import BASE_DIR, DATA_DIR
from fleet.core.database import FleetDatabase

RESULTS_FILE = DATA_DIR / "latest_test_results.json"
PROJECT_ROOT = BASE_DIR.parent


class TestStatsPlugin:
    __test__ = False

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0
        self.total = 0
        self.tests = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.total += 1
            if report.passed:
                self.passed += 1
                self.tests.append({
                    "name": report.nodeid,
                    "status": "PASS",
                    "duration_sec": round(report.duration, 4)
                })
            elif report.failed:
                self.failed += 1
                self.tests.append({
                    "name": report.nodeid,
                    "status": "FAIL",
                    "duration_sec": round(report.duration, 4),
                    "error": str(report.longrepr)[:200]
                })
            elif report.skipped:
                self.skipped += 1
                self.tests.append({
                    "name": report.nodeid,
                    "status": "SKIP",
                    "duration_sec": round(report.duration, 4)
                })
        elif report.when == "setup" and report.failed:
            self.total += 1
            self.errors += 1
            self.tests.append({
                "name": report.nodeid,
                "status": "ERROR",
                "duration_sec": round(report.duration, 4),
                "error": str(report.longrepr)[:200]
            })


def run_test_suite(db: Optional[FleetDatabase] = None) -> Dict[str, Any]:
    """
    Executes the full unit test suite with code coverage analysis.
    Returns structured results and stores them in database and JSON.
    """
    # Set headless SDL drivers for pygame tests and enforce zero-token test mode
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["FLEET_TEST_MODE"] = "1"

    database = db or FleetDatabase()
    database.set_setting("token_exhaustion_override", "")
    try:
        from fleet.core.antigravity_mirror import AGENT_STATE, set_active_model
        AGENT_STATE["status"] = "idle"
        set_active_model("gemini-3.8-flash-high")
    except Exception:
        pass
    start_time = time.time()

    # Configure Coverage
    cov = coverage.Coverage(
        config_file=str(PROJECT_ROOT / ".coveragerc"),
    )



    cov.start()

    # Ensure pre-imported modules are fully traced under coverage
    import importlib
    for mod_name in list(sys.modules.keys()):
        if (mod_name.startswith("fleet") or mod_name == "pong") and mod_name != "fleet.tools.test_runner":
            try:
                importlib.reload(sys.modules[mod_name])
            except Exception:
                pass



    plugin = TestStatsPlugin()
    tests_dir = str(PROJECT_ROOT / "tests")

    # Run pytest
    exit_code = pytest.main(

        [
            "-q",
            "--tb=short",
            tests_dir,
        ],
        plugins=[plugin]
    )

    cov.stop()
    cov.save()

    try:
        database.set_setting("token_exhaustion_override", "")
        from fleet.core.antigravity_mirror import AGENT_STATE, set_active_model
        AGENT_STATE["status"] = "idle"
        set_active_model("gemini-3.8-flash-high")
    except Exception:
        pass

    # Capture coverage report
    rep_io = io.StringIO()
    try:
        coverage_pct = round(cov.report(file=rep_io), 2)
    except Exception:
        coverage_pct = 0.0

    duration = round(time.time() - start_time, 2)
    total_tests = plugin.total
    passed_tests = plugin.passed
    failed_tests = plugin.failed + plugin.errors
    pass_pct = round((passed_tests / total_tests * 100), 1) if total_tests > 0 else 0.0
    status = "PASS" if failed_tests == 0 and total_tests > 0 else "FAIL"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results: Dict[str, Any] = {
        "timestamp": now_str,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "skipped_tests": plugin.skipped,
        "pass_pct": pass_pct,
        "coverage_pct": coverage_pct,
        "duration_sec": duration,
        "status": status,
        "exit_code": int(exit_code),
        "tests": plugin.tests[:60],
    }

    # Save to database
    try:
        run_id = database.save_test_run(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            pass_pct=pass_pct,
            coverage_pct=coverage_pct,
            duration_sec=duration,
            status=status,
            details_json=json.dumps(results)
        )
        results["run_id"] = run_id
    except Exception as e:
        results["db_error"] = str(e)

    # Save to JSON file for instant API retrieval
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    except Exception:
        pass

    return results


def get_latest_results(db: Optional[FleetDatabase] = None) -> Dict[str, Any]:
    """Retrieve the most recent test run results from file or database."""
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    database = db or FleetDatabase()
    latest = database.get_latest_test_run()
    if latest:
        try:
            data = json.loads(latest.get("details_json", "{}"))
            if data:
                return data
        except Exception:
            pass
        return latest

    # If no test has run yet, trigger one
    return run_test_suite(database)


def run_test_suite_isolated(db: Optional[FleetDatabase] = None) -> Dict[str, Any]:
    """
    Executes the test suite in an isolated subprocess to protect the live server memory.
    Returns structured results.
    """
    try:
        import subprocess
        hidden_kwargs: Dict[str, Any] = {}
        if os.name == "nt":
            hidden_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            si = subprocess.STARTUPINFO()
            si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
            si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            hidden_kwargs["startupinfo"] = si
        subprocess.run(
            [sys.executable, "-m", "fleet.tools.test_runner"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(PROJECT_ROOT),
            **hidden_kwargs,
        )
        results = get_latest_results(db)
        if db and results and results.get("status") in ("PASS", "FAIL"):
            try:
                db.save_test_run(
                    total_tests=results.get("total_tests", 0),
                    passed_tests=results.get("passed_tests", 0),
                    failed_tests=results.get("failed_tests", 0),
                    pass_pct=results.get("pass_pct", 0.0),
                    coverage_pct=results.get("coverage_pct", 0.0),
                    duration_sec=results.get("duration_sec", 0.0),
                    status=results.get("status", "UNKNOWN"),
                    details_json=json.dumps(results)
                )
            except Exception:
                pass
        return results
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "total_tests": 0, "passed_tests": 0}


if __name__ == "__main__":
    res = run_test_suite()
    print(f"Tests: {res['passed_tests']}/{res['total_tests']} Passed ({res['pass_pct']}%)")
    print(f"Coverage: {res['coverage_pct']}%")
    print(f"Duration: {res['duration_sec']}s")
