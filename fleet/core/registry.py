"""
Fleet Agent Registry & Dynamic Plugin Loader.
Auto-discovers, loads, and manages lifecycle for plug-and-play agents.
Supports both built-in core agents (fleet/agents/) and private user custom agents
(fleet/data/user/custom_agents/), with runtime customization and persistent overrides.
"""

import importlib.util
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

        # User custom agents directory (persisted and git-ignored)
        if custom_agents_dir is not None:
            self.custom_agents_dir = Path(custom_agents_dir)
        elif "custom_agents_dir" in self.config:
            self.custom_agents_dir = Path(self.config["custom_agents_dir"])
        else:
            try:
                from fleet.config import DATA_DIR
                self.custom_agents_dir = DATA_DIR / "user" / "custom_agents"
            except Exception:
                self.custom_agents_dir = self.agents_dir.parent / "data" / "user" / "custom_agents"

    def _get_overrides_file(self) -> Path:
        """Returns path to the user's persistent agent configuration overrides file."""
        try:
            from fleet.config import DATA_DIR
            vault = DATA_DIR / "user"
        except Exception:
            vault = self.agents_dir.parent / "data" / "user"
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
                    db=self.db,
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
    ) -> Dict[str, Any]:
        """
        Scaffolds a new user-customized agent in the private user vault (custom_agents_dir)
        and loads it into the live registry immediately.
        """
        clean_id = re.sub(r"[^a-zA-Z0-9_]", "", agent_id.lower()).strip()
        if not clean_id:
            raise ValueError(f"Invalid agent ID '{agent_id}'. Must contain alphanumeric characters.")

        if clean_id in self.agents:
            raise ValueError(f"Agent with ID '{clean_id}' already exists.")

        agent_folder = self.custom_agents_dir / clean_id
        ui_folder = agent_folder / "ui"
        ui_folder.mkdir(parents=True, exist_ok=True)

        # 1. manifest.json
        manifest = {
            "id": clean_id,
            "name": name,
            "version": "1.0.0",
            "icon": icon,
            "description": description or f"User custom agent: {name}",
            "permissions": permissions or ["db:read", "ui:render"],
        }
        (agent_folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 2. agent.py
        class_name = "".join(part.capitalize() for part in clean_id.split("_")) + "Agent"
        agent_code = f'''"""
Custom User Agent: {name}
Auto-generated by Personal Agentic Fleet Customization Engine.
"""

from pathlib import Path
from typing import Any, Dict
from fleet.core.base_agent import FleetAgent


class {class_name}(FleetAgent):
    @property
    def id(self) -> str:
        return "{clean_id}"

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def icon(self) -> str:
        return "{icon}"

    @property
    def order(self) -> int:
        return {initial_order}

    def on_startup(self) -> None:
        pass
'''
        (agent_folder / "agent.py").write_text(agent_code, encoding="utf-8")

        # 3. ui/panel.html (Header identity is rendered once by #viewActiveAgentStage)
        panel_html = f'''<div class="panel-section">
  <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 24px;">
    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 16px;">
      {description or "Welcome to your custom agent pane. Edit this panel in fleet/data/user/custom_agents/" + clean_id + "/ui/panel.html"}
    </p>
    <div style="font-family: monospace; font-size: 12px; color: #38bdf8; background: #0f172a; padding: 12px; border-radius: 8px;">
      Declared Permissions: {', '.join(permissions or ['db:read', 'ui:render'])}
    </div>
  </div>
</div>
'''
        (ui_folder / "panel.html").write_text(panel_html, encoding="utf-8")

        # 4. ui/style.css
        (ui_folder / "style.css").write_text(f"/* Custom styles for {clean_id} */\n", encoding="utf-8")

        # Load newly created agent immediately
        agent_instance = self._load_agent_from_file(
            file_path=agent_folder / "agent.py",
            agent_dir=agent_folder,
            agent_cfg={"enabled": True},
            module_prefix="fleet.custom_agents",
        )
        if agent_instance:
            self.agents[clean_id] = agent_instance
            self._all_discovered_agents[clean_id] = agent_instance
            return agent_instance.get_ui_manifest()

        raise RuntimeError(f"Failed to load newly created agent '{clean_id}'")

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
