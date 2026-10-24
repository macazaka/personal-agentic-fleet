---
name: "🚀 Agent Proposal"
about: "Propose a new plug-and-play agent plugin for Fleet"
title: "[Agent Proposal]: "
labels: ["agent-proposal", "enhancement"]
assignees: ["macazaka"]
---

### Agent Name & Icon
<!-- e.g. Docker Container Monitor 🐳 -->

### Purpose & Problem Statement
<!-- What problem does this agent solve for personal computing/productivity? -->

### Proposed Architecture
- **Backend API Endpoints**:
  - `GET /api/...`
  - `POST /api/...`
- **Dashboard Pane Features**:
  - <!-- e.g. Container status table, restart buttons, logs viewer -->
- **Scheduled Background Tasks / Cron (if any)**:
  - <!-- e.g. Alert when container crashes -->

### Zero-Token Determinism
<!-- Confirm how this agent runs locally without consuming unnecessary LLM tokens -->
- [ ] Uses deterministic local Python/system tools
- [ ] Only uses LLM when semantic generation is strictly required
