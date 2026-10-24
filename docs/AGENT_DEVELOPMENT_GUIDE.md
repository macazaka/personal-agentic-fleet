# Agent Development Guide

This guide walks you through building and publishing a custom agent for the **Personal Agentic Fleet**.

---

## 🏗️ The `FleetAgent` Anatomy

Every agent in Fleet is a Python package located in `fleet/agents/<agent_id>/` that inherits from `fleet.core.base_agent.FleetAgent`.

```text
fleet/agents/weather/
├── agent.py               # Core backend class
├── agent.yaml             # (Optional) Metadata specification
└── ui/
    ├── panel.html         # HTML pane injected into the dashboard
    ├── style.css          # (Optional) Agent-scoped styles
    └── script.js          # (Optional) Agent-scoped client interactivity
```

---

## 🚀 Step-by-Step Tutorial: Creating a Weather Agent

### Step 1: Create the directory
```bash
mkdir -p fleet/agents/weather/ui
```

### Step 2: Implement `fleet/agents/weather/agent.py`
```python
from typing import Any, Dict
from pathlib import Path
import urllib.request
import json

from fleet.core.base_agent import FleetAgent


class WeatherAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "weather"

    @property
    def name(self) -> str:
        return "Local Weather"

    @property
    def icon(self) -> str:
        return "☀️"

    @property
    def order(self) -> int:
        return 55

    def register_routes(self, router) -> None:
        """Register custom API endpoints."""
        @router.get("/api/weather/current")
        def get_weather(handler: Any, parsed_url: Any):
            city = self.config.get("default_city", "San Francisco")
            # Return weather data
            handler._send_json({
                "city": city,
                "temp_c": 22,
                "condition": "Sunny"
            })

    def register_tasks(self) -> list:
        """(Optional) Register background cron checks."""
        return [
            {
                "name": "weather_hourly_poll",
                "interval_seconds": 3600,
                "handler": lambda: print("Checking weather...")
            }
        ]
```

### Step 3: Implement `fleet/agents/weather/ui/panel.html`
```html
<div id="viewWeather" class="agent-dynamic-pane" style="display: none; flex-direction: column; gap: 16px;">
  <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 20px;">
    <h3>☀️ Local Weather</h3>
    <p>Live meteorological conditions and forecasts.</p>
    <div id="weatherDisplay">Loading weather data...</div>
  </div>
</div>
```

### Step 4: Implement `fleet/agents/weather/ui/script.js`
```javascript
async function fetchWeatherData() {
  try {
    const res = await fetch('/api/weather/current');
    const data = await res.json();
    const el = document.getElementById('weatherDisplay');
    if (el) {
      el.innerHTML = `<strong>${data.city}</strong>: ${data.temp_c}°C, ${data.condition}`;
    }
  } catch (e) {
    console.error('Weather load error:', e);
  }
}

// Automatically fetch on tab switch
window.addEventListener('DOMContentLoaded', fetchWeatherData);
```

---

## ⚙️ Configuration in `fleet.yaml`

Users configure your agent via `fleet.yaml`:
```yaml
agents:
  weather:
    enabled: true
    default_city: "Pune"
```
Within `agent.py`, access these settings via `self.config.get("default_city")`.

---

## 🧪 Testing Your Agent

Create `tests/test_weather_agent.py`:
```python
from fleet.agents.weather.agent import WeatherAgent
from pathlib import Path

def test_weather_agent_properties(tmp_path):
    agent = WeatherAgent(agent_dir=tmp_path, config={"default_city": "Tokyo"})
    assert agent.id == "weather"
    assert agent.name == "Local Weather"
    assert agent.icon == "☀️"
    assert agent.config["default_city"] == "Tokyo"
```

Run pytest:
```bash
python -m pytest tests/test_weather_agent.py
```
Your agent is now ready to ship!

