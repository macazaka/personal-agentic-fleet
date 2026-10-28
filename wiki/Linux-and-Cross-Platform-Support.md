# Linux & Cross-Platform Support

Personal Agentic Fleet provides **Tier 1 Native Support** across all three major personal computing platforms: **Windows 10/11 (64-bit)**, **macOS (Apple Silicon & Intel)**, and modern **Linux distributions** (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux).

---

## 1. Operating System Compatibility Matrix

| Platform / Distribution | Support Tier | Hardware Architecture | Native Integration Capabilities |
| :--- | :--- | :--- | :--- |
| **Windows 10 / 11** | **Tier 1** *(First-Class)* | 64-bit (x86_64, ARM64) | Win32 DPAPI (`crypt32`), PSAPI hardware telemetry, WinRT native toasts, NTFS `icacls` user-scoped hardening, PowerShell engine. |
| **macOS 12+ (Monterey+)** | **Tier 1** *(First-Class)* | Apple Silicon (M1/M2/M3/M4) & Intel | Apple Keychain Services, `sysctl`/`vm_stat` hardware metrics, AppleScript notification alerts, `LaunchAgents` background daemons. |
| **Ubuntu 20.04+ / Debian 11+** | **Tier 1** *(First-Class)* | 64-bit (x86_64, aarch64) | `systemd --user` units, `resolvectl` DNS cache flush, Secret Service API, `notify-send`, `/proc` telemetry, POSIX `0700` user vault. |
| **Fedora 38+ / RHEL 9+** | **Tier 1** *(First-Class)* | 64-bit (x86_64, aarch64) | Full systemd user integration, libsecret vault, SELinux compatible file permissions, native D-Bus notifications. |
| **Arch Linux / Manjaro** | **Tier 1** *(First-Class)* | 64-bit (x86_64) | Rolling-release Python runtime compatibility, native POSIX sandboxing, pacman/AUR environment isolation. |
| **Generic POSIX / FreeBSD** | **Tier 2** *(Standard)* | POSIX Compliant | Standard portable microkernel, POSIX `chmod 0700` vault, SQLite WAL persistence. |

---

## 2. Platform-Specific Native Integrations

### 2.1 Windows 10 & 11 (64-bit)
- **Cryptographic Security**: Uses Win32 Data Protection API (DPAPI) via `ctypes.windll.crypt32.CryptProtectData`, tying encryption keys directly to the logged-in Windows user account.
- **Hardware Telemetry**: Direct Win32 `psapi.dll` and `kernel32.dll` calls measure RAM working set size in microseconds without spawning subprocesses.
- **Process Management**: Uses `STARTUPINFO` and `CREATE_NO_WINDOW` flags to ensure background daemon and command-line scripts run completely hidden without flashing command prompt windows.
- **Filesystem Security**: Fleet Doctor verifies and applies user-scoped NTFS ACLs via `icacls`, stripping inheritance and restricting read/write access to the active user profile.

### 2.2 macOS (Apple Silicon & Intel)
- **Apple Keychain**: Credentials and master encryption keys are secured inside the macOS Keychain via the system `/usr/bin/security` subsystem.
- **Hardware Telemetry**: Reads memory pressure and CPU core loads via native `sysctl -n hw.memsize` and `vm_stat` page calculations.
- **Desktop Alerts**: Dispatches native macOS notification banners via `osascript -e 'display notification ...'`.
- **Daemon Management**: Can be registered as a persistent user service using `~/Library/LaunchAgents/com.fleet.daemon.plist`.

### 2.3 Linux (Ubuntu, Debian, Fedora, Arch)
- **Freedesktop Secret Service**: Interfaces with `secret-tool` and libsecret to store encryption keys in the desktop session keyring (GNOME Keyring / KWallet).
- **In-Process Telemetry**: Telemetry engine reads directly from `/proc/meminfo` and `/proc/stat`, executing in $< 0.1\text{ms}$ with zero child process overhead.
- **DNS Resolver Flushing**: Automatically detects `systemd-resolved` and flushes cache via `resolvectl flush-caches` during PC Optimizer operations.
- **Systemd User Units**: Fleet daemon runs smoothly as a systemd user service (`~/.config/systemd/user/fleet.service`).

---

## 3. Platform Detection Engine (`detect_os_compatibility`)

Fleet Doctor deterministically verifies the host operating system before executing sensitive operations:
```python
from fleet.tools.fleet_doctor import detect_os_compatibility

status = detect_os_compatibility()
print(f"OS: {status['os']} | Tier: {status['tier']} | Supported: {status['supported']}")
# Output on Ubuntu: OS: Ubuntu 24.04 LTS | Tier: Tier 1 | Supported: True
```

The detector parses `/etc/os-release` according to the FreeDesktop specification, inspects processor bitness (requiring 64-bit), and validates native library presence.
