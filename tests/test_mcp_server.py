"""Unit tests for fleet.mcp_server."""
from unittest.mock import patch
import fleet.mcp_server as mcp_mod


def test_mcp_all_tools():
    # 1. Daily Briefing
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"briefing_markdown": "Morning Briefing"}}
        assert "Morning Briefing" in mcp_mod.fleet_get_daily_briefing()

        mock_bus.return_value = {"status": "error", "message": "DB Down"}
        assert "Error fetching briefing" in mcp_mod.fleet_get_daily_briefing()

    # 2. Add Task
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"task_id": 10}}
        assert "Successfully added task #10" in mcp_mod.fleet_add_task("Test MCP", priority="P1")

        mock_bus.return_value = {"status": "error", "message": "Failed"}
        assert "Error adding task" in mcp_mod.fleet_add_task("Test MCP")

    # 3. List Tasks
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "tasks": [
                    {"id": 1, "title": "T1", "priority": "P1", "status": "pending"},
                    {"id": 2, "title": "T2", "priority": "P2", "status": "completed"}
                ]
            }
        }
        res = mcp_mod.fleet_list_tasks()
        assert "#1" in res and "#2" in res

        # Empty tasks
        mock_bus.return_value = {"status": "success", "data": {"tasks": []}}
        assert "No tasks found" in mcp_mod.fleet_list_tasks()

        mock_bus.return_value = {"status": "error", "message": "Err"}
        assert "Error listing tasks" in mcp_mod.fleet_list_tasks()

    # 4. Complete Task
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"completed": True}}
        assert "marked as completed" in mcp_mod.fleet_complete_task(1)

        mock_bus.return_value = {"status": "error", "message": "Not found"}
        assert "Failed to complete task" in mcp_mod.fleet_complete_task(999)

    # 5. List Routines
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "routines": [
                    {"id": 1, "title": "Coffee", "time_target": "08:00", "completed_today": True},
                    {"id": 2, "title": "Yoga", "time_target": "09:00", "completed_today": False}
                ]
            }
        }
        r_res = mcp_mod.fleet_list_routines()
        assert "Coffee" in r_res

        mock_bus.return_value = {"status": "error", "message": "Fail"}
        assert "Error listing routines" in mcp_mod.fleet_list_routines()

    # 6. Toggle Routine
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"toggled": True}}
        assert "toggled" in mcp_mod.fleet_toggle_routine(1)

        mock_bus.return_value = {"status": "error", "message": "Fail"}
        assert "Error toggling routine" in mcp_mod.fleet_toggle_routine(1)

    # 7. Send Notification
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {"status": "success", "data": {"sent": True}}
        assert "Windows Toast alert sent" in mcp_mod.fleet_send_notification("Title", "Msg")

        mock_bus.return_value = {"status": "error", "message": "Fail"}
        assert "Failed to display notification" in mcp_mod.fleet_send_notification("Title", "Msg")

    # 8. Scan Directory
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {"directory": "C:/test", "total_files": 5, "total_size_mb": 1.2, "categories": {"Code": 5}}
        }
        scan_out = mcp_mod.fleet_scan_directory("C:/test")
        assert "total_files" in scan_out
        assert "C:/test" in scan_out

        mock_bus.return_value = {"status": "error", "message": "Fail"}
        assert "Error scanning directory" in mcp_mod.fleet_scan_directory("C:/test")

    # 9. Classify Emails
    with patch("fleet.mcp_server.bus.dispatch") as mock_bus:
        mock_bus.return_value = {
            "status": "success",
            "data": {
                "counts": {"Meetings": 2, "Respond": 1, "Note": 0, "FYI": 3, "Ignore": 5},
                "total_processed": 11,
                "dry_run": True
            }
        }
        email_out = mcp_mod.fleet_classify_recent_emails(dry_run=True)
        assert "Gmail Classification Complete" in email_out

        mock_bus.return_value = {"status": "error", "message": "Fail"}
        assert "Error classifying emails" in mcp_mod.fleet_classify_recent_emails()
