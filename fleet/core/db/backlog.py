"""
Feature Backlog domain repository mixin for FleetDatabase.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fleet.core.db.base import is_test_environment

_UNIT_TEST_BACKLOG_TITLES = frozenset({
    "discord integration bot",
    "test feature",
    "unit test feature",
    "sample backlog item",
    "e2e test feature",
})

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


FOUNDATIONAL_DEFAULT_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "Voice Commands & Native TTS Audio Briefing",
        "description": "Hands-free voice query input and spoken morning briefing audio generation.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.4.0",
        "created_at": "2026-10-14T01:24:47.196734",
    },
    {
        "title": "Telegram & WhatsApp Remote Bot Interface",
        "description": "Control Personal Fleet securely from mobile via bidirectional chat bot.",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.4.0",
        "created_at": "2026-10-14T01:24:47.196734",
    },
    {
        "title": "Calendar & Google Meet Auto-Agenda Prep",
        "description": "Analyze incoming calendar invites and automatically generate brief context notes.",
        "category": "Automation",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v1.4.0",
        "created_at": "2026-10-14T01:24:47.196734",
    },
    {
        "title": "Custom MCP Tool Creator UI",
        "description": "Visual interface to define and test new MCP tool servers directly in dashboard.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v1.5.0",
        "created_at": "2026-10-14T01:24:47.196734",
    },
    {
        "title": "Local Ollama Offline LLM Fine-Tuning",
        "description": "Offline private local model fallback with LoRA fine-tuning on personal habits.",
        "category": "AI/LLM",
        "priority": "P3",
        "status": "Completed",
        "target_version": "v2.0.0",
        "created_at": "2026-10-14T01:24:47.196734",
    },
]

ROBUSTNESS_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "Thread & Task Supervision Watchdog (Erlang-Style Supervisor)",
        "description": "Erlang-style supervisor pattern with exponential backoff & thread recovery for background daemon routines and agent task dispatchers.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:51.557791",
    },
    {
        "title": "Graceful Shutdown & Win32 Console Signal Trap Protocol",
        "description": "Unified signal handler for SIGINT, SIGTERM, and Win32 SetConsoleCtrlHandler to cleanly checkpoint SQLite WAL, drain EventBus, and remove PID lock.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:51.841157",
    },
    {
        "title": "Thread-Safe SQLite Connection Pool & Busy Timeout Guard",
        "description": "Thread-local SQLite connection pool with PRAGMA busy_timeout=10000 and automatic WAL checkpointing to eliminate lock contention under multi-threading.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:51.865458",
    },
    {
        "title": "Automated Daily Snapshot Backup & Corruption Recovery",
        "description": "Zero-token background daily backup using sqlite3.Connection.backup() to fleet/data/backups/ with SHA-256 integrity digests and 7-day snapshot retention.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:51.893162",
    },
    {
        "title": "Zero-Dependency Database Schema Migration Engine",
        "description": "Versioned database migrations using PRAGMA user_version with automated rollback snapshots and forward migration scripts.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:51.914401",
    },
    {
        "title": "OS Job Objects & POSIX Resource Quota Sandbox",
        "description": "Windows Job Objects (CreateJobObjectW) and POSIX setrlimit to enforce hard memory (500MB) and CPU ceilings on agent subprocesses.",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:51.943211",
    },
    {
        "title": "Socket-Level Network Egress Policy Enforcer",
        "description": "Intercept raw socket.connect calls in agent thread contexts to enforce manifest declared network:outbound permissions.",
        "category": "Security",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:51.970885",
    },
    {
        "title": "Resilient HTTP Transport with Circuit Breaker & Jittered Backoff",
        "description": "Zero-dependency resilient HTTP client with circuit breaking (trip on 5 consecutive 5xx/timeouts) and full jitter exponential backoff.",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:52.000020",
    },
    {
        "title": "Server-Sent Events (SSE) Live Push Stream (/api/events/stream)",
        "description": "Native /api/events/stream SSE endpoint eliminating 8-second client polling, reducing CPU wakeups and database reads to 0 when idle.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:52.026486",
    },
    {
        "title": "Localhost Token-Bucket Rate Limiter & DoS Shield",
        "description": "In-memory sliding window / token-bucket rate limiter in server.py capping requests to 60 req/s per route.",
        "category": "Security",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:52.051881",
    },
    {
        "title": "Structured JSON Logging & In-Memory Ring Buffer",
        "description": "Rotating JSON event logging with 1,000-event in-memory ring buffer exposed via /api/diagnostics/logs and 5MB rotation.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:52.073421",
    },
    {
        "title": "Global Crash Reporter & PII-Sanitized Stack Dumps",
        "description": "Global sys.excepthook and threading.excepthook capturing unhandled crashes to fleet/data/crash_reports/ with credentials auto-scrubbed.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:52.097100",
    },
    {
        "title": "System Sleep / Wake / Resume Lifecycle Handler",
        "description": "Native Windows Power Management & macOS sleep notifications to pause intervals during suspend and coalesce overdue jobs on resume.",
        "category": "Automation",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:52.130878",
    },
    {
        "title": "Offline Network Detection & Offline Event Spooling",
        "description": "Detect offline network status, suppress socket timeout retries, and spool outbound email/LLM tasks until connectivity is restored.",
        "category": "Integration",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T13:40:52.156241",
    },
    {
        "title": "Workstation Service Daemonization (Windows Task Scheduler / launchd / systemd)",
        "description": "1-click installer scripts for Windows Scheduled Task (Logon/Boot), macOS LaunchAgent plist, and Linux systemd user service.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.4.0",
        "created_at": "2026-10-26T13:40:52.176263",
    },
]

HISTORICAL_RELEASE_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "Core SQLite Memory Engine & Deterministic Zero-Token Event Bus",
        "description": "Persistent SQLite storage (fleet_memory.db) for tasks, memories, notes, routines, and $0.00 pub/sub DeterministicEventBus.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.0.0",
        "created_at": "2026-10-12T10:00:00.000000",
    },
    {
        "title": "5-Folder Email Intelligence Classifier & Daily Morning Briefing Engine",
        "description": "5-folder email triage (0-Meetings, 1-Respond, 2-Note, 3-FYI, 4-Ignore), Gmail OAuth2 sync, and rule-based Morning Briefing synthesis.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.0.0",
        "created_at": "2026-10-12T12:00:00.000000",
    },
    {
        "title": "Autonomous Background Execution Launcher & Native WinRT Toast Engine",
        "description": "Headless fleet_startup.vbs / setup_startup.py background survival without VS Code and zero-dependency PowerShell WinRT toast notifications.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.1.0",
        "created_at": "2026-10-13T10:00:00.000000",
    },
    {
        "title": "Automated Pytest Runner & >=98% Code Coverage Quality Gate",
        "description": "Programmatic test runner (fleet.tools.test_runner), test_runs SQLite persistence, and live Control Center coverage metrics widget.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.2.0",
        "created_at": "2026-10-13T18:00:00.000000",
    },
    {
        "title": "VS Code Antigravity Model Picker, Multi-Modal Image Attachments & Message Queue",
        "description": "Model popover (Gemini 3.8 Flash, Claude Opus/Sonnet 5.5), clipboard/drag-and-drop image attachments, and SQLite FIFO chat_queue when busy.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.3.0",
        "created_at": "2026-10-14T00:30:00.000000",
    },
    {
        "title": "Interactive Feature Backlog Management Panel & Kanban API",
        "description": "Dedicated Feature Backlog tab with priority sorting, status transitions, release filters, and /api/backlog* CRUD endpoints.",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v1.4.0",
        "created_at": "2026-10-14T01:20:00.000000",
    },
    {
        "title": "Email Intelligence 1-Click Unsubscribe (RFC 2369 / RFC 8058) & Auto-Archive",
        "description": "Automatic List-Unsubscribe header parsing, 1-click Unsubscribe button, persistent unsubscribed_emails table, and Fleet/4-Ignore auto-archiving.",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.5.0",
        "created_at": "2026-10-14T04:00:00.000000",
    },
    {
        "title": "Interactive Spoken Audio Briefing (Native Web Speech API TTS)",
        "description": "Zero-token offline speech synthesis (Speak button) on the Morning Briefing card with zero network latency.",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v1.6.0",
        "created_at": "2026-10-14T06:00:00.000000",
    },
    {
        "title": "Token Exhaustion Monitor, Prompt Preservation Vault & 1-Click Fallback Resumption",
        "description": "Live context capacity gauge (#agTokenHealthBar), HTTP 429 interception, non-destructive token_preservation_vault, and 1-click fallback model recovery.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.7.0",
        "created_at": "2026-10-14T09:00:00.000000",
    },
    {
        "title": "PC Performance Optimizer & 1-Click Workstation Auto-Tune Dashboard",
        "description": "Real-time RAM, Disk, Temp Junk, and Startup diagnostics with 0-100 Health Score and 1-click temp cleanup, DNS flush, cache purge, and RAM working-set trim.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.8.0",
        "created_at": "2026-10-14T14:00:00.000000",
    },
    {
        "title": "Full Codebase Modularization: Domain API Routers, DB Mixins & ES Modules",
        "description": "Modularized fleet/server.py (96.4% size reduction) into fleet/api/* routers, fleet/core/db/* domain mixins, and isolated fleet/web/static/js/* modules.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v1.9.0",
        "created_at": "2026-10-14T19:00:00.000000",
    },
    {
        "title": "Metabolic Health Intelligence, Biomarker Lab Diagnostics & Adherence Protocol",
        "description": "Personalized metabolic profile, HbA1c countdown, baseline lab report modal, mealtime-grouped supplement adherence, and multi-metric SVG trend charts.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.0.0",
        "created_at": "2026-10-24T12:00:00.000000",
    },
    {
        "title": "12-Layer Defense-in-Depth Security Scanner, DPAPI Crypto Vault & CycloneDX SBOM",
        "description": "Windows DPAPI + HMAC-SHA256 at-rest encryption, CSRF/DNS-rebinding guard, CSP headers, plugin capability sandboxing, and CycloneDX 1.5 SBOM generator.",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.1.0",
        "created_at": "2026-10-25T15:00:00.000000",
    },
    {
        "title": "Full Native macOS Compatibility: Keychain Vault, AppleScript Notifications & Darwin Telemetry",
        "description": "macOS Keychain credential protection, osascript notifications, vm_stat memory telemetry, purge RAM sweep, and LaunchAgents startup inspection.",
        "category": "Integration",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.2.0",
        "created_at": "2026-10-26T04:00:00.000000",
    },
    {
        "title": "Customizable YAML Agent Scheduling Engine & Visual Schedule Manager",
        "description": "Zero-dependency YAML parser, cron/interval/time-of-day scheduler (fleet/config/schedules.yaml), and interactive Overview schedule manager.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.3.0",
        "created_at": "2026-10-26T08:00:00.000000",
    },
    {
        "title": "1-Command Agent Scaffolding CLI & Rootless Container Distribution (ghcr.io)",
        "description": "fleet/tools/create_agent.py package generator and multi-stage rootless Dockerfile with automated GitHub Releases & CodeQL pipelines.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.3.0",
        "created_at": "2026-10-26T09:00:00.000000",
    },
    {
        "title": "Browser-Based Fleet Settings & Universal Agent Customizer Modal",
        "description": "Live agent activation toggles, display/icon/prompt/provider customization, timezone & quiet-hours settings, and instant SQLite snapshot creation.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T18:00:00.000000",
    },
    {
        "title": "Comprehensive Native Linux OS Support & FreeDesktop Hardware Parity",
        "description": "Linux notify-send/zenity/kdialog notifications, /proc RSS & malloc_trim(0), XDG/systemd autostart scanning, and secret-tool Keyring integration.",
        "category": "Integration",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.5.0",
        "created_at": "2026-10-26T20:00:00.000000",
    },
    {
        "title": "4-Layer Cognitive Fleet Mind (Brain, Consciousness, Subconsciousness & Soul)",
        "description": "Executive task routing (Brain), post-action self-critique (Consciousness), idle dream synthesis (Subconsciousness), and constitutional invariant auditing (Soul).",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.6.0",
        "created_at": "2026-10-27T12:00:00.000000",
    },
    {
        "title": "Proactive Log Scanner & Autonomous Self-Healing Engine (AutoHealer)",
        "description": "Periodic background log triage automatically remediating WAL bloat, crash dump retention, and task errors in auto_improvements.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.6.0",
        "created_at": "2026-10-27T15:00:00.000000",
    },
    {
        "title": "Proactive Semantic Release Manager, Doc/Wiki Enhancer & Zero-Diagnostic Auto-Fixer",
        "description": "Automated semantic versioning, AST API route & module introspection into GitHub Wiki, and pre-commit Pyright/CodeQL auto-remediation.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.6.0",
        "created_at": "2026-10-27T21:00:00.000000",
    },
    {
        "title": "Scalable 100+ Agent Operations Center, Command Deck Layouts & Live Version Parity",
        "description": "3 scalable agent navigation layouts (Matrix Cards, Compact Chips, Dense Table), drawer navigator, and automatic GitHub Release version parity checks.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.7.0",
        "created_at": "2026-10-27T23:00:00.000000",
    },
    {
        "title": "Multi-Turn Conversational Omnibar Assistant & Context Memory",
        "description": "Upgraded Ctrl+K Unified Fleet Omnibar with multi-turn conversational follow-ups and contextual agent dispatch.",
        "category": "AI/LLM",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.10.0",
        "created_at": "2026-10-28T18:00:00.000000",
    },
    {
        "title": "Right-Docked Antigravity Live Panel & Integrated $0.00 Fleet Chat Switcher",
        "description": "Split-screen right-docked Antigravity Live console with instant toggle between Antigravity IDE session and $0.00 local Fleet Chat.",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.11.0",
        "created_at": "2026-10-28T20:00:00.000000",
    },
    {
        "title": "Zero-Code Agent Studio Phases 1-6: Multi-Document Guided Creation, Drop-Folders & AI Evolution Advisor",
        "description": "Multi-attachment document synthesis (PDF/DOCX/XLSX/CSV/EML/ICS), 12 declarative SQLite UI blocks, watched drop-folders, Grounded RAG chat, and 10-point AI Evolution Advisor.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.13.0",
        "created_at": "2026-10-31T08:00:00.000000",
    },
    {
        "title": "Autonomous Post-Commit GitHub Pipeline, CodeQL SARIF & OSV.dev Vulnerability Sentinel",
        "description": "Detached post-commit/pre-push sentinel auditing GitHub Actions runs, CodeQL alerts, Dependabot, OSV.dev CVEs, Discussions, Wiki comments, and Issues.",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.13.1",
        "created_at": "2026-10-31T14:00:00.000000",
    },
    {
        "title": "Universal '10 Ways to Improve' & Manual Self-Improvement Undertaking Engine",
        "description": "1-click button on every built-in and custom Studio agent generating 10 domain-authentic feature improvements with multi-select checkboxes and manual self-improvement undertaking.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.14.3",
        "created_at": "2026-11-04T23:55:00.000000",
    },
]

UX_ROADMAP_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "[UX-01] Natural-Language 'Zero-Code' Agent Studio Skill & Conversational Workflow",
        "description": "Describe any agent in 1 plain-English sentence to auto-synthesize manifest.json, schedules.yaml, 6 declarative UI blocks (kpi_row, history_table, checklist), and unit tests in <15s. Spec: docs/backlog/UX-01-natural-language-agent-studio-skill.md",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.8.9",
    },
    {
        "title": "[UX-02] Autonomous Process Discovery & Agent Recommendation Engine (process_discovery)",
        "description": "100% local ($0.00 token) workflow miner observing dashboard logs, Win32 PSAPI app clusters, Git repos, and email triage over 1-14 days to recommend ready-to-spawn agents at 21:00 with 1-click creation. Spec: docs/backlog/UX-02-process-discovery-and-recommendation-agent.md",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.8.9",
    },
    {
        "title": "[UX-03] Visual Multi-Agent Playbook & Event-Chain Composer (IFTTT for Fleet)",
        "description": "Connect multiple agents into automated pipelines (WHEN [Trigger] -> IF [Condition] -> THEN [Agent A -> Agent B -> Toast]) via playbooks.yaml and a visual builder. Spec: docs/backlog/UX-03-multi-agent-playbook-and-workflow-chaining.md",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.8.9",
    },
    {
        "title": "[UX-04] 1-Click Agent Blueprint Templates & Portable .fleetagent Share Packs",
        "description": "15+ ready-to-use domain blueprints (Pomodoro Guardian, Subscription Sentinel, Multi-Repo Git Watcher, CGM Glucose Log) + drag-and-drop .fleetagent export/import audited by 12-Layer Security Scanner. Spec: docs/backlog/UX-04-agent-blueprint-templates-and-share-packs.md",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.8.9",
    },
    {
        "title": "[UX-05] Unified 'Ask Fleet Anything' Omnibar & Cross-Agent Dispatcher (Ctrl+K)",
        "description": "Upgrades Ctrl+K Spotlight into a Raycast-style universal Omnibar supporting @agent commands, natural-language Tier-0 execution, and instant inline result cards without switching tabs. Spec: docs/backlog/UX-05-unified-ask-fleet-omnibar-and-nl-dispatcher.md",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.8.9",
    },
    {
        "title": "[UX-06] Interactive First-Run Persona Onboarding & Goal-Driven Auto-Setup",
        "description": "60-second guided setup where users pick personas (FFD Athlete, Software Engineer, Inbox Zero) to auto-configure layouts, themes, schedules.yaml, and pinned tabs. Spec: docs/backlog/UX-06-interactive-persona-onboarding-and-auto-setup.md",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.14.0",
    },
    {
        "title": "[UX-07] Focus-Aware Smart Nudges & Actionable Notification Cards",
        "description": "Detects full-screen meetings/deep-work flow to batch non-urgent alerts, and adds 1-click action buttons ([+1 Glass], [Snooze 30m], [Complete]) directly inside notifications. Spec: docs/backlog/UX-07-context-aware-smart-nudges-and-interactive-toasts.md",
        "category": "Automation",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.14.0",
    },
    {
        "title": "[UX-08] Agent Time-Machine, 1-Click Undo Rollback & Safe Dry-Run Sandbox",
        "description": "Adds a Simulate (Dry Run) preview button using SQLite savepoints and a transactional agent_undo_journal allowing 1-click rollback of any agent mutation. Spec: docs/backlog/UX-08-agent-time-machine-undo-and-dry-run-sandbox.md",
        "category": "Security",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.14.0",
    },
    {
        "title": "[UX-09] Pin-to-Overview Micro-Widgets & Customizable Executive Bento Grid",
        "description": "Pin compact 1x1 or 2x1 live micro-widgets (get_micro_widget) from your favorite agents onto the main Overview Executive Cockpit. Spec: docs/backlog/UX-09-pin-to-overview-micro-widgets-and-bento-grid.md",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.14.0",
    },
    {
        "title": "[UX-10] Ambient System Tray Companion, Global Hotkey (Alt+Space) & Voice Capture",
        "description": "Native OS system tray status icon, global Alt+Space quick-capture HUD over any app, and zero-token voice command transcription. Spec: docs/backlog/UX-10-system-tray-companion-global-hotkey-and-voice-capture.md",
        "category": "Integration",
        "priority": "P3",
        "status": "Completed",
        "target_version": "v2.14.0",
    },
]

ALL_CANONICAL_BACKLOG_ITEMS: List[Dict[str, str]] = (
    FOUNDATIONAL_DEFAULT_BACKLOG_ITEMS
    + HISTORICAL_RELEASE_BACKLOG_ITEMS
    + ROBUSTNESS_BACKLOG_ITEMS
    + UX_ROADMAP_BACKLOG_ITEMS
)


class BacklogMixin(_DbBase):
    def sync_ux_roadmap_backlog(self) -> int:
        """Idempotently ensures all historical (v1.0.0..v2.14.3), ROB-01..ROB-15, and UX-01..UX-10 backlog items exist."""
        inserted = 0
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM feature_backlog")
            existing_titles = {str(row["title"]).strip() for row in cursor.fetchall()}
            for item in ALL_CANONICAL_BACKLOG_ITEMS:
                title = item["title"].strip()
                created_ts = item.get("created_at") or now
                if title not in existing_titles:
                    cursor.execute(
                        """
                        INSERT INTO feature_backlog (title, description, category, priority, status, target_version, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            title,
                            item["description"],
                            item["category"],
                            item["priority"],
                            item["status"],
                            item["target_version"],
                            created_ts,
                            now,
                        ),
                    )
                    existing_titles.add(title)
                    inserted += 1
                elif item["status"] == "Completed":
                    cursor.execute(
                        "UPDATE feature_backlog SET status = ?, target_version = ?, updated_at = ? WHERE title = ?",
                        (item["status"], item["target_version"], now, title),
                    )
            conn.commit()
        return inserted

    # --- Feature Backlog Operations ---
    def find_feature_backlog_item_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        clean_title = (title or "").strip().lower()
        if not clean_title:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM feature_backlog WHERE LOWER(TRIM(title)) = ? ORDER BY id DESC LIMIT 1",
                (clean_title,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_feature_backlog_item(self, title: str, description: str = "",
                                 category: str = "Core", priority: str = "P2",
                                 status: str = "Idea", target_version: str = "v1.4.0") -> int:
        clean_title = (title or "").strip()
        clean_desc = (description or "").strip()
        if not is_test_environment() or os.environ.get("FLEET_PRODUCTION_SERVER") == "1":
            t_low = clean_title.lower()
            if t_low in _UNIT_TEST_BACKLOG_TITLES or t_low.startswith("unit test") or t_low.startswith("e2e test"):
                return -1

        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feature_backlog (title, description, category, priority, status, target_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (clean_title, clean_desc, category, priority, status, target_version, now, now))
            conn.commit()
            return cursor.lastrowid or 0

    def list_feature_backlog_items(self, status: Optional[str] = None,
                                   category: Optional[str] = None,
                                   target_version: Optional[str] = None,
                                   priority: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM feature_backlog WHERE 1=1"
        params: List[Any] = []
        if not is_test_environment():
            query += (
                " AND LOWER(TRIM(title)) NOT IN ('discord integration bot', 'test feature', 'unit test feature', 'sample backlog item', 'e2e test feature')"
                " AND LOWER(title) NOT LIKE '%unit test%'"
                " AND LOWER(title) NOT LIKE '%e2e test%'"
            )
        if status and status.strip().lower() != "all":
            statuses = [s.strip() for s in status.split(",") if s.strip() and s.strip().lower() != "all"]
            if len(statuses) == 1:
                query += " AND status = ?"
                params.append(statuses[0])
            elif len(statuses) > 1:
                placeholders = ", ".join("?" for _ in statuses)
                query += f" AND status IN ({placeholders})"
                params.extend(statuses)
        if priority and priority.strip().lower() != "all":
            priorities = [p.strip().upper() for p in priority.split(",") if p.strip() and p.strip().lower() != "all"]
            if len(priorities) == 1:
                query += " AND priority = ?"
                params.append(priorities[0])
            elif len(priorities) > 1:
                placeholders = ", ".join("?" for _ in priorities)
                query += f" AND priority IN ({placeholders})"
                params.extend(priorities)
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category)
        if target_version and target_version.lower() != "all":
            query += " AND target_version = ?"
            params.append(target_version)

        query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, id DESC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_feature_backlog_item(self, item_id: int, **kwargs) -> bool:
        ALLOWED_FIELDS = {
            "title": "title = ?",
            "description": "description = ?",
            "category": "category = ?",
            "priority": "priority = ?",
            "status": "status = ?",
            "target_version": "target_version = ?",
        }
        set_clauses = []
        params = []
        for k, clause in ALLOWED_FIELDS.items():
            if k in kwargs and kwargs[k] is not None:
                set_clauses.append(clause)
                params.append(kwargs[k])
        if not set_clauses:
            return False
        set_clauses.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(item_id)
        sql = "UPDATE feature_backlog SET " + ", ".join(set_clauses) + " WHERE id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def delete_feature_backlog_item(self, item_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feature_backlog WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_feature_backlog_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, COUNT(*) as count FROM feature_backlog GROUP BY status")
            counts = {row["status"]: row["count"] for row in cursor.fetchall()}
            cursor.execute("SELECT priority, COUNT(*) as count FROM feature_backlog GROUP BY priority")
            prio_counts = {row["priority"]: row["count"] for row in cursor.fetchall()}
            cursor.execute("SELECT COUNT(*) as total FROM feature_backlog")
            total = cursor.fetchone()["total"]
            return {
                "total": total,
                "unapproved": counts.get("Unapproved", 0),
                "idea": counts.get("Idea", 0),
                "planned": counts.get("Planned", 0),
                "in_progress": counts.get("In Progress", 0),
                "completed": counts.get("Completed", 0),
                "deferred": counts.get("Deferred", 0),
                "p1": prio_counts.get("P1", 0),
                "p2": prio_counts.get("P2", 0),
                "p3": prio_counts.get("P3", 0),
            }

