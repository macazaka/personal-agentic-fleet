# 🎙️ UX-10: Ambient System Tray Companion, Global Hotkey (`Alt+Space`) & Voice Capture

| Attribute | Value |
| :--- | :--- |
| **Feature ID** | `UX-10` |
| **Priority** | 🟢 **P3 (Delight & Ambient UX Enhancement — Rank #10)** |
| **UX Impact Score** | **80 / 100** *(Impact: 32/40, Friction Reduction: 20/25, Zero-Token Leverage: 17/20, Speed: 11/15)* |
| **Category** | `Integration` & `UI/UX` |
| **Target Release** | `v3.1.0` |
| **Status** | `Idea` |
| **Affected Subsystems** | `fleet/app.py`, `fleet/tools/tray_companion.py`, `fleet/web/templates/dashboard.html` |

---

## 1. Executive Summary & User Problem Statement

### Current Friction
Even when the AFCC background daemon is running silently via `pythonw.exe` on port `7890`, interacting with the Fleet requires switching to a web browser window and finding the `127.0.0.1:7890` tab. If the user is in the middle of an IDE session, game, or document and wants to capture a quick task, log a glass of water, or check Cognitive Harmony, browser context-switching adds friction.

### Proposed UX Transformation
1. **Zero-Bloat Native OS System Tray Icon (`fleet/tools/tray_companion.py`)**:
   - Displays live Fleet health status in the Windows 11/10 System Tray / macOS Menu Bar / Linux Status Tray (`🟢 Harmony: 96% | 7 Agents Active`).
   - Right-click quick menu: `Open AFCC Dashboard`, `Log +1 Water Glass`, `Run RAM Optimizer`, `Trigger Morning Briefing`, `Pause Notifications (1h)`.
2. **Global Hotkey Mini-HUD (`Alt+Space` or `Ctrl+Shift+Space`) & Voice Quick-Capture**:
   - Summons a lightweight floating Quick-Capture bar anywhere on the desktop, supporting both keyboard Tier-0 commands and browser/OS native WebSpeech / offline speech-to-text voice commands (`"Add high priority task review architecture"`).

---

## 2. Acceptance Criteria & Verification Plan
- [ ] Optional `--tray` flag on `python -m fleet.app` launches the native OS tray icon without spawning any console window.
- [ ] Voice microphone button in the AFCC Omnibar (`UX-05`) transcribes spoken commands directly into the Tier-0 intent router at `$0.00` token cost.

