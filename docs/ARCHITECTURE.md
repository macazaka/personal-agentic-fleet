# 🏛️ Personal Agentic Fleet — System Architecture & Design Manual

Welcome to the comprehensive technical architecture manual for **Personal Agentic Fleet**. This document provides an in-depth breakdown of the system design, microkernel subsystems, deterministic event-driven bus, Tier 0 token conservation mechanics, multi-hyperscaler LLM gateway, and AI developer tools bridge.

---

## 1. High-Level System Architecture

Personal Agentic Fleet is designed as a **local-first, plug-and-play agentic microkernel**. It strictly enforces **Fleet Rule 1: Tier 0 Deterministic Governance ($0.00 / 0 Tokens Default)** while providing seamless on-demand bridges to all major cloud hyperscalers (Google, Microsoft, AWS, Anthropic, OpenAI) and AI developer tools (GitHub Copilot, Claude Code, Gemini CLI, Amazon Q).

```mermaid
flowchart TD
    subgraph ClientLayer["User & Interface Layer"]
        Browser["Web Dashboard\n(http://127.0.0.1:7890)"]
        CLI["Command Line Interface\n(python -m fleet.app)"]
        Console["Dashboard Command Console\n(Slash Commands & Natural Language)"]
        MCPClient["Model Context Protocol (MCP) Clients\n(Antigravity, Claude Code, Cursor, Copilot)"]
    end

    subgraph SecurityPerimeter["Localhost Security Perimeter"]
        AuthGuard["Localhost Session Auth & CSRF Guard\n(fleet/core/session_auth.py)"]
        SecHeaders["Security Headers & DNS Rebinding Blocker\n(CSP + CORS Lock + Host Whitelist)"]
        DPAPIVault["Hardware-Bound OS Vault (Windows DPAPI & macOS Keychain)\n(fleet/core/crypto_vault.py)"]
    end

    subgraph Microkernel["Microkernel & Core Services"]
        Server["Robust HTTPServer\n(fleet/server.py)"]
        Router["Domain API Router\n(fleet/core/registry.py)"]
        EventBus["Deterministic Event Bus\n(fleet/core/event_bus.py)"]
        Daemon["Background Fleet Daemon\n(fleet/daemon.py - 60m Pulse)"]
        FastMCP["FastMCP Server\n(fleet/mcp_server.py)"]
        DB["SQLite Embedded Database (WAL Mode)\n(PRAGMA secure_delete=ON)"]
    end

    subgraph Tier0Engine["Tier 0 Token & Cost Governance Engine ($0.00)"]
        IntentRouter["Deterministic Regex Intent Router\n(0 Tokens / $0.00)"]
        BM25RAG["Local Knowledge Base BM25 RAG\n(0 Tokens / $0.00)"]
        FuzzyCache["Fuzzy Jaccard + Trigram Semantic Cache\n(0 Tokens / $0.00)"]
        Compressor["AST Tokenizer & Prompt Compressor\n(20-50% Context Reduction)"]
        Deduplicator["SHA-256 Vision Image Deduplicator\n(Prevents Duplicate Token Billing)"]
        DeltaCache["MCP Delta Response Cache\n(0 Tokens for Unchanged Outputs)"]
    end

    subgraph HyperscalerGatewaySubsystem["Multi-Hyperscaler LLM Gateway"]
        Gateway["Hyperscaler Gateway\n(fleet/core/hyperscalers.py)"]
        GoogleHub["Google Ecosystem\n(Antigravity, Gemini API, Vertex AI, Gemini CLI)"]
        MicrosoftHub["Microsoft & GitHub Ecosystem\n(Azure OpenAI, Azure AI Foundry, GitHub Models)"]
        AWSHub["Amazon Web Services Ecosystem\n(Bedrock SigV4 IAM / Bearer: Claude, Nova, Titan)"]
        AnthropicHub["Anthropic Direct Messages API\n(Claude 3.7 Sonnet, Opus 5.5, Sonnet 5.5)"]
        OpenAIHub["OpenAI Direct API\n(GPT-4o, o1, o3-mini)"]
        OllamaHub["Local Ollama Engine\n(Llama 3.2, Qwen 2.5 Coder, DeepSeek-R1)"]
    end

    subgraph DevToolsBridge["AI Developer Tools Bridge"]
        DevBridge["Dev Tools Integration Bridge\n(fleet/core/dev_tools.py)"]
        CopilotBridge["GitHub Copilot CLI & IDE Sync\n(.github/copilot-instructions.md)"]
        ClaudeBridge["Claude Code CLI & Instruction Sync\n(CLAUDE.md)"]
        GeminiBridge["Google Gemini CLI & Vertex Sync\n(GEMINI.md)"]
        QBridge["Amazon Q Developer CLI Bridge\n(AWS Bedrock Fallback)"]
    end

    subgraph ModularAgents["Plug-and-Play Agent Ecosystem"]
        HealthAgent["Health & Wellness Agent\n(Metabolic Reversal, 6-Day Strength Split)"]
        OverviewAgent["Overview Agent\n(Daily Briefing, Tasks, Routines)"]
        OptimizerAgent["Silent PC Optimizer Agent\n(PSAPI Memory, Temp, DNS Flush)"]
        MirrorAgent["Antigravity Mirror Agent\n(Token Health & Parallel Agent Pool)"]
        BacklogAgent["Feature Backlog Agent\n(Kanban Roadmap)"]
        GmailAgent["Gmail Classifier Agent\n(5-Folder Deterministic Engine)"]
    end

    Browser --> AuthGuard
    Console --> AuthGuard
    CLI --> Microkernel
    MCPClient --> FastMCP

    AuthGuard --> SecHeaders --> Server --> Router
    Router --> EventBus
    FastMCP --> EventBus
    Daemon --> EventBus

    EventBus --> Tier0Engine
    Tier0Engine -->|Unresolved Complex Tasks| Gateway
    Tier0Engine -->|Developer Command| DevBridge

    Gateway --> GoogleHub
    Gateway --> MicrosoftHub
    Gateway --> AWSHub
    Gateway --> AnthropicHub
    Gateway --> OpenAIHub
    Gateway --> OllamaHub

    DevBridge --> CopilotBridge
    DevBridge --> ClaudeBridge
    DevBridge --> GeminiBridge
    DevBridge --> QBridge

    EventBus --> ModularAgents
    ModularAgents --> DB
    SecurityPerimeter --> DB
```

---

## 2. Core Microkernel Subsystems

### 2.1 Deterministic Event Bus (`fleet/core/event_bus.py`)
All inter-agent communication, background tasks, and MCP tool invocations route through the centralized `DeterministicEventBus`.
- **Decoupled Messaging**: Components emit `FleetEvent` objects containing `sender`, `target`, `action`, and `payload`.
- **Zero-Token Local Handlers**: Handlers for `agenda`, `files`, `notification`, `email`, and `system` execute pure Python logic without contacting external servers.
- **Parallel Dispatching**: Supports `bus.dispatch_parallel([events])` utilizing `ThreadPoolExecutor` for concurrent operations.

### 2.2 Scoped Agent Sandbox (`fleet/core/plugin_sandbox.py`)
Every agent in `fleet/agents/` is an isolated package with a strict `manifest.json`.
- **Least-Privilege Capabilities**: Agents declare required permissions (e.g., `db:read`, `db:write`, `ui:render`).
- **`ScopedDatabaseProxy`**: Wraps the database layer to block unauthorized table mutations or unauthorized reads.
- **Environment Sanitization**: When spawning subprocesses, `get_sanitized_plugin_env()` strips sensitive credentials and API tokens.

### 2.3 Tier 0 Token & Cost Governance Engine (`fleet/core/token_optimizer.py`)
Personal Agentic Fleet operates at **`$0.00` / 0 Cloud Tokens** by default using an 8-layer optimization pipeline:
1. **Deterministic Intent Router**: Evaluates input against known command patterns (`/task`, `/sync`, `/briefing`, `/notify`, `/security`, `/optimizer`).
2. **Offline BM25 Knowledge RAG**: Answers health, metabolic reversal, and workout questions using an indexed local corpus.
3. **Fuzzy Jaccard + Trigram Semantic Cache**: Reuses previous high-confidence answers for paraphrased queries.
4. **AST/Tokenizer Code Compressor**: Removes comments, redundant whitespace, and docstrings from code blocks passed in prompts.
5. **Prompt Batch Coalescer**: Groups consecutive user inputs to reduce LLM roundtrips.
6. **SHA-256 Vision Image Deduplicator**: Hashes uploaded screenshots and images, avoiding re-uploading and duplicate vision token billing.
7. **MCP Delta Response Cache**: Emits delta updates rather than full multi-kilobyte payloads when MCP data has not changed.
8. **Automated Tier Selection**: Routes unavoidable cloud LLM calls to the most cost-efficient tier (`flash_lite` -> `flash` -> `pro`).

---

## 3. Multi-Hyperscaler LLM Gateway (`fleet/core/hyperscalers.py`)

The fleet unifies inference across all major cloud hyperscalers through a standardized Python standard-library gateway:

| Hyperscaler | Supported Methods | Supported Models | Authentication |
| :--- | :--- | :--- | :--- |
| **Google** | Antigravity CLI (`agy`), Gemini REST API (AI Studio), Google Cloud Vertex AI, Gemini CLI (`gemini`) | `gemini-3.8-flash-high`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT` + `VERTEX_AI_TOKEN` or `gcloud` ADC |
| **Microsoft & GitHub** | Azure OpenAI Service, Azure AI Foundry Serverless, GitHub Models Inference API | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`, `Phi-4`, `DeepSeek-R1` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`, `AZURE_AI_FOUNDRY_KEY`, `GITHUB_TOKEN` |
| **Amazon Web Services (AWS)** | Amazon Bedrock Runtime (SigV4 IAM & Bearer), Amazon Q Developer CLI (`q`) | `anthropic.claude-3-7-sonnet`, `anthropic.claude-3-5-sonnet`, `amazon.nova-pro-v1:0`, `amazon.titan-text-express-v1`, `meta.llama3-3-70b` | Stdlib AWS SigV4 HMAC-SHA256 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`) or `AWS_BEARER_TOKEN` |
| **Anthropic** | Anthropic Direct Messages REST API, Claude Code CLI (`claude`) | `claude-3-7-sonnet-latest`, `claude-3-5-sonnet-latest`, `claude-3-5-haiku-latest`, `claude-3-opus-latest` | `ANTHROPIC_API_KEY` |
| **OpenAI Direct** | OpenAI Chat Completions API | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini` | `OPENAI_API_KEY` |
| **Local / Offline** | Local Ollama REST Daemon | `llama3.2`, `qwen2.5-coder`, `deepseek-r1`, `phi4`, `mistral` | `http://localhost:11434` (0 Cloud Tokens) |

### AWS SigV4 Pure-Stdlib Implementation
To eliminate heavy external SDK dependencies (`boto3`, `botocore`), [`_sign_aws_sigv4_headers`](../fleet/core/hyperscalers.py#L160-L236) implements the full AWS Signature Version 4 protocol in standard Python using `hmac` and `hashlib.sha256`. It computes canonical request hashes, string-to-sign scopes, and derived signing keys dynamically.

---

## 4. AI Developer Tools Bridge (`fleet/core/dev_tools.py`)

Personal Agentic Fleet acts as a bidirectional bridge with modern developer AI tools:
- **Detection & Introspection**: `detect_developer_tools()` probes for installed CLIs (`agy`, `gemini`, `claude`, `gh copilot`, `q`, `code`, `cursor`, `ollama`).
- **Execution Bridges with Automatic Cloud Fallback**:
  - `execute_claude_code()`: Invokes Anthropic's Claude Code CLI (`claude -p`), falling back to the Anthropic Direct API if the CLI is absent.
  - `execute_github_copilot_command()`: Invokes GitHub CLI Copilot (`gh copilot suggest/explain`), falling back to Azure OpenAI / GitHub Models.
  - `execute_google_gemini_cli()`: Invokes Google Gemini CLI (`gemini -p`), falling back to Google AI Studio / Vertex AI.
  - `execute_aws_q_developer()`: Invokes Amazon Q CLI (`q chat`), falling back to Amazon Bedrock.
- **Instruction Synchronization**:
  - Automatically generates and keeps in sync:
    - `.github/copilot-instructions.md` for GitHub Copilot in VS Code and GitHub CLI.
    - `CLAUDE.md` in repository root for Anthropic Claude Code.
    - `GEMINI.md` in repository root for Google Gemini CLI & Antigravity.

---

## 5. Control Center Web Dashboard & Server (`fleet/server.py`)

- **Robust Threading HTTP Server**: Implements `RobustThreadingHTTPServer` to handle concurrent UI requests, video byte-range streaming, and real-time polling.
- **Security Headers**: Injects Strict Content-Security-Policy (CSP), Permissions-Policy, Cross-Origin-Opener-Policy (COOP), Cross-Origin-Resource-Policy (CORP), and `X-Content-Type-Options: nosniff` on every HTTP response.
- **Domain API Dispatching**: Dynamically registers endpoints from all discovered agents.
- **Video Byte-Range Streaming (HTTP 206)**: Streams local workout and health MP4/MKV videos with seeking and fast scrubbing.

---

## 6. Background Routine Daemon (`fleet/daemon.py`)

The `FleetDaemon` executes silently in the background on a periodic loop:
- **Morning Briefing Pulse (08:30 IST)**: Generates high-priority agenda summaries and upcoming meeting reminders.
- **Evening Review Pulse (20:00 IST)**: Compiles habit completion metrics and day-end status.
- **2-Hour Email Sync Pulse**: Deterministically classifies new Gmail threads into 5 folders.
- **60-Minute Security Audit Pulse**: Runs the 12-layer security scanner and alerts the user if any finding is detected.
- **Scheduled CI Test Pulse**: Runs isolated pytest suites and records test health in SQLite.

---

## 7. Platform Abstraction Layer (Windows, macOS, Linux)

Personal Agentic Fleet provides native OS parity across modern desktop operating systems through its zero-dependency platform abstraction layer:

| Subsystem | Windows 10 / 11 Native | macOS (Apple Silicon & Intel) Native | Linux (Ubuntu, Debian, Fedora) |
| :--- | :--- | :--- | :--- |
| **Notifications** | WinRT Toast Notification Manager via PowerShell | AppleScript Notification Center (`osascript`) | Desktop notification daemon (`notify-send`) |
| **Secret Vault** | Windows DPAPI (`crypt32.dll`) | Apple Keychain Services CLI (`/usr/bin/security`) | Standard POSIX user vault (`chmod 0700`) |
| **RAM & Diagnostics** | In-process Win32 `PSAPI` & `GlobalMemoryStatusEx` | Native `sysctl` (`hw.memsize`) & `vm_stat` | `/proc/meminfo` & POSIX `ps -A -o comm,rss` |
| **DNS Resolver Flush** | `ipconfig /flushdns` | `dscacheutil -flushcache` + `killall -HUP mDNSResponder` | `resolvectl flush-caches` |
| **Memory Purge** | In-process `EmptyWorkingSet` | Native macOS `purge` command | Python `gc.collect()` |
| **Startup Services** | Registry Run keys (`HKCU` & `HKLM`) | `~/Library/LaunchAgents` & `/Library/LaunchAgents` | systemd user services |
| **CLI Tool Paths** | `%LOCALAPPDATA%\Programs`, `%APPDATA%\npm` | `/opt/homebrew/bin`, `/usr/local/bin`, `/Applications` | `/usr/bin`, `/usr/local/bin`, `~/.local/bin` |

---

## 8. Data & Storage Architecture

- **SQLite Engine**: Embedded database with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and synchronous checkpointing.
- **Secure Delete**: `PRAGMA secure_delete = ON` guarantees deleted task or memory rows are physically zeroed out from disk immediately.
- **At-Rest Hardware Encryption**: High-security settings, credentials, and notes are encrypted via Windows Data Protection API (`crypt32.dll`) and stored in `fleet/data/user/master.dpapi`.
- **Database Path Routing**: Enforces strict test-mode isolation; all unit test suites redirect SQLite access to `fleet_test_memory.db` so production data in `fleet_memory.db` is never modified during tests.
