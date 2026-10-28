# 🏛️ System Architecture & Microkernel Internals

> **Release Version**: `v2.10.0` | **Core Modules**: `fleet/server.py`, `fleet/api/router.py`, `fleet/core/database.py`, `fleet/core/registry.py`, `fleet/core/plugin_sandbox.py`, `fleet/core/event_bus.py`

The **Personal Agentic Fleet** is engineered as a local-first, zero-dependency Python microkernel operating system. It combines a multi-threaded HTTP/1.1 + RFC 7233 byte-range server (`fleet/server.py`), a modular REST & SSE router (`fleet/api/router.py`), a capability-enforced plugin sandbox (`fleet/core/plugin_sandbox.py`), a thread-pooled SQLite 3 WAL storage engine (`fleet/core/database.py`), and the **4-Layer Cognitive Fleet Mind** (`fleet/core/mind/`).

---

## 1. End-to-End Microkernel Topology

```mermaid
graph TD
    subgraph UI ["Agentic Fleet Control Center (AFCC — Port 7890)"]
        Browser["Desktop Browser UI (dashboard.html)"]
        Nav["100+ Agent Fleet Navigator & Spotlight (Ctrl+K)"]
        LayoutEngine["6-Layout & 6-Theme Workspace Engine"]
        SSEClient["EventSource (/api/events) Real-Time Stream"]
        Browser --> Nav
        Browser --> LayoutEngine
        Browser --> SSEClient
    end

    subgraph Server ["HTTP & Security Boundary (fleet/server.py & fleet/api/router.py)"]
        FastHTTP["ThreadingHTTPServer + FleetRequestHandler"]
        HostGuard["DNS-Rebinding, Origin/CSRF & 5MB Payload Guard"]
        ApiRouter["ApiRouter (GET / POST / DELETE + Prefix Dispatch)"]
        VideoStreamer["HTTP 206 Partial Content Byte-Range Streamer"]
        FastHTTP --> HostGuard --> ApiRouter
        ApiRouter --> VideoStreamer
    end

    subgraph Kernel ["Core Microkernel Subsystems (fleet/core/)"]
        Registry["AgentRegistry (Dynamic Discovery & Manifest Loader)"]
        Sandbox["PluginSandbox & ScopedDatabaseProxy (Least-Privilege ACLs)"]
        TokenOpt["8-Layer TokenOptimizer (Tier 0, BM25 RAG, Fuzzy Cache)"]
        Hyperscalers["HyperscalerGateway (Gemini, Azure, Bedrock SigV4, Claude, Ollama)"]
        Scheduler["AgentScheduler (schedules.yaml Cron/Interval Engine)"]
        Mind["4-Layer CognitiveFleetMind (Brain, Consciousness, Subconscious, Soul)"]
    end

    subgraph Storage ["Persistence & Hardware Crypto Layer"]
        ConnPool["SQLiteConnectionPool (WAL Mode, busy_timeout=15000ms)"]
        SQLite[("fleet_memory.db (8 Core Tables)")]
        CryptoVault["CryptoVault (Win32 DPAPI / macOS Keychain / Linux SecretService)"]
    end

    Browser <==>|"REST JSON & SSE"| FastHTTP
    ApiRouter --> Registry
    Registry --> Sandbox
    ApiRouter --> TokenOpt --> Hyperscalers
    ApiRouter --> Scheduler
    ApiRouter --> Mind
    Sandbox --> ConnPool --> SQLite
    Sandbox --> CryptoVault
```

---

## 2. HTTP Server & Modular API Router (`fleet/server.py` & `fleet/api/router.py`)

### 2.1 Zero-Dependency Multi-Threaded Server (`ThreadingHTTPServer`)
Instead of requiring external ASGI/WSGI servers (`uvicorn`, `gunicorn`, `fastapi`) that introduce transitive supply-chain vulnerabilities, Personal Agentic Fleet runs on Python's native `http.server.ThreadingHTTPServer` enhanced with:
1. **DNS-Rebinding & Host Allowlisting**: Rejects any HTTP request whose `Host` header is not in `{"127.0.0.1", "localhost", "[::1]"}` (or explicitly configured LAN bindings) with `HTTP 403 Forbidden`.
2. **CSRF Origin & Custom Header Verification**: Mutating requests (`POST`, `PUT`, `DELETE`) verify `Origin`/`Referer` loopback fidelity and session tokens via `fleet/core/session_auth.py`.
3. **Strict Payload & Path Traversal Guards**:
   - Caps request bodies at `MAX_PAYLOAD_BYTES = 5_242_880` (`5 MB`) to prevent memory exhaustion DoS.
   - Verifies all static asset paths via `Path.resolve().is_relative_to(STATIC_ROOT)` before opening files.
4. **Hardened Response Headers**:
   - `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: no-referrer`

### 2.2 Declarative `ApiRouter` Dispatch Pipeline (`fleet/api/router.py`)
`ApiRouter` decouples endpoint logic from `FleetRequestHandler` using three dispatch tiers:
1. **Exact Route Hash Table (`O(1)` lookup)**: Maps `(method, path)` tuples directly to bound handler methods (`_get_routes`, `_post_routes`, `_delete_routes`).
2. **Prefix Route Table**: Handles parameterized paths such as `/api/agents/<agent_id>/settings`, `/api/tasks/<task_id>`, and `/api/exercises/video`.
3. **Dynamic Agent Route Forwarding**: Automatically routes `/api/agents/<agent_id>/<subroute>` to the target agent's sandboxed `handle_api(method, subroute, payload)` method after verifying `manifest.json` permissions.

---

## 3. Plugin Capability Sandbox & `ScopedDatabaseProxy` (`fleet/core/plugin_sandbox.py`)

Every agent in `fleet/agents/<agent_id>/` declares its required permissions in `manifest.json`. At load time, `AgentRegistry` wraps the agent in a `PluginSandbox` and injects a `ScopedDatabaseProxy` rather than the raw `FleetDatabase` instance.

### 3.1 Capability Permission Matrix (`VALID_PERMISSIONS`)

| Permission Token | Capability Granted | Enforcement Mechanism |
| :--- | :--- | :--- |
| `db:read` | Read access to allowed SQLite tables | Enforced by `ScopedDatabaseProxy._check_read()` |
| `db:write` | Write/mutate access to allowed SQLite tables | Enforced by `ScopedDatabaseProxy._check_write()` |
| `ui:render` | Render isolated HTML/CSS/JS panel in AFCC | Verified by `AgentRegistry` during dashboard assembly |
| `notifications:send` | Dispatch OS desktop toast notifications | Gated by `ScopedNotificationProxy` |
| `network:http` | Outbound HTTPS requests via `EgressGate` | Checked against domain allowlist & circuit breaker |
| `secrets:read` | Decrypt agent-scoped keys from `CryptoVault` | Restricted to keys prefixed with `agent.<agent_id>.*` |
| `system:read` | Read OS memory/CPU/process telemetry | Audited by `security_scanner.py` AST inspection |
| `system:execute` | Execute approved maintenance commands | Restricted to built-in signed system agents (`optimizer`) |

---

## 4. SQLite 3 WAL Storage Engine & Complete Schema Reference (`fleet/core/database.py`)

`FleetDatabase` uses a thread-safe connection pool (`fleet/core/connection_pool.py`) with Write-Ahead Logging (`PRAGMA journal_mode=WAL`), `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=15000`, `PRAGMA foreign_keys=ON`, and `PRAGMA secure_delete=ON`.

### Complete 8-Table Relational Schema (`fleet_memory.db`)

| Table Name | Primary Key | Columns & Types | Purpose |
| :--- | :--- | :--- | :--- |
| **`tasks`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `title TEXT`, `description TEXT`, `priority TEXT DEFAULT 'medium'`, `category TEXT DEFAULT 'general'`, `due_date TEXT`, `completed INTEGER DEFAULT 0`, `created_at TEXT`, `completed_at TEXT` | Personal & engineering task management board. |
| **`routines`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `name TEXT UNIQUE`, `category TEXT`, `target_time TEXT`, `completed_today INTEGER DEFAULT 0`, `last_completed_date TEXT`, `streak_count INTEGER DEFAULT 0` | Daily habits with automatic midnight reset and streak tracking. |
| **`health_metrics`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `date TEXT UNIQUE`, `water_glasses INTEGER DEFAULT 0`, `calories INTEGER DEFAULT 0`, `workout_completed INTEGER DEFAULT 0`, `workout_type TEXT`, `weight_kg REAL`, `fasting_bsl INTEGER`, `post_meal_bsl INTEGER`, `notes TEXT` | Daily hydration, FFD blood sugar levels (BSL), and 6-Day Strength Split logs. |
| **`memories`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `key TEXT UNIQUE`, `value TEXT`, `category TEXT DEFAULT 'general'`, `importance INTEGER DEFAULT 5`, `created_at TEXT`, `updated_at TEXT` | Long-term epistemic key-value store & circadian dream insights. |
| **`notes`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `title TEXT`, `content TEXT`, `tags TEXT`, `pinned INTEGER DEFAULT 0`, `created_at TEXT`, `updated_at TEXT` | Encrypted-capable markdown scratchpad and quick notes. |
| **`activity_logs`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `timestamp TEXT`, `agent_id TEXT`, `action TEXT`, `details TEXT`, `status TEXT DEFAULT 'info'` | Immutable audit trail of agent operations, schedules, and reflex events. |
| **`backlog`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `title TEXT`, `description TEXT`, `priority TEXT DEFAULT 'P2'`, `category TEXT DEFAULT 'Feature'`, `status TEXT DEFAULT 'pending'`, `created_at TEXT`, `completed_at TEXT` | Kanban feature roadmap and bug tracking tickets. |
| **`auto_improvements`** | `id INTEGER PRIMARY KEY AUTOINCREMENT` | `timestamp TEXT`, `category TEXT`, `issue_detected TEXT`, `action_taken TEXT`, `status TEXT`, `impact_score INTEGER DEFAULT 5` | Autonomous self-healing actions recorded by `AutoHealer` and `FleetSoul`. |

<!-- AUTO-CORE-MODULES:START -->
## 🧩 Live Microkernel Core Modules Inventory (`31` Modules — `v2.10.0`)

Automatically introspected from `fleet/core/*.py` on every release:

| Python Module | Source File | Responsibility |
| :--- | :--- | :--- |
| `fleet.core.agent_catalog` | [`fleet/core/agent_catalog.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/agent_catalog.py) | Agent Catalog & Remote Download Engine for Personal Agentic Fleet. |
| `fleet.core.agent_studio` | [`fleet/core/agent_studio.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/agent_studio.py) | UX-01: Natural-Language "Zero-Code" Agent Studio & Declarative UI Block Synthesizer. |
| `fleet.core.antigravity_mirror` | [`fleet/core/antigravity_mirror.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/antigravity_mirror.py) | Antigravity Live Session Mirror & Command Console Engine. |
| `fleet.core.auto_healer` | [`fleet/core/auto_healer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/auto_healer.py) | Proactive Log Analysis & Autonomous Self-Healing Engine for Personal Agentic Fleet. |
| `fleet.core.base_agent` | [`fleet/core/base_agent.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/base_agent.py) | Fleet Agent Base Contract for Personal Agentic Fleet. |
| `fleet.core.briefing` | [`fleet/core/briefing.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/briefing.py) | Core microkernel subsystem module. |
| `fleet.core.crypto_vault` | [`fleet/core/crypto_vault.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/crypto_vault.py) | At-Rest Cryptographic Vault for Personal Agentic Fleet. |
| `fleet.core.database` | [`fleet/core/database.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/database.py) | Database management for Personal Agentic Fleet. |
| `fleet.core.dev_tools` | [`fleet/core/dev_tools.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/dev_tools.py) | Core microkernel subsystem module. |
| `fleet.core.event_bus` | [`fleet/core/event_bus.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/event_bus.py) | Core microkernel subsystem module. |
| `fleet.core.exercise_manager` | [`fleet/core/exercise_manager.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/exercise_manager.py) | Exercise, Traditional Strength Training, and Video Management for Personal Agentic Fleet. |
| `fleet.core.http_client` | [`fleet/core/http_client.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/http_client.py) | Resilient HTTP Client with 3-State Circuit Breaker & Exponential Backoff for Personal Agentic Fleet. |
| `fleet.core.hyperscalers` | [`fleet/core/hyperscalers.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/hyperscalers.py) | Hyperscaler & Multi-Provider LLM Gateway for Personal Agentic Fleet. |
| `fleet.core.lifecycle` | [`fleet/core/lifecycle.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/lifecycle.py) | Unified Lifecycle, Signal Trap & Clean Shutdown Coordinator for Personal Agentic Fleet. |
| `fleet.core.logger` | [`fleet/core/logger.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/logger.py) | Structured JSON Logging Engine, Error Forensics & Ring Buffer for Personal Agentic Fleet. |
| `fleet.core.network_spool` | [`fleet/core/network_spool.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/network_spool.py) | Offline Network Detection & Event Spooling Engine for Personal Agentic Fleet. |
| `fleet.core.omnibar_dispatcher` | [`fleet/core/omnibar_dispatcher.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/omnibar_dispatcher.py) | UX-05: Unified "Ask Fleet Anything" Conversational Omnibar & Cross-Agent Dispatcher. |
| `fleet.core.optimizer` | [`fleet/core/optimizer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/optimizer.py) | PC Performance Optimization Engine for Personal Agentic Fleet. |
| `fleet.core.playbook_engine` | [`fleet/core/playbook_engine.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/playbook_engine.py) | UX-03: Visual Multi-Agent Playbook & Event-Chain Composer (fleet.core.playbook_engine). |
| `fleet.core.plugin_sandbox` | [`fleet/core/plugin_sandbox.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/plugin_sandbox.py) | Plugin Capability Sandboxing & Permission Enforcement for Personal Agentic Fleet. |
| `fleet.core.power` | [`fleet/core/power.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/power.py) | System Sleep, Wake & Resume Lifecycle Handler for Personal Agentic Fleet. |
| `fleet.core.process_miner` | [`fleet/core/process_miner.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/process_miner.py) | UX-02: Autonomous Process Discovery & Agent Recommendation Engine (fleet.core.process_miner). |
| `fleet.core.rate_limiter` | [`fleet/core/rate_limiter.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/rate_limiter.py) | Localhost Token-Bucket Rate Limiter & DoS Shield for Personal Agentic Fleet. |
| `fleet.core.registry` | [`fleet/core/registry.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/registry.py) | Fleet Agent Registry & Dynamic Plugin Loader. |
| `fleet.core.sandbox_quota` | [`fleet/core/sandbox_quota.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/sandbox_quota.py) | OS Job Objects, POSIX Resource Quota & Socket Egress Sandbox for Personal Agentic Fleet. |
| `fleet.core.scheduler` | [`fleet/core/scheduler.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/scheduler.py) | Deterministic Agent Scheduling Engine for Personal Agentic Fleet. |
| `fleet.core.session_auth` | [`fleet/core/session_auth.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/session_auth.py) | Localhost Session Cookie, CSRF & DNS-Rebinding Guard for Personal Agentic Fleet. |
| `fleet.core.supervisor` | [`fleet/core/supervisor.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/supervisor.py) | Thread & Task Supervision Watchdog for Personal Agentic Fleet. |
| `fleet.core.token_optimizer` | [`fleet/core/token_optimizer.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/token_optimizer.py) | Advanced Zero-Token & Cost Optimization Engine for Personal Agentic Fleet. |
| `fleet.core.updater` | [`fleet/core/updater.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/updater.py) | GitHub Version Checking, Native Notifications & 1-Click Update Engine |
| `fleet.core.yaml_helper` | [`fleet/core/yaml_helper.py`](https://github.com/macazaka/personal-agentic-fleet/blob/main/fleet/core/yaml_helper.py) | Pure-Python zero-dependency YAML parser and serializer for Personal Agentic Fleet. |
<!-- AUTO-CORE-MODULES:END -->
