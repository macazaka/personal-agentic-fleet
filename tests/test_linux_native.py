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



from fleet.tools.fleet_doctor import parse_linux_os_release, detect_os_compatibility, run_fleet_doctor


def test_linux_os_release_parsing(tmp_path):
    os_rel = tmp_path / "os-release"
    os_rel.write_text(
        "# Header comment\n"
        "NAME=\"Ubuntu\"\n"
        "VERSION=\"22.04.4 LTS (Jammy Jellyfish)\"\n"
        "ID=ubuntu\n"
        "ID_LIKE=debian\n"
        "PRETTY_NAME=\"Ubuntu 22.04.4 LTS\"\n"
        "VERSION_ID=\"22.04\"\n",
        encoding="utf-8"
    )
    parsed = parse_linux_os_release(os_rel)
    assert parsed["ID"] == "ubuntu"
    assert parsed["VERSION_ID"] == "22.04"
    assert parsed["PRETTY_NAME"] == "Ubuntu 22.04.4 LTS"


def test_linux_os_compatibility_ubuntu_matrix(tmp_path):
    # Ubuntu 22.04 -> Tier 1 PASS
    os_rel_22 = tmp_path / "os-release-ubuntu-22"
    os_rel_22.write_text(
        "ID=ubuntu\nVERSION_ID=\"22.04\"\nPRETTY_NAME=\"Ubuntu 22.04.4 LTS\"\n",
        encoding="utf-8"
    )
    res_22 = detect_os_compatibility(os_release_path=os_rel_22, platform_override="linux")
    assert res_22["status"] == "PASS"
    assert res_22["tier"] == "Tier 1"
    assert res_22["distro"] == "Ubuntu"
    assert "Tier 1 First-Class Native Support" in res_22["detail"]

    # Ubuntu 20.04 -> Tier 1 PASS
    os_rel_20 = tmp_path / "os-release-ubuntu-20"
    os_rel_20.write_text(
        "ID=ubuntu\nVERSION_ID=\"20.04\"\nPRETTY_NAME=\"Ubuntu 20.04.6 LTS\"\n",
        encoding="utf-8"
    )
    res_20 = detect_os_compatibility(os_release_path=os_rel_20, platform_override="linux")
    assert res_20["status"] == "PASS"
    assert res_20["tier"] == "Tier 1"

    # Legacy Ubuntu 18.04 -> Tier 2 WARN
    os_rel_18 = tmp_path / "os-release-ubuntu-18"
    os_rel_18.write_text(
        "ID=ubuntu\nVERSION_ID=\"18.04\"\nPRETTY_NAME=\"Ubuntu 18.04 LTS\"\n",
        encoding="utf-8"
    )
    res_18 = detect_os_compatibility(os_release_path=os_rel_18, platform_override="linux")
    assert res_18["status"] == "WARN"
    assert res_18["tier"] == "Tier 2"


def test_linux_os_compatibility_debian_matrix(tmp_path):
    # Debian 12 (Bookworm) -> Tier 1 PASS
    os_rel_12 = tmp_path / "os-release-deb-12"
    os_rel_12.write_text(
        "ID=debian\nVERSION_ID=\"12\"\nPRETTY_NAME=\"Debian GNU/Linux 12 (bookworm)\"\n",
        encoding="utf-8"
    )
    res_12 = detect_os_compatibility(os_release_path=os_rel_12, platform_override="linux")
    assert res_12["status"] == "PASS"
    assert res_12["tier"] == "Tier 1"
    assert res_12["distro"] == "Debian"

    # Debian 11 (Bullseye) -> Tier 1 PASS
    os_rel_11 = tmp_path / "os-release-deb-11"
    os_rel_11.write_text(
        "ID=debian\nVERSION_ID=\"11\"\nPRETTY_NAME=\"Debian GNU/Linux 11 (bullseye)\"\n",
        encoding="utf-8"
    )
    res_11 = detect_os_compatibility(os_release_path=os_rel_11, platform_override="linux")
    assert res_11["status"] == "PASS"
    assert res_11["tier"] == "Tier 1"

    # Debian 10 (Buster) -> Tier 2 WARN
    os_rel_10 = tmp_path / "os-release-deb-10"
    os_rel_10.write_text(
        "ID=debian\nVERSION_ID=\"10\"\nPRETTY_NAME=\"Debian GNU/Linux 10 (buster)\"\n",
        encoding="utf-8"
    )
    res_10 = detect_os_compatibility(os_release_path=os_rel_10, platform_override="linux")
    assert res_10["status"] == "WARN"
    assert res_10["tier"] == "Tier 2"


def test_linux_os_compatibility_fedora_matrix(tmp_path):
    # Fedora 39 -> Tier 1 PASS
    os_rel_39 = tmp_path / "os-release-fed-39"
    os_rel_39.write_text(
        "ID=fedora\nVERSION_ID=\"39\"\nPRETTY_NAME=\"Fedora Linux 39 (Workstation Edition)\"\n",
        encoding="utf-8"
    )
    res_39 = detect_os_compatibility(os_release_path=os_rel_39, platform_override="linux")
    assert res_39["status"] == "PASS"
    assert res_39["tier"] == "Tier 1"
    assert res_39["distro"] == "Fedora"

    # Fedora 38 -> Tier 1 PASS
    os_rel_38 = tmp_path / "os-release-fed-38"
    os_rel_38.write_text(
        "ID=fedora\nVERSION_ID=\"38\"\nPRETTY_NAME=\"Fedora Linux 38 (Workstation Edition)\"\n",
        encoding="utf-8"
    )
    res_38 = detect_os_compatibility(os_release_path=os_rel_38, platform_override="linux")
    assert res_38["status"] == "PASS"
    assert res_38["tier"] == "Tier 1"

    # Fedora 36 -> Tier 2 WARN
    os_rel_36 = tmp_path / "os-release-fed-36"
    os_rel_36.write_text(
        "ID=fedora\nVERSION_ID=\"36\"\nPRETTY_NAME=\"Fedora Linux 36\"\n",
        encoding="utf-8"
    )
    res_36 = detect_os_compatibility(os_release_path=os_rel_36, platform_override="linux")
    assert res_36["status"] == "WARN"
    assert res_36["tier"] == "Tier 2"


def test_linux_os_compatibility_arch_rolling(tmp_path):
    # Arch Linux -> Tier 1 PASS (Rolling)
    os_rel_arch = tmp_path / "os-release-arch"
    os_rel_arch.write_text(
        "ID=arch\nPRETTY_NAME=\"Arch Linux\"\n",
        encoding="utf-8"
    )
    res_arch = detect_os_compatibility(os_release_path=os_rel_arch, platform_override="linux")
    assert res_arch["status"] == "PASS"
    assert res_arch["tier"] == "Tier 1"
    assert res_arch["distro"] == "Arch Linux"
    assert "Tier 1 First-Class Native Support" in res_arch["detail"]


def test_os_compatibility_windows_macos_and_posix():
    # Windows 64-bit
    with patch("struct.calcsize", return_value=8):
        res_win = detect_os_compatibility(platform_override="win32")
        assert res_win["status"] == "PASS"
        assert res_win["tier"] == "Tier 1"
        assert res_win["supported"] is True

    # Windows 32-bit (unsupported)
    with patch("struct.calcsize", return_value=4):
        res_win32 = detect_os_compatibility(platform_override="win32")
        assert res_win32["status"] == "FAIL"
        assert res_win32["tier"] == "Unsupported"
        assert res_win32["supported"] is False

    # macOS
    res_mac = detect_os_compatibility(platform_override="darwin")
    assert res_mac["status"] == "PASS"
    assert res_mac["tier"] == "Tier 1"

    # Generic unknown POSIX
    res_other = detect_os_compatibility(platform_override="freebsd")
    assert res_other["status"] == "WARN"
    assert res_other["tier"] == "Tier 2"


def test_fleet_doctor_includes_os_compatibility(tmp_path):
    report = run_fleet_doctor(repo_root=tmp_path)
    assert "os_compatibility" in report
    assert report["os_compatibility"]["tier"] in ("Tier 1", "Tier 2")
    os_diag = next((d for d in report["diagnostics"] if d["check"] == "os_compatibility"), None)
    assert os_diag is not None
    assert os_diag["status"] in ("PASS", "WARN")
