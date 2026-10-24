# Changelog

All notable changes to the **Personal Agentic Fleet** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-10-24

### Added
- **Metabolic Health Intelligence & Wellness Protocol Integration**:
  - **Personalized Metabolic Profile & Tracking**:
    - Configurable **Metabolic & Biomarker Profile** backed by the isolated local user vault (`fleet/data/user/`).
    - Active 3-Month Target Countdown: Configurable **HbA1c target** with daily remaining countdown badge and follow-up lab alert.
    - Basic Health Goal (BHG) tracking: Configurable target weight and metabolic milestones.
    - Clinical directives tracking: Dietary guidelines, daily blood pressure monitoring, and meal sequencing rules.
  - **Comprehensive Baseline Lab Diagnostics Integration**:
    - Structured baseline biomarkers in SQLite: Fasting Glucose, 2hr PPBS, HbA1c, Fasting C-Peptide, Lipid Panel, Liver Enzymes, Kidney Function (eGFR, Creatinine), and Vitamin D3/B12 levels.
    - Added interactive **Diagnostic Lab Report Modal** with complete biological reference intervals and status flags.
  - **Medication, Supplement & Mealtime Adherence Management**:
    - Implemented configurable mealtime-grouped medication and supplement schedule:
      - Morning / Post-Breakfast (08:30): Morning supplements and prescribed regimen
      - Afternoon / Post-Lunch (13:30): Midday supplements and nutritional support
      - Evening / Post-Dinner (20:00): Evening supplements and recovery regimen
    - Added mealtime-grouped schedule with 1-click adherence logging and timing countdowns.
  - **Structured Diet & Habit Routines**:
    - Embedded structured daily wellness schedule into routines (07:00 Morning Smoothie, 08:30 25-25-50 Breakfast, 11:00 Mid-Morning Hydration, 13:30 25% Quad Lunch, 16:15 Evening Snack & Nuts/Seeds, 19:30 Early Dinner, 22:30 Sleep Hygiene).
    - Added dedicated modals for **Diet Protocol & Smoothie Recipes** and **Medication & Supplement Guidelines**.
  - **Proactive Daemon Alerts & Daily Briefing**:
    - `FleetDaemon` delivers proactive Windows toast notifications for each meal, hydration, and supplement milestone.
    - Morning Briefing automatically tracks daily adherence and days remaining to the configured metabolic goal.
  - **Multi-Metric Interactive SVG Trend Charts**:
    - Expanded deterministic SVG charting engine to visualize Fasting Blood Sugar, Post-Meal Sugar (PPBS), Body Weight, and Systolic Blood Pressure alongside Hydration, Sleep, Steps, and Heart Rate.

---

## [1.9.0] - 2026-10-14

### Added
- **Full Codebase Modularization & Token Optimization Architecture**:
  - **Frontend UI Modularization (`fleet/web/`)**:
    - Extracted styles into `fleet/web/static/css/dashboard.css`.
    - Extracted layout into semantic template `fleet/web/templates/dashboard.html`.
    - Split monolithic client scripts into 11 isolated, single-responsibility ES modules under `fleet/web/static/js/`:
      - `core.js`: Navigation, tabs, alerts, modals, release notes
      - `briefing.js`: Morning briefing display & speech synthesis
      - `tasks.js`: Daily tasks CRUD and completion toggling
      - `routines.js`: Daily habits and checklist tracking
      - `emails.js`: Email intelligence 5-folder preview & unsubscribe actions
      - `antigravity.js`: Antigravity live transcript, agent queue, model selector, image uploads
      - `health.js`: Hydration glasses grid, medication reminders, vitals logging, SVG trend chart
      - `backlog.js`: Feature backlog CRUD and multi-filter tables
      - `optimizer.js`: PC optimizer diagnostics & 1-click tune
      - `tests.js`: Unit test status card & test runner controls
      - `app.js`: Application bootstrapper and polling lifecycle
    - Built `fleet/web/builder.py` providing dual-mode serving: modular asset caching via HTTP and standalone inlined HTML export.
  - **Backend API Modularization (`fleet/api/`)**:
    - Created lightweight `ApiRouter` in `fleet/api/router.py`.
    - Modularized endpoints into clean domain routers:
      - `fleet/api/tasks_api.py`: `/api/tasks*`, `/api/routines*`
      - `fleet/api/health_api.py`: `/api/health/*` (summary, water, medications, trends, metrics)
      - `fleet/api/email_api.py`: `/api/emails*`, `/api/emails/body`, `/api/emails/unsubscribe`
      - `fleet/api/backlog_api.py`: `/api/backlog*`
      - `fleet/api/optimizer_api.py`: `/api/optimizer/*`
      - `fleet/api/antigravity_api.py`: `/api/antigravity/*`
      - `fleet/api/system_api.py`: `/api/status`, `/api/version`, `/api/release_notes`, `/api/notify`, `/api/test_results`, `/api/run_tests`
  - **Database Domain Mixins (`fleet/core/db/`)**:
    - Modularized `FleetDatabase` into 5 domain mixins (`base.py`, `tasks.py`, `health.py`, `emails.py`, `backlog.py`, `system.py`), dropping `database.py` from 1,249 lines to 53 lines while preserving 100% API compatibility.
  - **Monolithic `fleet/server.py` Downsizing**:
    - Reduced `fleet/server.py` from **4,882 lines (224 KB)** down to **198 lines (7 KB)** (96.4% reduction in code size and token consumption).
  - **Zero-Token Governance & Bug Elimination**:
    - Resolved string escaping token bug (`emailContent.includes('\n')`) by isolating JS into real `.js` files, completely restoring all header buttons and tabs.
    - Full test suite verified: **80/80 passed (100.0%)** with **98.15% code coverage**.

---

## [1.8.0] - 2026-10-14

### Added
- **PC Performance Optimizer & System Tuning Dashboard**:
  - **Dedicated Control Center Tab (`🚀 PC Optimizer`)**:
    - Full telemetry diagnostics: RAM memory load and available GB, Disk storage (C: drive), Windows temporary junk file bloat, startup boot programs, and top active memory processes.
    - Overall Performance Health Score (0–100) dynamically synthesized across memory load, disk capacity, temp junk, and startup volume with clear status badges (Excellent, Good, Fair, Needs Optimization).
    - Quick Overview Card integrated into the main Overview tab displaying instantaneous RAM load, disk space, junk bloat, and quick action buttons.
  - **Actionable 1-Click Remediation Controls**:
    - 🧹 **Clean Windows Temporary Files**: Safely purges stale cache files from `%TEMP%`, freeing disk space and reducing file indexing overhead.
    - ⚡ **Flush DNS Resolver Cache**: Purges stale and corrupted DNS entries via `ipconfig /flushdns` to eliminate network stalls and API latency.
    - 🐍 **Purge Dev & PyCache Folders**: Recursively removes `__pycache__`, `.pytest_cache`, and compiled bytecode (`*.pyc`) files.
    - 💾 **Optimize RAM Working Sets**: Trims inactive working sets and executes garbage collection (`gc.collect()`) to reclaim system RAM.
    - 🚀 **Manage Startup Apps**: Directly opens the native Windows Settings Startup page (`ms-settings:startupapps`) to disable unwanted boot applications.
    - ⚡ **1-Click Complete Auto-Tune**: Executes cleanup, DNS flush, cache purge, and memory sweep in a single unified action.
  - **Deterministic Event Bus Integration**:
    - Registered `system` target worker on `DeterministicEventBus` supporting `DIAGNOSTICS`, `CLEAN_TEMP`, `FLUSH_DNS`, `PURGE_CACHES`, `OPTIMIZE_RAM`, and `OPEN_STARTUP`.
  - **Zero-Token Governance Compliance**:
    - All diagnostics, registry inspections, memory calculations, and optimization actions run in pure Tier 0 deterministic Python ($0.00 / 0 Tokens). Tokens remain strictly and exclusively reserved for code enhancement.
  - **Quality & Coverage Verification**:
    - Expanded suite to **71 passing unit tests (100.0%)** with **98.37% code coverage** and zero token consumption.

---

## [1.7.0] - 2026-10-14

### Added
- **Token Exhaustion Monitoring & Zero-Loss Work Preservation**:
  - **Live Context Window & Token Capacity Monitor**: Integrated real-time token tracking in the Antigravity chat header bar with a color-coded percentage gauge (`#agTokenHealthBar`).
  - **Quota Exhaustion & 429 Error Interception**: Automatically detects context saturation and intercepts HTTP 429 / `RESOURCE_EXHAUSTED` responses from providers.
  - **Multi-Channel Proactive Alerting**: Sends native Windows toast notifications (`⚠️ Antigravity Token Alert`) so the user is immediately alerted even when away from the screen or laptop is unattended.
  - **Non-Destructive SQLite Prompt Vaulting**:
    - Protects in-flight and queued chat messages by transitioning them to `vaulted` state in `chat_queue` and recording immutable event logs in `token_preservation_vault`.
    - Guarantees zero data loss: prompts, custom commands, and multi-modal image references remain safe and intact.
  - **1-Click Fallback Model Resumption**:
    - Prominently displays an alert banner (`#agTokenExhaustedBanner`) above the chat view with a one-click `🔄 Resume with Fallback` button.
    - Seamlessly migrates all vaulted prompts to a high-capacity fallback model (e.g. Claude Opus 5.5, Claude Sonnet 5.5, or Gemini 3.8 Flash) and auto-resumes queue processing.
  - **Token Preservation Vault Modal (`📦 View Vault`)**:
    - Dedicated UI panel to inspect vaulted prompts, review original model targets, and manually trigger batch recovery.
  - **Fail-Safe Testing & Simulation Controls**:
    - Added simulation triggers (`⚠️ Simulate Token Exhaustion`, `✅ Reset Normal Health`) inside the LLM Details modal for effortless verification.
  - **Zero-Token Governance Compliance**:
    - All token calculations, file heuristics, SQLite operations, and UI updates execute strictly under Tier 0 deterministic Python ($0.00 / 0 Tokens).
- **Zero-Token & Zero-Network Unit Test Suite Hardening**:
  - Enforced strict Tier 0 deterministic execution across all 52 unit tests and code coverage runs ($0.00 / 0 Tokens).
  - Implemented `FLEET_TEST_MODE` safety gates across `_execute_agy_or_fallback` in `antigravity_mirror.py` and `_init_service` in `gmail_client.py`, preventing unmocked `agy.exe` invocations and live Google OAuth / Gmail network requests.
  - Added root `conftest.py` with an autouse network guard fixture blocking all non-localhost outbound sockets during test execution.
  - Optimized SQLite database connection PRAGMAs (`WAL` mode and `synchronous = NORMAL`), accelerating test execution time by ~94% (from 590.18s down to 36.72s).
  - Achieved **52/52 passing tests (100.0%)** with **98.26% code coverage**.

---

## [1.6.0] - 2026-10-14

### Added
- **Calendar & Google Meet Auto-Agenda Preparation**:
  - Automatically analyzes incoming calendar invites and meeting notifications from Inbox / Gmail Folder 0 (`Fleet/0-Meetings`).
  - Extracted metadata: clean meeting title, scheduled time, platform (`Google Meet`, `Zoom`, `Microsoft Teams`, `Calendly`), and organizer.
  - Generates tailored context preparation checklists based on meeting nature (roadmap milestones & sprint goals, client proposals & pitch terms, 1-on-1s & interviews, and general deliverables).
  - Integrated into `BriefingEngine` and rendered dynamically inside the Morning Briefing card on the Control Center dashboard.
- **Interactive Spoken Audio Briefing (Text-to-Speech)**:
  - Added `🔊 Speak` button to the Morning Briefing dashboard card.
  - Native Web Speech API synthesis provides crystal-clear spoken briefing playback with zero network latency, zero token cost (\$0.00), and full offline capability.
- **Autonomous Fleet Daemon Operation**:
  - Proactive background monitoring for Morning Briefing (08:30 AM), Evening Wrap-up (08:00 PM), 2-hour email pulses, and 30-minute automated test suite coverage runs.
  - Updated Feature Backlog item "Calendar & Google Meet Auto-Agenda Prep" to `Completed`.
- **Unit Test Suite & Code Quality Gate**:
  - Suite expanded to **50 passing tests** with **98.7% code coverage**.

---

## [1.5.0] - 2026-10-14

### Added
- **Email Intelligence Unsubscribe Option & Workload Reduction**:
  - Added smart unsubscription detection and direct unsubscription control in the **Email Intelligence** pane.
  - Automatically parses standard `List-Unsubscribe` (RFC 2369) and `List-Unsubscribe-Post` (RFC 8058 One-Click) headers as well as opt-out links from email bodies/snippets.
  - Dynamically displays an interactive `🔕 Unsubscribe` button alongside external link shortcut (`↗`) **only** when an unsubscribe option exists in the email (e.g., newsletters, promotions, marketing blasts), preserving a clean display for personal and meeting emails.
  - 1-click unsubscribe action triggers background HTTP request to unsubscription endpoints or dispatches unsubscription handlers.
  - Live Gmail integration auto-labels unsubscribed threads to `Fleet/4-Ignore` and removes them from the Inbox (`INBOX`) to immediately reduce incoming email volume and user workload.
  - Persistent SQLite storage in `unsubscribed_emails` table tracking message IDs, senders, subjects, URLs, and timestamps.
  - Real-time UI status updates dynamically switching the button to a green `✓ Unsubscribed` badge.
- **REST Endpoints & Event Bus Handlers**:
  - `POST /api/emails/unsubscribe`: Initiates unsubscription, records preference, and moves emails out of the inbox.
  - Deterministic Event Bus action `UNSUBSCRIBE` routed directly to `GmailManager.unsubscribe_from_email`.
- **Database & Integration Layer**:
  - `FleetDatabase.record_unsubscribed_email`, `is_email_unsubscribed`, and `list_unsubscribed_emails`.
  - `GmailManager.extract_unsubscribe_info` and `unsubscribe_from_email`.
- **Test Suite & Verification**:
  - Added comprehensive test coverage across database, classifier, Gmail client, event bus, and HTTP server.
  - Expanded test suite to **49 passing tests** with **99.1% code coverage**.

---

## [1.4.0] - 2026-10-14

### Added
- **Feature Backlog Management Panel**:
  - Dedicated top-level navigation tab (`📋 Feature Backlog`) in the Web Control Center (`http://127.0.0.1:7890`).
  - Interactive product roadmap & feature backlog manager with persistent SQLite storage (`feature_backlog` table).
  - Pre-seeded roadmap features: Voice Commands, Multi-channel Messaging Bots, Calendar Auto-agenda, MCP Tool Creator, and Local Ollama Fine-tuning.
  - Interactive status workflow: `Idea` ➔ `Planned` ➔ `In Progress` ➔ `Completed` / `Deferred`.
  - Feature priority tagging (`P1 - Critical`, `P2 - High`, `P3 - Normal`, `P4 - Low`) with automated priority-ordered sorting.
  - Categorization across `Fleet Core`, `Antigravity Integration`, `Automation & Daemon`, `UI & UX`, `AI & ML Models`, and `Integrations`.
  - Target release milestone tagging (e.g. `v1.4.0`, `v1.5.0`, `v2.0.0`, `Backlog`).
  - Quick-filter toolbar supporting combined filtering by Status, Category, and Target Release.
  - Statistical backlog metrics header cards displaying Total Features, In Progress, Planned, Ideas, and Completed counts.
  - Inline editing for instant status transitions and item deletion.
- **Backlog HTTP API Endpoints**:
  - `GET /api/backlog`: Query backlog items with optional status, category, and target version filters, plus aggregate summary statistics.
  - `POST /api/backlog`: Create new backlog items with title, description, category, priority, status, and target version.
  - `POST /api/backlog/update`: Update backlog item properties and statuses.
  - `POST /api/backlog/delete`: Remove items from the backlog.
- **Database CRUD Methods**:
  - Added `add_feature_backlog_item`, `list_feature_backlog_items`, `update_feature_backlog_item`, `delete_feature_backlog_item`, and `get_feature_backlog_stats` to `FleetDatabase`.
- **Extended Test Suite & Coverage**:
  - Added full test coverage for database backlog operations and HTTP server backlog endpoints.
  - Suite increased to 47 passing tests with **99.1% code coverage**.

---

## [1.3.0] - 2026-10-14

### Added
- **VS Code Antigravity Model Picker**:
  - Replicated exact visual popover popup in the Web Control Center matching VS Code Antigravity.
  - Model options:
    - `Gemini 3.8 Flash` (`High` green badge) — Active default
    - `Gemini 4 Argon (Medium)` (`Unavailable` gray badge)
    - `Claude Opus 5.5` (`Medium`, `New` purple badge)
    - `Claude Sonnet 5.5` (`Medium`, `New` purple badge)
    - `GPT-OSS 120B (Medium)` (`Notice` orange badge)
  - Seamless model selection updating local database setting `active_model`.
- **LLM Usage Details Modal**:
  - Speedometer-accessible overlay (`⚡ View Usage`) showing real-time token stats.
  - Active model & effort level indicator.
  - Session cost tracker verified at **\$0.00** under Tier 0 Fleet Computational Optimization.
  - Context window size (`1,000,000 Tokens`), input token count, output token count, and provider status.
- **Multi-Modal Image Attachment Suite**:
  - Paperclip attachment button (`📎`) supporting `.png`, `.jpg`, `.jpeg`, `.webp`, and `.gif`.
  - Direct clipboard paste (`Ctrl+V`) into chat bar or screen.
  - Drag-and-drop file upload zones over chat history and command console.
  - Real-time pre-send thumbnail attachment strip with individual remove buttons (`✕`).
  - Inline image thumbnails embedded in message bubbles for both User and Assistant turns.
  - Click-to-zoom Lightbox modal for high-resolution inspection.
  - Dual-path file persistence: saved to `fleet/data/uploads` and mirrored to active brain session `.user_uploaded`.
- **Message Queuing Engine**:
  - Thread-safe agent status detector (`idle` vs. `busy`).
  - Automatic prompt & image queueing in SQLite (`chat_queue` table) when Antigravity is busy.
  - `📥 Message Queue` banner showing pending item count, prompt snippets, target models, and `✕ Cancel` buttons.
  - Background queue worker automatically dequeuing and dispatching pending messages in FIFO order once the active turn concludes.
- **Standalone CLI Execution**:
  - Direct execution via standalone `agy.exe` (`--model`, `-c`, `-p`, `--dangerously-skip-permissions`) without requiring VS Code.
  - Safe offline memory note fallback when running without CLI.
- **Centralized Versioning & Release Notes**:
  - Added `fleet.__version__` (`1.3.0`) and `fleet.config.VERSION`.
  - Added `/api/version` and `/api/release_notes` HTTP endpoints.
  - Interactive version badge in Control Center header opening this Release Notes modal.

### Changed
- Refactored `parse_transcript` to extract step `media` payloads and markdown image references into structured media objects.
- Enhanced `execute_dashboard_command` to support image-only prompts, explicit target models, and queueing flags.
- Updated Control Center send button state: dynamically toggles between `➤ Send` and `📥 Queue Message`.

### Fixed
- Fixed JSON serialization in `FleetDatabase.enqueue_chat_message`.
- Corrected thread worker recursion during queue test mocks.
- Ensured proper media MIME type header serving in HTTP server.

---

## [1.2.0] - 2026-10-13

### Added
- **Automated Unit Testing & Coverage Gate**:
  - Integrated `pytest` and `coverage.py` test suite covering all fleet modules.
  - Created programmatic test runner `fleet.tools.test_runner` to execute test suites and record metrics.
  - Strict coverage enforcement maintaining **$\ge 98.0\%$ code coverage** (achieved **99.0%**).
  - SQLite persistence of all test runs in `test_runs` table (`total_tests`, `passed_tests`, `pass_pct`, `coverage_pct`, `duration_sec`, `status`).
  - Results caching in `fleet/data/test_results.json` for instant UI loading.
- **Live Test Quality Metrics in Control Center**:
  - Dashboard test metrics widget displaying pass percentage (`100%`), test count (`46 / 46`), coverage (`99%`), execution duration, and timestamp.
  - Interactive **⚡ Run Tests Now** button with real-time UI state feedback.
  - Automatic hourly test suite execution scheduled via `fleet.daemon.FleetDaemon`.
- **HTTP Endpoints**:
  - `GET /api/test_results`: Returns latest test execution run.
  - `POST /api/run_tests`: Triggers immediate test suite execution and persists updated metrics.

### Changed
- Configured `.coveragerc` with branch coverage, precise exclusions, and source tracking.
- Protected server and daemon test suites from recursive runner execution during pytest runs.

---

## [1.1.0] - 2026-10-13

### Added
- **Autonomous Background Execution (No VS Code Required)**:
  - Created `fleet/app.py` unified launcher with automatic port conflict handling and single-instance PID tracking.
  - Created silent Windows VBS launcher `fleet_startup.vbs` executing headless via `pythonw.exe`.
  - Created `setup_startup.py` to automatically register the launcher in the Windows Startup directory (`shell:startup`).
  - Added graceful process termination and port recycling on exit (`atexit`).
- **Windows Toast Notification Engine**:
  - Native toast notifications via PowerShell WinRT XML with zero external pip dependencies.
  - Integration with dashboard button (`🔔 Trigger Notification`) and `/notify` CLI command.
  - Fallback notification logging in `fleet_memory.db`.

### Changed
- Migrated Control Center server from single-threaded `HTTPServer` to `ThreadingHTTPServer` with daemonized worker threads.
- Refactored server process management to ensure background survival upon closing VS Code.

### Fixed
- Fixed port `7890` collision on restart by implementing socket reuse (`allow_reuse_address = True`) and active PID cleanup.
- Fixed Python 3.14 stdout/stderr pipe crashes under headless `pythonw.exe` by implementing `setup_streams()`.

---

## [1.0.0] - 2026-10-12

### Added
- **Core Database & Memory System**:
  - Persistent SQLite storage (`fleet_memory.db`) for tasks, key-value memories, notes, and activity logs.
  - Pre-seeded daily routines (Morning Meditation, Code Review, Evening Walk, Read Architecture Docs, Backup Workspaces).
- **Deterministic Event Bus**:
  - Zero-token internal pub/sub event bus (`FleetEvent`, `bus`) for decoupled inter-module messaging.
- **Email Intelligence System**:
  - 5-Folder classification engine: `0) Meetings`, `1) Respond`, `2) Note`, `3) FYI`, `4) Ignore`.
  - Gmail API integration (`gmail_client.py`) with OAuth2 token handling and 60-day query sync.
  - Deterministic fallback simulation mode when Gmail credentials are not present.
- **Daily Morning Briefing Engine**:
  - Rule-based briefing generator producing headlines, daily priority summaries, and habit completion stats.
- **Web Control Center Dashboard**:
  - Sleek modern single-page dashboard at `http://127.0.0.1:7890`.
  - Glassmorphic UI with animated gradients, task checklists, habit trackers, and email categorizer preview.
  - Zero third-party web framework dependencies (built with Python standard library `http.server`).
- **Agentic Fleet Governance**:
  - Implemented `AGENTS.md` Prime Directive: Tier 0 computational optimization ($0.00 / 0 Tokens) for all deterministic system operations.

