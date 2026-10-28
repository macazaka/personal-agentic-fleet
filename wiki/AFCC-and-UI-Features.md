# 🖥️ Agentic Fleet Control Center (AFCC) & UI Architecture Deep-Dive

> **Release Version**: `v2.8.9` | **Templates & Assets**: `fleet/web/templates/dashboard.html`, `fleet/agents/<agent_id>/ui/panel.html` | **Default Endpoint**: `http://127.0.0.1:7890`

The **Agentic Fleet Control Center (AFCC)** is the local desktop web console for Personal Agentic Fleet. Engineered in zero-dependency HTML5, modern CSS Grid/Flexbox, and vanilla ES6+ JavaScript, AFCC renders in `< 10ms` from local disk and scales cleanly from 7 built-in agents to **100+ concurrent modular agents** with **zero horizontal scrollbars**, **strict DOM view scoping**, and **instant keyboard navigation**.

---

## 1. Core UI Engineering Invariants

1. **Zero External CDN / Framework Bloat**: No React, Webpack, or external font/script CDNs. AFCC works 100% offline in air-gapped environments while maintaining strict `Content-Security-Policy` headers.
2. **Strict Agent View Scoping (`switchTab` Isolation)**:
   - Every agent's UI resides strictly inside its own `fleet/agents/<agent_id>/ui/panel.html` root container (`<div id="viewHealth" class="tab-content active">`, `<div id="viewOverview" class="tab-content">`, etc.).
   - Sub-panes such as the **Exercise, Videos & Traditional Strength Training Hub** are nested strictly inside `#viewHealth` so they never bleed into Overview, Optimizer, Antigravity, Backlog, or Gmail tabs.
3. **Zero Horizontal Scrollbars Guarantee**:
   - Global CSS enforces `html, body { max-width: 100vw; overflow-x: hidden; }` and suppresses horizontal scrollbar tracks (`*::-webkit-scrollbar:horizontal { display: none !important; height: 0 !important; }`).
   - All navigation bars (including `.settings-nav-tabs` inside the Fleet Customizations & Settings modal) use `flex-wrap: wrap` rather than horizontal overflow scrolling.
4. **Proactive Pre-Commit HTML/CSS Diagnostic Gate**:
   - `fleet/tools/auto_fixer.py` (`audit_html_css_diagnostics()`) parses every `<style>` block and inline `style="..."` attribute across `dashboard.html` and `fleet/agents/*/ui/panel.html` on every commit, guaranteeing `0` VS Code `css-rparentexpected` or unclosed brace warnings.

---

## 2. The 6 Scalable Workspace Layouts (`setWorkspaceLayout`)

AFCC provides **6 adaptive layout modes** persisted in `fleet.yaml` (`layout`) and switchable instantaneously from the Header Layout Selector or **Settings → General & Automations**:

| Layout ID | Display Name | Ideal Scale | Structural Topology & UX Behavior |
| :--- | :--- | :---: | :--- |
| `sidebar_dock` *(Default)* | **Sidebar Dock** | `10 – 100+` agents | Left vertical collapsible navigation rail with category headers, live status dots, search filter, and full-width right workspace pane. |
| `command_deck` | **Command Deck** | `20 – 100+` agents | Top horizontal command bar featuring pinned core tabs + categorized dropdown matrix, maximizing vertical viewport height for dense tables and code diffs. |
| `launchpad_grid` | **Launchpad Grid** | `5 – 60` agents | macOS/iOS-style high-density card launchpad showing live telemetry summaries and 1-click jump cards for every installed agent. |
| `compact_tabs` | **Compact Pill Bar** | `5 – 15` agents | Single-row wrapping pill navigation bar with compact status badges and minimal header chrome. |
| `split_ops` | **Split Operations View** | `10 – 100+` agents | Dual-pane operational layout pairing the active agent workspace with a persistent live telemetry & event stream sidebar. |
| `zen_focus` | **Zen Focus Mode** | `Any` | Distraction-free single-agent canvas hiding secondary navigation rails; switch agents purely via Spotlight (`Ctrl+K` / `/`). |

---

## 3. The 6 Ergonomic Visual Themes (`applyTheme`)

AFCC ships with **6 WCAG-compliant visual themes** controlled via CSS Custom Properties (`--bg`, `--bg-card`, `--text`, `--accent`, `--border`) on `document.documentElement`:

| Theme ID | Theme Name | Primary Background | Surface Card | Primary Accent | Ergonomic Target |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `dark` *(Default)* | **Midnight Obsidian** | `#0b0f19` | `#111827` | `#06b6d4` *(Cyan)* | Low-glare dark mode for daily engineering & operations. |
| `light` | **Clean Daylight** | `#f8fafc` | `#ffffff` | `#0284c7` *(Ocean Blue)* | High-ambient daylight offices and print-ready reporting. |
| `aurora` | **Nordic Aurora** | `#061a14` | `#0d281e` | `#10b981` *(Emerald)* | Metabolic & health monitoring with calming green contrast. |
| `midnight` | **Deep AMOLED** | `#000000` | `#090d16` | `#a855f7` *(Electric Purple)* | Zero-backlight true black for OLED/AMOLED monitors. |
| `cyberpunk` | **Neon Synthwave** | `#0f0720` | `#1a0b36` | `#f43f5e` *(Neon Rose)* | High-contrast night operations and security monitoring. |
| `solarized` | **Solarized Slate** | `#002b36` | `#073642` | `#2aa198` *(Teal Cyan)* | Classic Ethan Schoonover low-eye-strain precision palette. |

---

## 4. 100+ Agent Fleet Navigator & Spotlight Command Palette (`Ctrl+K` / `/`)

### 4.1 Off-Canvas Fleet Navigator Drawer (`toggleAgentDrawer`)
- **Real-Time Fuzzy Filtering**: Filters 100+ agents by title, ID, category (`Core`, `Health`, `Productivity`, `System`, `DevOps`, `Custom`), or runtime state (`Working`, `Idle`, `Disabled`).
- **1-Click Pin-to-Bar**: Users can pin/unpin any agent to the primary navigation bar (`pinned_agents` persisted in `fleet.yaml`).

### 4.2 Spotlight Command Palette (`Ctrl+K` or `/`)
- Instant keyboard-first launcher supporting:
  - **Agent Switching**: Jump to any agent in `< 50ms` (`Enter`).
  - **Direct Operational Actions**: Trigger `Run 12-Layer Security Audit`, `Run Circadian Dream Cycle`, `Flush DNS & Optimize RAM`, `Open Agent Creation Wizard (+)`, or `Check GitHub Releases`.
  - **Tier 0 Natural-Language Execution**: Type commands directly into the command bar to execute zero-token intents.

---

## 5. Interactive 4-Step Visual Agent Creation Wizard (`+` Header Button)

Clicking the **`+` Create Agent** button in the AFCC header opens an interactive 4-step modal wizard:
1. **Step 1 — Identity & Persona**: Configure `agent_id` (`^[a-z][a-z0-9_]{1,30}$`), display name, emoji icon, category, and system prompt persona.
2. **Step 2 — Capability Sandbox Permissions**: Select least-privilege permissions (`db:read`, `db:write`, `ui:render`, `notifications:send`, `network:http`, `secrets:read`) with live security risk explanations.
3. **Step 3 — Custom Settings Schema**: Define typed configuration fields (`string`, `number`, `boolean`, `select`) that automatically render in the Settings modal.
4. **Step 4 — Live Code Preview & 1-Click Scaffold**: Previews generated `manifest.json`, `agent.py`, and `ui/panel.html` and scaffolds the package via `POST /api/agents/create` with immediate hot-reload into AFCC.
