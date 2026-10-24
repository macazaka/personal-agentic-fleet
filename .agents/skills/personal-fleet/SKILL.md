---
name: personal-fleet
description: >-
  Personal Agentic Fleet integration skill for Antigravity.
  Use to manage daily routines, retrieve morning briefings, query and create to-do tasks,
  and trigger Windows desktop notifications directly from Antigravity chat.
---

# Personal Agentic Fleet Skill

This skill connects Antigravity directly to the user's local **Personal Agentic Fleet** running on their Windows laptop.

## Core Capabilities
1. **Daily Briefing**: Synthesizes the user's high-priority tasks (P1), open goals, and habit completion stats.
2. **Task & Agenda Management**: Reads, adds, and marks tasks as completed in the local SQLite database (`fleet/data/fleet_memory.db`).
3. **Windows Desktop Alerts**: Sends native toast notifications to the user's laptop screen.

## Database Location & Operations
- Database: `fleet/data/fleet_memory.db`
- Python Module: `fleet.core.database.FleetDatabase`
- Briefing Module: `fleet.core.briefing.BriefingEngine`
- Notification Tool: `fleet.tools.system_tools.send_windows_notification(title, message)`

## Usage Examples

### 1. Adding a Task from Antigravity Chat
When the user asks to add or schedule a task, use Python:
```python
from fleet.core.database import FleetDatabase
db = FleetDatabase()
task_id = db.add_task(title="Prepare presentation", priority="P1", description="Final slides for Monday")
```

### 2. Fetching Today's Briefing
```python
from fleet.core.briefing import BriefingEngine
engine = BriefingEngine()
briefing = engine.generate_daily_briefing()
print(briefing["briefing_markdown"])
```

### 3. Firing a Native Windows Toast
```python
from fleet.tools.system_tools import send_windows_notification
send_windows_notification("Antigravity Reminder", "Time for your deep focus session!")
```

## Computational & Decision Guidelines
- **Zero-Token Operations**: Always use deterministic Python code and SQLite queries for adding tasks, toggling habits, calculating briefings, and formatting. Do not perform extraneous LLM roundtrips.
- **Minimal Context**: Load only what is needed (e.g. limit queries, top 3 priorities) to keep token counts minimal.
- **Personal Life Decisions**: Never default to or force the lowest-cost option for personal lifestyle, shopping, travel, or tools. Always present options with their tradeoffs (quality, features, convenience, price) and let the user decide.

