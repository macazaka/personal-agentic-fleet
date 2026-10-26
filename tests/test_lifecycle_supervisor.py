"""
Unit tests for Process Lifecycle & Supervision: FleetSupervisor, Lifecycle Signals, and Service Installer.
"""

import time
import pytest
from unittest.mock import patch

from fleet.core.supervisor import FleetSupervisor, SupervisedWorker
from fleet.core.lifecycle import (
    register_shutdown_callback,
    execute_clean_shutdown,
    write_pid_file,
    remove_pid_file,
    PID_FILE
)
from fleet.tools.install_service import install_service, uninstall_service


def test_supervisor_registration_and_status():
    sup = FleetSupervisor()
    called = []

    def dummy_task():
        called.append(time.time())

    worker = sup.register_worker(
        name="test_worker",
        target=dummy_task,
        restart_strategy="temporary",
        auto_start=False
    )

    status = sup.get_status()
    assert "test_worker" in status["workers"]
    assert status["total_workers"] == 1

    worker.start()
    time.sleep(0.1)
    worker.stop()
    assert len(called) >= 1


def test_supervisor_worker_revival():
    sup = FleetSupervisor()
    attempts = []

    def crashing_task():
        attempts.append(time.time())
        if len(attempts) == 1:
            raise RuntimeError("Transient crash test")

    worker = sup.register_worker(
        name="crashing_worker",
        target=crashing_task,
        restart_strategy="permanent",
        base_backoff_sec=0.05,
        max_backoff_sec=0.1,
        auto_start=False
    )

    worker.start()
    time.sleep(0.3)
    worker.stop()

    assert len(attempts) >= 2
    assert worker.total_restarts >= 1
    assert "Transient crash test" in str(worker.last_error)


def test_lifecycle_pid_and_callbacks(tmp_path):
    callbacks_run = []

    def mock_cleanup():
        callbacks_run.append("cleanup_done")

    register_shutdown_callback("mock_cleanup", mock_cleanup, priority=10)

    # Test PID file write/remove
    write_pid_file()
    assert PID_FILE.is_file()

    # Execute shutdown
    execute_clean_shutdown()
    assert "cleanup_done" in callbacks_run
    assert not PID_FILE.is_file()


def test_service_installer_dispatch():
    with patch("sys.platform", "unknown_os"):
        with patch("fleet.tools.install_service.install_linux_systemd", return_value={"status": "mock_linux"}):
            res = install_service()
            assert res["status"] == "mock_linux"
