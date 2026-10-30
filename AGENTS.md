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

---

### 6. AFCC UI & UX Standards (Universal Tooltips SOP)
- **Mandatory Tooltip Coverage**: Every button (`<button>`) across all Agentic Fleet Control Center (AFCC) HTML templates, modals, cards, toolbars, and agent UI panels MUST include an informative, descriptive `title="..."` attribute explaining clearly what action occurs upon hover, click, or keyboard trigger.
- **Zero-Unlabeled Buttons Invariant**: Automated test suites (`test_afcc_all_buttons_have_tooltips_sop`) strictly enforce 100% button tooltip coverage across all HTML assets in `fleet/`.

---

### 7. Proactive Zero-Diagnostic Static Analysis & Pre-Commit Quality Gate SOP
- **Zero Pylance / Pyright Diagnostics Invariant**: Every code modification across `fleet/` and `tests/` MUST pass static type analysis (`0 errors, 0 warnings`) using the workspace Pyright/Pylance configuration (`pyrightconfig.json` / `[tool.pyright]` in `pyproject.toml`) **before** finishing an engineering task or committing.
- **Genuine Type Narrowing Over Suppression**: Fix static type errors via proper variable narrowing (e.g., bind `raw_val = obj.get("k")` to a local variable before `isinstance(raw_val, dict)` checks rather than repeating `obj.get("k")`, narrow stdlib union returns like `Message.get_payload(decode=True)` with `isinstance(payload, (bytes, bytearray))`, and import all typing symbols explicitly). Never mask genuine undefined variables or broken types with `# type: ignore`.
- **Mandatory Post-Edit / Pre-Commit Verification Checklist**:
  1. `python -X utf8 -c "from fleet.tools.preflight_gate import verify_static_type_integrity; r = verify_static_type_integrity(); assert r['status'] == 'PASS', r"` (verifies **0 Pylance/Pyright errors** + **0 HTML/CSS/JS/Workflow diagnostics**).
  2. `python -X utf8 -m fleet.tools.security_scanner` (verifies **100/100** across all 12 security & privacy layers).
  3. `python -X utf8 -m pytest` on affected & regression test suites (verifies **100% passing runtime behavior** + tooltip SOP).


