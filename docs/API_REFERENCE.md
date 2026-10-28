# 📡 Personal Agentic Fleet — Complete API, MCP & Command Reference

This document provides a comprehensive reference for the Fleet REST API, Model Context Protocol (FastMCP) tools, and Dashboard Console slash commands.

---

## 1. REST API Reference (Base URL: `http://127.0.0.1:7890`)

All responses return standard JSON with `Content-Type: application/json` unless otherwise specified.

### 1.1 Core System & Health Endpoints

| Method | Endpoint | Description | Request Body / Parameters | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard Single Page Application (SPA). | None | HTML Document (`text/html`) |
| `GET` | `/api/status` | System status, version, server timestamp, and primary drive disk usage. | None | `{"status": "online", "version": "2.0.0", "time": "ISO-8601", "disk": {...}}` |
| `GET` | `/api/version` | Semantic versioning metadata. | None | `{"version": "2.0.0", "name": "Personal Agentic Fleet", ...}` |
| `GET` | `/api/release_notes` | Current version release notes and changelog markdown. | None | `{"version": "2.0.0", "changelog_markdown": "..."}` |
| `GET` | `/api/logs` | Returns recent system and audit activities. | Query: `limit=15` | `[{"id": 1, "agent": "...", "action": "...", "timestamp": "..."}]` |
| `GET` | `/api/diagnostics/logs` | Returns recent structured JSON telemetry from the in-memory ring buffer. | Query: `limit=100`, `min_level=WARNING`, `level=ERROR`, `agent=...`, `search=...` | `{"status": "success", "logs": [...], "count": 10}` |
| `GET` | `/api/diagnostics/errors` | Error isolation endpoint returning recent warnings, errors, and failures from memory and disk. | Query: `limit=50`, `source=ring\|disk\|both` | `{"status": "success", "ring_buffer_errors": [...], "disk_error_log": [...], "count": 2}` |
| `GET` | `/api/diagnostics/log-analysis` | Returns latest proactive log scan triage, active diagnostic issues, and system health index. | None | `{"status": "success", "report": {"scan_id": "...", "system_health_index": 100.0, "findings": [...]}}` |
| `POST` | `/api/diagnostics/log-analysis/run` | Triggers immediate on-demand proactive log scan and autonomous self-healing improvements. | `{}` | `{"status": "success", "report": {"scan_id": "...", "improvements_applied_count": 1, ...}}` |
| `GET` | `/api/diagnostics/auto-improvements` | Historical ledger of automated self-healing improvements executed by the system. | Query: `limit=50` | `{"status": "success", "improvements": [...], "stats": {...}, "count": 12}` |
| `GET` | `/api/diagnostics/crashes` | Lists recorded sanitized crash forensic dump reports in `fleet/data/crash_reports/`. | None | `{"status": "success", "reports": [...], "count": 3}` |
| `GET` | `/api/mind/status` | Holistic telemetry for the 4 cognitive layers (Brain, Consciousness, Subconsciousness, Soul) and Cognitive Harmony Index. | None | `{"status": "success", "cognitive_harmony_index": 100.0, "overall_state": "ENLIGHTENED", "layers": {...}}` |
| `GET` | `/api/mind/insights` | Distilled subconscious dream insights, latent habits, and friction patterns. | Query: `limit=30` | `{"status": "success", "insights": [...], "count": 3}` |
| `GET` | `/api/mind/critiques` | Conscious executive self-critique evaluations stream. | Query: `limit=30` | `{"status": "success", "critiques": [...], "count": 12}` |
| `GET` | `/api/mind/soul/audits` | Moral alignment audits against Sovereign Privacy, $0.00 Frugality, and Metabolic Care. | Query: `limit=10` | `{"status": "success", "audits": [...], "count": 2}` |
| `POST` | `/api/mind/critique` | Evaluates an agent action execution against structural soundness and intent fidelity. | `{"agent": "...", "action": "...", "input": {...}, "result": {...}}` | `{"status": "success", "critique": {"score": 95.0, "passed": true, ...}}` |
| `POST` | `/api/mind/dream` | Executes a subconscious dream cycle consolidating episodic memory into actionable wisdom. | `{"max_activities": 200}` | `{"status": "success", "insight": {"cycle_id": "...", "events_consolidated": 200, ...}}` |
| `POST` | `/api/mind/soul/audit` | Audits fleet actions against foundational ethical and wellbeing tenets. | `{}` | `{"status": "success", "audit": {"alignment_score": 100.0, "status": "PURE", ...}}` |
| `POST` | `/api/mind/self_improve` | Ascends the fleet to the next evolutionary generation with calibrated directives. | `{}` | `{"status": "ASCENDING", "generation": 2, "evolutionary_directives_applied": [...]}` |
| `POST` | `/api/mind/heal` | Triggers the brainstem autonomic self-healing reflex arc. | `{}` | `{"status": "HEALTHY", "health_score": 100.0, "anomalies_detected": [...], ...}` |

---

### 1.2 Multi-Hyperscaler & AI Developer Tool Endpoints

| Method | Endpoint | Description | Request Body / Parameters | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/hyperscalers/providers` | Lists all 7 hyperscaler providers and their configuration status. | None | `{"status": "success", "providers": [...]}` |
| `GET` | `/api/hyperscalers/dev_tools` | Probes for installed AI developer CLI tools (`agy`, `gemini`, `claude`, `gh`, `q`, `cursor`, `ollama`). | None | `{"status": "success", "tools": {...}}` |
| `POST` | `/api/hyperscalers/generate` | Dispatches prompt to any cloud hyperscaler or Tier 0 local engine. | `{"prompt": "...", "provider": "google\|microsoft\|aws\|anthropic\|openai\|ollama", "model": "..."}` | `{"status": "SUCCESS", "text": "...", "tokens_used": 0, "cost_usd": "$0.00"}` |
| `POST` | `/api/hyperscalers/dev_tools/claude_code` | Executes a terminal coding query via Anthropic Claude Code CLI (`claude -p`). | `{"prompt": "Refactor auth module"}` | `{"status": "success", "tool": "claude_code", "output": "..."}` |
| `POST` | `/api/hyperscalers/dev_tools/copilot` | Executes a shell query via GitHub Copilot CLI (`gh copilot suggest`). | `{"prompt": "git squash command", "type": "suggest"}` | `{"status": "success", "tool": "github_copilot_cli", "output": "..."}` |
| `POST` | `/api/hyperscalers/dev_tools/gemini_cli` | Executes a task via Google Gemini CLI (`gemini -p`). | `{"prompt": "Deploy Cloud Run"}` | `{"status": "success", "tool": "google_gemini_cli", "output": "..."}` |
| `POST` | `/api/hyperscalers/dev_tools/aws_q` | Executes a query via Amazon Q Developer CLI (`q chat`). | `{"prompt": "Create IAM role"}` | `{"status": "success", "tool": "aws_q_developer_cli", "output": "..."}` |
| `POST` | `/api/hyperscalers/dev_tools/sync_all_instructions` | Synchronizes `.github/copilot-instructions.md`, `CLAUDE.md`, and `GEMINI.md`. | `{}` | `{"status": "synced", "synced_files": [...]}` |
| `POST` | `/api/hyperscalers/configure_key` | Securely stores an API key in the Windows DPAPI hardware vault. | `{"provider": "google", "key": "AIza..."}` | `{"status": "success", "message": "Key securely stored"}` |

---

### 1.3 Tasks, Agenda & Routines Endpoints

| Method | Endpoint | Description | Request Body / Parameters | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/tasks` | Lists tasks with optional status filter (`pending`, `completed`). | Query: `status=pending` | `[{"id": 1, "title": "...", "priority": "P1", "status": "pending"}]` |
| `POST` | `/api/tasks` | Creates a new task. | `{"title": "Deploy v2", "description": "Release", "priority": "P1"}` | `{"id": 1, "status": "created"}` |
| `POST` | `/api/tasks/toggle` | Toggles a task between pending and completed. | `{"id": 1}` | `{"status": "updated", "task_id": 1, "new_status": "completed"}` |
| `POST` | `/api/tasks/delete` | Permanently deletes a task. | `{"id": 1}` | `{"status": "deleted", "id": 1}` |
| `GET` | `/api/routines` | Lists daily habits and completion status for today. | None | `[{"id": 1, "title": "Coffee", "time_target": "08:00", "completed_today": true}]` |
| `POST` | `/api/routines/toggle` | Toggles today's completion status for a habit routine. | `{"id": 1}` | `{"status": "toggled", "id": 1}` |
| `GET` | `/api/briefing` | Generates today's dynamic morning briefing. | None | `{"headline": "...", "top_focus": [...], "upcoming_meetings": [...]}` |

---

### 1.5 Automated Agent Schedules Endpoints

| Method | Endpoint | Description | Request Body / Parameters | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/schedules` | Lists all automated agent schedules with next/last run times and active status. | None | `{"status": "success", "schedules": [...], "timezone": "Asia/Kolkata"}` |
| `POST` | `/api/schedules/toggle` | Enables or disables an automated agent schedule. | `{"id": "overview_morning_briefing", "enabled": false}` | `{"status": "success", "id": "...", "enabled": false}` |
| `POST` | `/api/schedules/run` | Triggers an immediate ad-hoc or scheduled agent task run. | `{"id": "health_smoothie_reminder"}` or `{"agent": "health", "task": "smoothie_reminder"}` | `{"id": "...", "agent": "health", "status": "SUCCESS", "duration": 0.05, ...}` |
| `POST` | `/api/schedules/reload` | Dynamically reloads schedule configurations from `schedules.yaml` and `fleet.yaml`. | `{}` | `{"status": "success", "count": 13}` |

---

| Method | Endpoint | Description | Request Body / Parameters | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/antigravity/models` | Lists available LLM models and currently active model. | None | `{"models": [...], "active_model": "gemini-3.8-flash-high"}` |
| `POST` | `/api/antigravity/models` | Changes the active model across all agents. | `{"model": "claude-3-7-sonnet"}` | `{"status": "success", "active_model": "claude-3-7-sonnet"}` |
| `GET` | `/api/antigravity/usage` | Detailed session token usage, token limit, and cost breakdown. | None | `{"cost_usd": "$0.00", "tokens_used": 18450, "context_window": "1,000,000 Tokens"}` |
| `GET` | `/api/antigravity/tokens` | Live token health status and warning state. | Query: `simulate=warning\|exhausted` | `{"status": "ok", "percent_used": 1.8, "is_exhausted": false}` |
| `POST` | `/api/antigravity/command` | Dispatches user prompt from the Command Console. | `{"command": "/briefing", "images": []}` | `{"status": "success", "type": "briefing", "message": "..."}` |
| `POST` | `/api/antigravity/upload` | Uploads an image with SHA-256 deduplication to prevent duplicate token spend. | `{"filename": "shot.png", "data": "data:image/png;base64,..."}` | `{"filename": "shot.png", "url": "/api/antigravity/media/shot.png"}` |
| `GET` | `/api/antigravity/queue` | Returns active parallel agent workers and pending queue. | None | `{"status": "idle", "active_agents_count": 0, "queue_length": 0}` |
| `POST` | `/api/antigravity/fast_track` | Drains queue into available parallel agent slots. | `{}` | `{"status": "success", "launched_count": 2}` |
| `POST` | `/api/antigravity/parallel_limit`| Sets max concurrent parallel worker agents (1–8). | `{"limit": 4}` | `{"max_parallel_agents": 4}` |

---

### 1.5 PC Performance Optimizer Endpoints

| Method | Endpoint | Description | Request Body | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/optimizer/diagnostics` | Full system health score (0–100), RAM, disk, temp bloat, and top processes. | None | `{"health_score": 92, "score_status": "Excellent", "top_processes": [...]}` |
| `POST` | `/api/optimizer/clean_temp` | Purges stale temporary files from user temp directory. | `{}` | `{"status": "success", "deleted_files": 12, "reclaimed_mb": 45.2}` |
| `POST` | `/api/optimizer/flush_dns` | Flushes native Windows DNS resolver cache (`ipconfig /flushdns`). | `{}` | `{"status": "success", "message": "Successfully flushed..."}` |
| `POST` | `/api/optimizer/purge_caches` | Purges workspace `__pycache__` and `.pyc` files. | `{}` | `{"status": "success", "removed_files": 25, "reclaimed_mb": 4.1}` |
| `POST` | `/api/optimizer/optimize_ram` | Performs garbage collection and sweeps process working sets (`EmptyWorkingSet`). | `{}` | `{"status": "success", "freed_mb": 180.5, "memory_load": 42}` |
| `POST` | `/api/optimizer/auto_tune` | 1-Click complete optimization (Temp + DNS + Caches + RAM). | `{}` | `{"status": "success", "reclaimed_mb": 49.3}` |

---

### 1.6 Health, Metabolic & Strength Endpoints

| Method | Endpoint | Description | Request Body | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/health/summary` | Today's hydration, medication checklist, vitals, and strength workout. | None | `{"hydration": {...}, "medications": [...], "workout": {...}}` |
| `POST` | `/api/health/water` | Logs water intake delta. | `{"delta_glasses": 1, "delta_ml": 250}` | `{"glasses": 4, "percentage": 50.0}` |
| `POST` | `/api/health/water/goal` | Updates daily hydration goal. | `{"goal_ml": 3000}` | `{"goal_ml": 3000}` |
| `POST` | `/api/health/medications/toggle`| Marks prescription as taken/unmarked today. | `{"id": 1}` | `{"status": "toggled", "taken": true}` |
| `POST` | `/api/health/metrics/log` | Logs vital metric (`weight_kg`, `fasting_bg`, `resting_hr`). | `{"metric_type": "weight_kg", "value": 72.5}` | `{"status": "logged", "id": 1}` |

---

### 1.7 Security, Audit & CycloneDX SBOM Endpoints

| Method | Endpoint | Description | Request Body | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/security/scan` | Runs full 12-layer security audit locally and returns results. | None | `{"status": "PASS", "score": 100, "checks": [...], "findings": []}` |
| `GET` | `/api/security/latest` | Returns cached results of the most recent security scan. | None | `{"status": "PASS", "score": 100, ...}` |
| `GET` | `/api/security/sbom` | Generates on-demand CycloneDX v1.5 SBOM with SHA-256 digests. | None | Standard CycloneDX v1.5 JSON |

---

### 1.8 Agent Registry, Customization & Package Scaffolding Endpoints

| Method | Endpoint | Description | Request Body | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/fleet/agents` | Lists UI manifests for all loaded agents in sorted tab order. | None | `{"status": "ok", "count": 7, "agents": [...]}` |
| `GET` | `/api/fleet/agents/{id}/config` | Returns an agent's active configuration, preferred provider/model, and prompt. | None | `{"status": "ok", "id": "health", "config": {...}, "preferred_provider": "auto"}` |
| `POST` | `/api/fleet/agents/{id}/config` | Dynamically customizes any agent (name, icon, order, provider, model, prompt). | `{"name": "...", "icon": "...", "provider": "anthropic", "model": "..."}` | `{"status": "success", "agent": {...}}` |
| `POST` | `/api/fleet/agents/{id}/reset` | Resets an agent's configuration back to built-in package defaults. | `{}` | `{"status": "success", "agent": {...}}` |
| `POST` | `/api/fleet/agents/custom/create` | Scaffolds a new isolated custom agent in `fleet/data/user/custom_agents/`. | `{"id": "my_agent", "name": "...", "icon": "✨", "permissions": ["db:read", "ui:render"]}` | `{"status": "success", "agent": {...}}` |
| `GET` | `/api/fleet/agents/{id}/style.css` | Serves scoped CSS styling for the agent's isolated UI panel. | None | `text/css` |
| `GET` | `/api/fleet/agents/{id}/script.js` | Serves scoped JavaScript for the agent's isolated UI panel. | None | `application/javascript` |
| `GET` | `/api/settings` | Returns global fleet settings, agent list, active/disabled counts. | None | `{"status": "ok", "settings": {...}, "active_agents_count": 7, "total_agents_count": 8}` |
| `POST` | `/api/settings` | Updates global fleet settings, preferences, and notifications. | `{"settings": {"timezone": "Asia/Kolkata", "theme": "dark"}}` | `{"status": "success", "updated_keys": [...]}` |
| `POST` | `/api/settings/agents/toggle` | Activates or disables an agent dynamically at runtime. | `{"id": "optimizer", "enabled": false}` | `{"status": "success", "agent_id": "optimizer", "enabled": false}` |
| `GET` | `/api/settings/agents/schema` | Retrieves an agent's manifest and dynamic settings schema. | Query: `id=health` | `{"status": "ok", "schema": {...}}` |
| `POST` | `/api/settings/agents/configure` | Saves agent-specific custom settings schema values. | `{"id": "weather", "settings": {"default_city": "Tokyo"}}` | `{"status": "success", "saved": true}` |
| `GET` | `/api/settings/agents/catalog` | Lists downloadable remote agents catalog with installation status. | None | `{"status": "ok", "catalog": [...], "total_available": 10}` |
| `POST` | `/api/settings/agents/catalog/install` | Downloads and installs an agent package from the catalog into custom agents. | `{"id": "home_assistant"}` | `{"status": "success", "installed": true, "name": "Home Assistant"}` |
| `GET` | `/api/settings/updates` | Checks GitHub releases for newer version availability. | Query: `refresh=true` | `{"status": "ok", "update_available": true, "latest_version": "2.1.0", "current_version": "2.0.0"}` |
| `POST` | `/api/settings/updates/apply` | Downloads and applies release updates from GitHub with automatic pre-update backup. | `{}` | `{"status": "success", "message": "Updated to v2.1.0"}` |

---

## 2. Model Context Protocol (FastMCP) Tools Reference

Personal Agentic Fleet registers as an MCP server under the name `personal-fleet`. Connect via `mcp.run(transport="stdio")` in `fleet/mcp_server.py`.

```json
{
  "mcpServers": {
    "personal-fleet": {
      "command": "python",
      "args": ["-m", "fleet.mcp_server"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\personal-agentic-fleet"
      }
    }
  }
}
```

### Available MCP Tools

| MCP Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| `fleet_get_daily_briefing` | Returns today's morning briefing, high-priority (P1) tasks, habit completion %, and focus summary. Uses delta-only caching. | None |
| `fleet_add_task` | Adds a new task to your personal task board. | `title` (str, req), `priority` ('P1'/'P2'/'P3'), `description` (str), `due_date` (str) |
| `fleet_list_tasks` | Lists tasks with optional status filter (`pending`, `completed`, or None for all). | `status` (str, opt), `limit` (int, default=15) |
| `fleet_complete_task` | Marks a task as completed by its integer ID. | `task_id` (int, req) |
| `fleet_list_routines` | Lists daily habits and completion checkmarks for today. | None |
| `fleet_toggle_routine` | Toggles today's completed status of a daily routine by its ID. | `routine_id` (int, req) |
| `fleet_send_notification` | Sends an immediate native Windows Toast alert. | `title` (str, req), `message` (str, req) |
| `fleet_scan_directory` | Scans a folder on your machine and categorizes file types, sizes, and count. | `path` (str, default="~/Downloads") |
| `fleet_classify_recent_emails`| Deterministically classifies Gmail threads from this month and last month into 5 folders. | `dry_run` (bool, default=False), `auto_archive_ignore` (bool) |
| `fleet_list_hyperscalers_and_tools`| Lists all supported hyperscalers (Google, Microsoft, AWS, Anthropic, OpenAI, Ollama) and detected dev tools. | None |
| `fleet_query_hyperscaler` | Dispatches an inference prompt through the Fleet Multi-Hyperscaler Gateway with Tier 0 local caching. | `prompt` (str, req), `provider` ('google'/'microsoft'/'aws'/'anthropic'/'openai'/'ollama'), `model` (str) |
| `fleet_run_developer_tool` | Invokes an AI developer tool across `'copilot'`, `'claude_code'`, `'gemini_cli'`, or `'aws_q'`. | `tool_name` (str, req), `prompt` (str, req) |
| `fleet_customize_agent` | Dynamically customizes any agent's display name, icon, order, provider, model, or system prompt. | `agent_id` (str, req), `name` (str), `icon` (str), `order` (int), `provider` (str), `model` (str), `system_prompt` (str) |
| `fleet_create_custom_agent` | Scaffolds a new isolated custom agent with manifest, backend logic, and UI pane in user vault. | `agent_id` (str, req), `name` (str, req), `icon` (str), `description` (str), `order` (int) |
| `fleet_list_schedules` | Lists all recurring automated agent schedules, frequencies, trigger times, and live status. | None |
| `fleet_toggle_schedule` | Enables or disables an automated agent schedule by its unique ID. | `schedule_id` (str, req), `enabled` (bool, opt) |
| `fleet_run_scheduled_task` | Triggers an immediate manual execution of any agent schedule on demand. | `schedule_id` (str, opt), `agent` (str, opt), `task` (str, opt) |

---

## 3. Web Dashboard Command Console & Slash Commands

Enter these commands into the Web Dashboard Console at the bottom of the screen:

- `/task <title> | <description>`: Creates a new task.
- `/tasks`: Lists your top pending tasks.
- `/briefing`: Generates a fresh morning briefing on demand.
- `/sync`: Runs a 2-month Gmail classification sweep.
- `/notify <message>`: Dispatches an immediate Windows Toast notification.
- `/providers` or `/tools`: Shows live connection status across all hyperscalers and dev tools.
- `/copilot <query>`: Runs prompt through GitHub Copilot CLI.
- `/claude <query>`: Runs prompt through Anthropic Claude Code CLI.
- `/gemini <query>`: Runs prompt through Google Gemini CLI.
- `/vertex <query>`: Dispatches prompt to Google Cloud Vertex AI.
- `/azure <query>`: Dispatches prompt to Microsoft Azure OpenAI / Foundry.
- `/aws <query>` or `/bedrock <query>`: Dispatches prompt to Amazon Bedrock Runtime.
- `/ollama <query>`: Dispatches prompt to Local Ollama (0 cloud tokens).
- `/security`: Runs the 12-layer security scanner and displays health score.
- `/optimizer`: Shows current RAM, disk, and performance diagnostics.

---

## 4. Unified Fleet Command Line Interface (CLI)

The Personal Agentic Fleet provides a comprehensive terminal interface accessible directly via `fleet <command>` or `python -m fleet <command>`:

| Command | Arguments / Flags | Description |
| :--- | :--- | :--- |
| `fleet start` | `--port <int>`, `--host <str>`, `--no-browser`, `-d/--daemon` | Launches the web dashboard and background routine daemon. Supports foreground or silent background daemon modes. |
| `fleet stop` | None | Gracefully signals and stops running Fleet background processes and frees listening ports. |
| `fleet status` | `--json` | Checks daemon liveness, memory WorkingSet (MB), database size, active agents, and Cognitive Harmony Index. |
| `fleet doctor` | `--strict`, `--json` | Executes the strict 7-point Fleet Doctor invariant checks (Python version, TLS 1.3, NTFS ACLs, SQLite integrity). |
| `fleet mind` | `--status`, `--dream`, `--soul`, `--heal`, `--improve`, `--critique <agent> <action>`, `--json` | Introspects or commands the 4-layer Cognitive Fleet Mind (Brain, Consciousness, Subconsciousness, Soul). |
| `fleet agents list` | None | Displays formatted terminal table of all registered modular agents, versions, enabled status, and permissions. |
| `fleet agents enable` | `<agent_id>` | Dynamically activates an agent at runtime. |
| `fleet agents disable` | `<agent_id>` | Dynamically deactivates an agent at runtime without server restart. |
| `fleet agents info` | `<agent_id>` | Outputs complete UI and configuration manifest for the designated agent. |
| `fleet agents create` | Interactive | Launches terminal wizard to scaffold a new isolated agent in the user vault. |
| `fleet security` | `--strict`, `--json` | Runs the deterministic 12-layer security, secret, and PII scanner (target score: 100/100). |
| `fleet heal` | `--force`, `--json` | Analyzes application and crash logs proactively, executing autonomous self-healing routines. |
| `fleet test` | `--coverage`, `--fast` | Executes the comprehensive unit test suite and optional code coverage report. |
| `fleet wiki` | `--dry-run` | Synchronizes documentation corpus to the GitHub Wiki git repository. |
| `fleet version` | None | Displays version, Python interpreter details, and operating system platform. |

<!-- AUTO-API-ROUTES:START -->
## 🔄 Complete Live REST API Route Inventory (`109` Endpoints — `v2.9.7`)

This table is **automatically introspected from `fleet/api/*.py` AST decorators** on every release by `fleet.tools.doc_wiki_enhancer`:

| Method | Endpoint Path | Handler & Source File | Description |
| :---: | :--- | :--- | :--- |
| `GET` | `/api/antigravity/transcript` | `get_transcript` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `get_transcript` in `fleet/api/antigravity_api.py`. |
| `GET` | `/api/antigravity/models` | `get_models` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `get_models` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/models` | `post_models` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_models` in `fleet/api/antigravity_api.py`. |
| `GET` | `/api/antigravity/usage` | `get_usage` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `get_usage` in `fleet/api/antigravity_api.py`. |
| `GET` | `/api/antigravity/tokens` | `get_tokens` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `get_tokens` in `fleet/api/antigravity_api.py`. |
| `GET` | `/api/antigravity/queue` | `get_queue` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `get_queue` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/command` | `post_command` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_command` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/upload` | `post_upload` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_upload` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/queue/cancel` | `cancel_queue` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `cancel_queue` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/tokens/resume` | `resume_tokens` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `resume_tokens` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/fast_track` | `post_fast_track` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_fast_track` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/parallel_limit` | `post_parallel_limit` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_parallel_limit` in `fleet/api/antigravity_api.py`. |
| `POST` | `/api/antigravity/tokens/simulate` | `post_simulate_tokens` ([`fleet/api/antigravity_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/antigravity_api.py)) | Handler `post_simulate_tokens` in `fleet/api/antigravity_api.py`. |
| `GET` | `/api/backlog` | `get_backlog` ([`fleet/api/backlog_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/backlog_api.py)) | Handler `get_backlog` in `fleet/api/backlog_api.py`. |
| `POST` | `/api/backlog` | `add_backlog_item` ([`fleet/api/backlog_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/backlog_api.py)) | Handler `add_backlog_item` in `fleet/api/backlog_api.py`. |
| `POST` | `/api/backlog/update` | `update_backlog_item` ([`fleet/api/backlog_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/backlog_api.py)) | Handler `update_backlog_item` in `fleet/api/backlog_api.py`. |
| `POST` | `/api/backlog/delete` | `delete_backlog_item` ([`fleet/api/backlog_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/backlog_api.py)) | Handler `delete_backlog_item` in `fleet/api/backlog_api.py`. |
| `GET` | `/api/emails` | `get_emails` ([`fleet/api/email_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/email_api.py)) | Handler `get_emails` in `fleet/api/email_api.py`. |
| `GET` | `/api/emails/body` | `get_email_body` ([`fleet/api/email_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/email_api.py)) | Handler `get_email_body` in `fleet/api/email_api.py`. |
| `POST` | `/api/emails/sync` | `sync_emails` ([`fleet/api/email_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/email_api.py)) | Handler `sync_emails` in `fleet/api/email_api.py`. |
| `POST` | `/api/emails/unsubscribe` | `unsubscribe_email` ([`fleet/api/email_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/email_api.py)) | Handler `unsubscribe_email` in `fleet/api/email_api.py`. |
| `GET` | `/api/health/summary` | `get_health_summary` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_health_summary` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/water` | `get_water` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_water` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/water` | `log_water` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `log_water` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/water/goal` | `set_water_goal` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `set_water_goal` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/medications` | `get_medications` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_medications` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/medications` | `add_medication` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `add_medication` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/medications/toggle` | `toggle_medication` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `toggle_medication` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/medications/delete` | `delete_medication` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `delete_medication` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/trends` | `get_health_trends` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_health_trends` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/metrics/log` | `log_health_metric` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `log_health_metric` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/profile` | `get_health_profile` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_health_profile` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/profile` | `update_health_profile` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `update_health_profile` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/videos` | `get_exercise_videos` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_exercise_videos` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/image` | `get_health_image` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_health_image` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/video/stream` | `stream_video` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `stream_video` in `fleet/api/health_api.py`. |
| `POST` | `/api/health/video/open_system` | `open_video_in_system` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `open_video_in_system` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/strength_plan` | `get_strength_plan` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_strength_plan` in `fleet/api/health_api.py`. |
| `GET` | `/api/health/exercise_plan` | `get_exercise_plan` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `get_exercise_plan` in `fleet/api/health_api.py`. |
| `GET` | `/api/hyperscalers/providers` | `get_hyperscaler_providers` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Returns list of supported hyperscalers and their configured models. |
| `GET` | `/api/hyperscalers/dev_tools` | `get_developer_tools_status` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Returns detection status for GitHub Copilot, Claude Code, Antigravity, Gemini CLI, Amazon Q, Cursor, VS Code, and Ollama. |
| `POST` | `/api/hyperscalers/generate` | `post_hyperscaler_generate` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Executes a completion request through the unified HyperscalerGateway. |
| `POST` | `/api/hyperscalers/dev_tools/claude_code` | `post_execute_claude_code` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Executes a command via Claude Code CLI with Anthropic Direct fallback. |
| `POST` | `/api/hyperscalers/dev_tools/copilot` | `post_execute_copilot` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Executes a command via GitHub Copilot CLI with Azure OpenAI / GitHub Models fallback. |
| `POST` | `/api/hyperscalers/dev_tools/gemini_cli` | `post_execute_gemini_cli` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Executes a command via Google Gemini CLI with Gemini REST / Vertex AI fallback. |
| `POST` | `/api/hyperscalers/dev_tools/aws_q` | `post_execute_aws_q` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Executes a command via Amazon Q Developer CLI with AWS Bedrock fallback. |
| `POST` | `/api/hyperscalers/dev_tools/sync_copilot_instructions` | `post_sync_copilot_instructions` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Syncs .github/copilot-instructions.md for VS Code & Copilot alignment. |
| `POST` | `/api/hyperscalers/dev_tools/sync_all_instructions` | `post_sync_all_instructions` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Syncs .github/copilot-instructions.md, CLAUDE.md, and GEMINI.md across workspace. |
| `POST` | `/api/hyperscalers/configure_key` | `post_configure_hyperscaler_key` ([`fleet/api/hyperscalers_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/hyperscalers_api.py)) | Stores an API key or endpoint in Windows Credential Manager (DPAPI keyring) and runtime environment. |
| `GET` | `/api/optimizer/diagnostics` | `get_diagnostics` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `get_diagnostics` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/clean_temp` | `post_clean_temp` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_clean_temp` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/flush_dns` | `post_flush_dns` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_flush_dns` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/purge_caches` | `post_purge_caches` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_purge_caches` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/optimize_ram` | `post_optimize_ram` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_optimize_ram` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/open_startup` | `post_open_startup` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_open_startup` in `fleet/api/optimizer_api.py`. |
| `POST` | `/api/optimizer/auto_tune` | `post_auto_tune` ([`fleet/api/optimizer_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/optimizer_api.py)) | Handler `post_auto_tune` in `fleet/api/optimizer_api.py`. |
| `GET` | `/api/settings` | `get_fleet_settings` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Returns global fleet settings, preferences, and all discovered agents with activation state. |
| `POST` | `/api/settings` | `update_fleet_settings` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Updates global fleet settings and preferences in the database. |
| `POST` | `/api/settings/agents/toggle` | `toggle_agent_activation` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Activates or deactivates an agent by ID at runtime and persists state. |
| `POST` | `/api/settings/agents/customize` | `customize_agent_settings` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Customizes an agent's display properties, LLM model, prompt, or default status. |
| `POST` | `/api/settings/agents/reset` | `reset_agent_settings` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Resets an agent back to factory built-in configuration. |
| `POST` | `/api/settings/backup/snapshot` | `create_backup_snapshot` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Creates an immediate snapshot backup of the database and agent overrides. |
| `GET` | `/api/settings/version` | `get_fleet_version_status` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Returns the current running version, latest GitHub release version, and update status. |
| `POST` | `/api/settings/version/check` | `check_fleet_version_update` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Forces an immediate check against GitHub Releases for new updates. |
| `POST` | `/api/settings/version/upgrade` | `apply_fleet_update` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Downloads/applies the latest release from GitHub (via git pull or zipball). |
| `GET` | `/api/settings/agents/catalog` | `get_agent_catalog_list` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Returns downloadable agents catalog with current installation status. |
| `POST` | `/api/settings/agents/catalog/install` | `install_catalog_agent` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Downloads and installs a new agent from the catalog into custom_agents. |
| `POST` | `/api/studio/synthesize` | `synthesize_agent_studio_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-01: Zero-Code Natural-Language Agent Studio synthesizer endpoint. |
| `POST` | `/api/settings/agents/create` | `create_new_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Scaffolds, registers, and activates a brand-new agent package in the user custom agents vault. |
| `GET` | `/api/discovery/recommendations` | `get_discovery_recommendations_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-02: Returns ranked agent recommendations mined from local workstation telemetry ($0.00). |
| `POST` | `/api/discovery/spawn` | `spawn_discovery_recommendation_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-02 -> UX-01: Scaffolds and activates a recommended agent in 1 click. |
| `GET` | `/api/playbooks` | `get_playbooks_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Lists all configured multi-agent playbooks. |
| `POST` | `/api/playbooks` | `save_playbook_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Creates or updates a multi-agent playbook. |
| `POST` | `/api/playbooks/run` | `run_playbook_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Executes a multi-agent playbook immediately. |
| `GET` | `/api/agents/export` | `export_agent_pack_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-04: Exports an agent as a SHA-256 verified .fleetagent JSON bundle. |
| `POST` | `/api/agents/import` | `import_agent_pack_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-04: Audits and imports a .fleetagent JSON bundle into custom_agents. |
| `GET` | `/api/omnibar/commands` | `get_omnibar_commands_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-05: Lists all @agent slash commands and omnibar shortcuts across active agents. |
| `POST` | `/api/omnibar/execute` | `execute_omnibar_query_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-05: Executes an Omnibar @agent command or Tier-0 query and returns an inline card. |
| `GET` | `/api/briefing` | `get_briefing` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_briefing` in `fleet/api/system_api.py`. |
| `GET` | `/api/logs` | `get_logs` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_logs` in `fleet/api/system_api.py`. |
| `GET` | `/api/status` | `get_status` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_status` in `fleet/api/system_api.py`. |
| `GET` | `/api/version` | `get_version` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_version` in `fleet/api/system_api.py`. |
| `GET` | `/api/release_notes` | `get_release_notes` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_release_notes` in `fleet/api/system_api.py`. |
| `POST` | `/api/notify` | `post_notify` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_notify` in `fleet/api/system_api.py`. |
| `GET` | `/api/test_results` | `get_test_results` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_test_results` in `fleet/api/system_api.py`. |
| `POST` | `/api/run_tests` | `post_run_tests` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_run_tests` in `fleet/api/system_api.py`. |
| `GET` | `/api/security/scan` | `get_security_scan` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_security_scan` in `fleet/api/system_api.py`. |
| `POST` | `/api/security/scan` | `post_security_scan` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_security_scan` in `fleet/api/system_api.py`. |
| `GET` | `/api/security/sbom` | `get_security_sbom` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_security_sbom` in `fleet/api/system_api.py`. |
| `GET` | `/api/security/token_stats` | `get_security_token_stats` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_security_token_stats` in `fleet/api/system_api.py`. |
| `GET` | `/api/security/doctor` | `get_security_doctor` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_security_doctor` in `fleet/api/system_api.py`. |
| `GET` | `/api/diagnostics/log-analysis` | `get_log_analysis` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_log_analysis` in `fleet/api/system_api.py`. |
| `POST` | `/api/diagnostics/log-analysis/run` | `post_log_analysis_run` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_log_analysis_run` in `fleet/api/system_api.py`. |
| `GET` | `/api/diagnostics/auto-improvements` | `get_auto_improvements` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_auto_improvements` in `fleet/api/system_api.py`. |
| `GET` | `/api/mind/status` | `get_mind_status` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_mind_status` in `fleet/api/system_api.py`. |
| `GET` | `/api/mind/insights` | `get_mind_insights` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_mind_insights` in `fleet/api/system_api.py`. |
| `GET` | `/api/mind/critiques` | `get_mind_critiques` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_mind_critiques` in `fleet/api/system_api.py`. |
| `GET` | `/api/mind/soul/audits` | `get_mind_soul_audits` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `get_mind_soul_audits` in `fleet/api/system_api.py`. |
| `POST` | `/api/mind/critique` | `post_mind_critique` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_mind_critique` in `fleet/api/system_api.py`. |
| `POST` | `/api/mind/dream` | `post_mind_dream` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_mind_dream` in `fleet/api/system_api.py`. |
| `POST` | `/api/mind/soul/audit` | `post_mind_soul_audit` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_mind_soul_audit` in `fleet/api/system_api.py`. |
| `POST` | `/api/mind/self_improve` | `post_mind_self_improve` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_mind_self_improve` in `fleet/api/system_api.py`. |
| `POST` | `/api/mind/heal` | `post_mind_heal` ([`fleet/api/system_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/system_api.py)) | Handler `post_mind_heal` in `fleet/api/system_api.py`. |
| `GET` | `/api/tasks` | `get_tasks` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `get_tasks` in `fleet/api/tasks_api.py`. |
| `POST` | `/api/tasks` | `create_task` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `create_task` in `fleet/api/tasks_api.py`. |
| `POST` | `/api/tasks/toggle` | `toggle_task` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `toggle_task` in `fleet/api/tasks_api.py`. |
| `POST` | `/api/tasks/delete` | `delete_task` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `delete_task` in `fleet/api/tasks_api.py`. |
| `GET` | `/api/routines` | `get_routines` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `get_routines` in `fleet/api/tasks_api.py`. |
| `POST` | `/api/routines/toggle` | `toggle_routine` ([`fleet/api/tasks_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/tasks_api.py)) | Handler `toggle_routine` in `fleet/api/tasks_api.py`. |
<!-- AUTO-API-ROUTES:END -->
