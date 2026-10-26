# ⚡ Personal Agentic Fleet

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Security: 100/100 PASS](https://img.shields.io/badge/Security%20Audit-100%2F100%20%5B12%20Layers%5D-brightgreen.svg)](docs/SECURITY.md)
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)](docs/ARCHITECTURE.md)
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First%20DPAPI-teal.svg)](docs/SECURITY.md)
[![Hyperscalers](https://img.shields.io/badge/Hyperscalers-Google%20%7C%20Azure%20%7C%20AWS%20%7C%20Claude%20%7C%20Ollama-purple.svg)](docs/HYPERSCALERS_AND_DEV_TOOLS.md)
[![macOS: Universal](https://img.shields.io/badge/macOS-Apple%20Silicon%20%7C%20Intel-black.svg?logo=apple)](docs/PREREQUISITES_AND_OS.md)
[![Dev Tools](https://img.shields.io/badge/Dev%20Tools-Copilot%20%7C%20Claude%20Code%20%7C%20Gemini%20%7C%20Amazon%20Q-blueviolet.svg)](docs/HYPERSCALERS_AND_DEV_TOOLS.md)

> **An open-source, local-first agentic operating system with a plug-and-play microkernel architecture.**
> Run personal intelligence, metabolic & strength tracking, PC optimizations, and autonomous routines with **0 cloud token spend (`$0.00`)** and 100% deterministic local Python & SQLite execution.
> Plug in any frontier LLM across **Google Gemini, Microsoft Azure, AWS Bedrock (with native SigV4), Anthropic Claude, OpenAI, or local Ollama**, and bridge seamlessly with **GitHub Copilot, Claude Code, Gemini CLI, and Amazon Q Developer**.

---

## 📚 Comprehensive Documentation Library

| Documentation Guide | Scope & Key Technical Topics |
| :--- | :--- |
| 📖 **[Installation Guide (`INSTALL.md`)](INSTALL.md)** | Step-by-step setup, Python discovery, DPAPI secrets configuration, and background daemon startup. |
| 🏛️ **[System Architecture (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)** | Microkernel subsystems, deterministic event bus, Tier 0 engine, SQLite WAL persistence, and data flow. |
| 🛡️ **[Security Architecture (`docs/SECURITY.md`)](docs/SECURITY.md)** | 12-layer defense-in-depth model, Windows DPAPI at-rest encryption, threat model, SAST, and automated audits. |
| 🌐 **[Hyperscalers & Dev Tools (`docs/HYPERSCALERS_AND_DEV_TOOLS.md`)](docs/HYPERSCALERS_AND_DEV_TOOLS.md)** | Multi-provider LLM gateway, stdlib AWS SigV4, GitHub Copilot, Claude Code, Gemini CLI, and Amazon Q. |
| 💻 **[OS Prerequisites & Platform Matrix (`docs/PREREQUISITES_AND_OS.md`)](docs/PREREQUISITES_AND_OS.md)** | Detailed OS matrix: Windows 10/11 & macOS primary, Linux CI, unsupported OSes & hardware requirements. |
| 🔌 **[API & FastMCP Reference (`docs/API_REFERENCE.md`)](docs/API_REFERENCE.md)** | REST endpoints, FastMCP tool schemas, CLI commands, and Dashboard slash commands. |
| 🛠️ **[Developer & Contribution Guide (`docs/DEVELOPER_GUIDE.md`)](docs/DEVELOPER_GUIDE.md)** | Architecture rules, 3-step agent creation, adding hyperscalers, testing practices, and preflight gate. |
| 🎨 **[Agent Customization & Package Isolation (`docs/CUSTOMIZING_AGENTS.md`)](docs/CUSTOMIZING_AGENTS.md)** | Customizing any agent (name, icon, order, default tab, provider, model, prompt, panel) and building isolated private agents. |
| 🔄 **[Documentation Maintenance Guide (`docs/MAINTAINING_DOCUMENTATION.md`)](docs/MAINTAINING_DOCUMENTATION.md)** | Continuous documentation verification invariants, commit checklist, and update cadence. |
| 🛡️ **[Native Robustness Architecture Backlog (`docs/ROBUSTNESS_BACKLOG.md`)](docs/ROBUSTNESS_BACKLOG.md)** | 6-pillar framework robustness roadmap: thread supervisors, connection pool, OS job objects, circuit breakers, and crash forensics. |
| 🤝 **[Community Contributing Guide (`CONTRIBUTING.md`)](CONTRIBUTING.md)** | Branching workflow, pull request guidelines, security disclosure policy, and code style. |

---

## 💻 Operating System Support & Prerequisites

| Operating System | Compatibility Status | Native OS Capabilities Used |
| :--- | :--- | :--- |
| **Windows 11 (64-bit)** | 🟢 **Officially Supported (Primary)** | Native Win32 `Kernel32`/`PSAPI` (zero popup windows), at-rest **DPAPI `crypt32.dll`** hardware-bound encryption, WinRT Toast Notifications, NTFS User ACLs (`icacls`), and dual PowerShell 7 / 5.1 support. |
| **Windows 10 (64-bit, v1903+)** | 🟢 **Officially Supported (Primary)** | Full parity with Windows 11: in-process PSAPI memory enumeration, DPAPI crypto vault, WinRT toast alerts, and silent windowless background execution (`CREATE_NO_WINDOW`). |
| **macOS (12+ Monterey / Ventura / Sonoma / Sequoia on Apple Silicon & Intel)** | 🟢 **Officially Supported (Primary)** | Native AppleScript Notification Center alerts (`osascript`), hardware-backed **Apple Keychain Services** (`/usr/bin/security`), native `sysctl` (`hw.memsize`) & `vm_stat` memory telemetry, Directory Services DNS flush (`dscacheutil`), RAM cache purge (`purge`), LaunchAgents auto-start auditing, and Homebrew (`/opt/homebrew` & `/usr/local`) CLI discovery. |
| **Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch)** | 🟡 **Supported (Core Engine & CI)** | Continuous multi-version CI validation across Ubuntu Linux; standard POSIX permissions and process monitoring. |
| **Windows 7 / 8 / 8.1 / 32-bit (x86)** | 🔴 **Not Supported** | Missing modern WinRT notification subsystems, TLS 1.3 cryptographic cipher suites, and modern Python 3.10+ runtimes. Do not deploy on legacy Windows. |
| **Mobile / Android / iOS** | 🔴 **Not Supported** | Designed as a local workstation control center, not a mobile app. Access remotely via desktop browser over local LAN/VPN. |

For deep technical details on OS capability matrices and runtime requirements, refer to **[docs/PREREQUISITES_AND_OS.md](docs/PREREQUISITES_AND_OS.md)**.

### Minimum Hardware & Runtime Prerequisites
- **Python**: **Python 3.10+** (64-bit required; Python 3.11–3.14 recommended).
- **PowerShell**: **PowerShell 7+ (`pwsh`)** recommended; **Windows PowerShell 5.1** fully supported out-of-the-box.
- **Git**: Git 2.30+ with SSH commit signing support.
- **RAM**: 50 MB resident memory footprint (extremely lightweight microkernel).
- **Disk**: 150 MB disk space for database, logs, and cache.

---

## 🌟 Key Highlights

- **🔌 Modular Plug-and-Play Agents**: Every dashboard view is a standalone, self-contained agent package inside `fleet/agents/` with least-privilege capability manifests (`manifest.json`) enforced by `ScopedDatabaseProxy`.
- **💰 8-Layer Zero-Token & Cost Optimization Engine (`fleet/core/token_optimizer.py`)**:
  - **Tier 0 Natural-Language Intent Router & Offline BM25 Knowledge RAG**: Answers FFD diabetes reversal, nutrition, and 6-day workout questions locally in Python for **0 LLM tokens (`$0.00`)**.
  - **Fuzzy Jaccard + Trigram Semantic Cache**: Catches paraphrased repeat questions at 0 tokens.
  - **AST/Tokenize Code Minifier, Prompt Batch Coalescer, SHA-256 Image Deduplicator & Delta-Only MCP Cache**: Cuts LLM context window spend by 40%–70%.
- **🌐 Universal Hyperscaler Gateway & AI Developer Tools Bridge (`fleet/core/hyperscaler_gateway.py`)**:
  - Out-of-the-box support for **Google Gemini**, **Microsoft Azure OpenAI**, **AWS Bedrock** (via pure stdlib SigV4 signing — no boto3 bloat), **Anthropic Claude**, **OpenAI**, and **Local Ollama**.
  - CLI bridges and instruction synchronizers for **GitHub Copilot**, **Claude Code**, **Gemini CLI**, and **Amazon Q Developer**. See **[docs/HYPERSCALERS_AND_DEV_TOOLS.md](docs/HYPERSCALERS_AND_DEV_TOOLS.md)**.
- **⏰ Automated & Customizable Agent Scheduling Engine (`fleet/core/scheduler.py`, `schedules.yaml`)**:
  - Run agent tasks automatically at exact times of day (`time: "08:30"`, `times: ["08:30", "20:00"]`), recurring intervals (`interval_hours: 6`, `every: "2h"`), or standard 5-field cron syntax (`cron: "0 9 * * 1-5"`).
  - Ships with complete pre-configured default schedules for all 7 agents out of the box with zero third-party dependencies (pure-Python YAML parser & serializer in `fleet/core/yaml_helper.py`).
  - Real-time management via REST API (`/api/schedules`), MCP tools (`fleet_list_schedules`, `fleet_toggle_schedule`, `fleet_run_scheduled_task`), and the background routine daemon. See **[docs/CUSTOMIZING_AGENTS.md](docs/CUSTOMIZING_AGENTS.md)**.
- **🌿 Health & Wellness Command Center (Default Tab)**: Track metabolic reversal goals, hydration, daily prescriptions, a **6-Day Traditional Strength Split** (**Monday: Mudgal**, **Wednesday: Samtola**, **Friday: Bhim Gadha**, **Tue/Thu/Sat: Mandatory World's Best Warm-up & FFD Protocols**, **Sunday: Rest**), and stream local Exercise & Diet videos via HTTP 206 byte-range streaming with live HTML5 video thumbnails.
- **🚀 Silent PC Optimizer**: In-process Win32 PSAPI memory monitoring (`0` external `tasklist.exe` windows), dev-cache purging, temp cleanup, and DNS flushing.
- **🛡️ 12-Layer Automated Security & Privacy Scanner**: Runs automatically every **60 minutes** in the background daemon, on every **Git `pre-commit` & `pre-push`**, and daily via **GitHub Actions CI**, backed by native **Windows DPAPI (`crypt32.dll`) + HMAC-SHA256** at-rest encryption.

---

## 🚀 60-Second Installation & Quick Start

> For full setup instructions (Virtual Environments, Windows Credential Manager DPAPI secrets, silent background startup, and Antigravity MCP configuration), see **[INSTALL.md](INSTALL.md)**.

### 1. Verify Python >= 3.10 & Clone the Repository
```powershell
git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# Automated 1-Command Bootstrap (Discovers/provisions Python >=3.10, hardens Vault ACLs, installs Git hooks & launches)
.\bootstrap.ps1 -Launch
```

### 2. Configure Settings & Install Git Security Hooks
```powershell
# Copy the example configuration (fleet.yaml is git-ignored for your privacy)
Copy-Item fleet.yaml.example fleet.yaml

# Install automated 12-layer pre-commit & pre-push security hooks
python -m fleet.tools.install_git_hooks
```

### 3. Launch Fleet
```powershell
# Interactive foreground launch (Web Server + Background Routine Daemon)
python -m fleet.app
```
Or launch **silently in the background on Windows** (zero console windows):
```powershell
Start-Process -FilePath "pythonw.exe" -ArgumentList "-m", "fleet.server" -WindowStyle Hidden
Start-Process -FilePath "pythonw.exe" -ArgumentList "-m", "fleet.daemon" -WindowStyle Hidden
```
Open **[http://127.0.0.1:7890](http://127.0.0.1:7890)** in your browser!

---

## 🏗️ Architecture

```
personal-agentic-fleet/
├── docs/                       # COMPREHENSIVE DOCUMENTATION LIBRARY
│   ├── ARCHITECTURE.md         # Microkernel design, subsystems & event bus
│   ├── SECURITY.md             # 12-layer defense-in-depth & DPAPI vault
│   ├── HYPERSCALERS_AND_DEV_TOOLS.md # Google, Azure, AWS Bedrock, Claude & CLI tools
│   ├── PREREQUISITES_AND_OS.md # Platform support matrix & runtime requirements
│   ├── API_REFERENCE.md        # REST endpoints & FastMCP tool schemas
│   ├── DEVELOPER_GUIDE.md      # Contributor guidelines & agent development
│   └── MAINTAINING_DOCUMENTATION.md # Continuous doc integrity invariants
│
├── fleet/
│   ├── core/                   # MICROKERNEL & SECURITY ENGINE
│   │   ├── base_agent.py       # Base contract every plug-and-play agent implements
│   │   ├── registry.py         # Dynamic agent discoverer & route loader
│   │   ├── plugin_sandbox.py   # Least-privilege capability enforcement & env sanitizer
│   │   ├── crypto_vault.py     # Native Windows DPAPI + HMAC-SHA256 at-rest encryption
│   │   ├── session_auth.py     # DNS-Rebinding, CSRF, Session Cookie & Rate Limit guard
│   │   ├── token_optimizer.py  # 8-Layer Zero-Token RAG, Fuzzy Cache & Prompt Compressor
│   │   ├── hyperscaler_gateway.py # Universal multi-provider LLM gateway & SigV4
│   │   ├── dev_tools_bridge.py # CLI bridges for Copilot, Claude Code, Gemini & Amazon Q
│   │   ├── event_bus.py        # Deterministic inter-agent pub/sub bus
│   │   └── database.py         # SQLite persistence (WAL + PRAGMA secure_delete=ON)
│   │
│   ├── tools/                  # AUTOMATED SECURITY, CI & PREFLIGHT GATES
│   │   ├── security_scanner.py # 12-Layer Zero-Token Security & PII Scanner
│   │   ├── preflight_gate.py   # Preflight gate verifying Doctor, Security, Docs & Pytest
│   │   ├── sbom_generator.py   # CycloneDX v1.5 SHA-256 SBOM Generator
│   │   ├── install_git_hooks.py# Native Python pre-commit & pre-push hook installer
│   │   └── test_runner.py      # Isolated pytest & coverage runner
│   │
│   ├── agents/                 # PLUG-AND-PLAY AGENTS (Self-Contained)
│   │   ├── health/             # 🌿 Health, FFD reversal, 6-day strength & video vault
│   │   ├── overview/           # ⚡ Daily briefing, task board & habit routines
│   │   ├── optimizer/          # 🚀 Silent Win32 PC diagnostics & optimization
│   │   ├── antigravity/        # 🤖 Antigravity live mirror & token vault
│   │   ├── backlog/            # 📋 Kanban feature backlog & roadmap
│   │   └── gmail/              # 📬 5-folder deterministic email classifier
│   │
│   └── data/user/              # 🔒 GIT-IGNORED PRIVATE USER VAULT
│
├── INSTALL.md                  # Step-by-step installation & configuration guide
├── CONTRIBUTING.md             # Contributor workflow & security requirements
└── LICENSE                     # Apache 2.0 Commercial-Friendly Open-Source License
```

For full system diagrams and component breakdowns, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## 🛠️ Developing a New Agent in 3 Steps

Contributing a new capability requires **zero edits** to core files:

1. **Create an agent folder & `manifest.json`**: `fleet/agents/my_agent/manifest.json`
   ```json
   {
     "id": "my_agent",
     "name": "My Custom Agent",
     "version": "1.0.0",
     "icon": "✨",
     "permissions": ["db:read", "ui:render"]
   }
   ```
2. **Implement `fleet/agents/my_agent/agent.py`** subclassing `FleetAgent`.
3. **Add `fleet/agents/my_agent/ui/panel.html`** (`style.css` and `script.js` optional).

On startup, `AgentRegistry` validates your agent's permissions, registers its routes, and renders its tab automatically. See **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** and **[docs/AGENT_DEVELOPMENT_GUIDE.md](docs/AGENT_DEVELOPMENT_GUIDE.md)** for step-by-step guides.

---

## 🧪 Testing, Security & Documentation Verification

Run the complete local CI quality gate (`$0.00 / 0 tokens`), verifying Fleet Doctor, the 12-layer security scanner, documentation integrity, and the full unit test suite:
```powershell
python -m fleet.tools.preflight_gate
```

---

## 📜 License

Distributed under the **Apache License 2.0** (permissive commercial and open-source use with patent protection). See [`LICENSE`](LICENSE) for details.
Created and maintained by [**macazaka**](https://github.com/macazaka).
