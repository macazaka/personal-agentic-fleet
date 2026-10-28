# Personal Agentic Fleet Wiki

Welcome to the official **Personal Agentic Fleet Documentation Wiki**!

[![Release: v2.8.2](https://img.shields.io/badge/Release-v2.8.2-00b4d8.svg)](Release-Notes)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Security: 100/100 PASS](https://img.shields.io/badge/Security%20Audit-100%2F100%20%5B12%20Layers%5D-brightgreen.svg)](Security-Model)
[![Zero-Token Engine](https://img.shields.io/badge/Architecture-Zero--Token%20Microkernel-orange.svg)](Architecture)
[![Privacy: Local-First](https://img.shields.io/badge/Privacy-100%25%20Local--First%20DPAPI-teal.svg)](Security-Model)
[![Windows: 10 / 11](https://img.shields.io/badge/Windows-10%20%7C%2011%20(64--bit)-0078D6.svg?logo=windows)](Linux-and-Cross-Platform-Support)
[![macOS: Universal](https://img.shields.io/badge/macOS-Apple%20Silicon%20%7C%20Intel-black.svg?logo=apple)](Linux-and-Cross-Platform-Support)
[![Linux: Native](https://img.shields.io/badge/Linux-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch-orange.svg?logo=linux)](Linux-and-Cross-Platform-Support)

Personal Agentic Fleet is an enterprise-grade, privacy-first personal AI operations center running 100% locally with zero-token deterministic compute ($0.00 cost) and an organic **4-Layer Cognitive Fleet Mind** (Brain, Consciousness, Subconsciousness, Soul).

---

## Quick Navigation

| Wiki Guide | Description |
| :--- | :--- |
| **[[Architecture]]** | 4-Layer Cognitive Mind, FastHTTP microkernel, synaptic event bus, SQLite WAL memory. |
| **[[Agent-Development-Guide]]** | Masterclass in building custom agents: UI Wizard, Antigravity Skill, CLI, and strict `manifest.json` capability contracts. |
| **[[CLI-and-Automation-Tools]]** | Unified `fleet` CLI subcommands, proactive release manager, and zero-intervention auto-fixer. |
| **[[Customizing-Agents]]** | Dynamic runtime activation/deactivation, agent settings schema drawer, and remote catalog discovery. |
| **[[Cognitive-Fleet-Mind]]** | In-depth exploration of Brain, Consciousness, Subconsciousness, Soul, and the Cognitive Harmony Index. |
| **[[Robustness-and-Self-Healing]]** | 7-Pillar native robustness, proactive log scanner, circuit breakers, and autonomous remediation recipes. |
| **[[API-Reference]]** | Complete REST & SSE API specification (`/api/mind/*`, `/api/settings/*`, `/api/diagnostics/*`). |
| **[[Security-Model]]** | 12-layer security scanner, NIST SP 800-132 PBKDF2 vault, DPAPI/Keychain, and pre-commit CodeQL AST guards. |
| **[[Linux-and-Cross-Platform-Support]]** | Tier 1 native support for Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux, macOS, and Windows. |

| **[[Release-Notes]]** | Semantic version release history and changelog notes (`v2.6.0`). |

---

## Core Pillars & System Invariants

1. **Deterministic Tier 0 Compute ($0.00 / Zero Tokens)**:
   Calculations, routine tracking, daily briefing formatting, local BM25 RAG search, and email classification execute 100% locally using zero LLM tokens. Tokens are strictly reserved for on-demand code generation or deep synthesis.
2. **The 4-Layer Cognitive Fleet Mind**:
   - **Physical Brain**: Synaptic event bus, dual-tier ephemeral RAM and durable SQLite memory, autonomic reflex arcs.
   - **Conscious Executive**: Real-time attention focus, self-critique rubric scoring (target $\ge 85$), and multi-axial quality evaluation.
   - **Subconscious Mind & Dreaming**: Background log consolidation, habit/friction discovery, proactive immunological self-repair.
   - **Fleet Soul & Moral Compass**: Inviolable privacy boundaries, frugal compute invariants, and user-choice autonomy.
3. **100+ Agent Concurrent Scalability**:
   Optimized for large multi-agent fleets with virtualized UI pagination, debounced multi-field search, status filtering, and Spotlight Command Palette (`Ctrl+K` or `/`).
4. **Proactive Self-Healing**:
   Continuous background log scanner that mines error logs, detects anomalies, and automatically applies self-healing recipes (log rotation, SQLite WAL checkpoints, cache clearing, PID reap).

---

## Getting Started

### Local Quickstart
```bash
# Clone the repository
git clone git@github.com:macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# Run the automated preflight quality gate
python -m fleet.tools.preflight_gate

# Launch the Workstation Control Center
python -m fleet.server --port 7890
```
Open your browser to `http://127.0.0.1:7890` to access the live dashboard.
