"""
Fleet Agent Scaffolder CLI (fleet.tools.create_agent).
Automates scaffolding of brand-new, isolated plug-and-play agent packages
with valid manifest contracts, entrypoints, and UI panels.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS, validate_manifest_permissions


def sanitize_agent_id(agent_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]", "_", agent_id.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or not re.match(r"^[a-z0-9_]+$", cleaned):
        raise ValueError(f"Invalid agent ID '{agent_id}'. Must be lowercase alphanumeric and underscores.")
    return cleaned


def to_pascal_case(snake_str: str) -> str:
    return "".join(part.capitalize() for part in snake_str.split("_") if part)


def scaffold_agent(
    agent_id: str,
    name: Optional[str] = None,
    icon: str = "⚡",
    description: str = "Plug-and-play Fleet agent package.",
    permissions: Optional[List[str]] = None,
    order: int = 60,
    target_dir: Optional[Path] = None,
) -> Path:
    agent_id = sanitize_agent_id(agent_id)
    display_name = name.strip() if name and name.strip() else to_pascal_case(agent_id) + " Agent"

    if permissions is None:
        permissions = ["db:read", "ui:render"]

    # Validate permissions
    invalid = [p for p in permissions if p not in ALLOWED_AGENT_PERMISSIONS]
    if invalid:
        raise ValueError(f"Invalid permissions {invalid}. Allowed: {sorted(list(ALLOWED_AGENT_PERMISSIONS))}")

    # Determine base directory
    if target_dir is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        target_dir = repo_root / "fleet" / "agents" / agent_id
    else:
        target_dir = Path(target_dir).resolve() / agent_id

    if target_dir.exists():
        raise FileExistsError(f"Agent directory already exists at {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)
    ui_dir = target_dir / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate manifest.json
    manifest_data = {
        "id": agent_id,
        "name": display_name,
        "version": "1.0.0",
        "description": description.strip(),
        "icon": icon.strip(),
        "order": int(order),
        "is_default": False,
        "permissions": permissions,
        "entrypoint": "agent.py",
        "author": "Fleet Contributor"
    }

    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # 2. Generate agent.py
    class_name = to_pascal_case(agent_id) + "Agent"
    agent_code = f'''"""
{display_name} package for Personal Agentic Fleet.
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent


class {class_name}(FleetAgent):
    @property
    def id(self) -> str:
        return "{agent_id}"

    @property
    def name(self) -> str:
        return "{display_name}"

    @property
    def icon(self) -> str:
        return "{icon}"

    @property
    def order(self) -> int:
        return {order}

    @property
    def is_default(self) -> bool:
        return False

    def register_routes(self, router) -> None:
        """Register custom FastAPI / HTTP endpoints if needed."""
        pass

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute scheduled recurring task or ad-hoc background job."""
        return {{
            "status": "success",
            "title": f"{icon} {display_name}: {{task}}",
            "message": f"Executed scheduled task '{{task}}' successfully.",
            "agent": self.id,
            "task": task
        }}
'''
    agent_py_path = target_dir / "agent.py"
    agent_py_path.write_text(agent_code, encoding="utf-8")

    # 3. Generate ui/panel.html
    panel_html = f'''<div class="agent-panel" id="panel_{agent_id}" style="padding: 16px;">
  <div class="card" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px;">
    <div class="card-title" style="display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 700; color: var(--text);">
      <span>{icon}</span>
      <span>{display_name}</span>
    </div>
    <p style="color: var(--text-muted); font-size: 13px; margin-top: 8px;">
      {description}
    </p>
    <div style="margin-top: 14px; padding: 12px; background: rgba(15, 23, 42, 0.5); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05);">
      <div style="font-size: 11px; font-weight: 600; color: var(--accent-cyan); text-transform: uppercase;">Declared Capabilities</div>
      <div style="display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap;">
        {' '.join(f'<span class="badge" style="background: rgba(56, 189, 248, 0.12); color: var(--accent-cyan); font-size: 11px; padding: 2px 8px;">{p}</span>' for p in permissions)}
      </div>
    </div>
  </div>
</div>
'''
    panel_html_path = ui_dir / "panel.html"
    panel_html_path.write_text(panel_html, encoding="utf-8")

    # 4. Verify package integrity
    validate_manifest_permissions(agent_id, permissions)
    return target_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a brand-new plug-and-play isolated agent package for Personal Agentic Fleet."
    )
    parser.add_argument("--id", "-i", required=True, help="Unique lowercase agent ID (e.g. weather, finance, notes)")
    parser.add_argument("--name", "-n", default=None, help="User-facing display name")
    parser.add_argument("--icon", default="⚡", help="Display emoji / icon (default: ⚡)")
    parser.add_argument("--description", "-d", default="Plug-and-play Fleet agent package.", help="Short summary")
    parser.add_argument(
        "--permissions", "-p",
        default="db:read,ui:render",
        help="Comma-separated least-privilege permissions (e.g. db:read,db:write,ui:render,system:exec)"
    )
    parser.add_argument("--order", type=int, default=60, help="Navigation order index (default: 60)")
    parser.add_argument("--target-dir", default=None, help="Custom parent directory (default: fleet/agents/)")

    args = parser.parse_args()

    perms = [p.strip() for p in args.permissions.split(",") if p.strip()]

    try:
        path = scaffold_agent(
            agent_id=args.id,
            name=args.name,
            icon=args.icon,
            description=args.description,
            permissions=perms,
            order=args.order,
            target_dir=Path(args.target_dir) if args.target_dir else None
        )
        print(f"✅ Successfully created agent '{args.id}' at: {path}")
        print(f"   Manifest: {path / 'manifest.json'}")
        print(f"   Code:     {path / 'agent.py'}")
        print(f"   UI:       {path / 'ui' / 'panel.html'}")
        return 0
    except Exception as exc:
        print(f"❌ Error scaffolding agent: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
