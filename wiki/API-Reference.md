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
