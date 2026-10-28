# 🤖 Built-in Agents Deep-Dive Reference

> **Release Version**: `v2.11.1` | **Package Root**: `fleet/agents/<agent_id>/` | **Core Engines**: `fleet/core/exercise_manager.py`, `fleet/core/antigravity_mirror.py`, `fleet/core/system_optimizer.py`, `fleet/integrations/gmail_classifier.py`

Personal Agentic Fleet ships with **7 production-grade built-in agents**, each isolated in its own self-contained package under `fleet/agents/<agent_id>/` with a declarative `manifest.json` capability contract, a `FleetAgent` subclass in `agent.py`, and a scoped HTML5/CSS/JS workspace in `ui/panel.html`.

---

## 1. Built-in Agent Matrix & Capability Contracts

| Agent ID | Display Name | Default Order | Declared `manifest.json` Permissions | Primary Storage Tables & Subsystems |
| :--- | :--- | :---: | :--- | :--- |
| `health` | **🌿 Health & Wellness Command Center** | `1` *(Default Tab)* | `db:read`, `db:write`, `ui:render`, `notifications:send` | `health_metrics`, `routines`, `ExerciseManager`, HTTP 206 Video Streamer |
| `overview` | **⚡ Daily Briefing, Tasks & Habits** | `2` | `db:read`, `db:write`, `ui:render`, `notifications:send` | `tasks`, `routines`, `notes`, `activity_logs`, `DailyBriefingEngine` |
| `optimizer` | **🚀 Silent PC & System Optimizer** | `3` | `db:read`, `db:write`, `ui:render`, `system:read`, `system:execute` | `activity_logs`, `SystemOptimizer` (Win32 `PSAPI.dll` / `Kernel32.dll`) |
| `antigravity` | **🤖 Antigravity Live Hub & Token Vault** | `4` | `db:read`, `ui:render`, `system:read` | `AntigravityMirror` (`.gemini/antigravity/brain/*`), `TokenOptimizer` |
| `backlog` | **📋 Feature Backlog & Kanban** | `5` | `db:read`, `db:write`, `ui:render` | `backlog`, `auto_improvements`, `AutoHealer` ticket bridge |
| `gmail` | **📬 Gmail 5-Folder Inbox Intelligence** | `6` | `db:read`, `db:write`, `ui:render`, `network:http`, `secrets:read` | `GmailClassifier`, `CryptoVault` (DPAPI OAuth/IMAP credentials) |
| `mind` / `pr_review` | **🧠 Cognitive Fleet Mind & PR Sentinel** | `7` | `db:read`, `db:write`, `ui:render`, `system:read` | `CognitiveFleetMind`, `memories`, `auto_improvements`, Git diff analyzer |

---

## 2. Deep-Dive Specifications by Agent

### 2.1 🌿 Health & Wellness Command Center (`health`)

**Source Files**: `fleet/agents/health/agent.py`, `fleet/agents/health/ui/panel.html`, `fleet/core/exercise_manager.py`

The **Health & Wellness Command Center** is the default landing workspace in AFCC, combining **Freedom From Diabetes (FFD) Metabolic Reversal Protocols** with a **6-Day Traditional Indian Akhada Strength Conditioning Split** and local **HTTP 206 Byte-Range Video Streaming**.

#### A. The 6-Day Traditional Indian Strength Split (`DEFAULT_STRENGTH_SPLIT`)
Managed by `ExerciseManager` in `fleet/core/exercise_manager.py`, the weekly schedule rotates deterministically based on `datetime.now().strftime("%A")`:

| Day | Primary Tool / Modality | Focus Area | Prescribed Sets, Reps & Biomechanical Protocol |
| :--- | :--- | :--- | :--- |
| **Monday** | **Mudgal (Indian Club / Karlakattai)** | 360° Shoulder Girdle, Grip & Core Torque | • **Mandatory World's Best Warm-up** (`5 mins`: Deep Squat w/ Thoracic Reach, World's Greatest Lunge Stretch, Scapular Halos)<br>• **360° Pendulum Swings (ek-haath & do-haath)**: `4 sets × 15 reps/side`<br>• **Front Shield Casts & Mills**: `3 sets × 12 reps/side`<br>• **Post-Workout**: 10-min Pranayama & Wrist Decompression |
| **Tuesday** | **Active FFD Metabolic Reversal** | Insulin Sensitivity & GLUT-4 Activation | • **Mandatory World's Best Warm-up** (`5 mins`)<br>• **Surya Namaskar (Sun Salutations)**: `12 rounds` with rhythmic breath synchronization<br>• **Nitric Oxide Dump (NOD)**: `3 sets × 10 reps` (Squats, Alternating Arm Raises, Non-Jumping Jacks, Shoulder Presses)<br>• **Post-Meal Antigravity Step Climbing**: `15 mins` (60–90 mins after meals) |
| **Wednesday** | **Samtola (Traditional Wooden Barbell / Mugdar)** | Anterior/Posterior Chain & Rotational Stability | • **Mandatory World's Best Warm-up** (`5 mins`)<br>• **Samtola Overhead Akhada Press**: `4 sets × 10–12 reps`<br>• **Samtola Bent-Over Pendulum Rows**: `4 sets × 12 reps`<br>• **Rotational Core Torque Twists**: `3 sets × 16 alternating reps`<br>• **Hindu Dand (Dive-Bomber Pushups)**: `3 sets × 10 reps` |
| **Thursday** | **Active FFD Reversal & Zone-2 Conditioning** | Vascular Nitric Oxide & Lymphatic Drainage | • **Mandatory World's Best Warm-up** (`5 mins`)<br>• **Nitric Oxide Dump (NOD)**: `3 sets × 10 reps` across all 4 movements<br>• **Brisk Zone-2 / Weighted Walking**: `35–45 mins` nasal breathing<br>• **Sapate / Hindu Baithak (Bodyweight Squats)**: `3 sets × 20 reps` |
| **Friday** | **Bhim Gadha (Heavy Traditional Mace)** | Posterior Chain, Lats, Triceps & Anti-Rotation Core | • **Mandatory World's Best Warm-up** (`5 mins`)<br>• **Bhim Gadha 10-to-2 & 2-to-10 Pendulum Swings**: `5 sets × 10 reps/side`<br>• **Single-Arm Gadha Shield Casts**: `3 sets × 8 reps/side`<br>• **Gadha Ballistic Halos + Isometric Crush Hold**: `3 sets × 60 sec` |
| **Saturday** | **Triple-Tool Akhada Flow (Mudgal + Samtola + Bhim Gadha)** | Full-Body Metabolic & Neuromuscular Integration | • **Mandatory World's Best Warm-up** (`5 mins`)<br>• **Complex Round (4 Rounds, 90s rest)**:<br>  1. `10 reps/side` Mudgal Mills<br>  2. `10 reps` Samtola Overhead Press<br>  3. `8 reps/side` Bhim Gadha 360° Swings<br>  4. `15 reps` Hindu Baithak |
| **Sunday** | **Deep Parasympathetic Recovery & Mobility** | Myofascial Release, Vagal Tone & Glycogen Reset | • **Gentle Joint Rotations (Sukshma Vyayama)**: `15 mins`<br>• **Yoga Nidra / Box Breathing (`4-4-4-4`)**: `20 mins`<br>• **Zero Heavy Loading**: Full connective-tissue and CNS restoration |

#### B. FFD Diabetes Reversal & Nutrition Protocols
- **Morning Green Smoothie Prescription**: Spinach/Palak or Methi (1 handful) + Cucumber (1/2) + Tomato (1) or Amla (4–5 pieces) + low-GI fruit (1/2 Apple/Guava/Pear) + ginger, lemon, black salt, cinnamon, black pepper + `250ml` water (blended, never strained).
- **25-25-50% Breakfast & 25% Quad Plate Lunch/Dinner**: Enforces high-fiber raw salad first (`25%`), cooked low-GI greens (`25%`), plant protein/sprouts/dal (`25%`), and ancient grains (`25%` khapli wheat / millets).
- **Hypoglycemia Rule of 15 Alert**: Built-in protocol for Blood Sugar Level `< 70 mg/dL` (15g fast carbs → 15-min retest → complex carb + protein stabilizer).

#### C. HTTP 206 Byte-Range Local Video Streaming & Live HTML5 Thumbnails
- `ExerciseManager` indexes local MP4/WebM/MKV exercise and nutrition videos stored in the user's configured Exercise & Diet folders (`fleet/data/user/exercise_catalog.json`).
- **RFC 7233 Byte-Range Streaming (`/api/exercises/video?id=<video_id>`)**:
  - Parses incoming `Range: bytes=<start>-<end>` HTTP headers.
  - Responds with `HTTP/1.1 206 Partial Content`, `Accept-Ranges: bytes`, `Content-Range: bytes {start}-{end}/{total_size}`, and streams chunked slices (`64 KB` buffer) directly from disk.
  - Enables instant video scrubbing, zero-buffering playback, and client-side `<video preload="metadata">` live frame thumbnail extraction (`#t=2.5`).
- **Strict DOM Scoping**: The entire `<div id="viewHealth">` pane resides exclusively inside `fleet/agents/health/ui/panel.html`, ensuring the Exercise, Videos & Traditional Strength Training Hub never leaks into other agent tabs.

---

### 2.2 ⚡ Overview, Tasks & Habit Routines (`overview`)

**Source Files**: `fleet/agents/overview/agent.py`, `fleet/core/briefing.py`, `fleet/core/database.py`

- **Priority Task Engine**: Full CRUD over the `tasks` SQLite table (`title`, `priority` in `high`/`medium`/`low`, `category`, `due_date`, `completed`, `created_at`, `completed_at`).
- **Deterministic Daily Habit Routines**: Tracks recurring daily habits (`Morning Green Smoothie`, `6-Day Strength Split Session`, `8 Glasses Hydration`, `Inbox Zero Sweep`, `Evening Shutdown Review`). Automatically resets completion flags at midnight (`last_completed_date != today_iso`) while preserving historical streak counters (`streak_count`).
- **Executive Daily Briefing (`fleet/core/briefing.py`)**: Synthesizes pending high-priority tasks, today's strength training tool (e.g., *Wednesday: Samtola*), hydration progress, and system health into a single zero-token executive briefing card and optional Windows/macOS/Linux desktop toast notification.

---

### 2.3 🚀 Silent PC & System Optimizer (`optimizer`)

**Source Files**: `fleet/agents/optimizer/agent.py`, `fleet/core/system_optimizer.py`

- **Zero-Popup In-Process Win32 Telemetry**:
  - Uses Python's `ctypes.windll.kernel32` (`GlobalMemoryStatusEx` with `MEMORYSTATUSEX` struct) and `ctypes.windll.psapi` (`GetProcessMemoryInfo` with `PROCESS_MEMORY_COUNTERS` struct) on Windows.
  - Enumerates top memory-consuming processes and system RAM utilization (`total_gb`, `used_gb`, `free_gb`, `percent`) **100% in-process** with **0 external `tasklist.exe` or `wmic.exe` console flashes**.
  - On macOS, uses `sysctl hw.memsize` & `vm_stat`; on Linux, reads `/proc/meminfo` & `/proc/[pid]/statm` directly.
- **Automated Maintenance Operations**:
  - **Temp & Dev Cache Purge**: Safely cleans stale files in `%TEMP%`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, and browser/IDE caches, returning exact bytes reclaimed.
  - **Silent DNS Resolver Flush**: Runs `ipconfig /flushdns` (`CREATE_NO_WINDOW = 0x08000000` on Windows), `dscacheutil -flushcache` on macOS, or `resolvectl flush-caches` on Linux.
  - **SQLite WAL Compaction**: Executes `PRAGMA wal_checkpoint(TRUNCATE)` and `PRAGMA optimize` on `fleet_memory.db`.

---

### 2.4 🤖 Antigravity Live Hub & Token Vault (`antigravity`)

**Source Files**: `fleet/agents/antigravity/agent.py`, `fleet/core/antigravity_mirror.py`, `fleet/core/token_optimizer.py`

- **Live Brain Directory Mirror (`AntigravityMirror`)**:
  - Automatically discovers `~/.gemini/antigravity/brain/<conversation-id>` directories.
  - Parses `transcript.jsonl` (compact step stream), `task.md`, `implementation_plan.md`, and `walkthrough.md` without modifying or locking Antigravity's files.
  - Extracts step counts, active tool calls, model reasoning checkpoints, and artifact summaries for live inspection in AFCC.
- **8-Layer Token & Dollar Savings Vault**:
  - Displays live cumulative statistics from `fleet/core/token_optimizer.py`: total queries intercepted at Tier 0 (`$0.00`), BM25 RAG hits, Fuzzy Jaccard/Trigram cache hits, AST code minification savings, and estimated USD saved across frontier LLM pricing tiers.

---

### 2.5 📋 Feature Backlog & Kanban (`backlog`)

**Source Files**: `fleet/agents/backlog/agent.py`, `fleet/core/database.py`, `fleet/core/auto_healer.py`

- **Structured Engineering Roadmap**: Manages items in the `backlog` SQLite table with priority tiers (`P0`, `P1`, `P2`, `P3`), categories (`Architecture`, `Security`, `UI/UX`, `Agent`, `Performance`), and statuses (`pending`, `in_progress`, `completed`).
- **Autonomous `AutoHealer` Ticket Creation**: When `fleet/core/auto_healer.py` detects recurring operational friction or log anomalies, it logs structured remediation records into `auto_improvements` and links actionable engineering items to the Backlog tab.

---

### 2.6 📬 Gmail 5-Folder Inbox Intelligence (`gmail`)

**Source Files**: `fleet/agents/gmail/agent.py`, `fleet/integrations/gmail_classifier.py`, `fleet/core/crypto_vault.py`

- **Zero-Token 5-Folder Deterministic Triage Engine**:
  Classifies incoming emails locally in Python (`$0.00` token spend, zero third-party cloud forwarding) into 5 action-oriented folders:
  1. `01-Focus` — Direct human correspondence, VIP senders, urgent security alerts, and calendar invitations requiring immediate reply.
  2. `02-Paper-Trail` — Invoices, tax receipts, banking statements, flight/hotel confirmations, and order tracking notices.
  3. `03-Read-Feed` — Engineering digests, Substacks, curated newsletters, and GitHub release summaries.
  4. `04-Promotions` — Marketing campaigns, coupon blasts, and retail offers (`List-Unsubscribe` header + promotional keyword scoring).
  5. `05-Archive-Sweep` — Automated no-reply notifications, expired OTP codes, and stale telemetry alerts ready for 1-click bulk archive.
- **Hardware-Bound DPAPI Credential Storage**: Gmail IMAP App Passwords and OAuth tokens are encrypted at rest via `CryptoVault` (`crypt32.dll` on Windows, Keychain on macOS, SecretService on Linux) inside `fleet/data/user/vault.enc`.

---

### 2.7 🧠 Cognitive Fleet Mind & PR Sentinel (`mind` / `pr_review`)

**Source Files**: `fleet/core/mind/gestalt.py`, `fleet/tools/fleet_mind.py`, `fleet/tools/auto_fixer.py`

- **4-Layer Gestalt Introspection**: Renders live telemetry for **Layer 1 (`PhysicalBrain`)**, **Layer 2 (`ConsciousExecutive`)**, **Layer 3 (`SubconsciousMind`)**, and **Layer 4 (`FleetSoul`)**, along with the composite **0–100 Cognitive Harmony Index**.
- **Pre-Commit & PR Sentinel**: Integrates with `fleet/tools/auto_fixer.py` and `fleet/tools/security_scanner.py` to inspect staged Git diffs against all 12 security layers, Pyright static type checks, and HTML/CSS diagnostic rules before any commit or release tag is created.
