"""
Exhaustive unit tests targeting remaining branches in lifecycle, power, supervisor, sandbox_quota, pool, crypto_vault, session_auth, backup.
"""

import os
from pathlib import Path
import signal
import socket
import sqlite3
import sys
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

import fleet.core.lifecycle as lc_mod
import fleet.core.power as pwr_mod
import fleet.core.supervisor as sup_mod
import fleet.core.sandbox_quota as sq_mod
import fleet.core.db.pool as pool_mod
import fleet.core.crypto_vault as cv_mod
import fleet.core.session_auth as sa_mod
import fleet.core.db.backup as bk_mod


# ==============================================================================
# LIFECYCLE TESTS
# ==============================================================================

def test_lifecycle_signals_and_ctrl(tmp_path):
    # POSIX signal handler
    with patch("sys.exit") as mock_exit:
        with patch.object(lc_mod, "execute_clean_shutdown") as mock_shutdown:
            lc_mod._posix_signal_handler(signal.SIGINT, None)
            mock_shutdown.assert_called_with(exit_code=0)
            mock_exit.assert_called_with(0)

    # Checkpoint WAL missing file vs success vs error
    assert lc_mod.checkpoint_sqlite_wal(db_path=tmp_path / "nonexistent.db") is True
    
    # Checkpoint SQLite WAL error handling
    locked_db = tmp_path / "corrupt.db"
    locked_db.write_text("not a sqlite db", encoding="utf-8")
    assert lc_mod.checkpoint_sqlite_wal(db_path=locked_db) is False

    # Clean shutdown with callback raising exception
    def failing_cb():
        raise RuntimeError("Callback crashed")

    lc_mod._SHUTDOWN_CALLBACKS.append((10, "failing_callback", failing_cb))
    lc_mod._SHUTDOWN_TRIGGERED = False
    lc_mod.execute_clean_shutdown()
    assert lc_mod.SHUTDOWN_EVENT.is_set()

    # Reset lifecycle state for subsequent test isolation
    lc_mod._SHUTDOWN_TRIGGERED = False
    lc_mod.SHUTDOWN_EVENT.clear()
    lc_mod._SHUTDOWN_CALLBACKS = [cb for cb in lc_mod._SHUTDOWN_CALLBACKS if cb[1] != "failing_callback"]

    # Win32 console ctrl hook
    mock_kernel32 = MagicMock()
    with patch("os.name", "nt"), patch("ctypes.windll", create=True) as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        lc_mod._setup_win32_console_ctrl()
        mock_kernel32.SetConsoleCtrlHandler.assert_called()


# ==============================================================================
# POWER LIFECYCLE TESTS
# ==============================================================================

def test_power_manager_callbacks_and_monitoring():
    pm = pwr_mod.PowerLifecycleManager(gap_threshold_sec=2.0, wake_cooldown_sec=0.01)
    
    sleep_called = []
    pm.register_sleep_callback(lambda: sleep_called.append(True))
    assert len(pm._sleep_callbacks) == 1

    # Test wake callback and exception handling
    wake_log = []
    pm.register_wake_callback(lambda dt: wake_log.append(dt))
    pm.register_wake_callback(lambda dt: (_ for _ in ()).throw(RuntimeError("Wake error")))

    with patch("fleet.core.power.is_network_available", return_value=True):
        pm._handle_system_resume(estimated_sleep_sec=5.0)
        time.sleep(0.05)
        assert len(wake_log) >= 1

    # Test start and stop monitoring
    with patch.object(pm, "_monitoring_loop"):
        pm.start_monitoring()
        assert pm._monitor_thread is not None
        pm.stop_monitoring()
        assert pm._stop_event.is_set()


# ==============================================================================
# SUPERVISOR TESTS
# ==============================================================================

def test_supervisor_worker_restart_and_limits():
    sup = sup_mod.FleetSupervisor()
    
    # 1. Temporary worker terminates on error without restarting
    worker_temp = sup.register_worker(
        name="temp_worker",
        target=lambda: (_ for _ in ()).throw(ValueError("Temporary crash")),
        restart_strategy="temporary",
        auto_start=False
    )
    worker_temp.running = True
    worker_temp._run_loop()
    assert worker_temp.last_error == "Temporary crash"

    # 2. Permanent worker exceeding max restarts
    worker_perm = sup.register_worker(
        name="perm_worker",
        target=lambda: (_ for _ in ()).throw(RuntimeError("Crasher")),
        restart_strategy="permanent",
        max_restarts=1,
        window_seconds=10.0,
        base_backoff_sec=0.001,
        auto_start=False
    )
    worker_perm.running = True
    worker_perm.restart_timestamps = [time.time(), time.time()]
    worker_perm._run_loop()
    assert worker_perm.running is False

    # 3. Start, status, and stop
    sup.start()
    status = sup.get_status()
    assert status["supervisor_active"] is True
    sup.stop()
    assert sup.get_status()["supervisor_active"] is False

    # Singleton getter
    assert sup_mod.get_fleet_supervisor() is not None


# ==============================================================================
# SANDBOX QUOTA & EGRESS TESTS
# ==============================================================================

def test_sandbox_quota_posix_and_memory():
    quota = sq_mod.ProcessQuotaManager(memory_limit_mb=64)
    res_posix = quota._apply_posix_rlimit()
    assert isinstance(res_posix, bool)

    # get_process_memory_mb on Linux
    with patch("sys.platform", "linux"):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "read_text", return_value="VmRSS:     10240 kB\n"):
                mem_mb = sq_mod.get_process_memory_mb(pid=123)
                assert mem_mb == 10.0

    # get_process_memory_mb on Darwin
    with patch("sys.platform", "darwin"):
        mock_resource = MagicMock()
        mock_resource.RUSAGE_SELF = 0
        mock_usage = MagicMock()
        mock_usage.ru_maxrss = 16 * 1024 * 1024
        mock_resource.getrusage.return_value = mock_usage
        with patch.dict(sys.modules, {"resource": mock_resource}):
            mem_mb_d = sq_mod.get_process_memory_mb(pid=123)
            assert mem_mb_d == 16.0

    # Egress enforcement: mock connect BEFORE entering context
    with patch("socket.socket.connect") as mock_conn:
        with sq_mod.enforce_agent_egress("test_agent", ["db:read"]):
            mock_sock = MagicMock()
            mock_sock.family = socket.AF_INET
            
            # Localhost connect succeeds
            socket.socket.connect(mock_sock, ("127.0.0.1", 8080))
            assert mock_conn.called

            # External connect raises PermissionError
            with pytest.raises(PermissionError):
                socket.socket.connect(mock_sock, ("93.184.216.34", 80))


# ==============================================================================
# DB POOL, CRYPTO VAULT & BACKUP TESTS
# ==============================================================================

def test_db_pool_and_backup(tmp_path):
    test_db = tmp_path / "fleet_pool_test.db"
    
    # Initialize valid db
    conn_init = sqlite3.connect(str(test_db))
    conn_init.execute("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    conn_init.commit()
    conn_init.close()

    pool = pool_mod.SQLiteConnectionPool(timeout=5.0)
    conn = pool.get_connection(test_db)
    assert conn is not None
    pool.close_current_thread_connection()
    pool_mod.close_all_pooled_connections()

    # Backup engine functions
    bk_dir = tmp_path / "backups"
    res_bk = bk_mod.perform_database_backup(source_db_path=test_db, backup_dir=bk_dir, max_retained=2)
    assert res_bk["status"] == "success"
    assert res_bk["integrity_verified"] is True

    # List backups
    backups = bk_mod.list_backups(backup_dir=bk_dir)
    assert len(backups) == 1

    # Prune backups
    pruned = bk_mod.prune_old_backups(backup_dir=bk_dir, max_retained=0)
    assert pruned == 1


def test_crypto_vault_and_session_auth():
    # DPAPI Crypto Vault edge cases
    plaintext = "super_secret_token_12345"
    enc = cv_mod.encrypt_sensitive_text(plaintext)
    assert enc.startswith("ENC:")
    dec = cv_mod.decrypt_sensitive_text(enc)
    assert dec == plaintext

    # Corrupt or non-ENC string
    assert cv_mod.decrypt_sensitive_text("plaintext_without_prefix") == "plaintext_without_prefix"

    # Session Auth CSRF / DNS Rebinding
    ok_host, _ = sa_mod.validate_request_security({"Host": "127.0.0.1:7890"}, method="GET", allowed_origins=set())
    assert ok_host is True

    bad_host, _ = sa_mod.validate_request_security({"Host": "attacker.com"}, method="GET", allowed_origins=set())
    assert bad_host is False

