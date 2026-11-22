# ⚡ Antigravity Live via AFCC — Architecture, Diagrams & Principal Critique

This wiki page documents the full runtime architecture of **Antigravity Live via AFCC (Agentic Fleet Control Center)** — tracing every client keystroke, image paste, voice directive, parallel dispatch, incremental transcript sync, and crash recovery path under the resource envelope of a personal Windows laptop, alongside the 10 architectural hardenings (`[AGL-01]`–`[AGL-10]`).

See also the source manual: [Antigravity Live via AFCC Architecture (Docs)](https://github.com/macazaka/personal-agentic-fleet/blob/main/docs/ANTIGRAVITY_LIVE_AFCC_ARCHITECTURE.md) | [[Architecture]] | [[Hyperscalers-Token-Optimizer-and-Scheduler]] | [[API-Reference]]

---

## 1. Personal Laptop Operating Envelope & Constraints

| Constraint Dimension | Personal Laptop Reality | Design Implication |
| :--- | :--- | :--- |
| **Shared RAM Ceiling** | IDE (`Code.exe` / Antigravity LS), browser tabs, Python server, and child `agy.exe` CLI processes share `16–32 GB` physical RAM. | Bounded HTTP worker pools (`16`), capped DOM (`80`) & transcript caches (`300`), SHA-256 media deduplication, and `88%` RAM admission control. |
| **Shared CPU & Thermals** | Continuous polling timers and regex scans compete with IDE editing and trigger laptop fans. | Visibility-aware (`document.hidden`), adaptive (`2.5s` active -> `12–20s` idle), delta-indexed (`since_step`), and O(N) non-backtracking overlap checks. |
| **Windows Process Cost** | `CreateProcessW` + `agy.exe` Node runtime bootstrap uses `~150–400ms` and `80–250MB` RAM per subagent. | Non-recursive fallback (`allow_agy_cli=False`), `60s` circuit breaker, and Windows `taskkill /F /T` process-tree termination on cancel/timeout. |
| **Single-Writer SQLite WAL** | All HTTP/agent threads share local SQLite WAL. | Atomic `UPDATE ... WHERE status='queued'` claims, startup orphan recovery, and short connection scopes. |
| **Browser Battery & Layout** | Right-docked chat stream stays visible across all tabs. | Incremental appends (`insertAdjacentHTML`), single-flight fetch guards, and payload signature diffing (`_afccHasPayloadChanged`). |
| **Zero-Cloud Privacy Firewall** | Transcripts, uploads, and voiceprints stay strictly local and gitignored. | Safe extension allowlist (`10 MB` upload cap), `X-Content-Type-Options: nosniff` on `/media/`, and local encryption. |

---

## 2. End-to-End Architecture Diagrams

### 2.1 High-Level System Architecture & Process / Trust Topology

```mermaid
flowchart TD
    subgraph BrowserUI["AFCC Browser SPA (http/https 127.0.0.1:7890)"]
        Dock["Right Dock or Tab (#viewAntigravity)"]
        VoiceHUD["Mahadev Voice Cockpit (#afccVoiceCopilotHud)"]
        PollLoop["Adaptive Poll Loop (scheduleAgPoll 2.5s..20s)"]
        VaultModal["Usage, Diagnostics & Vault Modals"]
    end

    subgraph HTTPBoundary["Dual-Stack TLS + Security Boundary (fleet/server.py)"]
        TLSGate["RobustThreadingHTTPServer (16 Worker Pool + MSG_PEEK TLS)"]
        SecGuard["Host Whitelist + CSRF/Session + nosniff + 20MB Ceiling"]
        Router["APIRouter (fleet/api/antigravity_api.py)"]
    end

    subgraph CoreEngine["Antigravity Mirror Engine (fleet/core/antigravity_mirror.py)"]
        Tier0["Tier-0 Slash + Intent + Semantic Cache ($0.00)"]
        Overlap["Task Fingerprint & Overlap Detector (O(N))"]
        Pool["Parallel Agent Pool (1..8 Slots + RAM Guard)"]
        Lease["Primary CLI Conversation Lease Lock"]
        CB["agy.exe Circuit Breaker (3 fails -> 60s open)"]
        TranscriptIO["Transcript Reader/Writer (_TRANSCRIPT_IO_LOCK + Delta Cache)"]
        Telemetry["Usage & Diagnostics Ledger (Tokens, Cost, Cache Hit%)"]
    end

    subgraph Storage["Local Storage & Transcripts"]
        SQLiteDB["SQLite WAL (chat_queue, token_preservation_vault, settings)"]
        BrainLogs["IDE / CLI Session Logs (~/.gemini/antigravity*/brain/*/transcript.jsonl)"]
        Uploads["Deduplicated Uploads (fleet/data/uploads + .user_uploaded)"]
    end

    subgraph Providers["Execution Backends (Multi-Provider + Fallback)"]
        AgyCLI["Google Antigravity CLI (agy.exe via stdin pipe)"]
        DevCLIs["Dev Tool CLIs (Claude Code, Copilot, Gemini CLI, Amazon Q)"]
        Hyperscaler["HyperscalerGateway (Vertex, Gemini API, Azure, Bedrock, OpenAI, Ollama)"]
    end

    Dock --> Router
    VoiceHUD --> Router
    PollLoop --> Router
    VaultModal --> Router

    Router --> TLSGate
    TLSGate --> SecGuard
    SecGuard --> Tier0
    Tier0 -->|"$0.00 Hit"| TranscriptIO
    Tier0 -->|"Natural Language Prompt"| Overlap
    Overlap -->|"Conflict or Full or High RAM"| SQLiteDB
    Overlap -->|"Clear & Admitted"| Pool

    Pool --> Lease
    Pool --> CB
    CB -->|"Closed / Half-Open"| AgyCLI
    CB -->|"Open / Unavailable"| Hyperscaler
    Pool --> DevCLIs
    Pool --> Hyperscaler
    AgyCLI -->|"Empty or Failure (allow_agy_cli=False)"| Hyperscaler

    AgyCLI --> TranscriptIO
    Hyperscaler --> TranscriptIO
    DevCLIs --> TranscriptIO
    TranscriptIO <--> BrainLogs
    Router <--> Uploads
    Pool <--> SQLiteDB
    Telemetry --> Router
```

### 2.2 Typed Prompt & Natural Language End-to-End Dispatch Sequence

```mermaid
sequenceDiagram
    actor User as "User (AFCC UI)"
    participant JS as "antigravity.js (submitAgCommand)"
    participant API as "antigravity_api.py (POST /api/antigravity/command)"
    participant Mirror as "antigravity_mirror.py (execute_dashboard_command)"
    participant DB as "SQLite WAL (chat_queue / settings)"
    participant Worker as "Worker Thread (_spawn_parallel_agent_worker)"
    participant Exec as "agy.exe or HyperscalerGateway"
    participant TLog as "transcript.jsonl (_TRANSCRIPT_IO_LOCK)"

    User->>JS: "Type prompt or click Send / Press Enter"
    JS->>JS: "Check _agCommandSubmitting double-submit guard"
    JS->>API: "POST /api/antigravity/command (command, images, model)"
    API->>Mirror: "execute_dashboard_command(cmd, images, model)"

    alt "Slash Command or Tier-0 Intent/RAG/Cache Hit ($0.00)"
        Mirror->>TLog: "append_transcript_turn(USER_INPUT + PLANNER_RESPONSE)"
        Mirror-->>API: "Immediate $0.00 deterministic result"
    else "Token Limit Exhausted"
        Mirror->>DB: "enqueue_chat_message + vault_pending_prompts"
        Mirror->>TLog: "append_transcript_turn(Vaulted notice)"
        Mirror-->>API: "status=vaulted (Windows toast alert)"
    else "Slots Full OR Overlap Detected OR RAM >= 88%"
        Mirror->>DB: "enqueue_chat_message(status='queued')"
        Mirror-->>API: "status=queued (overlap_reason or position)"
    else "Admitted for Immediate Parallel Execution"
        Mirror->>TLog: "append_transcript_turn(USER_INPUT)"
        Mirror->>Worker: "_spawn_parallel_agent_worker(Agent-N, cancel_event)"
        Mirror-->>API: "200 OK (agent_dispatched, Agent-N, active/max_slots)"
        API-->>JS: "Render green toast + wake scheduleAgPoll(true) @ 2.5s"

        Worker->>Exec: "_execute_agy_or_fallback (managed Popen or Hyperscaler)"
        Exec-->>Worker: "Reply text + usage telemetry"
        Worker->>TLog: "append_transcript_turn(PLANNER_RESPONSE)"
        Worker->>Worker: "finally: pop ACTIVE_PARALLEL_AGENTS & process_next_in_queue()"
    end

    Note over JS,TLog: "Next Poll Tick (2.5s active)"
    JS->>API: "GET /api/antigravity/transcript?limit=80&since_step=N"
    API->>TLog: "parse_transcript newline-aligned tail read"
    API-->>JS: "New delta turns -> insertAdjacentHTML + scrollBottom"
```

### 2.3 Voice-to-Antigravity Escalation & Image Upload Pipeline

```mermaid
sequenceDiagram
    actor Speaker as "User (Mic / Clipboard)"
    participant Voice as "antigravity.js (SpeechRecognition + DSP)"
    participant Disp as "omnibar_dispatcher.py (POST /api/voice/stream)"
    participant ImgAPI as "antigravity_api.py (POST /api/antigravity/upload)"
    participant Dedup as "token_optimizer.py (SHA-256 Registry)"
    participant Media as "fleet/data/uploads & .user_uploaded"
    participant Console as "Antigravity Console (submitAgCommand)"

    alt "Image Paste (Ctrl+V) or Drag-and-Drop"
        Speaker->>Voice: "Paste or drop image file"
        Voice->>ImgAPI: "POST /api/antigravity/upload (filename, base64)"
        ImgAPI->>ImgAPI: "Validate extension whitelist + 10MB decoded cap"
        ImgAPI->>Dedup: "deduplicate_uploaded_image(sha256)"
        alt "New Image SHA-256"
            Dedup->>Media: "Write image & mirror to brain/.user_uploaded + prune >200"
        else "Duplicate SHA-256"
            Dedup-->>ImgAPI: "Reuse cached URL (saves ~1,000 vision tokens)"
        end
        ImgAPI-->>Console: "Attach thumbnail to #agAttachmentStrip"
    end

    alt "Spoken Directive ('Ask Antigravity to ...' or Auto-Fallback)"
        Speaker->>Voice: "Speak command (verified by 12-D Biometric Owner Lock)"
        Voice->>Disp: "POST /api/voice/stream (transcript, routing_mode)"
        alt "Direct Voice Pattern (# 0B)"
            Disp-->>Voice: "mode='antigravity_direct' + ui_actions=[send_to_antigravity]"
        else "Unhandled Local Intent (# 12)"
            Disp-->>Voice: "mode='antigravity_auto_fallback' + ui_actions=[send_to_antigravity]"
        end
        Voice->>Voice: "Speak acknowledgment clause while queuing DOM action"
        Voice->>Console: "setAgChatEngineMode('antigravity_live') -> set value -> submitAgCommand()"
    end
```

### 2.4 Multi-Provider Model Routing & Non-Recursive Fallback Decision Tree

```mermaid
flowchart TD
    Start["Request enters _execute_agy_or_fallback(prompt, images, model)"] --> ModelSel["Resolve model: explicit param -> active_model -> select_optimal_model_tier"]
    ModelSel --> DevCheck{"CLI Dev Tool?\n(claude-code / copilot / gemini-cli / aws-q)"}
    DevCheck -->|"Yes"| RunDev["fleet/core/dev_tools.py -> append PLANNER_RESPONSE"]
    DevCheck -->|"No"| ExtCheck{"External Hyperscaler Prefix\n(azure-, aws-, ollama-, vertex-, openai-, non-local claude-)?"}

    ExtCheck -->|"Yes"| RunHS["HyperscalerGateway.complete(provider, model) -> REST / Ollama"]
    ExtCheck -->|"No"| AgyCheck{"agy.exe exists & CB Allows?\n(threshold=3 fails, cooldown=60s)"}

    AgyCheck -->|"Circuit Open or No agy.exe"| DirectHS["HyperscalerGateway.complete(provider='google', allow_agy_cli=False)"]
    AgyCheck -->|"Yes"| LeaseCheck["Acquire Primary CLI Conversation Lease"]
    LeaseCheck -->|"Primary Owner"| WithConv["Popen agy.exe --model M --output-format json --conversation CONV_ID"]
    LeaseCheck -->|"Concurrent Parallel Worker"| EphemTurn["Popen agy.exe --model M --output-format json (ephemeral, no --conversation)"]

    WithConv --> ParseOut{"Valid JSON output?"}
    EphemTurn --> ParseOut

    ParseOut -->|"Quota / 429 Error"| Vault["handle_token_exhaustion -> Vault Prompts -> Alert User"]
    ParseOut -->|"Success"| RecSuccess["Record usage tokens + reset CB + save primary conv_id -> append_transcript_turn"]
    ParseOut -->|"Cancelled by User"| CancelTurn["Kill process tree (taskkill /T) -> append Cancelled notice"]
    ParseOut -->|"Empty / Error / Timeout"| RecFail["Record CB failure -> Fallback: HyperscalerGateway(..., allow_agy_cli=False)"]
    DirectHS --> Heuristic{"Cloud Key Missing?"}
    RecFail --> Heuristic
    Heuristic -->|"Yes"| SmartNote["Offline Local Heuristic / Note Fallback (No Recursion Loop)"]
    Heuristic -->|"No"| CloudReply["Cloud Gemini / Vertex AI Reply -> append_transcript_turn"]
```

### 2.5 Parallel Agent Pool, Overlap, Cancellation, Vault & Recovery State Machine

```mermaid
stateDiagram-v2
    [*] --> Queued: "Enqueue when busy, overlapping, RAM >= 88%, or vaulted"
    [*] --> Claimed: "Admitted directly when slot free & orthogonal"

    Queued --> Claimed: "process_next_in_queue() atomic SQLite claim\n(no intra-batch overlap, slots free, RAM < 88%)"
    Queued --> Vaulted: "Token limit / 429 exhaustion"
    Queued --> Cancelled: "POST /api/antigravity/queue/cancel"
    Queued --> Queued: "Startup recovery from orphaned 'processing' row"

    Claimed --> Running: "_spawn_parallel_agent_worker() starts daemon thread & Popen"
    Running --> Vaulted: "429 / Quota error during execution"
    Running --> Cancelling: "POST /api/antigravity/agents/cancel"
    Cancelling --> Cancelled: "_terminate_process_tree() kills PID tree -> append notice -> drain queue"
    Running --> Completed: "Reply written to transcript.jsonl -> drain queue"
    Running --> Failed: "Non-quota exception -> error turn written to transcript.jsonl -> drain queue"

    Vaulted --> Queued: "POST /api/antigravity/tokens/resume (optional fallback model)"
    Completed --> [*]
    Failed --> [*]
    Cancelled --> [*]
```

### 2.6 Incremental Transcript Sync & SQLite Schema

```mermaid
flowchart LR
    Poll["Browser Poll GET /api/antigravity/transcript?limit=80&since_step=S"] --> Lock["Acquire _TRANSCRIPT_IO_LOCK"]
    Lock --> PathMemo["Resolve active path (3s TTL scandir memo outside tests)"]
    PathMemo --> Stat["stat(): compare path, mtime_ns, size"]
    Stat -->|"Unchanged & since_step >= cached_latest"| FastPath["O(1) Unchanged Fast Path (~0.02ms): unchanged=True, messages=[]"]
    Stat -->|"Appended bytes & matching 128B header signature"| Seek["seek(cached_size) -> read raw_delta bytes"]
    Seek --> NLCheck{"last_nl = raw_delta.rfind(newline)\nIs last_nl >= 0?"}
    NLCheck -->|"No partial line yet"| HoldSize["Keep cached_size intact (wait for \\n flush) -> unchanged=True"]
    NLCheck -->|"Yes"| Slice["Decode [:last_nl+1], advance cache size = cached_size + last_nl + 1"]
    Slice --> Filter["Filter step_index > since_step -> return delta messages"]
    Stat -->|"New session / truncated / initial load"| TailRead["Tail-window read (up to 1.5MB if >2MB file) -> populate 300-step cache"]
```

```mermaid
erDiagram
    CHAT_QUEUE {
        int id PK
        text prompt
        text images_json
        text model
        text status "queued | processing | completed | failed | vaulted | cancelled"
        text created_at
        text updated_at
    }
    TOKEN_PRESERVATION_VAULT {
        int id PK
        text session_id
        text model
        int tokens_used
        int token_limit
        text status "exhausted"
        text reason
        text preserved_prompts_json
        text created_at
    }
    SETTINGS {
        text key PK "active_model | max_parallel_agents | token_exhaustion_override | antigravity_cli_conversation_id"
        text value
    }
    CHAT_QUEUE ||--o{ TOKEN_PRESERVATION_VAULT : "vault_pending_prompts snapshots queued & processing rows"
```

---

## 3. Principal Architect Critique & Hardening Summary (`[AGL-01]`–`[AGL-10]`)

1. **`[AGL-01]` Transcript Concurrency & Partial-Line Safety**: Added `_TRANSCRIPT_IO_LOCK` and newline-aligned byte cursor advancement (`rfind(b"\n")`) in `parse_transcript()` and `append_transcript_turn()`.
2. **`[AGL-02]` Process Tree Control, Cancellation & Laptop RAM Guard**: Managed `Popen` subprocess registry, Windows `taskkill /F /T` termination, `POST /api/antigravity/agents/cancel`, `shutdown_all_parallel_agents()`, and >88% RAM admission queueing.
3. **`[AGL-03]` Crash-Safe Queue Recovery & Atomic Claims**: `recover_orphaned_queue_on_startup()`, atomic SQLite `claim_queued_chat_message()`, `_QUEUE_DRAIN_LOCK`, and intra-batch overlap checks.
4. **`[AGL-04]` Primary Conversation Lease & Parallel Isolation**: `_CLI_CONV_LOCK` grants persisted `antigravity_cli_conversation_id` exclusively to the primary lease holder while concurrent workers run ephemeral isolated turns.
5. **`[AGL-05]` True Token/Cost Telemetry & Post-Compaction Context**: Tracks real LLM vs Tier-0 turns, input/output tokens, and USD estimates; computes context usage from tail bytes after `<CONTEXT_SUMMARY>`.
6. **`[AGL-06]` Adaptive Polling & DOM Diffing**: `scheduleAgPoll()` (`2.5s` active -> `12s/20s` idle), startup deduplication in `app.js`, and `_afccHasPayloadChanged` DOM skipping.
7. **`[AGL-07]` Zero Silent Failures & Live Stop UI**: Error/cancel transcript turns, double-submit guard (`_agCommandSubmitting`), and `#agLiveWorkingIndicator` active-agent bar with 1-click Stop.
8. **`[AGL-08]` Memoized Transcript Discovery & Upload Hygiene**: `3s` `os.scandir` path cache, `10 MB` + safe extension whitelist on `/upload`, `200`-file / `250 MB` upload pruning, and `X-Content-Type-Options: nosniff` on `/media/`.
9. **`[AGL-09]` Non-Recursive `agy.exe` Fallback & Circuit Breaker**: `allow_agy_cli=False` prevents double CLI hangs, 3-failure `60s` circuit breaker fast-bypasses dead CLI binaries, and CLI runs deterministically at repository root.
10. **`[AGL-10]` Unified Live Diagnostics (`GET /api/antigravity/diagnostics`)**: Real-time engine health, cache hit rate, circuit breaker state, RAM guard, and LLM/Tier-0 telemetry surfaced directly inside `#usageModal`.
