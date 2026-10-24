## Description
<!-- Briefly describe the changes introduced in this pull request -->

## Type of Change
- [ ] 🚀 New plug-and-play agent (under `fleet/agents/<name>/`)
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ⚡ Performance improvement (zero-token optimization)
- [ ] 📖 Documentation update
- [ ] 🧪 Tests enhancement

## Checklist
- [ ] My code follows the code style and guidelines of this project
- [ ] I have verified that no personal credentials, secrets, or `.db` files are included
- [ ] I have added tests for any new agents or core features
- [ ] All 89+ pytest tests pass locally (`python -m pytest tests/`)
- [ ] If adding an agent, I updated `fleet.yaml.example` with default settings
- [ ] This change adheres to the **Tier 0 Deterministic Policy** (0 unnecessary LLM tokens)
