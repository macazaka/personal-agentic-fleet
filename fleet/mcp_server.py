"""
FastMCP Server for Personal Agentic Fleet.
Exposes fleet capabilities to Google Antigravity via Model Context Protocol (MCP).
All tool executions are routed through the Deterministic Event Bus for 0-token local execution.
"""

import json
from typing import Any, Optional
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    class MCPServer:
        """Lightweight zero-dependency fallback for MCPServer when mcp package is not installed."""
        def __init__(self, name: str = "", version: str = "", description: str = ""):
            self.name = name
            self.version = version
            self.description = description
            self.tools = {}

        def tool(self, description: str = ""):
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, *args, **kwargs):
            pass

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
        from fleet.core.token_optimizer import check_mcp_delta_response
        briefing = result["data"]
        md = briefing.get("briefing_markdown", json.dumps(briefing, indent=2))
        return check_mcp_delta_response("fleet_get_daily_briefing", md)
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
def fleet_list_tasks(status: Optional[str] = None, limit: int = 15) -> str:
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
            desc_part = f" - {t['description'][:120]}" if t.get("description") else ""
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


@mcp.tool(description="List all supported hyperscaler LLM providers (Google Gemini/Vertex, Microsoft Azure/Foundry/GitHub Models, AWS Bedrock, Anthropic Claude, OpenAI, Ollama) and detected AI developer tools (GitHub Copilot, Claude Code, Google Antigravity, Gemini CLI, Amazon Q).")
def fleet_list_hyperscalers_and_tools() -> str:
    """Return availability status of all hyperscalers and AI developer tools."""
    from fleet.core.dev_tools import detect_developer_tools
    from fleet.core.hyperscalers import HyperscalerGateway
    providers = HyperscalerGateway.list_available_providers()
    tools = detect_developer_tools()
    return json.dumps({"providers": providers, "developer_tools": tools}, indent=2)


@mcp.tool(description="Execute a prompt through the Fleet Multi-Hyperscaler Gateway (tier-0 local check first, then Google Gemini, Google Cloud Vertex AI, Microsoft Azure OpenAI/Foundry, AWS Bedrock, Anthropic Claude, OpenAI, or Local Ollama).")
def fleet_query_hyperscaler(prompt: str, provider: str = "auto", model: str = "") -> str:
    """Route an inference request to any configured hyperscaler with Tier 0 local caching."""
    from fleet.core.hyperscalers import HyperscalerGateway
    gw = HyperscalerGateway()
    res = gw.complete(prompt=prompt, provider=provider, model=model or None)
    return json.dumps(res, indent=2)


@mcp.tool(description="Customize any agent's display name, icon, order, default tab status, preferred LLM provider/model, system prompt, or settings.")
def fleet_customize_agent(
    agent_id: str,
    name: str = "",
    icon: str = "",
    order: int = -1,
    is_default: bool = False,
    provider: str = "",
    model: str = "",
    system_prompt: str = "",
    enabled: bool = True,
) -> str:
    """Customize an existing agent at runtime."""
    from fleet.server import agent_registry
    updates: dict[str, Any] = {}
    if name:
        updates["name"] = name
    if icon:
        updates["icon"] = icon
    if order >= 0:
        updates["order"] = order
    if is_default:
        updates["is_default"] = True
    if provider:
        updates["provider"] = provider
    if model:
        updates["model"] = model
    if system_prompt:
        updates["system_prompt"] = system_prompt
    updates["enabled"] = enabled

    try:
        manifest = agent_registry.customize_agent(agent_id, updates)
        return json.dumps({"status": "success", "agent": manifest}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(description="Create and scaffold a new custom agent with panel UI and backend logic in the user's private vault.")
def fleet_create_custom_agent(
    agent_id: str,
    name: str,
    icon: str = "✨",
    description: str = "",
    order: int = 80,
) -> str:
    """Scaffold a brand new custom agent."""
    from fleet.server import agent_registry
    try:
        manifest = agent_registry.create_custom_agent(
            agent_id=agent_id,
            name=name,
            icon=icon,
            description=description,
            initial_order=order,
        )
        return json.dumps({"status": "success", "agent": manifest}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)



@mcp.tool(description="Execute a developer tool command across GitHub Copilot CLI ('copilot'), Anthropic Claude Code CLI ('claude_code'), Google Gemini CLI ('gemini_cli'), or Amazon Q Developer ('aws_q').")
def fleet_run_developer_tool(tool_name: str, prompt: str) -> str:
    """Invoke an AI developer CLI tool or its cloud API fallback."""
    from fleet.core.dev_tools import (
        execute_aws_q_developer,
        execute_claude_code,
        execute_github_copilot_command,
        execute_google_gemini_cli,
    )
    t = tool_name.lower().strip()
    if t in ("copilot", "github_copilot", "gh"):
        res = execute_github_copilot_command(prompt)
    elif t in ("claude", "claude_code"):
        res = execute_claude_code(prompt)
    elif t in ("gemini", "gemini_cli", "google"):
        res = execute_google_gemini_cli(prompt)
    elif t in ("aws", "aws_q", "q"):
        res = execute_aws_q_developer(prompt)
    else:
        res = {"status": "error", "message": f"Unknown tool '{tool_name}'. Supported: copilot, claude_code, gemini_cli, aws_q"}
    return json.dumps(res, indent=2)


if __name__ == "__main__":
    # Runs the stdio MCP server for Antigravity, Claude Code, GitHub Copilot, and Cursor
    mcp.run(transport="stdio")

