"""
Fleet Settings & Dynamic Customization API for Personal Agentic Fleet.
Enables browser-based configuration of system preferences, timezone, notifications,
hyperscaler defaults, and runtime activation/deactivation of agents.
"""

from datetime import datetime
import json
from pathlib import Path
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
}


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
        "agents": all_manifests,
        "active_agents_count": len(active_manifests),
        "total_agents_count": len(all_manifests),
        "timestamp": datetime.now().isoformat(),
    })


@router.post("/api/settings")
def update_fleet_settings(handler: Any, body: Dict[str, Any]):
    """Updates global fleet settings and preferences in the database."""
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
            srv.bus.dispatch(FleetEvent(target="system", action="settings_updated", payload={"keys": updated_keys}))
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
    agent_id = str(body.get("id", "")).strip()
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
    agent_id = str(body.get("id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    allowed = {
        "name", "icon", "order", "is_default", "enabled",
        "provider", "model", "system_prompt", "prompt", "custom_panel_path"
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
    agent_id = str(body.get("id", "")).strip()
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
