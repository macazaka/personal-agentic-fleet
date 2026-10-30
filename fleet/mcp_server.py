"""
FastMCP Server for Personal Agentic Fleet.
Exposes fleet capabilities to Google Antigravity via Model Context Protocol (MCP).
All tool executions are routed through the Deterministic Event Bus for 0-token local execution.
"""

import json
from typing import Any, Dict, Optional
MCPServer: Any
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    class _FallbackMCPServer:
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

        def run(self, *args: Any, **kwargs: Any) -> None:
            pass

    MCPServer = _FallbackMCPServer

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
def fleet_toggle_routine(routine_id: int | str) -> str:
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
    import fleet.server as srv
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
        manifest = srv.agent_registry.customize_agent(agent_id, updates)
        return json.dumps({"status": "success", "agent": manifest}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(description="Create and scaffold a new custom Studio v2.0 agent (from explicit fields or a 1-step natural-language prompt) with typed SQLite fields, declarative UI blocks, live FleetScheduler registration, and EventBus triggers.")
def fleet_create_custom_agent(
    agent_id: str = "",
    name: str = "",
    icon: str = "✨",
    description: str = "",
    order: int = 80,
    nl_prompt: str = "",
    ui_blocks: Optional[list[str]] = None,
    fields: Optional[list[dict[str, Any]]] = None,
    schedule_cadence: str = "",
    event_triggers: Optional[list[str]] = None,
    intelligence_mode: str = "",
) -> str:
    """Scaffold a brand new custom agent (supports v1 explicit args and Phase 4 v2.0 NL Studio synthesis)."""
    import fleet.server as srv
    registry = srv.agent_registry
    try:
        synth: dict[str, Any] = {}
        if nl_prompt and nl_prompt.strip():
            from fleet.core.agent_studio import synthesize_agent_from_prompt
            synth = synthesize_agent_from_prompt(
                nl_prompt.strip(),
                custom_id=agent_id.strip() or None,
                requested_blocks=ui_blocks,
            )

        eff_name = (name or synth.get("name") or "").strip()
        eff_id = (agent_id or synth.get("agent_id") or "").strip()
        if not eff_name or not eff_id:
            return json.dumps({
                "status": "error",
                "message": "Provide either 'nl_prompt' or both 'agent_id' and 'name'.",
            }, indent=2)

        eff_icon = icon if (icon and icon != "✨") else str(synth.get("icon") or icon or "✨")
        eff_desc = (description or synth.get("description") or nl_prompt or eff_name).strip()
        eff_blocks = ui_blocks or synth.get("ui_blocks")
        eff_fields = fields or synth.get("fields")
        eff_cadence = (schedule_cadence or synth.get("schedule_cadence") or "daily_morning").strip()
        eff_triggers = event_triggers if event_triggers is not None else synth.get("event_triggers")
        eff_intel = (intelligence_mode or synth.get("intelligence_mode") or "hybrid").strip()
        raw_sched_obj = synth.get("schedule")
        sched_obj: Dict[str, Any] = raw_sched_obj if isinstance(raw_sched_obj, dict) else {}
        routine_task = str(synth.get("routine_task") or "run_check")

        manifest = registry.create_custom_agent(
            agent_id=eff_id,
            name=eff_name,
            icon=eff_icon,
            permissions=synth.get("permissions"),
            description=eff_desc,
            initial_order=order,
            ui_blocks=eff_blocks,
            routine_task=routine_task,
            schedule_display=str(sched_obj.get("display") or "Daily at 09:00"),
            category=str(synth.get("category") or "Productivity"),
            archetype=str(synth.get("archetype") or "tracker"),
            intelligence_mode=eff_intel,
            model=synth.get("model"),
            system_prompt=synth.get("system_prompt"),
            fields=eff_fields,
            checklist_items=synth.get("checklist_items"),
            event_triggers=eff_triggers,
            schedule_cadence=eff_cadence,
            schedule=sched_obj or None,
        )

        registered_schedule = None
        synced_playbooks: list[Any] = []
        try:
            from fleet.api.settings_api import _sync_custom_agent_events, _sync_custom_agent_schedule
            raw_mf_sched = manifest.get("schedule")
            eff_sched_info: Dict[str, Any] = raw_mf_sched if isinstance(raw_mf_sched, dict) else sched_obj
            registered_schedule = _sync_custom_agent_schedule(
                agent_id=manifest["id"],
                name=manifest["name"],
                icon=manifest["icon"],
                routine_task=str(manifest.get("routine_task") or "run_check"),
                schedule_cadence=str(manifest.get("schedule_cadence") or eff_cadence),
                schedule_info=eff_sched_info,
            )
            synced_playbooks = _sync_custom_agent_events(
                agent_id=manifest["id"],
                name=manifest["name"],
                icon=manifest["icon"],
                routine_task=str(manifest.get("routine_task") or "run_check"),
                event_triggers=manifest.get("event_triggers"),
            )
        except Exception:
            pass

        return json.dumps({
            "status": "success",
            "agent": manifest,
            "schedule": registered_schedule,
            "event_playbooks": synced_playbooks,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(description="Retrieve live SQLite dashboard state (KPIs, upcoming renewal countdowns, tracked entries, daily checklist streaks, and latest AI briefing) for any custom Studio agent.")
def fleet_get_custom_agent_state(agent_id: str) -> str:
    """Return full SQLite state and manifest summary for a custom Studio agent."""
    import fleet.server as srv
    clean_id = (agent_id or "").strip()
    if not clean_id:
        return json.dumps({"status": "error", "message": "Parameter 'agent_id' is required."}, indent=2)
    try:
        agent = srv.agent_registry.get_agent(clean_id) if getattr(srv, "agent_registry", None) else None
        manifest = agent.get_ui_manifest() if agent else {"id": clean_id}
        state = srv.db.get_custom_agent_dashboard_state(clean_id, manifest=manifest)
        return json.dumps({
            "status": "ok",
            "agent_id": clean_id,
            "name": manifest.get("name", clean_id),
            "ui_blocks": manifest.get("ui_blocks", []),
            "fields": manifest.get("fields", []),
            "state": state,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(description="Add, update, mark completed, or delete structured SQLite records for a custom Studio agent directly from Antigravity chat ($0.00 token cost).")
def fleet_manage_custom_agent_record(
    agent_id: str,
    action: str = "add",
    title: str = "",
    due_date: str = "",
    numeric_value: float = 0.0,
    record_id: int = 0,
    status: str = "ok",
    extra_json: str = "{}",
) -> str:
    """Perform CRUD ('add', 'update', 'complete', 'delete') on a custom agent's SQLite records."""
    import fleet.server as srv
    clean_id = (agent_id or "").strip()
    act = (action or "add").strip().lower()
    if not clean_id:
        return json.dumps({"status": "error", "message": "Parameter 'agent_id' is required."}, indent=2)

    try:
        extra_data = json.loads(extra_json) if extra_json and extra_json.strip() else {}
        if not isinstance(extra_data, dict):
            extra_data = {}
    except Exception:
        extra_data = {}

    try:
        agent = srv.agent_registry.get_agent(clean_id) if getattr(srv, "agent_registry", None) else None
        manifest = agent.get_ui_manifest() if agent else {}

        if act == "add":
            if not title.strip():
                return json.dumps({"status": "error", "message": "Field 'title' is required when action='add'."}, indent=2)
            new_id = srv.db.add_custom_agent_record(
                agent_id=clean_id,
                title=title.strip(),
                record_type="entry",
                data=extra_data,
                status=status or "ok",
                due_date=due_date.strip(),
                numeric_value=float(numeric_value or 0.0),
            )
            state = srv.db.get_custom_agent_dashboard_state(clean_id, manifest=manifest)
            return json.dumps({"status": "success", "action": "add", "record_id": new_id, "kpis": state.get("kpis")}, indent=2)

        if act in ("update", "complete"):
            if int(record_id or 0) <= 0:
                return json.dumps({"status": "error", "message": "Valid 'record_id' is required for update/complete."}, indent=2)
            eff_status = "completed" if act == "complete" else (status if status else None)
            updated = srv.db.update_custom_agent_record(
                agent_id=clean_id,
                record_id=int(record_id),
                title=title.strip() if title.strip() else None,
                due_date=due_date.strip() if due_date else None,
                numeric_value=float(numeric_value) if numeric_value else None,
                status=eff_status,
                data=extra_data if extra_data else None,
            )
            state = srv.db.get_custom_agent_dashboard_state(clean_id, manifest=manifest)
            return json.dumps({"status": "success", "action": act, "updated": updated, "kpis": state.get("kpis")}, indent=2)

        if act == "delete":
            if int(record_id or 0) <= 0:
                return json.dumps({"status": "error", "message": "Valid 'record_id' is required for delete."}, indent=2)
            deleted = srv.db.delete_custom_agent_record(clean_id, int(record_id))
            state = srv.db.get_custom_agent_dashboard_state(clean_id, manifest=manifest)
            return json.dumps({"status": "success", "action": "delete", "deleted": deleted, "kpis": state.get("kpis")}, indent=2)

        return json.dumps({"status": "error", "message": f"Unsupported action '{action}'. Use add, update, complete, or delete."}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(description="Ingest a document (PDF policy, Word contract, Excel/CSV sheet, Email .eml, Calendar .ics, Lab report, or inline text) into a custom Studio agent and extract structured tracking items via LLM.")
def fleet_extract_document_to_agent(
    agent_id: str,
    file_path: str = "",
    text_content: str = "",
    filename: str = "",
    extraction_hint: str = "",
    auto_commit: bool = True,
) -> str:
    """Extract structured tracking items from a document into a custom agent's SQLite tracker."""
    import base64
    from pathlib import Path
    import fleet.server as srv
    from fleet.core.document_extractor import extract_tracking_items_from_document

    clean_id = (agent_id or "").strip()
    if not clean_id:
        return json.dumps({"status": "error", "message": "Parameter 'agent_id' is required."}, indent=2)

    try:
        agent = srv.agent_registry.get_agent(clean_id) if getattr(srv, "agent_registry", None) else None
        if not agent:
            return json.dumps({"status": "error", "message": f"Agent '{clean_id}' not found."}, indent=2)

        manifest = agent.get_ui_manifest()
        b64_payload = ""
        eff_name = filename.strip()
        if file_path and file_path.strip():
            fp = Path(file_path.strip()).expanduser().resolve()
            if not fp.is_file():
                return json.dumps({"status": "error", "message": f"File not found: '{file_path}'."}, indent=2)
            b64_payload = base64.b64encode(fp.read_bytes()).decode("ascii")
            eff_name = eff_name or fp.name

        prov = str(manifest.get("provider") or "auto").strip()
        if manifest.get("intelligence_mode") == "deterministic" and not manifest.get("provider"):
            prov = "deterministic"

        ext_res = extract_tracking_items_from_document(
            filename=eff_name,
            content_base64=b64_payload,
            text_content=text_content,
            agent_id=agent.id,
            agent_name=str(manifest.get("name") or getattr(agent, "name", agent.id)),
            agent_description=str(manifest.get("description") or getattr(agent, "description", "")),
            agent_system_prompt=str(manifest.get("system_prompt") or ""),
            fields=manifest.get("fields"),
            provider=prov,
            model=str(manifest.get("model") or "") or None,
            extraction_hint=extraction_hint,
            persist_to_vault=True,
        )

        doc_rec_id = srv.db.add_custom_agent_record(
            agent_id=agent.id,
            title=ext_res["filename"],
            record_type="document",
            data={
                "filename": ext_res["filename"],
                "detected_scenario": ext_res["detected_scenario"],
                "scenario_title": ext_res["scenario_profile"]["title"],
                "summary": ext_res["document_summary"],
                "items_count": ext_res["items_count"],
                "engine_used": ext_res["engine_used"],
                "model_used": ext_res["model_used"],
            },
            status="ok",
            numeric_value=float(ext_res["items_count"]),
        )

        committed_ids: list[int] = []
        if auto_commit and ext_res["items"]:
            for item in ext_res["items"]:
                extra_d = dict(item.get("extra_fields") or {})
                extra_d.setdefault("source_document", ext_res["filename"])
                extra_d["doc_record_id"] = doc_rec_id
                cid = srv.db.add_custom_agent_record(
                    agent_id=agent.id,
                    title=str(item.get("title") or ext_res["filename"]),
                    record_type="entry",
                    data=extra_d,
                    status="ok",
                    due_date=str(item.get("due_date") or ""),
                    numeric_value=float(item.get("numeric_value") or 0.0),
                )
                committed_ids.append(cid)

        state = srv.db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
        return json.dumps({
            "status": "success",
            "agent_id": agent.id,
            "doc_record_id": doc_rec_id,
            "auto_committed": auto_commit,
            "committed_count": len(committed_ids),
            "committed_ids": committed_ids,
            "document_summary": ext_res["document_summary"],
            "detected_scenario": ext_res["detected_scenario"],
            "engine_used": ext_res["engine_used"],
            "items": ext_res["items"],
            "kpis": state.get("kpis"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    description=(
        "Analyze multiple document attachments (PDF policies, DOCX contracts, XLSX/CSV sheets, EML emails, "
        "ICS calendars, lab reports, or images) via AFCC's connected LLM to synthesize, guide, and optionally "
        "scaffold & pre-seed a new custom Studio agent."
    )
)
def fleet_create_agent_from_documents(
    file_paths: Optional[list[str]] = None,
    prompt: str = "",
    custom_id: str = "",
    provider: str = "auto",
    model: str = "",
    auto_create: bool = True,
) -> str:
    """Multi-attachment LLM-guided agent creation workflow over MCP."""
    import base64
    from pathlib import Path
    import re
    import fleet.server as srv
    from fleet.core.document_extractor import (
        analyze_multiple_documents_for_studio_creation,
        normalize_extracted_date,
        normalize_extracted_number,
        promote_staged_document_to_agent_vault,
    )

    paths = [p.strip() for p in (file_paths or []) if isinstance(p, str) and p.strip()]
    if not paths:
        return json.dumps({"status": "error", "message": "Provide at least one file path in 'file_paths'."}, indent=2)

    try:
        docs_payload = []
        for raw_p in paths[:10]:
            fp = Path(raw_p).expanduser().resolve()
            if not fp.is_file():
                return json.dumps({"status": "error", "message": f"Attachment not found: '{raw_p}'."}, indent=2)
            docs_payload.append({
                "filename": fp.name,
                "content_base64": base64.b64encode(fp.read_bytes()).decode("ascii"),
            })

        analysis = analyze_multiple_documents_for_studio_creation(
            documents=docs_payload,
            user_prompt=prompt,
            custom_id=custom_id.strip() or None,
            provider=provider or "auto",
            model=model.strip() or None,
        )
        spec = analysis["spec"]

        if not auto_create:
            return json.dumps({
                "status": "analyzed",
                "attachments_count": analysis["attachments_count"],
                "connected_llm": analysis["connected_llm"],
                "spec": spec,
                "workflow_guidance": analysis["workflow_guidance"],
                "documents": analysis["documents"],
                "items_count": analysis["extraction"]["items_count"],
            }, indent=2)

        if not getattr(srv, "agent_registry", None):
            return json.dumps({"status": "error", "message": "Agent registry unavailable."}, indent=2)

        base_id = re.sub(r"[^a-zA-Z0-9_]", "_", str(custom_id.strip() or spec["agent_id"]).lower()).strip("_") or "doc_guided_agent"
        clean_id = base_id
        suffix = 2
        while clean_id in srv.agent_registry.agents:
            clean_id = f"{base_id}_{suffix}"
            suffix += 1

        manifest = srv.agent_registry.create_custom_agent(
            agent_id=clean_id,
            name=spec["name"],
            icon=spec["icon"],
            permissions=spec["permissions"],
            description=spec["description"],
            ui_blocks=spec["ui_blocks"],
            routine_task=spec["routine_task"],
            schedule_display=spec["schedule"]["display"],
            category=spec["category"],
            archetype=spec["archetype"],
            intelligence_mode=spec.get("intelligence_mode", "hybrid"),
            model=spec.get("model"),
            system_prompt=spec.get("system_prompt"),
            fields=spec["fields"],
            checklist_items=spec.get("checklist_items"),
            event_triggers=spec.get("event_triggers"),
            outbound_actions=spec.get("outbound_actions"),
            auto_ingest_inbox=bool(spec.get("auto_ingest_inbox", True)),
            default_recurrence=str(spec.get("default_recurrence", "none")),
            schedule_cadence=spec.get("schedule_cadence", "daily_morning"),
            schedule=spec.get("schedule"),
        )

        doc_id_by_fn: dict[str, int] = {}
        default_rec = str(spec.get("default_recurrence") or "none")
        seeded_docs = 0
        seeded_items = 0
        if getattr(srv, "db", None) is not None:
            for d_res in analysis["documents"]:
                staged_rel = str((d_res.get("vault") or {}).get("vault_rel_path") or "")
                promoted_rel = promote_staged_document_to_agent_vault(staged_rel, clean_id) if staged_rel else ""
                did = srv.db.add_custom_agent_record(
                    agent_id=clean_id,
                    title=d_res["filename"][:160],
                    record_type="document",
                    data={
                        "filename": d_res["filename"],
                        "sha256": str((d_res.get("vault") or {}).get("sha256") or ""),
                        "ingestion_source": "mcp_multi_doc_creation",
                        "detected_scenario": d_res["detected_scenario"],
                        "scenario_title": d_res["scenario_profile"]["title"],
                        "scenario_icon": d_res["scenario_profile"]["icon"],
                        "summary": d_res["document_summary"],
                        "items_count": d_res["items_count"],
                        "engine_used": d_res["engine_used"],
                        "model_used": d_res["model_used"],
                        "vault_rel_path": promoted_rel or staged_rel,
                    },
                    status="ok",
                    numeric_value=float(d_res["items_count"]),
                )
                doc_id_by_fn[d_res["filename"]] = did
                seeded_docs += 1

            for item in analysis["extraction"]["items"]:
                extra_d = dict(item.get("extra_fields") or {})
                src_fn = str(extra_d.get("source_document") or "")
                if src_fn in doc_id_by_fn:
                    extra_d["doc_record_id"] = doc_id_by_fn[src_fn]
                if default_rec and default_rec != "none":
                    extra_d.setdefault("recurrence", default_rec)
                srv.db.add_custom_agent_record(
                    agent_id=clean_id,
                    title=str(item["title"])[:160],
                    record_type="entry",
                    data=extra_d,
                    status="ok",
                    due_date=normalize_extracted_date(item.get("due_date")),
                    numeric_value=normalize_extracted_number(item.get("numeric_value")),
                )
                seeded_items += 1

        return json.dumps({
            "status": "success",
            "agent_id": clean_id,
            "manifest": manifest,
            "seeded_documents_count": seeded_docs,
            "seeded_records_count": seeded_items,
            "connected_llm": analysis["connected_llm"],
            "workflow_guidance": analysis["workflow_guidance"],
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool(
    description=(
        "Ask a grounded question or issue a natural-language command ('add Policy due 2026-12-15 for 18500', "
        "'renew Policy annual', 'complete Policy') to any custom Studio agent over its SQLite records and vaulted documents."
    )
)
def fleet_ask_custom_agent(agent_id: str, message: str) -> str:
    """Phase 6: Grounded RAG Q&A and natural-language mutation over a custom Studio agent."""
    import fleet.server as srv
    from fleet.core.studio_phase6 import answer_custom_agent_chat

    try:
        clean_id = (agent_id or "").strip().lower()
        agent = srv.agent_registry.get_agent(clean_id) if getattr(srv, "agent_registry", None) else None
        if not agent:
            return json.dumps({"status": "error", "message": f"Agent '{clean_id}' not found."}, indent=2)
        res = answer_custom_agent_chat(agent=agent, db=srv.db, message=message)
        return json.dumps({
            "status": res["status"],
            "agent_id": agent.id,
            "question": res["question"],
            "answer": res["answer"],
            "mutation": res["mutation"],
            "used_llm": res["used_llm"],
            "engine": res["engine"],
            "kpis": (res.get("state") or {}).get("kpis"),
        }, indent=2)
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


@mcp.tool(description="List recurring automated agent schedules, their trigger times, intervals, and current status.")
def fleet_list_schedules() -> str:
    """List all automated agent schedules."""
    from fleet.core.scheduler import get_fleet_scheduler
    scheduler = get_fleet_scheduler()
    scheds = scheduler.get_schedules()
    if not scheds:
        return "No agent schedules configured."
    lines = [f"**Fleet Agent Schedules ({scheduler.timezone}):**"]
    for s in scheds:
        status_icon = "🟢" if s.get("enabled") else "⚪"
        stype = s.get("schedule_type", "interval")
        if stype == "time_of_day":
            timing = f"Daily at {s.get('time') or ', '.join(s.get('times', []))}"
        elif stype == "interval":
            timing = f"Every {s.get('interval_hours')}h" if s.get("interval_hours") else f"Every {s.get('interval_minutes') or (s.get('interval_seconds', 0)//60)}m"
        else:
            timing = f"Cron: {s.get('cron')}"
        lines.append(f"- {status_icon} **{s['agent']}**.{s['task']} ({timing}) - {s.get('description', '')} [ID: `{s['id']}`]")
    return "\n".join(lines)


@mcp.tool(description="Enable or disable an automated agent schedule by its ID.")
def fleet_toggle_schedule(schedule_id: str, enabled: Optional[bool] = None) -> str:
    """Toggle or set enabled status of an agent schedule."""
    from fleet.core.scheduler import get_fleet_scheduler
    scheduler = get_fleet_scheduler()
    res = scheduler.toggle_schedule(schedule_id, enabled=enabled)
    if res.get("status") == "success":
        return res["message"]
    return f"Error: {res.get('message')}"


@mcp.tool(description="Execute a scheduled agent task immediately on-demand.")
def fleet_run_scheduled_task(schedule_id: Optional[str] = None, agent: Optional[str] = None, task: Optional[str] = None) -> str:
    """Run an agent schedule immediately."""
    from fleet.core.scheduler import get_fleet_scheduler
    scheduler = get_fleet_scheduler()
    res = scheduler.run_now(schedule_id=schedule_id, agent_id=agent, task=task)
    if res.get("status") == "SUCCESS":
        return f"Successfully executed scheduled task '{res.get('task')}' on agent '{res.get('agent')}' (took {res.get('duration')}s)."
    return f"Failed to execute task: {res.get('result', {}).get('error', 'Unknown error')}"


if __name__ == "__main__":
    # Runs the stdio MCP server for Antigravity, Claude Code, GitHub Copilot, and Cursor
    mcp.run(transport="stdio")
