# 🖥️ Agentic Fleet Control Center (AFCC) & UI Architecture Deep-Dive

> **Release Version**: `v2.21.0` | **Templates & Assets**: `fleet/web/templates/dashboard.html`, `fleet/agents/<agent_id>/ui/panel.html` | **Default Endpoint**: `http://127.0.0.1:7890`

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

### 4.2 Unified "Ask Fleet Anything" Omnibar (`Ctrl+K` / `/`, `UX-05`)
- Instant keyboard-first launcher and cross-agent dispatcher (`fleet/core/omnibar_dispatcher.py`, `POST /api/omnibar/execute`):
  - **Agent Switching**: Jump to any agent in `< 30ms` (`Enter`).
  - **1-Click Omnibar Quick Pills**:
    - `🕵️ @discover`: Runs the Autonomous Process Discovery Engine (`UX-02`) and renders inline 1-click **🚀 Spawn Agent** cards.
    - `🔗 Run Morning Playbook`: Executes `@playbook pb_morning_vitality` (`UX-03`) across Health, Optimizer, Gmail, and Overview.
    - `💧 +2 Glasses Water`: Logs `@health water +2` directly to SQLite without switching tabs (`UX-05`).
    - `✨ Zero-Code Studio`: Opens the Natural-Language Agent Studio (`UX-01`).
  - **Direct `@agent` Slash Commands & Tier 0 Execution**: Type `@studio <description>`, `@playbook <id>`, `@<agent_id> <task>`, or natural-language queries to execute zero-token actions inline.

---

## 5. Zero-Code Agent Studio (`UX-01`) & Interactive 4-Step Visual Creation Wizard (`+` Header Button)

Clicking the **`+` Create Agent** button in the AFCC header opens the interactive 4-step modal wizard powered by `fleet/core/agent_studio.py`:
0. **✨ Zero-Code Plain-English Synthesizer Bar (`UX-01`)**: Describe your agent in 1 sentence (e.g., *"Check my local git repos every evening at 6 PM and alert me if uncommitted changes exist"*) and click **✨ Auto-Fill Wizard** (`POST /api/studio/synthesize`) to auto-populate all 4 steps in `< 5ms` at `$0.00` token cost.
1. **Step 1 — Identity & Persona**: Configure `agent_id` (`^[a-z][a-z0-9_]{1,30}$`), display name, emoji icon, category, and system prompt persona.
2. **Step 2 — Capability Sandbox Permissions**: Select least-privilege permissions (`db:read`, `db:write`, `ui:render`, `event_bus:publish`, `network:outbound`, `system:diagnostics`) with live security explanations.
3. **Step 3 — Custom Settings Schema & 6 Declarative UI Widget Blocks**: Define typed configuration fields (`string`, `number`, `boolean`, `select`), schedule cadence, and pick from **6 Declarative UI Widget Blocks** (`alert_banner`, `kpi_row`, `quick_capture_bar`, `habit_checklist`, `history_table`, `status_timeline`).
4. **Step 4 — Live Code Preview & 1-Click Scaffold**: Previews generated `manifest.json`, `agent.py`, and `ui/panel.html` and scaffolds the package via `POST /api/settings/agents/create` with immediate hot-reload into AFCC.

---

## 6. J.A.R.V.I.S. Voice Cockpit (`v2.20.0`) — 10 Critical Performance Enhancements, Sequential Audio Queue & Conversational Topic Stack

1. **10 Critical Performance Enhancements (`[JV-01]`..`[JV-10]`)**:
   - **`[JV-01]` O(1) Frozenset Token Intersection (`_JARVIS_SINGLE_WORD_SET`) & Single Multi-Word Regex (`_JARVIS_MULTI_WORD_RE`)**: Cuts N-best ASR candidate scoring CPU time by `>96%`.
   - **`[JV-02]` 60s Memoized Wake-Word Setting & Compiled Regex Cache (`_get_compiled_wake_word_regex`)**: Eliminates per-turn SQLite wake-word reads and regex compilations.
   - **`[JV-03]` Pre-Compiled Speech Sanitizer Pipeline & Bounded 32-Entry LRU Cache (`_CLEAN_SPEECH_CACHE`)**: Pre-compiles all URL, account, currency, Markdown, emoji, and clause-boundary regexes at import time.
   - **`[JV-04]` Turn-Scoped SQLite Task List Coalescing (`_get_turn_cached_tasks`)**: Coalesces `db.list_tasks(limit=200)` within a `1.2s` turn window with immediate invalidation on task mutations.
   - **`[JV-05]` O(1) Canonical Voice Intent Fast-Path Hash Table (`_FAST_INTENT_CANONICAL_ALIASES`)**: Resolves top 30+ high-frequency phrases in O(1) before regex cascade evaluation.
   - **`[JV-06B]` Zero-Allocation Spectrum Canvas 32-Bit Signature Diffing & Offscreen Skip (`renderJarvisLiveSpectrumCanvas`)**: Skips `<canvas>` 2D repaints when hidden (`!canvas.offsetParent`) or when `_lastSpectrumSig` is unchanged.
   - **`[JV-07]` In-Memory Decrypted AES-256-GCM Voiceprint Cache (`_VOICEPRINT_MEM_CACHE`)**: Eliminates repeated decryption on `GET /api/voice/voiceprint` and `POST /api/voice/voiceprint/verify`.
   - **`[JV-08]` Single-Flight Voice Turn Deduplicator & `AbortController` (`_activeVoiceFetchController`)**: Prevents `<150ms` duplicate turn dispatches and aborts superseded in-flight requests.
   - **`[JV-09]` Non-Blocking `requestAnimationFrame` Post-Speech DOM Batching**: Defers visual badge and chat DOM updates until after `SpeechSynthesis` audio starts.
   - **`[JV-10]` Stale-While-Revalidate (SWR) Non-Blocking Background RSS News Refresh**: Serves cached news/Pune headlines in `0.05ms` while refreshing Google News RSS asynchronously on a background daemon thread.
2. **6 High/Medium/Low Feature Enhancements (`[JV-11]`..`[JV-16]`)**:
   - **`[JV-11]` Conversational Voice Undo (`"Undo that"`, `"Scratch that"`)**: Reverses the last voice-triggered task completion, creation, rename, priority/note edit, or water log (`_LAST_VOICE_MUTATION_JOURNAL`).
   - **`[JV-12]` Spoken Time, Date, Day & Schedule Context (`"What time is it?"`, `"What day is today?"`)**: Speaks current time, date, day of week, today's FFD workout, and open action item count at `$0.00`.
   - **`[JV-13]` Interactive Voice Queue & Parked Topic Stack Verbal Inspector (`"What is in my voice queue?"`, `"Clear parked topics"`)**: Reads out or clears active and parked conversational topics.
   - **`[JV-14]` Indian Currency (`Rs` / `₹` / `lakh` / `crore`) Phonetic Normalizer**: Normalizes `Rs. 40,000` → `40,000 rupees` and `₹35 lakh` → `35 lakh rupees`.
   - **`[JV-15]` Whisper / Late-Night Quiet Voice Mode (`"Whisper mode on"`, `"Whisper mode off"`)**: Softens TTS volume (`0.45`) and cadence (`0.85x`).
   - **`[JV-16]` Real-Time Voice Performance & Cache Diagnostics (`GET /api/voice/diagnostics` & `"Voice diagnostics"`)**: Reports live O(1) cache hit/miss counters, LRU sizes, SWR status, and topic stack depth.
3. **Multi-Question Sequential Audio Queue & Human-Like Conversational Topic Stack (`#voiceQueueAndTopicStackBar`)**:
   - Decomposes multi-part utterances into priority-ordered `voice_queue_items` played sequentially via event-driven `utterance.onend` chaining (`playJarvisSequentialAudioQueue`) and automatically parks/resumes interrupted discussions (`_VOICE_TOPIC_STACK_STATE`).
