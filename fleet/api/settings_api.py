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
from typing import Any, Dict, Optional
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


@router.post("/api/settings/agents/delete")
def delete_custom_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Permanently deletes a custom/catalog agent from custom_agents and unregisters it live."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    agent_id = str(body.get("id", "") or body.get("agent_id", "")).strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    try:
        res = srv.agent_registry.delete_custom_agent(agent_id)
        removed_schedules = 0
        try:
            from fleet.core.scheduler import get_fleet_scheduler
            active_sched = getattr(srv, "scheduler", None) or get_fleet_scheduler()
            if active_sched and hasattr(active_sched, "remove_agent_schedules"):
                removed_schedules = active_sched.remove_agent_schedules(agent_id)
        except Exception:
            pass
        removed_playbooks = 0
        try:
            from fleet.core.playbook_engine import remove_custom_agent_playbooks
            removed_playbooks = remove_custom_agent_playbooks(agent_id)
        except Exception:
            pass
        active_count = len(srv.agent_registry.get_manifests(include_disabled=False))
        total_count = len(srv.agent_registry.get_manifests(include_disabled=True))
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetSettings", "agent_deleted", f"Deleted custom agent '{agent_id}' ({res.get('name', agent_id)})")
        handler._send_json({
            "status": "success",
            "deleted": res,
            "removed_schedules": removed_schedules,
            "removed_playbooks": removed_playbooks,
            "active_agents_count": active_count,
            "total_agents_count": total_count,
            "message": f"Agent '{res.get('name', agent_id)}' permanently deleted.",
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
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


def _sync_custom_agent_schedule(
    agent_id: str,
    name: str,
    icon: str,
    routine_task: str,
    schedule_cadence: str,
    schedule_info: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Registers, updates, or clears a custom agent's live rule in FleetScheduler."""
    scheduler = getattr(srv, "scheduler", None)
    if not scheduler:
        try:
            from fleet.core.scheduler import get_fleet_scheduler
            scheduler = get_fleet_scheduler()
        except Exception:
            scheduler = None
    if not scheduler:
        return None
    if schedule_cadence == "manual_only":
        if hasattr(scheduler, "remove_agent_schedules"):
            scheduler.remove_agent_schedules(agent_id)
        return {"enabled": False, "mode": "manual_only"}
    if not hasattr(scheduler, "upsert_custom_schedule"):
        return None

    return scheduler.upsert_custom_schedule(
        agent_id=agent_id,
        task_name=routine_task or "run_check",
        cadence=schedule_cadence or "daily_morning",
        schedule_info=schedule_info,
        description=f"{icon} {name} ({routine_task or 'run_check'})",
        enabled=True,
        notify=True,
    )


def _sync_custom_agent_events(
    agent_id: str,
    name: str,
    icon: str,
    routine_task: str,
    event_triggers: Any,
) -> list[Dict[str, Any]]:
    """Phase 3: Registers or clears deterministic EventBus playbooks for a custom agent."""
    try:
        from fleet.core.playbook_engine import sync_custom_agent_event_playbooks
        triggers_list = event_triggers if isinstance(event_triggers, list) else []
        return sync_custom_agent_event_playbooks(
            agent_id=agent_id,
            name=name,
            icon=icon,
            routine_task=routine_task or "run_check",
            event_triggers=triggers_list,
        )
    except Exception:
        return []


@router.get("/api/studio/blueprints")
def get_studio_blueprints_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Phase 2-6: Returns curated 1-click starter blueprints, Multi-Agent Squads, UI blocks, EventBus triggers, Outbound Actions, and Document Scenarios."""
    try:
        from fleet.core.agent_studio import (
            SUPPORTED_UI_BLOCKS,
            get_starter_blueprints,
            get_supported_event_triggers,
        )
        from fleet.core.document_extractor import (
            get_document_scenario_profiles,
            resolve_afcc_connected_llm,
        )
        from fleet.core.studio_phase6 import (
            get_squad_blueprints,
            get_supported_outbound_actions,
        )
        bps = get_starter_blueprints()
        handler._send_json({
            "status": "ok",
            "blueprints": bps,
            "squad_blueprints": get_squad_blueprints(),
            "supported_ui_blocks": list(SUPPORTED_UI_BLOCKS.values()),
            "supported_event_triggers": get_supported_event_triggers(),
            "supported_outbound_actions": get_supported_outbound_actions(),
            "document_scenarios": get_document_scenario_profiles(),
            "connected_llm": resolve_afcc_connected_llm(),
            "total": len(bps),
        })
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


def _seed_studio_documents_and_records(
    clean_id: str,
    payload_source: Dict[str, Any],
    default_recurrence: str = "none",
) -> tuple[int, int]:
    """
    Promotes staged Studio documents into `fleet/data/user/agent_docs/<clean_id>/`
    and seeds extracted tracking records into `custom_agent_records`.
    Shared by both `POST /api/settings/agents/create` and `POST /api/studio/deep_build`.
    """
    active_db: Any = getattr(srv, "db", None)
    if active_db is None and hasattr(srv, "agent_registry") and srv.agent_registry is not None:
        resolver = getattr(srv.agent_registry, "_resolve_db", None)
        active_db = resolver() if callable(resolver) else getattr(srv.agent_registry, "db", None)
    if active_db is None:
        return 0, 0

    from fleet.core.document_extractor import (
        normalize_extracted_date,
        normalize_extracted_number,
        promote_staged_document_to_agent_vault,
    )

    init_docs_list: list[Dict[str, Any]] = []
    if isinstance(payload_source.get("initial_documents"), list):
        init_docs_list.extend(d for d in payload_source["initial_documents"] if isinstance(d, dict) and d.get("filename"))
    init_doc_single = payload_source.get("initial_document")
    if isinstance(init_doc_single, dict) and init_doc_single.get("filename") and not init_docs_list:
        init_docs_list.append(init_doc_single)

    doc_id_by_filename: Dict[str, int] = {}
    default_doc_rec_id = 0
    default_doc_filename = ""
    seeded_documents_count = 0
    seeded_records_count = 0

    for d_meta in init_docs_list[:15]:
        d_fname = str(d_meta["filename"])
        staged_rel = str(
            d_meta.get("vault_rel_path")
            or ((d_meta.get("vault") or {}).get("vault_rel_path") if isinstance(d_meta.get("vault"), dict) else "")
            or ""
        )
        promoted_rel = promote_staged_document_to_agent_vault(staged_rel, clean_id) if staged_rel else ""
        sha_hex = str(
            d_meta.get("sha256")
            or ((d_meta.get("vault") or {}).get("sha256") if isinstance(d_meta.get("vault"), dict) else "")
            or ""
        )
        d_rec_id = active_db.add_custom_agent_record(
            agent_id=clean_id,
            title=d_fname[:160],
            record_type="document",
            data={
                "filename": d_fname,
                "sha256": sha_hex,
                "ingestion_source": "studio_creation_workflow",
                "detected_scenario": str(d_meta.get("detected_scenario") or ""),
                "scenario_title": str(
                    d_meta.get("scenario_title")
                    or ((d_meta.get("scenario_profile") or {}).get("title") if isinstance(d_meta.get("scenario_profile"), dict) else "")
                    or ""
                ),
                "scenario_icon": str(
                    d_meta.get("scenario_icon")
                    or ((d_meta.get("scenario_profile") or {}).get("icon") if isinstance(d_meta.get("scenario_profile"), dict) else "")
                    or "📄"
                ),
                "summary": str(d_meta.get("document_summary") or d_meta.get("summary") or ""),
                "items_count": int(d_meta.get("items_count") or 0),
                "engine_used": str(d_meta.get("engine_used") or ""),
                "model_used": str(d_meta.get("model_used") or ""),
                "vault_rel_path": promoted_rel or staged_rel,
            },
            status="ok",
            numeric_value=float(d_meta.get("items_count") or 0),
        )
        doc_id_by_filename[d_fname] = d_rec_id
        seeded_documents_count += 1
        if default_doc_rec_id == 0:
            default_doc_rec_id = d_rec_id
            default_doc_filename = d_fname

    init_records = payload_source.get("initial_records")
    if isinstance(init_records, list):
        for item in init_records[:100]:
            if not isinstance(item, dict):
                continue
            it_title = str(item.get("title") or "").strip()
            if not it_title:
                continue
            extra_d = dict(item.get("extra_fields") or {}) if isinstance(item.get("extra_fields"), dict) else {}
            src_fn = str(item.get("source_document") or extra_d.get("source_document") or default_doc_filename or "").strip()
            if src_fn:
                extra_d["source_document"] = src_fn
            linked_doc_id = doc_id_by_filename.get(src_fn, default_doc_rec_id)
            if linked_doc_id > 0:
                extra_d.setdefault("doc_record_id", linked_doc_id)
            if default_recurrence and default_recurrence != "none":
                extra_d.setdefault("recurrence", default_recurrence)
            active_db.add_custom_agent_record(
                agent_id=clean_id,
                title=it_title[:160],
                record_type="entry",
                data=extra_d,
                status="ok",
                due_date=normalize_extracted_date(item.get("due_date")),
                numeric_value=normalize_extracted_number(item.get("numeric_value")),
            )
            seeded_records_count += 1

    return seeded_documents_count, seeded_records_count


@router.post("/api/studio/squads/deploy")
def deploy_agent_squad_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 6: Scaffolds, registers, schedules, and wires an entire Multi-Agent Squad in 1 click."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return
    squad_id = str(body.get("squad_id") or body.get("id") or "").strip()
    if not squad_id:
        handler._send_json({"status": "error", "message": "Missing required field 'squad_id'"}, status=400)
        return
    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    try:
        from fleet.core.studio_phase6 import get_squad_blueprints
        squad = next((s for s in get_squad_blueprints() if s.get("id") == squad_id), None)
        if not squad:
            handler._send_json({"status": "error", "message": f"Unknown squad blueprint '{squad_id}'"}, status=404)
            return

        deployed: list[Dict[str, Any]] = []
        base_order = int(body.get("initial_order", 72))
        for idx, member in enumerate(squad.get("agents") or []):
            base_id = re.sub(r"[^a-zA-Z0-9_]", "_", str(member.get("id") or f"squad_agent_{idx+1}").lower()).strip("_")
            clean_id = base_id
            suffix = 2
            while clean_id in srv.agent_registry.agents:
                clean_id = f"{base_id}_{suffix}"
                suffix += 1

            m_name = str(member.get("name") or clean_id)
            if clean_id != base_id:
                m_name = f"{m_name} ({suffix - 1})"
            m_icon = str(member.get("icon") or squad.get("icon") or "✨")
            m_routine = str(member.get("routine_task") or "run_check")
            m_cadence = str(member.get("schedule_cadence") or "daily_morning")
            m_sched = member.get("schedule") if isinstance(member.get("schedule"), dict) else {}

            manifest = srv.agent_registry.create_custom_agent(
                agent_id=clean_id,
                name=m_name,
                icon=m_icon,
                permissions=member.get("permissions"),
                description=str(member.get("description") or ""),
                initial_order=base_order + idx,
                ui_blocks=member.get("ui_blocks"),
                routine_task=m_routine,
                schedule_display=str(m_sched.get("display") or "Daily at 09:00"),
                category=str(member.get("category") or squad.get("category") or "Productivity"),
                archetype=str(member.get("archetype") or "tracker"),
                intelligence_mode=str(member.get("intelligence_mode") or "hybrid"),
                fields=member.get("fields"),
                checklist_items=member.get("checklist_items"),
                event_triggers=member.get("event_triggers"),
                outbound_actions=member.get("outbound_actions"),
                auto_ingest_inbox=bool(member.get("auto_ingest_inbox", False)),
                default_recurrence=str(member.get("default_recurrence") or "none"),
                schedule_cadence=m_cadence,
                schedule=m_sched,
            )
            sched_res = _sync_custom_agent_schedule(
                agent_id=clean_id,
                name=m_name,
                icon=m_icon,
                routine_task=m_routine,
                schedule_cadence=m_cadence,
                schedule_info=m_sched,
            )
            ev_res = _sync_custom_agent_events(
                agent_id=clean_id,
                name=m_name,
                icon=m_icon,
                routine_task=m_routine,
                event_triggers=manifest.get("event_triggers"),
            )
            deployed.append({
                "id": clean_id,
                "name": m_name,
                "icon": m_icon,
                "manifest": manifest,
                "schedule": sched_res,
                "event_playbooks": ev_res,
            })

        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity(
                "FleetAgentCreator",
                "squad_deployed",
                f"Deployed Multi-Agent Squad '{squad['title']}' ({len(deployed)} agents: {', '.join(a['id'] for a in deployed)})",
            )
        from fleet.tools.system_tools import send_notification
        send_notification(
            f"{squad.get('icon', '🤝')} Squad Deployed",
            f"Activated {len(deployed)} coordinated agents in '{squad['title']}'.",
        )
        handler._send_json({
            "status": "success",
            "squad_id": squad["id"],
            "squad_title": squad["title"],
            "deployed_count": len(deployed),
            "primary_agent_id": deployed[0]["id"] if deployed else "",
            "agents": deployed,
            "message": f"Deployed '{squad['title']}' ({len(deployed)} coordinated agents).",
        })
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/documents/analyze")
def analyze_studio_document_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Phase 5 & Multi-Attachment Studio Workflow: Analyzes one or multiple uploaded attachments
    during Step 1 of Zero-Code Agent Studio via AFCC's connected LLM to guide the agent creation
    workflow, synthesize a unified cross-document Blueprint, and pre-stage tracking items.
    """
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    try:
        from fleet.core.document_extractor import analyze_multiple_documents_for_studio_creation

        raw_docs = body.get("documents")
        if isinstance(raw_docs, list) and len(raw_docs) > 0:
            doc_list = [d for d in raw_docs if isinstance(d, dict)]
        else:
            doc_list = [
                {
                    "filename": str(body.get("filename") or ""),
                    "content_base64": str(body.get("content_base64") or ""),
                    "text_content": str(body.get("text_content") or ""),
                }
            ]

        result = analyze_multiple_documents_for_studio_creation(
            documents=doc_list,
            user_prompt=str(body.get("prompt") or ""),
            custom_id=str(body.get("id") or "").strip() or None,
            provider=str(body.get("provider") or "auto"),
            model=str(body.get("model") or "").strip() or None,
        )
        handler._send_json(result)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/dry_run")
def dry_run_agent_studio_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 2: Validates AST, sandbox permissions, and simulates an agent dry-run before activation."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    raw_spec = body.get("spec")
    spec: Dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else body
    sample_input = str(body.get("sample_input") or "")
    try:
        from fleet.core.agent_studio import dry_run_agent_spec
        result = dry_run_agent_spec(spec=spec, sample_input=sample_input)
        handler._send_json(result, status=200 if result.get("status") == "ok" else 400)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
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


def _resolve_evolve_manifest_and_runtime(body: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads an agent's live manifest (overlaid with any draft Studio spec) and non-PII SQLite telemetry."""
    raw_spec = body.get("spec")
    spec_dict: Dict[str, Any] = raw_spec if isinstance(raw_spec, dict) else {}
    agent_id = str(
        body.get("id")
        or body.get("agent_id")
        or spec_dict.get("id")
        or spec_dict.get("agent_id")
        or ""
    ).strip()

    live_manifest: Dict[str, Any] = {}
    if agent_id and hasattr(srv, "agent_registry") and srv.agent_registry:
        ag = srv.agent_registry.get_agent(agent_id)
        if not ag:
            all_ag = getattr(srv.agent_registry, "_all_discovered_agents", {})
            if isinstance(all_ag, dict):
                ag = all_ag.get(agent_id)
        if ag and hasattr(ag, "get_ui_manifest"):
            raw_m = ag.get_ui_manifest()
            if isinstance(raw_m, dict):
                live_manifest = dict(raw_m)

    if not live_manifest and not spec_dict:
        if agent_id:
            raise KeyError(agent_id)
        raise ValueError("Field 'id' or 'spec' is required.")

    effective_manifest: Dict[str, Any] = dict(live_manifest)
    for k, v in spec_dict.items():
        if v is not None:
            effective_manifest[k] = v
    if agent_id and not effective_manifest.get("id"):
        effective_manifest["id"] = agent_id

    runtime_summary: Dict[str, Any] = {}
    eff_id = str(effective_manifest.get("id") or agent_id or "").strip()
    active_db = getattr(srv, "db", None)
    if eff_id and active_db and hasattr(active_db, "get_custom_agent_dashboard_state"):
        try:
            st = active_db.get_custom_agent_dashboard_state(eff_id, manifest=effective_manifest)
            if isinstance(st, dict):
                raw_kpis = st.get("kpis")
                kpis: Dict[str, Any] = raw_kpis if isinstance(raw_kpis, dict) else {}
                raw_cds = st.get("countdowns")
                cds: list[Any] = raw_cds if isinstance(raw_cds, list) else []
                overdue_cnt = sum(1 for c in cds if isinstance(c, dict) and c.get("urgency") == "overdue")
                runtime_summary = {
                    "entries_count": int(kpis.get("entries_count") or 0),
                    "documents_count": int(kpis.get("documents_count") or 0),
                    "due_soon_count": int(kpis.get("due_soon") or 0),
                    "overdue_count": overdue_cnt,
                    "numeric_sum": kpis.get("numeric_sum", 0),
                    "runs_count": int(kpis.get("runs_count") or 0),
                }
        except Exception:
            runtime_summary = {}

    return effective_manifest, runtime_summary


@router.post("/api/studio/evolve/suggestions")
def generate_studio_evolve_suggestions_endpoint(handler: Any, body: Dict[str, Any]):
    """
    AI Evolution Advisor: Automatically analyzes an existing custom agent via AFCC's connected LLM
    when 'Evolve in Studio' is clicked and returns 10 tailored, selectable improvements.
    """
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    try:
        from fleet.core.agent_studio import generate_agent_evolution_suggestions

        effective_manifest, runtime_summary = _resolve_evolve_manifest_and_runtime(body)
        provider = str(body.get("provider") or "auto").strip() or "auto"
        model = str(body.get("model") or "").strip() or None
        raw_count = body.get("count", 10)
        target_count = int(raw_count) if isinstance(raw_count, (int, float, str)) and str(raw_count).isdigit() else 10

        result = generate_agent_evolution_suggestions(
            agent_manifest=effective_manifest,
            runtime_summary=runtime_summary,
            provider=provider,
            model=model,
            target_count=target_count,
            force_refresh=bool(body.get("force_refresh", False)),
        )
        handler._send_json(result)
    except KeyError as ke:
        handler._send_json({"status": "error", "message": f"Agent {ke} not found"}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/evolve/parse_custom")
def parse_custom_evolve_improvement_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Parses a user-entered custom evolution improvement into a structured Studio blueprint patch
    so users can add their own custom improvements alongside the 10 LLM suggestions.
    """
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    text = str(body.get("text") or body.get("improvement") or "").strip()
    if not text:
        handler._send_json({"status": "error", "message": "Field 'text' is required"}, status=400)
        return
    try:
        from fleet.core.agent_studio import parse_custom_improvement_to_patch

        effective_manifest: Dict[str, Any] = {}
        try:
            effective_manifest, _ = _resolve_evolve_manifest_and_runtime(body)
        except (KeyError, ValueError):
            raw_spec = body.get("spec")
            if isinstance(raw_spec, dict):
                effective_manifest = raw_spec

        suggestion = parse_custom_improvement_to_patch(text=text, current_manifest=effective_manifest)
        handler._send_json({"status": "ok", "suggestion": suggestion})
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/create")
def create_new_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Scaffolds, registers, schedules, and activates a brand-new custom agent package."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    # Support 1-step Express creation directly from natural-language prompt
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
    category = str(body.get("category", "Productivity")).strip() or "Productivity"
    description = str(body.get("description", "")).strip() or f"User custom agent: {name}"
    archetype = str(body.get("archetype", "tracker")).strip() or "tracker"
    intelligence_mode = str(body.get("intelligence_mode", "hybrid")).strip() or "hybrid"
    model = str(body.get("model", "")).strip() or None
    system_prompt = body.get("system_prompt")

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
        permissions: list[str] = ["db:read", "db:write", "ui:render"]
    else:
        permissions = [str(perm_aliases.get(p, p)) for p in raw_perms if p is not None]
        invalid = [p for p in permissions if p not in ALLOWED_AGENT_PERMISSIONS]
        if invalid:
            handler._send_json({"status": "error", "message": f"Invalid permissions: {invalid}"}, status=400)
            return

    initial_order = int(body.get("order", 70))
    ui_blocks = body.get("ui_blocks") if isinstance(body.get("ui_blocks"), list) else None
    fields = body.get("fields") if isinstance(body.get("fields"), list) else None
    checklist_items = body.get("checklist_items") if isinstance(body.get("checklist_items"), list) else None
    event_triggers = body.get("event_triggers") if isinstance(body.get("event_triggers"), list) else None
    outbound_actions = body.get("outbound_actions") if isinstance(body.get("outbound_actions"), list) else None
    auto_ingest_inbox = bool(body.get("auto_ingest_inbox", False))
    default_recurrence = str(body.get("default_recurrence", "none")).strip().lower() or "none"
    routine_task = str(body.get("routine_task", "run_check")).strip() or "run_check"
    schedule_cadence = str(body.get("schedule_cadence", "daily_morning")).strip() or "daily_morning"
    schedule_info: Dict[str, Any] = body.get("schedule") if isinstance(body.get("schedule"), dict) else {}  # type: ignore[assignment]
    schedule_display = str(schedule_info.get("display", "Daily at 09:00"))

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
            category=category,
            archetype=archetype,
            intelligence_mode=intelligence_mode,
            model=model,
            system_prompt=str(system_prompt) if system_prompt else None,
            fields=fields,
            checklist_items=checklist_items,
            event_triggers=event_triggers,
            outbound_actions=outbound_actions,
            auto_ingest_inbox=auto_ingest_inbox,
            default_recurrence=default_recurrence,
            schedule_cadence=schedule_cadence,
            schedule=schedule_info,
        )

        custom_settings = body.get("settings")
        prompt = body.get("prompt")
        provider = body.get("provider")
        overrides: Dict[str, Any] = {}
        if custom_settings and isinstance(custom_settings, dict):
            overrides["settings"] = custom_settings
        if system_prompt:
            overrides["system_prompt"] = str(system_prompt)
        if prompt:
            overrides["prompt"] = str(prompt)
        if model:
            overrides["model"] = model
        if provider:
            overrides["provider"] = str(provider)
        if overrides:
            manifest = srv.agent_registry.customize_agent(clean_id, overrides)

        # Register live FleetScheduler rule automatically
        registered_schedule = _sync_custom_agent_schedule(
            agent_id=clean_id,
            name=name,
            icon=icon,
            routine_task=routine_task,
            schedule_cadence=schedule_cadence,
            schedule_info=schedule_info,
        )

        # Phase 3: Wire deterministic EventBus trigger playbooks automatically
        synced_playbooks = _sync_custom_agent_events(
            agent_id=clean_id,
            name=name,
            icon=icon,
            routine_task=routine_task,
            event_triggers=manifest.get("event_triggers") if isinstance(manifest, dict) else event_triggers,
        )

        # Phase 5 & Multi-Attachment Workflow: Seed all uploaded documents, promote vaulted files, and seed extracted records
        seeded_documents_count, seeded_records_count = _seed_studio_documents_and_records(
            clean_id=clean_id,
            payload_source=body,
            default_recurrence=default_recurrence,
        )

        # Optional immediate initial run upon activation
        initial_run = None
        if body.get("run_immediately"):
            created_agent = srv.agent_registry.get_agent(clean_id)
            if created_agent:
                try:
                    initial_run = created_agent.execute_task(routine_task, payload={"skip_llm": True})
                except Exception as run_exc:
                    initial_run = {"status": "warning", "message": str(run_exc)}

        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetAgentCreator", "agent_created", f"Created and registered custom agent '{clean_id}' ({name})")

        from fleet.tools.system_tools import send_notification
        send_notification("⚡ New Agent Created", f"Agent '{name}' was created and activated in your fleet.")

        handler._send_json({
            "status": "success",
            "message": f"Agent '{name}' successfully created and activated.",
            "agent_id": clean_id,
            "manifest": manifest,
            "schedule": registered_schedule,
            "event_playbooks": synced_playbooks,
            "seeded_documents_count": seeded_documents_count,
            "seeded_records_count": seeded_records_count,
            "initial_run": initial_run,
        })
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/evolve")
def evolve_custom_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 2 & 3: Evolves an existing custom agent's UI blocks, fields, schedule, triggers, and code in-place."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    agent_id = str(body.get("id") or body.get("agent_id") or "").strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    try:
        manifest = srv.agent_registry.evolve_custom_agent(agent_id, body)
        raw_sched = manifest.get("schedule")
        sched_info: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
        registered_schedule = _sync_custom_agent_schedule(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
            schedule_info=sched_info,
        )
        synced_playbooks = _sync_custom_agent_events(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            event_triggers=manifest.get("event_triggers"),
        )
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetAgentCreator", "agent_evolved", f"Evolved custom agent '{manifest['id']}' in Studio")
        handler._send_json({
            "status": "success",
            "message": f"Agent '{manifest['name']}' evolved and hot-reloaded while preserving existing data.",
            "agent_id": manifest["id"],
            "manifest": manifest,
            "schedule": registered_schedule,
            "event_playbooks": synced_playbooks,
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.get("/api/settings/agents/revisions")
def list_custom_agent_revisions_endpoint(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Phase 4: Lists saved blueprint revision snapshots for an evolved custom agent."""
    query = urllib.parse.parse_qs(parsed_url.query)
    agent_id = (query.get("id") or query.get("agent_id") or [""])[0].strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing query parameter 'id'"}, status=400)
        return
    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return
    try:
        revisions = srv.agent_registry.list_custom_agent_revisions(agent_id)
        handler._send_json({
            "status": "ok",
            "agent_id": agent_id,
            "count": len(revisions),
            "revisions": revisions,
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Agent '{agent_id}' not found"}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/rollback")
def rollback_custom_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 4: Restores a custom agent's blueprint from a saved revision while preserving SQLite records."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return
    agent_id = str(body.get("id") or body.get("agent_id") or "").strip()
    if not agent_id:
        handler._send_json({"status": "error", "message": "Missing required field 'id'"}, status=400)
        return
    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    revision_id = str(body.get("revision_id") or "").strip() or None
    try:
        manifest = srv.agent_registry.rollback_custom_agent(agent_id, revision_id=revision_id)
        raw_sched = manifest.get("schedule")
        sched_info: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
        registered_schedule = _sync_custom_agent_schedule(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
            schedule_info=sched_info,
        )
        synced_playbooks = _sync_custom_agent_events(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            event_triggers=manifest.get("event_triggers"),
        )
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity(
                "FleetAgentCreator",
                "agent_rollback",
                f"Rolled back custom agent '{manifest['id']}' to revision '{manifest.get('restored_revision_id', 'latest')}'",
            )
        handler._send_json({
            "status": "success",
            "agent_id": manifest["id"],
            "restored_revision_id": manifest.get("restored_revision_id"),
            "manifest": manifest,
            "schedule": registered_schedule,
            "event_playbooks": synced_playbooks,
            "message": f"Restored '{manifest['name']}' from revision '{manifest.get('restored_revision_id', 'latest')}' (SQLite records preserved).",
        })
    except KeyError as ke:
        handler._send_json({"status": "error", "message": str(ke)}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/settings/agents/clone")
def clone_custom_agent_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 3: Clones an existing agent into a fresh custom agent blueprint without copying private SQLite data."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    source_id = str(body.get("source_id") or body.get("id") or body.get("agent_id") or "").strip()
    if not source_id:
        handler._send_json({"status": "error", "message": "Missing required field 'source_id'"}, status=400)
        return

    if not hasattr(srv, "agent_registry") or not srv.agent_registry:
        handler._send_json({"status": "error", "message": "Agent registry unavailable"}, status=503)
        return

    target_id = str(body.get("target_id") or "").strip() or None
    new_name = str(body.get("name") or "").strip() or None

    try:
        manifest = srv.agent_registry.clone_custom_agent(
            source_agent_id=source_id,
            target_agent_id=target_id,
            new_name=new_name,
        )
        raw_sched = manifest.get("schedule")
        sched_info: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
        registered_schedule = _sync_custom_agent_schedule(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
            schedule_info=sched_info,
        )
        synced_playbooks = _sync_custom_agent_events(
            agent_id=manifest["id"],
            name=manifest["name"],
            icon=manifest["icon"],
            routine_task=str(manifest.get("routine_task") or "run_check"),
            event_triggers=manifest.get("event_triggers"),
        )
        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity("FleetAgentCreator", "agent_cloned", f"Cloned '{source_id}' -> '{manifest['id']}' ({manifest['name']})")
        handler._send_json({
            "status": "success",
            "message": f"Cloned '{source_id}' into '{manifest['name']}' ({manifest['id']}).",
            "agent_id": manifest["id"],
            "manifest": manifest,
            "schedule": registered_schedule,
            "event_playbooks": synced_playbooks,
        })
    except KeyError:
        handler._send_json({"status": "error", "message": f"Source agent '{source_id}' not found"}, status=404)
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/deep_build")
def deep_build_agent_studio_endpoint(handler: Any, body: Dict[str, Any]):
    """
    Phase 3: 1-Click 'Deep-Build with Antigravity' Direct Bridge.
    Optionally scaffolds/evolves the custom agent package first, builds an engineering brief,
    and dispatches directly to Antigravity Live (`srv.execute_dashboard_command`).
    """
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return

    nested_spec = body.get("spec")
    raw_spec: Dict[str, Any] = nested_spec if isinstance(nested_spec, dict) else body
    spec: Dict[str, Any] = dict(raw_spec)

    if not spec.get("name"):
        nl_prompt = str(spec.get("nl_prompt") or spec.get("prompt") or spec.get("description") or "").strip()
        if nl_prompt:
            from fleet.core.agent_studio import synthesize_agent_from_prompt
            synth = synthesize_agent_from_prompt(nl_prompt, custom_id=spec.get("id") or spec.get("agent_id"))
            spec = {**synth, **spec, "name": synth["name"], "id": spec.get("id") or synth["agent_id"]}

    name = str(spec.get("name") or "").strip()
    if not name:
        handler._send_json({"status": "error", "message": "Agent 'name' or 'prompt' is required for Deep-Build."}, status=400)
        return

    raw_id = str(spec.get("id") or spec.get("agent_id") or name).strip()
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id.lower()).strip("_")
    clean_id = re.sub(r"_+", "_", clean_id) or "custom_agent"
    spec["id"] = clean_id
    spec["agent_id"] = clean_id

    scaffold_first = bool(body.get("scaffold_first", True))
    is_evolve = bool(body.get("is_evolve", False))
    manifest: Optional[Dict[str, Any]] = None

    try:
        seeded_documents_count = 0
        seeded_records_count = 0
        if scaffold_first and hasattr(srv, "agent_registry") and srv.agent_registry:
            existing = srv.agent_registry.agents.get(clean_id)
            if existing and getattr(existing, "is_custom", False):
                manifest = srv.agent_registry.evolve_custom_agent(clean_id, spec)
            elif not existing:
                raw_sched_obj = spec.get("schedule")
                sched_obj: Dict[str, Any] = raw_sched_obj if isinstance(raw_sched_obj, dict) else {}
                def_rec = str(spec.get("default_recurrence") or body.get("default_recurrence") or "none").strip().lower()
                manifest = srv.agent_registry.create_custom_agent(
                    agent_id=clean_id,
                    name=name,
                    icon=str(spec.get("icon") or "⚡").strip() or "⚡",
                    permissions=spec.get("permissions") if isinstance(spec.get("permissions"), list) else ["db:read", "db:write", "ui:render"],
                    description=str(spec.get("description") or f"User custom agent: {name}"),
                    ui_blocks=spec.get("ui_blocks") if isinstance(spec.get("ui_blocks"), list) else None,
                    routine_task=str(spec.get("routine_task") or "run_check"),
                    schedule_display=str(sched_obj.get("display", "Daily at 09:00")),
                    category=str(spec.get("category") or "Productivity"),
                    archetype=str(spec.get("archetype") or "tracker"),
                    intelligence_mode=str(spec.get("intelligence_mode") or "hybrid"),
                    model=str(spec.get("model") or "").strip() or None,
                    system_prompt=str(spec.get("system_prompt")) if spec.get("system_prompt") else None,
                    fields=spec.get("fields") if isinstance(spec.get("fields"), list) else None,
                    checklist_items=spec.get("checklist_items") if isinstance(spec.get("checklist_items"), list) else None,
                    event_triggers=spec.get("event_triggers") if isinstance(spec.get("event_triggers"), list) else None,
                    outbound_actions=spec.get("outbound_actions") if isinstance(spec.get("outbound_actions"), list) else None,
                    auto_ingest_inbox=bool(spec.get("auto_ingest_inbox", False)),
                    default_recurrence=def_rec,
                    schedule_cadence=str(spec.get("schedule_cadence") or "daily_morning"),
                    schedule=sched_obj,
                )
                seed_source = body if ("initial_documents" in body or "initial_records" in body or "initial_document" in body) else spec
                seeded_documents_count, seeded_records_count = _seed_studio_documents_and_records(
                    clean_id=clean_id,
                    payload_source=seed_source,
                    default_recurrence=def_rec,
                )
            elif is_evolve:
                raise ValueError(f"Built-in agent '{clean_id}' cannot be overwritten by Deep-Build.")

            if manifest:
                raw_sched_info = manifest.get("schedule")
                sched_info: Dict[str, Any] = raw_sched_info if isinstance(raw_sched_info, dict) else {}
                _sync_custom_agent_schedule(
                    agent_id=manifest["id"],
                    name=manifest["name"],
                    icon=manifest["icon"],
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
                    schedule_info=sched_info,
                )
                _sync_custom_agent_events(
                    agent_id=manifest["id"],
                    name=manifest["name"],
                    icon=manifest["icon"],
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    event_triggers=manifest.get("event_triggers"),
                )

        from fleet.core.agent_studio import build_antigravity_deep_build_prompt
        deep_prompt = build_antigravity_deep_build_prompt(spec)
        chosen_model = str(body.get("model") or spec.get("model") or "").strip() or None

        dispatch_result: Dict[str, Any] = {"status": "queued"}
        if hasattr(srv, "execute_dashboard_command") and callable(srv.execute_dashboard_command):
            try:
                raw_dispatch = srv.execute_dashboard_command(
                    deep_prompt, images=[], model=chosen_model, bypass_tier0=True
                )
            except TypeError:
                raw_dispatch = srv.execute_dashboard_command(deep_prompt, images=[], model=chosen_model)
            if isinstance(raw_dispatch, dict):
                dispatch_result = raw_dispatch

        dispatch_status = str(dispatch_result.get("status") or "success").strip().lower()
        dispatch_type = str(dispatch_result.get("type") or "").strip().lower()
        dispatch_msg = str(dispatch_result.get("message") or "").strip()

        if dispatch_status in ("error", "failed", "blocked", "busy"):
            http_code = 409 if dispatch_status == "busy" else 502
            err_msg = dispatch_msg or f"Deep-Build dispatch failed ({dispatch_status})."
            if hasattr(srv, "db") and srv.db:
                srv.db.log_activity(
                    "FleetAgentCreator",
                    "studio_deep_build_failed",
                    f"Deep-Build dispatch failed for '{clean_id}' ({name}): {err_msg}",
                )
            handler._send_json(
                {
                    "status": "error",
                    "dispatch_status": dispatch_status,
                    "agent_id": clean_id,
                    "manifest": manifest,
                    "dispatch": dispatch_result,
                    "message": err_msg,
                },
                status=http_code,
            )
            return

        if hasattr(srv, "db") and srv.db:
            srv.db.log_activity(
                "FleetAgentCreator",
                "studio_deep_build",
                f"Dispatched Antigravity Deep-Build for custom agent '{clean_id}' ({name}) [{dispatch_status}]",
            )

        if dispatch_status == "vaulted" or dispatch_type == "token_exhausted":
            user_message = (
                dispatch_msg
                or f"Scaffolded '{name}', and vaulted Deep-Build prompt safely due to active token quota limit."
            )
        elif dispatch_status == "queued" or dispatch_type in ("queued", "note_logged"):
            user_message = (
                dispatch_msg
                or f"Scaffolded '{name}' and queued Deep-Build brief in Antigravity Live."
            )
        else:
            user_message = (
                f"Scaffolded '{name}' and launched Deep-Build in Antigravity Live."
                + (f" ({dispatch_msg})" if dispatch_msg else "")
            )

        handler._send_json({
            "status": "success",
            "dispatch_status": dispatch_status,
            "agent_id": clean_id,
            "manifest": manifest,
            "seeded_documents_count": seeded_documents_count,
            "seeded_records_count": seeded_records_count,
            "prompt": deep_prompt,
            "dispatch": dispatch_result,
            "message": user_message,
        })
    except ValueError as ve:
        handler._send_json({"status": "error", "message": str(ve)}, status=400)
    except Exception as e:
        handler._send_json({"status": "error", "message": str(e)}, status=500)


@router.post("/api/studio/events/emit")
def emit_studio_event_trigger_endpoint(handler: Any, body: Dict[str, Any]):
    """Phase 3: Dispatches a canonical Fleet EventBus trigger to all subscribed playbooks & custom agents."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected a JSON object"}, status=400)
        return
    event_name = str(body.get("event") or body.get("event_name") or "").strip()
    if not event_name:
        handler._send_json({"status": "error", "message": "Field 'event' is required"}, status=400)
        return
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else None
    try:
        from fleet.core.playbook_engine import dispatch_event_trigger
        res = dispatch_event_trigger(
            event_name=event_name,
            payload=payload,
            agent_registry=getattr(srv, "agent_registry", None),
            db=getattr(srv, "db", None),
        )
        handler._send_json(res)
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
    """UX-02 -> UX-01: Scaffolds, schedules, and activates a recommended agent in 1 click."""
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
        manifest = res.get("manifest") if isinstance(res.get("manifest"), dict) else None
        if manifest:
            sched_info = manifest.get("schedule") if isinstance(manifest.get("schedule"), dict) else {}
            res["schedule"] = _sync_custom_agent_schedule(
                agent_id=manifest["id"],
                name=manifest["name"],
                icon=manifest.get("icon", "⚡"),
                routine_task=str(manifest.get("routine_task") or "run_check"),
                schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
                schedule_info=sched_info,
            )
            res["event_playbooks"] = _sync_custom_agent_events(
                agent_id=manifest["id"],
                name=manifest["name"],
                icon=manifest.get("icon", "⚡"),
                routine_task=str(manifest.get("routine_task") or "run_check"),
                event_triggers=manifest.get("event_triggers"),
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
    """UX-04: Audits and imports a .fleetagent JSON bundle into custom_agents, syncing schedule & triggers."""
    if not isinstance(body, dict):
        handler._send_json({"status": "error", "message": "Expected JSON object"}, status=400)
        return
    nested_pack = body.get("pack")
    pack_data: Dict[str, Any] = nested_pack if isinstance(nested_pack, dict) else body
    from fleet.core.database import is_test_environment
    from fleet.config import DATA_DIR
    custom_dir = getattr(getattr(srv, "agent_registry", None), "custom_agents_dir", None)
    if not custom_dir:
        sub_vault = "test_user" if is_test_environment() else "user"
        custom_dir = DATA_DIR / sub_vault / "custom_agents"
    try:
        from fleet.core.agent_catalog import import_agent_pack
        res = import_agent_pack(pack_data, custom_dir, agent_registry=getattr(srv, "agent_registry", None))
        raw_manifest = pack_data.get("manifest")
        manifest: Dict[str, Any] = raw_manifest if isinstance(raw_manifest, dict) else {}
        imported_id = str(res.get("agent_id") or manifest.get("id") or "")
        if imported_id and manifest:
            raw_sched_info = manifest.get("schedule")
            sched_info: Dict[str, Any] = raw_sched_info if isinstance(raw_sched_info, dict) else {}
            if manifest.get("schedule_cadence") or sched_info:
                res["schedule"] = _sync_custom_agent_schedule(
                    agent_id=imported_id,
                    name=str(manifest.get("name") or imported_id),
                    icon=str(manifest.get("icon") or "⚡"),
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
                    schedule_info=sched_info,
                )
            if manifest.get("event_triggers"):
                res["event_playbooks"] = _sync_custom_agent_events(
                    agent_id=imported_id,
                    name=str(manifest.get("name") or imported_id),
                    icon=str(manifest.get("icon") or "⚡"),
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    event_triggers=manifest.get("event_triggers"),
                )
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

