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

