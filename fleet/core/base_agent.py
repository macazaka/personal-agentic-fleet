"""
Fleet Agent Base Contract for Personal Agentic Fleet.
All plug-and-play agents inherit from FleetAgent.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class FleetAgent(ABC):
    """
    Abstract Base Class that every plug-and-play Fleet Agent implements.
    Agents are modular units that provide backend APIs, background tasks,
    database schemas, and UI dashboard panes.
    """

    def __init__(self, agent_dir: Path, config: Dict[str, Any], event_bus=None, db=None):
        import json
        from fleet.core.plugin_sandbox import ScopedDatabaseProxy, validate_manifest_permissions

        self.agent_dir = Path(agent_dir)
        self.config = config or {}
        self.event_bus = event_bus
        self.enabled = self.config.get("enabled", True)

        manifest_path = self.agent_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.permissions: List[str] = manifest_data.get("permissions", ["db:read", "ui:render"])
            except Exception:
                self.permissions = ["db:read", "ui:render"]
        else:
            self.permissions = ["db:read", "db:write", "ui:render"]

        unknown_perms = validate_manifest_permissions(self.agent_dir.name, self.permissions)
        if unknown_perms:
            raise PermissionError(f"Agent '{self.agent_dir.name}' declared unknown permissions: {unknown_perms}")

        self._raw_db = db
        self.db = ScopedDatabaseProxy(db, self.agent_dir.name, self.permissions) if db is not None else None

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique machine-readable identifier (e.g. 'health', 'optimizer')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name (e.g. 'Health & Wellness')."""
        pass

    @property
    @abstractmethod
    def icon(self) -> str:
        """Emoji or SVG icon used in tabs and badges (e.g. '🌿', '🚀')."""
        pass

    @property
    def order(self) -> int:
        """Display order for navigation tabs (lower numbers appear first)."""
        return 100

    @property
    def is_default(self) -> bool:
        """Whether this agent is the active default tab on dashboard load."""
        return False

    def on_startup(self) -> None:
        """Called when the fleet server starts up."""
        pass

    def on_shutdown(self) -> None:
        """Called when the fleet server is shutting down."""
        pass

    def register_routes(self, router) -> None:
        """
        Register agent-specific HTTP API endpoints on the fleet router.
        """
        pass

    def register_events(self, event_bus) -> None:
        """
        Subscribe to inter-agent events on the Fleet Event Bus.
        """
        pass

    def register_tasks(self) -> List[Dict[str, Any]]:
        """
        Register scheduled background tasks or toast reminders.
        Returns a list of dicts: [{'name': ..., 'interval_seconds': ..., 'handler': ...}]
        """
        return []

    def get_ui_manifest(self) -> Dict[str, Any]:
        """
        Returns the agent's UI pane HTML, CSS styles, and JavaScript.
        Looks in self.agent_dir / 'ui' by default.
        """
        ui_dir = self.agent_dir / "ui"
        panel_html = ""
        panel_file = ui_dir / "panel.html"
        if panel_file.is_file():
            panel_html = panel_file.read_text(encoding="utf-8")

        has_css = (ui_dir / "style.css").is_file()
        has_js = (ui_dir / "script.js").is_file()

        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "order": self.order,
            "is_default": self.is_default,
            "permissions": getattr(self, "permissions", []),
            "html": panel_html,
            "css_url": f"/api/fleet/agents/{self.id}/style.css" if has_css else None,
            "js_url": f"/api/fleet/agents/{self.id}/script.js" if has_js else None,
        }

