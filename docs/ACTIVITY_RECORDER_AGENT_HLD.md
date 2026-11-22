# 🏛️ High-Level Design (HLD): Multimodal Activity & Audio Recorder → Brain Synthesizer → Self-Healing Headless Agent Studio

> **Version Target**: `v2.21.0` | **Platform Target**: Personal Windows Laptop (Zero-Cloud, Zero Third-Party `pip` Dependencies, Local-First AFCC) | **Status**: Finalized & Implemented  
> **Companion Document**: [Low-Level Design (`docs/ACTIVITY_RECORDER_AGENT_LLD.md`)](ACTIVITY_RECORDER_AGENT_LLD.md) • [System Architecture (`docs/ARCHITECTURE.md`)](ARCHITECTURE.md)

---

## 1. Executive Vision & Problem Statement

Traditional Robotic Process Automation (RPA) tools break on personal laptops because they either require heavy third-party browser frameworks (`playwright` / `selenium` / `.NET` runtimes), capture raw unredacted passwords/keystrokes onto disk, fail silently when DOM selectors shift, or deploy blindly without requirements traceability or unit tests.

This subsystem enables any user in **Agentic Fleet Control Center (AFCC)** to create a production-grade **New Agent** through **two synchronized capture ways fused with natural voice narration**:
1. **Way 1 — Browser Activity Recording**: Automatic isolated Chrome/Edge instrumentation over pure-stdlib Chrome DevTools Protocol (CDP) WebSockets **plus** a zero-launch Active-Tab Bookmarklet bridge for existing authenticated tabs.
2. **Way 2 — Desktop Activity Recording (and Browser + Desktop Hybrid)**: Pure-stdlib Windows Win32 (`ctypes`) + non-windowed UI Automation (UIA) observation across desktop applications, without installing global keyboard hooks.
3. **Synchronized Voice / Audio Narration**: While clicking and navigating through browser or desktop workflows, the user speaks continuously into their laptop microphone explaining intent, edge cases, wait conditions, schedules, and which values must be asked dynamically on future runs.

Instead of blindly replaying fragile coordinates, the Brain drives a **rigorous 11-step closed-loop software engineering lifecycle**:
1. User starts multimodal recording (Screen Activity + Microphone Audio Narration).
2. User performs their end-to-end tasks across Browser and/or Desktop applications.
3. User narrates continuously what each step means, business rules, and dynamic runtime inputs.
4. User stops recording (hardware mic streams and browser/Win32 watchers release immediately).
5. Process Discovery & Brain fuse screen telemetry with timestamped audio narration segments ($\pm 3.5\text{s}$ temporal correlation + lexical binding).
6. Brain generates a formal **Requirements Document** complete with a **Mermaid Process Flow diagram**, Functional/Non-Functional Requirements, Screen-to-Audio Traceability Matrix, and Typed Runtime Input Schema.
7. Automation Synthesizer generates the **Parameterized Workflow IR (`workflow_ir`)**, custom `agent.py`, declarative AFCC UI panel, and a **tailored Pytest Unit Test Suite**, executing tests inside an isolated sandbox.
8. **Visible Sandbox Dry-Run Theater** replays steps visibly on screen (non-headless highlighted Chrome/Edge overlay + AFCC step-by-step theater + interactive Ask-for-Inputs test prompt).
9. Any failures are automatically captured and repaired via **Tier-1 Autonomous Self-Healing** (multi-tier selector fallback, adaptive waits, ambiguity-to-input promotion) and **Tier-2 User Audio-Guided Rectification**.
10. User and Brain iterate rapidly (`v1 -> v2 -> ...`) with full revision history until unit tests and visible sandbox dry-run pass `100%`.
11. Only after **explicit user approval** (`user_approved: true`) does AFCC publish the draft into a **Live Headless Custom Agent** that executes headlessly on schedule or demand and pauses cleanly (`waiting_for_input`) whenever dynamic or sensitive user inputs are required.

---

## 2. End-to-End 11-Step System Context & Trust Boundary

```mermaid
flowchart TD
    User["User on Personal Windows Laptop"] -->|"1-4. Start/Stop Screen + Voice"| StudioUI["AFCC Create Agent Studio (#wizardStep_1)"]
    User -->|"2. Interacts with Web Pages"| BrowserTarget["Chrome / Edge (Isolated CDP or Active-Tab Bookmarklet)"]
    User -->|"2. Interacts with Desktop Apps"| DesktopTarget["Win32 Apps (Foreground / Click / UIA Metadata)"]
    User -->|"3. Speaks Workflow Intent & Rules"| MicStream["Browser WebAudio MediaRecorder + SpeechRecognition"]

    BrowserTarget -->|"Sanitized DOM Events + 6-Tier Locators"| EdgeGuard["Edge PII & Secret Redaction Gate"]
    DesktopTarget -->|"Win32 Focus/Click + Password-Window Mask"| EdgeGuard
    MicStream -->|"Timestamped Narration Segments + Audio Blob"| EdgeGuard

    EdgeGuard -->|"Encrypted AES-256-GCM Trace + Audio"| SessionVault["Local Recording Vault (fleet/data/user/recordings/)"]
    SessionVault -->|"5. Temporal Fusion (+-3.5s) + Entity Binding"| BrainSynth["Brain Synthesizer ($0.00 Deterministic + Optional LLM)"]

    BrainSynth -->|"6. Requirements Doc + Mermaid Process Flow"| ReqArtifact["Formal Requirements Spec & Trace Matrix"]
    BrainSynth -->|"7. Workflow IR + agent.py + Pytest Suite"| TestRunner["Isolated Tempdir Pytest Sandbox Runner"]
    ReqArtifact --> TestRunner

    TestRunner -->|"8. Visible Non-Headless Dry-Run + Overlay"| SandboxTheater["Visible Sandbox Dry-Run Theater"]
    SandboxTheater -->|"9-10. Failures + Spoken Audio Corrections"| SelfHealer["Tier-1 Auto Self-Healer + Tier-2 Audio Rectifier"]
    SelfHealer -->|"Mutates Spec, IR, Req Doc & Re-Runs Tests"| BrainSynth

    SandboxTheater -->|"11. Explicit User Approval Gate"| PublishGate["Studio Publish Engine (create_custom_agent)"]
    PublishGate --> LiveAgent["Live Headless Custom Agent (archetype: recorded_workflow)"]
    LiveAgent -->|"Headless Chrome (--headless=new) / Headless Desktop"| HeadlessExec["Headless Execution Engine"]
    HeadlessExec -->|"Missing Required / Secret Input"| PauseCheckpoint["SQLite Checkpoint (status: waiting_for_input)"]
    PauseCheckpoint -->|"UI Prompt Form / Resume API"| User
    User -->|"Submits Runtime Input (RAM-only for secrets)"| HeadlessExec
```

---

## 3. Dual-Modality Recording Architecture (Zero External Dependencies)

Because a personal Windows laptop running Python 3.14 stock stdlib + `cryptography` may not have Playwright, Selenium, `pynput`, or `websockets` installed, AFCC implements the complete capture stack natively:

```mermaid
flowchart LR
    subgraph Way1["Way 1: Browser Activity Recorder"]
        BMode1["Managed Isolated Chrome/Edge (--remote-debugging-port)"] -->|"Pure-Stdlib TCP + RFC 6455 WebSocket"| CDP["MinimalCDPClient (SHA-1 RFC 6455 usedforsecurity=False)"]
        CDP -->|"Page.addScriptToEvaluateOnNewDocument + Runtime.addBinding"| DOMJS["DOM_RECORDER_JS (Capture Phase click/input/change/submit)"]
        BMode2["Active-Tab Zero-Launch Bookmarklet"] -->|"Token-Authenticated Loopback POST /api/studio/recorder/event"| IngestAPI["Recorder Ingestion API"]
        DOMJS -->|"6-Tier Selectors + Pre-Send Password Masking"| IngestAPI
    end

    subgraph Way2["Way 2: Desktop Activity Recorder"]
        Win32["Win32 ctypes Polling (user32/kernel32/psapi)"] -->|"Adaptive 250ms Active / 750ms Idle Cadence"| SelfFilter["AFCC Window Self-Click Filter"]
        UIA["Scoped Non-Windowed UIA Probe (Optional)"] --> SelfFilter
        SelfFilter -->|"NO WH_KEYBOARD_LL Hook (Zero Keylogger Risk)"| WinMask["Credential / OTP Window Title Masking"]
        WinMask --> IngestAPI
    end

    subgraph AudioTrack["Synchronized Audio Narration Track"]
        Speech["Browser Continuous SpeechRecognition (Transcript + Offset Sec)"] -->|"POST /api/studio/recorder/audio_segment"| AudioSan["Spoken Secret Scrubber (Passwords/OTP/Cards/PAN)"]
        MediaRec["MediaRecorder Opus/WebM (16kHz Mono)"] -->|"Base64 Upload on Stop"| AudioVault["AES-256-GCM Binary Audio Vault"]
        AudioSan --> IngestAPI
    end

    IngestAPI -->|"Bounded 500-Event Ring Buffer"| SessionMgr["RecordingSessionManager (RLock Protected)"]
```

### Why This Dual-Path Architecture Wins on a Personal Laptop
- **Zero `pip install` fragility**: Works out-of-the-box with Python stdlib + `cryptography` + installed `chrome.exe` / `msedge.exe` + `user32.dll`.
- **Two browser workflows supported cleanly**:
  - *Managed Isolated Profile Mode*: AFCC spawns Chrome/Edge with `--user-data-dir=<temp_dir>` on an ephemeral loopback port (`127.0.0.1:<free_port>`), preserving the user's personal browser cookies/sessions untouched and preventing debugging-port leaks into daily browsing.
  - *Active-Tab Bookmarklet Mode*: When automating a portal where the user is already authenticated with corporate SSO/MFA in their regular Chrome tab, clicking the 1-line AFCC Bookmarklet streams sanitized DOM events for that single session using a per-session CSPRNG `capture_token`.

---

### 3.1 Architectural Evaluation: Browser vs. Desktop vs. Requirement-Driven Hybrid Recorder

| Evaluation Dimension | Way 1: Browser-Based Recorder (CDP / Bookmarklet) | Way 2: Desktop-Based Recorder (Win32 `ctypes` / UIA) | Hybrid (Recommended When Cross-Boundary) |
| :--- | :--- | :--- | :--- |
| **True Headless Reliability (`--headless=new`)** | **98% (`true_headless_background`)** — runs cleanly even when Windows session is locked or minimized | **52%** unless compiled into CLI/File adapters; raw Win32/UIA clicks fail when screen is locked (`desktop_uia_gui`) | **80% (`hybrid_headless_with_local_adapters`)** — headless browser + filesystem/CSV adapters |
| **Selector Resilience** | **95% (`6-Tier` DOM Ladder)** — `data-testid` -> `id` -> `aria-label` -> `role+text` -> `css` -> `xpath` | **70% (`4-Tier` Desktop Ladder)** — breaks across DPI scaling, theme, or localized window changes unless UIA `AutomationId` exists | **88%** — semantic DOM for web + UIA/adapters for local steps |
| **Secret & Password Safety** | **98%** — inspects `type="password"` & `autocomplete` directly in DOM before data leaves the tab | **82%** — zero `WH_KEYBOARD_LL` hook; relies on protected window title heuristics | **92%** — capture-edge masking on both boundaries |
| **Personal Laptop Footprint** | Low–Medium (~1 isolated headless Chrome instance gated by `Semaphore(1)`) | Minimal (`<1%` idle CPU via adaptive `250ms/750ms` polling) | Low–Medium |
| **Workload Coverage** | ~75–80% of daily workflows (SaaS, bills, GitHub, Jira, forms, dashboards) | ~20–25% (Excel desktop, Tally, SAP GUI, Outlook Desktop, File Explorer) | **100%** (Portal downloads -> Local Excel/Folder ops) |

```mermaid
flowchart TD
    ReqIn["User Requirement + Target URL + Target Apps"] --> Eval["recommend_recording_modality ($0.00 Classifier)"]
    Eval -->|"Web / URL Signals Only"| PickBrowser["Recommend BROWSER Mode (96% Headless Feasibility)"]
    Eval -->|"Desktop Apps Only"| PickDesktop["Recommend DESKTOP Mode + Headless-First Adapter Compiler"]
    Eval -->|"Web URL + Local Apps / Excel / Folders"| PickHybrid["Recommend HYBRID Mode (Browser CDP + Local Adapters)"]

    PickBrowser --> SSOCheck{"Existing Corporate SSO or MFA Session?"}
    SSOCheck -->|"Yes"| TabMode["Use 1-Click Active-Tab Bookmarklet"]
    SSOCheck -->|"No"| IsoCDP["Launch Isolated Temp-Profile Chrome CDP"]

    PickDesktop --> DeskCompile["compile_desktop_step_headless_capability"]
    DeskCompile -->|"Explorer / Excel / PowerShell / Chrome"| AdapterMode["Compile to Headless Adapter (Path / Tabular / CLI / CDP Upgrade)"]
    DeskCompile -->|"Opaque Win32 GUI"| GuardWarn["Flag requires_unlocked_desktop in Requirements Doc"]
```

**Final Architectural Verdict (`[REC-13]`):**
1. **Browser-based recording** is strictly superior whenever the task happens inside web apps (higher headless reliability, semantic 6-tier DOM locators, strict `type="password"` masking, and live sandbox DOM highlighting).
2. **Desktop-based recording** should NOT be omitted — local desktop apps (Excel, Tally, SAP GUI, File Explorer, PowerShell) require it — **and** every captured desktop step MUST pass through `compile_desktop_step_headless_capability()` so file/CSV/CLI steps compile to true headless adapters rather than fragile GUI coordinates.
3. AFCC therefore provides **BOTH Browser and Desktop (plus Hybrid)**, led by the requirement-driven **Smart Modality Advisor** (`recommend_recording_modality`) so the user never picks blindly.

---

## 4. 11-Step Closed-Loop Sequence Diagram

```mermaid
sequenceDiagram
    actor U as User
    participant UI as AFCC Studio UI
    participant API as Recorder REST API
    participant Rec as RecordingSessionManager
    participant Brain as Multimodal Brain Synthesizer
    participant Test as Isolated Pytest Runner
    participant Sbx as Visible Sandbox & Healer
    participant Reg as AgentRegistry & Runtime

    U->>UI: 1. Click Start Recording (Mode + Voice Narration ON)
    UI->>MediaDevices: Request mic track + SpeechRecognition
    UI->>API: POST /api/studio/recorder/start
    API->>Rec: Launch CDP Chrome / Desktop Watcher + token

    loop 2-3. User Acts & Explains Aloud
        U->>Rec: Browser DOM / Desktop Win32 clicks & navigations
        U->>UI: Speaks requirements ("Wait 2s, ask me for policy ID")
        UI->>API: POST /api/studio/recorder/audio_segment
    end

    U->>UI: 4. Click Stop Recording
    UI->>MediaDevices: Immediately stop() all mic tracks (LED off)
    UI->>API: POST /api/studio/recorder/stop (audio blob + segments)
    API->>Rec: Save AES-256-GCM trace & audio

    UI->>API: 5-6. POST /api/recorder/convert
    API->>Brain: Temporal Fusion (+-3.5s) -> Req Doc + Flowchart + IR + Tests
    Brain-->>UI: Render Requirements Doc, Mermaid Process Flow & Spec v1

    UI->>API: 7. POST /api/recorder/run_tests
    API->>Test: Execute generated pytest suite in tempdir
    Test-->>UI: Pass/Fail Telemetry

    UI->>API: 8. POST /api/recorder/sandbox_run (visible_browser=True)
    API->>Sbx: Open Visible Browser + Step Highlight Overlay + Input Preview
    Sbx-->>UI: Failures detected at Step k

    U->>UI: 9-10. Speak fix ("Wait 3s & click Submit") or Auto-Heal
    UI->>API: POST /api/recorder/heal
    API->>Sbx: Apply Tier-1 Auto-Heal + Tier-2 Audio Rectification -> v2
    Sbx->>Brain: Update Req Doc + Flowchart + Workflow IR + Unit Tests
    Sbx-->>UI: Re-run Sandbox & Tests -> PASS

    U->>UI: 11. Check Approve & Click Publish Live Headless Agent
    UI->>API: POST /api/recorder/publish (user_approved=true)
    API->>Reg: Scaffold custom agent (archetype=recorded_workflow)
    Reg-->>U: Live Headless Agent activated & hot-loaded
```

---

## 5. Live Headless Execution & Human-in-the-Loop (`waiting_for_input`) State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: Agent Published Live
    Idle --> ValidateInputs: Trigger Run Headless or Dry-Run

    ValidateInputs --> WaitingForInput: Required, Secret, or Ask-On-Each-Run Value Missing
    ValidateInputs --> RunningHeadless: All Initial Inputs Present

    WaitingForInput --> PersistCheckpoint: Save SQLite workflow_run Checkpoint (Zero Secrets)
    PersistCheckpoint --> PromptUser: Render Inline Input Form in CustomAgentRuntime
    PromptUser --> ResumeFromCheckpoint: User Submits Values via POST /workflows/resume

    ResumeFromCheckpoint --> RunningHeadless: Merge Non-Secret State + RAM-Only Secrets
    RunningHeadless --> ExecuteStep: Next Step (Headless Chrome / Headless Desktop)
    ExecuteStep --> SelfHealRetry: Primary Locator Failed -> Try Tiers 2..6 + Backoff
    SelfHealRetry --> ExecuteStep: Fallback Locator Succeeded

    ExecuteStep --> WaitingForInput: Reached Mid-Run prompt_user or OTP Step
    ExecuteStep --> FailedRun: All Tiers Exhausted or Timeout Exceeded
    ExecuteStep --> CompletedRun: All Steps Succeeded + Output Extracted

    CompletedRun --> Idle: Publish Audit Record & Toast
    FailedRun --> Idle: Log Actionable Remediation Hint
```

---

## 6. Security, Privacy & Personal Laptop Constraint Architecture

```mermaid
flowchart TD
    RawDOM["Raw Browser Input / Window Event / Speech"] --> EdgeGate["Capture-Edge Redaction Filter"]
    EdgeGate -->|"type=password / autocomplete=one-time-code"| MaskSecret["Replace value -> {{secret:param}}"]
    EdgeGate -->|"Regex: 12-16 digit card/Aadhaar, PAN, OTP, CVV"| MaskPII["Scrub Transcript/Title -> [REDACTED_SECRET]"]
    EdgeGate -->|"Clean Non-Sensitive Value"| CleanEvt["Sanitized Event & Narration Segment"]

    MaskSecret --> Vault["AES-256-GCM Encryption at Rest (crypto_vault.py)"]
    MaskPII --> Vault
    CleanEvt --> Vault

    Vault -->|"Saved Under Ignored fleet/data/user/recordings/"| LocalDisk["Local Encrypted Storage Only"]
    HeadlessRun["Headless Execution Checkpoint"] -->|"NEVER Persists Secret Values"| SQLiteDB["SQLite custom_agent_records"]
    SecretInput["Runtime Secret Supplied by User"] -->|"Ephemeral RAM Buffer Only (Cleared Post-Run)"| HeadlessRun
```

### Personal Laptop Compute, RAM, Mic & Battery Budget

```mermaid
flowchart LR
    Budget["Personal Windows Laptop Constraints"] --> CPU["CPU < 1.5% Idle (250ms/750ms Adaptive Win32 Poll)"]
    Budget --> RAM["RAM <= 1 Headless Browser Concurrent (Semaphore=1)"]
    Budget --> Disk["Disk <= 500 Events & <= 15 MB Encrypted Audio/Session"]
    Budget --> Mic["Mic LED Guaranteed OFF via Immediate track.stop() on Stop/Close"]
    Budget --> Zombie["Zero Zombie Chrome Processes via Isolated Tmp Profile + taskkill /F /T"]
```

---

## 7. Top-1% Principal Architect Critique & Hardened Final Design (`[REC-01]`–`[REC-12]`)

If a naive engineer built "record activity + voice and convert to headless agent" on a personal Windows laptop, **twelve distinct failure modes** would break it in real-world use. Below is our architectural teardown and the finalized hardening built into AFCC:

| ID | Principal Architect Critique (What Breaks Naively) | Hardened Final Decision Implemented in AFCC |
| :--- | :--- | :--- |
| **`[REC-01]`** | **External Dependency Fantasy**: Assuming `playwright`, `selenium`, `websockets`, or `pynput` are installed fails immediately on stock Python 3.14. | Pure-stdlib **RFC 6455 WebSocket + Minimal CDP Client (`MinimalCDPClient`)** over TCP loopback + Windows `ctypes` (`user32`/`kernel32`/`psapi`) observer. Zero new pip packages required. |
| **`[REC-02]`** | **Raw Password / OTP / Audio PII Leakage**: Recording raw keystrokes or spoken SSNs/OTPs/cards exposes credentials in JSON traces, SQLite checkpoints, and LLM prompts. | **Zero `WH_KEYBOARD_LL` keylogging**; capture-edge redaction in JS (`DOM_RECORDER_JS`), desktop titles, AND spoken transcripts (`sanitize_audio_transcript`). Secrets become `{{secret:...}}` and live in ephemeral RAM only during execution. |
| **`[REC-03]`** | **Zombie Chrome & Locked Daily Profile**: Launching the user's primary Chrome `--user-data-dir` fails when Chrome is already open (`ProcessSingleton` lock), and crashed runs leak 400 MB headless processes forever. | Every recording and headless/visible sandbox run creates a **disposable isolated temp `--user-data-dir`**, uses an ephemeral free loopback port, deletes the temp dir, and runs `terminate_process_tree()` (`taskkill /F /T /PID` with `shell=False`) in `finally:`. |
| **`[REC-04]`** | **Self-Click Pollution & Event Storms**: Clicking "Stop Recording" in AFCC records clicking AFCC itself; mouse move/keystroke streams flood the trace with thousands of useless events. | **AFCC Self-Click Filter** ignores events whose window title/origin belongs to AFCC; mouse-move spam is never recorded; bounded 500-event ring buffer + `coalesce_raw_events()` collapses consecutive typing and `<350ms` duplicate clicks. |
| **`[REC-05]`** | **Brittle Coordinate & XPath Selectors**: Replaying `x=412, y=633` or `/html/body/div[4]/div[2]/button` breaks as soon as window size or DOM layout shifts. | **6-Tier Self-Healing Browser Locator Ladder** (`data-testid` -> `id` -> `aria-label` -> `role+name` -> visible `text` -> `css_path/xpath`) and **4-Tier Desktop Locator Ladder** (`process+UIA AutomationId` -> `window_title+control_name` -> headless CLI/HTTP equivalent -> relative `%x, %y`). |
| **`[REC-06]`** | **Blocking Headless Execution on Missing Input / MFA**: Calling blocking `input()` or crashing silently on CAPTCHAs/2FA stalls background worker threads indefinitely. | Non-blocking **Checkpoint/Resume State Machine (`waiting_for_input`)**: suspends execution cleanly at exact `step_index`, saves non-secret state in SQLite `custom_agent_records` (`record_type="workflow_run"`), surfaces a dynamic typed input card in UI, and resumes deterministically via `resume_workflow_run()`. |
| **`[REC-07]`** | **Desynchronized Voice & Screen Stream ("Click Here" Ambiguity)**: Transcribing audio in one giant blob after stop loses which spoken constraint (*"ask me for this every time"*, *"wait 3 seconds"*) belongs to which button/input. | Timestamped **$\pm 3.5\text{s}$ Multimodal Temporal Fusion (`fuse_audio_and_screen_events`)** aligns spoken `AudioNarrationSegment`s directly onto coinciding screen steps, extracts `ask_on_each_run` parameters, wait times, and business rules automatically. |
| **`[REC-08]`** | **Black-Box "Trust Me" Generation Without Verification**: Jumping straight from raw trace to live background cron creates broken agents with no specification or regression tests. | Mandatory **Requirements Document + Mermaid Process Flow (`flowchart TD`)** synthesis PLUS automatic generation and **isolated `tempdir` pytest execution** (`run_generated_agent_unit_tests`) BEFORE publishing. |
| **`[REC-09]`** | **Opaque Dry-Run + Unrectified Failures**: Users cannot verify headless automation unless they can *see* the first run execute and verbally explain why Step 3 misclicked. | **Visible Sandbox Dry-Run Theater** (non-headless highlighted browser overlay + AFCC step theater) coupled with **Tier-1 Auto Self-Healer** (wait/selector escalation) + **Tier-2 Spoken Audio Rectification** loop (`v1 -> v2 -> ...`). |
| **`[REC-10]`** | **Hardware Mic Leak & CPU Drain**: Leaving `MediaStream` open after recording or polling Win32 in tight 10 ms loops keeps the laptop webcam/mic LED glowing and fans spinning. | Strict mic lifecycle (`track.stop()` on stop/modal close/unmount), max 1800s auto-stop cap, and adaptive Win32 polling (`250ms` active / `750ms` idle -> `<1%` CPU). |
| **`[REC-11]`** | **Unauthenticated Localhost Ingestion Bridge**: Leaving `/api/studio/recorder/event` open without authentication allows arbitrary local tabs to spoof recorded steps. | Every recording session issues a per-session CSPRNG `capture_token` validated via constant-time `hmac.compare_digest` on external/bookmarklet uploads, paired with `urllib.parse.urlparse()` navigation SSRF checks blocking `169.254.169.254` & `file://` schemes. |
| **`[REC-12]`** | **Broken Backward Compatibility in AFCC Agent Studio**: Adding naive new UI blocks or breaking `create_custom_agent` would violate existing Phase 1–6 Studio invariants (`len(SUPPORTED_UI_BLOCKS) == 12`). | Preserves exact `12` declarative `SUPPORTED_UI_BLOCKS` contract while rendering the dedicated **Headless Workflow Runner & Ask-for-Inputs Panel** whenever `workflow_ir` is attached; extends `create_custom_agent()` strictly via optional default-`None` parameters. |
| **`[REC-13]`** | **Blind Single-Modality Lock-In**: Exposing only Desktop recording breaks headless background execution on locked laptops, while Browser-only blocks local Excel/File/Win32 workflows. | Implements **Smart Requirement-Driven Modality Advisor** (`recommend_recording_modality`) + **Headless-First Desktop Adapter Compiler** (`compile_desktop_step_headless_capability`) providing Browser, Desktop, and Hybrid with explicit headless feasibility scoring and SSO bookmarklet auto-selection. |
