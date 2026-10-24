# ⚡ Personal Agentic Fleet — Control Center

A high-performance, cost-optimized local multi-agent management system running on your Windows laptop, powered by **Google Antigravity**, **FastMCP**, and a **Deterministic In-Process Event Bus**.

---

## 🌟 Architecture & Key Features

### 1. 🔌 FastMCP Server (`fleet/mcp_server.py`)
- Implements the official **Model Context Protocol (MCP)** via `mcp.server.mcpserver`.
- Configured globally for Google Antigravity in `~/.gemini/config/mcp_config.json`.
- Exposes 8 single-hop tools to Antigravity:
  - `fleet_get_daily_briefing`: Morning greeting, priorities, and stats.
  - `fleet_add_task`: Add tasks (`🔴 P1`, `🟡 P2`, `🟢 P3`).
  - `fleet_list_tasks`: List open/completed tasks.
  - `fleet_complete_task`: Mark tasks as done.
  - `fleet_list_routines`: View today's habit checklist.
  - `fleet_toggle_routine`: Check/uncheck habits.
  - `fleet_send_notification`: Trigger native Windows desktop toast alerts.
  - `fleet_scan_directory`: Analyze folder disk space and file categories.

### 2. ⚡ Deterministic Event Bus (0-Token A2A) (`fleet/core/event_bus.py`)
- **Zero Token Overhead ($0.00)**: Internal Agent-to-Agent communication does not use wasteful natural-language chat loops.
- Routes typed `FleetEvent` message envelopes directly to local Python worker handlers (`AgendaWorker`, `FileWorker`, `NotificationWorker`).
- Automatically logs all agent events to SQLite `activity_logs`.

### 3. 🖥️ Standalone Local Web Dashboard (`fleet/server.py`)
- Clean browser dashboard on `http://127.0.0.1:7890`.
- Real-time task board, daily habits checklist, briefing card, and activity stream.
- Zero external pip requirements (runs on Python's built-in `http.server`).

### 4. 🔔 Proactive Background Daemon (`fleet/daemon.py`)
- Monitors daily routine times via the Event Bus.
- Fires native Windows Toast popups:
  - **08:30 AM**: Morning Briefing toast with open task count and P1 priorities.
  - **08:00 PM**: Evening Review reminder.

---

### 1. Launch Options (Independent of VS Code)

- **Option A: 1-Click Silent Background (Recommended)**
  Double-click `start_control_center.vbs` or `start_control_center.bat` in the project root.
  Runs silently in the background via `pythonw.exe` without keeping any terminal open. **Closing VS Code will not affect it!**
  
- **Option B: From Terminal / VS Code**
  ```powershell
  python -m fleet.app
  ```
  *(Note: closing VS Code terminates its integrated terminal processes).*

- **Option C: Automatic Launch on Laptop Boot (Auto-Start)**
  Double-click `enable_autostart.bat` (or run `powershell -File .\setup_autostart.ps1 -Action enable`).
  Places a silent shortcut in your Windows Startup folder (`shell:startup`). Whenever your laptop turns on or logs in, the Control Center and background daemon start automatically.
  To disable auto-start anytime, double-click `disable_autostart.bat`.

- **To Stop the Control Center**
  Double-click `stop_control_center.bat`.

### 2. Run Automated Verification Test
```powershell
python -m fleet.test_fleet
python -m fleet.test_gmail_classifier
```

### 3. Connect Live Gmail Account (OAuth 2.0)
```powershell
python -m fleet.setup_gmail
```
Follow the 3-minute prompts to place `credentials.json` into `fleet/data/credentials.json`. Once authenticated, it creates your 5 Fleet folders in Gmail and classifies this month & last month's emails automatically!

---

## 📁 Project Architecture

```
fleet/
├── app.py                  # Unified launcher (starts dashboard + background daemon)
├── mcp_server.py           # FastMCP stdio server exposing 8 tools to Antigravity
├── server.py               # Local web dashboard HTTP server & REST API
├── daemon.py               # Proactive background scheduler for Windows Toast alerts
├── test_fleet.py           # Automated test suite for Event Bus and MCP tools
├── config.py               # Schedule timings, paths, and cost governance policy
├── README.md               # Documentation and usage guide
├── core/
│   ├── event_bus.py        # Deterministic Event Bus for 0-token A2A messaging
│   ├── database.py         # SQLite storage for tasks, routines, memories, and logs
│   └── briefing.py         # Synthesis engine for morning briefings & statistics
├── tools/
│   └── system_tools.py     # Native Windows toast notifications and disk tools
└── data/
    └── fleet_memory.db     # 100% private local SQLite database
```

---

## 📜 Fleet Governance Rules

1. **Computational & Token Cost**: Strict Lowest Cost First (Deterministic code Tier 0 -> Single-hop MCP Tier 1 -> Context pruning Tier 2 -> Flash models Tier 3).
2. **Personal Life Decisions**: **User-Choice First**. For personal purchases, travel, tools, or lifestyle recommendations, the fleet presents balanced options across tiers and never forces the cheapest option.
