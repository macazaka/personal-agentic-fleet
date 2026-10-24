"""Unit tests for fleet.core.event_bus."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from fleet.core.database import FleetDatabase
from fleet.core.event_bus import DeterministicEventBus, FleetEvent


def test_event_bus_full_dispatch():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_bus.db"
        db = FleetDatabase(db_path=db_path)
        bus = DeterministicEventBus(db=db)

        # 1. Agenda Worker
        ev_add = FleetEvent("AgentA", "agenda", "ADD_TASK", {"title": "Task 1", "description": "Details for task 1", "priority": "P1"})
        res_add = bus.dispatch(ev_add)
        assert res_add["status"] == "success"
        task_id = res_add["data"]["task_id"]

        ev_list = FleetEvent("AgentA", "agenda", "LIST_TASKS")
        res_list = bus.dispatch(ev_list)
        assert res_list["status"] == "success"
        assert len(res_list["data"]["tasks"]) == 1

        ev_comp = FleetEvent("AgentA", "agenda", "COMPLETE_TASK", {"task_id": task_id})
        res_comp = bus.dispatch(ev_comp)
        assert res_comp["status"] == "success"

        ev_routines = FleetEvent("AgentA", "agenda", "LIST_ROUTINES")
        res_routines = bus.dispatch(ev_routines)
        assert res_routines["status"] == "success"

        ev_toggle = FleetEvent("AgentA", "agenda", "TOGGLE_ROUTINE", {"routine_id": 1})
        res_toggle = bus.dispatch(ev_toggle)
        assert res_toggle["status"] == "success"

        ev_brief = FleetEvent("AgentA", "agenda", "GET_BRIEFING")
        res_brief = bus.dispatch(ev_brief)
        assert res_brief["status"] == "success"

        ev_bad_agenda = FleetEvent("AgentA", "agenda", "UNKNOWN_ACTION")
        res_bad_agenda = bus.dispatch(ev_bad_agenda)
        assert res_bad_agenda["status"] == "error"

        # 2. Files Worker
        with patch("fleet.core.event_bus.scan_directory") as mock_scan:
            mock_scan.return_value = {"total_files": 10}
            res_scan = bus.dispatch(FleetEvent("AgentA", "files", "SCAN_DIR", {"path": tmpdir}))
            assert res_scan["status"] == "success"

        with patch("fleet.core.event_bus.find_large_files") as mock_large:
            mock_large.return_value = []
            res_large = bus.dispatch(FleetEvent("AgentA", "files", "FIND_LARGE_FILES", {"path": tmpdir}))
            assert res_large["status"] == "success"

        with patch("fleet.core.event_bus.organize_directory") as mock_org:
            mock_org.return_value = {"status": "ok"}
            res_org = bus.dispatch(FleetEvent("AgentA", "files", "ORGANIZE_DIR", {"path": tmpdir}))
            assert res_org["status"] == "success"

        res_bad_files = bus.dispatch(FleetEvent("AgentA", "files", "INVALID_FILE_ACTION"))
        assert res_bad_files["status"] == "error"

        # 3. Notification Worker
        with patch("fleet.core.event_bus.send_windows_notification") as mock_notif:
            mock_notif.return_value = True
            res_notif = bus.dispatch(FleetEvent("AgentA", "notification", "SEND_TOAST", {"title": "T", "message": "M"}))
            assert res_notif["status"] == "success"
            assert res_notif["data"]["sent"] is True

        # 4. Email Worker
        with patch("fleet.integrations.gmail_client.gmail_manager.sync_and_classify") as mock_sync:
            mock_sync.return_value = {"counts": {}}
            res_email = bus.dispatch(FleetEvent("AgentA", "email", "CLASSIFY_RECENT", {"dry_run": True}))
            assert res_email["status"] == "success"

        res_email_status = bus.dispatch(FleetEvent("AgentA", "email", "GET_STATUS"))
        assert res_email_status["status"] == "success"

        with patch("fleet.integrations.gmail_client.gmail_manager.unsubscribe_from_email") as mock_unsub:
            mock_unsub.return_value = {"status": "success", "unsubscribed": True}
            res_unsub = bus.dispatch(FleetEvent("AgentA", "email", "UNSUBSCRIBE", {"message_id": "m_123", "url": "https://unsub.com"}))
            assert res_unsub["status"] == "success"
            assert res_unsub["data"]["unsubscribed"] is True

        res_bad_email = bus.dispatch(FleetEvent("AgentA", "email", "INVALID_EMAIL_ACTION"))
        assert res_bad_email["status"] == "error"

        # 5. Unknown Target Worker
        res_unknown = bus.dispatch(FleetEvent("AgentA", "nonexistent_target", "ACTION"))
        assert res_unknown["status"] == "error"
        assert "Unknown target worker" in res_unknown["message"]

        # 6. Parallel Dispatching (dispatch_parallel)
        ev1 = FleetEvent("AgentA", "agenda", "LIST_TASKS")
        ev2 = FleetEvent("AgentA", "agenda", "LIST_ROUTINES")
        parallel_results = bus.dispatch_parallel([ev1, ev2], max_workers=2)
        assert len(parallel_results) == 2
        assert all(r["status"] == "success" for r in parallel_results)
        assert bus.dispatch_parallel([]) == []
