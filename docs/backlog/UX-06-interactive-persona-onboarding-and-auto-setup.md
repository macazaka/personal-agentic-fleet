# 🧭 UX-06: Interactive First-Run Persona Onboarding & Goal-Driven Auto-Setup

| Attribute | Value |
| :--- | :--- |
| **Feature ID** | `UX-06` |
| **Priority** | 🟡 **P2 (Medium-High UX Enhancement — Rank #6)** |
| **UX Impact Score** | **89 / 100** *(Impact: 35/40, Friction Reduction: 22/25, Zero-Token Leverage: 18/20, Speed: 14/15)* |
| **Category** | `UI/UX` & `Core` |
| **Target Release** | `v3.0.0` |
| **Status** | `Planned` |
| **Affected Subsystems** | `fleet/web/templates/dashboard.html`, `fleet/api/settings_api.py`, `fleet/config.py`, `schedules.yaml` |

---

## 1. Executive Summary & User Problem Statement

### Current Friction
When a user launches Personal Agentic Fleet for the first time, all 7 built-in agents are active with default generic settings. However, different users have vastly different primary goals: one user may want a **Metabolic Health & Traditional Strength Coach**, another wants a **Software Engineering & Antigravity Command Center**, and another wants an **Executive Task & Inbox Zero Workstation**. Manually configuring layout, theme, default landing tab, hydration goals, and schedules across multiple modals takes several minutes.

### Proposed UX Transformation
Deliver a **60-Second Interactive Persona & Goal Onboarding Experience** (accessible on first run and anytime via **Settings → Re-run Guided Setup**):
1. **Step 1 — Choose Your Primary Personas (Multi-Select)**:
   - 🌿 *FFD Metabolic Reversal & Traditional Strength Athlete*
   - 💻 *AI-Assisted Software Engineer (Antigravity / Copilot / Claude Code)*
   - ⚡ *Executive Productivity & Inbox Zero Operator*
   - 🚀 *PC Performance, Gaming & Homelab Enthusiast*
2. **Step 2 — Set Your Daily Rhythm**:
   - Wake/Morning Briefing time (e.g. `07:30`), Deep Work hours, Evening Wrap-up time (`21:00`), and Daily Water Target (`3.5L`).
3. **Step 3 — Pick Visual Ergonomics**:
   - Live interactive preview of the 6 Layouts (`sidebar_dock`, `command_deck`, `launchpad_grid`, etc.) and 6 Themes (`dark`, `aurora`, `midnight`, etc.).
4. **Step 4 — Instant Auto-Configuration**:
   - Automatically writes `fleet.yaml` and `schedules.yaml`, pins the highest-priority agents, sets the default landing tab, and seeds starter tasks/habits tailored to the chosen personas.

---

## 2. Acceptance Criteria & Verification Plan
- [ ] `POST /api/settings/onboarding` applies a complete persona bundle atomically to `fleet.yaml`, `schedules.yaml`, and SQLite `routines`.
- [ ] Zero network or cloud token usage (`$0.00`); completable in under 60 seconds.

