# Contributing to Personal Agentic Fleet

Thank you for your interest in contributing to Fleet! We welcome contributions from the community—whether it's adding new plug-and-play agents, improving the microkernel, or refining UI components.

---

## 🧭 Code of Conduct & Architectural Principles

1. **Zero-Token First**:
   - Fleet enforces a **Tier 0 Deterministic Policy**. If a task can be achieved in clean Python/SQLite logic (e.g. calculation, file scanning, string parsing, scheduled tasks), do NOT use LLM API calls.
   - LLMs should only be engaged when creative synthesis or semantic understanding is strictly necessary.

2. **Isolated Agent Boundaries**:
   - Each agent should live entirely in its own folder under `fleet/agents/<agent_name>/`.
   - Never hardcode an agent's tabs or views inside `fleet/web/templates/dashboard.html`. Let the `AgentRegistry` and dynamic shell handle injection.

3. **Privacy by Design**:
   - Never commit API keys, client secrets, passwords, or personal health/system data.
   - All sample data must be generic and anonymized.

---

## 🛠️ Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/macazaka/fleet.git
   cd fleet
   ```

2. (Optional) Create a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. Run the test suite:
   ```bash
   python -m pytest tests/
   ```

4. Run the development dashboard:
   ```bash
   python fleet/app.py
   ```

---

## 📦 Creating a New Agent Plugin

To create a new agent, see the comprehensive guide at:
👉 [`docs/AGENT_DEVELOPMENT_GUIDE.md`](docs/AGENT_DEVELOPMENT_GUIDE.md)

Checklist for submitting an agent:
- [ ] Agent inherits from `FleetAgent` in `fleet/agents/<name>/agent.py`.
- [ ] Has clean metadata (`id`, `name`, `icon`, `order`).
- [ ] UI panel is placed in `fleet/agents/<name>/ui/panel.html`.
- [ ] Unit tests are added in `tests/test_<name>_agent.py`.
- [ ] Configuration options are documented in `fleet.yaml.example`.

---

## 🔀 Submitting a Pull Request

1. Create a feature branch: `git checkout -b feature/my-cool-agent`
2. Commit your changes: `git commit -m "feat: Add Docker container agent"`
3. Push to your fork: `git push origin feature/my-cool-agent`
4. Open a Pull Request against the `main` branch of `macazaka/fleet`.

