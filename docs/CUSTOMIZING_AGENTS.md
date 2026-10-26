# 🎨 Customizing Agents & Package Isolation Guide

Personal Agentic Fleet provides a dual-guarantee architecture:
1. **Complete Customization Flexibility**: Users have full freedom to customize any built-in agent (display name, icon, tab ordering, default tab status, preferred LLM hyperscaler provider/model, custom system prompts, and custom UI panels).
2. **Strict Package Isolation**: Every agent inside `fleet/agents/` is a self-contained, isolated package governed by a strict `manifest.json`. Customizations can never elevate permissions or breach capability boundaries.

---

## 🏗️ The 3-File Agent Package Anatomy

Every agent in Fleet—whether built-in or user-customized—must strictly adhere to this isolated package structure:

```text
fleet/agents/<agent_id>/          (or fleet/data/user/custom_agents/<agent_id>/)
├── manifest.json                 # Mandatory: Declares unique ID, metadata, and strict least-privilege permissions
├── agent.py                      # Mandatory: Backend class inheriting from FleetAgent
└── ui/
    ├── panel.html                # Mandatory: Isolated HTML presentation pane
    ├── style.css                 # Optional: Scoped stylesheet
    └── script.js                 # Optional: Scoped client interactivity
```

---

## 🛡️ Package Isolation & Capability Sandboxing

Every agent operates within a defense-in-depth sandbox enforced by [`fleet/core/plugin_sandbox.py`](../fleet/core/plugin_sandbox.py):

| Mechanism | Enforcement | Security Guarantee |
| :--- | :--- | :--- |
| **Strict `manifest.json`** | Mandatory capability contract | Agents declare only required permissions from `ALLOWED_AGENT_PERMISSIONS` (`db:read`, `db:write`, `event_bus:publish`, etc.). |
| **Immutable Permissions** | Sourced strictly from package on disk | User configurations (`fleet.yaml`), runtime API updates, and LLMs **cannot modify or elevate permissions**. |
| **`ScopedDatabaseProxy`** | Wraps SQLite database calls | An agent without `db:write` in its manifest is blocked with `PermissionError` if it calls any mutating DB method. |
| **Asset Path Sandboxing** | Path canonicalization | `/api/fleet/agents/<id>/style.css` and `script.js` verify that file paths cannot traverse outside the agent's package directory. |
| **Subprocess Sanitizer** | `get_sanitized_plugin_env()` | Strips API keys, DPAPI secrets, and confidential tokens from environment mappings before any agent subprocess executes. |

---

## 🛠️ Method 1: Customizing Any Agent via `fleet.yaml`

Copy [`fleet.yaml.example`](../fleet.yaml.example) to `fleet.yaml`. You can customize any built-in agent without editing core code:

```yaml
# User Custom Agents Directory (immune to git pulls and git-ignored)
custom_agents_dir: "fleet/data/user/custom_agents"

agents:
  health:
    enabled: true
    name: "Metabolic & Akhada Strength Command"   # Custom display name
    icon: "💪"                                    # Custom emoji/icon
    order: 1                                      # Place as first tab in dashboard
    is_default: true                              # Open automatically on launch
    videos_directory: "D:/Fitness/Akhada"         # Custom fitness directory
    reminders_enabled: true

  antigravity:
    enabled: true
    name: "Senior Code Architect"
    icon: "🤖"
    order: 2
    provider: "anthropic"                         # Route completions to Anthropic Claude
    model: "claude-3-7-sonnet-20241022"
    system_prompt: "You are a principal engineer optimizing Python microkernels."

  overview:
    enabled: true
    name: "Mission Control"
    icon: "⚡"
    order: 3
    provider: "google"                            # Route completions to Google Gemini
    model: "gemini-2.5-pro"

  optimizer:
    enabled: true
    name: "PC Turbo Booster"
    icon: "🚀"
    order: 4
    scan_interval_hours: 4                        # Custom background schedule
```

### Supported Customization Keys

| Key | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Custom display name rendered in dashboard tabs. |
| `icon` | `string` | Custom emoji or SVG icon. |
| `order` | `integer` | Tab display order (lower integers appear first). |
| `is_default` | `boolean` | Whether this agent is the active default tab on dashboard load. |
| `enabled` | `boolean` | Toggles the agent on/off. |
| `provider` | `string` | Preferred hyperscaler: `"auto"`, `"google"`, `"anthropic"`, `"microsoft"`, `"aws"`, `"ollama"`. |
| `model` | `string` | Specific model: `"claude-3-7-sonnet"`, `"gemini-2.5-pro"`, `"gpt-4o"`, `"llama3.2"`. |
| `system_prompt` | `string` | Custom persona or system instructions. |
| `custom_panel_path` | `string` | Path to a custom HTML file that completely overrides the frontend pane. |
| `settings` | `object` | Key-value dictionary of custom agent-specific parameters. |

---

## 🌐 Method 2: Runtime Customization via REST API

The Fleet HTTP server exposes REST endpoints to inspect and customize any agent dynamically at runtime without restarting the server:

### 1. Inspect Agent Configuration
```http
GET /api/fleet/agents/{agent_id}/config
```
**Response:**
```json
{
  "status": "ok",
  "id": "health",
  "manifest": {
    "name": "Health & Wellness",
    "icon": "🌿",
    "order": 10,
    "is_default": true,
    "permissions": ["db:read", "db:write", "filesystem:videos", "ui:render"]
  },
  "preferred_provider": "auto",
  "preferred_model": null
}
```

### 2. Update Agent Configuration
```http
POST /api/fleet/agents/{agent_id}/config
Content-Type: application/json

{
  "name": "Personal Wellness Center",
  "icon": "🧘",
  "order": 1,
  "provider": "google",
  "model": "gemini-2.5-pro"
}
```
*Overrides are persisted to `fleet/data/user/agent_overrides.json` and immediately applied to the live agent in memory.*

### 3. Reset Agent to Defaults
```http
POST /api/fleet/agents/{agent_id}/reset
```
*Removes user overrides and restores original package defaults.*

---

## 🤖 Method 3: FastMCP Tools (AI Assistant Integration)

If you use Google Antigravity, Claude Code, Cursor, or GitHub Copilot, you can customize agents using FastMCP tools:

### `fleet_customize_agent`
```json
{
  "agent_id": "health",
  "name": "Metabolic Command",
  "icon": "🏋️",
  "order": 1,
  "provider": "anthropic",
  "model": "claude-3-7-sonnet-20241022"
}
```

### `fleet_create_custom_agent`
```json
{
  "agent_id": "smart_home",
  "name": "Home Assistant IoT",
  "icon": "🏠",
  "description": "Monitors Zigbee sensors, Philips Hue lights, and smart plugs.",
  "order": 25
}
```

---

## 📁 Method 4: Creating Private User Custom Agents

To create an entirely new agent that is **100% private**, protected by DPAPI ACLs, and immune to `git pull` overwrites, place it in `fleet/data/user/custom_agents/`:

### Step 1: Create Directory & Manifest
Create `fleet/data/user/custom_agents/weather/manifest.json`:
```json
{
  "id": "weather",
  "name": "Local Meteorology",
  "version": "1.0.0",
  "icon": "🌦️",
  "description": "Local weather forecasting and outdoor workout conditions.",
  "permissions": ["db:read", "ui:render"]
}
```

### Step 2: Implement Backend Class
Create `fleet/data/user/custom_agents/weather/agent.py`:
```python
from typing import Any, Dict
from pathlib import Path
from fleet.core.base_agent import FleetAgent

class WeatherAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "Local Meteorology"

    @property
    def icon(self) -> str:
        return "🌦️"

    @property
    def order(self) -> int:
        return 35

    def register_routes(self, router) -> None:
        @router.get("/api/weather/forecast")
        def get_forecast(handler: Any, parsed_url: Any):
            # Safe 0-token weather response
            handler._send_json({"status": "ok", "temp_c": 26, "condition": "Sunny", "good_for_akhada": True})
```

### Step 3: Add Frontend UI Pane
Create `fleet/data/user/custom_agents/weather/ui/panel.html`:
```html
<div class="panel-section">
  <div class="section-header">
    <div class="section-title">
      <span class="section-title-icon">🌦️</span>
      <span>Local Meteorology & Workout Conditions</span>
    </div>
  </div>
  <div class="card" style="padding: 20px;">
    <h3>26°C — Ideal for Akhada Mudgal Session</h3>
  </div>
</div>
```

On startup, [`AgentRegistry`](../fleet/core/registry.py) discovers your custom agent, validates its `manifest.json`, registers its routes, and renders its tab automatically!

---

## 🔒 Package Isolation Invariants Checklist

When customizing or creating agents, ensure:
- [x] Every agent folder has a valid `manifest.json` declaring minimal necessary permissions.
- [x] The manifest `id` matches the directory name exactly.
- [x] All declared permissions are from `ALLOWED_AGENT_PERMISSIONS`.
- [x] Backend logic inherits from `FleetAgent`.
- [x] Every agent package contains an isolated `ui/panel.html`.
- [x] Preflight quality gate passes: `python -m fleet.tools.preflight_gate`.
