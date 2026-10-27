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
- **Windows**: Windows Task Scheduler / Service integration via `fleet.tools.install_service` or `bootstrap.ps1 -InstallService`.

---

## Windows OS Native Integration (Windows 10 / 11 64-bit)

Personal Agentic Fleet provides deep, seamless native integration with modern Windows workstations:

1. **Zero-Popup Win32 Architecture**:
   - In-process process and RAM telemetry through Win32 `Kernel32.dll` and `PSAPI.dll` (`GetProcessMemoryInfo`). No external command-line windows (`tasklist.exe` / `wmic.exe`) flicker or steal focus.
   - Background execution runs silently via `pythonw.exe` and `CREATE_NO_WINDOW (0x08000000)`.

2. **Hardware-Bound User DPAPI (`crypt32.dll`)**:
   - Secrets are secured via Windows Data Protection API bound to the user's active Windows credentials and TPM (`CRYPTPROTECT_UI_FORBIDDEN`). No unauthenticated user on the system can decrypt your vault.

3. **NTFS User ACL Hardening (`icacls`)**:
   - Automated inheritance stripping and DACL assignment (`(OI)(CI)(F)`) restricting `.vault` and configuration files exclusively to the user's Windows SID.

4. **Native Windows Action Center Toast Notifications**:
   - Delivers rich desktop toasts directly to the Windows Action Center via non-blocking PowerShell background tasks.

5. **Windows Job Objects Sandboxing**:
   - Worker agents run inside kernel Job Objects to enforce memory quotas and prevent rogue CPU spikes.

6. **Dual PowerShell Engine Support**:
   - Seamless cross-compatibility across PowerShell 7+ (`pwsh`) and Windows PowerShell 5.1 (`powershell.exe`).
