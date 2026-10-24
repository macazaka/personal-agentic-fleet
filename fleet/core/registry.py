"""
Fleet Agent Registry & Dynamic Plugin Loader.
Auto-discovers, loads, and manages lifecycle for plug-and-play agents.
"""

import importlib.util
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from fleet.core.base_agent import FleetAgent

logger = logging.getLogger("fleet.registry")


class AgentRegistry:
    """
    Central registry that discovers and manages all modular Fleet Agents.
    """

    def __init__(self, agents_dir: Optional[Path] = None, config: Optional[Dict[str, Any]] = None, event_bus=None, db=None):
        if agents_dir is None:
            self.agents_dir = Path(__file__).resolve().parent.parent / "agents"
        else:
            self.agents_dir = Path(agents_dir)

        self.config = config or {}
        self.event_bus = event_bus
        self.db = db
        self.agents: Dict[str, FleetAgent] = {}

    def discover_and_load(self) -> Dict[str, FleetAgent]:
        """
        Scans agents_dir for subdirectories containing 'agent.py'.
        Instantiates each agent that subclasses FleetAgent.
        """
        if not self.agents_dir.exists():
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            return {}

        agents_config = self.config.get("agents", {})
        default_agent_id = self.config.get("default_agent", "health")

        for item in sorted(self.agents_dir.iterdir()):
            if not item.is_dir():
                continue
            agent_file = item / "agent.py"
            if not agent_file.is_file():
                continue

            agent_id = item.name
            agent_cfg = agents_config.get(agent_id, {})
            # If explicitly disabled in config, skip
            if agent_cfg.get("enabled") is False:
                logger.info(f"Agent '{agent_id}' is disabled in configuration.")
                continue

            try:
                agent_instance = self._load_agent_from_file(agent_file, item, agent_cfg)
                if agent_instance:
                    # Set is_default based on config or agent default
                    if default_agent_id == agent_instance.id:
                        agent_instance._override_default = True
                    self.agents[agent_instance.id] = agent_instance
                    logger.info(f"Loaded Fleet Agent: {agent_instance.name} [{agent_instance.id}]")
            except Exception as e:
                logger.error(f"Failed to load agent from {agent_file}: {e}", exc_info=True)

        return self.agents

    def _load_agent_from_file(self, file_path: Path, agent_dir: Path, agent_cfg: Dict[str, Any]) -> Optional[FleetAgent]:
        module_name = f"fleet.agents.{agent_dir.name}.agent"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the FleetAgent subclass in the module
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

    def register_all_routes(self, router) -> None:
        """Registers API routes for all loaded agents and registry management."""
        for agent in self.agents.values():
            try:
                agent.register_routes(router)
            except Exception as e:
                logger.error(f"Failed to register routes for agent '{agent.id}': {e}")

        # Core registry endpoints
        @router.get("/api/fleet/agents")
        def get_agents_manifest(handler: Any, parsed_url: urllib.parse.ParseResult):
            manifests = self.get_manifests()
            handler._send_json({"status": "ok", "count": len(manifests), "agents": manifests})

        @router.get("/api/fleet/agents/<agent_id>/style.css")
        def get_agent_style(handler: Any, parsed_url: urllib.parse.ParseResult):
            agent_id = parsed_url.path.split("/")[4]
            if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
                handler.send_error(400, "Invalid agent identifier")
                return
            agent = self.agents.get(agent_id)
            if not agent:
                handler.send_error(404, "Agent not found")
                return
            css_file = (agent.agent_dir / "ui" / "style.css").resolve()
            if not css_file.is_file() or not str(css_file).startswith(str(self.agents_dir.resolve())):
                handler.send_error(404, "Style not found")
                return
            css_bytes = css_file.read_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", "text/css; charset=utf-8")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.send_header("Content-Length", str(len(css_bytes)))
            handler.end_headers()
            handler.wfile.write(css_bytes)

        @router.get("/api/fleet/agents/<agent_id>/script.js")
        def get_agent_script(handler: Any, parsed_url: urllib.parse.ParseResult):
            agent_id = parsed_url.path.split("/")[4]
            if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
                handler.send_error(400, "Invalid agent identifier")
                return
            agent = self.agents.get(agent_id)
            if not agent:
                handler.send_error(404, "Agent not found")
                return
            js_file = (agent.agent_dir / "ui" / "script.js").resolve()
            if not js_file.is_file() or not str(js_file).startswith(str(self.agents_dir.resolve())):
                handler.send_error(404, "Script not found")
                return
            js_bytes = js_file.read_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", "application/javascript; charset=utf-8")
            handler.send_header("X-Content-Type-Options", "nosniff")
            handler.send_header("Content-Length", str(len(js_bytes)))
            handler.end_headers()
            handler.wfile.write(js_bytes)

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

    def get_manifests(self) -> List[Dict[str, Any]]:
        """Returns sorted list of agent UI manifests for dynamic dashboard rendering."""
        manifests = []
        for agent in self.agents.values():
            m = agent.get_ui_manifest()
            if getattr(agent, "_override_default", False):
                m["is_default"] = True
            manifests.append(m)
        manifests.sort(key=lambda x: (x.get("order", 100), x.get("name", "")))
        return manifests

    def get_agent(self, agent_id: str) -> Optional[FleetAgent]:
        return self.agents.get(agent_id)

