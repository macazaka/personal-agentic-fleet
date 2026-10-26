"""
Unit tests for Linux Native Capabilities in Personal Agentic Fleet.
Verifies memory diagnostics, process resident set sizing, XDG autostart,
systemd service units, DNS flush, native desktop notifications, and SecretService.
"""

from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from fleet.core.optimizer import (
    _get_memory_status_linux,
    flush_dns_cache,
    get_startup_apps,
    open_startup_settings,
    optimize_ram,
)
from fleet.core.sandbox_quota import get_process_memory_mb
from fleet.tools.system_tools import send_linux_notification, send_windows_notification
from fleet.tools.install_service import install_linux_systemd, uninstall_linux_systemd
import fleet.config as cfg
import fleet.core.crypto_vault as vault


def test_linux_memory_status_proc_meminfo(tmp_path):
    fake_meminfo = tmp_path / "meminfo"
    fake_meminfo.write_text(
        "MemTotal:       32768000 kB\n"
        "MemFree:         4096000 kB\n"
        "MemAvailable:   16384000 kB\n"
        "Buffers:          500000 kB\n"
        "Cached:          8000000 kB\n",
        encoding="utf-8"
    )

    with patch("fleet.core.optimizer.Path", return_value=fake_meminfo):
        res = _get_memory_status_linux()
        assert res is not None
        assert res["total_gb"] == 31.25
        assert res["avail_gb"] == 15.62
        assert res["used_gb"] == 15.63
        assert res["percent_used"] == 50
        assert res["status"] == "Optimal"


def test_linux_process_memory_mb(tmp_path):
    fake_status = tmp_path / "status"
    fake_status.write_text(
        "Name:\tpython3\n"
        "State:\tR (running)\n"
        "VmPeak:\t  120000 kB\n"
        "VmSize:\t  110000 kB\n"
        "VmRSS:\t   51200 kB\n"
        "VmData:\t   40000 kB\n",
        encoding="utf-8"
    )

    with patch("sys.platform", "linux"), patch("fleet.core.sandbox_quota.Path") as mock_path_cls:
        mock_instance = MagicMock()
        mock_instance.is_file.return_value = True
        mock_instance.read_text.return_value = fake_status.read_text(encoding="utf-8")
        mock_path_cls.return_value = mock_instance

        mem_mb = get_process_memory_mb(12345)
        assert mem_mb == 50.0  # 51200 / 1024


def test_linux_xdg_autostart_and_systemd(tmp_path):
    user_autostart = tmp_path / ".config" / "autostart"
    user_autostart.mkdir(parents=True, exist_ok=True)
    discord_desktop = user_autostart / "discord.desktop"
    discord_desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Discord\n"
        "Exec=/usr/bin/discord --start-minimized\n",
        encoding="utf-8"
    )

    sys_autostart = tmp_path / "etc_xdg_autostart"
    sys_autostart.mkdir(parents=True, exist_ok=True)

    user_systemd = tmp_path / ".config" / "systemd" / "user"
    user_systemd.mkdir(parents=True, exist_ok=True)
    svc = user_systemd / "agent_cron.service"
    svc.write_text("[Unit]\nDescription=Agent Cron\n", encoding="utf-8")

    with patch("sys.platform", "linux"), \
         patch("pathlib.Path.home", return_value=tmp_path):
        apps = get_startup_apps()
        assert len(apps) >= 2
        discord_app = next((a for a in apps if a["name"] == "Discord"), None)
        assert discord_app is not None
        assert discord_app["impact"] == "High"
        assert discord_app["scope"] == "User"

        systemd_app = next((a for a in apps if a["name"] == "agent_cron"), None)
        assert systemd_app is not None
        assert systemd_app["scope"] == "Systemd User"


def test_linux_desktop_notifications_fallback():
    # 1. Successful notify-send
    with patch("fleet.tools.system_tools.ENABLE_WINDOWS_NOTIFICATIONS", True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = send_linux_notification("Fleet Alert", "System check completed")
        assert ok is True
        mock_run.assert_called_with(
            ["notify-send", "-a", "Personal Agentic Fleet", "-i", "dialog-information", "Fleet Alert", "System check completed"],
            capture_output=True,
            timeout=5,
            check=False,
        )

    # 2. Zenity fallback when notify-send fails
    with patch("fleet.tools.system_tools.ENABLE_WINDOWS_NOTIFICATIONS", True), \
         patch("subprocess.run") as mock_run:
        # First call fails, second call succeeds
        mock_run.side_effect = [
            FileNotFoundError("notify-send not found"),
            MagicMock(returncode=0),
        ]
        ok = send_linux_notification("Fleet Alert", "Zenity fallback")
        assert ok is True

    # 3. Universal send_windows_notification routes to linux on non-nt
    with patch("sys.platform", "linux"), \
         patch("os.name", "posix"), \
         patch("fleet.tools.system_tools.send_linux_notification", return_value=True) as mock_linux_fn:
        assert send_windows_notification("Hello", "World") is True
        mock_linux_fn.assert_called_once_with("Hello", "World")


def test_linux_dns_flush_resolvectl():
    with patch("sys.platform", "linux"), \
         patch("os.name", "posix"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = flush_dns_cache()
        assert res["status"] == "success"
        assert "flushed Linux DNS resolver cache" in res["message"]
        mock_run.assert_called_with(["resolvectl", "flush-caches"], capture_output=True, text=True, timeout=5)


def test_linux_open_startup_settings():
    with patch("sys.platform", "linux"), \
         patch("os.name", "posix"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = open_startup_settings()
        assert res["status"] == "success"


def test_linux_secret_tool_integration():
    with patch("sys.platform", "linux"), \
         patch("subprocess.run") as mock_run:
        # Test store
        mock_run.return_value = MagicMock(returncode=0)
        stored = vault.set_secure_secret("TEST_SECRET_KEY", "secret_val_123")
        assert stored is True

        # Test lookup
        mock_run.return_value = MagicMock(returncode=0, stdout="retrieved_secret_val\n")
        val = cfg.get_secure_secret("TEST_SECRET_KEY")
        assert val == "retrieved_secret_val"


def test_linux_systemd_installer(tmp_path):
    with patch("pathlib.Path.home", return_value=tmp_path), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = install_linux_systemd()
        assert res["status"] == "success"

        service_file = tmp_path / ".config" / "systemd" / "user" / "fleet.service"
        assert service_file.is_file()
        content = service_file.read_text(encoding="utf-8")
        assert "Description=Personal Agentic Fleet Microkernel Daemon" in content
        assert "Restart=always" in content
        assert "Environment=FLEET_HOST=0.0.0.0" in content

        uninst = uninstall_linux_systemd()
        assert uninst["status"] == "success"
        assert not service_file.exists()

