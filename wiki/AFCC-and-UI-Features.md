# Agentic Fleet Control Center (AFCC) & UI Features

The **Agentic Fleet Control Center (AFCC)** is the central management web console for Personal Agentic Fleet. Accessible by default at `http://127.0.0.1:7890`, AFCC delivers a high-density, zero-latency desktop operations environment designed to scale effortlessly from a handful of local agents to **100+ concurrent agents** without clutter, horizontal scrollbars, or duplicate data.

---

## 1. Architectural Design Principles

AFCC is engineered around five fundamental UX and engineering invariants:
1. **Zero External Dependencies**: Pure vanilla modern HTML5, ES6 JavaScript, and responsive CSS with zero CDN scripts or heavyweight frontend frameworks. All assets load from local disk in `< 10ms`.
2. **Deterministic Responsiveness**: Renders instantly and maintains zero-jitter DOM updates via event-driven Server-Sent Events (SSE).
3. **No Horizontal Scrollbars**: All navigation rails, card lists, settings tabs, and modal dialogues employ responsive flex wrapping (`flex-wrap: wrap`), fluid grids, and internal vertical scrolling (`overflow-x: hidden`).
4. **Strict Element & Data Deduplication**: Each agent's view, settings inputs, and metrics are strictly unique with zero duplicate DOM element IDs or redundant widgets across tabs.
5. **Universal Spotlight Access**: Every screen, setting, and agent can be navigated in milliseconds via keyboard shortcuts (`Ctrl+K` or `/`).

---

## 2. Scalable Fleet Layouts for 100+ Agents

To prevent navigation fatigue as the fleet grows from 5 to dozens or hundreds of agents, AFCC introduces **3 high-efficiency layout modes**, selectable either via the Header Quick Selector or through the Settings Modal (**Settings -> General & Automations -> Fleet Layout**):

```
+-------------------------------------------------------------------------------------------------+
| Layout 1: Sidebar Dock          Layout 2: Command Deck            Layout 3: Launchpad Grid      |
| +----+-----------------------+  +-------------------------------+  +--------------------------+ |
| |Nav | Active Agent View     |  | Command Bar (Grouped Dropdown) |  | [Agent 1] [Agent 2]      | |
| |Rail| - Metrics             |  +-------------------------------+  | [Agent 3] [Agent 4]      | |
| |    | - Controls            |  | Active Agent Workspace        |  | (Status & Metrics Matrix)| |
| |    | - Isolated UI         |  |                               |  |                          | |
| +----+-----------------------+  +-------------------------------+  +--------------------------+ |
+-------------------------------------------------------------------------------------------------+
```

### Layout Comparison Matrix

| Layout Mode | Key Identifier | Ideal Agent Count | Primary Visual Metaphor | Workflow Strengths |
| :--- | :--- | :--- | :--- | :--- |
| **Sidebar Dock** *(Default)* | `sidebar_dock` | $10 - 100+$ agents | Vertical Dock with categories | Deep workspace focus; persistent categorized agent rail on the left; search filter input; collapsible on compact screens. |
| **Command Deck** | `command_deck` | $20 - 100+$ agents | Top Command Bar with Dropdown | Maximum vertical viewport space; dense agent grouping dropdown with status badges and quick-jump pills. |
| **Launchpad Grid** | `launchpad_grid` | $5 - 50+$ agents | High-density card matrix | Holistic fleet overview; live telemetry cards per agent displaying state, memory, and direct activation toggles. |

### Layout Switching Engine
The layout mode is persisted locally in `fleet.yaml` and synced across browser sessions via the REST endpoint `POST /api/settings`:
```json
{
  "layout": "sidebar_dock"
}
```

When switched in real-time, the client engine invokes `setWorkspaceLayout(layoutId)` which instantly toggles `data-layout` on `document.body` and recalculates container dimensions with zero reload.

---

## 3. Dynamic Themes & Visual Ergonomics

AFCC includes **4 custom visual themes** designed for low eye-strain during extended development and operations sessions:

| Theme ID | Name | Background Palette | Accent & Highlight | Best Suited For |
| :--- | :--- | :--- | :--- | :--- |
| `dark` *(Default)* | **Midnight Obsidian** | Deep space slate (`#0b0f19`, `#111827`) | Cyan Glow (`#06b6d4`, `#38bdf8`) | Default coding and low-light workstation environments. |
| `light` | **Clean Daylight** | Crisp off-white & soft gray (`#f8fafc`, `#f1f5f9`) | Ocean Azure (`#0284c7`, `#0369a1`) | High-ambient daylight development and documentation reviews. |
| `aurora` | **Nordic Aurora** | Deep emerald teal (`#061a14`, `#0d281e`) | Mint Neon (`#10b981`, `#34d399`) | Focus-intensive monitoring with high-contrast health states. |
| `midnight` | **Deep AMOLED** | Pure obsidian black (`#000000`, `#080808`) | Electric Purple (`#a855f7`, `#c084fc`) | Maximum energy savings and contrast on OLED displays. |

Themes can be adjusted at runtime via the Settings Modal under **Fleet Theme**. The selection is saved to user preferences and dynamically injected via CSS custom property overrides.

---

## 4. Spotlight Command Palette (`Ctrl+K` or `/`)

The Spotlight Command Palette provides instantaneous, zero-latency keyboard control across all agents, operational tools, settings panels, and actions:

### Keyboard Shortcuts
- `Ctrl + K` or `Cmd + K`: Toggle Command Palette.
- `/`: Open Command Palette when not focused in an input field.
- `Escape`: Dismiss Command Palette or active modal.
- `Arrow Up` / `Arrow Down`: Navigate filtered command candidates.
- `Enter`: Execute highlighted command.

### Search Capabilities
- **Fuzzy Agent Search**: Type any agent name (e.g. `health`, `pr review`, `optimizer`) to jump directly to its view.
- **Action Triggers**: Execute immediate operations such as `Run Security Scan`, `Trigger Dream Cycle`, `Run Auto-Fixer`, `Toggle Layout`, or `Open Settings`.
- **Direct Navigation**: Jump to specific sub-features such as the `Exercise Hub`, `Backlog Kanban`, or `Diagnostics Telemetry`.

---

## 5. Live Server-Sent Events (SSE) Streaming

AFCC does not poll the backend in loops. Instead, it maintains a persistent, low-overhead SSE stream at `/api/events`:
- **Synaptic Event Relays**: Agent state transitions, memory logs, and background tasks are pushed down the stream in real time.
- **Heartbeat & Telemetry**: Microkernel health metrics (RAM usage, active threads, SQLite transaction rates) refresh seamlessly.
- **Auto-Reconnection**: If the AFCC daemon restarts or reloads, the SSE client reconnects with exponential backoff and synchronizes the UI automatically.

---

## 6. Strict Data & DOM Deduplication

To ensure predictable performance and clean styling across 100+ agents, AFCC enforces strict non-duplication rules:
1. **Core & Pinned Agent Deduplication**: Core tab IDs (`overview`, `health`, `optimizer`, `antigravity`, `backlog`, `gmail`, `pr_review`) are registered once in `STATIC_CORE_TAB_IDS` and rendered once in the primary navigation structure.
2. **DOM ID Isolation**: Every input, button, and container uses scoped, unique identifiers. Redundant elements (such as duplicate search inputs or duplicated health water counters) are eliminated.
3. **Encapsulated Sub-Hubs**: Complex features—such as the **Exercise, Videos & Traditional Strength Training Hub**—are strictly enclosed within their parent agent's container (`<div id="viewHealth">`) and cannot leak into other agent views.

---

## 7. Zero Horizontal Scrollbars Guarantee

AFCC guarantees a clean vertical layout across all resolutions:
- Navigation tabs in the Settings modal (`.settings-nav-tabs`) use `flex-wrap: wrap` to gracefully wrap across multiple lines on smaller viewports.
- WebKit scrollbar pseudo-elements for horizontal axes (`*::-webkit-scrollbar:horizontal`) are explicitly suppressed via CSS (`display: none !important`).
- Card containers utilize CSS Grid auto-fill patterns (`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`) ensuring elements snap cleanly without overflowing their bounding boxes.

