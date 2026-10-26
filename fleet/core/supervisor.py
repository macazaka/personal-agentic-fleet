"""
Thread & Task Supervision Watchdog for Personal Agentic Fleet.
Implements Erlang/OTP-style one-for-one supervision with exponential backoff & thread auto-recovery.
"""

import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger("fleet.supervisor")


class SupervisedWorker:
    """Represents a supervised thread worker with restart tracking."""

    def __init__(
        self,
        name: str,
        target: Callable[[], None],
        restart_strategy: str = "permanent",  # 'permanent', 'transient', or 'temporary'
        max_restarts: int = 5,
        window_seconds: float = 60.0,
        base_backoff_sec: float = 1.0,
        max_backoff_sec: float = 30.0,
    ):
        self.name = str(name)
        self.target = target
        self.restart_strategy = restart_strategy
        self.max_restarts = max_restarts
        self.window_seconds = window_seconds
        self.base_backoff_sec = base_backoff_sec
        self.max_backoff_sec = max_backoff_sec

        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.restart_timestamps: List[float] = []
        self.total_restarts = 0
        self.last_error: Optional[str] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, name=f"Supervisor-{self.name}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        self._stop_event.set()

    def _run_loop(self) -> None:
        while self.running and not self._stop_event.is_set():
            try:
                self.target()
                # Target completed normally
                if self.restart_strategy != "permanent":
                    break
            except Exception as exc:
                self.last_error = str(exc)
                logger.error(f"[Supervisor] Worker '{self.name}' crashed with: {exc}", exc_info=True)

                if self.restart_strategy == "temporary":
                    break

                now = time.time()
                # Prune restart timestamps outside the tracking window
                self.restart_timestamps = [t for t in self.restart_timestamps if now - t <= self.window_seconds]
                self.restart_timestamps.append(now)
                self.total_restarts += 1

                if len(self.restart_timestamps) > self.max_restarts:
                    logger.critical(
                        f"[Supervisor] Worker '{self.name}' exceeded max restarts ({self.max_restarts}/{self.window_seconds}s). Halting worker."
                    )
                    self.running = False
                    break

                # Truncated exponential backoff with full jitter
                attempt = len(self.restart_timestamps)
                backoff = min(self.max_backoff_sec, self.base_backoff_sec * (2 ** (attempt - 1)))
                jitter = random.uniform(0.5, 1.5) * (backoff / 2.0)
                delay = backoff + jitter

                logger.info(f"[Supervisor] Reviving worker '{self.name}' in {delay:.2f}s (Restart #{self.total_restarts})...")
                self._stop_event.wait(timeout=delay)


class FleetSupervisor:
    """
    Central process and thread supervisor for Personal Agentic Fleet.
    Oversees long-running background threads (daemon, scheduler, optimizer, etc.)
    and automatically recovers failed workers without stopping the microkernel.
    """

    def __init__(self):
        self._workers: Dict[str, SupervisedWorker] = {}
        self._lock = threading.Lock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

    def register_worker(
        self,
        name: str,
        target: Callable[[], None],
        restart_strategy: str = "permanent",
        max_restarts: int = 5,
        window_seconds: float = 60.0,
        base_backoff_sec: float = 1.0,
        max_backoff_sec: float = 30.0,
        auto_start: bool = True
    ) -> SupervisedWorker:
        """Registers a worker callable under supervisor custody."""
        with self._lock:
            if name in self._workers:
                self._workers[name].stop()

            worker = SupervisedWorker(
                name=name,
                target=target,
                restart_strategy=restart_strategy,
                max_restarts=max_restarts,
                window_seconds=window_seconds,
                base_backoff_sec=base_backoff_sec,
                max_backoff_sec=max_backoff_sec
            )
            self._workers[name] = worker

            if auto_start and self._running:
                worker.start()

            return worker

    def start(self) -> None:
        """Starts all registered workers and the watchdog inspection loop."""
        with self._lock:
            self._running = True
            self._stop_event.clear()
            for worker in self._workers.values():
                if not worker.running:
                    worker.start()

            if self._watchdog_thread is None or not self._watchdog_thread.is_alive():
                self._watchdog_thread = threading.Thread(
                    target=self._watchdog_loop,
                    name="FleetSupervisorWatchdog",
                    daemon=True
                )
                self._watchdog_thread.start()

    def stop(self) -> None:
        """Stops all supervised workers and the watchdog loop."""
        with self._lock:
            self._running = False
            self._stop_event.set()
            for worker in self._workers.values():
                worker.stop()

    def get_status(self) -> Dict[str, Any]:
        """Returns health diagnostics for all supervised workers."""
        with self._lock:
            statuses = {}
            for name, w in self._workers.items():
                is_alive = bool(w.thread and w.thread.is_alive())
                statuses[name] = {
                    "running": w.running,
                    "is_alive": is_alive,
                    "total_restarts": w.total_restarts,
                    "recent_restarts": len(w.restart_timestamps),
                    "last_error": w.last_error,
                }
            return {
                "supervisor_active": self._running,
                "total_workers": len(self._workers),
                "workers": statuses
            }

    def _watchdog_loop(self) -> None:
        """Periodically inspects worker health and revives stalled threads."""
        while self._running and not self._stop_event.is_set():
            with self._lock:
                for name, worker in self._workers.items():
                    if worker.running and (worker.thread is None or not worker.thread.is_alive()):
                        logger.warning(f"[Watchdog] Worker '{name}' found dead unexpectedly. Initiating revival.")
                        worker.start()
            self._stop_event.wait(timeout=10.0)


# Global singleton supervisor
_SUPERVISOR = FleetSupervisor()


def get_fleet_supervisor() -> FleetSupervisor:
    """Returns the singleton FleetSupervisor instance."""
    return _SUPERVISOR
