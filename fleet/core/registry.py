"""
Fleet Agent Registry & Dynamic Plugin Loader.
Auto-discovers, loads, and manages lifecycle for plug-and-play agents.
Supports both built-in core agents (fleet/agents/) and private user custom agents
(fleet/data/user/custom_agents/), with runtime customization and persistent overrides.
"""

import csv
from datetime import datetime
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, List, Optional
import urllib.parse

from fleet.core.base_agent import FleetAgent

logger = logging.getLogger("fleet.registry")


class AgentRegistry:
    """
    Central registry that discovers, loads, and manages all modular Fleet Agents.
    Supports built-in agents and user-customized private agents.
    """

    def __init__(
        self,
        agents_dir: Optional[Path] = None,
        custom_agents_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
        event_bus=None,
        db=None,
    ):
        if agents_dir is None:
            self.agents_dir = Path(__file__).resolve().parent.parent / "agents"
        else:
            self.agents_dir = Path(agents_dir)

        self.config = config or {}
        self.event_bus = event_bus
        self.db = db
        self.agents: Dict[str, FleetAgent] = {}
        self.disabled_agents: Dict[str, FleetAgent] = {}
        self._all_discovered_agents: Dict[str, FleetAgent] = {}

        # User custom agents directory (persisted and git-ignored; isolated under test_user during tests)
        if custom_agents_dir is not None:
            self.custom_agents_dir = Path(custom_agents_dir)
        elif "custom_agents_dir" in self.config:
            self.custom_agents_dir = Path(self.config["custom_agents_dir"])
        else:
            from fleet.core.database import is_test_environment
            sub_vault = "test_user" if is_test_environment() else "user"
            try:
                from fleet.config import DATA_DIR
                self.custom_agents_dir = DATA_DIR / sub_vault / "custom_agents"
            except Exception:
                self.custom_agents_dir = self.agents_dir.parent / "data" / sub_vault / "custom_agents"

    def _get_overrides_file(self) -> Path:
        """Returns path to the user's persistent agent configuration overrides file."""
        from fleet.core.database import is_test_environment
        sub_vault = "test_user" if is_test_environment() else "user"
        try:
            from fleet.config import DATA_DIR
            vault = DATA_DIR / sub_vault
        except Exception:
            vault = self.agents_dir.parent / "data" / sub_vault
        vault.mkdir(parents=True, exist_ok=True)
        return vault / "agent_overrides.json"

    def load_overrides(self) -> Dict[str, Any]:
        """Loads persisted user agent customizations."""
        f = self._get_overrides_file()
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Could not load agent overrides: {e}")
        return {}

    def save_overrides(self, overrides: Dict[str, Any]) -> None:
        """Persists user agent customizations safely."""
        f = self._get_overrides_file()
        try:
            f.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Could not save agent overrides: {e}")

    def discover_and_load(self) -> Dict[str, FleetAgent]:
        """
        Scans both built-in agents_dir and user custom_agents_dir for subdirectories
        containing 'agent.py'. Instantiates each agent and merges persistent user overrides.
        """
        if not self.agents_dir.exists():
            self.agents_dir.mkdir(parents=True, exist_ok=True)

        if not self.custom_agents_dir.exists():
            try:
                self.custom_agents_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        agents_config = self.config.get("agents", {})
        default_agent_id = self.config.get("default_agent", "health")
        persisted_overrides = self.load_overrides()

        # 1. Discover built-in agents
        directories_to_scan = [(self.agents_dir, "fleet.agents")]

        # 2. Discover user custom agents (if directory exists)
        if self.custom_agents_dir.exists():
            directories_to_scan.append((self.custom_agents_dir, "fleet.custom_agents"))

        for scan_dir, module_prefix in directories_to_scan:
            for item in sorted(scan_dir.iterdir()):
                if not item.is_dir() or item.name.startswith((".", "_")):
                    continue
                agent_file = item / "agent.py"
                if not agent_file.is_file():
                    continue

                agent_id = item.name
                # Merge: built-in defaults < fleet.yaml config < persistent user overrides
                base_cfg = dict(agents_config.get(agent_id, {}))
                user_overrides = persisted_overrides.get(agent_id, {})
                agent_cfg = {**base_cfg, **user_overrides}

                try:
                    agent_instance = self._load_agent_from_file(agent_file, item, agent_cfg, module_prefix)
                    if agent_instance:
                        self._all_discovered_agents[agent_instance.id] = agent_instance
                        if default_agent_id == agent_instance.id or agent_cfg.get("is_default"):
                            agent_instance._override_default = True

                        if agent_cfg.get("enabled") is False:
                            agent_instance.enabled = False
                            self.disabled_agents[agent_instance.id] = agent_instance
                            logger.info(f"Agent '{agent_id}' is disabled in configuration.")
                        else:
                            agent_instance.enabled = True
                            self.agents[agent_instance.id] = agent_instance
                            logger.info(f"Loaded Fleet Agent: {agent_instance.display_name} [{agent_instance.id}]")
                except Exception as e:
                    logger.error(f"Failed to load agent from {agent_file}: {e}", exc_info=True)

        return self.agents

    def _resolve_db(self):
        """Returns self.db, falling back to fleet.server.db if self.db was not injected at init."""
        if self.db is not None:
            return self.db
        try:
            import fleet.server as srv
            srv_db = getattr(srv, "db", None)
            if srv_db is not None:
                self.db = srv_db
                for ag in self._all_discovered_agents.values():
                    if getattr(ag, "db", None) is None:
                        ag.db = srv_db
                return srv_db
        except Exception:
            pass
        return None

    def _load_agent_from_file(
        self,
        file_path: Path,
        agent_dir: Path,
        agent_cfg: Dict[str, Any],
        module_prefix: str = "fleet.agents",
    ) -> Optional[FleetAgent]:
        module_name = f"{module_prefix}.{agent_dir.name}.agent"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, FleetAgent)
                and attr is not FleetAgent
            ):
                return attr(
                    agent_dir=agent_dir,
                    config=agent_cfg,
                    event_bus=self.event_bus,
                    db=self._resolve_db(),
                )
        return None

    def customize_agent(self, agent_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically customizes any loaded agent at runtime and persists overrides
        to fleet/data/user/agent_overrides.json.
        """
        agent = self.agents.get(agent_id) or self.disabled_agents.get(agent_id) or self._all_discovered_agents.get(agent_id)
        if not agent:
            raise KeyError(f"Agent '{agent_id}' not found.")

        allowed_fields = {
            "name",
            "icon",
            "order",
            "is_default",
            "enabled",
            "provider",
            "model",
            "system_prompt",
            "prompt",
            "custom_panel_path",
            "custom_css",
            "settings",
        }
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        # Apply to live agent
        agent.update_config(filtered_updates)

        if "enabled" in filtered_updates:
            is_enabled = bool(filtered_updates["enabled"])
            agent.enabled = is_enabled
            if is_enabled:
                self.agents[agent_id] = agent
                self.disabled_agents.pop(agent_id, None)
            else:
                self.disabled_agents[agent_id] = agent
                self.agents.pop(agent_id, None)

        # Handle is_default tab override
        if filtered_updates.get("is_default"):
            for other_id, other_agent in self._all_discovered_agents.items():
                if other_id != agent_id:
                    other_agent._override_default = False

        # Save to persistent storage
        overrides = self.load_overrides()
        existing = overrides.get(agent_id, {})
        existing.update(filtered_updates)
        overrides[agent_id] = existing
        self.save_overrides(overrides)

        return agent.get_ui_manifest()

    update_agent = customize_agent

    def reset_agent(self, agent_id: str) -> Dict[str, Any]:
        """Resets an agent's configuration back to built-in defaults."""
        agent = self.agents.get(agent_id) or self.disabled_agents.get(agent_id) or self._all_discovered_agents.get(agent_id)
        if not agent:
            raise KeyError(f"Agent '{agent_id}' not found.")

        overrides = self.load_overrides()
        if agent_id in overrides:
            del overrides[agent_id]
            self.save_overrides(overrides)

        yaml_cfg = self.config.get("agents", {}).get(agent_id, {})
        agent.config = dict(yaml_cfg)
        agent.enabled = bool(agent.config.get("enabled", True))
        if agent.enabled:
            self.agents[agent_id] = agent
            self.disabled_agents.pop(agent_id, None)
        else:
            self.disabled_agents[agent_id] = agent
            self.agents.pop(agent_id, None)
        agent.on_config_updated()
        return agent.get_ui_manifest()

    update_agent = customize_agent

    def create_custom_agent(
        self,
        agent_id: str,
        name: str,
        icon: str = "✨",
        permissions: Optional[List[str]] = None,
        description: str = "",
        initial_order: int = 80,
        ui_blocks: Optional[List[str]] = None,
        routine_task: str = "run_check",
        schedule_display: str = "Daily at 09:00",
        category: str = "Productivity",
        archetype: str = "tracker",
        intelligence_mode: str = "hybrid",
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        checklist_items: Optional[List[Any]] = None,
        event_triggers: Optional[List[str]] = None,
        outbound_actions: Optional[List[str]] = None,
        auto_ingest_inbox: bool = False,
        default_recurrence: str = "none",
        schedule_cadence: str = "daily_morning",
        schedule: Optional[Dict[str, Any]] = None,
        settings_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Scaffolds a new functional, SQLite-backed user custom agent in custom_agents_dir
        and loads it into the live registry immediately.
        """
        from fleet.core.agent_studio import (
            generate_custom_agent_code,
            render_declarative_ui_blocks,
        )

        clean_id = re.sub(r"[^a-zA-Z0-9_]", "", agent_id.lower()).strip()
        if not clean_id:
            raise ValueError(f"Invalid agent ID '{agent_id}'. Must contain alphanumeric characters.")

        if clean_id in self.agents:
            raise ValueError(f"Agent with ID '{clean_id}' already exists.")

        agent_folder = self.custom_agents_dir / clean_id
        ui_folder = agent_folder / "ui"
        ui_folder.mkdir(parents=True, exist_ok=True)

        active_perms = list(permissions) if permissions else ["db:read", "db:write", "ui:render"]
        active_blocks = list(ui_blocks) if ui_blocks else ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"]
        active_desc = description or f"User custom agent: {name}"
        active_schedule = dict(schedule) if isinstance(schedule, dict) and schedule else {
            "type": "time",
            "value": "09:00",
            "time": "09:00",
            "display": schedule_display,
        }
        if not active_schedule.get("display"):
            active_schedule["display"] = schedule_display

        # 1. manifest.json
        manifest: Dict[str, Any] = {
            "id": clean_id,
            "name": name,
            "version": "2.0.0",
            "icon": icon,
            "category": category or "Productivity",
            "archetype": archetype or "tracker",
            "intelligence_mode": intelligence_mode or "hybrid",
            "description": active_desc,
            "permissions": active_perms,
            "ui_blocks": active_blocks,
            "routine_task": routine_task,
            "schedule_cadence": schedule_cadence,
            "schedule": active_schedule,
        }
        if model:
            manifest["model"] = str(model)
        if system_prompt:
            manifest["system_prompt"] = str(system_prompt)
        if fields:
            manifest["fields"] = fields
        if checklist_items:
            manifest["checklist_items"] = checklist_items
        if event_triggers:
            manifest["event_triggers"] = [str(t) for t in event_triggers if t]
        if outbound_actions:
            manifest["outbound_actions"] = [str(a) for a in outbound_actions if a]
        if auto_ingest_inbox:
            manifest["auto_ingest_inbox"] = True
            try:
                from fleet.core.studio_phase6 import get_agent_inbox_dir
                get_agent_inbox_dir(clean_id)
            except Exception:
                pass
        if default_recurrence and str(default_recurrence).strip().lower() != "none":
            manifest["default_recurrence"] = str(default_recurrence).strip().lower()
        (agent_folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 2. agent.py (Functional Studio runtime)
        agent_code = generate_custom_agent_code(
            agent_id=clean_id,
            name=name,
            icon=icon,
            description=active_desc,
            routine_task=routine_task,
            initial_order=initial_order,
            archetype=archetype or "tracker",
            intelligence_mode=intelligence_mode or "hybrid",
            settings_schema=settings_schema,
        )
        (agent_folder / "agent.py").write_text(agent_code, encoding="utf-8")

        # 3. ui/panel.html (Declarative UI blocks wired to CustomAgentRuntime)
        panel_html = render_declarative_ui_blocks(
            agent_id=clean_id,
            name=name,
            icon=icon,
            description=active_desc,
            permissions=active_perms,
            ui_blocks=active_blocks,
            routine_task=routine_task,
            schedule_display=str(active_schedule.get("display") or schedule_display),
            fields=fields,
            checklist_items=checklist_items,
            intelligence_mode=intelligence_mode or "hybrid",
        )
        (ui_folder / "panel.html").write_text(panel_html, encoding="utf-8")

        # 4. ui/style.css
        (ui_folder / "style.css").write_text(f"/* Custom styles for {clean_id} */\n", encoding="utf-8")

        # Load newly created agent immediately
        init_cfg: Dict[str, Any] = {"enabled": True}
        if model:
            init_cfg["model"] = str(model)
        if system_prompt:
            init_cfg["system_prompt"] = str(system_prompt)
        agent_instance = self._load_agent_from_file(
            file_path=agent_folder / "agent.py",
            agent_dir=agent_folder,
            agent_cfg=init_cfg,
            module_prefix="fleet.custom_agents",
        )
        if agent_instance:
            self.agents[clean_id] = agent_instance
            self._all_discovered_agents[clean_id] = agent_instance
            return agent_instance.get_ui_manifest()

        raise RuntimeError(f"Failed to load newly created agent '{clean_id}'")

    def evolve_custom_agent(self, agent_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 2 In-Place Agent Evolution:
        Updates a custom agent's manifest, typed domain fields, declarative UI blocks,
        intelligence mode, and Python runtime in-place while preserving 100% of existing SQLite records.
        """
        from fleet.core.agent_studio import (
            generate_custom_agent_code,
            render_declarative_ui_blocks,
            synthesize_agent_from_prompt,
        )
        from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", (agent_id or "").strip())
        if not clean_id:
            raise ValueError("Invalid agent ID.")

        agent = self.get_agent(clean_id)
        if not agent:
            raise KeyError(f"Agent '{clean_id}' not found.")

        agent_dir_resolved = agent.agent_dir.resolve()
        custom_root_resolved = self.custom_agents_dir.resolve()
        if custom_root_resolved not in agent_dir_resolved.parents:
            raise ValueError(
                f"Agent '{clean_id}' is a built-in core agent and cannot be rewritten via Studio Evolution. "
                "Use Settings -> Agents to customize its prompt, model, or settings."
            )

        manifest_path = agent.agent_dir / "manifest.json"
        existing_meta: Dict[str, Any] = {}
        if manifest_path.is_file():
            try:
                existing_meta = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                existing_meta = {}

        # Optional natural-language evolution prompt synthesis
        evo_prompt = str(updates.get("evolution_prompt") or updates.get("nl_prompt") or "").strip()
        synth_overlay: Dict[str, Any] = {}
        if evo_prompt:
            synth_overlay = synthesize_agent_from_prompt(evo_prompt, custom_id=clean_id)

        def _pick(key: str, default: Any = None) -> Any:
            if key in updates and updates[key] is not None and updates[key] != "":
                return updates[key]
            if key in synth_overlay and synth_overlay[key] is not None:
                return synth_overlay[key]
            if key in existing_meta and existing_meta[key] is not None:
                return existing_meta[key]
            return default

        name = str(_pick("name", agent.display_name)).strip() or agent.display_name
        icon = str(_pick("icon", agent.display_icon)).strip() or agent.display_icon
        category = str(_pick("category", "Productivity")).strip() or "Productivity"
        description = str(_pick("description", evo_prompt or existing_meta.get("description") or name)).strip()
        archetype = str(_pick("archetype", "tracker")).strip() or "tracker"
        intelligence_mode = str(_pick("intelligence_mode", "hybrid")).strip() or "hybrid"
        model = _pick("model", agent.preferred_model)
        system_prompt = _pick("system_prompt", agent.system_prompt)
        routine_task = str(_pick("routine_task", "run_check")).strip() or "run_check"
        schedule_cadence = str(_pick("schedule_cadence", "daily_morning")).strip() or "daily_morning"
        schedule_obj = _pick("schedule", {"type": "time", "value": "09:00", "display": "Daily at 09:00"})
        if not isinstance(schedule_obj, dict):
            schedule_obj = {"type": "time", "value": "09:00", "display": "Daily at 09:00"}
        schedule_display = str(schedule_obj.get("display") or "Daily at 09:00")

        perm_aliases = {
            "network:http": "network:outbound",
            "notifications:send": "event_bus:publish",
            "system:exec": "system:diagnostics",
            "storage:data_read": "db:read",
            "storage:data_write": "db:write",
        }
        raw_perms = _pick("permissions", existing_meta.get("permissions") or ["db:read", "db:write", "ui:render"])
        perms = [perm_aliases.get(str(p), str(p)) for p in (raw_perms or []) if p]
        perms = [p for p in perms if p in ALLOWED_AGENT_PERMISSIONS]
        for core_p in ("db:read", "db:write", "ui:render"):
            if core_p not in perms:
                perms.insert(0, core_p)

        ui_blocks = _pick("ui_blocks", ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"])
        fields = _pick("fields", None)
        checklist_items = _pick("checklist_items", None)
        event_triggers = updates.get("event_triggers") if "event_triggers" in updates else _pick("event_triggers", None)
        outbound_actions = updates.get("outbound_actions") if "outbound_actions" in updates else _pick("outbound_actions", None)
        auto_ingest_inbox = bool(updates.get("auto_ingest_inbox") if "auto_ingest_inbox" in updates else _pick("auto_ingest_inbox", False))
        default_recurrence = str(updates.get("default_recurrence") if "default_recurrence" in updates else _pick("default_recurrence", "none") or "none").strip().lower()
        order_val = int(updates.get("order", agent.display_order or 75))

        new_manifest: Dict[str, Any] = {
            "id": clean_id,
            "name": name,
            "version": "2.0.0",
            "icon": icon,
            "category": category,
            "archetype": archetype,
            "intelligence_mode": intelligence_mode,
            "description": description,
            "permissions": perms,
            "ui_blocks": ui_blocks,
            "routine_task": routine_task,
            "schedule_cadence": schedule_cadence,
            "schedule": schedule_obj,
        }
        if model:
            new_manifest["model"] = str(model)
        if system_prompt:
            new_manifest["system_prompt"] = str(system_prompt)
        if fields:
            new_manifest["fields"] = fields
        if checklist_items:
            new_manifest["checklist_items"] = checklist_items
        if event_triggers:
            new_manifest["event_triggers"] = [str(t) for t in event_triggers if t]
        if outbound_actions:
            new_manifest["outbound_actions"] = [str(a) for a in outbound_actions if a]
        if auto_ingest_inbox:
            new_manifest["auto_ingest_inbox"] = True
            try:
                from fleet.core.studio_phase6 import get_agent_inbox_dir
                get_agent_inbox_dir(clean_id)
            except Exception:
                pass
        if default_recurrence and default_recurrence != "none":
            new_manifest["default_recurrence"] = default_recurrence

        raw_prev_evo = existing_meta.get("evolution_improvements")
        prev_evo_list: List[Any] = raw_prev_evo if isinstance(raw_prev_evo, list) else []
        raw_new_evo = updates.get("evolution_improvements") if "evolution_improvements" in updates else None
        merged_evo: List[Dict[str, Any]] = []
        seen_evo_titles: set[str] = set()
        for src_list in (prev_evo_list, raw_new_evo if isinstance(raw_new_evo, list) else []):
            for item in src_list:
                if isinstance(item, dict):
                    e_title = str(item.get("title") or "").strip()
                    if not e_title or e_title.lower() in seen_evo_titles:
                        continue
                    seen_evo_titles.add(e_title.lower())
                    merged_evo.append({
                        "id": str(item.get("id") or ""),
                        "title": e_title[:90],
                        "description": str(item.get("description") or "")[:280],
                        "code_enhancement_brief": str(item.get("code_enhancement_brief") or "")[:360],
                        "is_custom": bool(item.get("is_custom", False)),
                    })
                elif isinstance(item, str) and item.strip():
                    e_title = item.strip()
                    if e_title.lower() not in seen_evo_titles:
                        seen_evo_titles.add(e_title.lower())
                        merged_evo.append({"id": "", "title": e_title[:90], "description": "", "code_enhancement_brief": "", "is_custom": False})
        if merged_evo:
            new_manifest["evolution_improvements"] = merged_evo[-30:]

        # Phase 4: Snapshot current blueprint revision before overwriting files on disk
        self._save_agent_revision_snapshot(agent.agent_dir, reason="evolve")

        manifest_path.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")

        agent_code = generate_custom_agent_code(
            agent_id=clean_id,
            name=name,
            icon=icon,
            description=description,
            routine_task=routine_task,
            initial_order=order_val,
            archetype=archetype,
            intelligence_mode=intelligence_mode,
        )
        (agent.agent_dir / "agent.py").write_text(agent_code, encoding="utf-8")

        ui_folder = agent.agent_dir / "ui"
        ui_folder.mkdir(parents=True, exist_ok=True)
        panel_html = render_declarative_ui_blocks(
            agent_id=clean_id,
            name=name,
            icon=icon,
            description=description,
            permissions=perms,
            ui_blocks=ui_blocks,
            routine_task=routine_task,
            schedule_display=schedule_display,
            fields=fields,
            checklist_items=checklist_items,
            intelligence_mode=intelligence_mode,
        )
        (ui_folder / "panel.html").write_text(panel_html, encoding="utf-8")

        # Sync overrides & hot-reload live agent instance
        merged_cfg = dict(agent.config)
        merged_cfg["name"] = name
        merged_cfg["icon"] = icon
        merged_cfg["order"] = order_val
        if model is not None:
            merged_cfg["model"] = str(model) if model else ""
        if system_prompt is not None:
            merged_cfg["system_prompt"] = str(system_prompt)
        if isinstance(updates.get("settings"), dict):
            cur_settings = dict(merged_cfg.get("settings") or {})
            cur_settings.update(updates["settings"])
            merged_cfg["settings"] = cur_settings

        overrides = self.load_overrides()
        overrides[clean_id] = {
            k: v for k, v in merged_cfg.items()
            if k in {"name", "icon", "order", "enabled", "provider", "model", "system_prompt", "settings"}
        }
        self.save_overrides(overrides)

        reloaded = self._load_agent_from_file(
            file_path=agent.agent_dir / "agent.py",
            agent_dir=agent.agent_dir,
            agent_cfg=merged_cfg,
            module_prefix="fleet.custom_agents",
        )
        if not reloaded:
            raise RuntimeError(f"Failed to hot-reload evolved agent '{clean_id}'")

        if reloaded.enabled:
            self.agents[clean_id] = reloaded
            self.disabled_agents.pop(clean_id, None)
        else:
            self.disabled_agents[clean_id] = reloaded
            self.agents.pop(clean_id, None)
        self._all_discovered_agents[clean_id] = reloaded
        return reloaded.get_ui_manifest()

    def _save_agent_revision_snapshot(self, agent_dir: Path, reason: str = "evolve") -> Optional[str]:
        """
        Phase 4 Blueprint Revision History:
        Saves a timestamped JSON snapshot of manifest.json, agent.py, and ui/panel.html
        under <agent_dir>/revisions/ (retaining up to 10 snapshots).
        """
        try:
            manifest_path = agent_dir / "manifest.json"
            code_path = agent_dir / "agent.py"
            panel_path = agent_dir / "ui" / "panel.html"
            if not code_path.is_file():
                return None

            manifest_data: Dict[str, Any] = {}
            if manifest_path.is_file():
                try:
                    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    manifest_data = {}

            agent_code = code_path.read_text(encoding="utf-8")
            panel_html = panel_path.read_text(encoding="utf-8") if panel_path.is_file() else ""

            rev_dir = agent_dir / "revisions"
            rev_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            rev_id = now.strftime("rev_%Y%m%d_%H%M%S_%f")
            blocks = manifest_data.get("ui_blocks") or []
            fields = manifest_data.get("fields") or []
            raw_sched = manifest_data.get("schedule")
            sched: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
            summary = (
                f"{manifest_data.get('icon', '✨')} {manifest_data.get('name', agent_dir.name)} "
                f"({len(blocks)} widgets, {len(fields)} fields, {sched.get('display', 'Daily')})"
            )

            snap = {
                "revision_id": rev_id,
                "created_at": now.isoformat(),
                "reason": str(reason or "evolve"),
                "summary": summary,
                "manifest": manifest_data,
                "agent_code": agent_code,
                "panel_html": panel_html,
            }
            (rev_dir / f"{rev_id}.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")

            # Prune snapshots older than the 10 most recent
            all_snaps = sorted(rev_dir.glob("rev_*.json"), key=lambda p: p.name)
            while len(all_snaps) > 10:
                oldest = all_snaps.pop(0)
                try:
                    oldest.unlink(missing_ok=True)
                except Exception:
                    pass
            return rev_id
        except Exception as e:
            logger.warning(f"Could not save revision snapshot for '{agent_dir.name}': {e}")
            return None

    def list_custom_agent_revisions(self, agent_id: str) -> List[Dict[str, Any]]:
        """Lists saved blueprint revisions for a custom agent (newest first)."""
        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", (agent_id or "").strip())
        if not clean_id:
            raise ValueError("Invalid agent ID.")
        agent = self.get_agent(clean_id)
        if not agent:
            raise KeyError(f"Agent '{clean_id}' not found.")

        rev_dir = agent.agent_dir / "revisions"
        if not rev_dir.is_dir():
            return []

        items: List[Dict[str, Any]] = []
        for f in sorted(rev_dir.glob("rev_*.json"), key=lambda p: p.name, reverse=True):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                raw_mf = raw.get("manifest")
                mf: Dict[str, Any] = raw_mf if isinstance(raw_mf, dict) else {}
                raw_sched = mf.get("schedule")
                sched: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
                items.append({
                    "revision_id": str(raw.get("revision_id") or f.stem),
                    "created_at": str(raw.get("created_at") or ""),
                    "reason": str(raw.get("reason") or "evolve"),
                    "summary": str(raw.get("summary") or mf.get("name") or clean_id),
                    "name": str(mf.get("name") or clean_id),
                    "icon": str(mf.get("icon") or "✨"),
                    "ui_blocks": mf.get("ui_blocks") or [],
                    "fields_count": len(mf.get("fields") or []),
                    "intelligence_mode": str(mf.get("intelligence_mode") or "hybrid"),
                    "schedule_display": str(sched.get("display") or "Daily"),
                })
            except Exception:
                continue
        return items

    def rollback_custom_agent(
        self,
        agent_id: str,
        revision_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 4 1-Click Blueprint Rollback:
        Restores manifest.json, agent.py, and ui/panel.html from a saved revision snapshot
        (defaulting to the latest revision), re-verifies AST/permissions, and hot-reloads the agent
        while preserving 100% of existing SQLite records and checklists.
        """
        from fleet.core.agent_studio import dry_run_agent_spec

        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", (agent_id or "").strip())
        if not clean_id:
            raise ValueError("Invalid agent ID.")
        agent = self.get_agent(clean_id)
        if not agent:
            raise KeyError(f"Agent '{clean_id}' not found.")

        agent_dir_resolved = agent.agent_dir.resolve()
        custom_root_resolved = self.custom_agents_dir.resolve()
        if custom_root_resolved not in agent_dir_resolved.parents:
            raise ValueError(f"Agent '{clean_id}' is a built-in core agent and cannot be rolled back.")

        rev_dir = agent.agent_dir / "revisions"
        if not rev_dir.is_dir():
            raise ValueError(f"No saved blueprint revisions exist for '{clean_id}'.")

        if revision_id:
            clean_rev = re.sub(r"[^a-zA-Z0-9_-]", "", str(revision_id).strip())
            target_file = (rev_dir / f"{clean_rev}.json").resolve()
            if not target_file.is_file() or rev_dir.resolve() not in target_file.parents:
                raise KeyError(f"Revision '{clean_rev}' not found for agent '{clean_id}'.")
        else:
            snaps = sorted(rev_dir.glob("rev_*.json"), key=lambda p: p.name, reverse=True)
            if not snaps:
                raise ValueError(f"No saved blueprint revisions exist for '{clean_id}'.")
            target_file = snaps[0]

        snap_data = json.loads(target_file.read_text(encoding="utf-8"))
        restored_manifest = snap_data.get("manifest") if isinstance(snap_data.get("manifest"), dict) else {}
        restored_code = str(snap_data.get("agent_code") or "")
        restored_panel = str(snap_data.get("panel_html") or "")
        if not restored_code.strip():
            raise ValueError("Selected revision snapshot has empty agent code.")

        restored_manifest["id"] = clean_id
        audit = dry_run_agent_spec({
            "id": clean_id,
            "name": restored_manifest.get("name", clean_id),
            "permissions": restored_manifest.get("permissions", ["db:read", "db:write", "ui:render"]),
            "agent_py": restored_code,
        })
        if audit.get("status") != "ok":
            raise ValueError(f"Revision failed AST/sandbox verification: {audit.get('message')}")

        (agent.agent_dir / "manifest.json").write_text(json.dumps(restored_manifest, indent=2), encoding="utf-8")
        (agent.agent_dir / "agent.py").write_text(restored_code, encoding="utf-8")
        ui_folder = agent.agent_dir / "ui"
        ui_folder.mkdir(parents=True, exist_ok=True)
        (ui_folder / "panel.html").write_text(restored_panel, encoding="utf-8")

        merged_cfg = dict(agent.config)
        if restored_manifest.get("name"):
            merged_cfg["name"] = str(restored_manifest["name"])
        if restored_manifest.get("icon"):
            merged_cfg["icon"] = str(restored_manifest["icon"])
        merged_cfg["model"] = str(restored_manifest.get("model") or "")
        merged_cfg["system_prompt"] = str(restored_manifest.get("system_prompt") or "")

        overrides = self.load_overrides()
        overrides[clean_id] = {
            k: v for k, v in merged_cfg.items()
            if k in {"name", "icon", "order", "enabled", "provider", "model", "system_prompt", "settings"}
        }
        self.save_overrides(overrides)

        reloaded = self._load_agent_from_file(
            file_path=agent.agent_dir / "agent.py",
            agent_dir=agent.agent_dir,
            agent_cfg=merged_cfg,
            module_prefix="fleet.custom_agents",
        )
        if not reloaded:
            raise RuntimeError(f"Failed to hot-reload rolled-back agent '{clean_id}'.")

        if reloaded.enabled:
            self.agents[clean_id] = reloaded
            self.disabled_agents.pop(clean_id, None)
        else:
            self.disabled_agents[clean_id] = reloaded
            self.agents.pop(clean_id, None)
        self._all_discovered_agents[clean_id] = reloaded

        out_manifest = reloaded.get_ui_manifest()
        out_manifest["restored_revision_id"] = str(snap_data.get("revision_id") or target_file.stem)
        return out_manifest

    def clone_custom_agent(
        self,
        source_agent_id: str,
        target_agent_id: Optional[str] = None,
        new_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phase 3 1-Click Blueprint Cloning:
        Duplicates an existing agent's Studio blueprint (manifest, typed fields, UI blocks,
        intelligence mode, system prompt, schedule, and event triggers) into a fresh custom agent
        without copying private SQLite records.
        """
        from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

        src_id = re.sub(r"[^a-zA-Z0-9_-]", "", (source_agent_id or "").strip())
        source_agent = self.get_agent(src_id)
        if not source_agent:
            raise KeyError(f"Source agent '{src_id}' not found.")

        src_ui = source_agent.get_ui_manifest()
        base_slug = re.sub(r"[^a-z0-9_]", "_", (target_agent_id or f"{src_id}_copy").lower()).strip("_") or "agent_copy"
        candidate_id = base_slug
        suffix = 2
        while candidate_id in self.agents or candidate_id in self._all_discovered_agents:
            candidate_id = f"{base_slug}_{suffix}"
            suffix += 1

        clone_name = (new_name or "").strip() or f"{src_ui.get('name', src_id)} (Copy)"
        raw_perms = [p for p in (src_ui.get("permissions") or []) if p in ALLOWED_AGENT_PERMISSIONS]
        for core_p in ("db:read", "db:write", "ui:render"):
            if core_p not in raw_perms:
                raw_perms.insert(0, core_p)

        raw_sched = src_ui.get("schedule")
        sched: Dict[str, Any] = raw_sched if isinstance(raw_sched, dict) else {}
        sched_display = str(sched.get("display") or "Daily at 09:00")

        return self.create_custom_agent(
            agent_id=candidate_id,
            name=clone_name,
            icon=str(src_ui.get("icon") or "✨"),
            permissions=raw_perms,
            description=str(src_ui.get("description") or f"Cloned from {src_id}"),
            initial_order=int(src_ui.get("order") or 78),
            ui_blocks=src_ui.get("ui_blocks") or ["alert_banner", "kpi_row", "quick_capture_bar", "history_table"],
            routine_task=str(src_ui.get("routine_task") or "run_check"),
            schedule_display=sched_display,
            category=str(src_ui.get("category") or "Productivity"),
            archetype=str(src_ui.get("archetype") or "tracker"),
            intelligence_mode=str(src_ui.get("intelligence_mode") or "hybrid"),
            model=src_ui.get("model") or None,
            system_prompt=src_ui.get("system_prompt") or None,
            fields=src_ui.get("fields") or None,
            checklist_items=src_ui.get("checklist_items") or None,
            event_triggers=src_ui.get("event_triggers") or None,
            schedule_cadence=str(src_ui.get("schedule_cadence") or "daily_morning"),
            schedule=sched or None,
        )

    def delete_custom_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Permanently deletes a user-created or catalog-installed custom agent from
        custom_agents_dir and unregisters it from the active runtime registry.
        Built-in core agents under fleet/agents/ are protected from disk deletion.
        """
        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", (agent_id or "").strip())
        if not clean_id:
            raise ValueError("Invalid agent ID.")

        agent = self.get_agent(clean_id)
        if not agent:
            raise KeyError(f"Agent '{clean_id}' not found.")

        agent_dir_resolved = agent.agent_dir.resolve()
        custom_root_resolved = self.custom_agents_dir.resolve()
        if custom_root_resolved not in agent_dir_resolved.parents:
            raise ValueError(
                f"Agent '{clean_id}' is a built-in core agent and cannot be permanently deleted. "
                "Toggle it off in Settings -> Agents to deactivate it."
            )

        display_name = agent.display_name
        try:
            agent.on_shutdown()
        except Exception as e:
            logger.warning(f"Error during shutdown of deleted agent '{clean_id}': {e}")

        self.agents.pop(clean_id, None)
        self.disabled_agents.pop(clean_id, None)
        self._all_discovered_agents.pop(clean_id, None)
        sys.modules.pop(f"fleet.custom_agents.{clean_id}.agent", None)

        overrides = self.load_overrides()
        if clean_id in overrides:
            overrides.pop(clean_id, None)
            self.save_overrides(overrides)

        if self.db is not None and hasattr(self.db, "clear_custom_agent_data"):
            try:
                self.db.clear_custom_agent_data(clean_id)
            except Exception as e:
                logger.warning(f"Error clearing custom SQLite data for '{clean_id}': {e}")

        if agent_dir_resolved.is_dir():
            shutil.rmtree(agent_dir_resolved, ignore_errors=True)

        # Clean up any Deep-Build local unit test for this deleted user-vault custom agent
        try:
            from fleet.config import BASE_DIR, DATA_DIR
            if custom_root_resolved == (DATA_DIR / "user" / "custom_agents").resolve():
                orphan_test = BASE_DIR.parent / "tests" / f"test_custom_{clean_id}.py"
                if orphan_test.is_file():
                    orphan_test.unlink(missing_ok=True)
        except Exception:
            pass

        return {"id": clean_id, "name": display_name, "deleted": True}

    def register_all_routes(self, router) -> None:
        """Registers API routes for all loaded agents and registry management."""
        for agent in self._all_discovered_agents.values() if self._all_discovered_agents else self.agents.values():
            try:
                agent.register_routes(router)
            except Exception as e:
                logger.error(f"Failed to register routes for agent '{agent.id}': {e}")

        # Core registry endpoints
        @router.get("/api/fleet/agents")
        def get_agents_manifest(handler: Any, parsed_url: urllib.parse.ParseResult):
            query = urllib.parse.parse_qs(parsed_url.query)
            include_all = query.get("all", ["false"])[0].lower() in ("true", "1")
            manifests = self.get_manifests(include_disabled=include_all)
            handler._send_json({"status": "ok", "count": len(manifests), "agents": manifests})

        # Ensure this registry instance owns the /api/fleet/agents/ prefix dispatchers on router
        if hasattr(router, "get_prefix_routes"):
            router.get_prefix_routes = [
                (p, fn) for p, fn in router.get_prefix_routes if p != "/api/fleet/agents/"
            ]
        if hasattr(router, "post_prefix_routes"):
            router.post_prefix_routes = [
                (p, fn) for p, fn in router.post_prefix_routes if p != "/api/fleet/agents/"
            ]

        @router.get_prefix("/api/fleet/agents/")
        def dispatch_agent_get(handler: Any, path: str, parsed_url: urllib.parse.ParseResult):
            parts = [p for p in path.split("/") if p]
            if len(parts) < 4:
                handler.send_error(400, "Invalid agent path")
                return

            agent_id = parts[3]
            subpath = parts[4] if len(parts) > 4 else ""

            if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
                handler.send_error(400, "Invalid agent identifier")
                return

            agent = self.get_agent(agent_id)
            if not agent:
                handler.send_error(404, f"Agent '{agent_id}' not found")
                return

            if subpath == "state":
                manifest = agent.get_ui_manifest()
                active_db = self._resolve_db()
                if active_db is not None and hasattr(active_db, "get_custom_agent_dashboard_state"):
                    state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                else:
                    state = {
                        "agent_id": agent.id,
                        "kpis": {"total_entries": 0, "total_runs": 0, "due_soon": 0, "warnings": 0, "numeric_sum": 0.0, "last_status": "ready"},
                        "entries": [],
                        "runs": [],
                        "countdowns": [],
                        "latest_insight": None,
                        "checklist": [],
                        "checklist_done": 0,
                        "checklist_total": 0,
                        "checklist_streak": 0,
                    }
                handler._send_json({"status": "ok", "agent_id": agent.id, "manifest": manifest, "state": state})
                return

            if subpath == "config":
                handler._send_json({
                    "status": "ok",
                    "id": agent.id,
                    "manifest": agent.get_ui_manifest(),
                    "config": agent.config,
                    "permissions": getattr(agent, "permissions", []),
                    "preferred_provider": agent.preferred_provider,
                    "preferred_model": agent.preferred_model,
                    "system_prompt": agent.system_prompt,
                })
                return

            if subpath == "style.css":
                css_file = (agent.agent_dir / "ui" / "style.css").resolve()
                if not css_file.is_file() or not str(css_file).startswith(str(agent.agent_dir.resolve())):
                    handler.send_error(404, "Style not found")
                    return
                css_bytes = css_file.read_bytes()
                handler.send_response(200)
                handler.send_header("Content-Type", "text/css; charset=utf-8")
                handler.send_header("X-Content-Type-Options", "nosniff")
                handler.send_header("Content-Length", str(len(css_bytes)))
                handler.end_headers()
                handler.wfile.write(css_bytes)
                return

            if subpath == "script.js":
                js_file = (agent.agent_dir / "ui" / "script.js").resolve()
                if not js_file.is_file() or not str(js_file).startswith(str(agent.agent_dir.resolve())):
                    handler.send_error(404, "Script not found")
                    return
                js_bytes = js_file.read_bytes()
                handler.send_response(200)
                handler.send_header("Content-Type", "application/javascript; charset=utf-8")
                handler.send_header("X-Content-Type-Options", "nosniff")
                handler.send_header("Content-Length", str(len(js_bytes)))
                handler.end_headers()
                handler.wfile.write(js_bytes)
                return

            if subpath in ("export.csv", "records.csv"):
                active_db = self._resolve_db()
                rows = (
                    active_db.list_custom_agent_records(agent.id, limit=500)
                    if active_db is not None and hasattr(active_db, "list_custom_agent_records")
                    else []
                )
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["id", "record_type", "title", "status", "due_date", "numeric_value", "created_at", "extra_fields"])

                def _safe_csv_cell(val: Any) -> str:
                    s = str(val if val is not None else "")
                    if s and s[0] in ("=", "+", "@", "\t", "\r"):
                        return "'" + s
                    return s

                for r in rows:
                    extra_str = json.dumps(r.get("data") or {}, ensure_ascii=False) if r.get("data") else ""
                    writer.writerow([
                        r.get("id", ""),
                        _safe_csv_cell(r.get("record_type", "entry")),
                        _safe_csv_cell(r.get("title", "")),
                        _safe_csv_cell(r.get("status", "ok")),
                        _safe_csv_cell(r.get("due_date", "")),
                        r.get("numeric_value", 0.0),
                        _safe_csv_cell(r.get("created_at", "")),
                        _safe_csv_cell(extra_str),
                    ])
                csv_bytes = buf.getvalue().encode("utf-8")
                handler.send_response(200)
                handler.send_header("Content-Type", "text/csv; charset=utf-8")
                handler.send_header("Content-Disposition", f'attachment; filename="{agent.id}_records.csv"')
                handler.send_header("X-Content-Type-Options", "nosniff")
                handler.send_header("Content-Length", str(len(csv_bytes)))
                handler.end_headers()
                handler.wfile.write(csv_bytes)
                return

            handler.send_error(404, "Unknown agent resource")

        @router.post_prefix("/api/fleet/agents/")
        def dispatch_agent_post(handler: Any, path: str, body: Dict[str, Any]):
            parts = [p for p in path.split("/") if p]
            # Pattern 1: /api/fleet/agents/custom/create
            if len(parts) >= 5 and parts[3] == "custom" and parts[4] == "create":
                try:
                    res = self.create_custom_agent(
                        agent_id=body.get("id", ""),
                        name=body.get("name", ""),
                        icon=body.get("icon", "✨"),
                        permissions=body.get("permissions"),
                        description=body.get("description", ""),
                        initial_order=int(body.get("order", 80)),
                    )
                    handler._send_json({"status": "success", "agent": res})
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=400)
                return

            # Pattern 2: /api/fleet/agents/<agent_id>/config
            if len(parts) >= 5 and parts[4] == "config":
                agent_id = parts[3]
                try:
                    res = self.customize_agent(agent_id, body)
                    handler._send_json({"status": "success", "agent": res})
                except KeyError:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=400)
                return

            # Pattern 3: /api/fleet/agents/<agent_id>/reset
            if len(parts) >= 5 and parts[4] == "reset":
                agent_id = parts[3]
                try:
                    res = self.reset_agent(agent_id)
                    handler._send_json({"status": "success", "agent": res})
                except KeyError:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=400)
                return

            # Pattern 4: /api/fleet/agents/<agent_id>/records and /records/delete
            if len(parts) >= 5 and parts[4] == "records":
                agent_id = parts[3]
                agent = self.get_agent(agent_id)
                if not agent:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                    return
                active_db = self._resolve_db()
                if active_db is None:
                    handler._send_json({"status": "error", "message": "Database unavailable"}, status=503)
                    return

                # /api/fleet/agents/<agent_id>/records/delete
                if len(parts) >= 6 and parts[5] == "delete":
                    try:
                        rec_id = int(body.get("record_id") or body.get("id") or 0)
                        deleted = active_db.delete_custom_agent_record(agent.id, rec_id)
                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest())
                        handler._send_json({"status": "success", "deleted": deleted, "state": state})
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=400)
                    return

                # /api/fleet/agents/<agent_id>/records/update (Phase 4 inline edit & Kanban stage move)
                if len(parts) >= 6 and parts[5] == "update":
                    try:
                        rec_id = int(body.get("record_id") or body.get("id") or 0)
                        if rec_id <= 0:
                            handler._send_json({"status": "error", "message": "Valid 'record_id' is required."}, status=400)
                            return
                        title_val = body.get("title") if "title" in body else None
                        due_val = body.get("due_date") if "due_date" in body else None
                        status_val = body.get("status") if "status" in body else None
                        num_val: Optional[float] = None
                        if "numeric_value" in body and body.get("numeric_value") not in (None, ""):
                            num_val = float(body["numeric_value"])
                        elif "numeric_value" in body and body.get("numeric_value") == "":
                            num_val = 0.0
                        extra_val = body.get("data") if isinstance(body.get("data"), dict) else None
                        updated = active_db.update_custom_agent_record(
                            agent_id=agent.id,
                            record_id=rec_id,
                            title=title_val,
                            due_date=due_val,
                            numeric_value=num_val,
                            status=status_val,
                            data=extra_val,
                        )
                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest())
                        handler._send_json({"status": "success", "updated": updated, "state": state})
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=400)
                    return

                # /api/fleet/agents/<agent_id>/records/renew (Phase 6: 1-Click Smart Renewal Roll-Forward)
                if len(parts) >= 6 and parts[5] == "renew":
                    try:
                        from fleet.core.studio_phase6 import roll_forward_custom_agent_record
                        rec_id = int(body.get("record_id") or body.get("id") or 0)
                        if rec_id <= 0:
                            handler._send_json({"status": "error", "message": "Valid 'record_id' is required"}, status=400)
                            return
                        new_num: Optional[float] = None
                        if body.get("numeric_value") not in (None, ""):
                            new_num = float(body["numeric_value"])
                        manifest = agent.get_ui_manifest()
                        rolled = roll_forward_custom_agent_record(
                            db=active_db,
                            agent_id=agent.id,
                            record_id=rec_id,
                            cycle=str(body.get("cycle") or ""),
                            next_due_date=str(body.get("next_due_date") or ""),
                            new_numeric_value=new_num,
                            default_recurrence=str(manifest.get("default_recurrence") or "none"),
                        )
                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                        handler._send_json({"status": "success", "renewed": rolled, "state": state})
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=400)
                    return

                # /api/fleet/agents/<agent_id>/records (create entry)
                try:
                    fields_sub = body.get("fields")
                    raw_fields: Dict[str, Any] = fields_sub if isinstance(fields_sub, dict) else body
                    manifest_fields = agent.get_ui_manifest().get("fields") or []
                    date_keys = [
                        f["key"] for f in manifest_fields
                        if isinstance(f, dict) and f.get("type") == "date" and f.get("key")
                    ]
                    num_keys = [
                        f["key"] for f in manifest_fields
                        if isinstance(f, dict) and f.get("type") == "number" and f.get("key")
                    ]
                    text_keys = [
                        f["key"] for f in manifest_fields
                        if isinstance(f, dict) and f.get("type") in ("text", "url") and f.get("key")
                    ]
                    url_keys = [
                        f["key"] for f in manifest_fields
                        if isinstance(f, dict) and f.get("type") == "url" and f.get("key")
                    ]

                    title_candidates = [
                        raw_fields.get("title"),
                        raw_fields.get("item_name"),
                        raw_fields.get("name"),
                        raw_fields.get("target_url"),
                        *[
                            v for k, v in raw_fields.items()
                            if any(tok in str(k).lower() for tok in ("_name", "title", "subject", "habit", "policy_name"))
                        ],
                        *[raw_fields.get(k) for k in text_keys],
                    ]
                    title = next(
                        (str(v).strip() for v in title_candidates if v not in (None, "") and str(v).strip()),
                        "",
                    )
                    if not title:
                        handler._send_json({"status": "error", "message": "Please enter an item title or value."}, status=400)
                        return

                    date_candidates = [
                        raw_fields.get("due_date"),
                        *[raw_fields.get(k) for k in date_keys],
                        *[
                            v for k, v in raw_fields.items()
                            if any(tok in str(k).lower() for tok in ("date", "expiry", "due", "deadline"))
                        ],
                    ]
                    due_date = next(
                        (str(v).strip() for v in date_candidates if v not in (None, "") and str(v).strip()),
                        "",
                    )

                    num_candidates = [
                        raw_fields.get("numeric_value"),
                        *[raw_fields.get(k) for k in num_keys],
                        *[
                            v for k, v in raw_fields.items()
                            if any(tok in str(k).lower() for tok in ("amount", "price", "cost", "premium", "value", "score"))
                        ],
                    ]
                    num_raw = next((v for v in num_candidates if v not in (None, "")), None)
                    try:
                        numeric_val = float(num_raw) if num_raw not in (None, "") else 0.0
                    except (TypeError, ValueError):
                        numeric_val = 0.0

                    consumed_keys = {"title", "due_date", "numeric_value", "record_type", "status"}
                    if text_keys and str(raw_fields.get(text_keys[0], "")).strip() == title:
                        consumed_keys.add(text_keys[0])
                    if date_keys and str(raw_fields.get(date_keys[0], "")).strip() == due_date:
                        consumed_keys.add(date_keys[0])
                    if num_keys and raw_fields.get(num_keys[0]) == num_raw:
                        consumed_keys.add(num_keys[0])

                    extra_data = {
                        k: v for k, v in raw_fields.items()
                        if k not in consumed_keys
                        and v not in (None, "")
                    }
                    for uk in url_keys:
                        uval = str(raw_fields.get(uk) or "").strip()
                        if uval and "target_url" not in extra_data:
                            extra_data["target_url"] = uval
                    default_rec = str(agent.get_ui_manifest().get("default_recurrence") or "none").strip().lower()
                    if default_rec and default_rec != "none":
                        extra_data.setdefault("recurrence", default_rec)
                    rec_id = active_db.add_custom_agent_record(
                        agent_id=agent.id,
                        title=title,
                        record_type=str(body.get("record_type") or "entry"),
                        data=extra_data,
                        status=str(body.get("status") or "ok"),
                        due_date=due_date,
                        numeric_value=numeric_val,
                    )
                    state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest())
                    handler._send_json({"status": "success", "record_id": rec_id, "state": state})
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=400)
                return

            # Pattern 5: /api/fleet/agents/<agent_id>/checklist
            if len(parts) >= 5 and parts[4] == "checklist":
                agent_id = parts[3]
                agent = self.get_agent(agent_id)
                if not agent:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                    return
                active_db = self._resolve_db()
                if active_db is None:
                    handler._send_json({"status": "error", "message": "Database unavailable"}, status=503)
                    return
                try:
                    item_key = str(body.get("item_key") or body.get("key") or "").strip()
                    if not item_key:
                        handler._send_json({"status": "error", "message": "Field 'item_key' is required"}, status=400)
                        return
                    label = str(body.get("label") or "").strip()
                    checked = body.get("checked") if isinstance(body.get("checked"), bool) else None
                    updated_item = active_db.toggle_custom_agent_checklist_item(
                        agent_id=agent.id,
                        item_key=item_key,
                        label=label,
                        checked=checked,
                    )
                    state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest())
                    handler._send_json({"status": "success", "item": updated_item, "state": state})
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=400)
                return

            # Pattern 5b: /api/fleet/agents/<agent_id>/documents/extract and /documents/commit (Phase 5 + Multi-Attachment)
            if len(parts) >= 6 and parts[4] == "documents":
                agent_id = parts[3]
                sub_action = parts[5]
                agent = self.get_agent(agent_id)
                if not agent:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                    return
                active_db = self._resolve_db()
                if active_db is None:
                    handler._send_json({"status": "error", "message": "Database unavailable"}, status=503)
                    return
                if getattr(agent, "db", None) is None:
                    agent.db = active_db

                manifest = agent.get_ui_manifest()

                if sub_action == "extract":
                    try:
                        from fleet.core.document_extractor import (
                            MAX_MULTI_ATTACHMENTS,
                            extract_tracking_items_from_documents_batch,
                            load_vaulted_documents_for_agent,
                        )
                        prov = str(body.get("provider") or manifest.get("provider") or "auto").strip()
                        if manifest.get("intelligence_mode") == "deterministic" and not body.get("provider"):
                            prov = "deterministic"
                        mdl = str(body.get("model") or manifest.get("model") or "").strip() or None
                        hint_val = str(body.get("extraction_hint") or "")
                        auto_commit = bool(body.get("auto_commit", False))
                        reextract_vault = bool(body.get("reextract_vault", False))
                        target_doc_rec_id = int(body.get("doc_record_id") or 0)

                        existing_state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                        existing_doc_rows = existing_state.get("documents") if isinstance(existing_state, dict) else []
                        existing_doc_by_sha: Dict[str, int] = {}
                        existing_doc_by_id: Dict[int, Dict[str, Any]] = {}
                        for dr in (existing_doc_rows or []):
                            if not isinstance(dr, dict):
                                continue
                            dr_id = int(dr.get("id") or 0)
                            if dr_id > 0:
                                existing_doc_by_id[dr_id] = dr
                            raw_dm = dr.get("data")
                            dm: Dict[str, Any] = raw_dm if isinstance(raw_dm, dict) else {}
                            d_sha = str(dm.get("sha256") or "").strip()
                            if d_sha and dr_id > 0:
                                existing_doc_by_sha[d_sha] = dr_id

                        persist_new_to_vault = True
                        raw_docs = body.get("documents")
                        if reextract_vault:
                            doc_inputs = load_vaulted_documents_for_agent(
                                agent_id=agent.id,
                                db_doc_records=existing_doc_rows,
                                target_doc_record_id=target_doc_rec_id,
                            )
                            if not doc_inputs:
                                raise ValueError(
                                    "No vaulted documents found for this agent yet — select or drop one or more files (PDF, DOCX, XLSX, CSV, EML, ICS, TXT, or Image) first."
                                )
                            persist_new_to_vault = False
                        elif isinstance(raw_docs, list) and len(raw_docs) > 0:
                            if len(raw_docs) > MAX_MULTI_ATTACHMENTS:
                                raise ValueError(f"Maximum {MAX_MULTI_ATTACHMENTS} attachments allowed per batch.")
                            doc_inputs = [d for d in raw_docs if isinstance(d, dict)]
                        else:
                            doc_inputs = [{
                                "filename": str(body.get("filename") or ""),
                                "content_base64": str(body.get("content_base64") or ""),
                                "text_content": str(body.get("text_content") or ""),
                            }]

                        batch_results = extract_tracking_items_from_documents_batch(
                            documents=doc_inputs,
                            agent_id=agent.id,
                            agent_name=str(manifest.get("name") or getattr(agent, "name", agent.id)),
                            agent_description=str(manifest.get("description") or getattr(agent, "description", "")),
                            agent_system_prompt=str(manifest.get("system_prompt") or ""),
                            fields=manifest.get("fields"),
                            provider=prov,
                            model=mdl,
                            extraction_hint=hint_val,
                            persist_to_vault=persist_new_to_vault,
                        )

                        all_items: List[Dict[str, Any]] = []
                        committed_ids: List[int] = []
                        per_doc_results: List[Dict[str, Any]] = []
                        primary_ext: Optional[Dict[str, Any]] = None
                        first_doc_rec_id = 0
                        total_tokens = 0

                        for idx_res, ext_res in enumerate(batch_results):
                            if primary_ext is None:
                                primary_ext = ext_res
                            total_tokens += int(ext_res.get("tokens_used", 0) or 0)
                            vault_meta = ext_res.get("vault") or {}
                            doc_sha = str(vault_meta.get("sha256") or "").strip()
                            doc_payload = {
                                "filename": ext_res["filename"],
                                "sha256": doc_sha,
                                "detected_scenario": ext_res["detected_scenario"],
                                "scenario_title": ext_res["scenario_profile"]["title"],
                                "scenario_icon": ext_res["scenario_profile"]["icon"],
                                "summary": ext_res["document_summary"],
                                "items_count": ext_res["items_count"],
                                "engine_used": ext_res["engine_used"],
                                "model_used": ext_res["model_used"],
                                "vault_rel_path": vault_meta.get("vault_rel_path", ""),
                            }
                            src_input = doc_inputs[idx_res] if idx_res < len(doc_inputs) else {}
                            matched_rec_id = int(src_input.get("doc_record_id") or 0)
                            if matched_rec_id not in existing_doc_by_id:
                                matched_rec_id = existing_doc_by_sha.get(doc_sha, 0) if doc_sha else 0
                            if reextract_vault and matched_rec_id > 0:
                                active_db.update_custom_agent_record(
                                    agent_id=agent.id,
                                    record_id=matched_rec_id,
                                    title=ext_res["filename"],
                                    numeric_value=float(ext_res["items_count"]),
                                    status="ok",
                                    data=doc_payload,
                                )
                                doc_rec_id = matched_rec_id
                            else:
                                doc_rec_id = active_db.add_custom_agent_record(
                                    agent_id=agent.id,
                                    title=ext_res["filename"],
                                    record_type="document",
                                    data=doc_payload,
                                    status="ok",
                                    numeric_value=float(ext_res["items_count"]),
                                )
                                if doc_sha:
                                    existing_doc_by_sha[doc_sha] = doc_rec_id
                            if first_doc_rec_id == 0:
                                first_doc_rec_id = doc_rec_id

                            for item in ext_res["items"]:
                                extra_data = dict(item.get("extra_fields") or {})
                                extra_data.setdefault("source_document", ext_res["filename"])
                                extra_data["doc_record_id"] = doc_rec_id
                                item_copy = {**item, "source_document": ext_res["filename"], "extra_fields": extra_data}
                                all_items.append(item_copy)
                                if auto_commit:
                                    cid = active_db.add_custom_agent_record(
                                        agent_id=agent.id,
                                        title=str(item.get("title") or ext_res["filename"]),
                                        record_type="entry",
                                        data=extra_data,
                                        status="ok",
                                        due_date=str(item.get("due_date") or ""),
                                        numeric_value=float(item.get("numeric_value") or 0.0),
                                    )
                                    committed_ids.append(cid)

                            per_doc_results.append({
                                "doc_record_id": doc_rec_id,
                                "filename": ext_res["filename"],
                                "detected_scenario": ext_res["detected_scenario"],
                                "scenario_profile": ext_res["scenario_profile"],
                                "document_summary": ext_res["document_summary"],
                                "items_count": ext_res["items_count"],
                                "engine_used": ext_res["engine_used"],
                                "model_used": ext_res["model_used"],
                            })

                        assert primary_ext is not None
                        combined_filename = (
                            per_doc_results[0]["filename"]
                            if len(per_doc_results) == 1
                            else f"{len(per_doc_results)} attachments ({', '.join(d['filename'] for d in per_doc_results[:3])})"
                        )
                        combined_summary = (
                            per_doc_results[0]["document_summary"]
                            if len(per_doc_results) == 1
                            else " | ".join(f"{d['filename']}: {d['document_summary']}" for d in per_doc_results if d.get("document_summary"))[:420]
                        )

                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                        handler._send_json({
                            "status": "success",
                            "attachments_count": len(per_doc_results),
                            "doc_record_id": first_doc_rec_id,
                            "documents": per_doc_results,
                            "auto_committed": auto_commit,
                            "committed_count": len(committed_ids),
                            "committed_ids": committed_ids,
                            "extraction": {
                                "filename": combined_filename,
                                "detected_scenario": primary_ext["detected_scenario"],
                                "scenario_profile": primary_ext["scenario_profile"],
                                "document_summary": combined_summary,
                                "engine_used": primary_ext["engine_used"],
                                "model_used": primary_ext["model_used"],
                                "tokens_used": total_tokens,
                                "items": all_items,
                                "items_count": len(all_items),
                            },
                            "state": state,
                        })
                    except ValueError as ve:
                        handler._send_json({"status": "error", "message": str(ve)}, status=400)
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=500)
                    return

                if sub_action == "commit":
                    try:
                        from fleet.core.document_extractor import (
                            normalize_extracted_date,
                            normalize_extracted_number,
                        )
                        raw_items = body.get("items")
                        if not isinstance(raw_items, list) or not raw_items:
                            handler._send_json({"status": "error", "message": "Expected non-empty 'items' list."}, status=400)
                            return
                        src_doc = str(body.get("source_document") or "").strip()
                        doc_rec_id = int(body.get("doc_record_id") or 0)
                        committed_ids = []
                        for item in raw_items[:100]:
                            if not isinstance(item, dict):
                                continue
                            title = str(item.get("title") or "").strip()
                            if not title:
                                continue
                            due_iso = normalize_extracted_date(item.get("due_date"))
                            num_val = normalize_extracted_number(item.get("numeric_value"))
                            extra_data = dict(item.get("extra_fields") or {}) if isinstance(item.get("extra_fields"), dict) else {}
                            if src_doc:
                                extra_data.setdefault("source_document", src_doc)
                            if doc_rec_id > 0:
                                extra_data.setdefault("doc_record_id", doc_rec_id)
                            cid = active_db.add_custom_agent_record(
                                agent_id=agent.id,
                                title=title[:160],
                                record_type="entry",
                                data=extra_data,
                                status="ok",
                                due_date=due_iso,
                                numeric_value=num_val,
                            )
                            committed_ids.append(cid)

                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                        handler._send_json({
                            "status": "success",
                            "committed_count": len(committed_ids),
                            "committed_ids": committed_ids,
                            "state": state,
                        })
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=400)
                    return

                if sub_action == "scan_inbox":
                    try:
                        from fleet.core.studio_phase6 import scan_and_ingest_agent_inbox
                        prov_override = str(body.get("provider")).strip() if body.get("provider") else None
                        scan_res = scan_and_ingest_agent_inbox(
                            agent=agent,
                            db=active_db,
                            payload=body,
                            provider_override=prov_override,
                        )
                        state = active_db.get_custom_agent_dashboard_state(agent.id, manifest=manifest)
                        handler._send_json({
                            "status": "success",
                            "scan": scan_res,
                            "state": state,
                        })
                    except Exception as e:
                        handler._send_json({"status": "error", "message": str(e)}, status=400)
                    return

            # Pattern 5c: /api/fleet/agents/<agent_id>/chat (Phase 6: Grounded In-Agent Q&A & Command Chat)
            if len(parts) >= 5 and parts[4] == "chat":
                agent_id = parts[3]
                agent = self.get_agent(agent_id)
                if not agent:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                    return
                active_db = self._resolve_db()
                if active_db is None:
                    handler._send_json({"status": "error", "message": "Database unavailable"}, status=503)
                    return
                if getattr(agent, "db", None) is None:
                    agent.db = active_db
                try:
                    from fleet.core.studio_phase6 import answer_custom_agent_chat
                    msg = str(body.get("message") or body.get("question") or "").strip()
                    chat_res = answer_custom_agent_chat(agent=agent, db=active_db, message=msg)
                    handler._send_json(chat_res)
                except ValueError as ve:
                    handler._send_json({"status": "error", "message": str(ve)}, status=400)
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=500)
                return

            # Pattern 6: /api/fleet/agents/<agent_id>/run
            if len(parts) >= 5 and parts[4] == "run":
                agent_id = parts[3]
                agent = self.get_agent(agent_id)
                if not agent:
                    handler.send_error(404, f"Agent '{agent_id}' not found")
                    return
                try:
                    active_db = self._resolve_db()
                    if getattr(agent, "db", None) is None and active_db is not None:
                        agent.db = active_db
                    meta = getattr(agent, "manifest_meta", {}) or {}
                    task_name = str(body.get("task") or meta.get("routine_task") or "run_check").strip()
                    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
                    exec_res = agent.execute_task(task_name, payload=payload)
                    state = (
                        active_db.get_custom_agent_dashboard_state(agent.id, manifest=agent.get_ui_manifest())
                        if active_db is not None and hasattr(active_db, "get_custom_agent_dashboard_state")
                        else {}
                    )
                    handler._send_json({"status": "success", "result": exec_res, "state": state})
                except Exception as e:
                    handler._send_json({"status": "error", "message": str(e)}, status=500)
                return

            handler.send_error(404, "Unknown agent endpoint")

    def startup_all(self) -> None:
        """Calls on_startup() on all loaded agents."""
        for agent in self.agents.values():
            try:
                agent.on_startup()
            except Exception as e:
                logger.error(f"Error starting agent '{agent.id}': {e}")

    def shutdown_all(self) -> None:
        """Calls on_shutdown() on all loaded agents."""
        for agent in self.agents.values():
            try:
                agent.on_shutdown()
            except Exception as e:
                logger.error(f"Error shutting down agent '{agent.id}': {e}")

    def get_manifests(self, include_disabled: bool = False) -> List[Dict[str, Any]]:
        """Returns sorted list of agent UI manifests for dynamic dashboard rendering."""
        manifests = []
        source_dict = self._all_discovered_agents if include_disabled else self.agents
        for agent in source_dict.values():
            if not include_disabled and not agent.enabled:
                continue
            m = agent.get_ui_manifest()
            if getattr(agent, "_override_default", False):
                m["is_default"] = True
            manifests.append(m)
        manifests.sort(key=lambda x: (x.get("order", 100), x.get("name", "")))
        return manifests

    def get_agent(self, agent_id: str) -> Optional[FleetAgent]:
        return self.agents.get(agent_id) or self.disabled_agents.get(agent_id) or self._all_discovered_agents.get(agent_id)
