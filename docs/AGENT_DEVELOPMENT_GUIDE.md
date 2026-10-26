# 🤖 Personal Agentic Fleet — Comprehensive Agent Development Guide

Welcome to the definitive guide for designing, building, sandboxing, and publishing custom autonomous agents for **Personal Agentic Fleet**.

Personal Agentic Fleet employs an isolated microkernel architecture: **every capability is a self-contained agent package**. Whether you are building an RSS news summarizer, home automation controller, financial portfolio tracker, or deep code auditor, this guide covers the entire lifecycle from visual wizard generation to production testing and self-critique calibration.

---

## 🏛️ Foundational Agent Design Invariants

Every agent in the fleet must adhere to these foundational principles:

1. **$0.00 Zero-Token Determinism by Default**: Fast, local Python and SQLite execution must be the default baseline. Cloud LLM calls should be reserved for complex reasoning and must route through the `HyperscalerGateway`.
2. **Least-Privilege Capability Manifest (`manifest.json`)**: Agents declare only the exact OS, network, and database capabilities they require. Undeclared operations are blocked at the microkernel sandbox boundary.
3. **Cognitive Integration (Brain, Consciousness, Subconsciousness, Soul)**:
   - *Brain*: All inter-agent communication routes through `fleet.core.event_bus`, firing synaptic impulses.
   - *Consciousness*: Agent actions are subject to real-time deterministic self-critique (`SelfCritiqueEngine`) measuring structural soundness, content completeness, and intent fidelity.
   - *Subconsciousness*: Agent activity logs are consolidated nightly during dream cycles (23:00–06:00), mining latent habits and operational friction.
   - *Soul*: Agents must respect Sovereign Privacy (local custody), Frugality ($0.00 invariant), and Metabolic Care (quiet hours).
4. **Complete Package Isolation**: Agents live entirely in `fleet/agents/<agent_id>/` (or `fleet/data/user/custom_agents/<agent_id>/`). They require zero edits to existing core files.
5. **Universal Multi-OS Parity**: Uniform behavior across Windows 10/11, macOS, and Linux without platform-specific hardcoding.

---

## 📦 The Agent Package Anatomy

An agent package consists of 3 mandatory files and optional assets:

```text
fleet/agents/<agent_id>/          (or fleet/data/user/custom_agents/<agent_id>/)
├── manifest.json                 # Mandatory: Package identity, capabilities & settings schema
├── agent.py                      # Mandatory: Backend class inheriting from FleetAgent
└── ui/
    ├── panel.html                # Mandatory: Presentation HTML injected into the dashboard
    ├── style.css                 # Optional: Scoped CSS stylesheets
    └── script.js                 # Optional: Scoped client-side interactivity
```

---

## 🛡️ The Capability Manifest Contract (`manifest.json`)

The `manifest.json` contract defines what the microkernel permits your agent to do. Any attempt to access undeclared resources raises a `PermissionError`.

```json
{
  "id": "smart_home",
  "name": "Smart Home Controller",
  "version": "1.0.0",
  "icon": "🏠",
  "order": 45,
  "category": "automation",
  "description": "Monitors and automates local IoT lights, therms, and sensors.",
  "permissions": [
    "network:outbound",
    "db:read",
    "db:write",
    "ui:render"
  ],
  "settings_schema": {
    "hub_ip": {
      "type": "string",
      "label": "Home Hub IP Address",
      "default": "192.168.1.100",
      "description": "Local IP address of your Home Assistant or Zigbee bridge"
    },
    "poll_interval_sec": {
      "type": "number",
      "label": "Sensor Poll Interval (sec)",
      "default": 30,
      "min": 5,
      "max": 3600
    },
    "enable_night_mode": {
      "type": "boolean",
      "label": "Auto-Dim at 22:30",
      "default": true
    }
  }
}
```

### Complete Permissions Reference

| Permission Key | Description & Enforcement |
| :--- | :--- |
| `network:outbound` | Permits outbound HTTP/socket connections through the network filter. |
| `db:read` | Permits reading tasks, notes, activities, and memories from the SQLite database. |
| `db:write` | Permits logging activities, creating tasks, and updating status via `ScopedDatabaseProxy`. |
| `ui:render` | Mounts the agent's `ui/panel.html` into the dashboard DOM and tab navigation. |
| `notification:send`| Permits dispatching native OS desktop notifications (WinRT, AppleScript, libnotify). |
| `fs:read` | Permits reading files within the user's workspace directory. |
| `fs:write` | Permits modifying files within the user's workspace directory. |
| `os:exec` | Permits launching external subprocesses (environment sanitized via `get_sanitized_plugin_env()`). |
| `tokens:spend` | Grants permission to request cloud LLM completions when local Tier 0 cannot resolve. |

---

## 🚀 4 Ways to Create a New Agent

### Method 1: The Visual 4-Step Wizard (Web Control Center)
1. Open the dashboard at `http://127.0.0.1:7890/`.
2. Click the **`+` icon** in the top-right header next to the Settings gear.
3. Complete the interactive workflow:
   - **Step 1: Identity & Persona**: Enter Name, Unique ID, Emoji icon, Category, and Description.
   - **Step 2: Security & Capabilities**: Toggle exact permission checkboxes.
   - **Step 3: Settings Schema & Routines**: Configure sync intervals and background task intervals.
   - **Step 4: Verification & Launch**: Inspect the live-rendered `manifest.json`, `agent.py`, and `ui/panel.html` code preview, then click **Create & Launch Agent**.
4. The agent is immediately provisioned, mounted into the navigation drawer, and running live.

---

### Method 2: The Antigravity `create-agent` Skill
If you are developing inside Google Antigravity, activate the dedicated agent creation skill:
```text
/agent create smart_home
```
The skill uses the template workflow in `.gemini/antigravity/builtin/skills/create-agent/SKILL.md` to interactively generate compliant boilerplate, validate syntax, and run verification tests.

---

### Method 3: Command-Line Generator CLI
You can scaffold a production-ready agent in one command from the terminal:
```powershell
# Interactive generator prompt
python -m fleet.tools.create_agent

# Direct non-interactive generation
python -m fleet.tools.create_agent \
  --id "crypto_tracker" \
  --name "Crypto Portfolio" \
  --icon "📈" \
  --category "finance" \
  --permissions "network:outbound,db:read,db:write,ui:render" \
  --sync-interval 60
```

---

### Method 4: Manual Package Authoring (From Scratch)

#### Step 1: Create Directory Tree
```bash
mkdir -p fleet/agents/weather/ui
```

#### Step 2: Write `fleet/agents/weather/manifest.json`
```json
{
  "id": "weather",
  "name": "Local Weather",
  "version": "1.0.0",
  "icon": "☀️",
  "order": 55,
  "category": "productivity",
  "description": "Real-time meteorological conditions and temperature alerts.",
  "permissions": [
    "network:outbound",
    "db:read",
    "db:write",
    "ui:render"
  ]
}
```

#### Step 3: Implement `fleet/agents/weather/agent.py`
```python
"""
WeatherAgent — Local weather telemetry and morning forecast briefings.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import json

from fleet.core.base_agent import FleetAgent


class WeatherAgent(FleetAgent):
    def __init__(self, agent_dir: Optional[Path] = None, *args, **kwargs):
        super().__init__(agent_dir=agent_dir or Path(__file__).resolve().parent, *args, **kwargs)

    def initialize(self) -> bool:
        """One-time startup initialization and state recovery."""
        self.logger.info("Initializing WeatherAgent (%s)", self.id)
        return True

    def register_routes(self, router) -> None:
        """Exposes REST API endpoints mounted under /api/weather/*."""
        
        @router.get("/api/weather/current")
        def get_weather(handler: Any, parsed_url: urllib.parse.ParseResult):
            city = self.config.get("default_city", "San Francisco")
            # In a real agent, fetch from your local station or weather API
            payload = {
                "status": "success",
                "city": city,
                "temperature_c": 21.5,
                "humidity_pct": 65,
                "condition": "Partly Cloudy",
                "forecast": "Pleasant conditions continuing into the evening."
            }
            handler._send_json(payload)

        @router.post("/api/weather/refresh")
        def refresh_weather(handler: Any, body: Dict[str, Any]):
            city = body.get("city", self.config.get("default_city", "San Francisco"))
            self.db.log_activity("WeatherAgent", "refresh", f"Refreshed forecast for {city}")
            handler._send_json({"status": "success", "refreshed": True, "city": city})

    def execute_task(self, task_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoked by the background scheduler daemon."""
        if task_name == "hourly_poll":
            # Execute automated forecast check
            self.db.log_activity("WeatherAgent", "hourly_poll", "Checked atmospheric pressure")
            return {"status": "success", "polled": True}
        return {"status": "error", "error": f"Unknown task: {task_name}"}

    def shutdown(self) -> None:
        """Graceful shutdown hook for cleaning handles and flushing caches."""
        self.logger.info("WeatherAgent shutting down cleanly.")
```

#### Step 4: Implement `fleet/agents/weather/ui/panel.html`
```html
<div id="viewWeather" class="agent-dynamic-pane" style="display: none; flex-direction: column; gap: 16px;">
  <!-- Header Card -->
  <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px; backdrop-filter: blur(10px);">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h3 style="margin: 0; font-size: 18px; color: var(--text);">☀️ Local Weather Command</h3>
        <p style="margin: 4px 0 0 0; font-size: 12.5px; color: var(--text-muted);">
          Real-time microclimate conditions and barometric alerts.
        </p>
      </div>
      <button class="btn btn-sm btn-primary" onclick="fetchWeatherData(true)">🔄 Refresh</button>
    </div>
  </div>

  <!-- Telemetry Grid -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
    <div style="padding: 16px; background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); border-radius: 8px; text-align: center;">
      <div style="font-size: 11.5px; color: var(--text-muted);">Temperature</div>
      <div id="weatherTemp" style="font-size: 24px; font-weight: 700; color: var(--accent-cyan); margin-top: 4px;">--°C</div>
    </div>
    <div style="padding: 16px; background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); border-radius: 8px; text-align: center;">
      <div style="font-size: 11.5px; color: var(--text-muted);">Humidity</div>
      <div id="weatherHumidity" style="font-size: 24px; font-weight: 700; color: var(--accent-green); margin-top: 4px;">--%</div>
    </div>
    <div style="padding: 16px; background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); border-radius: 8px; text-align: center;">
      <div style="font-size: 11.5px; color: var(--text-muted);">Condition</div>
      <div id="weatherCondition" style="font-size: 16px; font-weight: 600; color: var(--text); margin-top: 8px;">Loading...</div>
    </div>
  </div>
</div>
```

#### Step 5: Implement `fleet/agents/weather/ui/script.js`
```javascript
async function fetchWeatherData(manual = false) {
  try {
    const res = await fetch('/api/weather/current');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    const tempEl = document.getElementById('weatherTemp');
    const humEl = document.getElementById('weatherHumidity');
    const condEl = document.getElementById('weatherCondition');
    
    if (tempEl) tempEl.textContent = `${data.temperature_c}°C`;
    if (humEl) humEl.textContent = `${data.humidity_pct}%`;
    if (condEl) condEl.textContent = data.condition;
    
    if (manual && typeof showSettingsToast === 'function') {
      showSettingsToast('Weather forecast updated', 'success');
    }
  } catch (err) {
    console.error('Failed to load weather:', err);
  }
}

// Auto-mount hook invoked by FleetNavigator when switching to this agent
window.mount_weather = function() {
  fetchWeatherData();
};
```

---

## 🧠 Writing Code that Passes Conscious Self-Critique

Every action return value is evaluated by the fleet's **Conscious Self-Critique Engine** (`SelfCritiqueEngine`). Follow these patterns to achieve 100/100 critique scores:

### ✅ Good Pattern (100/100 PASS)
```python
def handle_action(self, payload):
    # 1. Wrap return in dictionary with explicit 'status'
    # 2. Populate all requested keys with non-null, actionable data
    # 3. Handle errors transparently without contradiction
    return {
        "status": "success",
        "action": "query_inventory",
        "items_count": 42,
        "items": [...],
        "latency_ms": 1.2
    }
```

### ❌ Anti-Patterns (Will Trigger Critique Deficiencies)
```python
# Anti-pattern 1: Returning None or non-dict
def handle_bad_1(self):
    return None  # CRITIQUE: Output is not a valid structured dictionary (-40 pts)

# Anti-pattern 2: Contradictory status
def handle_bad_2(self):
    return {"status": "success", "error": "Disk full"}  # CRITIQUE: Contradictory state (-30 pts)

# Anti-pattern 3: Missing status
def handle_bad_3(self):
    return {"data": 123}  # CRITIQUE: Lacks explicit status property (-10 pts)
```

---

## 🧪 Testing Your Custom Agent

Create a dedicated unit test in `tests/test_weather_agent.py`:

```python
"""
Unit test for WeatherAgent verifying manifest contracts and route handlers.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
import urllib.parse

from fleet.agents.weather.agent import WeatherAgent
from fleet.api.router import DomainRouter


class TestWeatherAgent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.agent_dir = Path(self.temp_dir.name)
        self.agent = WeatherAgent(agent_dir=self.agent_dir, config={"default_city": "Tokyo"})
        self.router = DomainRouter()
        self.agent.register_routes(self.router)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agent_manifest_properties(self):
        self.assertEqual(self.agent.id, "weather")
        self.assertEqual(self.agent.name, "Local Weather")
        self.assertEqual(self.agent.config.get("default_city"), "Tokyo")

    def test_weather_current_route(self):
        handler = MagicMock()
        last_data = {}
        def mock_send_json(data, status=200):
            nonlocal last_data
            last_data = data
        handler._send_json = mock_send_json

        handled = self.router.dispatch_get(
            handler,
            "/api/weather/current",
            urllib.parse.urlparse("/api/weather/current")
        )
        self.assertTrue(handled)
        self.assertEqual(last_data.get("status"), "success")
        self.assertEqual(last_data.get("city"), "Tokyo")
        self.assertIn("temperature_c", last_data)


if __name__ == "__main__":
    unittest.main()
```

Run pytest to verify with zero socket leaks:
```powershell
python -m pytest tests/test_weather_agent.py -v
```

---

## 🧭 Managing 100+ Concurrent Agents with Fleet Navigator

Once your agent is deployed:
- **Instant Search**: Press `Ctrl+K` or `/` anywhere in the dashboard to open the **Spotlight Command Palette** and type your agent's name.
- **Drawer Browsing**: Open the **Fleet Navigator Drawer** from the left bar to categorize agents, view real-time CPU/memory states, and filter by working or idle states.
- **Pin to Bar**: Click `📌 Pin to Bar` on any agent to keep it permanently in the top navigation bar.
- **Settings Management**: Click `⚙️ Agent Settings` to modify your agent's schema properties without restarting the microkernel.
