# ⚡ Personal Agentic Fleet

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Security: 100/100 PASS](https://img.shields.io/badge/Security%20Audit-100%2F100%20%5B11%20Layers%5D-brightgreen.svg)](docs/SECURITY_ARCHITECTURE_AND_ROADMAP.md)
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)]()
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First%20DPAPI-teal.svg)]()

> **An open-source, local-first agentic operating system with a plug-and-play microkernel architecture.**
> Run personal intelligence, metabolic & strength tracking, PC optimizations, and autonomous routines with **0 cloud token spend (`$0.00`)** and 100% deterministic local Python & SQLite execution.

📖 **[Complete Installation Guide (`INSTALL.md`)](INSTALL.md)** • 🛡️ **[Security Architecture & 11-Layer Scanner](docs/SECURITY_ARCHITECTURE_AND_ROADMAP.md)** • 🔌 **[Agent Development Guide](docs/AGENT_DEVELOPMENT_GUIDE.md)** • 🤝 **[Contributing Guide](CONTRIBUTING.md)**

---

## 🌟 Key Highlights

- **🔌 Modular Plug-and-Play Agents**: Every dashboard view is a standalone, self-contained agent package inside `fleet/agents/` with least-privilege capability manifests (`manifest.json`) enforced by `ScopedDatabaseProxy`.
- **💰 8-Layer Zero-Token & Cost Optimization Engine (`fleet/core/token_optimizer.py`)**:
  - **Tier 0 Natural-Language Intent Router & Offline BM25 Knowledge RAG**: Answers FFD diabetes reversal, nutrition, and 6-day workout questions locally in Python for **0 LLM tokens (`$0.00`)**.
  - **Fuzzy Jaccard + Trigram Semantic Cache**: Catches paraphrased repeat questions at 0 tokens.
  - **AST/Tokenize Code Minifier, Prompt Batch Coalescer, SHA-256 Image Deduplicator & Delta-Only MCP Cache**: Cuts LLM context window spend by 40%–70%.
- **🌿 Health & Wellness Command Center (Default Tab)**: Track metabolic reversal goals, hydration, daily prescriptions, a **6-Day Traditional Strength Split** (**Monday: Mudgal**, **Wednesday: Samtola**, **Friday: Bhim Gadha**, **Tue/Thu/Sat: Mandatory World's Best Warm-up & FFD Protocols**, **Sunday: Rest**), and stream local Exercise & Diet videos via HTTP 206 byte-range streaming with live HTML5 video thumbnails.
- **🚀 Silent PC Optimizer**: In-process Win32 PSAPI memory monitoring (`0` external `tasklist.exe` windows), dev-cache purging, temp cleanup, and DNS flushing.
- **🛡️ 11-Layer Automated Security & Privacy Scanner**: Runs automatically every **60 minutes** in the background daemon, on every **Git `pre-commit` & `pre-push`**, and daily via **GitHub Actions CI**, backed by native **Windows DPAPI (`crypt32.dll`) + HMAC-SHA256** at-rest encryption.

---

## 🚀 60-Second Installation & Quick Start

> For full setup instructions (Virtual Environments, Windows Credential Manager DPAPI secrets, silent background startup, and Antigravity MCP configuration), see **[INSTALL.md](INSTALL.md)**.

### 1. Verify Python >= 3.10 & Clone the Repository
```powershell
# Verify Python 3.10+ is installed
python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'; print('Python OK:', sys.version.split()[0])"

git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet
```

### 2. Configure Settings & Install Git Security Hooks
```powershell
# Copy the example configuration (fleet.yaml is git-ignored for your privacy)
Copy-Item fleet.yaml.example fleet.yaml

# Install automated 11-layer pre-commit & pre-push security hooks
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
├── fleet/
│   ├── core/                   # MICROKERNEL & SECURITY ENGINE
│   │   ├── base_agent.py       # Base contract every plug-and-play agent implements
│   │   ├── registry.py         # Dynamic agent discoverer & route loader
│   │   ├── plugin_sandbox.py   # Least-privilege capability enforcement & env sanitizer
│   │   ├── crypto_vault.py     # Native Windows DPAPI + HMAC-SHA256 at-rest encryption
│   │   ├── session_auth.py     # DNS-Rebinding, CSRF, Session Cookie & Rate Limit guard
│   │   ├── token_optimizer.py  # 8-Layer Zero-Token RAG, Fuzzy Cache & Prompt Compressor
│   │   ├── event_bus.py        # Deterministic inter-agent pub/sub bus
│   │   └── database.py         # SQLite persistence (WAL + PRAGMA secure_delete=ON)
│   │
│   ├── tools/                  # AUTOMATED SECURITY & DEVOPS TOOLS
│   │   ├── security_scanner.py # 11-Layer Zero-Token Security & PII Scanner
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

On startup, `AgentRegistry` validates your agent's permissions, registers its routes, and renders its tab automatically. See [`docs/AGENT_DEVELOPMENT_GUIDE.md`](docs/AGENT_DEVELOPMENT_GUIDE.md) for the full guide.

---

## 🧪 Testing & Security Verification

Run the automated test suite and 11-layer security audit locally (`$0.00 / 0 tokens`):
```powershell
python -m fleet.tools.security_scanner --strict
python -m pytest tests/ -v
```

---

## 📜 License

Distributed under the **Apache License 2.0** (permissive commercial and open-source use with patent protection). See [`LICENSE`](LICENSE) for details.
Created and maintained by [**macazaka**](https://github.com/macazaka).
