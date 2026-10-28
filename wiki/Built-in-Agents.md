# Built-in Agents Matrix

Personal Agentic Fleet comes pre-packaged with **7 high-performance built-in agents**, each isolated in its own package under `fleet/agents/<agent_id>/` with a strict `manifest.json` permission contract, an `agent.py` lifecycle handler, and an isolated `ui/panel.html` view.

---

## 1. Agent Overview & Permission Summary

| Agent ID | Display Name | Version | Core Permissions | Primary Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| `overview` | **Fleet Overview & Tasks** | `1.0.0` | `db:read`, `db:write`, `ui:render` | Aggregated executive telemetry, priority task list, daily routine checklists, and morning briefing. |
| `health` | **Health & Wellness Sentinel** | `1.0.0` | `db:read`, `db:write`, `ui:render`, `notifications:send` | Daily hydration tracking, calorie targets, workout logging, and Traditional Strength Training Hub. |
| `antigravity` | **Antigravity Live Hub** | `1.0.0` | `db:read`, `ui:render`, `system:read` | Local Antigravity IDE monitor, AI agent status, context telemetry, and live prompt inspector. |
| `backlog` | **Feature Backlog & Kanban** | `1.0.0` | `db:read`, `db:write`, `ui:render` | Project roadmap, bug backlog, priority ranking (P0/P1/P2), and completion tracking. |
| `optimizer` | **PC & System Optimizer** | `1.0.0` | `db:read`, `db:write`, `ui:render`, `system:read`, `system:execute` | In-process system performance diagnostics, RAM/CPU monitoring, cache clearing, and process management. |
| `gmail` | **Gmail Inbox Intelligence** | `1.0.0` | `db:read`, `db:write`, `ui:render`, `network:http`, `secrets:read` | Zero-token deterministic rule-based email classification, spam filtration, and action-item extraction. |
| `pr_review` | **PR & Code Review Sentinel** | `1.0.0` | `db:read`, `db:write`, `ui:render`, `system:read` | Automated local PR analysis, CodeQL invariant checks, git diff inspection, and security audit verification. |

---

## 2. In-Depth Agent Specifications

### 2.1 Overview & Tasks (`overview`)
The central dashboard agent providing an executive summary of personal tasks, daily routines, and agent status.
- **Priority Task Management**: Add, filter, complete, and delete personal tasks with priority weighting.
- **Habit & Routine Tracking**: Interactive checkboxes for daily routines that reset deterministically at midnight.
- **Daily Briefing Integration**: Automatically surfaces the morning executive briefing synthesized by `fleet.core.briefing`.
- **Fleet Metric Aggregation**: Displays live count of installed agents, active agents, background daemon health, and security scores.

---

### 2.2 Health & Wellness Sentinel (`health`)
A comprehensive personal wellness tracker operating 100% locally with zero external health data leakage.
- **Hydration Tracker**: Incremental water intake logger (glasses / liters) with real-time progress bars against a customizable daily target (default: `3.5L`).
- **Nutrition & Calorie Target**: Calorie intake tracker comparing against personal nutritional targets.
- **Exercise, Videos & Traditional Strength Training Hub**:
  - Encapsulated strictly inside `<div id="viewHealth">` to prevent UI leakage into other agent tabs.
  - **Video Form Guides**: Embedded high-yield technique videos for squats, deadlifts, bench presses, and mobility work.
  - **Traditional Strength Training Logging**: Exercise selection, set/rep/weight logging, rest timers, and historical progress graphs.
  - **Workout Routine Templates**: Push/Pull/Legs, Upper/Lower, and Full Body routines with one-click session initiation.
- **Configurable Settings Schema**:
  - `daily_water_target_liters` (Float, Default: `3.5`)
  - `daily_calorie_target` (Integer, Default: `2500`)
  - `enable_hydration_reminders` (Boolean, Default: `true`)
  - `reminder_interval_minutes` (Integer, Default: `60`)

---

### 2.3 Antigravity Live Hub (`antigravity`)
The dedicated telemetry bridge between the personal workstation and Google DeepMind's Antigravity AI pair programming environment.
- **Live Connection Monitor**: Checks local connectivity with the Antigravity daemon and IDE extensions.
- **Context Window Telemetry**: Tracks active prompt context token count and rate-limit headroom.
- **Prompt & Action Inspector**: Displays recent agent operations, subagent invocations, and workspace file modifications.
- **Settings Schema**:
  - `poll_interval_seconds` (Integer, Default: `5`)
  - `log_level` (Select: `DEBUG`, `INFO`, `WARN`, Default: `INFO`)
  - `show_token_counter` (Boolean, Default: `true`)

---

### 2.4 Feature Backlog & Kanban (`backlog`)
A structured project management and roadmap agent designed for autonomous engineering tasks and feature tracking.
- **Priority Tiering**: Strict categorization across `P0 (Critical)`, `P1 (High)`, `P2 (Medium)`, and `P3 (Low)`.
- **Status Lifecycle**: Items progress through `Backlog` -> `In Progress` -> `Review` -> `Completed`.
- **Self-Healing Integration**: Automatically captures unresolved system issues surfaced by the `AutoHealer` log scanner and logs them as trackable backlog tickets.
- **Settings Schema**:
  - `default_filter` (Select: `All`, `Active`, `Completed`, Default: `Active`)
  - `auto_archive_days` (Integer, Default: `30`)

---

### 2.5 PC & System Optimizer (`optimizer`)
A deterministic operating system maintenance and hardware telemetry sentinel.
- **Hardware Telemetry**: Real-time RAM utilization, CPU load, and disk capacity without spawning heavy subprocesses (utilizes Win32 PSAPI on Windows, `sysctl` on macOS, and `/proc` on Linux).
- **One-Click Maintenance Actions**:
  - Clear temporary files and browser cache directories.
  - Flush local DNS resolver cache (`ipconfig /flushdns` on Windows, `resolvectl flush-caches` on Linux).
  - Check database compaction and trigger SQLite `VACUUM` / WAL checkpointing.
- **Settings Schema**:
  - `ram_alert_threshold_percent` (Integer, Default: `85`)
  - `enable_auto_dns_flush` (Boolean, Default: `false`)

---

### 2.6 Gmail Inbox Intelligence (`gmail`)
A privacy-first email triage assistant that categorizes and analyzes emails without sending any inbox data to third-party AI APIs.
- **Deterministic Rule-Based Triage**: Evaluates sender reputation, keywords, headers, and unsubscribe links locally.
- **Action Item Extraction**: Identifies invoices, calendar invites, package delivery notices, and security alerts.
- **OAuth Vault Security**: Tokens and OAuth secrets are encrypted at rest via the platform cryptographic vault (DPAPI / Keychain) in `fleet/data/user/`.
- **Settings Schema**:
  - `sync_interval_minutes` (Integer, Default: `15`)
  - `auto_archive_spam` (Boolean, Default: `false`)
  - `max_emails_per_sync` (Integer, Default: `50`)

---

### 2.7 PR & Code Review Sentinel (`pr_review`)
A continuous software engineering assistant designed for git repositories.
- **Local Diff Inspection**: Inspects staged changes, unstaged working trees, or branch differences.
- **CodeQL Invariant Checks**: Verifies that new code does not introduce security vulnerabilities (e.g. CWE-078 command injection, CWE-327 weak cryptography).
- **Test Integrity Audit**: Confirms all unit tests pass before a pull request or release tag is generated.
- **Settings Schema**:
  - `strict_mode` (Boolean, Default: `true`)
  - `target_branch` (String, Default: `main`)

