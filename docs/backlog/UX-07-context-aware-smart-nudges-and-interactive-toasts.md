# 🔔 UX-07: Focus-Aware Smart Nudges & Actionable Notification Cards

| Attribute | Value |
| :--- | :--- |
| **Feature ID** | `UX-07` |
| **Priority** | 🟡 **P2 (Medium-High UX Enhancement — Rank #7)** |
| **UX Impact Score** | **87 / 100** *(Impact: 34/40, Friction Reduction: 21/25, Zero-Token Leverage: 19/20, Speed: 13/15)* |
| **Category** | `UI/UX` & `Automation` |
| **Target Release** | `v3.0.0` |
| **Status** | `Planned` |
| **Affected Subsystems** | `fleet/core/notifier.py`, `fleet/core/scheduler.py`, `fleet/web/templates/dashboard.html` |

---

## 1. Executive Summary & User Problem Statement

### Current Friction
Scheduled agent notifications (hydration reminders, RAM alerts, inbox sweeps, habit check-ins) currently fire strictly on wall-clock schedule (`10:00`, `12:00`, `15:00`) as passive text toasts. This creates two UX issues:
1. If the user is in a deep coding flow, video call, or full-screen presentation, a popup toast is either distracting or ignored.
2. When a notification arrives (e.g., *"Time for your 12:00 hydration check"* or *"3 urgent emails in 01-Focus"*), the user cannot act on it with a single click (`[+1 Glass]`, `[Snooze 30m]`, `[Complete Routine]`) directly from the alert banner.

### Proposed UX Transformation
1. **Focus & Meeting-Aware Smart Delivery (`FocusGuard`)**:
   - In-process Win32 / macOS / Linux check detects if the user is in a full-screen application, video call (`Zoom`, `Teams`, `Meet`), or active `FOCUSED` executive state.
   - Non-critical nudges are automatically queued into a **Smart Nudge Digest** and delivered gracefully during the next transition window.
2. **Actionable 1-Click Notification Cards (SSE + Desktop)**:
   - Every agent notification can attach up to 3 **Quick Action Buttons** (`actions: [{"label": "✓ Log 250ml", "endpoint": "/api/health/hydration", ...}]`) rendered inside the AFCC Notification Center andSSE toast overlay.

---

## 2. Acceptance Criteria & Verification Plan
- [ ] `FleetAgent.execute_task()` return payloads support an `actions: List[Dict]` array that renders interactive 1-click buttons in AFCC toast alerts.
- [ ] Quiet Hours and Focus Mode automatically batch non-urgent notifications into an expandable badge counter in the AFCC header.

