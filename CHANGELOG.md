# Changelog

All notable changes to the **Personal Agentic Fleet** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.8.5] - 2026-10-28

### Documentation & Maintenance
- **Wiki**: Create comprehensive detailed wiki covering AFCC, built-in agents, CI/CD, and architecture.

---

## [2.8.4] - 2026-10-28

### Fixed
- **CI**: Resolve immutable release asset conflict, Node 20 deprecation, and ubuntu-24.04 runner pinning with proactive workflow auto-fixer.

---

## [2.8.3] - 2026-10-28

### Fixed
- Proactive release synchronization, static type verification, and documentation maintenance.

---

## [2.8.2] - 2026-10-28

### Added
- **UI**: Eliminate horizontal scrollbars across AFCC and rename Workstation Control Center to Agentic Fleet Control Center (AFCC) (v2.8.4).

### Fixed
- **UI**: Encapsulate Exercise & Strength Training Hub strictly inside viewHealth container (v2.8.3).
- **UI**: Resolve VS Code HTML/CSS diagnostics on dashboard.html and add proactive HTML/CSS template auto-fixer (v2.8.2).

### Documentation & Maintenance
- **Hygiene**: Ignore test_user directory and refine template CSS auto-fixer.

---

## [2.8.1] - 2026-10-28

### Fixed
- **Isolation**: Enforce strict test firewall so unit/E2E tests never mutate production DB, hydration, backlog, or user agents (v2.8.1).

---

## [2.8.0] - 2026-10-27

### Added
- **WCC**: Eliminate duplicate agent information across sidebar dock, active stage, settings, and agent views.

---

## [2.7.0] - 2026-10-27

### Added
- **UI**: Redesign WCC header and add 3 scalable layouts for 100+ agents in settings.

### Fixed
- **Version**: Enforce live version parity between GitHub Release and Workstation Control Center.

### Documentation & Maintenance
- **Release**: Bump release to v2.7.0 and sync docs/wiki.

---

## [2.6.0] - 2026-10-27

### Added
- **Release**: Add proactive semantic release manager, doc/wiki enhancer, and lifecycle orchestrator (v2.6.0).
- **Autofix**: Add zero-intervention VSCode & CodeQL auto-fixer and SARIF CI verifier.
- **CLI**: Provide unified Fleet CLI (fleet & python -m fleet), full subcommands and test suite.
- **Wiki**: Establish complete GitHub Wiki documentation corpus, sync CLI, and automated workflow.
- **Mind**: Implement 4-layer Cognitive Fleet Mind (Brain, Consciousness, Subconsciousness, Soul).
- **Observability**: Add proactive periodic log scanner and autonomous self-healing improvements.
- **Observability**: Enable full-fledged structured logging with dedicated error isolation and deep diagnostics.
- **Ui Scale**: Add scalable 100+ agent operations center, drawer navigator, and Ctrl+K command palette.
- **Agent Wizard**: Add create-agent skill, header + button, and 4-step workflow wizard.
- **Settings**: Add agent activation toggles, agent-specific settings, GitHub update engine, and agent catalog download.
- **Linux**: Elevate Ubuntu 20.04+, Debian 11+, Fedora 38+, and Arch Linux to Tier 1 native support.
- **Test**: Elevate microkernel test suite to 99.12% code coverage (321 tests, Tier 0 deterministic).
- **Linux**: Comprehensive native Linux OS support and hardware parity.

### Security
- **Codeql**: Resolve final 4 CodeQL sensitive-data alerts in setup_gmail and hyperscalers.
- **Codeql**: Resolve all 15 remaining CodeQL alerts across server, hyperscalers, dev_tools, setup_gmail, and security_scanner.
- **Security**: Eliminate CodeQL ReDoS and path injection sinks via linear parsing and directory enumeration.
- **Security**: Resolve CodeQL incomplete URL substring sanitization and matrix CI dependencies.
- **Security**: Resolve all CodeQL code scanning alerts with strict path and command line barriers.
- **Security**: Resolve all 26 CodeQL alerts and enforce proactive pre-commit checks.

### Fixed
- **Vscode**: Eliminate Pylance settingsNotOverridden warning and stale GitHub Actions diagnostics.
- **Mind**: Replace Python 3.14-only RLock.locked() with cross-version dreaming flag.
- **CI**: Ensure user vault initialization in fresh checkout and install pytest in type-check job.
- **Typing**: Enforce zero VSCode/Pyright diagnostics across full workspace and CI.
- **CI**: Ensure multi-platform pyright compatibility and headless CI test stability.
- **Typing**: Eliminate all 133 VSCode/Pyright issues and enforce proactive pre-commit type check.
- **Tasks**: Ensure list_tasks default exclude_tests is false for deterministic internal operations.
- **Isolation**: Prevent unit test tasks and activity logs from polluting workstation control center.
- **Sandbox**: Guard POSIX RLIMIT_AS in test mode and mock egress connect.
- **CI**: Bind agent submodules for Python 3.10 and enforce headless SDL in CI matrix.
- **CI**: Add agent packages __init__.py, import ctypes in tests, stream pytest output in ci.
- **Cross Platform**: Guard STARTUPINFO/windll on posix, fix Path mocking, import pr_review agent, gracefully handle pages setup.
- **CI**: Add missing Tuple typing imports for python 3.10/3.11, install pygame-ce in ci, enable pages deployment.

### Documentation & Maintenance
- **Autofix**: Run full VS Code Pyright CLI auto-remediation and parent workspace config sync in pre-commit.
- **Readme**: Add Windows OS badge and native Win32/DPAPI architecture details.
- **Telemetry**: Record 385/385 test execution results and auto-improvements ledger.
- **Telemetry**: Record verified 384/384 test results (95.95% coverage) and auto-improvement ledger.
- Comprehensively enrich documentation with Cognitive Fleet Mind, Auto-Healer, Navigator, and Agent Wizard.
- **Test**: Record 100% test pass results and auto-improvements ledger.
- **Observability**: Document full-fledged structured logging, error forensics isolation, and diagnostics APIs.
- **Workstation**: Add comprehensive in-depth live socket e2e test suite.
- **Robustness**: Add comprehensive native robustness architecture and operations guide.

---

## [2.5.0] - 2026-10-26

### Added
- **Browser-Based Fleet Settings & Universal Agent Customizer**:
  - **Top Navigation Settings Icon (`⚙️`)**:
    - Embedded accessible settings trigger button into the dashboard header actions, providing 1-click modal configuration for all agents and system settings directly in the browser.
  - **Centralized Settings & Dynamic Customization Modal**:
    - **Tab 1: Agents & Extensions**:
      - Live inventory of all built-in and user custom agents (`overview`, `health`, `antigravity`, `backlog`, `optimizer`, `gmail`, `pr_review`, and custom agents).
      - Instant Active/Inactive toggle switches with optimistic UI update and dynamic navigation tab re-rendering in real time without page reload.
      - Inline configuration drawers per agent: customize Display Name, Emoji/SVG Icon, Tab Sort Order, LLM Hyperscaler Provider (`auto`, `google`, `anthropic`, `microsoft`, `aws`, `ollama`), LLM Model Tier, Custom System Prompts, and Default Tab designation.
      - 1-click "+ New Custom Agent" form generating isolated custom agents in the private user vault.
      - "Reset to Defaults" button restoring factory built-in configurations.
    - **Tab 2: General & Automations**:
      - Timezone selector supporting Indian Standard Time (IST, UTC+05:30), UTC, EST, PST, GMT, and JST.
      - Proactive desktop notifications toggle with configurable Quiet Hours window.
      - Cost & Inference Policy selector (`PREFER_ZERO_TOKEN_CODE`, `LOWEST_COST_FIRST`, `HIGHEST_REASONING_QUALITY`).
      - Dashboard color theme selector.
    - **Tab 3: AI & Hyperscaler Providers**:
      - Central default gateway provider and model selector.
      - Local Ollama Base URL configuration with live "Test Ping" connectivity tester.
    - **Tab 4: Backups & System Maintenance**:
      - Instant Point-in-Time SQLite Database Snapshot creator (`POST /api/settings/backup/snapshot`).
      - Direct access links to structured Activity Logs, Crash Reports forensics, and Settings Manifest JSON.
  - **Backend Settings API & Agent Lifecycle Subsystem (`fleet/api/settings_api.py`)**:
    - `GET /api/settings`: Serves merged system settings and all discovered agent manifests with enabled/disabled counts.
    - `POST /api/settings`: Atomically persists key-value system preferences to the SQLite `settings` table.
    - `POST /api/settings/agents/toggle`: Dynamically activates/deactivates agents at runtime with state persistence to `agent_overrides.json`.
    - `POST /api/settings/agents/customize`: Updates agent display, prompt, and routing configuration at runtime.
    - `POST /api/settings/agents/reset`: Reverts agent customizations to factory defaults.
    - `POST /api/settings/backup/snapshot`: Creates timestamped SQLite database backups in `fleet/data/backups/`.
  - **Enhanced Agent Discovery & Concurrency Contract (`fleet/core/registry.py`)**:
    - Registry loads and tracks all discovered agents across both active and inactive states (`_all_discovered_agents`, `disabled_agents`).
    - Extended `get_manifests(include_disabled: bool)` supporting both active tab navigation rendering and full settings inventory inspection.
  - **Automated Test Suite**:
    - Added comprehensive unit tests in `tests/test_settings_api.py` covering settings retrieval, updating, agent activation toggling, customization, resetting, and backup snapshots.
    - Test suite expanded to **190 tests passing** across 37 test suites with 100/100 security score.
- **Comprehensive Native Linux OS Support & Hardware Parity**:
  - **Linux Desktop Notifications**: Added native notification routing via `notify-send` (libnotify), GNOME `zenity`, and KDE `kdialog` with application branding and severity icons.
  - **Linux Hardware & Working Set Memory**: Enhanced `get_process_memory_mb()` to extract exact resident set size (`VmRSS`) from `/proc/{pid}/status`, and hooked Glibc `malloc_trim(0)` into `optimize_ram()` to return freed heap memory to the Linux kernel.
  - **XDG Autostart & systemd Scanning**: Enhanced `get_startup_apps()` to inspect both XDG user autostart entries (`~/.config/autostart/*.desktop`), system-wide autostart (`/etc/xdg/autostart/*.desktop`), and systemd user services (`~/.config/systemd/user/*.service`).
  - **Multi-Desktop Environment Startup Panel**: Enhanced `open_startup_settings()` to launch GNOME (`gnome-session-properties`), KDE (`kcmshell5 autostart`), XFCE (`xfce4-session-settings`), or open the XDG directory via `xdg-open`.
  - **Linux DNS Resolver Flushing**: Enhanced `flush_dns_cache()` to invoke `resolvectl flush-caches` with automatic fallback to `systemd-resolve --flush-caches`.
  - **Linux SecretService Credential Storage**: Added native `secret-tool` CLI fallback in `get_secure_secret` and `set_secure_secret` for seamless integration with FreeDesktop SecretService / GNOME Keyring.
  - **Native Linux Unit Test Suite**: Added `tests/test_linux_native.py` with 8 comprehensive unit tests, bringing the total suite to **198 tests passing**.

---

## [2.4.0] - 2026-10-26

### Added
- **6-Pillar Native Robustness & High-Availability Engine**:
  - **Pillar 1: Process Lifecycle & Resilience**:
    - **Thread & Task Supervision Watchdog (`fleet/core/supervisor.py`)**: Erlang/OTP one-for-one supervisor architecture with exponential backoff and full jitter ($t = \text{random}(0, \min(30, \text{base} \times 2^{\text{attempt}}))$), thread failure tracking, and automated worker revival.
    - **Unified Signal Trap & Clean Shutdown Protocol (`fleet/core/lifecycle.py`)**: Intercepts Win32 `SetConsoleCtrlHandler` (`CTRL_C_EVENT`, `CTRL_CLOSE_EVENT`, `CTRL_SHUTDOWN_EVENT`) and POSIX `SIGINT`/`SIGTERM` to safely checkpoint SQLite WAL, flush pooled connections, invoke prioritized shutdown hooks, and cleanly remove PID files.
    - **Multi-OS Workstation Service Daemonization Installers (`fleet/tools/install_service.py`)**: 1-command installer CLI configuring persistent login services across Windows Task Scheduler (`schtasks`), macOS LaunchAgents (`launchctl`), and Linux systemd (`systemctl --user`).
  - **Pillar 2: Storage & Database Concurrency**:
    - **Thread-Safe SQLite Connection Pool & Busy Timeout Guard (`fleet/core/db/pool.py`)**: Per-thread connection caching via `threading.local()` eliminating thread-affinity errors, paired with `PRAGMA busy_timeout = 10000` (10s lock wait) and `PRAGMA journal_mode = WAL`.
    - **Automated Daily Snapshot Backup Engine (`fleet/core/db/backup.py`)**: Non-blocking online backups using SQLite's native `sqlite3.Connection.backup()` API, SHA-256 integrity verification, and automatic FIFO 7-day snapshot retention pruning.
    - **Zero-Dependency Schema Migration Engine (`fleet/core/db/migrations.py`)**: Monotonic database versioning using `PRAGMA user_version` and atomic transactions (`BEGIN IMMEDIATE TRANSACTION`) with automatic rollback.
  - **Pillar 3: Agent Sandbox Hardening & Resource Containment**:
    - **OS Job Objects & POSIX Resource Quota Sandbox (`fleet/core/sandbox_quota.py`)**: Enforces hard 500 MB memory ceilings using Windows Job Objects (`JOBOBJECT_EXTENDED_LIMIT_INFORMATION`) and POSIX `setrlimit` (`RLIMIT_AS`).
    - **Socket-Level Network Egress Policy Enforcer (`fleet/core/sandbox_quota.py`)**: Context manager intercepting socket connection attempts within agent execution threads; blocks egress if manifest lacks `"network:outbound"` while permitting loopback IPC.
  - **Pillar 4: Network, Transport & API Robustness**:
    - **Resilient HTTP Client with 3-State Circuit Breaker (`fleet/core/http_client.py`)**: Pure-Python resilient HTTP client with `CLOSED`, `OPEN`, and `HALF_OPEN` states, 5-failure trip threshold, 30s cooldown, truncated exponential backoff, and full jitter.
    - **Localhost Token-Bucket Rate Limiter & DoS Shield (`fleet/core/rate_limiter.py`)**: In-memory token bucket rate limiter (60 req/s, burst capacity 100) returning HTTP 429 and `Retry-After` headers.
    - **Offline Network Detection & Task Spooling Engine (`fleet/core/network_spool.py`)**: Zero-token reachability probing, offline event deferral into SQLite `offline_spool`, and automatic event bus flushing upon network restoration.
    - **Server-Sent Events (SSE) Live Push Stream (`/api/events/stream`)**: Native standard library SSE streaming endpoint with per-client EventBus subscriber queues, instant push notifications, and 2-second keep-alive ping pulses.
  - **Pillar 5: Observability, Diagnostics & Crash Forensics**:
    - **Structured JSON Logging & In-Memory Ring Buffer (`fleet/core/logger.py`)**: Uniform JSON log formatting with rotating 5 MB file handlers (3 backups) and a thread-safe 1,000-event circular buffer queried via `GET /api/diagnostics/logs`.
    - **Global Crash Reporter & Secret Sanitization (`fleet/tools/crash_reporter.py`)**: Universal hooks for `sys.excepthook` and `threading.excepthook`, automated PII and API key redaction, system hardware snapshots, and JSON forensics dumped into `fleet/data/crash_reports/`.
  - **Pillar 6: Hardware & Power State Awareness**:
    - **System Sleep / Wake / Resume Lifecycle Handler (`fleet/core/power.py`)**: Precision monotonic gap detection for suspend/sleep transitions, 5-second post-wake network stabilization cooldown, and coalesced routine triggering.
- **Preflight Quality Gate Verification**:
  - Expanded automated test suite from 89 to **109 unit and integration tests** across 33 test suites (`tests/test_db_robustness.py`, `tests/test_lifecycle_supervisor.py`, `tests/test_transport_robustness.py`, `tests/test_observability_robustness.py`, `tests/test_sandbox_quota.py`, `tests/test_power_robustness.py`).
  - Preflight quality gate (`fleet.tools.preflight_gate`) verified 100% compliance: Fleet Doctor healthy, Security Scanner 100/100 (0 findings), 10 isolated agent packages valid, 13 documentation cross-reference files verified (111 links intact).

---

## [2.3.0] - 2026-10-26

### Added
- **Automated & Customizable YAML Agent Scheduling Engine (`fleet/core/scheduler.py`)**:
  - **Zero-Dependency Pure-Python YAML Parser & Serializer (`fleet/core/yaml_helper.py`)**:
    - Implemented robust pure-Python YAML parser (`safe_load_yaml`, `load_yaml_file`) and serializer (`dump_yaml`, `save_yaml_file`) supporting nested dictionaries, lists of objects, inline arrays, and type conversions without requiring third-party libraries (`PyYAML` optional).
  - **Flexible Timing Modes & Evaluators**:
    - Exact time-of-day triggering: single `time: "08:30"` or multiple `times: ["08:30", "20:00"]` with daily date-stamped execution tracking.
    - Recurring intervals: `interval_hours: 6`, `interval_minutes: 30`, `interval_seconds: 30`, or human strings `every: "2h"`.
    - Standard 5-field cron syntax: `cron: "0 9 * * 1-5"` or `*/15 * * * *` with step, range, and list parsing.
    - Filter guards: `days: ["mon", "wed", "fri"]`, `weekdays_only: true`, and `active_hours: "08:00-18:00"`.
  - **Pre-Configured Out-Of-The-Box Schedules (`fleet/config/schedules.yaml`)**:
    - Default schedules configured for all 7 agent packages: `overview` morning briefing (08:30) & evening review (20:00), `health` smoothie (07:00), breakfast meds (08:30), lunch meds (13:30), afternoon snack (16:15), dinner meds (20:00), sleep recovery (22:30), `optimizer` quick optimize (every 6h), `gmail` sync (every 2h), `antigravity` process queue (every 15m), and `backlog` grooming (Fridays 17:00).
    - Provided root template `schedules.yaml.example` for instant user overrides.
  - **Agent Task Dispatching Interface (`execute_task`)**:
    - Added `execute_task(self, task: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]` to `FleetAgent` and implemented task handlers across all agents in `fleet/agents/` maintaining strict package isolation.
  - **Background Daemon, REST API & MCP Integration**:
    - Integrated scheduler loop into `FleetDaemon.check_and_trigger()`.
    - Added REST endpoints: `GET /api/schedules`, `POST /api/schedules/toggle`, `POST /api/schedules/run`, `POST /api/schedules/reload`.
    - Added MCP tools: `fleet_list_schedules`, `fleet_toggle_schedule`, `fleet_run_scheduled_task`.
  - **Automated Test Coverage**:
    - Comprehensive unit and integration test suites: `tests/test_yaml_helper.py` (4 tests) and `tests/test_scheduler.py` (11 tests), plus REST API test coverage in `tests/test_server.py`.
- **Interactive Visual Schedule Manager in Web Dashboard**:
  - Live visual schedule card in Overview tab (`fleet/web/templates/dashboard.html`) powered by `fleet/web/static/js/schedules.js`.
  - Displays real-time agent schedule badges, timing descriptions, status counters, one-click pause/resume toggles (`/api/schedules/toggle`), and instant manual task triggers (`/api/schedules/run`).
- **1-Command Agent Scaffolding CLI (`fleet/tools/create_agent.py`)**:
  - Added CLI tool to instantly bootstrap new isolated agent packages with manifest permissions verification, backend class structure, and UI panels.
  - Added comprehensive test suite in `tests/test_create_agent.py` (5 tests).
- **GitHub Packages & Container Distribution (`ghcr.io`)**:
  - Added multi-stage, rootless `Dockerfile` and `.dockerignore` running under unprivileged user `fleet:fleet` (UID 10001).
  - Added `.github/workflows/package.yml` to automatically build and publish container images to GitHub Container Registry (`ghcr.io`) at zero cost.
- **Automated GitHub Releases Pipeline**:
  - Added `.github/workflows/release.yml` to automatically build wheel/sdist packages, generate CycloneDX SBOMs and SHA-256 checksums, and publish GitHub releases on tag push `v*.*.*`.
- **GitHub CodeQL Static Security Analysis**:
  - Added `.github/workflows/codeql.yml` to automatically run GitHub CodeQL static analysis and surface vulnerabilities on the native Security tab.
- **Interactive GitHub YAML Issue Forms & Pages Portal**:
  - Migrated issue templates to interactive YAML forms (`.github/ISSUE_TEMPLATE/*.yml`) with OS dropdown selectors and added `config.yml` linking to security reporting and community discussions.
  - Added `.github/workflows/pages.yml` to automatically deploy documentation to GitHub Pages.

---

## [2.2.0] - 2026-10-26

### Added
- **Full Native macOS Compatibility & Cross-Platform Hardware Parity**:
  - **Native AppleScript Notification Center Integration**:
    - Implemented `send_macos_notification()` in `fleet/tools/system_tools.py` using AppleScript (`osascript`) with quotes and backslash escaping.
    - Unified `send_windows_notification()` and `send_notification()` as cross-platform routers directing notifications to macOS Notification Center on Darwin, `notify-send` on Linux, and WinRT Toast Notifications on Windows NT.
  - **macOS Memory & Hardware Telemetry**:
    - Implemented `_get_memory_status_darwin()` in `fleet/core/optimizer.py` utilizing `sysctl -n hw.memsize`, `sysctl -n vm.pagesize`, and `vm_stat` free/inactive/purgeable page metrics.
    - Implemented `_get_memory_status_linux()` reading `/proc/meminfo`.
    - Rewrote POSIX process inspection to use standard `ps -A -o comm,rss` with in-memory Python sorting, resolving GNU `--sort` incompatibilities on macOS BSD `ps`.
  - **Apple Keychain Services & Hardware-Backed Security**:
    - Integrated native macOS Keychain CLI (`/usr/bin/security add-generic-password` and `find-generic-password`) into `fleet/core/crypto_vault.py` and `fleet/config.py`, providing hardware-backed Secure Enclave credential protection with zero pip dependencies.
    - Hardened master key file permissions to POSIX `chmod 0600` on non-NT systems.
  - **macOS System Optimizer Subsystems**:
    - Added Directory Services DNS resolver cache flushing (`dscacheutil -flushcache` and `killall -HUP mDNSResponder`).
    - Added macOS RAM optimization sweep via native `purge` command.
    - Added macOS LaunchAgents startup inspection (`~/Library/LaunchAgents` and `/Library/LaunchAgents`) and one-click macOS System Settings launcher (`x-apple.systempreferences:com.apple.LoginItems-Settings.extension`).
  - **Apple Silicon & Homebrew CLI Auto-Discovery**:
    - Added path resolution in `fleet/core/dev_tools.py` for `/opt/homebrew/bin` (Apple Silicon M-series), `/usr/local/bin` (Intel Mac), and `/Applications/` bundles for `agy`, `gh`, `claude`, `gemini`, `aws`, `ollama`, `code`, and `cursor`.
  - **Cross-Platform Continuous Integration Matrix**:
    - Added `macos-latest` to `.github/workflows/ci.yml` matrix alongside `ubuntu-latest` and `windows-latest` across Python 3.10, 3.11, and 3.12.

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

