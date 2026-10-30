"""
Fleet Agent Base Contract for Personal Agentic Fleet.
All plug-and-play agents inherit from FleetAgent.
Provides universal customization hooks, least-privilege sandboxing,
per-agent hyperscaler routing, and dynamic UI pane management.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class FleetAgent(ABC):
    """
    Abstract Base Class that every plug-and-play Fleet Agent implements.
    Agents are modular units that provide backend APIs, background tasks,
    database schemas, and UI dashboard panes.

    Universal Customization Framework:
    - Users can customize display name, icon, order, default status, system prompt,
      and preferred hyperscaler provider/model via `fleet.yaml` or the Agent Settings API.
    - Custom panel templates can be placed in `fleet/data/user/custom_ui/<agent_id>/panel.html`.
    """

    def __init__(self, agent_dir: Path, config: Optional[Dict[str, Any]] = None, event_bus=None, db=None):
        import json
        from fleet.core.plugin_sandbox import ScopedDatabaseProxy, validate_manifest_permissions

        self.agent_dir = Path(agent_dir)
        self.config = dict(config or {})
        self.event_bus = event_bus
        self.enabled = bool(self.config.get("enabled", True))

        self.manifest_meta: Dict[str, Any] = {}
        manifest_path = self.agent_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(manifest_data, dict):
                    self.manifest_meta = manifest_data
                self.permissions: List[str] = self.manifest_meta.get("permissions", ["db:read", "ui:render"])
            except Exception:
                self.permissions = ["db:read", "ui:render"]
        else:
            self.permissions = ["db:read", "db:write", "ui:render"]

        unknown_perms = validate_manifest_permissions(self.agent_dir.name, self.permissions)
        if unknown_perms:
            raise PermissionError(f"Agent '{self.agent_dir.name}' declared unknown permissions: {unknown_perms}")

        self._raw_db = db
        self.db = ScopedDatabaseProxy(db, self.agent_dir.name, self.permissions) if db is not None else None
        self._override_default: Optional[bool] = None

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique machine-readable identifier (e.g. 'health', 'optimizer')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Default human-readable display name (e.g. 'Health & Wellness')."""
        pass

    @property
    @abstractmethod
    def icon(self) -> str:
        """Default emoji or SVG icon used in tabs and badges (e.g. '🌿', '🚀')."""
        pass

    @property
    def order(self) -> int:
        """Default display order for navigation tabs (lower numbers appear first)."""
        return 100

    @property
    def is_default(self) -> bool:
        """Whether this agent is the active default tab on dashboard load."""
        return False

    @property
    def is_custom(self) -> bool:
        """Whether this agent is a user-created or catalog-installed custom agent."""
        return "custom_agents" in self.agent_dir.as_posix()

    # === Universal User Customization Overrides ===

    @property
    def display_name(self) -> str:
        """Human-readable name, respecting user configuration override if present."""
        return str(self.config.get("name") or self.name)

    @property
    def display_icon(self) -> str:
        """Icon/emoji, respecting user configuration override if present."""
        return str(self.config.get("icon") or self.icon)

    @property
    def display_order(self) -> int:
        """Tab sort order, respecting user configuration override if present."""
        val = self.config.get("order")
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return self.order

    @property
    def is_active_default(self) -> bool:
        """Whether this agent is the active default tab, respecting user override."""
        if "is_default" in self.config:
            return bool(self.config["is_default"])
        return getattr(self, "_override_default", self.is_default)

    # === Hyperscaler & Model Preferences Per Agent ===

    @property
    def preferred_provider(self) -> str:
        """
        Configured LLM hyperscaler provider for this agent:
        'auto', 'google', 'anthropic', 'microsoft', 'aws', or 'ollama'.
        """
        return str(self.config.get("provider", "auto"))

    @property
    def preferred_model(self) -> Optional[str]:
        """
        Configured LLM model for this agent (e.g., 'gemini-3.8-flash-low', 'claude-sonnet-5-5-medium').
        """
        val = self.config.get("model") or getattr(self, "manifest_meta", {}).get("model")
        return str(val) if val else None

    @property
    def system_prompt(self) -> Optional[str]:
        """User-customized system instruction or prompt for this agent."""
        return (
            self.config.get("system_prompt")
            or self.config.get("prompt")
            or getattr(self, "manifest_meta", {}).get("system_prompt")
        )

    def complete_prompt(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Routes an inference request through the Fleet Hyperscaler Gateway using
        this agent's configured provider, model, and system prompt.
        """
        from fleet.core.hyperscalers import HyperscalerGateway
        gw = HyperscalerGateway()
        return gw.complete(
            prompt=prompt,
            provider=provider or self.preferred_provider,
            model=model or self.preferred_model,
            system_instruction=system_instruction or self.system_prompt or "",
            **kwargs,
        )

    # === Dynamic Runtime Customization & Settings ===

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves an agent-specific setting from the agent's configuration."""
        settings = self.config.get("settings", {})
        if isinstance(settings, dict) and key in settings:
            return settings[key]
        return self.config.get(key, default)

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically updates the agent's active configuration at runtime.
        Enables live reconfiguration without restarting the server.
        """
        self.config.update(new_config)
        if "enabled" in new_config:
            self.enabled = bool(new_config["enabled"])
        self.on_config_updated()
        return self.config

    def on_config_updated(self) -> None:
        """Lifecycle hook called when the agent configuration is modified dynamically."""
        pass

    # === Lifecycle Hooks ===

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

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a scheduled or ad-hoc task for this agent.
        Subclasses override this to implement agent-specific scheduled logic.
        """
        return {"status": "NOT_IMPLEMENTED", "agent": self.id, "task": task}

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        """
        Returns a list of agent-specific configurable settings declarations.
        Subclasses override this to expose custom settings to the dashboard.
        """
        return []

    def get_omnibar_commands(self) -> List[Dict[str, Any]]:
        """
        UX-05 & Phase 4: Returns @agent slash/omnibar commands supported by this agent.
        Automatically indexed by the Unified Ask-Fleet Omnibar (Ctrl+K), including
        auto-generated quick-capture (`add`) and on-demand AI briefing (`ai`) shortcuts for custom Studio agents.
        """
        meta = getattr(self, "manifest_meta", {}) or {}
        routine_task = str(meta.get("routine_task") or "default")
        cmds: List[Dict[str, Any]] = [
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": f"@{self.id}",
                "syntax": f"@{self.id} run",
                "description": f"Execute '{routine_task}' on {self.display_name}",
                "task": routine_task if self.is_custom else "default",
            },
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": f"@{self.id} open",
                "syntax": f"@{self.id} open",
                "description": f"Switch workspace view to {self.display_name}",
                "task": "open_tab",
            },
        ]
        if self.is_custom:
            cmds.append({
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": f"@{self.id} add",
                "syntax": f"@{self.id} add <item> [YYYY-MM-DD] [amount]",
                "description": f"Log a new SQLite record into {self.display_name} ($0.00)",
                "task": "add_record",
            })
            intel_mode = str(meta.get("intelligence_mode") or "hybrid")
            if intel_mode != "deterministic":
                cmds.append({
                    "agent_id": self.id,
                    "agent_name": self.display_name,
                    "icon": self.display_icon,
                    "trigger": f"@{self.id} ai",
                    "syntax": f"@{self.id} ai",
                    "description": f"Synthesize Antigravity AI executive briefing on {self.display_name}",
                    "task": "ai_analyze",
                })
        return cmds


    # === UI Manifest & Template Customization ===

    def get_ui_manifest(self) -> Dict[str, Any]:
        """
        Returns the agent's UI pane HTML, CSS styles, and JavaScript.
        Supports custom user UI pane overrides from:
          1. config['custom_panel_path']
          2. fleet/data/user/custom_ui/<agent_id>/panel.html
          3. built-in self.agent_dir / 'ui' / 'panel.html'
        """
        ui_dir = self.agent_dir / "ui"
        panel_html = ""

        # 1. Custom panel path specified in config
        custom_panel_path = self.config.get("custom_panel_path")
        if custom_panel_path:
            p = Path(custom_panel_path)
            if p.is_file():
                try:
                    panel_html = p.read_text(encoding="utf-8")
                except Exception as e:
                    panel_html = f"<!-- Error loading custom panel: {e} -->"

        # 2. User vault custom UI override
        if not panel_html:
            try:
                from fleet.config import DATA_DIR
                user_ui_panel = DATA_DIR / "user" / "custom_ui" / self.id / "panel.html"
                if user_ui_panel.is_file():
                    panel_html = user_ui_panel.read_text(encoding="utf-8")
            except Exception:
                pass

        # 3. Default built-in panel
        if not panel_html:
            panel_file = ui_dir / "panel.html"
            if panel_file.is_file():
                panel_html = panel_file.read_text(encoding="utf-8")

        has_css = (ui_dir / "style.css").is_file()
        has_js = (ui_dir / "script.js").is_file()

        schema = self.get_agent_settings_schema()
        current_settings = self.config.get("settings", {})
        if not isinstance(current_settings, dict):
            current_settings = {}
        enriched_schema = []
        for s in schema:
            s_copy = dict(s)
            s_copy["value"] = current_settings.get(s["id"], s.get("default"))
            enriched_schema.append(s_copy)

        is_customized = bool(
            self.config.get("name")
            or self.config.get("icon")
            or self.config.get("order") is not None
            or self.config.get("provider")
            or self.config.get("model")
            or self.config.get("system_prompt")
            or self.config.get("custom_panel_path")
            or self.config.get("settings")
        )

        is_custom = "custom_agents" in self.agent_dir.as_posix()
        meta = getattr(self, "manifest_meta", {}) or {}

        return {
            "id": self.id,
            "name": self.display_name,
            "version": str(meta.get("version") or "1.0.0"),
            "icon": self.display_icon,
            "order": self.display_order,
            "category": str(meta.get("category") or ""),
            "description": str(meta.get("description") or ""),
            "is_default": self.is_active_default,
            "is_custom": is_custom,
            "enabled": self.enabled,
            "provider": self.preferred_provider,
            "model": self.preferred_model,
            "system_prompt": self.system_prompt,
            "intelligence_mode": str(meta.get("intelligence_mode") or "hybrid"),
            "archetype": str(meta.get("archetype") or ""),
            "ui_blocks": meta.get("ui_blocks", []),
            "routine_task": str(meta.get("routine_task") or ""),
            "schedule": meta.get("schedule", {}),
            "schedule_cadence": str(meta.get("schedule_cadence") or ""),
            "fields": meta.get("fields", []),
            "checklist_items": meta.get("checklist_items", []),
            "event_triggers": meta.get("event_triggers", []),
            "outbound_actions": meta.get("outbound_actions", []),
            "auto_ingest_inbox": bool(meta.get("auto_ingest_inbox", False)),
            "default_recurrence": str(meta.get("default_recurrence") or "none"),
            "evolution_improvements": meta.get("evolution_improvements", []),
            "settings": current_settings,
            "agent_settings_schema": enriched_schema,
            "is_customized": is_customized,
            "permissions": getattr(self, "permissions", []),
            "html": panel_html,
            "panel_html": panel_html,
            "css_url": f"/api/fleet/agents/{self.id}/style.css" if has_css else None,
            "js_url": f"/api/fleet/agents/{self.id}/script.js" if has_js else None,
        }
