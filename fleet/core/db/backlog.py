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
    {
        "title": "Autonomous Delegated Bill & Subscription Payment Execution Engine (Pay on My Behalf)",
        "description": "Enable AFCC to securely make payments on the user's behalf (Credit Card bills, Electricity bills, Broadband/Mobile bills, Loan EMIs, NPS/PPF investments, Insurance renewals, and KINDUZ compliance/vendor payments) with human-in-the-loop OTP/UPI/2FA approval, spend-limit guardrails, DPAPI vault security, receipt verification, and automatic task completion.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-01] Unit Test Suite: Email Proposal Workflow & Attachment Virus Scan HTTP API Endpoints",
        "description": "Add direct HTTP endpoint unit tests for fleet/api/email_api.py routes: GET /api/emails/proposals (get_email_proposals_endpoint), POST /api/emails/proposals/approve (approve_email_proposal_endpoint), POST /api/emails/proposals/reject (reject_email_proposal_endpoint), and POST /api/emails/attachments/scan (scan_email_attachment_endpoint).",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-02] Unit Test Suite: Cognitive Mind Layer, Soul Audits & Diagnostics Health HTTP API Endpoints",
        "description": "Add direct unit tests for fleet/api/system_api.py & fleet/core/mind/consciousness.py: GET /api/diagnostics/health (get_diagnostics_health), GET/POST /api/logs/analyze, GET /api/mind/status, /api/mind/insights, /api/mind/critiques, /api/mind/soul_audits, POST /api/mind/critique, /api/mind/dream, /api/mind/soul_audit, /api/mind/self_improve, /api/mind/heal, and ExecutiveAttention.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-03] Unit Test Suite: Focus Guard, Smart Nudges & Agent Dry-Run / Undo Time-Machine API Endpoints",
        "description": "Add unit tests for fleet/api/settings_api.py, fleet/core/focus_guard.py, and fleet/core/plugin_sandbox.py: POST /api/notifications/nudge, POST /api/notifications/nudges/flush, POST /api/notifications/nudges/action, POST /api/notifications/focus, POST /api/agents/dry_run (simulate_agent_task_dry_run), POST /api/agents/undo, and build_default_nudge_actions.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-04] Unit Test Suite: Omnibar Voice Router, System Tray Companion Actions & Playbook/Onboarding APIs",
        "description": "Add unit tests for fleet/api/settings_api.py, fleet/core/omnibar_dispatcher.py, and fleet/tools/tray_companion.py: POST /api/omnibar/voice (post_omnibar_voice_endpoint), POST /api/tray/action (post_tray_action_endpoint), POST /api/playbooks/save, POST /api/onboarding/apply, get_omnibar_chat_history, get_voice_activities_catalog, and launch_tray_companion_background.",
        "category": "Integration",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-05] Unit Test Suite: Unified Fleet Tasks Aggregation & Inline Task Edit Draft Preservation",
        "description": "Add unit tests for fleet/api/tasks_api.py (collect_unified_fleet_tasks and GET /api/tasks/unified) and frontend inline task editor state preservation (isTaskEditingActive, captureEditTaskDraft, _editingTaskDrafts, maskSensitiveTaskText, resolveTaskTemporalMeta in fleet/web/static/js/tasks.js).",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-06] Unit Test Suite: Custom Video Playlists Persistence, Sequential Auto-Play & Zero-Stream Card Themes",
        "description": "Add edge-case unit tests for save_video_playlists in fleet/api/health_api.py (corrupted JSON recovery, duplicate playlist ID update, empty video list rejection, path traversal guard on /api/health/video/open_folder) and sequential playlist auto-advance (playCustomPlaylistFromIndex, playNextInCustomPlaylist, _getVideoCardTheme in fleet/web/static/js/health.js).",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-07] Unit Test Suite: Agent Studio Phase 6 Runtime, Multi-Document Batch Extraction & Prompt Improviser",
        "description": "Add unit tests for fleet/core/agent_studio.py (execute_studio_agent_runtime, generate_custom_agent_code, get_agent_improvement_context, improvise_agent_improvement_prompt, undertake_agent_self_improvements), fleet/core/studio_phase6.py (scan_and_ingest_agent_inbox, infer_recurrence_cycle, roll_forward_custom_agent_record, execute_outbound_action_hooks, answer_custom_agent_chat), and fleet/core/document_extractor.py batch extraction.",
        "category": "AI/LLM",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-08] Unit Test Suite: Unified Fleet CLI Subcommands (cmd_start..cmd_version) & Release/Auto-Fixer Tooling",
        "description": "Add unit tests for all 16 CLI subcommand handlers in fleet/cli.py (cmd_start, cmd_stop, cmd_status, cmd_doctor, cmd_mind, cmd_agents, cmd_security, cmd_heal, cmd_test, cmd_wiki, cmd_autofix, cmd_release, cmd_docs, cmd_lifecycle, cmd_version), fleet/tools/release_manager.py (ensure_workstation_version_parity, run_proactive_release_check), and fleet/tools/auto_fixer.py.",
        "category": "Automation",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-09] Unit Test Suite: SQLite Schema Forward Migrations (v1-v5) & Event Playbook Trigger Engine",
        "description": "Add isolated unit tests for individual schema migration steps in fleet/core/db/migrations.py (migration_v1_baseline through migration_v5_cognitive_mind) and event playbook synchronization in fleet/core/playbook_engine.py (save_playbooks, remove_custom_agent_playbooks, sync_custom_agent_event_playbooks, dispatch_event_trigger).",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
    {
        "title": "[QA-10] Unit Test Suite: Compact Self-Improvement Header Popover, 24h Completed Task Expiry & Frontend JS Modules",
        "description": "Add unit tests covering the compact Self-Improvement & Feature Evolution header popover (toggleEvolveHeaderPopover, closeEvolveHeaderPopover), 24-hour auto-expiry of completed evolution undertakings (_pruneExpiredCompletedUndertakings in create_agent.js), SemVer backlog sorting (backlog.js), and Settings agent drawer lifecycle (settings.js).",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.17.0",
    },
]

TRI_DEVICE_BACKLOG_ITEMS: List[Dict[str, str]] = [
    {
        "title": "[TD-01] Tri-Device Phase 1: Tailscale WireGuard Private Mesh, Local Root CA (/api/security/ca.crt) & Mobile Bearer Token Gateway",
        "description": "Phase 1 Practical Foundation (EC-01, EC-02, EC-08): Because Apple Watch only pairs with iPhone (never Windows) and Windows 10 Home lacks Win11 Phone Link for iPhone, provision zero-config Wi-Fi LAN HTTP/HTTPS discovery (/api/mobile/gateway/status) as primary transport with optional Tailscale WireGuard roaming, 1-tap iOS 26.3.1 Root CA download (/api/security/ca.crt), and 256-bit DPAPI-backed Mobile Bearer Token authentication (/api/mobile/gateway/token).",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-02] Tri-Device Phase 1: Apple Watch & iPhone HealthKit Telemetry Ingestion + FFD Workout Readiness Engine (/api/mobile/health/ingest)",
        "description": "Phase 1 Practical Foundation (EC-01, EC-04, EC-10): Ingest Apple Watch biometrics via iPhone 15 HealthKit Companion Relay (HRV SDNN, Sleep hours, Resting HR, SpO2, Steps, Active kcal, Glucose, Water ml), compute deterministic 0-100 FFD & 6-Day Akhada Strength Readiness Score (Mudgal/Samtola/Bhim Gadha adaptation), and persist in local-only AES-256-GCM encrypted apple_health_sync_vault.json & hardware_inventory_vault.json (100% gitignored).",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-03] Tri-Device Phase 1: iOS Automated Background Health Sync Shortcut, Standalone PWA (manifest.json + sw.js) & Tri-Device Hub UI",
        "description": "Phase 1 Practical Foundation (EC-03, EC-04): Zero-Xcode / Zero-$99-Dev-Account architecture using W3C Web App Manifest (/manifest.json), zero-cloud Service Worker (/sw.js), downloadable iOS 26.3.1 Health Sync Shortcut recipe (/api/mobile/shortcuts/template) bound to FaceID-unlocked triggers (Wake-Up Alarm Stopped, Workout Ends, App Open, or Back-Tap to bypass iOS lock-screen HealthKit encryption), and dedicated Connection Agents Tri-Device Hub.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-04] Tri-Device Phase 2: Responsive iPhone Safari Standalone PWA Shell & Touch-Optimized Bottom Tab Bar",
        "description": "Phase 2 Mobile Voice & PWA (EC-03, EC-07): iOS 26.3.1 Safari Add-to-Home-Screen standalone PWA (/mobile-pair & dashboard) with viewport-fit=cover safe-area styling, zero-cert native iOS Keyboard Dictation / Siri voice input fallback on plain LAN HTTP, Apple Watch HRV/Sleep 6-day Akhada adaptation (/api/mobile/workout/adaptation), and touch-ergonomic navigation across Action Items, Mahadev Voice, Monthly UPI Payments, and Health.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-05] Tri-Device Phase 2: 'Mahadev' Wake-Word Mobile Voice Cockpit (1.5x–3x Speed) & Live Verbal Action-Item Conversation Engine",
        "description": "Phase 2 Mobile Voice & PWA (EC-05, EC-09): Ultra-low-CPU (<3% on dual-core 1.70GHz laptop) WebAudio 6D biometric voiceprint gate + $0.00 Tier-0 regex intent engine (<5ms latency), custom 'Mahadev' wake word, high-speed Indian English TTS (1.5x, 1.75x, 2x, 2.5x, 3x), Bluetooth headset mic routing, and stateful verbal closing, editing, reprioritizing, and reopening of open and closed Action Items.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-06] Tri-Device Phase 2: iOS IndexedDB Offline Encrypted Cache & Background Outbox Sync Queue",
        "description": "Phase 2 Mobile Voice & PWA (EC-08): Client-side localStorage/IndexedDB outbox queue on iPhone 15 (/mobile-pair) and iOS Shortcuts File-Spool fallback that buffers water logs, task closures, and HealthKit snapshots when away from home Wi-Fi and auto-flushes upon LAN/Tailscale reconnection via /api/mobile/outbox/sync.",
        "category": "Core",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-07] Tri-Device Phase 2: iOS Scriptable Home Screen & Lock Screen FFD Readiness & Action-Item Widgets",
        "description": "Phase 2 Mobile Voice & PWA (EC-03): Zero-Xcode iOS 26.3.1 Home Screen & Lock Screen widgets (/api/mobile/widgets/scriptable) via free Scriptable app or native iOS Pinned Shortcuts consuming /api/mobile/watch/complication (<2KB JSON) to display live FFD Workout Readiness Score, Daily Hydration progress, and top P1 Action Item count.",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-08] Tri-Device Phase 3: 1-Tap iPhone Open Payment Deep-Link Dispatcher (BHIM, ICICI iMobile, GPay, PhonePe) & Voltage-FPE VPA Masking",
        "description": "Phase 3 Practical 1-Tap UPI & Bank Payments (EC-06): Overcomes iOS 26.3.1 Safari deep-link sandboxing via Dual-Mode Dispatch — (A) Dynamic NPCI upi://pay SVG QR Code rendered on Laptop Hub for 2-second iPhone BHIM/ICICI/GPay camera scan, and (B) Explicit user-gesture deep-link buttons (bhim://, imobileapp://, tez://, phonepe://) + 1-Tap Copy VPA on /mobile-pair with Voltage-FPE VPA masking and 1-tap Monthly Action Item closure.",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-09] Tri-Device Phase 3: iOS Share Sheet & Bank SMS Confirmation Receipt Parser for Auto-Closing Paid Monthly Action Items",
        "description": "Phase 3 Practical 1-Tap UPI & Bank Payments (EC-02, EC-06): Because Windows 10 Home lacks iPhone SMS/Notification relay, use an iOS 26.3.1 Share Sheet Shortcut & Automation ('When Message Received from Bank/UPI') to parse UTR/reference numbers from BHIM, ICICI iMobile, or GPay receipts and POST to /api/mobile/payments/parse_receipt to auto-close the matching Monthly Action Item and persist in AES-256-GCM encrypted payment_receipts_vault.json.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-10] Tri-Device Phase 4: Apple Watch Smart Stack Complication (<2KB Snapshot) & 1-Tap Wrist Actions (+250ml Water / Close Top Action Item)",
        "description": "Phase 4 Practical Apple Watch Complication & Haptics (EC-01, EC-03): Zero-Xcode Apple Watch integration using native watchOS Shortcuts ('Show on Apple Watch' enabled in iCloud Shortcuts) + Smart Stack Complication backed by sub-2KB /api/mobile/watch/complication (<5ms) for 1-tap wrist actions (+250ml Water, Close Top Action Item, Check FFD Readiness).",
        "category": "Integration",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-11] Tri-Device Phase 4: Apple Watch Action Button & Siri 'Mahadev' Wrist Voice Bridge Recipe",
        "description": "Phase 4 Practical Apple Watch Complication & Haptics (EC-01, EC-03): Zero-Xcode watchOS Siri Shortcut ('Mahadev Wrist Bridge') using Dictate Text -> Get Contents of URL (POST /api/mobile/voice/relay) -> Speak Text on Apple Watch for instant wrist-level verbal Action Item review and closure via iPhone Wi-Fi relay.",
        "category": "AI/LLM",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
    {
        "title": "[TD-12] Tri-Device Phase 4: Windows Laptop Lock/Unlock Presence Handshake & Apple Watch Haptic Nudger",
        "description": "Phase 4 Practical Apple Watch Complication & Haptics (EC-02, EC-05, EC-09): Zero-CPU Windows 10 workstation lock/idle detection + <2ms winreg BTHENUM Bluetooth presence check (/api/mobile/presence/nudge) + split Bluetooth audio profile router (/api/mobile/audio/routing) that routes urgent P1 bill and hydration nudges to iPhone 15 & Apple Watch Taptic Engine.",
        "category": "Automation",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.18.0",
    },
]

JARVIS_PERFORMANCE_AND_UX_BACKLOG_ITEMS: List[Dict[str, str]] = [
    # --- 10 Critical (P1/Critical) J.A.R.V.I.S. Performance Enhancements ---
    {
        "title": "[JV-01] Critical Perf #1: O(1) Frozenset Token Intersection & Pre-Compiled Multi-Word Regex for N-Best ASR Scoring (_score_voice_candidate)",
        "description": "Eliminates 330 dynamic re.search() regex compilations per voice turn in _score_voice_candidate by replacing the 66-keyword loop with an O(1) frozenset token intersection (_JARVIS_SINGLE_WORD_SET) and a single pre-compiled _JARVIS_MULTI_WORD_RE, cutting N-best candidate scoring CPU time by >96%.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-02] Critical Perf #2: In-Memory Wake-Word Setting & Compiled Regex Memoization Cache (_WAKE_WORD_MEMO_CACHE)",
        "description": "Memoizes db.get_setting('voice_wake_word') and its compiled wake-word stripping regex per DB instance (with 60s TTL & instant invalidation on settings update), eliminating 1-6 redundant SQLite SELECT queries and regex compilations on every voice turn.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-03] Critical Perf #3: Pre-Compiled Speech Sanitizer Pipeline & Bounded 32-Entry LRU Memo Cache (_clean_for_speech & split_speech_into_stream_clauses)",
        "description": "Pre-compiles all URL, account-masking, Markdown, emoji, whitespace, and clause-boundary regexes at module import time and caches cleaned spoken strings in a bounded 32-entry ring buffer (_CLEAN_SPEECH_CACHE) so repeated speech sanitization passes execute in <0.01ms with zero GC churn.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-04] Critical Perf #4: Turn-Scoped SQLite Task List & Live Fleet Snapshot Coalescing (_get_turn_cached_tasks)",
        "description": "Coalesces db.list_tasks(limit=200) and _gather_live_fleet_snapshot across topic-stack rehydration, multi-question decomposition, and sub-command execution within a 1.5s turn window so a 3-part voice queue runs at most 1 SQLite task scan instead of 4-6 redundant queries.",
        "category": "Core",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-06] Critical Perf #5: O(1) Canonical Fast-Intent Hash Dispatch Table (_FAST_INTENT_CANONICAL_ALIASES)",
        "description": "Normalizes the 25 highest-frequency J.A.R.V.I.S. voice phrases ('can you hear me', 'lets discuss action items', 'next action item', 'close it', 'good morning', 'tell me todays news', 'tell me about latest updates of pune', etc.) via an O(1) hash lookup table before evaluating 40+ regex branches.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-06B] Critical Perf #6: Zero-Allocation Audio Spectrum Canvas 32-Bit Signature Diffing & Offscreen Skip (renderJarvisLiveSpectrumCanvas)",
        "description": "Skips WebAudio <canvas> 2D clearRect/fillRect repaints when #afccVoiceCopilotHud is hidden (offsetParent === null) and compares a quantized 32-bit bar-height signature (_lastSpectrumSig) to avoid redundant GPU/CPU canvas repaints when bar heights are unchanged.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-07] Critical Perf #7: In-Memory Decrypted Voiceprint Profile & Sandbox History Read-Through Cache (_VOICEPRINT_MEM_CACHE)",
        "description": "Caches decrypted AES-256-GCM jarvis_voiceprint_profile and jarvis_voiceprint_sandbox_history in memory inside fleet/api/settings_api.py (invalidated on write), eliminating repeated PBKDF2/AES decryption and disk I/O on GET /api/voice/voiceprint and biometric verification turns.",
        "category": "Security",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-08] Critical Perf #8: Client-Side Single-Flight Voice Turn Deduplicator & AbortController Guard (_activeVoiceFetchController)",
        "description": "Prevents duplicate concurrent /api/voice/stream network requests when SpeechRecognition early-endpointing and rec.onend fire within <150ms for the same utterance, deduplicating by transcript signature and aborting superseded in-flight fetches.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-09] Critical Perf #9: Speak-First Hardware TTS Scheduling with requestAnimationFrame DOM Mutation Batching",
        "description": "Queues Clause #0 on the browser SpeechSynthesis hardware thread BEFORE batching post-turn DOM updates (transcript badge, activity pills, context chips, focused task bar, queue bar) inside requestAnimationFrame, eliminating main-thread layout thrashing during audio onset.",
        "category": "UI/UX",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-10] Critical Perf #10: Stale-While-Revalidate (SWR) Non-Blocking Background News & City RSS Cache Engine",
        "description": "Upgrades _fetch_live_news_and_web_digest with a 2-tier SWR cache (10-min fresh TTL + 60-min stale-while-revalidate window) that returns cached headlines in 0.05ms and refreshes Google News RSS asynchronously on a background daemon thread.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    # --- 6 Non-Conflicting High (P1), Medium (P2), and Low (P3) J.A.R.V.I.S. Feature Enhancements ---
    {
        "title": "[JV-11] High Crit #11: Conversational Voice Undo & Correction Reflex ('Undo that', 'Scratch that') with Mutation Journal",
        "description": "Maintains a bounded in-memory _LAST_VOICE_MUTATION_JOURNAL recording the last voice-triggered task closure, task creation, title/priority edit, or water log so saying 'Undo that' or 'Scratch that' reverses the mutation in <5ms at $0.00.",
        "category": "Automation",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-12] High Crit #12: Zero-Token Spoken Time, Date, Day & Schedule Context Awareness ('What time is it?', 'What day is today?')",
        "description": "Instantaneous (<1ms, $0.00) local temporal & schedule awareness answering current time, date, day of week, today's 6-day strength split, and active cron routines aloud without external API calls.",
        "category": "AI/LLM",
        "priority": "P1",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-13] Medium Crit #13: Interactive Voice Queue & Parked Topic Stack Verbal Inspector ('What is in my queue?', 'Clear parked topics')",
        "description": "Enables verbal inspection and clearing of the active conversational topic stack and parked topics ('What is in my queue?', 'List parked topics', 'Clear parked topics'), reading out each parked topic and its priority level.",
        "category": "UI/UX",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-14] Medium Crit #14: Indian Currency (Rs / ₹ / Lakh / Crore) & Technical Acronym Phonetic Normalizer in _clean_for_speech",
        "description": "Normalizes Indian currency symbols and numbers ('Rs. 40,000' -> '40,000 rupees', '₹35 lakh' -> '35 lakh rupees') and technical acronyms in _clean_for_speech for natural Indian English, Hindi, Telugu, and Marathi TTS pronunciation.",
        "category": "AI/LLM",
        "priority": "P2",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-15] Low Crit #15: Whisper / Late-Night Quiet Voice Mode ('Whisper mode on', 'Quiet mode') with Softened Gain & Ultra-Short Replies",
        "description": "Adds voice- and UI-togglable Whisper Mode (window.AFCCVoice.whisperMode) that softens TTS output volume (0.45), lowers pitch (0.92), and enforces ultra-concise 1-clause spoken replies for quiet environments.",
        "category": "UI/UX",
        "priority": "P3",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
    {
        "title": "[JV-16] Low Crit #16: Real-Time J.A.R.V.I.S. Performance & Cache Telemetry Diagnostics Endpoint (GET /api/voice/diagnostics & 'Voice diagnostics')",
        "description": "Exposes GET /api/voice/diagnostics and voice command 'Jarvis performance report' returning real-time hit/miss counters, cache sizes (_CLEAN_SPEECH_CACHE, _LIVE_NEWS_CACHE, _WAKE_WORD_MEMO_CACHE), topic stack depth, and sub-5ms dispatch latency.",
        "category": "Core",
        "priority": "P3",
        "status": "Completed",
        "target_version": "v2.20.0",
    },
]

ALL_CANONICAL_BACKLOG_ITEMS: List[Dict[str, str]] = (
    FOUNDATIONAL_DEFAULT_BACKLOG_ITEMS
    + HISTORICAL_RELEASE_BACKLOG_ITEMS
    + ROBUSTNESS_BACKLOG_ITEMS
    + UX_ROADMAP_BACKLOG_ITEMS
    + TRI_DEVICE_BACKLOG_ITEMS
    + JARVIS_PERFORMANCE_AND_UX_BACKLOG_ITEMS
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
                        "UPDATE feature_backlog SET description = ?, status = ?, target_version = ?, updated_at = ? WHERE title = ?",
                        (item["description"], item["status"], item["target_version"], now, title),
                    )
                elif title.startswith("[TD-"):
                    cursor.execute(
                        "UPDATE feature_backlog SET description = ?, updated_at = ? WHERE title = ?",
                        (item["description"], now, title),
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
            if t_low in _UNIT_TEST_BACKLOG_TITLES or t_low.startswith("unit test feature") or t_low.startswith("e2e test feature"):
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
                " AND LOWER(TRIM(title)) NOT LIKE 'unit test feature%'"
                " AND LOWER(TRIM(title)) NOT LIKE 'e2e test feature%'"
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

