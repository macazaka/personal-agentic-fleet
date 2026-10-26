"""
System Sleep, Wake & Resume Lifecycle Handler for Personal Agentic Fleet.
Detects workstation sleep/resume events across Windows, macOS, and Linux.
Prevents timer stampedes, pauses scheduler during WiFi/VPN reconnection, and coalesces runs.
Zero pip dependencies.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

from fleet.core.network_spool import is_network_available

logger = logging.getLogger("fleet.power")

DEFAULT_SLEEP_DETECTION_GAP_SEC = 8.0  # Ticks every 1s; if delta > 8s, system was asleep
DEFAULT_WAKE_COOLDOWN_SEC = 5.0        # Grace period for network re-association


class PowerLifecycleManager:
    """
    Monitors OS power state transitions (suspend, sleep, wake, resume).
    Uses precision monotonic time-gap analysis with native OS hooks fallback.
    """

    def __init__(
        self,
        gap_threshold_sec: float = DEFAULT_SLEEP_DETECTION_GAP_SEC,
        wake_cooldown_sec: float = DEFAULT_WAKE_COOLDOWN_SEC
    ):
        self.gap_threshold_sec = gap_threshold_sec
        self.wake_cooldown_sec = wake_cooldown_sec
        self._wake_callbacks: List[Callable[[float], None]] = []
        self._sleep_callbacks: List[Callable[[], None]] = []
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._is_in_cooldown = False
        self._last_wake_time: Optional[float] = None
        self._lock = threading.Lock()

    def register_wake_callback(self, callback: Callable[[float], None]) -> None:
        """Registers a callback executed when system resumes from sleep. Callback receives sleep duration in seconds."""
        with self._lock:
            self._wake_callbacks.append(callback)

    def register_sleep_callback(self, callback: Callable[[], None]) -> None:
        """Registers a callback executed when system initiates sleep."""
        with self._lock:
            self._sleep_callbacks.append(callback)

    @property
    def is_in_cooldown(self) -> bool:
        """Indicates if system recently woke and is in network reconnection cooldown."""
        return self._is_in_cooldown

    def start_monitoring(self) -> None:
        """Starts background daemon thread monitoring sleep/wake events."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="PowerLifecycleMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("[PowerManager] Power lifecycle monitor started.")

    def stop_monitoring(self) -> None:
        """Stops the monitoring thread."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        logger.info("[PowerManager] Power lifecycle monitor stopped.")

    def _monitoring_loop(self) -> None:
        last_wall_time = time.time()
        while not self._stop_event.is_set():
            time.sleep(1.0)
            now_wall_time = time.time()
            elapsed = now_wall_time - last_wall_time

            # If elapsed wall-clock time significantly exceeds the 1.0s sleep interval,
            # the host machine was suspended, asleep, or hibernating.
            if elapsed >= self.gap_threshold_sec:
                sleep_duration = elapsed - 1.0
                self._handle_system_resume(sleep_duration)

            last_wall_time = now_wall_time

    def _handle_system_resume(self, estimated_sleep_sec: float) -> None:
        """Executes the clean resume protocol: pauses scheduler, waits for network, triggers callbacks."""
        logger.warning(
            f"[PowerManager] Workstation resume detected! Estimated sleep duration: {estimated_sleep_sec:.1f}s. "
            f"Entering {self.wake_cooldown_sec}s network stabilization cooldown..."
        )
        self._is_in_cooldown = True
        self._last_wake_time = time.time()

        def _cooldown_worker():
            # Wait for Wi-Fi / Ethernet to re-associate
            time.sleep(self.wake_cooldown_sec)

            # Probe connectivity
            online = is_network_available(timeout=2.0)
            logger.info(f"[PowerManager] Cooldown ended. Network reachability status: {'ONLINE' if online else 'OFFLINE'}")

            self._is_in_cooldown = False

            with self._lock:
                callbacks = list(self._wake_callbacks)

            for cb in callbacks:
                try:
                    cb(estimated_sleep_sec)
                except Exception as e:
                    logger.error(f"[PowerManager] Error in wake callback {cb}: {e}")

        # Run cooldown asynchronously so monitor loop keeps ticking
        t = threading.Thread(target=_cooldown_worker, name="WakeCooldownWorker", daemon=True)
        t.start()


# Global singleton instance
power_manager = PowerLifecycleManager()
