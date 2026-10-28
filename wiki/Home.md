# Personal Agentic Fleet Documentation Wiki

Welcome to the comprehensive **Personal Agentic Fleet Documentation Wiki**!

[![Release: v2.8.6](https://img.shields.io/badge/Release-v2.8.6-00b4d8.svg)](Release-Notes)
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

## 📚 Complete Wiki Guide Directory

### 🧠 Core Architecture & Cognitive Science
| Guide | Highlights & Features |
| :--- | :--- |
| **[[Architecture]]** | FastHTTP microkernel, SQLite WAL zero-lock concurrency, synaptic event bus, security headers, and high-level topology. |
| **[[Cognitive-Fleet-Mind]]** | In-depth exploration of Brain, Consciousness, Subconsciousness, Soul, the Attention Focus Engine, and the Cognitive Harmony Index. |

### 🖥️ Desktop Experience & Agent Capabilities
| Guide | Highlights & Features |
| :--- | :--- |
| **[[AFCC-and-UI-Features]]** | Agentic Fleet Control Center (AFCC), 3 scalable layouts (`sidebar_dock`, `command_deck`, `launchpad_grid`) for 100+ agents, 4 color themes, and Spotlight Command Palette (`Ctrl+K`). |
| **[[Built-in-Agents]]** | Specifications for all 7 built-in agents (`overview`, `health`, `antigravity`, `backlog`, `optimizer`, `gmail`, `pr_review`), manifest permissions, and the Exercise & Strength Training Hub. |
| **[[Customizing-Agents]]** | Dynamic runtime activation/deactivation, dynamic agent settings schema drawer, and remote agent catalog one-click installation. |
| **[[Agent-Development-Guide]]** | Masterclass in building custom agents: UI 4-Step Wizard, Antigravity AI Skill, CLI `fleet create-agent`, and strict `manifest.json` capability contracts. |

### ⚙️ Operations, Tooling & Infrastructure
| Guide | Highlights & Features |
| :--- | :--- |
| **[[CLI-and-Automation-Tools]]** | Complete reference of all `fleet` subcommands, autonomous zero-intervention auto-fixer (`auto_fixer.py`), release manager, and doc/wiki enhancer. |
| **[[Proactive-CI-and-Release-Pipeline]]** | GitHub Actions workflows (`release.yml`, `ci.yml`, `security.yml`, `codeql.yml`), immutable release safe publishing, runner image pinning (`ubuntu-24.04`), and Node.js 24 compliance. |
| **[[Robustness-and-Self-Healing]]** | 7-Pillar native robustness, universal crash reporter with forensic dumps, AutoHealer proactive log scanner, circuit breakers, and test DB isolation invariants. |
| **[[API-Reference]]** | Exhaustive REST & Server-Sent Events (SSE) API specification with JSON request/response schemas and curl examples. |
| **[[Security-Model]]** | 12-layer deterministic security scanner, at-rest DPAPI/Keychain cryptographic vault, scoped user vault with OS-level ACLs, and CycloneDX 1.5 SBOM provenance. |
| **[[Linux-and-Cross-Platform-Support]]** | Tier 1 native support for Windows 10/11, macOS (Apple Silicon/Intel), and modern Linux distributions (Ubuntu, Debian, Fedora, Arch). |
| **[[Release-Notes]]** | Full semantic version release history and categorized changelog notes (`v2.8.3`). |

---

## ⚡ Core Pillars & Operational Invariants

1. **Deterministic Tier 0 Compute ($0.00 / Zero Tokens)**:
   Daily routine checklists, hydration tracking, local BM25 RAG search, system telemetry, and email classification execute 100% locally with zero token consumption. External LLM calls are strictly reserved for on-demand creative generation or deep synthesis.
2. **The 4-Layer Cognitive Fleet Mind**:
   - **Physical Brain**: High-throughput synaptic event bus and dual-tier ephemeral RAM and durable SQLite memory.
   - **Conscious Executive**: Real-time attention focus, self-critique rubric scoring (target $\ge 85$), and multi-axial quality evaluation.
   - **Subconscious Mind & Dreaming**: Background log consolidation, habit/friction discovery, and proactive immunological self-repair.
   - **Fleet Soul & Moral Compass**: Inviolable privacy boundaries, frugal compute invariants, and user-choice autonomy.
3. **100+ Agent Concurrent Scalability**:
   Engineered for large multi-agent fleets with 3 adaptive layouts, virtualized pagination, multi-field search, status filtering, and Spotlight Command Palette (`Ctrl+K` or `/`).
4. **Proactive Self-Healing & Zero-Crash Resilience**:
   Continuous background log scanner that mines runtime logs, detects anomalies, and automatically applies self-healing recipes (log rotation, SQLite WAL checkpoints, cache clearing, PID reap).

---

## 🚀 Quickstart

```bash
# Clone the repository
git clone git@github.com:macazaka/personal-agentic-fleet.git
cd personal-agentic-fleet

# Run the automated preflight quality gate
python -m fleet.tools.preflight_gate

# Launch the Agentic Fleet Control Center (AFCC)
python -m fleet.server --port 7890
```
Open your browser to `http://127.0.0.1:7890` to access the live dashboard.
