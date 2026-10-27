# Agent Development Guide

This guide details the complete process for designing, implementing, packaging, and testing agents in the Personal Agentic Fleet.

---

## The 4 Creation Pathways

Agents can be created through four distinct workflows:

1. **Visual UI Wizard**: Click the **`+`** icon in the dashboard header to launch the interactive 4-step wizard.
2. **Antigravity Skill**: Invoke the `/create-agent` skill in your Antigravity conversational session.
3. **Developer CLI Tool**: Run `python -m fleet.tools.create_agent --name "My Agent" --id my_agent`.
4. **Manual Package Development**: Create a self-contained package folder under `fleet/agents/<agent_id>/`.

---

## Agent Package Layout

Every agent lives in `fleet/agents/<agent_id>/` with strict package isolation:

```
fleet/agents/<agent_id>/
+-- __init__.py           # Package export exposing the Agent class
+-- agent.py              # Subclass of BaseAgent implementing execute()
+-- manifest.json         # Capability contract, metadata, and settings schema
+-- ui/
    +-- panel.html        # Glassmorphic dashboard widget markup
    +-- style.css         # Agent-specific CSS styling
    +-- script.js         # Frontend controller and DOM rendering logic
```

---

## Strict Manifest Contract (`manifest.json`)

The `manifest.json` defines identity, security permissions, and runtime settings:

```json
{
  "id": "weather_forecaster",
  "name": "Weather Forecaster",
  "version": "1.0.0",
  "description": "Local meteorological forecasts and outdoor fitness recommendations.",
  "category": "lifestyle",
  "icon": "cloud-sun",
  "permissions": [
    "network",
    "notifications",
    "diagnostics"
  ],
  "entrypoint": "agent.py:WeatherAgent",
  "custom_settings_schema": {
    "default_city": {
      "type": "string",
      "label": "Default City",
      "default": "San Francisco",
      "description": "Default city for automated morning briefings."
    },
    "units": {
      "type": "select",
      "label": "Temperature Units",
      "options": ["metric", "imperial"],
      "default": "metric"
    }
  }
}
```

---

## Implementing the Agent Class (`agent.py`)

Agents inherit from `BaseAgent` and implement `execute()`:

```python
from typing import Any, Dict
from fleet.core.base_agent import BaseAgent

class WeatherAgent(BaseAgent):
    def __init__(self, agent_id: str, manifest: Dict[str, Any]):
        super().__init__(agent_id=agent_id, manifest=manifest)

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        city = self.get_config("default_city", "San Francisco")
        units = self.get_config("units", "metric")
        
        # Pure deterministic Tier 0 processing ($0.00 compute)
        forecast = self._fetch_local_forecast(city, units)
        
        # Self-critique compliance check
        critique = self.evaluate_output(forecast)
        
        return {
            "status": "success",
            "data": forecast,
            "critique": critique
        }

    def evaluate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Conscious self-critique rubric compliance."""
        score = 95 if output.get("city") else 60
        return {
            "conscious_score": score,
            "soundness": "PASS",
            "token_waste": 0.0
        }
```

---

## Testing New Agents

All agent tests must execute without polluting production databases or activity feeds. Use `suppress_test_logs()`:

```python
from fleet.common.logging import suppress_test_logs

def test_weather_agent_execution():
    with suppress_test_logs():
        agent = WeatherAgent("weather_forecaster", manifest)
        res = agent.execute({"city": "Seattle"})
        assert res["status"] == "success"
        assert res["critique"]["conscious_score"] >= 85
```
