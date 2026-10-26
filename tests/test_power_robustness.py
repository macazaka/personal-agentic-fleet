"""
Unit tests for Pillar 6: Hardware & Power State Awareness.
Tests System Sleep / Wake / Resume Lifecycle Handler (ROB-14).
"""

import time
from unittest.mock import patch

from fleet.core.power import PowerLifecycleManager


def test_power_lifecycle_resume_handling():
    manager = PowerLifecycleManager(gap_threshold_sec=2.0, wake_cooldown_sec=0.1)
    
    wake_events = []
    
    def on_wake(sleep_sec):
        wake_events.append(sleep_sec)

    manager.register_wake_callback(on_wake)

    with patch("fleet.core.power.is_network_available", return_value=True):
        # Trigger simulated resume
        manager._handle_system_resume(estimated_sleep_sec=15.5)
        assert manager.is_in_cooldown is True

        # Wait for cooldown worker to complete
        time.sleep(0.3)
        assert manager.is_in_cooldown is False
        assert len(wake_events) == 1
        assert wake_events[0] == 15.5
