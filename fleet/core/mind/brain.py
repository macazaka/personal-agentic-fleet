"""
The Brain — Physical & Neurological Substrate of Personal Agentic Fleet.
Coordinates the neuro-synaptic bus, dual-memory architecture (working & epistemic),
motor schedulers, and autonomic reflex arcs for biological-grade self-healing.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import os
from pathlib import Path
import platform
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from fleet.config import DATA_DIR, DB_PATH
from fleet.core.auto_healer import run_proactive_log_scan_and_heal
from fleet.core.logger import get_recent_errors, get_recent_logs

logger = logging_instance = None


def _get_logger():
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger("fleet.mind.brain")
    return logger


@dataclass
class WorkingMemorySnapshot:
    process_pid: int
    working_set_mb: float
    active_threads_count: int
    open_synapses_count: int
    ring_buffer_usage_pct: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EpistemicMemoryStats:
    total_memories: int
    total_notes: int
    total_tasks: int
    total_activities: int
    wal_journal_mb: float


class PhysicalBrain:
    """
    Neurological substrate coordinating Synapses (Event Bus), Memory (Working & Epistemic),
    Motor Execution (Schedulers), and Autonomic Reflexes (Auto-Healer).
    """

    def __init__(self, db: Any = None):
        self.db = db
        self._synapse_counter = 0
        self._synapse_lock = threading.RLock()
        self._birth_time = time.time()

    @property
    def synapses_fired(self) -> int:
        return self._synapse_counter

    def record_synapse_firing(self) -> int:
        """Records an electrical impulse / message routed through the synaptic bus."""
        with self._synapse_lock:
            self._synapse_counter += 1
            return self._synapse_counter

    def get_working_memory(self) -> WorkingMemorySnapshot:
        """Inspects physical short-term RAM working memory and neural active threads."""
        pid = os.getpid()
        active_threads = len(threading.enumerate())
        working_set_mb = 0.0

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                    ]
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                windll = getattr(ctypes, "windll", None)
                if windll is not None:
                    handle = windll.kernel32.GetCurrentProcess()
                    if windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                        working_set_mb = round(counters.WorkingSetSize / (1024 * 1024), 2)
            except Exception:
                pass

        recent_logs_count = len(get_recent_logs(limit=2000))
        ring_pct = round((recent_logs_count / 2000.0) * 100.0, 1)

        return WorkingMemorySnapshot(
            process_pid=pid,
            working_set_mb=working_set_mb,
            active_threads_count=active_threads,
            open_synapses_count=self._synapse_counter,
            ring_buffer_usage_pct=ring_pct,
        )

    def get_epistemic_memory_stats(self) -> EpistemicMemoryStats:
        """Measures long-term persistent declarative memory stored in the SQLite substrate."""
        total_mem = 0
        total_notes = 0
        total_tasks = 0
        total_acts = 0
        wal_mb = 0.0

        if self.db and hasattr(self.db, "_get_connection"):
            try:
                with self.db._get_connection() as conn:
                    c = conn.cursor()
                    total_mem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                    total_notes = c.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
                    total_tasks = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                    total_acts = c.execute("SELECT COUNT(*) FROM activity_logs").fetchone()[0]
            except Exception:
                pass

        wal_file = Path(str(DB_PATH) + "-wal")
        if wal_file.exists():
            wal_mb = round(wal_file.stat().st_size / (1024 * 1024), 2)

        return EpistemicMemoryStats(
            total_memories=total_mem,
            total_notes=total_notes,
            total_tasks=total_tasks,
            total_activities=total_acts,
            wal_journal_mb=wal_mb,
        )

    def trigger_autonomic_reflex(self) -> Dict[str, Any]:
        """Triggers the brainstem autonomic self-healing reflex arc to resolve physical contention."""
        _get_logger().info("Autonomic reflex arc firing: executing proactive self-healing")
        heal_res = run_proactive_log_scan_and_heal(db=self.db)
        health_idx = heal_res.get("system_health_index", 100.0)
        return {
            "status": "HEALTHY" if health_idx >= 75.0 else "RECOVERING",
            "health_score": health_idx,
            "anomalies_detected": heal_res.get("findings", []),
            "auto_repairs_applied": heal_res.get("improvements", []),
            "scan_id": heal_res.get("scan_id"),
        }

    def get_status(self) -> Dict[str, Any]:
        wm = self.get_working_memory()
        em = self.get_epistemic_memory_stats()
        uptime_sec = round(time.time() - self._birth_time, 1)

        # Brain Health Index based on memory pressure, WAL size, and error density
        errs = len(get_recent_errors(limit=50))
        health = 100.0 - min(40.0, (wm.working_set_mb / 20.0)) - min(30.0, (em.wal_journal_mb * 5.0)) - min(30.0, errs * 2.0)
        health = round(max(10.0, min(100.0, health)), 1)

        return {
            "layer": "Brain (Physical Substrate)",
            "health_score": health,
            "synapses_fired": self._synapse_counter,
            "status": "VIBRANT" if health >= 85 else ("STABLE" if health >= 60 else "STRAINED"),
            "uptime_sec": uptime_sec,
            "working_memory": asdict(wm),
            "epistemic_memory": asdict(em),
        }
