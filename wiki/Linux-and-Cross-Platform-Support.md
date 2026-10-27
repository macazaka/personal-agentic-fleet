# Linux & Cross-Platform Support

The Personal Agentic Fleet provides **Tier 1 native support** across Linux distributions, macOS, and Windows.

---

## Supported Linux Distributions

| Distribution | Minimum Supported Version | Package Manager | Tested Init |
| :--- | :--- | :--- | :--- |
| **Ubuntu** | 20.04 LTS (Focal Fossa) + | `apt` | systemd |
| **Debian** | 11 (Bullseye) + | `apt` | systemd |
| **Fedora** | 38 + | `dnf` | systemd |
| **Arch Linux** | Rolling Release | `pacman` | systemd |

---

## Platform-Specific Bridges

### 1. Headless Display Drivers
On Linux servers or CI containers without a physical monitor, the microkernel detects missing `DISPLAY` and automatically sets:
```bash
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy
```

### 2. Native Desktop Notifications
- **Linux**: Uses `notify-send` (libnotify).
- **macOS**: Uses native AppleScript notifications (`display notification`).
- **Windows**: Uses Windows PowerShell Toast notifications.

### 3. Credential Vaults
- **Linux**: `secret-tool` (SecretService standard).
- **macOS**: `/usr/bin/security` (Keychain).
- **Windows**: DPAPI (`CryptProtectData`).

### 4. Background Daemon Services
- **Linux / systemd**: System service generator via `python -m fleet.tools.install_service --systemd`.
- **macOS / launchd**: LaunchAgent plist generator via `python -m fleet.tools.install_service --launchd`.
- **Windows**: Windows Task Scheduler integration via `start_fleet.bat`.
