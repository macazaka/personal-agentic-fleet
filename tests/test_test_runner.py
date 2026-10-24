"""Unit tests for fleet.tools.test_runner."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fleet.core.database import FleetDatabase
from fleet.tools.test_runner import TestStatsPlugin, get_latest_results, run_test_suite



def test_test_stats_plugin():
    plugin = TestStatsPlugin()

    # Call report passed
    rep_pass = MagicMock()
    rep_pass.when = "call"
    rep_pass.passed = True
    rep_pass.failed = False
    rep_pass.skipped = False
    rep_pass.nodeid = "test_pass"
    rep_pass.duration = 0.05
    plugin.pytest_runtest_logreport(rep_pass)
    assert plugin.passed == 1
    assert plugin.total == 1

    # Call report failed
    rep_fail = MagicMock()
    rep_fail.when = "call"
    rep_fail.passed = False
    rep_fail.failed = True
    rep_fail.skipped = False
    rep_fail.nodeid = "test_fail"
    rep_fail.duration = 0.02
    rep_fail.longrepr = "AssertionError"
    plugin.pytest_runtest_logreport(rep_fail)
    assert plugin.failed == 1
    assert plugin.total == 2

    # Call report skipped
    rep_skip = MagicMock()
    rep_skip.when = "call"
    rep_skip.passed = False
    rep_skip.failed = False
    rep_skip.skipped = True
    rep_skip.nodeid = "test_skip"
    rep_skip.duration = 0.01
    plugin.pytest_runtest_logreport(rep_skip)
    assert plugin.skipped == 1

    # Setup report error
    rep_setup_err = MagicMock()
    rep_setup_err.when = "setup"
    rep_setup_err.failed = True
    rep_setup_err.nodeid = "test_setup_err"
    rep_setup_err.duration = 0.01
    rep_setup_err.longrepr = "SetupError"
    plugin.pytest_runtest_logreport(rep_setup_err)
    assert plugin.errors == 1


def test_run_test_suite_mocked():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test.db")
        with patch("pytest.main", return_value=0):
            with patch("coverage.Coverage") as mock_cov_cls:
                mock_cov = MagicMock()
                mock_cov_cls.return_value = mock_cov
                mock_cov.report.return_value = 99.2

                results = run_test_suite(db)
                assert results["status"] in ("PASS", "FAIL")
                assert results["coverage_pct"] == 99.2
                assert db.get_latest_test_run() is not None


def test_get_latest_results():
    from fleet.tools.test_runner import get_latest_results

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_res_file = Path(tmpdir) / "latest.json"
        tmp_res_file.write_text('{"pass_pct": 100.0, "total_tests": 38}', encoding="utf-8")

        # 1. From results file
        with patch("fleet.tools.test_runner.RESULTS_FILE", tmp_res_file):
            data = get_latest_results()
            assert data["pass_pct"] == 100.0

        # 2. From database
        with patch("fleet.tools.test_runner.RESULTS_FILE", Path(tmpdir) / "missing.json"):
            db = FleetDatabase(db_path=Path(tmpdir) / "test.db")
            db.save_test_run(
                total_tests=38,
                passed_tests=38,
                failed_tests=0,
                pass_pct=100.0,
                coverage_pct=98.5,
                duration_sec=1.5,
                status="PASS",
                details_json='{"status": "PASS", "from_db": true}'
            )
            data_db = get_latest_results(db)
            assert data_db.get("from_db") is True

        # 3. Fallback when neither file nor db has runs
        with patch("fleet.tools.test_runner.RESULTS_FILE", Path(tmpdir) / "missing2.json"):
            empty_db = FleetDatabase(db_path=Path(tmpdir) / "empty.db")
            with patch("fleet.tools.test_runner.run_test_suite", return_value={"status": "TRIGGERED"}):
                data_empty = get_latest_results(empty_db)
                assert data_empty["status"] == "TRIGGERED"


def test_test_runner_error_handling_and_main():
    import runpy

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_db_path = Path(tmpdir) / "test.db"
        db = FleetDatabase(db_path=tmp_db_path)

        # 1. Coverage report raises exception & DB error & file write error
        with patch("pytest.main", return_value=1):
            with patch("coverage.Coverage") as mock_cov_cls:
                mock_cov = MagicMock()
                mock_cov_cls.return_value = mock_cov
                mock_cov.report.side_effect = Exception("Coverage report fail")

                bad_db = MagicMock()
                bad_db.save_test_run.side_effect = Exception("DB error")

                with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
                    res = run_test_suite(bad_db)
                    assert res["coverage_pct"] == 0.0
                    assert "db_error" in res


        # 2. Corrupted RESULTS_FILE and corrupted DB details_json
        corrupted_file = Path(tmpdir) / "corrupt.json"
        corrupted_file.write_text("invalid json {", encoding="utf-8")
        with patch("fleet.tools.test_runner.RESULTS_FILE", corrupted_file):
            db.save_test_run(
                total_tests=1,
                passed_tests=1,
                failed_tests=0,
                pass_pct=100.0,
                coverage_pct=99.0,
                duration_sec=0.1,
                status="PASS",
                details_json="not valid json"
            )
            data = get_latest_results(db)
            assert data["total_tests"] == 1


def test_run_test_suite_isolated():
    from fleet.tools.test_runner import run_test_suite_isolated

    mock_db = MagicMock()
    with patch("subprocess.run") as mock_sub:
        with patch("fleet.tools.test_runner.get_latest_results", return_value={"status": "PASS", "total_tests": 76}):
            res = run_test_suite_isolated(mock_db)
            assert res["status"] == "PASS"
            mock_db.save_test_run.assert_called_once()

    # DB error branch
    bad_db = MagicMock()
    bad_db.save_test_run.side_effect = Exception("DB write failed")
    with patch("subprocess.run"):
        with patch("fleet.tools.test_runner.get_latest_results", return_value={"status": "PASS", "total_tests": 76}):
            res2 = run_test_suite_isolated(bad_db)
            assert res2["status"] == "PASS"

    with patch("subprocess.run", side_effect=Exception("Subprocess timeout")):
        res_err = run_test_suite_isolated()
        assert res_err["status"] == "ERROR"




