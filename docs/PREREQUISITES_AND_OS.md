# 💻 Operating System Support, Hardware & Software Prerequisites Manual

This document details the exact **Operating System Support Matrix**, **Designed OS Environments**, **Unsupported Environments**, and **Minimum Hardware & Software Prerequisites** for **Personal Agentic Fleet**.

---

## 1. Operating System Compatibility Matrix

| Operating System | Support Tier | Compatibility Status | Native OS Capabilities Used |
| :--- | :---: | :--- | :--- |
| **Windows 11 (64-bit)** | Tier 1 | 🟢 **Primary Target (Designed For)** | Hardware-bound **DPAPI (`crypt32.dll`)** at-rest encryption; in-process Win32 `Kernel32`/`PSAPI` memory telemetry (zero tasklist popup windows); native WinRT Toast Notifications; NTFS User ACLs (`icacls`); PowerShell 7.4+ and Windows PowerShell 5.1 dual-engine execution. |
| **Windows 10 (64-bit, v1903+)** | Tier 1 | 🟢 **Primary Target (Designed For)** | 100% feature parity with Windows 11: in-process PSAPI memory enumeration, DPAPI crypto vault, WinRT toast alerts, silent windowless background execution (`CREATE_NO_WINDOW`), and local user ACL isolation. |
| **Ubuntu Linux (20.04 LTS, 22.04 LTS, 24.04 LTS+)** | Tier 1 | 🟢 **Primary Target (Fully Supported Native)** | First-class native Linux integration: systemd user units (`systemctl --user`), `resolvectl` / `systemd-resolved` DNS cache purge, FreeDesktop SecretService (`secret-tool` / libsecret) keyring encryption, `notify-send` (libnotify) / Zenity / KDialog desktop notifications, in-process zero-subprocess `/proc/meminfo` and `/proc/<pid>/status` (`VmRSS`) telemetry, XDG autostart discovery (`~/.config/autostart`), POSIX `resource.setrlimit` (`RLIMIT_AS`) memory containment, and POSIX `chmod 0700` vault hardening. Continuous 9-matrix verification across Python 3.10, 3.11, and 3.12. |
| **Debian Linux (11 Bullseye, 12 Bookworm, Testing / Sid+)** | Tier 1 | 🟢 **Primary Target (Fully Supported Native)** | 100% feature parity with Ubuntu Linux: native systemd user services, `secret-tool` (libsecret-tools) vault credential storage, `resolvectl` DNS flushing, `/proc` memory diagnostics, and XDG desktop notifications. |
| **Fedora Linux (38, 39, 40, 41+)** | Tier 1 | 🟢 **Primary Target (Fully Supported Native)** | First-class modern systemd & SELinux-compatible execution: systemd user daemons, `resolvectl` DNS cache flush, `secret-tool` credential integration, native `/proc` memory introspection, and `notify-send` desktop alerts. |
| **Arch Linux (Rolling Release)** | Tier 1 | 🟢 **Primary Target (Fully Supported Native)** | Bleeding-edge Linux kernel and systemd integration: rolling Python 3.12+ execution, systemd user services, `libsecret` vault credentials, `resolvectl` DNS flushing, in-process `/proc` telemetry, and XDG autostart management. |
| **macOS (12+ Monterey, Ventura, Sonoma, Sequoia on Apple Silicon & Intel)** | Tier 1 | 🟢 **Primary Target (Fully Supported)** | Hardware-backed Apple **Keychain Services** via `/usr/bin/security`; native AppleScript Notification Center banners (`osascript`); native `sysctl` (`hw.memsize`) & `vm_stat` memory diagnostics; native Directory Services DNS cache flush (`dscacheutil`); RAM cache sweep (`purge`); LaunchAgents auto-start management; and Homebrew (`/opt/homebrew` & `/usr/local`) CLI discovery. |
| **Windows 7 / 8 / 8.1 (All Editions)** | — | 🔴 **NOT Supported (Do Not Deploy)** | **Incompatible.** Lacks modern TLS 1.3 cryptographic cipher suites, lacks WinRT toast notification manager, lacks modern PowerShell 7+ capabilities, and cannot run official Python 3.10+ releases. |
| **32-bit (x86) Operating Systems** | — | 🔴 **NOT Supported (Do Not Deploy)** | **Incompatible.** Fleet requires 64-bit address spaces for SQLite memory mapping, high-precision timer counters, and 64-bit Python runtimes. |
| **Mobile OS (Android, iOS, iPadOS)** | — | 🔴 **NOT Supported (Do Not Deploy)** | **Incompatible.** Fleet is an autonomous personal desktop daemon and microkernel, not a mobile application. Access the dashboard from mobile devices via local LAN browser at `http://<desktop-ip>:7890`. |

---

## 2. Deep Dive: What Personal Agentic Fleet is Designed For

### Windows 10 & Windows 11 (Primary Designed OS)
Personal Agentic Fleet was engineered from day one to deliver a seamless, unobtrusive experience on modern 64-bit Windows workstations:
- **Zero Popup Console Windows**: Fleet utilizes native Windows `CREATE_NO_WINDOW (0x08000000)` and `SW_HIDE` process flags. Background checks, DNS flushes, and daemon pulses never flash black console windows or steal focus from active games, code editors, or meetings.
- **Hardware-Bound User DPAPI (`crypt32.dll`)**: Secret API keys and private health logs are encrypted using Windows Data Protection API bound to your active Windows login credentials (`CRYPTPROTECT_UI_FORBIDDEN`). No unauthenticated user on the machine can decrypt your vault.
- **In-Process Win32 Memory Telemetry**: Rather than constantly spawning `tasklist.exe` (which spikes CPU and flickers windows), Fleet queries process WorkingSet sizes in-process via `CreateToolhelp32Snapshot`, `OpenProcess`, and `GetProcessMemoryInfo` (`psapi.dll`).
- **Native Toast Notifications**: Actionable notifications for morning briefings, token limit warnings, and security findings are delivered via Windows Action Center Toast Notifications.

### macOS (Apple Silicon M1/M2/M3/M4 & Intel 64-bit) (Primary Designed OS)
Personal Agentic Fleet delivers first-class native operating system integration on modern macOS workstations:
- **Native AppleScript Notification Center Alerts**: System reminders, morning briefings, and token limit warnings are dispatched directly to the macOS Notification Center via `osascript -e 'display notification ...'`.
- **Apple Keychain Services & Hardware-Backed Security**: Secret API keys and private tokens are protected transparently via macOS Keychain Services (`/usr/bin/security add-generic-password` and `find-generic-password`), backed by the Mac's hardware Secure Enclave and user login keychain.
- **Native Memory & Kernel Diagnostics**: Real-time memory pressure and usage are collected using native macOS `sysctl` (`hw.memsize`, `vm.pagesize`) and `vm_stat` page counters, avoiding heavy external tools.
- **Process Memory Diagnostics**: Processes and RSS are monitored using POSIX BSD `ps -A -o comm,rss` with in-memory Python sorting.
- **Native Cache Optimization & DNS Resolver Flush**: DNS resolution latency and stale directory records are purged using macOS `dscacheutil -flushcache` and `killall -HUP mDNSResponder`; memory cache sweeps invoke the native macOS `purge` command.
- **macOS Startup & Login Items**: Background daemons and auto-start applications are audited directly from `~/Library/LaunchAgents` and `/Library/LaunchAgents`, with one-click access to macOS System Settings (`x-apple.systempreferences:com.apple.LoginItems-Settings.extension`).
- **Apple Silicon & Homebrew CLI Auto-Discovery**: Automatic path resolution detects Developer CLIs across `/opt/homebrew/bin` (Apple Silicon M-series) and `/usr/local/bin` (Intel) for `agy`, `gh`, `claude`, `gemini`, `aws`, `ollama`, and `/Applications/Visual Studio Code.app`.

### Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux) (Primary Designed OS)
Personal Agentic Fleet delivers first-class native operating system integration on modern Linux workstations:
- **Systemd User Daemon Service**: Daemon autostart managed cleanly per-user via `fleet/tools/install_service.py` (`systemctl --user enable --now fleet.service`), requiring zero root/sudo privileges and restarting automatically upon system boot or crashes.
- **Hardware & SecretService Keyring Storage**: Secure credentials stored via FreeDesktop SecretService API using `secret-tool` (libsecret), keeping master encryption keys and tokens protected by the user's desktop login keyring (GNOME Keyring / KeePassXC / KWallet).
- **In-Process Kernel Telemetry (`/proc`)**: Zero child processes spawned for memory monitoring: RAM status parsed directly from `/proc/meminfo` (`MemTotal`, `MemAvailable`), and per-process memory measured via `/proc/<pid>/status` (`VmRSS`), preserving CPU cycles and avoiding tasklist spawning.
- **Native Desktop Notifications**: Banners dispatched via standard freedesktop `notify-send` (libnotify), with automatic fallback to GNOME `zenity` or KDE `kdialog` across desktop environments (GNOME, KDE Plasma, XFCE, Cinnamon, MATE) and tiling window managers (i3, Sway, Hyprland).
- **DNS Resolver Cache Purge**: Deterministic DNS cache purging via `resolvectl flush-caches` (with automatic fallback to `systemd-resolve --flush-caches`).
- **POSIX Resource Quota Sandbox (`RLIMIT_AS`)**: Agent processes bounded by POSIX `resource.setrlimit(resource.RLIMIT_AS, ...)` virtual address space ceilings.
- **XDG Autostart & Service Auditing**: Desktop startup items audited across `~/.config/autostart/*.desktop`, `/etc/xdg/autostart/*.desktop`, and `~/.config/systemd/user/*.service`.
- **Filesystem Hardening**: User data vault protected with POSIX `chmod 0700` (`rwx------`) ensuring only the owner UID can access runtime state, tokens, and logs.

---

## 3. Deep Dive: What Fleet is NOT Designed For & Technical Rationale

1. **Legacy Windows (Windows 7, 8, 8.1, Windows XP)**:
   - **Python Deprecation**: The Python core team dropped support for Windows 7/8 in Python 3.9. Python 3.10+ binaries fail to launch with `api-ms-win-core-path-l1-1-0.dll missing`.
   - **TLS 1.3 Absence**: Legacy Windows Schannel stacks lack modern TLS 1.3 cipher suites, exposing connections to cryptographic downgrade attacks.
   - **Missing WinRT Toast Subsystem**: Modern toast notifications (`[Windows.UI.Notifications.ToastNotificationManager]`) do not exist on Windows 7.
2. **32-Bit (x86) Architectures**:
   - 32-bit process spaces are capped at 2 GB virtual address space per process, which leads to memory exhaustion when loading large local vector indices, SBOMs, or handling concurrent video byte-range streams.
3. **Mobile & Sandboxed Operating Systems (iOS, Android, ChromeOS)**:
   - Mobile operating systems aggressively kill background Python processes within 30–60 seconds, preventing the `FleetDaemon` from maintaining scheduled briefings, 2-hour email pulses, or background security scans.

---

## 4. Minimum Hardware & Software Prerequisites

### Hardware Prerequisites
- **Architecture**: 64-bit (x86_64, amd64, or ARM64).
- **RAM**: Minimum **512 MB available RAM** (Fleet microkernel consumes `< 50 MB` resident memory).
- **Disk Space**: Minimum **150 MB free disk space** for SQLite database, logs, and cache (additional storage required if hosting large local exercise MP4 video libraries).
- **Network**: Localhost loopback interface (`127.0.0.1`); optional Internet connection for external hyperscaler APIs (Google, Microsoft, AWS, Anthropic, OpenAI) and Gmail OAuth.

### Software Prerequisites

| Component | Minimum Version | Recommended Version | Verification Command |
| :--- | :--- | :--- | :--- |
| **Python** | **Python 3.10+** (64-bit) | **Python 3.11 – 3.14** | `python --version` |
| **PowerShell** | Windows PowerShell 5.1 | **PowerShell 7.4+ (`pwsh`)** | `pwsh --version` or `$PSVersionTable.PSVersion` |
| **Git** | Git 2.30+ | Git 2.45+ with SSH signing | `git --version` |
| **Web Browser** | Any modern Evergreen browser | Chrome, Edge, Firefox, Brave | Used to access `http://127.0.0.1:7890` |

---

## 5. Self-Bootstrapping & Automated Environment Verification

You can verify your environment in 5 seconds using Fleet's automated self-diagnostic tools:

### Automated Preflight Invariants Check
```powershell
# Verifies Python >= 3.10, SQLite, OpenSSL TLS 1.3, Git hooks, and Vault ACLs
python -m fleet.tools.fleet_doctor
```

### Automated 1-Command Bootstrap (Windows)
```powershell
# Automatically provisions Python 3.12 if missing, hardens Vault ACLs, installs hooks & launches
.\bootstrap.ps1 -Launch
```

### Automated 1-Command Bootstrap (macOS / Linux)
```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

---

## 6. Comprehensive Deployment Guides & Real-World Scenarios

For complete, step-by-step deployment manuals and operational scenarios across all platforms:
- **Windows 11 & Windows 10 (64-bit)**: Automated bootstrap, silent background VBS execution, Task Scheduler autostart, and WSL2 interoperability.
- **macOS (Apple Silicon & Intel)**: Homebrew setup, Apple Keychain integration, LaunchAgents background service, and Notification Center permissions.
- **Linux & Headless Homelab**: Systemd user service, Ubuntu Server / Raspberry Pi, and headless daemon operation.
- **Containerized Environments**: Official Docker images (`ghcr.io/macazaka/personal-agentic-fleet`), Docker Compose, and rootless Podman.
- **Operational Scenarios**: Zero-token offline mode, multi-hyperscaler cloud gateway, AI developer tools bridge, athletic strength training splits, automated YAML scheduling, FastMCP tools, and secure Tailscale VPN access.

👉 See **[docs/DEPLOYMENT_AND_SCENARIOS.md](DEPLOYMENT_AND_SCENARIOS.md)** for the complete multi-OS deployment and scenario runbook.
