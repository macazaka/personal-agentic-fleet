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
