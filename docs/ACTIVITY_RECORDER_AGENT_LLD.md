# 🔧 Low-Level Design (LLD): Multimodal Activity & Audio Recorder, Requirements Compiler, Visible Sandbox, Self-Healer & Headless Workflow Runtime

> **Version Target**: `v2.21.0` | **Primary Implementation Module**: [`fleet/core/activity_recorder.py`](../fleet/core/activity_recorder.py) • [`fleet/api/recorder_api.py`](../fleet/api/recorder_api.py)  
> **Companion Document**: [High-Level Design (`docs/ACTIVITY_RECORDER_AGENT_HLD.md`)](ACTIVITY_RECORDER_AGENT_HLD.md)

---

## 1. Module & Class Architecture (`classDiagram`)

```mermaid
classDiagram
    class RecordingSessionManager {
        +RLock _lock
        +Dict active_session
        +Path recordings_dir
        +start_recording(mode, start_url, launch_browser, record_audio, label) Dict
        +ingest_event(event, session_id, capture_token, trusted_internal) Dict
        +ingest_audio_segment(offset_sec, transcript, duration_sec, confidence, is_final, ...) Dict
        +mark_dynamic_input(name, label, input_type, prompt_question, required, sensitive, default_value) Dict
        +stop_recording(session_id, audio_base64, audio_mime, audio_segments) Dict
        +get_status() Dict
        +list_sessions(limit) List
        +load_session(session_id) Dict
        +save_session(session_data) Path
        +delete_session(session_id) bool
    }

    class MinimalCDPClient {
        +socket sock
        +int msg_id
        +connect(ws_url, timeout) void
        +compute_ws_accept_key(ws_key) str
        +encode_ws_frame(payload, opcode, masked) bytes
        +recv_ws_frame() Tuple
        +send_command(method, params, timeout) Dict
        +poll_events(timeout) List
        +close() void
    }

    class BrowserCDPRecorder {
        +int debug_port
        +Path profile_dir
        +Popen process
        +MinimalCDPClient cdp
        +Thread pump_thread
        +start(start_url, on_event) bool
        +stop() void
    }

    class DesktopActivityWatcher {
        +Thread watch_thread
        +Event stop_event
        +int last_hwnd
        +start(on_event) void
        +stop() void
        -_poll_win32_snapshot() Dict
    }

    class MultimodalBrainSynthesizer {
        +coalesce_raw_events(raw_events) List
        +fuse_audio_and_screen_events(steps, audio_segments) Dict
        +build_requirements_document(name, modality, steps, input_schema, audio_segments, rules, criteria) Dict
        +generate_agent_unit_tests_code(agent_spec) str
        +synthesize_agent_from_recording(session_id, ...) Dict
    }

    class VisibleSandboxAndHealer {
        +run_generated_agent_unit_tests(agent_spec, unit_tests_code) Dict
        +run_visible_sandbox_dry_run(session_id, user_inputs, visible_browser, simulate_only, inject_failure_step) Dict
        +heal_and_iterate_workflow(session_id, failures, user_audio_feedback, user_text_feedback, ...) Dict
        +publish_recorded_agent(session_id, agent_registry, user_approved, overrides, db) Dict
    }

    class HeadlessWorkflowRunner {
        +Semaphore _HEADLESS_SEMAPHORE
        +execute_recorded_workflow(agent, user_inputs, dry_run, task) Dict
        +resume_workflow_run(agent, run_id, user_inputs, dry_run) Dict
        -_execute_browser_steps_cdp(steps, resolved_inputs, headless, ...) List
        -_execute_desktop_step(step, resolved_inputs, dry_run) Dict
    }

    RecordingSessionManager --> BrowserCDPRecorder
    RecordingSessionManager --> DesktopActivityWatcher
    BrowserCDPRecorder --> MinimalCDPClient
    MultimodalBrainSynthesizer --> RecordingSessionManager
    VisibleSandboxAndHealer --> MultimodalBrainSynthesizer
    HeadlessWorkflowRunner --> VisibleSandboxAndHealer
```

---

## 2. Canonical JSON Schemas

### 2.1 `RawRecordedEvent` (Captured by Browser CDP/Bookmarklet or Desktop Watcher)
```json
{
  "event_id": "evt_00012",
  "offset_sec": 14.28,
  "timestamp": "2026-11-22T18:45:10.120000",
  "channel": "browser",
  "action": "change",
  "url": "https://portal.example.com/renewals",
  "title": "Policy Renewal Search",
  "locators": {
    "data_testid": "policy-number-input",
    "id": "policyNo",
    "aria_label": "Policy Number",
    "name": "policy_number",
    "role": "textbox",
    "placeholder": "Enter policy number",
    "label_text": "Policy Number",
    "text": "",
    "css_path": "#policyNo",
    "xpath": "//*[@id='policyNo']"
  },
  "value": "POL-98412",
  "input_type": "text",
  "sensitive": false,
  "param_hint": "policy_number",
  "source": "cdp_dom"
}
```
> **Edge Secret Rule**: Whenever `input_type == "password"`, `autocomplete in ("one-time-code", "current-password", "new-password", "cc-number", "cc-csc")`, or `SENSITIVE_FIELD_RE` matches field/window metadata, `"value"` is immediately replaced at capture edge with `"{{secret:<param_hint>}}"` and `"sensitive": true`.

### 2.2 `AudioNarrationSegment` (Timestamped Voice Narration)
```json
{
  "segment_id": "aud_00004",
  "offset_sec": 15.10,
  "duration_sec": 2.8,
  "timestamp": "2026-11-22T18:45:11.020000",
  "transcript": "Here ask me for the policy number every time, wait 2 seconds after submitting, and extract the renewal status.",
  "confidence": 0.94,
  "is_final": true,
  "linked_step_index": 2
}
```

### 2.3 `InputFieldSpec` (Runtime Parameter Prompt Schema)
```json
{
  "key": "policy_number",
  "label": "Policy Number",
  "type": "text",
  "prompt": "Enter the Policy Number for this run:",
  "required": true,
  "ask_on_each_run": true,
  "sensitive": false,
  "default": "POL-98412",
  "options": [],
  "source": "audio_and_dom_fusion"
}
```
Supported `type` values: `"text"`, `"secret"`, `"number"`, `"date"`, `"url"`, `"select"`, `"file"`. For `"secret"` fields, `"default"` is ALWAYS forced to `""` and `"sensitive"` to `true`.

### 2.4 `ParameterizedWorkflowIR` (`schema_version: "1.0"`)
```json
{
  "schema_version": "1.0",
  "recording_id": "rec_20261122_184500_a1b2c3",
  "modality": "browser",
  "execution_mode": "headless",
  "start_url": "https://portal.example.com/renewals",
  "input_schema": [],
  "steps": [
    {
      "step_id": "step_1",
      "index": 0,
      "channel": "browser",
      "action": "navigate",
      "description": "Open Policy Renewal Search page",
      "url": "https://portal.example.com/renewals",
      "locators": {},
      "value_template": "",
      "input_key": "",
      "wait_before_ms": 0,
      "timeout_sec": 15,
      "retries": 2,
      "on_error": "retry_then_prompt",
      "narration": "Open the policy renewal portal"
    }
  ],
  "output_schema": {
    "summary_field": "result_summary",
    "extract_keys": ["page_title", "extracted_text"]
  }
}
```

### 2.5 `RequirementsDocumentSpec` (`requirements_doc`)
Contains: `doc_id`, `version`, `title`, `summary`, `modality`, `mermaid_process_flow` (valid `flowchart TD`), `functional_requirements` (`FR-01`..), `non_functional_requirements` (`NFR-01`..), `business_rules` (`[]`), `input_schema`, `trace_matrix` (mapping `step_id` -> `screen_action` -> `audio_narration` -> `locator_summary`), `acceptance_criteria`, and `markdown`.

### 2.6 `WorkflowRunCheckpoint` (SQLite `custom_agent_records` `record_type="workflow_run"`)
Stored in existing `custom_agent_records` table (zero schema breaking migrations required!):
- `agent_id`: `<custom_agent_id>`
- `record_type`: `"workflow_run"`
- `title`: `"Run <run_id> (Paused at step 2/5)"`
- `status`: `"waiting_for_input"` | `"completed"` | `"failed"`
- `data` (JSON): `run_id`, `step_index`, `total_steps`, `pending_inputs`, `non_secret_inputs` (strictly filtered so ZERO `sensitive: true` keys are written to SQLite!), `completed_steps`, `dry_run`, `modality`, `updated_at`.

---

## 3. Pure-Stdlib RFC 6455 WebSocket + CDP Sequence (`sequenceDiagram`)

```mermaid
sequenceDiagram
    participant Py as MinimalCDPClient
    participant Sock as TCP 127.0.0.1:free_port
    participant Chr as Chrome/Edge Debug Target

    Py->>Sock: HTTP GET /json (discover page webSocketDebuggerUrl)
    Sock-->>Py: [{type:"page", webSocketDebuggerUrl:"ws://127.0.0.1:PORT/devtools/page/..."}]
    Py->>Sock: GET /devtools/page/... Upgrade: websocket + Sec-WebSocket-Key
    Sock-->>Py: HTTP 101 Switching Protocols + Sec-WebSocket-Accept
    Note over Py: Verify Accept = Base64(SHA1(key + RFC6455_GUID, usedforsecurity=False))

    Py->>Chr: WS Masked Text Frame: Page.enable
    Py->>Chr: WS Masked Text Frame: Runtime.enable
    Py->>Chr: WS Masked Text Frame: Runtime.addBinding (__afccRecordEvent)
    Py->>Chr: WS Masked Text Frame: Page.addScriptToEvaluateOnNewDocument (DOM_RECORDER_JS)

    loop Live User Activity
        Chr-->>Py: WS Text Frame: Runtime.bindingCalled (Sanitized JSON Event)
        Chr-->>Py: WS Text Frame: Page.frameNavigated (URL + Frame Title)
        opt Frame Opcode == 0x8 Close or 0x9 Ping
            Py->>Chr: WS Pong (0xA) / Clean Close
        end
    end
```

### RFC 6455 Framing Byte Layout
- Outgoing client frames MUST set `MASK = 1` (`0x80`) with a 4-byte `secrets.token_bytes(4)` masking key XORed across the UTF-8 JSON payload.
- Extended payload headers: `<126` (7-bit), `126` (16-bit big-endian `>H`), `127` (64-bit big-endian `>Q`).
- Incoming server frames from local Chrome are unmasked (`MASK = 0`) and parsed safely via bounded socket `recv` loops.
- `hashlib.sha1(..., usedforsecurity=False)` is strictly compliant with AFCC's 12-Layer SAST security scanner.

---

## 4. Desktop Win32 / UIA Adaptive Polling & Noise Filtering (`flowchart TD`)

```mermaid
flowchart TD
    StartPoll["DesktopActivityWatcher Daemon Thread"] --> CheckStop{"stop_event Set or Elapsed > 1800s?"}
    CheckStop -->|"Yes"| ExitLoop["Terminate Loop Cleanly"]
    CheckStop -->|"No"| Win32Call["user32.GetForegroundWindow + GetWindowTextW + GetWindowThreadProcessId"]

    Win32Call --> ResolveExe["kernel32.QueryFullProcessImageNameW (Process Basename)"]
    ResolveExe --> CheckSelf{"Window Title Contains AFCC Dashboard or 127.0.0.1:7890?"}
    CheckSelf -->|"Yes"| SkipSelf["Drop Event (Prevent Stop-Button Self-Click Pollution)"]

    CheckSelf -->|"No"| CheckSensitive{"Matches Password Manager, UAC, Login or OTP Window?"}
    CheckSensitive -->|"Yes"| EmitRedacted["Emit Redacted prompt_user / Protected Focus Marker"]
    CheckSensitive -->|"No"| CheckDelta{"Window Changed or Left Mouse Button Clicked (GetAsyncKeyState 0x01)?"}

    CheckDelta -->|"Window Changed"| EmitAppSwitch["Emit app_switch Event (Process, Clean Title)"]
    CheckDelta -->|"Mouse Click Edge"| RelCoords["Compute Normalized Relative Coordinates (rx, ry) + Window Size"]
    RelCoords --> OptionalUIA["Optional Scoped UIA Focus Probe (CREATE_NO_WINDOW)"]
    OptionalUIA --> EmitClick["Emit desktop_click Event (Tiers: Process+UIA+RelPos)"]
    CheckDelta -->|"Idle"| Backoff["Increase Poll Interval 250ms -> 750ms"]

    EmitRedacted --> Buffer["Append to 500-Event Bounded Buffer"]
    EmitAppSwitch --> Buffer
    EmitClick --> Buffer
    SkipSelf --> Sleep["Sleep Adaptive Interval"]
    Backoff --> Sleep
    Buffer --> Sleep
    Sleep --> CheckStop
```

---

## 5. Multimodal Temporal Fusion & Requirements Compiler (`flowchart LR`)

```mermaid
flowchart LR
    RawEvts["Raw Screen Events"] --> Filter["1. Coalesce Noise (Merge Consecutive Fill, Drop <350ms Dup Clicks)"]
    Filter --> Steps["Normalized Action Steps (step_1..step_N)"]

    AudioSegs["Speech Narration Segments (offset_sec, transcript)"] --> Scrub["Scrub Spoken Secrets (OTP/Card/PIN/PAN)"]
    Scrub --> Align{"2. Distance |seg.offset - step.offset| <= 3.5s or Lexical Match"}

    Steps --> Align
    Align --> BoundSteps["Steps Annotated With Spoken Intent (narration)"]

    BoundSteps --> CueParse["3. Intent & Rule Extractor"]
    CueParse -->|"ask me / prompt / every time / dynamic"| UpgradeInput["Promote Parameter -> ask_on_each_run: true"]
    CueParse -->|"wait N seconds / pause"| InjectWait["Inject wait_before_ms on Target Step"]
    CueParse -->|"every morning / hourly / daily / weekly"| SchedHint["Extract Schedule Cadence Metadata"]
    CueParse -->|"extract / save / record / notify"| OutSchema["Populate output_schema + Business Rules"]

    UpgradeInput --> ReqGen["4. Compile RequirementsDocumentSpec + Mermaid Flowchart"]
    InjectWait --> ReqGen
    SchedHint --> ReqGen
    OutSchema --> ReqGen

    ReqGen --> TestGen["5. Generate Tailored Pytest Suite (test_<id>_workflow.py)"]
```

---

## 6. Visible Sandbox Dry-Run & Iterative Self-Healing Loop (`flowchart TD`)

```mermaid
flowchart TD
    Launch["run_visible_sandbox_dry_run (session_id)"] --> CheckIn{"All Required Inputs Present?"}
    CheckIn -->|"Missing"| ReturnPrompt["Return status=waiting_for_input + Interactive Input Form in Theater"]
    CheckIn -->|"Present"| ExecMode{"Visible Chrome Available and Simulate Only = False?"}

    ExecMode -->|"Yes"| VisChrome["Launch NON-Headless Chrome Temp Profile + SANDBOX_OVERLAY_JS"]
    ExecMode -->|"No"| SimEval["Deterministic Step-by-Step Simulator & Safety Auditor"]

    VisChrome --> StepLoop["Execute Step i With 6-Tier Self-Healing Locator Ladder"]
    SimEval --> StepLoop

    StepLoop --> StepRes{"Step Result"}
    StepRes -->|"Passed / Auto-Healed Mid-Run"| NextStep["Render Live Green/Amber Highlight + Next Step"]
    StepRes -->|"Failed"| LogFail["Record SandboxStepFailure (step_id, error_type, reason)"]

    NextStep --> DoneSteps{"More Steps?"}
    LogFail --> DoneSteps
    DoneSteps -->|"Yes"| StepLoop
    DoneSteps -->|"No"| CloseChr["Destroy Temp Profile + taskkill /F /T Process Tree"]

    CloseChr --> CheckFail{"Failures > 0 or User Requests Changes?"}
    CheckFail -->|"Yes"| Heal["heal_and_iterate_workflow (Tier-1 Auto + Tier-2 Audio Feedback)"]
    Heal --> Mutate["Update workflow_ir + Requirements Doc + Flowchart + Unit Tests (v N -> N+1)"]
    Mutate --> Launch

    CheckFail -->|"0 Failures"| ReadyPub["lifecycle_status = sandbox_passed (Ready for Publish Approval)"]
```

---

## 7. Multi-Tier Self-Healing Selector Resolution Algorithm

### Browser 6-Tier Resolution (`execute_recorded_workflow` / `run_visible_sandbox_dry_run`)
Executed inside target page via CDP `Runtime.evaluate(expression, returnByValue=True)`:
1. **Tier 1 (`data_testid`)**: `document.querySelector('[data-testid="..."]')`
2. **Tier 2 (`id`)**: `document.getElementById('...')` (ignoring volatile UUIDs containing `>= 8` hex digits)
3. **Tier 3 (`aria_label` / `placeholder` / `name`)**: Attribute match on interactive tags (`input, button, a, select, textarea`)
4. **Tier 4 (`role` + visible `text` / `label_text`)**: Case-insensitive normalized text lookup across interactive elements & `<label for=...>` associations
5. **Tier 5 (`css_path`)**: Recorded structural CSS path
6. **Tier 6 (`xpath`)**: `document.evaluate(..., XPathResult.FIRST_ORDERED_NODE_TYPE)`

### Desktop 4-Tier Resolution
1. **Tier 1 (`headless_adapter`)**: If action compiled to safe HTTP check or local CLI/file probe, execute headlessly with `shell=False` and zero GUI dependency.
2. **Tier 2 (`uia_automation_id`)**: Focused PowerShell `.NET` `System.Windows.Automation` lookup by `AutomationId` + `ProcessName`.
3. **Tier 3 (`uia_control_name`)**: Window title + control `Name` match.
4. **Tier 4 (`relative_coords`)**: Fallback normalized `(rx, ry)` fraction inside foreground client rectangle.

---

## 8. Encrypted Storage & SQLite Checkpoint Entity-Relationship Schema (`erDiagram`)

```mermaid
erDiagram
    RECORDING_SESSION_VAULT {
        string session_id PK
        string mode
        string lifecycle_status
        int iteration_version
        string start_url
        string created_at
        json redacted_events
        json audio_segments
        json draft_bundle
    }

    ENCRYPTED_AUDIO_BLOB {
        string session_id FK
        string mime_type
        int byte_length
        binary aes256gcm_ciphertext
    }

    CUSTOM_AGENT_PACKAGE {
        string agent_id PK
        string recording_id FK
        string archetype
        json workflow_ir
        json requirements_summary
        file requirements_md
        file test_agent_py
    }

    SQLITE_CUSTOM_AGENT_RECORDS {
        int id PK
        string agent_id FK
        string record_type
        string title
        string status
        json non_secret_data
        string created_at
    }

    RECORDING_SESSION_VAULT ||--o| ENCRYPTED_AUDIO_BLOB : "stores voice narration"
    RECORDING_SESSION_VAULT ||--o| CUSTOM_AGENT_PACKAGE : "publishes after approval"
    CUSTOM_AGENT_PACKAGE ||--o{ SQLITE_CUSTOM_AGENT_RECORDS : "persists workflow_run checkpoints"
```

---

## 9. Live Headless Checkpoint & Human-in-the-Loop Resume Sequence (`sequenceDiagram`)

```mermaid
sequenceDiagram
    participant UI as CustomAgentRuntime
    participant API as Workflows REST API
    participant Exec as execute_recorded_workflow
    participant DB as SQLite custom_agent_records
    participant Headless as Headless Chrome (--headless=new)

    UI->>API: POST /api/studio/workflows/run (agent_id, inputs={})
    API->>Exec: Evaluate input_schema + prompt_user steps
    Exec-->>Exec: Detect missing required/secret/ask_on_each_run param
    Exec->>DB: INSERT workflow_run (status=waiting_for_input, step_index=0, NO secrets)
    Exec-->>API: {status: waiting_for_input, run_id, pending_inputs}
    API-->>UI: Render inline Ask-for-Inputs form + focus first field

    UI->>API: POST /api/studio/workflows/resume (agent_id, run_id, inputs)
    API->>Exec: resume_workflow_run (merge non-secret DB state + RAM secrets)
    Exec->>Headless: Launch temp profile Chrome --headless=new
    Headless-->>Exec: Run 6-Tier Locators -> Extract outputs -> Return telemetry
    Exec->>Headless: Destroy temp profile + taskkill /F /T
    Exec->>DB: Update workflow_run (status=completed, output_summary, 0 secrets)
    Exec-->>API: {status: success, completed_steps, outputs}
    API-->>UI: Refresh KPI/Timeline + Clear Secret DOM Inputs
```

---

## 10. REST API Contract Table (15 Endpoints)

| Method & Endpoint | Request Payload | Response Summary | Module Handler |
| :--- | :--- | :--- | :--- |
| `POST /api/studio/recorder/recommend_modality` | `{requirement, start_url, target_apps, needs_strict_headless, needs_existing_login}` | `{recommended_mode, recommended_browser_strategy, headless_feasibility_score, rationale, warnings, auto_config, tradeoff_comparison}` | `recorder_api.py` |
| `POST /api/studio/recorder/start` | `{mode, start_url, launch_browser, record_audio, label}` | `{session_id, capture_token, bookmarklet_js, browser_launched}` | `recorder_api.py` |
| `POST /api/studio/recorder/stop` | `{session_id, audio_base64, audio_mime, audio_segments}` | `{session, events_count, audio_segments_count, audio_saved}` | `recorder_api.py` |
| `GET /api/studio/recorder/status` | `?limit=25` | `{active, session_id, elapsed_sec, events_count, recent_events, audio_segments}` | `recorder_api.py` |
| `POST /api/studio/recorder/event` | `{session_id, capture_token, action, locators, value, ...}` | `{status, event_id, redacted, events_count}` | `recorder_api.py` |
| `POST /api/studio/recorder/audio_segment` | `{session_id, capture_token, offset_sec, transcript, ...}` | `{status, segment_id, scrubbed_transcript}` | `recorder_api.py` |
| `POST /api/studio/recorder/mark_input` | `{session_id, name, label, input_type, prompt, sensitive, required}` | `{status, field, event_id}` | `recorder_api.py` |
| `GET /api/studio/recorder/sessions` | `?limit=25` | `{sessions: [{session_id, mode, lifecycle_status, ...}]}` | `recorder_api.py` |
| `POST /api/studio/recorder/convert` | `{session_id, label, use_llm, auto_run_tests}` | `{spec, workflow_ir, requirements_doc, unit_tests_code, unit_test_report}` | `recorder_api.py` |
| `POST /api/studio/recorder/run_tests` | `{session_id}` | `{status, passed, failed, errors, total, duration_ms, output}` | `recorder_api.py` |
| `POST /api/studio/recorder/sandbox_run` | `{session_id, inputs, visible_browser, simulate_only, inject_failure_step}` | `{status, steps, failures, healed_count, pending_inputs, lifecycle_status}` | `recorder_api.py` |
| `POST /api/studio/recorder/heal` | `{session_id, failures, user_audio_feedback, user_text_feedback, rerun_tests}` | `{status, iteration_version, healing_actions, requirements_doc, workflow_ir, unit_test_report}` | `recorder_api.py` |
| `POST /api/studio/recorder/publish` | `{session_id, user_approved, overrides}` | `{status, agent_id, manifest, requirements_path, tests_path}` | `recorder_api.py` |
| `POST /api/studio/workflows/run` | `{agent_id, inputs, dry_run}` | `{status: "completed" \| "waiting_for_input", run_id, pending_inputs, state}` | `recorder_api.py` |
| `POST /api/studio/workflows/resume` | `{agent_id, run_id, inputs, dry_run}` | `{status, run_id, completed_steps, outputs, state}` | `recorder_api.py` |

---

## 11. Failure, Timeout & Retry Matrix

| Failure Mode | Detection Trigger | Automatic Recovery / Fallback | Security / Laptop Guard |
| :--- | :--- | :--- | :--- |
| **Missing Chromium Binary** | Neither `chrome.exe` nor `msedge.exe` found | Safe HTTP GET probe fallback (for read/extract flows) + clear diagnostics | Blocks `file://` and internal cloud metadata URLs (`169.254.169.254`) |
| **External Token Spoof** | Invalid `capture_token` on `/recorder/event` or `/audio_segment` | Reject immediately with `HTTP 403 Forbidden` | Constant-time `hmac.compare_digest` check |
| **Selector Changed on Portal** | Tier 1 (`data_testid`) & Tier 2 (`id`) return `null` | Walk Tiers 3..6 (`aria_label` -> `text` -> `css` -> `xpath`) and record `healed` tier | Never persists sensitive field DOM values |
| **Step Timeout (`15s`)** | Navigation or DOM render stalls | Retry up to `2` times with bounded jitter, inject `wait_before_ms` in Self-Healer | Strict process-tree kill in `finally:` prevents Chrome RAM leak |
| **Dynamic / Secret Input Needed** | Parameter missing, `ask_on_each_run=true`, or `sensitive=true` | Pause run cleanly (`waiting_for_input`), save SQLite checkpoint, notify user | Secret values are NEVER persisted to disk/SQLite |
| **Unapproved Publish Attempt** | `POST /recorder/publish` without `user_approved: true` | Reject cleanly with `HTTP 400` requiring explicit user sign-off | Enforces human-in-the-loop approval before scheduling |

---

## 12. Smart Modality Advisor & Headless-First Desktop Adapter Compiler (`[REC-13]`)

- `recommend_recording_modality(requirement_text, start_url, target_apps, needs_strict_headless, needs_existing_login)`:
  - Classifies `$0.00` regex signals across Web/Portal (`_WEB_SIGNAL_RE` + validated `start_url`), Desktop Apps/Files (`_DESKTOP_SIGNAL_RE`), and Existing SSO/MFA Sessions (`_EXISTING_LOGIN_SIGNAL_RE`).
  - Outputs `recommended_mode` (`"browser"` | `"desktop"` | `"hybrid"`), `recommended_browser_strategy` (`"isolated_cdp"` | `"active_tab_bookmarklet"` | `"none"`), `headless_feasibility_score` (`0..100`), `warnings`, `auto_config`, and a scored `tradeoff_comparison` across Browser, Desktop, and Hybrid.
- `compile_desktop_step_headless_capability(step)`:
  - Annotates every captured step in `synthesize_agent_from_recording()` with `headless_capability` (`"true_headless"` | `"headless_adapter"` | `"requires_unlocked_desktop"`) and `headless_adapter` (`cdp_headless`, `hitl_checkpoint`, `file_system_adapter`, `tabular_file_adapter`, `powershell_readonly_adapter`, `browser_cdp_upgrade_recommended`, `http_native`, or `desktop_uia_gui`).
  - Populates `workflow_ir["headless_readiness_pct"]`, `workflow_ir["requires_unlocked_desktop"]`, and renders the readiness summary directly inside `requirements_doc["markdown"]`.
