# ⚡ Personal Agentic Fleet

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 89 Passed](https://img.shields.io/badge/Tests-89%20Passed-brightgreen.svg)]()
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)]()
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First-teal.svg)]()

> **An open-source, local-first agentic operating system with a plug-and-play microkernel architecture.**
> Run personal intelligence, metabolic tracking, PC optimizations, and autonomous routines with **0 cloud token spend** and 100% deterministic local Python & SQLite execution.

---

## 🌟 Key Highlights

- **🔌 Modular Plug-and-Play Agents**: Every dashboard view is a standalone, self-contained agent package inside `fleet/agents/`. Adding or removing an agent requires **zero edits** to core code.
- **⚡ Zero-Token Deterministic Core**: Briefings, metric computations, disk cleanups, and video vault streaming run completely locally in Python and SQLite for **$0.00 / 0 LLM tokens**.
- **🌿 Health & Wellness Command Center**: Track metabolic goals, hydration, daily medication compliance, 6-day traditional Akhada strength splits (Mudgal, Samtola, Bhim Gadha), and stream local workout videos via HTTP 206 byte-range streaming with live frame thumbnails.
- **🚀 PC Optimizer**: Real-time RAM boosting, dev-cache cleaning (npm, pip, yarn, PyTorch), DNS flushing, and process monitoring.
- **🤖 Antigravity Live**: Live token telemetry, model router, and workspace mirror.
- **📋 Feature Backlog**: Kanban-style roadmap and task lifecycle management.
- **🛡️ 100% Privacy & Sanitized**: All personal databases, credentials, and uploaded files stay strictly local and ignored by Git.

---

## 🏗️ Architecture

Fleet uses an **asynchronous microkernel** with an event-driven plugin registry:

```
fleet/
├── core/                   # MICROKERNEL ENGINE
│   ├── base_agent.py       # Base class every agent implements
│   ├── registry.py         # Dynamic agent discoverer & loader
│   ├── event_bus.py        # Asynchronous inter-agent pub/sub
│   ├── server.py           # Robust HTTP server (standard library)
│   ├── database.py         # Scoped SQLite persistence
│   └── config.py           # fleet.yaml / fleet.json parser
│
├── web/                    # DYNAMIC DASHBOARD SHELL
│   ├── templates/          # Glassmorphism dynamic UI shell
│   └── static/             # Reusable CSS & JavaScript client
│
└── agents/                 # PLUG-AND-PLAY AGENTS (Self-Contained)
    ├── health/             # 🌿 Health, metabolic & strength agent
    ├── overview/           # ⚡ System vitals & daily briefing agent
    ├── optimizer/          # 🚀 PC cleanup & performance agent
    ├── antigravity/        # 🤖 Antigravity live mirror agent
    ├── backlog/            # 📋 Feature backlog & task board
    └── gmail/              # 📧 Email intelligence agent
```

---

## 🚀 Quickstart

### 1. Clone the Repository
```bash
git clone https://github.com/macazaka/fleet.git
cd fleet
```

### 2. Configure Settings (Optional)
Copy the example configuration:
```bash
cp fleet.yaml.example fleet.yaml
```
Enable or disable agents, or point to your local video library:
```yaml
server:
  port: 7890
  default_agent: "health"

agents:
  health:
    enabled: true
    videos_directory: "~/Videos/Workouts"
  optimizer:
    enabled: true
  backlog:
    enabled: true
```

### 3. Launch Fleet
```bash
python fleet/app.py
```
Open **[http://127.0.0.1:7890](http://127.0.0.1:7890)** in your browser!

---

## 🛠️ Developing a New Agent in 3 Steps

Contributing a new capability to Fleet requires zero changes to the core engine:

1. **Create an agent directory**: `fleet/agents/my_agent/`
2. **Implement `agent.py`**:
   ```python
   from fleet.core.base_agent import FleetAgent

   class MyAgent(FleetAgent):
       @property
       def id(self) -> str: return "my_agent"
       @property
       def name(self) -> str: return "My Custom Agent"
       @property
       def icon(self) -> str: return "✨"
       @property
       def order(self) -> int: return 70

       def register_routes(self, router):
           @router.get("/api/my_agent/status")
           def status(handler, parsed):
               handler._send_json({"status": "active"})
   ```
3. **Add `ui/panel.html`**:
   ```html
   <div id="viewMy_agent" class="agent-dynamic-pane" style="display: none;">
     <h3>✨ My Custom Agent</h3>
     <p>Your interactive dashboard UI goes here.</p>
   </div>
   ```

On launch, `AgentRegistry` discovers your agent, registers its routes, and renders its tab in the dashboard shell automatically. See [`docs/AGENT_DEVELOPMENT_GUIDE.md`](docs/AGENT_DEVELOPMENT_GUIDE.md) for full details.

---

## 🧪 Testing

Fleet has a 100% test pass rate with zero external mock services needed:
```bash
python -m pytest tests/
```
All **89 unit and integration tests** run deterministically in under 45 seconds.

---

## 🔒 Security & Privacy

- Fleet never transmits telemetry or personal analytics to third parties.
- Local SQLite databases (`*.db`), Google API credentials (`client_secret*.json`), tokens, and uploads are strictly `.gitignore`d.
- Contributors can safely push code without leaking private medical or machine configurations.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
Created by [**macazaka**](https://github.com/macazaka).
