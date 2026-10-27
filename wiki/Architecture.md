# System Architecture

The **Personal Agentic Fleet** is structured as a resilient, multi-layered operations system operating with 100% local determinism ($0.00 compute). It integrates a lightweight FastHTTP microkernel, Server-Sent Events (SSE) streaming, SQLite Write-Ahead Logging (WAL) concurrency, and an organic **4-Layer Cognitive Fleet Mind**.

---

## High-Level Topology

```
+---------------------------------------------------------------------------------+
|                     User Workstation Browser (HTML5 / Vanilla JS)              |
|   - 100+ Agent Fleet Navigator     - Spotlight Command Palette (Ctrl+K)         |
|   - 4-Step Agent Creation Wizard   - Cognitive Mind Telemetry & Dream Dashboard |
|   - Dynamic Agent Settings Drawer  - Continuous GitHub Update Notifications     |
+---------------------------------------------------------------------------------+
                                       | HTTP / SSE (Port 7890)
+---------------------------------------------------------------------------------+
|                           Microkernel Server Layer                              |
|   - FastHTTP BaseHTTPRequestHandler  - SSE Streaming & Synaptic Event Relays    |
|   - Content-Security-Policy & CSRF   - Path-Traversal Guard (is_relative_to)    |
|   - Session Auth & DNS Rebinding     - Zero-Token Intent Intercept Engine       |
+---------------------------------------------------------------------------------+
                                       |
+---------------------------------------------------------------------------------+
|                         The 4-Layer Cognitive Fleet Mind                        |
|  [Layer 1: Brain]           [Layer 2: Consciousness]   [Layer 3: Subconscious]   |
|   - Synaptic Event Bus       - Real-time Attention      - Periodic Log Mining   |
|   - Autonomic Reflexes       - Conscious Self-Critique  - Dream Consolidation   |
|   - Epistemic Memory Store   - Quality Rubric (>=85)    - Auto-Healing Engine   |
|                                                                                 |
|  [Layer 4: Fleet Soul]                                                          |
|   - Inviolable Ethical Tenets: Sovereign Privacy, Zero-Token Invariant,        |
|     Metabolic System Care, User-Choice-First Autonomy Directive                 |
+---------------------------------------------------------------------------------+
                                       |
+---------------------------------------------------------------------------------+
|                          Isolated Agent Package Matrix                          |
|  - antigravity   - overview    - backlog       - pr_review                      |
|  - gmail         - health      - optimizer     - custom user agents             |
|  * Strict manifest.json permission boundaries & capability sandboxing           |
+---------------------------------------------------------------------------------+
                                       |
+---------------------------------------------------------------------------------+
|                          Storage & Persistence Layer                            |
|  - SQLite (WAL Mode, PRAGMA busy_timeout=15000, NORMAL Sync, Foreign Keys)      |
|  - At-Rest Cryptographic Vault (NIST SP 800-132 PBKDF2-HMAC-SHA256, DPAPI)      |
|  - Dedicated Scoped User Vault: fleet/data/user/ (master.dpapi, pii_blocklist)  |
+---------------------------------------------------------------------------------+
```

---

## 4-Layer Cognitive Fleet Mind & Harmony Index

The system formalizes the unified cognitive state using the **Cognitive Harmony Index**:

$$\text{Harmony Score} = (\text{Brain} \times 0.35) + (\text{Consciousness} \times 0.35) + (\text{Soul} \times 0.30)$$

1. **Brain Score ($B$)**: Computed from event delivery latency, SQLite connection health, and autonomic reflex dispatch.
2. **Consciousness Score ($C$)**: Computed from active attention focus stability and multi-axial self-critique scores (target $\ge 85$).
3. **Soul Score ($S$)**: Computed from ethical tenet alignment, zero token waste verification, and privacy invariant checks.

---

## Concurrency & Storage Architecture

- **SQLite WAL Mode**: Allows simultaneous non-blocking concurrent readers while a single background writer commits transactions.
- **Connection Pool**: Dedicated thread-local connections configured with `PRAGMA busy_timeout = 15000` to prevent database locks under high concurrent workloads.
- **Zero-Token Cache**: In-memory prompt-response cache and BM25 local retrieval avoid redundant computation.
