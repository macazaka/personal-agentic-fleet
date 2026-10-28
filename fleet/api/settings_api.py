"""
Fleet Settings & Dynamic Customization API for Personal Agentic Fleet.
Enables browser-based configuration of system preferences, timezone, notifications,
hyperscaler defaults, and runtime activation/deactivation of agents.
"""

from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict
import urllib.parse

from fleet.api.router import router
from fleet.config import DATA_DIR, load_fleet_config
import fleet.server as srv


DEFAULT_SETTINGS = {
    "timezone": "Asia/Kolkata (IST, UTC+05:30)",
    "notifications_enabled": "true",
    "quiet_hours_enabled": "false",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "default_provider": "auto",
    "default_model": "gemini-2.5-flash",
    "ollama_url": "http://localhost:11434",
    "cost_policy": "PREFER_ZERO_TOKEN_CODE",
    "auto_backup_enabled": "true",
    "theme": "dark",
    "layout": "sidebar_dock",
}

AVAILABLE_LAYOUTS = [
    {
        "id": "sidebar_dock",
        "name": "IDE Left Activity Dock & Sidebar (Default)",
        "badge": "Best for 100+ Agents",
        "description": "VS Code / Linear style collapsible vertical sidebar with live search, pinned favorites, and collapsible domain category tree. Keeps the top header ultra-clean.",
    },
    {
        "id": "command_deck",
        "name": "Compact Pinned Bar + Spotlight Command Deck",
        "badge": "Max Screen Width",
        "description": "Raycast / Terminal style two-tier top command deck displaying up to 5 pinned agents, an automatic +N overflow counter, a prominent Ctrl+K omni-search bar, and the off-canvas Fleet Hub drawer.",
    },
    {
        "id": "launchpad_grid",
        "name": "Mission Control Bento Matrix / Launchpad",
        "badge": "Multi-Domain Matrix",
        "description": "Datadog / Launchpad style collapsible multi-column agent matrix dock at the top of the workspace with instant domain category tabs, live search, and high-density status chips.",
    },
]

AVAILABLE_THEMES = [
    {"id": "dark", "name": "Cyber Neon Dark (Default)"},
    {"id": "midnight", "name": "Deep Midnight Slate"},
    {"id": "aurora", "name": "Emerald Aurora Matrix"},
    {"id": "solar", "name": "High-Contrast Obsidian Gold"},
]


def _get_merged_settings() -> Dict[str, str]:
    """Retrieves all settings from SQLite DB merged with factory defaults."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        if hasattr(srv, "db") and srv.db:
            db_settings = srv.db.get_all_settings()
            settings.update(db_settings)
    except Exception:
        pass
    return settings


@router.get("/api/settings")
def get_fleet_settings(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns global fleet settings, preferences, and all discovered agents with activation state."""
    settings = _get_merged_settings()
    all_manifests = []
    active_manifests = []

    if hasattr(srv, "agent_registry") and srv.agent_registry:
        all_manifests = srv.agent_registry.get_manifests(include_disabled=True)
        active_manifests = srv.agent_registry.get_manifests(include_disabled=False)

    handler._send_json({
        "status": "ok",
        "settings": settings,
        "available_layouts": AVAILABLE_LAYOUTS,
        "available_themes": AVAILABLE_THEMES,
        "agents": all_manifests,
        "active_agents_count": len(active_manifests),
        "total_agents_count": len(all_manifests),
        "timestamp": datetime.now().isoformat(),
    })


@router.post("/api/settings")
def update_fleet_settings(handler: Any, body: Dict[str, Any]):
    """Updates global fleet settings and preferences in the database."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object of settings"}, status=400)
        return

    settings_to_update = body.get("settings", body)
    if not isinstance(settings_to_update, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object of settings"}, status=400)
        return

    updated_keys = []
    for k, v in settings_to_update.items():
        if k in ("status", "agents", "active_agents_count", "total_agents_count", "timestamp"):
            continue
        str_val = str(v).lower() if isinstance(v, bool) else str(v)
        try:
            if hasattr(srv, "db") and srv.db:
                srv.db.set_setting(k, str_val)
                updated_keys.append(k)
        except Exception:
            pass

    if hasattr(srv, "bus") and srv.bus:
        try:
            from fleet.core.event_bus import FleetEvent
            srv.bus.dispatch(FleetEvent(sender="settings_api", target="system", action="settings_updated", payload={"keys": updated_keys}))
        except Exception:
            pass

    handler._send_json({
        "status": "success",
        "message": f"Updated {len(updated_keys)} settings.",
        "settings": _get_merged_settings(),
    })


@router.post("/api/settings/agents/toggle")
def toggle_agent_activation(handler: Any, body: Dict[str, Any]):
    """Activates or deactivates an agent by ID at runtime and persists state."""
    agent_id = str(body.get("id", "") or body.get("agent_id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    enabled = bool(body.get("enabled", True))
    try:
        manifest = srv.agent_registry.customize_agent(agent_id, {"enabled": enabled})
        active_count = len(srv.agent_registry.get_manifests(include_disabled=False))
        total_count = len(srv.agent_registry.get_manifests(include_disabled=True))

        if hasattr(srv, "db") and srv.db:
            action = "activated" if enabled else "deactivated"
            srv.db.log_activity("FleetSettings", "agent_toggle", f"Agent '{agent_id}' {action}")

        handler._send_json({
            "status": "success",
            "agent": manifest,
            "active_agents_count": active_count,
            "total_agents_count": total_count,
            "message": f"Agent '{agent_id}' {'activated' if enabled else 'deactivated'} successfully.",
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/customize")
def customize_agent_settings(handler: Any, body: Dict[str, Any]):
    """Customizes an agent's display properties, LLM model, prompt, or default status."""
    agent_id = str(body.get("id", "") or body.get("agent_id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    allowed = {
        "name", "icon", "order", "is_default", "enabled",
        "provider", "model", "system_prompt", "prompt", "custom_panel_path", "settings"
    }
    updates = {k: v for k, v in body.items() if k in allowed}

    try:
        manifest = srv.agent_registry.customize_agent(agent_id, updates)
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetSettings", "agent_customize", f"Customized agent '{agent_id}'")

        handler._send_json({
            "status": "success",
            "agent": manifest,
            "message": f"Agent '{agent_id}' customization saved.",
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/reset")
def reset_agent_settings(handler: Any, body: Dict[str, Any]):
    """Resets an agent back to factory built-in configuration."""
    agent_id = str(body.get("id", "") or body.get("agent_id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    try:
        manifest = srv.agent_registry.reset_agent(agent_id)
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetSettings", "agent_reset", f"Reset agent '{agent_id}' to defaults")

        handler._send_json({
            "status": "success",
            "agent": manifest,
            "message": f"Agent '{agent_id}' reset to factory defaults.",
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/backup/snapshot")
def create_backup_snapshot(handler: Any, body: Dict[str, Any]):
    """Creates an immediate snapshot backup of the database and agent overrides."""
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_file = DATA_DIR / "fleet.db"
    dest_name = f"fleet_snapshot_{timestamp}.db"
    dest_path = backup_dir / dest_name

    file_size = 0
    if db_file.is_file():
        try:
            shutil.copy2(db_file, dest_path)
            file_size = dest_path.stat().st_size
        except Exception as e:
            handler._send_json({"status": "error", "message": f"Failed to snapshot DB: {e}"}, status=500)
            return

    if hasattr(srv, "db") and srv.db:
        srv.db.log_activity("FleetSettings", "backup_snapshot", f"Created database snapshot {dest_name} ({file_size} bytes)")

    handler._send_json({
        "status": "success",
        "snapshot_file": dest_name,
        "path": str(dest_path),
        "size_bytes": file_size,
        "timestamp": datetime.now().isoformat(),
        "message": f"Backup snapshot created successfully: {dest_name}",
    })


# --- Version & GitHub Update APIs ---

@router.get("/api/settings/version")
def get_fleet_version_status(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns the current running version, latest GitHub release version, and update status."""
    try:
        from fleet.core.updater import check_github_for_updates
        status = check_github_for_updates(timeout_sec=3.0)
        handler._send_json(status)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/version/check")
def check_fleet_version_update(handler: Any, body: Dict[str, Any]):
    """Forces an immediate check against GitHub Releases for new updates."""
    try:
        from fleet.core.updater import check_github_for_updates
        status = check_github_for_updates(timeout_sec=5.0)
        handler._send_json(status)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/version/upgrade")
def apply_fleet_update(handler: Any, body: Dict[str, Any]):
    """Downloads/applies the latest release from GitHub (via git pull or zipball)."""
    try:
        from fleet.core.updater import download_and_apply_update
        res = download_and_apply_update()
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetUpdater", "apply_update", f"Update applied: {res.get('message')}")
        handler._send_json(res)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


# --- Agent Catalog & Remote Download APIs ---

@router.get("/api/settings/agents/catalog")
def get_agent_catalog_list(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns downloadable agents catalog with current installation status."""
    try:
        from fleet.core.agent_catalog import get_agent_catalog
        installed_ids = set()
        if hasattr(srv, "agent_registry") and srv.agent_registry:
            manifests = srv.agent_registry.get_manifests(include_disabled=True)
            installed_ids = {m["id"] for m in manifests}

        catalog = get_agent_catalog(installed_agent_ids=installed_ids)
        handler._send_json({
            "status": "ok",
            "catalog": catalog,
            "total_available": len(catalog),
            "total_installed": len([c for c in catalog if c["is_installed"]]),
        })
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/catalog/install")
def install_catalog_agent(handler: Any, body: Dict[str, Any]):
    """Downloads and installs a new agent from the catalog into custom_agents."""
    agent_id = str(body.get("id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    from fleet.core.agent_catalog import install_agent_from_catalog
    from fleet.core.database import is_test_environment
    custom_dir = getattr(srv.agent_registry, "custom_agents_dir", None)
    if not custom_dir:
        from fleet.config import DATA_DIR
        sub_vault = "test_user" if is_test_environment() else "user"
        custom_dir = DATA_DIR / sub_vault / "custom_agents"

    try:
        res = install_agent_from_catalog(agent_id, custom_dir, agent_registry=srv.agent_registry)
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetSettings", "agent_install", f"Installed agent '{agent_id}' from catalog")

        from fleet.tools.system_tools import send_notification
        send_notification("⚡ New Agent Installed", f"Agent '{res.get('name', agent_id)}' was downloaded and activated.")

        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/synthesize")
def synthesize_agent_studio_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-01: Zero-Code Natural-Language Agent Studio synthesizer endpoint."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        handler._send_json({"status": "error", "message": "Field 'prompt' is required"}, status=400)
        return
    custom_id = body.get("id")
    requested_blocks = body.get("ui_blocks") if isinstance(body.get("ui_blocks"), list) else None
    try:
        from fleet.core.agent_studio import synthesize_agent_from_prompt
        spec = synthesize_agent_from_prompt(prompt=prompt, custom_id=custom_id, requested_blocks=requested_blocks)
        handler._send_json(spec)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/create")
def create_new_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Scaffolds, registers, and activates a brand-new agent package in the user custom agents vault."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    # Support 1-step creation directly from natural-language prompt if name is omitted
    nl_prompt = str(body.get("nl_prompt", "")).strip()
    if nl_prompt and not body.get("name"):
        from fleet.core.agent_studio import synthesize_agent_from_prompt
        synth = synthesize_agent_from_prompt(nl_prompt, custom_id=body.get("id"))
        body = {**synth, **body, "name": synth["name"], "id": body.get("id") or synth["agent_id"]}

    name = str(body.get("name", "")).strip()
    if not name:
        handler._send_json({"status": "error", "message": "Agent name is required"}, status=400)
        return

    raw_id = str(body.get("id", "")).strip() or name
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id.lower()).strip("_")
    clean_id = re.sub(r"_+", "_", clean_id)
    if not clean_id:
        handler._send_json({"status": "error", "message": f"Invalid agent ID '{raw_id}'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    if clean_id in srv.agent_registry.agents:
        handler._send_json({"status": "error", "message": f"Agent with ID '{clean_id}' already exists"}, status=409)
        return

    icon = str(body.get("icon", "⚡")).strip() or "⚡"
    description = str(body.get("description", "")).strip() or f"User custom agent: {name}"
    
    # Sandboxed permissions validation and alias mapping
    from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS
    perm_aliases = {
        "network:http": "network:outbound",
        "notifications:send": "event_bus:publish",
        "system:exec": "system:diagnostics",
        "storage:data_read": "db:read",
        "storage:data_write": "db:write",
        "storage:read": "db:read",
        "storage:write": "db:write",
    }
    raw_perms = body.get("permissions")
    if not isinstance(raw_perms, list) or not raw_perms:
        permissions: list[str] = ["db:read", "ui:render"]
    else:
        permissions = [str(perm_aliases.get(p, p)) for p in raw_perms if p is not None]
        invalid = [p for p in permissions if p not in ALLOWED_AGENT_PERMISSIONS]
        if invalid:
            handler._send_json({"status": "error", "message": f"Invalid permissions: {invalid}"}, status=400)
            return

    initial_order = int(body.get("order", 70))
    ui_blocks = body.get("ui_blocks") if isinstance(body.get("ui_blocks"), list) else None
    routine_task = str(body.get("routine_task", "run_check")).strip() or "run_check"
    schedule_info = body.get("schedule") if isinstance(body.get("schedule"), dict) else {}
    schedule_display = str(schedule_info.get("display", "Daily at 09:00"))  # type: ignore[reportOptionalMemberAccess]

    try:
        manifest = srv.agent_registry.create_custom_agent(
            agent_id=clean_id,
            name=name,
            icon=icon,
            permissions=permissions,
            description=description,
            initial_order=initial_order,
            ui_blocks=ui_blocks,
            routine_task=routine_task,
            schedule_display=schedule_display,
        )

        custom_settings = body.get("settings")
        system_prompt = body.get("system_prompt")
        prompt = body.get("prompt")
        overrides = {}
        if custom_settings and isinstance(custom_settings, dict):
            overrides["settings"] = custom_settings
        if system_prompt:
            overrides["system_prompt"] = str(system_prompt)
        if prompt:
            overrides["prompt"] = str(prompt)
        if overrides:
            srv.agent_registry.customize_agent(clean_id, overrides)

        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetAgentCreator", "agent_created", f"Created and registered custom agent '{clean_id}' ({name})")

        from fleet.tools.system_tools import send_notification
        send_notification("⚡ New Agent Created", f"Agent '{name}' was created and activated in your fleet.")

        handler._send_json({
            "status": "success",
            "message": f"Agent '{name}' successfully created and activated.",
            "agent_id": clean_id,
            "manifest": manifest,
        })
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


# =========================================================================
# UX-02: Autonomous Process Discovery & Agent Recommendation Endpoints
# =========================================================================

@router.get("/api/discovery/recommendations")
def get_discovery_recommendations_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """UX-02: Returns ranked agent recommendations mined from local workstation telemetry ($0.00)."""
    try:
        from fleet.core.process_miner import mine_workstation_recommendations
        installed = set()
        if hasattr(srv, "agent_registry") and srv.agent_registry:
            installed = set(getattr(srv.agent_registry, "agents", {}).keys())
        report = mine_workstation_recommendations(
            db=getattr(srv, "db", None),
            installed_agent_ids=installed,
        )
        handler._send_json(report)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/discovery/spawn")
def spawn_discovery_recommendation_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-02 -> UX-01: Scaffolds and activates a recommended agent in 1 click."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    rec_id = str(body.get("recommendation_id", "")).strip()
    if not rec_id:
        handler._send_json({"status": "error", "message": "Field 'recommendation_id' is required"}, status=400)
        return
    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return
    try:
        from fleet.core.process_miner import spawn_recommended_agent
        res = spawn_recommended_agent(
            recommendation_id=rec_id,
            agent_registry=srv.agent_registry,
            db=getattr(srv, "db", None),
        )
        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


# =========================================================================
# UX-03: Visual Multi-Agent Playbook & Event-Chain Endpoints
# =========================================================================

@router.get("/api/playbooks")
def get_playbooks_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """UX-03: Lists all configured multi-agent playbooks."""
    try:
        from fleet.core.playbook_engine import list_playbooks
        pbs = list_playbooks()
        handler._send_json({"status": "ok", "playbooks": pbs, "total": len(pbs)})
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/playbooks")
def save_playbook_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-03: Creates or updates a multi-agent playbook."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    try:
        from fleet.core.playbook_engine import add_or_update_playbook
        saved = add_or_update_playbook(body)
        handler._send_json({"status": "success", "playbook": saved})
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/playbooks/run")
def run_playbook_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-03: Executes a multi-agent playbook immediately."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    pb_id = str(body.get("id") or body.get("playbook_id") or "").strip()
    if not pb_id:
        handler._send_json({"status": "error", "message": "Field 'playbook_id' is required"}, status=400)
        return
    try:
        from fleet.core.playbook_engine import execute_playbook
        res = execute_playbook(
            playbook_id=pb_id,
            agent_registry=getattr(srv, "agent_registry", None),
            db=getattr(srv, "db", None),
        )
        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


# =========================================================================
# UX-04: Portable .fleetagent Share Pack Export & Import Endpoints
# =========================================================================

@router.get("/api/agents/export")
def export_agent_pack_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """UX-04: Exports an agent as a SHA-256 verified .fleetagent JSON bundle."""
    query = urllib.parse.parse_qs(parsed_url.query)
    agent_id = (query.get("id", [""])[0] or "").strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Query parameter 'id' is required"}, status=400)
        return
    try:
        from fleet.core.agent_catalog import export_agent_pack
        pack = export_agent_pack(agent_id, getattr(srv, "agent_registry", None))
        handler._send_json({"status": "ok", "pack": pack})
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=404)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/agents/import")
def import_agent_pack_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-04: Audits and imports a .fleetagent JSON bundle into custom_agents."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    pack_data = body.get("pack") if isinstance(body.get("pack"), dict) else body
    from fleet.core.database import is_test_environment
    from fleet.config import DATA_DIR
    custom_dir = getattr(getattr(srv, "agent_registry", None), "custom_agents_dir", None)
    if not custom_dir:
        sub_vault = "test_user" if is_test_environment() else "user"
        custom_dir = DATA_DIR / sub_vault / "custom_agents"
    try:
        from fleet.core.agent_catalog import import_agent_pack
        res = import_agent_pack(pack_data, custom_dir, agent_registry=getattr(srv, "agent_registry", None))  # type: ignore[reportArgumentType]
        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


# =========================================================================
# UX-05: Unified Ask-Fleet Omnibar Commands & Dispatcher Endpoints
# =========================================================================

@router.get("/api/omnibar/commands")
def get_omnibar_commands_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """UX-05: Lists all @agent slash commands and omnibar shortcuts across active agents."""
    try:
        from fleet.core.omnibar_dispatcher import get_all_omnibar_commands
        cmds = get_all_omnibar_commands(getattr(srv, "agent_registry", None))
        handler._send_json({"status": "ok", "commands": cmds, "total": len(cmds)})
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/omnibar/execute")
def execute_omnibar_query_endpoint(handler: Any, body: Dict[str, Any]):
    """UX-05: Executes an Omnibar @agent command or Tier-0 query and returns an inline card."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    query = str(body.get("query", "")).strip()
    if not query:
        handler._send_json({"status": "error", "message": "Field 'query' is required"}, status=400)
        return
    try:
        from fleet.core.omnibar_dispatcher import dispatch_omnibar_query
        res = dispatch_omnibar_query(
            query=query,
            agent_registry=getattr(srv, "agent_registry", None),
            db=getattr(srv, "db", None),
        )
        handler._send_json(res)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)

