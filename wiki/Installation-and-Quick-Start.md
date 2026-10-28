# 🚀 Installation, Multi-OS Prerequisites & Quick Start Deep-Dive

> **Release Version**: `v2.10.0` | **Bootstrap Scripts**: `bootstrap.ps1`, `fleet.bat`, `fleet/tools/install_service.py`, `fleet/tools/install_git_hooks.py`

This guide provides complete, step-by-step installation, cryptographic vault initialization, and background service configuration instructions across **Windows 10/11 (64-bit)**, **macOS (12+ Apple Silicon & Intel)**, and **Linux (Ubuntu, Debian, Fedora, Arch)**.

---

## 1. Operating System Matrix & Native Subsystem Bindings

| Operating System | Support Tier | Cryptographic Vault Backend | Memory & Process Telemetry | Desktop Notifications | Background Service Persistence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Windows 11 / 10 (64-bit, v1903+)** | 🟢 **Tier 1 Primary** | Win32 **DPAPI (`crypt32.dll`)** (`CryptProtectData` + TPM user SID binding) + NTFS `icacls` `(OI)(CI)(F)` | In-process Win32 `Kernel32.dll` (`GlobalMemoryStatusEx`) & `PSAPI.dll` (`GetProcessMemoryInfo`) | WinRT `Windows.UI.Notifications` Action Center Toast | Windows Task Scheduler (`ONLOGON`) & `pythonw.exe` (`CREATE_NO_WINDOW`) |
| **macOS 12+ (Apple Silicon M1–M4 & Intel)** | 🟢 **Tier 1 Primary** | **Apple Keychain Services** (`/usr/bin/security add-generic-password`) + POSIX `0700` vault | Native `sysctl hw.memsize` & `vm_stat` page statistics | AppleScript Notification Center (`osascript -e 'display notification'`) | `~/Library/LaunchAgents/com.personal.agentic.fleet.plist` (`launchctl`) |
| **Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch)** | 🟢 **Tier 1 Primary** | **FreeDesktop SecretService** (`secret-tool` / `libsecret`) + PBKDF2-HMAC-SHA256 fallback + `chmod 0700` | Direct `/proc/meminfo` & `/proc/[pid]/statm` kernel procfs | `notify-send` (`libnotify`), `zenity`, or `kdialog` | `~/.config/systemd/user/personal-fleet.service` (`systemctl --user`) |

---

## 2. 60-Second Automated Bootstrap (Windows 10 / 11)

```powershell
# 1. Clone the repository
git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# 2. Run the 1-Command Automated Bootstrap
#    - Discovers/validates 64-bit Python >= 3.10
#    - Initializes fleet.yaml from fleet.yaml.example
#    - Hardens fleet/data/user/ NTFS ACLs via icacls
#    - Installs 12-layer pre-commit & pre-push Git hooks
#    - Launches the Agentic Fleet Control Center (AFCC) on http://127.0.0.1:7890
.\bootstrap.ps1 -Launch
```

### Silent Windowless Background Startup on Windows
To run Personal Agentic Fleet continuously in the background with **zero console windows**:
```powershell
# Register automatic startup at Windows logon
python -m fleet.tools.install_service

# Or launch immediately via pythonw.exe
Start-Process -FilePath "pythonw.exe" -ArgumentList "-m", "fleet.app", "--no-browser" -WindowStyle Hidden
```

---

## 3. macOS & Linux Installation

```bash
# 1. Clone and enter repository
git clone https://github.com/macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# 2. Create optional virtual environment & copy configuration
python3 -m venv .venv && source .venv/bin/activate
cp fleet.yaml.example fleet.yaml

# 3. Install Git security hooks & run Fleet Doctor
python3 -m fleet.tools.install_git_hooks
python3 -m fleet.tools.fleet_doctor

# 4. Start the Agentic Fleet Control Center (AFCC)
python3 -m fleet.app
```

---

## 4. Configuring Encrypted Hyperscaler Keys in the DPAPI / Keychain Vault

Never store plaintext API keys in tracked files. Store them via the **AFCC Settings Modal (`⚙️ -> AI & Providers`)** or via CLI/API:
```powershell
# Verify environment & vault status
python -m fleet.tools.fleet_doctor
```
All secrets are encrypted at rest inside `fleet/data/user/vault.enc` with an HMAC-SHA256 integrity seal.

