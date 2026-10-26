# 💻 Operating System Support, Hardware & Software Prerequisites Manual

This document details the exact **Operating System Support Matrix**, **Designed OS Environments**, **Unsupported Environments**, and **Minimum Hardware & Software Prerequisites** for **Personal Agentic Fleet**.

---

## 1. Operating System Compatibility Matrix

| Operating System | Support Tier | Compatibility Status | Native OS Capabilities Used |
| :--- | :---: | :--- | :--- |
| **Windows 11 (64-bit)** | Tier 1 | 🟢 **Primary Target (Designed For)** | Hardware-bound **DPAPI (`crypt32.dll`)** at-rest encryption; in-process Win32 `Kernel32`/`PSAPI` memory telemetry (zero tasklist popup windows); native WinRT Toast Notifications; NTFS User ACLs (`icacls`); PowerShell 7.4+ and Windows PowerShell 5.1 dual-engine execution. |
| **Windows 10 (64-bit, v1903+)** | Tier 1 | 🟢 **Primary Target (Designed For)** | 100% feature parity with Windows 11: in-process PSAPI memory enumeration, DPAPI crypto vault, WinRT toast alerts, silent windowless background execution (`CREATE_NO_WINDOW`), and local user ACL isolation. |
| **Ubuntu Linux (20.04, 22.04, 24.04)** | Tier 2 | 🟢 **CI-Verified Cross-Platform** | Validated continuously across Python 3.10, 3.11, and 3.12 in GitHub Actions; standard POSIX `chmod 0700` user vault hardening; automated fallback for Windows-specific registry/audio calls. |
| **Debian / Fedora / Arch / RHEL** | Tier 2 | 🟢 **Supported Cross-Platform** | Same as Ubuntu Linux; standard POSIX microkernel execution, SQLite WAL mode, zero-token RAG, and Web Dashboard support. |
| **macOS (12+ Monterey, Ventura, Sonoma, Sequoia)** | Tier 2 | 🟡 **Core Engine Supported** | Microkernel, SQLite, 12-layer security scanner, zero-token RAG, and web dashboard run 100%; POSIX `chmod 0700` vault isolation; fallback notification and memory heuristics. |
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

### Linux & macOS (Cross-Platform Parity)
- While Windows offers hardware-bound DPAPI and Win32 PSAPI optimizations, all core business logic, SQLite WAL persistence, 12-layer security audits, zero-token intent routing, BM25 knowledge RAG, FastMCP server, and Web Dashboard are 100% portable Python Standard Library code verified on Linux and macOS.

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
