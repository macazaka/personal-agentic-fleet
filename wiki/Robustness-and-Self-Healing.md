# Robustness & Autonomous Self-Healing

The Personal Agentic Fleet is engineered with a **7-Pillar Native Robustness Architecture** ensuring zero-downtime operations, fault tolerance, and automated healing without human intervention.

---

## The 7 Robustness Pillars

| Pillar | Mechanism | Objective |
| :--- | :--- | :--- |
| **1. Zero-Token Cost Invariant** | Deterministic Tier 0 Local Engine | Guarantees $0.00 operating cost for all background monitoring and classifications. |
| **2. Concurrency & High Availability** | SQLite WAL & Thread-Local Pool | Eliminates `database locked` errors with 15,000ms busy timeouts and WAL mode. |
| **3. Circuit Breakers & Backoff** | Exponential backoff with full jitter | Prevents cascade failures during external network or API outages. |
| **4. Process & Memory Resilience** | Autonomic PID monitoring & garbage sweeps | Reclaims memory and purges zombie worker processes automatically. |
| **5. Crash Forensics Isolation** | Isolated JSON crash dumps | Logs stack traces in dedicated crash dumps without exposing user PII. |
| **6. Cross-Platform Parity** | Native Windows, macOS, and Linux bridges | Seamless operations across Windows 10/11, macOS Sonoma/Sequoia, and Linux. |
| **7. Proactive Auto-Healing** | Autonomous Log Scanner & Healer | Mines error logs periodically and applies remediation recipes autonomously. |

---

## Autonomous Self-Healing Recipes

The proactive log scanner analyzes logs every 15 minutes and executes targeted recipes:

```
+--------------------+-----------------------------+------------------------------------+
| Anomaly Pattern    | Root Cause                  | Autonomous Self-Healing Action     |
+--------------------+-----------------------------+------------------------------------+
| SQLITE_BUSY        | High concurrent writes      | Reset WAL checkpoint (PRAGMA WAL)  |
| LOG_GROWTH_EXCESS  | Log file exceeds threshold  | Rotate and gzip archive log file   |
| TASK_CONSECUTIVE   | Task failing continuously   | Quarantine task & apply backoff    |
| CRASH_DUMP_ACCUM   | Crash reports exceed limit  | Prune reports older than 7 days    |
| ZOMBIE_SUBPROCESS  | Orphaned worker processes   | Reclaim handles and terminate PIDs |
| CACHE_BLOAT        | Temp artifacts accumulate   | Sweep __pycache__ and temp cache   |
+--------------------+-----------------------------+------------------------------------+
```

All healing actions are recorded in the **Auto-Improvements Ledger** (`fleet/data/auto_improvements.json`), visible in the dashboard Settings panel.
