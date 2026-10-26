# 🛠️ Personal Agentic Fleet — Contributor & Agent Development Manual

Welcome to the **Personal Agentic Fleet Developer Guide**. This manual details how to set up your local development environment, build plug-and-play agents, add new hyperscaler providers, write tests, and pass the **Preflight Quality Gate**.

---

## 1. Developer Environment Setup

### 1.1 Automated Bootstrap
The repository includes automated bootstrap scripts that locate or provision Python `>= 3.10`, create `fleet.yaml`, harden the user vault, and install Git hooks:
```powershell
# Windows PowerShell
.\bootstrap.ps1

# Linux / macOS
chmod +x bootstrap.sh
./bootstrap.sh
```

### 1.2 Virtual Environment & Test Dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install pytest coverage anyio pyyaml
```

---

## 2. Core Architectural Conventions

When writing code for Personal Agentic Fleet, you must adhere to these foundational conventions:
1. **Fleet Rule 1: Tier 0 Cost & Token Governance ($0.00 Default)**:
   - Always prioritize deterministic regex, SQLite queries, and local BM25 RAG before calling external LLMs.
   - External LLM API calls must route through [`HyperscalerGateway`](../fleet/core/hyperscalers.py#L239-L729).
2. **Zero Plaintext Secrets**:
   - Never commit raw API keys or store them unencrypted. Use `get_secure_secret()` or the Windows DPAPI crypto vault.
3. **Cross-Platform Compatibility**:
   - Code must run cleanly on both **Windows 10/11** and **Ubuntu Linux** across Python 3.10, 3.11, and 3.12.
   - Guard OS-specific modules (`winreg`, `ctypes.windll`) with platform checks (`if sys.platform == "win32":`).
4. **Zero Test Socket Leakage**:
   - Unit tests are guarded by `conftest.py`'s socket fixture. Any outbound network call during a test will immediately raise a `RuntimeError`. Mock all external HTTP requests.

---

## 3. Creating a Custom Plug-and-Play Agent in 3 Steps

Fleet uses a modular, plug-and-play agent architecture. Creating a new capability requires **zero edits** to existing core files:

### Step 1: Create the Agent Directory & Manifest
Create `fleet/agents/my_agent/manifest.json`:
```json
{
  "id": "my_agent",
  "name": "My Custom Agent",
  "version": "1.0.0",
  "icon": "🚀",
  "order": 50,
  "description": "Performs custom autonomous workflows.",
  "permissions": [
    "db:read",
    "db:write",
    "ui:render"
  ]
}
```
*Allowed permissions*: `"db:read"`, `"db:write"`, `"ui:render"`, `"notification:send"`, `"network:outbound"`, `"fs:read"`, `"fs:write"`.

### Step 2: Implement the Agent Logic
Create `fleet/agents/my_agent/agent.py`:
```python
from typing import Any, Dict
from fleet.core.base_agent import FleetAgent

class MyCustomAgent(FleetAgent):
    def initialize(self) -> bool:
        # Perform one-time setup
        return True

    def register_routes(self, router) -> None:
        # Register custom REST API endpoints
        @router.get("/api/my_agent/data")
        def get_data(handler, parsed_url):
            handler._send_json({"status": "success", "items": []})

        @router.post("/api/my_agent/action")
        def run_action(handler, body):
            # Safe database write via ScopedDatabaseProxy
            self.db.log_activity("MyCustomAgent", "action_run", "Executed successfully")
            handler._send_json({"status": "completed"})
```

### Step 3: Add the UI Panel
Create `fleet/agents/my_agent/ui/panel.html`:
```html
<div class="agent-panel" id="panel-my-agent">
  <div class="panel-header">
    <h2>🚀 My Custom Agent</h2>
  </div>
  <div class="panel-body">
    <p>Autonomous capability is active and running at Tier 0 ($0.00).</p>
    <button class="btn btn-primary" onclick="triggerMyAction()">Execute Workflow</button>
  </div>
</div>
```
*(Optional `style.css` and `script.js` can be placed in the same `ui/` directory)*.

On next startup, `AgentRegistry` discovers your agent, validates its permissions against `plugin_sandbox.py`, mounts its routes, and renders its tab in the dashboard!

---

## 4. Cognitive Fleet Mind Integration Conventions

Agents operating within Personal Agentic Fleet are part of an integrated cognitive intelligence loop. When developing agent logic, adhere to these cognitive guidelines:

### 4.1 Conscious Self-Critique Compliance
Every action result emitted by an agent is evaluated in real time by the **Conscious Self-Critique Engine** (`fleet.core.mind.consciousness.SelfCritiqueEngine`):
- **Always return a structured dictionary**: Returning raw primitives or `None` incurs a 40-point deduction.
- **Always provide explicit status**: Include `"status": "success"` (or `"error"` if failing).
- **Populate actionable fields**: Avoid empty or null values; results with empty dictionaries or blank strings lose quality points.
- **Maintain status honesty**: Never set `"status": "success"` if an `"error"` key is populated.
- **Target quality score**: Ensure your return values consistently score $\ge 85.0/100$.

### 4.2 Synaptic Event Emission
To participate in the brain's neurological telemetry:
```python
from fleet.core.event_bus import bus, FleetEvent

# Emitting a synaptic event
bus.dispatch(FleetEvent(
    sender="my_custom_agent",
    target="overview",
    action="UPDATE_VITALS",
    payload={"metric": "battery", "value": 98}
))
```

### 4.3 Unit Test Logging Suppression Invariant
To keep the Workstation Control Center's Overview and Tasks panes completely clean of development test noise:
- The microkernel enforces `is_unit_test_log(message, agent, action)`.
- Never bypass the `FLEET_TEST_MODE` environment check.
- When writing tests, use `conftest.py` fixtures which automatically redirect logs away from production activity tables.

---

## 5. Adding a New Hyperscaler or Model

To add support for a new model or hyperscaler:
1. **Update Provider Catalog**: Add the provider definition in [`SUPPORTED_PROVIDERS`](../fleet/core/hyperscalers.py#L51-L157) in `fleet/core/hyperscalers.py`.
2. **Implement Completion Handler**: Add `_call_<provider>()` inside `HyperscalerGateway`. Use Python standard library (`urllib.request`) to avoid external dependencies.
3. **Register in Mirror**: Add the model to [`AVAILABLE_MODELS`](../fleet/core/antigravity_mirror.py#L101-L328) in `fleet/core/antigravity_mirror.py`.
4. **Add Unit Tests**: Add a mock test in `tests/test_hyperscalers.py` verifying response parsing and Tier 0 caching.

---

## 5. Preflight Quality Gate & Local Verification

Before submitting a Pull Request or pushing commits, run the **Preflight Quality Gate**:
```powershell
python -m fleet.tools.preflight_gate
```
The Preflight Gate automatically runs:
1. **Fleet Doctor**: Validates Python >= 3.10 runtime, OpenSSL TLS 1.3, SQLite WAL mode, Git hooks, and Vault ACL permissions (`100/100`).
2. **12-Layer Security Scanner**: Audits for secret patterns, PII leaks, SAST vulnerabilities, and token governance (`100/100, 0 findings`).
3. **Full Pytest Suite**: Executes all 380+ unit tests across the microkernel, cognitive mind, and plugins.

---

## 6. Developer CLI Toolkit

| Tool | Command | Purpose |
| :--- | :--- | :--- |
| **Fleet Mind** | `python -m fleet.tools.fleet_mind --status` | Terminal introspection for Brain, Consciousness, Subconsciousness, Soul |
| **Agent Scaffolder** | `python -m fleet.tools.create_agent` | Interactive CLI wizard to create new sandboxed agents |
| **Fleet Doctor** | `python -m fleet.tools.fleet_doctor` | Pre-flight diagnostics (Python >=3.10, TLS 1.3, DPAPI, ACLs, DB integrity) |
| **Security Scanner** | `python -m fleet.tools.security_scanner` | 12-layer security, secret, and privacy audit |
| **Test Runner** | `python -m fleet.tools.test_runner` | Isolated test execution with coverage and database logging |
| **Preflight Gate** | `python -m fleet.tools.preflight_gate` | Complete gate verifying Doctor + Scanner + Isolation + Docs + Tests |

Exit code is `0` only when all checks pass, guaranteeing **100% green CI runs on GitHub Actions**.
