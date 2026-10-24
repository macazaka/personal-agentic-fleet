"""
FastMCP Server for Personal Agentic Fleet.
Exposes fleet capabilities to Google Antigravity via Model Context Protocol (MCP).
All tool executions are routed through the Deterministic Event Bus for 0-token local execution.
"""

import json
from typing import Any, Optional
from mcp.server.mcpserver import MCPServer

from fleet.core.event_bus import FleetEvent, bus

# Initialize FastMCP Server
mcp = MCPServer(
    name="personal-fleet",
    version="1.0.0",
    description="Personal Agentic Fleet management tools for tasks, routines, briefings, and notifications."
)


@mcp.tool(description="Get the daily morning briefing, high-priority (P1) tasks, habit completion %, and focus summary.")
def fleet_get_daily_briefing() -> str:
    """Retrieve today's morning briefing and priority goals."""
    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="GET_BRIEFING"
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        briefing = result["data"]
        return briefing.get("briefing_markdown", json.dumps(briefing, indent=2))
    return f"Error fetching briefing: {result.get('message')}"


@mcp.tool(description="Add a new task to your personal task board.")
def fleet_add_task(
    title: str,
    priority: str = "P2",
    description: str = "",
    due_date: Optional[str] = None
) -> str:
    """
    Add a task to the personal fleet.
    Priority must be 'P1' (High), 'P2' (Medium), or 'P3' (Low).
    """
    task_desc = (description or "").strip() or f"Task: {title.strip()}"
    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="ADD_TASK",
        payload={
            "title": title,
            "priority": priority.upper(),
            "description": task_desc,
            "due_date": due_date
        }
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        task_id = result["data"]["task_id"]
        return f"Successfully added task #{task_id}: '{title}' [{priority.upper()}]"
    return f"Error adding task: {result.get('message')}"


@mcp.tool(description="List tasks from the task board with optional status filter ('pending', 'completed', or None for all).")
def fleet_list_tasks(status: Optional[str] = None, limit: int = 50) -> str:
    """List open or completed tasks."""

    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="LIST_TASKS",
        payload={"status": status, "limit": limit}
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        tasks = result["data"]["tasks"]
        if not tasks:
            return "No tasks found matching criteria."
        lines = []
        for t in tasks:
            icon = "✅" if t["status"] == "completed" else ("🔴" if t["priority"] == "P1" else ("🟡" if t["priority"] == "P2" else "🟢"))
            desc_part = f" - {t['description']}" if t.get("description") else ""
            lines.append(f"- #{t['id']} {icon} [{t['priority']}] **{t['title']}**{desc_part} ({t['status']})")
        return "\n".join(lines)
    return f"Error listing tasks: {result.get('message')}"


@mcp.tool(description="Mark a task as completed by its ID.")
def fleet_complete_task(task_id: int) -> str:
    """Mark a task as completed."""
    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="COMPLETE_TASK",
        payload={"task_id": task_id}
    )
    result = bus.dispatch(event)
    if result["status"] == "success" and result["data"].get("completed"):
        return f"Task #{task_id} marked as completed!"
    return f"Failed to complete task #{task_id}: {result.get('message')}"


@mcp.tool(description="List daily routines/habits and see what is completed today.")
def fleet_list_routines() -> str:
    """List all daily routines and habits."""
    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="LIST_ROUTINES"
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        routines = result["data"]["routines"]
        lines = ["**Today's Daily Routines:**"]
        for r in routines:
            check = "✅" if r.get("completed_today") else "⬜"
            lines.append(f"- {check} `{r['time_target']}` **{r['title']}** (ID: {r['id']})")
        return "\n".join(lines)
    return f"Error listing routines: {result.get('message')}"


@mcp.tool(description="Toggle completion status of a daily routine/habit by its ID.")
def fleet_toggle_routine(routine_id: int) -> str:
    """Toggle a routine's completed status for today."""
    event = FleetEvent(
        sender="Antigravity",
        target="agenda",
        action="TOGGLE_ROUTINE",
        payload={"routine_id": routine_id}
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        return f"Routine #{routine_id} status toggled for today."
    return f"Error toggling routine: {result.get('message')}"


@mcp.tool(description="Send an immediate native Windows Desktop Toast notification.")
def fleet_send_notification(title: str, message: str) -> str:
    """Trigger a Windows desktop toast alert."""
    event = FleetEvent(
        sender="Antigravity",
        target="notification",
        action="SEND_TOAST",
        payload={"title": title, "message": message}
    )
    result = bus.dispatch(event)
    if result["status"] == "success" and result["data"].get("sent"):
        return f"Windows Toast alert sent: '{title}' - '{message}'"
    return "Failed to display notification."


@mcp.tool(description="Scan a folder on your laptop and report file count, size, and category distribution.")
def fleet_scan_directory(path: str = "~/Downloads") -> str:
    """Scan and analyze disk space and file categories in a directory."""
    event = FleetEvent(
        sender="Antigravity",
        target="files",
        action="SCAN_DIR",
        payload={"path": path}
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        data = result["data"]
        return json.dumps(data, indent=2)
    return f"Error scanning directory: {result.get('message')}"


@mcp.tool(description="Classify Gmail emails from this month and last month into 5 folders: 0) Meetings, 1) Respond, 2) Note, 3) FYI, 4) Ignore.")
def fleet_classify_recent_emails(dry_run: bool = False, auto_archive_ignore: bool = False) -> str:
    """
    Run automated classification on all emails spanning this month and last month.
    Applies Gmail labels: Fleet/0-Meetings, Fleet/1-Respond, Fleet/2-Note, Fleet/3-FYI, Fleet/4-Ignore.
    Set dry_run=True to preview classifications without modifying Gmail.
    """
    event = FleetEvent(
        sender="Antigravity",
        target="email",
        action="CLASSIFY_RECENT",
        payload={"dry_run": dry_run, "auto_archive_ignore": auto_archive_ignore}
    )
    result = bus.dispatch(event)
    if result["status"] == "success":
        data = result["data"]
        counts = data["counts"]
        mode = "[DRY RUN PREVIEW]" if data["dry_run"] else "[APPLIED TO GMAIL]"
        summary = (
            f"**Gmail Classification Complete {mode}**\n"
            f"Total Processed: {data['total_processed']} emails (From this month & last month)\n"
            f"- 📅 Meetings: {counts.get('Meetings', 0)}\n"
            f"- 💬 Respond: {counts.get('Respond', 0)}\n"
            f"- 📝 Note: {counts.get('Note', 0)}\n"
            f"- ℹ️ FYI: {counts.get('FYI', 0)}\n"
            f"- 🚫 Ignore: {counts.get('Ignore', 0)}\n"
        )
        return summary
    return f"Error classifying emails: {result.get('message')}"


if __name__ == "__main__":
    # Runs the stdio MCP server for Antigravity
    mcp.run(transport="stdio")

