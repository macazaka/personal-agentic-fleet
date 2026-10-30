# REST & SSE API Reference

The Agentic Fleet Control Center (AFCC) exposes a deterministic REST and Server-Sent Events (SSE) API on `http://127.0.0.1:7890`. All endpoints return standard JSON and execute locally with zero external network dependencies.

---

## 1. System Health & Real-Time Events

### `GET /api/status`
Returns live system health, daemon uptime, active agent counts, and hardware telemetry.

#### Response `200 OK`
```json
{
  "status": "ok",
  "version": "2.8.3",
  "port": 7890,
  "uptime_seconds": 1420,
  "active_agents_count": 7,
  "total_agents_count": 7,
  "security_score": 100,
  "harmony_score": 94.5,
  "memory_mb": 42.8,
  "cpu_percent": 1.2
}
```

---

### `GET /api/version`
Returns the currently running microkernel version.

#### Response `200 OK`
```json
{
  "status": "ok",
  "version": "2.8.3",
  "build": "stable"
}
```

---

### `GET /api/events` *(SSE Stream)*
Establishes a persistent Server-Sent Events connection for real-time telemetry, agent state transitions, and background notifications.

#### Event Stream Format
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"type": "heartbeat", "timestamp": "2026-10-28T11:00:00Z", "health_index": 100.0}

data: {"type": "agent_event", "agent": "health", "event": "water_logged", "amount": 0.5}
```

---

## 2. Cognitive Fleet Mind Endpoints

### `GET /api/mind/status`
Returns the live state of all 4 cognitive layers and the overall Cognitive Harmony Index.

#### Response `200 OK`
```json
{
  "status": "ok",
  "harmony_index": 92.4,
  "brain": {
    "event_bus_latency_ms": 0.42,
    "epistemic_records": 1284,
    "active_reflexes": ["memory_guard", "crash_reporter"]
  },
  "consciousness": {
    "focal_target": "overview",
    "attention_depth": 0.85,
    "recent_critique_average": 91.2
  },
  "subconscious": {
    "last_dream_cycle": "2026-10-28T09:30:00Z",
    "anomalies_healed_today": 3
  },
  "soul": {
    "privacy_violations": 0,
    "token_expenditure_usd": "$0.00",
    "tenets_enforced": 4
  }
}
```

---

### `POST /api/mind/dream`
Triggers an immediate Subconscious Dream Cycle to consolidate memory and run the AutoHealer log scanner.

#### Request Body
```json
{
  "force_checkpoint": true
}
```

#### Response `200 OK`
```json
{
  "status": "success",
  "dream_cycle_id": "DREAM-20261028-1115",
  "memories_consolidated": 18,
  "wal_checkpoints_flushed": true,
  "harmony_score_post": 95.0
}
```

---

## 3. Settings & Customization Endpoints

### `GET /api/settings`
Returns fleet preferences (active layout, visual theme, enabled agents).

#### Response `200 OK`
```json
{
  "status": "ok",
  "settings": {
    "layout": "sidebar_dock",
    "theme": "dark",
    "dark_mode": "true",
    "cost_optimization_policy": "LOWEST_COST_FIRST"
  },
  "available_layouts": [
    {"id": "sidebar_dock", "name": "Sidebar Dock"},
    {"id": "command_deck", "name": "Command Deck"},
    {"id": "launchpad_grid", "name": "Launchpad Grid"}
  ],
  "available_themes": [
    {"id": "dark", "name": "Midnight Obsidian"},
    {"id": "light", "name": "Clean Daylight"},
    {"id": "aurora", "name": "Nordic Aurora"},
    {"id": "midnight", "name": "Deep AMOLED"}
  ]
}
```

---

### `POST /api/settings`
Updates fleet-wide preferences (layout, theme, cost policies).

#### Request Body
```json
{
  "layout": "command_deck",
  "theme": "aurora"
}
```

#### Response `200 OK`
```json
{
  "status": "success",
  "settings": {
    "layout": "command_deck",
    "theme": "aurora"
  }
}
```

---

### `POST /api/settings/agents/toggle`
Dynamically activates or deactivates an agent.

#### Request Body
```json
{
  "id": "gmail",
  "enabled": false
}
```

#### Response `200 OK`
```json
{
  "status": "success",
  "agent_id": "gmail",
  "enabled": false
}
```

---

### `POST /api/settings/agents/config`
Updates agent-specific settings declared in its settings schema.

#### Request Body
```json
{
  "id": "health",
  "settings": {
    "daily_water_target_liters": 4.0,
    "daily_calorie_target": 2300
  }
}
```

#### Response `200 OK`
```json
{
  "status": "success",
  "agent_id": "health",
  "settings": {
    "daily_water_target_liters": 4.0,
    "daily_calorie_target": 2300
  }
}
```

---

### `GET /api/settings/agents/catalog`
Lists available remote and community agents available for installation.

#### Response `200 OK`
```json
{
  "status": "ok",
  "total_available": 6,
  "catalog": [
    {
      "id": "crypto_trader",
      "name": "Crypto Sentinel",
      "is_installed": false,
      "description": "Local DCA and cryptocurrency price tracker."
    },
    {
      "id": "home_assistant",
      "name": "Home Assistant Bridge",
      "is_installed": false,
      "description": "Local IoT light and climate automation."
    }
  ]
}
```

---

### `POST /api/settings/agents/catalog/install`
Installs an agent package from the catalog.

#### Request Body
```json
{
  "id": "home_assistant"
}
```

#### Response `200 OK`
```json
{
  "status": "success",
  "agent_id": "home_assistant",
  "path": "fleet/data/custom_agents/home_assistant"
}
```

---

## 4. Security & Diagnostic Endpoints

### `GET /api/security/scan`
Executes or retrieves the latest 12-layer security scanner audit report.

#### Query Parameters
- `refresh=true`: Forces an immediate re-scan.

#### Response `200 OK`
```json
{
  "status": "PASS",
  "score": 100,
  "passed_checks": 12,
  "total_checks": 12,
  "total_findings": 0,
  "files_scanned": 142,
  "cost_usd": "$0.00"
}
```

---

### `GET /api/security/sbom`
Retrieves the live CycloneDX 1.5 Software Bill of Materials (SBOM).

#### Response `200 OK`
```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "serialNumber": "urn:uuid:...",
  "metadata": {
    "component": {
      "name": "personal-agentic-fleet",
      "version": "2.8.3"
    }
  },
  "components": [...]
}
```

---

## 5. Tasks & Routines Endpoints

### `GET /api/tasks`
Returns list of priority tasks.

### `POST /api/tasks/add`
Creates a new priority task.
```json
{
  "title": "Review pull request #14",
  "priority": "p1"
}
```

### `POST /api/tasks/complete`
Marks a task as completed.
```json
{
  "id": 42
}
```

---

### `GET /api/routines`
Returns today's daily habit routines and streaks.

### `POST /api/routines/toggle`
Toggles completion of a daily habit routine.
```json
{
  "id": "morning_water",
  "completed": true
}
```

---

## 6. P1 UX & Agent-Simplicity Endpoints (`UX-01` – `UX-05`)

### `POST /api/studio/synthesize` (`UX-01`)
Synthesizes a complete, least-privilege Fleet agent specification (`manifest.json`, `agent.py`, 6 declarative UI widget blocks, and `schedules.yaml` cadence) from a plain-English description at `$0.00` token spend.

#### Request Body
```json
{
  "prompt": "Check my local git repos every evening at 6 PM and alert me if uncommitted changes exist"
}
```

---

### `GET /api/discovery/recommendations` (`UX-02`)
Mines 4 local privacy-preserving telemetry streams (dashboard task/activity logs, Win32 PSAPI memory/process clusters, Git repos, and `02-Paper-Trail` inbox triage) and returns ranked agent recommendations scored via $\mathcal{A}_p = \text{round}(0.35 F_p + 0.30 T_p + 0.20 R_p + 0.15 D_p, 1)$.

### `POST /api/discovery/spawn` (`UX-02` -> `UX-01`)
Scaffolds and hot-loads a recommended agent in 1 click using `recommendation_id`.
```json
{
  "recommendation_id": "rec_git_eod_sentinel"
}
```

---

### `GET /api/playbooks` & `POST /api/playbooks` (`UX-03`)
Lists or creates/updates deterministic multi-agent event chains (`WHEN [Trigger] -> IF [Condition] -> THEN [Step 1 -> Step 2 -> ...]`). Ships with 8 built-in playbooks (`morning_vitality_launchpad`, `high_ram_autonomic_relief`, `invoice_to_priority_task`, `evening_shutdown_and_dream`, `post_workout_hydration_boost`, `pre_commit_security_sentinel`, `afternoon_glucose_walk_nudge`, `weekly_roadmap_grooming`).

### `POST /api/playbooks/run` (`UX-03`)
Executes a multi-agent playbook immediately and returns step-by-step telemetry.
```json
{
  "playbook_id": "morning_vitality_launchpad"
}
```

---

### `GET /api/agents/export?id=<agent_id>` & `POST /api/agents/import` (`UX-04`)
Exports any installed or catalog agent as a `fleetagent-v1` JSON bundle signed with a SHA-256 cryptographic digest, or imports a `.fleetagent` bundle after verifying its SHA-256 digest, `ALLOWED_AGENT_PERMISSIONS`, and Python AST static security gate.

---

### `GET /api/omnibar/commands` & `POST /api/omnibar/execute` (`UX-05`)
Lists all `@agent` slash commands across active agents or executes a Unified `Ctrl+K` Omnibar query (`@discover`, `@studio <prompt>`, `@playbook <id>`, `@health water +2`, or Tier-0 natural language) returning an inline preview card in `< 30 ms`.
```json
{
  "query": "@discover"
}
```

<!-- AUTO-API-ROUTES:START -->
## 🔄 Complete Live REST API Route Inventory (`123` Endpoints — `v2.13.0`)

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
| `POST` | `/api/health/medications/update` | `update_medication` ([`fleet/api/health_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/health_api.py)) | Handler `update_medication` in `fleet/api/health_api.py`. |
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
| `POST` | `/api/settings/agents/delete` | `delete_custom_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Permanently deletes a custom/catalog agent from custom_agents and unregisters it live. |
| `POST` | `/api/settings/backup/snapshot` | `create_backup_snapshot` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Creates an immediate snapshot backup of the database and agent overrides. |
| `GET` | `/api/settings/version` | `get_fleet_version_status` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Returns the current running version, latest GitHub release version, and update status. |
| `POST` | `/api/settings/version/check` | `check_fleet_version_update` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Forces an immediate check against GitHub Releases for new updates. |
| `POST` | `/api/settings/version/upgrade` | `apply_fleet_update` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Downloads/applies the latest release from GitHub (via git pull or zipball). |
| `GET` | `/api/settings/agents/catalog` | `get_agent_catalog_list` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Returns downloadable agents catalog with current installation status. |
| `POST` | `/api/settings/agents/catalog/install` | `install_catalog_agent` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Downloads and installs a new agent from the catalog into custom_agents. |
| `GET` | `/api/studio/blueprints` | `get_studio_blueprints_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 2-6: Returns curated 1-click starter blueprints, Multi-Agent Squads, UI blocks, EventBus triggers, Outbound Actions, and Document Scenarios. |
| `POST` | `/api/studio/squads/deploy` | `deploy_agent_squad_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 6: Scaffolds, registers, schedules, and wires an entire Multi-Agent Squad in 1 click. |
| `POST` | `/api/studio/documents/analyze` | `analyze_studio_document_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 5 & Multi-Attachment Studio Workflow: Analyzes one or multiple uploaded attachments |
| `POST` | `/api/studio/dry_run` | `dry_run_agent_studio_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 2: Validates AST, sandbox permissions, and simulates an agent dry-run before activation. |
| `POST` | `/api/studio/synthesize` | `synthesize_agent_studio_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-01: Zero-Code Natural-Language Agent Studio synthesizer endpoint. |
| `POST` | `/api/studio/evolve/suggestions` | `generate_studio_evolve_suggestions_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | AI Evolution Advisor: Automatically analyzes an existing custom agent via AFCC's connected LLM |
| `POST` | `/api/studio/evolve/parse_custom` | `parse_custom_evolve_improvement_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Parses a user-entered custom evolution improvement into a structured Studio blueprint patch |
| `POST` | `/api/settings/agents/create` | `create_new_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Scaffolds, registers, schedules, and activates a brand-new custom agent package. |
| `POST` | `/api/settings/agents/evolve` | `evolve_custom_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 2 & 3: Evolves an existing custom agent's UI blocks, fields, schedule, triggers, and code in-place. |
| `GET` | `/api/settings/agents/revisions` | `list_custom_agent_revisions_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 4: Lists saved blueprint revision snapshots for an evolved custom agent. |
| `POST` | `/api/settings/agents/rollback` | `rollback_custom_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 4: Restores a custom agent's blueprint from a saved revision while preserving SQLite records. |
| `POST` | `/api/settings/agents/clone` | `clone_custom_agent_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 3: Clones an existing agent into a fresh custom agent blueprint without copying private SQLite data. |
| `POST` | `/api/studio/deep_build` | `deep_build_agent_studio_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 3: 1-Click 'Deep-Build with Antigravity' Direct Bridge. |
| `POST` | `/api/studio/events/emit` | `emit_studio_event_trigger_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | Phase 3: Dispatches a canonical Fleet EventBus trigger to all subscribed playbooks & custom agents. |
| `GET` | `/api/discovery/recommendations` | `get_discovery_recommendations_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-02: Returns ranked agent recommendations mined from local workstation telemetry ($0.00). |
| `POST` | `/api/discovery/spawn` | `spawn_discovery_recommendation_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-02 -> UX-01: Scaffolds, schedules, and activates a recommended agent in 1 click. |
| `GET` | `/api/playbooks` | `get_playbooks_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Lists all configured multi-agent playbooks. |
| `POST` | `/api/playbooks` | `save_playbook_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Creates or updates a multi-agent playbook. |
| `POST` | `/api/playbooks/run` | `run_playbook_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-03: Executes a multi-agent playbook immediately. |
| `GET` | `/api/agents/export` | `export_agent_pack_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-04: Exports an agent as a SHA-256 verified .fleetagent JSON bundle. |
| `POST` | `/api/agents/import` | `import_agent_pack_endpoint` ([`fleet/api/settings_api.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/api/settings_api.py)) | UX-04: Audits and imports a .fleetagent JSON bundle into custom_agents, syncing schedule & triggers. |
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
