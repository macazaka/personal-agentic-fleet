# 📦 Personal Agentic Fleet — Complete Installation & Setup Guide

Welcome to **Personal Agentic Fleet**! Because the core microkernel, HTTP server, SQLite database, 11-layer security scanner, and 8-layer zero-token RAG engine are built using **100% Python Standard Library**, you can launch the dashboard in under **60 seconds** with zero mandatory pip dependencies, or install optional integrations (such as Windows Credential Manager `keyring`, Gmail OAuth, and `pytest` coverage).

---

## 📋 1. Prerequisites & Operating System Matrix

### Operating System Compatibility Matrix

| Operating System | Tier | Compatibility Details |
| :--- | :--- | :--- |
| **Windows 11 (64-bit)** | 🟢 **Primary Target** | Full native integration: in-process Win32 `PSAPI` memory telemetry, hardware-backed **DPAPI `crypt32.dll`** at-rest vault, WinRT toast notifications, NTFS user ACL hardening (`icacls`), and PowerShell 7 / 5.1 launcher. |
| **Windows 10 (64-bit, Build 18362+)** | 🟢 **Primary Target** | Identical feature parity to Windows 11: native DPAPI encryption, windowless background processes (`CREATE_NO_WINDOW`), WinRT notifications, and local user ACL isolation. |
| **macOS (12+ Monterey, Ventura, Sonoma, Sequoia on Apple Silicon & Intel)** | 🟢 **Primary Target (Fully Supported)** | Full native parity: Apple Keychain Services (`/usr/bin/security`) hardware vault, AppleScript Notification Center banners (`osascript`), `sysctl` & `vm_stat` memory pressure telemetry, Directory Services DNS flush (`dscacheutil`), RAM sweep (`purge`), LaunchAgents service management, and Homebrew CLI discovery. |
| **Linux (Ubuntu, Debian, Fedora, Arch)** | 🟡 **Core Supported / CI** | Core engine, CLI, and dashboard verified across Ubuntu in GitHub Actions CI matrix (Python 3.10, 3.11, 3.12). |
| **Windows 7 / 8 / 8.1 / 32-bit (x86)** | 🔴 **NOT Supported** | **Incompatible.** Missing TLS 1.3 cryptographic suites, modern Python `>=3.10` runtime support, WinRT toast notification subsystems, and NTFS security semantics. |
| **Mobile (iOS, Android, ChromeOS)** | 🔴 **NOT Supported** | **Incompatible.** Not built as a mobile app. The Control Center runs as a local PC daemon and can be accessed via local LAN browser. |

### Minimum Software & Hardware Prerequisites

| Requirement | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Architecture** | 64-bit (x86_64 / amd64 / arm64) | 64-bit x86_64 | 32-bit architectures are not supported. |
| **Python** | **Python 3.10+** | Python 3.11 – 3.14 | Enforced at startup by `check_minimum_python_version()` and PEP 621 `pyproject.toml`. |
| **PowerShell** | Windows PowerShell 5.1 | **PowerShell 7.4+ (`pwsh`)** | `start_fleet.bat` auto-detects PowerShell 7 and falls back to 5.1 seamlessly. |
| **Git** | Git 2.30+ | Git 2.40+ | Required for cloning, automated `pre-push` quality gates, and Ed25519 commit signing. |
| **Memory** | 512 MB available RAM | 2+ GB RAM | Microkernel runs in `< 50 MB` resident RAM. |
| **Disk Space** | 100 MB free space | 500 MB+ | For SQLite databases, logs, and optional local video streaming. |

Verify your environment and enforce the **minimum Python 3.10+ requirement** in PowerShell or Terminal:
```powershell
python --version
python -c "import sys; assert sys.version_info >= (3, 10), f'ERROR: Python 3.10+ is required (found {sys.version.split()[0]})'; print(f'OK: Python {sys.version.split()[0]} meets minimum requirement (>=3.10)')"
git --version
```
> **Note**: Personal Agentic Fleet also performs an automatic runtime check (`check_minimum_python_version()`) on startup and enforces `requires-python = ">=3.10"` in [`pyproject.toml`](pyproject.toml).

---

## ⚡ 2. 60-Second Quick Start (Automated Self-Bootstrap)

The repository includes **self-bootstrapping scripts** (`bootstrap.ps1` for Windows, `bootstrap.sh` for macOS/Linux, and `start_fleet.bat`) that automatically:
1. Locate a valid **Python `>= 3.10`** interpreter (or auto-provision Python 3.12 in user scope if missing).
2. Create your local `fleet.yaml` from `fleet.yaml.example`.
3. Harden OS filesystem ACL permissions (`icacls` on Windows / `chmod 0700` on POSIX) on your private `fleet/data/user/` vault.
4. Install the automated Git `pre-commit` & `pre-push` security hooks.
5. Run **Fleet Doctor** (`fleet_doctor.py`) and the **12-Layer Security Scanner** before launching the Fleet!

### Option A: Automated 1-Command Bootstrap & Launch (Recommended)
```powershell
git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# Windows (PowerShell): Verify/provision Python >= 3.10, harden security, and launch silently
.\bootstrap.ps1 -Launch
```
*(On macOS / Linux, run `chmod +x bootstrap.sh && ./bootstrap.sh`)*

### Option B: Manual Standard-Library Launch
```powershell
# 1. Clone the repository
git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# 2. Create your local configuration from the template
Copy-Item fleet.yaml.example fleet.yaml

# 3. Run Pre-Flight Doctor & Launch the Fleet Control Center
python -m fleet.tools.fleet_doctor
python -m fleet.app
```

Open **[http://127.0.0.1:7890](http://127.0.0.1:7890)** in your browser!

---

## 🛠️ 3. Full Installation (Virtual Environment & Optional Integrations)

If you want to use **Windows Credential Manager (`keyring`)**, **Live Gmail OAuth2 Classification**, **MCP Server integration**, or **Automated Unit Test & Coverage pulses**, set up a virtual environment:

### Windows (PowerShell)
```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install optional dependencies & test suite tools
pip install --upgrade pip
pip install -r requirements.txt
pip install keyring pytest coverage pyyaml
```

### macOS / Linux (Bash / Zsh)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install keyring pytest coverage pyyaml
```

---

## ⚙️ 4. Configuring Your Fleet (`fleet.yaml` / `fleet.json`)

Your local `fleet.yaml` (or `fleet.json`) is **git-ignored** so your personal paths and preferences are never committed to GitHub.

Edit `fleet.yaml`:
```yaml
server:
  host: "127.0.0.1"
  port: 7890
  default_agent: "health"       # Default tab opened on startup: 'health', 'overview', 'optimizer', 'antigravity', 'backlog'

agents:
  health:
    enabled: true
    videos_directory: "C:\\Users\\YourName\\Videos\\Workouts"  # Folder for local MP4/MKV/WebM workout & diet videos
    reminders_enabled: true

  overview:
    enabled: true

  optimizer:
    enabled: true
    scan_interval_hours: 6

  antigravity:
    enabled: true

  backlog:
    enabled: true

  gmail:
    enabled: false              # Set to true after placing client_secret.json in fleet/data/user/
    credentials_path: "fleet/data/user/client_secret.json"

security:
  scan_interval_minutes: 60     # Automatic 11-layer background security scan frequency
  block_commits_on_findings: true
  toast_alerts_on_findings: true
```

---

## 🔐 5. Secure Secret & Personal Data Setup (Zero Hardcoding)

Personal Agentic Fleet enforces a strict **Scoped User Vault** architecture:

### A. Private User Data Folder (`fleet/data/user/`)
All personal files belong inside `fleet/data/user/` (which is locked by `.gitignore` and verified by the 11-layer security scanner):
- `fleet/data/user/client_secret.json` — Google Cloud OAuth2 Desktop credentials (for optional Gmail Intelligence)
- `fleet/data/user/pii_blocklist.json` — Local list of personal names/identifiers that the security scanner blocks from ever appearing in git-tracked files
- `fleet/data/user/master.dpapi` — Auto-generated 256-bit master key encrypted by Windows OS Data Protection API (`crypt32.dll`)

### B. Storing API Keys in Windows Credential Manager (DPAPI)
Never paste API keys into source files. Store them in the **Windows OS Credential Vault** (encrypted via Windows DPAPI):
```powershell
python -c "from fleet.core.crypto_vault import set_secure_secret; set_secure_secret('GEMINI_API_KEY', 'YOUR_KEY_HERE')"
```
Or store them in a user-level Windows Environment Variable:
```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "YOUR_KEY_HERE", "User")
```

---

## 🖥️ 6. Running Silently in the Background on Windows

To run the Fleet Server and Routine Daemon silently in the background (using `pythonw.exe` with zero console windows and zero focus interruption):

### Option A: One-Click Batch Launcher
Double-click **`start_fleet.bat`** in the project root, or run from PowerShell:
```powershell
Start-Process -FilePath "pythonw.exe" -ArgumentList "-m", "fleet.server" -WindowStyle Hidden
Start-Process -FilePath "pythonw.exe" -ArgumentList "-m", "fleet.daemon" -WindowStyle Hidden
```

### Option B: Auto-Start on Windows Boot
1. Press **`Win + R`**, type `shell:startup`, and press **Enter**.
2. Right-click inside the Startup folder $\rightarrow$ **New** $\rightarrow$ **Shortcut**.
3. Point the shortcut to `<repo-path>\start_fleet.bat`.

---

## 🛡️ 7. Enabling Automated Git Security Hooks

Install the local Git `pre-commit` and `pre-push` security gates so every commit and push is automatically audited across all 11 security layers (`$0.00 / 0 LLM tokens`):

```powershell
python -m fleet.tools.install_git_hooks
```

Run an on-demand 11-layer security audit anytime:
```powershell
python -m fleet.tools.security_scanner --strict
```

Generate a cryptographic **CycloneDX v1.5 Software Bill of Materials (SBOM)**:
```powershell
python -m fleet.tools.sbom_generator
```

---

## 🤖 8. Connecting to Google Antigravity IDE (MCP Server)

Personal Agentic Fleet includes a built-in **Model Context Protocol (MCP)** server (`fleet/mcp_server.py`) that exposes 0-token tools (`fleet_get_daily_briefing`, `fleet_add_task`, `fleet_list_tasks`, `fleet_complete_task`, `fleet_list_routines`, `fleet_toggle_routine`, `fleet_send_notification`, `fleet_scan_directory`, `fleet_classify_recent_emails`).

Add the following entry to your Antigravity MCP configuration (`mcp_config.json`):
```json
{
  "mcpServers": {
    "personal-fleet": {
      "command": "python",
      "args": ["-m", "fleet.mcp_server"],
      "cwd": "C:/path/to/personal-agentic-fleet",
      "env": {
        "PYTHONPATH": "C:/path/to/personal-agentic-fleet"
      }
    }
  }
}
```

---

## 🧪 9. Running the Automated Test Suite

Run the full deterministic test suite (`100+` unit and security tests, `$0.00` token cost):
```powershell
python -m pytest tests/ -v
```

---

## ❓ 10. Troubleshooting

- **Port `7890` Already in Use**:
  Find and stop any existing process on port `7890` in PowerShell:
  ```powershell
  Get-NetTCPConnection -LocalPort 7890 | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
  ```
- **Workout Videos Not Showing in Video Vault**:
  Ensure `agents.health.videos_directory` in `fleet.yaml` points to an existing folder containing `.mp4`, `.mkv`, `.webm`, or `.mov` files.
- **PowerShell `Activate.ps1` Blocked by Execution Policy**:
  Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` in PowerShell.

---

## 🐳 11. Containerized Deployments (Docker, Docker Compose & Podman)

Personal Agentic Fleet publishes official, rootless multi-architecture container images to GitHub Container Registry (**GHCR**).

### 1-Command Docker Run
```bash
docker run -d \
  --name personal-fleet \
  --restart unless-stopped \
  -p 7890:7890 \
  -v $(pwd)/fleet-data:/app/fleet/data \
  ghcr.io/macazaka/personal-agentic-fleet:latest
```

### Docker Compose
```bash
# Clone the repository and launch via Docker Compose
docker compose up -d
```

---

## 📱 12. Remote LAN, Homelab & Mobile Access (Tailscale VPN)

Fleet runs locally on your workstation or headless home server, accessible securely across your local network:
1. Start with `$env:FLEET_HOST = "0.0.0.0"` (Windows) or `FLEET_HOST=0.0.0.0 python3 -m fleet.app` (macOS/Linux).
2. Access `http://<your-workstation-ip>:7890` from phone, iPad, or laptop on the same WiFi.
3. For encrypted access outside the home without opening router ports, connect via [Tailscale](https://tailscale.com) and navigate to `http://<tailscale-ip>:7890`.

👉 For comprehensive deployment guides across all operating systems and detailed operational scenarios, see **[docs/DEPLOYMENT_AND_SCENARIOS.md](docs/DEPLOYMENT_AND_SCENARIOS.md)**.
