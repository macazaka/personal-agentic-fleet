# ⚡ Personal Agentic Fleet

[![Release: v2.6.0](https://img.shields.io/badge/Release-v2.6.0-00b4d8.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Security: 100/100 PASS](https://img.shields.io/badge/Security%20Audit-100%2F100%20%5B12%20Layers%5D-brightgreen.svg)](docs/SECURITY.md)
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)](docs/ARCHITECTURE.md)
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First%20DPAPI-teal.svg)](docs/SECURITY.md)
[![Hyperscalers](https://img.shields.io/badge/Hyperscalers-Google%20%7C%20Azure%20%7C%20AWS%20%7C%20Claude%20%7C%20Ollama-purple.svg)](docs/HYPERSCALERS_AND_DEV_TOOLS.md)
[![Windows: 10 / 11](https://img.shields.io/badge/Windows-10%20%7C%2011%20(64--bit)-0078D6.svg?logo=windows)](docs/PREREQUISITES_AND_OS.md)
[![macOS: Universal](https://img.shields.io/badge/macOS-Apple%20Silicon%20%7C%20Intel-black.svg?logo=apple)](docs/PREREQUISITES_AND_OS.md)
[![Linux: Native](https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch-orange.svg?logo=linux)](docs/PREREQUISITES_AND_OS.md)
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
| 🌐 **[Multi-OS Deployment & Scenarios (`docs/DEPLOYMENT_AND_SCENARIOS.md`)](docs/DEPLOYMENT_AND_SCENARIOS.md)** | Step-by-step setup across Windows, macOS, Linux, Docker containers, homelab, and real-world operational scenarios. |
| 🔌 **[API & FastMCP Reference (`docs/API_REFERENCE.md`)](docs/API_REFERENCE.md)** | REST endpoints, FastMCP tool schemas, CLI commands, and Dashboard slash commands. |
| 🛠️ **[Developer & Contribution Guide (`docs/DEVELOPER_GUIDE.md`)](docs/DEVELOPER_GUIDE.md)** | Architecture rules, agent creation, adding hyperscalers, testing practices, and preflight gate. |
| 🤖 **[Agent Development & Creation Guide (`docs/AGENT_DEVELOPMENT_GUIDE.md`)](docs/AGENT_DEVELOPMENT_GUIDE.md)** | Step-by-step agent creation via Wizard, `create-agent` Skill, CLI generator, manifest contracts, and self-critique loop. |
| 🛡️ **[Robustness Architecture & Operations Guide (`docs/ROBUSTNESS_GUIDE.md`)](docs/ROBUSTNESS_GUIDE.md)** | 7-pillar native robustness, Cognitive Mind layers, supervisors, connection pool, job objects, circuit breakers, and APIs. |
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
| **Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch)** | 🟢 **Officially Supported (Primary)** | First-class native Linux integration: systemd user units (`systemctl --user`), `resolvectl` DNS cache flush, FreeDesktop SecretService (`secret-tool` / libsecret) keyring encryption, `notify-send` (libnotify) / Zenity / KDialog desktop notifications, in-process `/proc` telemetry, XDG autostart, POSIX `RLIMIT_AS` memory containment, and POSIX `chmod 0700` vault hardening. Continuous 9-matrix verification across Python 3.10, 3.11, and 3.12. |
| **Windows 7 / 8 / 8.1 / 32-bit (x86)** | 🔴 **Not Supported** | Missing modern WinRT notification subsystems, TLS 1.3 cryptographic cipher suites, and modern Python 3.10+ runtimes. Do not deploy on legacy Windows. |
| **Mobile / Android / iOS** | 🔴 **Not Supported** | Designed as a local workstation control center, not a mobile app. Access remotely via desktop browser over local LAN/VPN. |

For deep technical details on OS capability matrices and runtime requirements, refer to **[docs/PREREQUISITES_AND_OS.md](docs/PREREQUISITES_AND_OS.md)**.

### 🪟 Windows OS Native Architecture & Capabilities (Windows 10 / 11)

Personal Agentic Fleet is engineered with first-class native Windows architecture and zero-friction enterprise integration:

1. **Zero-Flicker In-Process Win32 Subsystems**:
   - System telemetry and PC optimization query RAM and process metrics via direct Win32 `Kernel32.dll` and `PSAPI.dll` ctypes bindings (`GetProcessMemoryInfo`, `GlobalMemoryStatusEx`).
   - **Zero black console popups**: Background tasks, scheduled maintenance, and DNS sweeps never flash windows or steal focus during gaming, editing, or video calls. Background services execute silently via `pythonw.exe` and `CREATE_NO_WINDOW (0x08000000)`.

2. **Hardware-Tied Windows DPAPI Security (`crypt32.dll`)**:
   - Master keys, tokens, and private health records are encrypted at rest using the Windows Data Protection API bound to the active user's Windows security descriptor and TPM (`CRYPTPROTECT_UI_FORBIDDEN`).
   - Unauthenticated accounts or separate users on the same machine cannot decrypt vault secrets.

3. **NTFS User ACL Security Envelope (`icacls`)**:
   - Vault directories (`fleet/data/user/`) are automatically locked down to the current Windows user SID (`(OI)(CI)(F)`) with inheritance stripped from unprivileged accounts, preventing lateral privilege escalation.

4. **Native Windows Action Center Toast Notifications**:
   - Dispatches rich, interactive notifications to the Windows 10/11 Action Center for daily morning briefings, strength split workout prompts, and security alerts via non-blocking PowerShell background jobs.

5. **Windows Job Objects Quota Sandboxing**:
   - Worker agents run within Windows Job Objects (`CreateJobObjectW`, `SetInformationJobObject`) enforcing hard limits on peak memory footprint and thread priority, guaranteeing background agents never cause system lag.

6. **Dual PowerShell Engine Compatibility**:
   - Full out-of-the-box support for modern cross-platform **PowerShell 7+ (`pwsh`)** as well as legacy **Windows PowerShell 5.1** (`powershell.exe`) with seamless execution policy handling (`-ExecutionPolicy Bypass -Scope Process`).

7. **Windows Service & Task Scheduler Automation**:
   - Complete automated background persistence via `fleet.tools.install_service` and `bootstrap.ps1 -InstallService`, allowing Fleet to run seamlessly at user logon.

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
- **🏗️ 7-Pillar Native Robustness Architecture**: Erlang-style thread supervisor, Win32/POSIX signal traps, SQLite connection pooling with WAL checkpointing, automated point-in-time snapshots, OS resource quotas (Windows Job Objects & POSIX rlimits), socket egress gating, circuit breakers, rate limiting, and sleep/wake power state awareness. See **[docs/ROBUSTNESS_GUIDE.md](docs/ROBUSTNESS_GUIDE.md)** and **[docs/ROBUSTNESS_BACKLOG.md](docs/ROBUSTNESS_BACKLOG.md)**.
- **🧠 4-Layer Cognitive Fleet Mind (Brain, Consciousness, Subconsciousness, Soul)**:
  - **Layer 1: Brain (Physical & Neurological Substrate)**: Synaptic event bus impulse routing, dual working set RAM & epistemic SQLite memory, motor task schedules, and autonomic self-healing reflex arc.
  - **Layer 2: Consciousness (Executive Attention & Meta-Critique)**: Real-time focus window (`FOCUSED`, `AWARE`, `REFLECTING`) and deterministic multi-axial self-critique loop (`SelfCritiqueEngine`) validating action soundness, completeness, intent fidelity, and error transparency.
  - **Layer 3: Subconsciousness (Circadian Dreaming & Memory Consolidation)**: Background memory consolidation engine executing during sleep windows (23:00–06:00) to discover latent habit clusters, operational friction patterns, and immunological pruning.
  - **Layer 4: Soul (Teleological Purpose & Moral Compass)**: Inviolable ethical tenets (**Sovereign Privacy**, **$0.00 Token Frugality**, **Metabolic Care**, **Transparent Integrity**), soul alignment audits (`audit_alignment()`), and evolutionary generation ascent (`evolve_and_improve()`).
  - **Cognitive Harmony Index**: Quantitative 0–100 equilibrium metric with terminal introspection via `python -m fleet.tools.fleet_mind`.
- **🧭 100+ Agent Fleet Navigator & Spotlight Command Palette (`Ctrl+K` / `/`)**:
  - Designed for enterprise scale: manage dozens or hundreds of concurrent agents without UI clutter.
  - Off-canvas drawer with real-time fuzzy search, domain categories, state filtering (`Working`, `Idle`, `Disabled`), and 1-click pin-to-bar.
  - Spotlight Command Palette with keyboard shortcuts (`↑` / `↓` / `Enter`) for instant jumping between agents.
- **🪄 Visual Agent Creation Wizard & `create-agent` Skill Workflow**:
  - Click the **`+` icon** in the workstation header to launch an interactive 4-step wizard: Identity & Persona, Security Capabilities, Settings Schema, and One-Click Launch with live code preview.
  - Backed by the official `create-agent` skill in `.gemini/antigravity/builtin/skills/create-agent/` and CLI tool `fleet/tools/create_agent.py`.
- **🛠️ Proactive Log Scanner & Autonomous Self-Healing Engine (`fleet/core/auto_healer.py`)**:
  - Continuous proactive background analysis across application logs, ring buffers, error tails, and crash dumps.
  - Detects database contention, disk bloat, crash accumulations, rate limit backoffs, and task failure loops, executing automated zero-token self-healing actions.
- **🚀 Continuous GitHub Update Checks & Remote Agent Catalog**:
  - Checks GitHub releases on workstation startup and surfaces an update badge with desktop notifications when new versions appear.
  - Discover and download new community and official agents dynamically from the Discover & Download catalog.

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

### 3. Launch Fleet via Unified CLI or Python Module
```powershell
# Launch via Fleet CLI: fleet start (or python -m fleet start)
# Run status, diagnostics, security, or daemon:
#   fleet status       (live telemetry & Cognitive Harmony)
#   fleet agents list  (inspect all modular agents)
#   fleet doctor       (7-point environment audit)
#   fleet security     (12-layer security scanner)
#   fleet start -d     (silent background daemon)
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
