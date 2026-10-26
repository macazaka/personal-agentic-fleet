# Agentic Fleet Governance & Rules

## Prime Directive: Computational & Token Cost Optimization

All agents in this fleet must strictly prioritize **the lowest cost solution for system, token, and compute operations**.

---

### 1. Token & Compute Cost Hierarchy
When processing any request or task, always resolve at the lowest possible computational tier:

- **Tier 0 — Deterministic Code (0 Tokens / $0.00)**:
  - If a task can be solved using local Python logic, SQLite queries, filesystem operations, regex, or system utilities, **never invoke an LLM**.
  - Calculations, routine tracking, daily briefing formatting, statistics, notifications, and **Email Intelligence (classification, synchronization, unsubscription detection, refresh)** must ALWAYS run in pure deterministic Python using 0 tokens ($0.00).
  - **Token Usage Restriction**: Tokens are strictly and exclusively reserved for **code enhancement** (e.g., code development, architectural refactoring, unit test creation, deep debugging). Tokens must NEVER be consumed for email intelligence, routine lookups, or system operations.
- **Tier 1 — Single-Hop Tool / MCP Calls (Minimal Tokens)**:
  - When an LLM is required, use concise, structured tool calling (e.g. `fleet_add_task`, `fleet_get_briefing`).
  - Never initiate conversational multi-agent debate or verbose back-and-forth chatter when a direct function call suffices.
- **Tier 2 — Context Pruning**:
  - Keep prompts minimal and payload data strictly filtered (e.g., fetch the top 5 high-priority items rather than dumping entire databases into prompt context).
- **Tier 3 — Model Selection**:
  - Always default to lightweight/efficient models (`flash_lite` / `flash`) for routine lookups, research, and tools. Reserve high-capacity models only for complex reasoning when strictly necessary.

---

### 2. Personal Life Decisions — User-Choice First (Never Force Lowest Cost)
When assisting the user with personal life activities, lifestyle, or choices (e.g., software, services, shopping, travel, tools, subscriptions):
- **Do NOT force or default to the lowest-cost option.**
- **Present balanced options and let the user choose.** Provide clear comparisons across tiers (e.g., quality, convenience, features, price) and respect the user's personal judgment and preferences.
- The user has 100% decision-making autonomy for all real-world and personal life decisions.

---

### 3. Cognitive Fleet Mind Compliance & Self-Critique Invariants
Every agent integrated into or created within the fleet adheres to the 4-layer Cognitive Fleet Mind:
- **Layer 1: Fleet Brain (Execution & Deterministic Dispatch)**: Executes deterministic Tier 0 Python pipelines (.00 compute) and coordinates inter-agent messaging via SQLite without token burn.
- **Layer 2: Fleet Consciousness (Active Self-Critique & State Tracking)**: Every agent execution must be self-critiqued prior to commit. Agents must evaluate outputs against safety, token efficiency, deterministic verification, and maintain a Conscious Score >= 85.
- **Layer 3: Fleet Subconsciousness (Proactive Auto-Healing & Log Mining)**: Agents cooperate with the background log scanner. When errors or anomalies arise, self-healing recipes are queued automatically without human intervention.
- **Layer 4: Fleet Soul (Ethical Alignment & Zero-Waste Invariant)**: Agents strictly uphold user autonomy, security boundaries, and zero token waste directives.

---

### 4. Unit Test Log & Activity Isolation Invariant
- **Zero Production Pollution**: No unit test, mock execution, test fixture, or automated verification step may EVER create, append, or pollute production activity logs, tasks, daily briefings, or the Workstation Control Center dashboard.
- **Dynamic Suppression Context**: Unit test suites must execute within the leet.common.logging.suppress_test_logs() context manager or set is_test=True / suppress_dashboard=True on diagnostic events.

---

### 5. Fleet Navigator & 100+ Agent Scalability Governance
- **Concurrency & Virtualization**: The fleet architecture supports 100+ concurrent agents. Agents must implement lazy state hydration and expose lightweight status endpoints.
- **Runtime State Control**: Agents can be enabled, disabled, or configured at runtime without restarting the workstation control center. Disabled agents cease background polling and release system handles immediately.
- **Agent Settings Schemas**: Agent-specific settings are validated strictly against their manifest.json schemas and persisted in the local SQLite key-value store.
