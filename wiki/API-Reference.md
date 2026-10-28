# API Reference Manual

The Agentic Fleet Control Center (AFCC) exposes a clean, zero-dependency REST and Server-Sent Events (SSE) API on port `7890`.

---

## Cognitive Fleet Mind Endpoints

### `GET /api/mind/status`
Returns the current holistic harmony score and state of the 4 cognitive layers.
```json
{
  "harmony_score": 96.5,
  "brain": {"synaptic_events_total": 412, "memory_nodes": 128},
  "consciousness": {"attention_focus": "idle", "average_critique_score": 94.2},
  "subconsciousness": {"last_dream_at": "2026-10-27 04:00:00", "healed_issues": 8},
  "soul": {"tenet_violations": 0, "privacy_boundary_status": "SECURE"}
}
```

### `POST /api/mind/critique`
Evaluates an action or output against the Conscious Self-Critique rubric.
- **Request Body:** `{"action": "string", "output": {...}}`
- **Response:** `{"status": "PASS", "conscious_score": 95, "token_waste": 0.0}`

### `GET /api/mind/events`
Server-Sent Events (SSE) stream broadcasting real-time synaptic events.

---

## Diagnostics & Autonomous Healing

### `GET /api/diagnostics/logs`
Returns structured application logs with query filtering (`level`, `limit`, `since`).

### `POST /api/diagnostics/heal`
Triggers an immediate proactive log scan and auto-healing cycle.
- **Response:** `{"status": "success", "improvements_applied": 2, "details": [...]}`

---

## Agent Management & Settings

### `GET /api/settings/agents`
Lists all installed agents, their activation state, and custom settings schemas.

### `POST /api/settings/agents/<id>/toggle`
Activates or disables an agent dynamically.
- **Request Body:** `{"enabled": true}`

### `POST /api/settings/agents/<id>/config`
Updates agent-specific configuration parameters.
- **Request Body:** `{"key": "value"}`

### `GET /api/settings/updates/check`
Queries GitHub Releases for newly published fleet versions.

### `GET /api/settings/agents/catalog`
Queries the remote verified agent registry for newly available agents.

### `POST /api/settings/agents/catalog/install`
Installs and activates a package from the agent catalog.
- **Request Body:** `{"agent_id": "weather_forecaster"}`

---

## 4. Unified Fleet CLI Reference

The fleet is fully controllable via the terminal (`fleet <cmd>` or `python -m fleet <cmd>`):

| Command | Key Arguments | Description |
| :--- | :--- | :--- |
| `fleet start` | `--port`, `--daemon`, `--no-browser` | Launches server and daemon (interactive or silent background) |
| `fleet stop` | None | Gracefully stops running fleet daemon and frees port 7890 |
| `fleet status` | `--json` | Health status, memory WorkingSet, DB size, and Cognitive Harmony |
| `fleet doctor` | `--strict`, `--json` | Strict 7-layer environment & security diagnostics |
| `fleet mind` | `--status`, `--dream`, `--soul`, `--heal`, `--json` | Introspect or trigger 4-layer Cognitive Fleet Mind operations |
| `fleet agents` | `list`, `enable <id>`, `disable <id>`, `info <id>`, `create` | Complete modular agent lifecycle management |
| `fleet security`| `--strict`, `--json` | 12-layer security, secret, and PII audit (100/100 target) |
| `fleet heal` | `--force`, `--json` | Proactive log analysis and autonomous remediation |
| `fleet test` | `--coverage`, `--fast` | Comprehensive test runner and coverage reports |
| `fleet wiki` | `--dry-run` | Synchronize documentation to GitHub Wiki |
| `fleet version` | None | Print version and platform details |
