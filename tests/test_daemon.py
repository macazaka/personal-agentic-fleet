"""Unit tests for fleet.daemon."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from fleet.daemon import FleetDaemon


def test_daemon_triggers():
    daemon = FleetDaemon()
    daemon.bus = MagicMock()
    daemon.bus.dispatch.return_value = {
        "status": "success",
        "data": {
            "headline": "Top goal",
            "summary_stats": {"pending_count": 3, "p1_count": 1, "completed_count": 2, "completion_rate": 40.0},
            "counts": {"Meetings": 1, "Respond": 0}
        }
    }

    with patch("fleet.tools.test_runner.run_test_suite_isolated") as mock_suite:
        # 1. Trigger Morning Briefing (08:35)
        with patch("fleet.daemon.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 8, 35)
            daemon.check_and_trigger()
            assert daemon.last_briefing_date == "2026-10-13"

        # 2. Trigger Evening Review (20:05)
        with patch("fleet.daemon.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 20, 5)
            daemon.check_and_trigger()
            assert daemon.last_evening_date == "2026-10-13"

        # 3. Trigger 2-Hour Pulse Email Classification (10:00)
        with patch("fleet.daemon.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 10, 0)
            daemon.check_and_trigger()
            assert daemon.last_email_sync_hour == 10

        # 4. Trigger Scheduled Test Suite Pulse
        daemon.last_test_run_time = 0.0
        daemon.check_and_trigger()
        mock_suite.assert_called_once()
        assert daemon.last_test_run_time > 0

        # Scheduled test suite exception handled gracefully
        daemon.last_test_run_time = 0.0
        mock_suite.side_effect = Exception("Runner failed")
        daemon.check_and_trigger()


def test_daemon_run_loop_interrupt():
    daemon = FleetDaemon()
    with patch.object(daemon, "check_and_trigger", side_effect=KeyboardInterrupt):
        # Should cleanly break without unhandled exception
        daemon.run_loop(poll_interval_sec=0)

    # Normal iteration with sleep then stop
    step_calls = []
    def _normal_then_stop():
        step_calls.append(1)
        if len(step_calls) >= 2:
            raise KeyboardInterrupt

    with patch.object(daemon, "check_and_trigger", side_effect=_normal_then_stop):
        with patch("fleet.daemon.time.sleep") as mock_sleep:
            daemon.run_loop(poll_interval_sec=5)
            mock_sleep.assert_called_with(5)

    # Exception path handled
    called = []
    def _err_then_stop():
        called.append(1)
        if len(called) == 1:
            raise RuntimeError("Transient Error")
        raise KeyboardInterrupt

    with patch.object(daemon, "check_and_trigger", side_effect=_err_then_stop):
        with patch("fleet.daemon.time.sleep"):
            daemon.run_loop(poll_interval_sec=0)
    assert len(called) == 2



