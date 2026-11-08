"""Unit tests for fleet.core.optimizer (PC Performance Optimizer)."""
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fleet.core.event_bus import DeterministicEventBus, FleetEvent
from fleet.core.optimizer import (
    clean_temp_files,
    flush_dns_cache,
    get_dev_cache_info,
    get_memory_status,
    get_pc_performance_diagnostics,
    get_startup_apps,
    get_temp_bloat_info,
    get_top_processes,
    open_startup_settings,
    optimize_ram,
    purge_dev_caches,
)


def test_get_memory_status_normal():
    mem = get_memory_status()
    assert isinstance(mem, dict)
    assert "total_gb" in mem
    assert "avail_gb" in mem
    assert "used_gb" in mem
    assert "percent_used" in mem
    assert mem["total_gb"] > 0
    assert 0 <= mem["percent_used"] <= 100


def test_get_memory_status_fallback():
    with patch("fleet.core.optimizer._get_memory_status_win32", return_value=None), \
         patch("fleet.core.optimizer._get_memory_status_darwin", return_value=None), \
         patch("fleet.core.optimizer._get_memory_status_linux", return_value=None):
        mem = get_memory_status()
        assert mem["total_gb"] == 16.0
        assert mem["percent_used"] == 50


def test_get_top_processes_csv():
    sample_csv = (
        '"chrome.exe","1234","Console","1","250,500 K"\n'
        '"code.exe","5678","Console","1","180,000 K"\n'
        '"python.exe","9012","Console","1","95,000 K"\n'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=sample_csv)
        procs = get_top_processes(limit=3)
        assert len(procs) == 3
        assert procs[0]["name"] == "chrome.exe"
        assert procs[0]["mem_mb"] == 244.6
        assert procs[0]["memory_mb"] == 244.6
        assert procs[1]["name"] == "code.exe"


def test_get_top_processes_fallback():
    with patch("subprocess.run", side_effect=Exception("tasklist not found")):
        procs = get_top_processes()
        assert procs == []


def test_get_temp_bloat_info():
    with tempfile.TemporaryDirectory() as tmp_dir:
        f1 = Path(tmp_dir) / "test1.tmp"
        f2 = Path(tmp_dir) / "test2.log"
        f1.write_text("hello" * 200)
        f2.write_text("world" * 500)

        with patch("tempfile.gettempdir", return_value=tmp_dir):
            info = get_temp_bloat_info()
            assert info["file_count"] >= 2
            assert info["size_mb"] >= 0.0
            assert "dir_path" in info


def test_get_dev_cache_info():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir) / "fleet" / "__pycache__"
        cache_dir.mkdir(parents=True)
        pyc_file = cache_dir / "mod.cpython-314.pyc"
        pyc_file.write_bytes(b"\x00" * 1024)

        extra_pyc = Path(tmp_dir) / "test.pyc"
        extra_pyc.write_bytes(b"\x00" * 2048)

        info = get_dev_cache_info(target_path=tmp_dir)
        assert info["dir_count"] == 1
        assert info["file_count"] == 2
        assert info["size_mb"] >= 0.0

    # Non-existent target
    info_none = get_dev_cache_info(target_path="Z:/non_existent_path_99999")
    assert info_none["dir_count"] == 0
    assert info_none["file_count"] == 0


def test_get_startup_apps():
    apps = get_startup_apps()
    assert isinstance(apps, list)

    # Exception path (Windows registry mock)
    with patch("sys.platform", "win32"), patch("winreg.OpenKey", side_effect=FileNotFoundError("Key missing")):
        apps_empty = get_startup_apps()
        assert apps_empty == []


def test_clean_temp_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        f1 = Path(tmp_dir) / "clean1.tmp"
        f2 = Path(tmp_dir) / "sub" / "clean2.tmp"
        f2.parent.mkdir()
        f1.write_text("junk data 1")
        f2.write_text("junk data 2")

        with patch("tempfile.gettempdir", return_value=tmp_dir):
            res = clean_temp_files()
            assert res["status"] == "success"
            assert res["deleted_files"] == 2
            assert not f1.exists()


def test_clean_temp_files_locked():
    with tempfile.TemporaryDirectory() as tmp_dir:
        f1 = Path(tmp_dir) / "locked.tmp"
        f1.write_text("locked file")

        with patch("tempfile.gettempdir", return_value=tmp_dir):
            with patch.object(Path, "unlink", side_effect=PermissionError("File locked")):
                res = clean_temp_files()
                assert res["status"] == "success"
                assert res["skipped_locked_files"] >= 1


def test_flush_dns_cache_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Successfully flushed the DNS Resolver Cache.")
        res = flush_dns_cache()
        assert res["status"] == "success"
        assert "Successfully flushed" in res["message"]


def test_flush_dns_cache_error():
    with patch("subprocess.run", side_effect=Exception("ipconfig timed out")):
        res = flush_dns_cache()
        assert res["status"] == "error"
        assert "ipconfig timed out" in res["message"]


def test_purge_dev_caches():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir) / "__pycache__"
        cache_dir.mkdir()
        pyc = cache_dir / "app.pyc"
        pyc.write_text("bytecode")

        orphan_pyc = Path(tmp_dir) / "standalone.pyc"
        orphan_pyc.write_text("standalone")

        res = purge_dev_caches(target_path=tmp_dir)
        assert res["status"] == "success"
        assert res["removed_dirs"] >= 1
        assert res["removed_files"] >= 2
        assert not pyc.exists()
        assert not orphan_pyc.exists()


def test_optimize_ram():
    res = optimize_ram()
    assert res["status"] == "success"
    assert "memory_load" in res
    assert "available_gb" in res
    assert "RAM optimization sweep completed" in res["message"]


def test_open_startup_settings():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = open_startup_settings()
        assert res["status"] == "success"

    with patch("subprocess.run", side_effect=Exception("powershell missing")):
        res_err = open_startup_settings()
        assert res_err["status"] == "error"


def test_get_pc_performance_diagnostics_normal():
    diag = get_pc_performance_diagnostics()
    assert diag["status"] == "success"
    assert 0 <= diag["health_score"] <= 100
    assert diag["score_status"] in ["Excellent", "Good", "Fair", "Needs Optimization"]
    assert diag["tokens_used"] == 0
    assert diag["cost_usd"] == "$0.00"
    assert isinstance(diag["recommendations"], list)
    assert len(diag["top_processes"]) > 0


def test_get_pc_performance_diagnostics_score_branches():
    # 1. Heavy load scenario (score drops below 55)
    mock_mem_heavy = {"total_gb": 16.0, "avail_gb": 2.0, "used_gb": 14.0, "percent_used": 88.0}
    mock_disk_heavy = {"total_gb": 500.0, "free_gb": 40.0, "used_gb": 460.0, "percent_used": 92.0}
    mock_temp_heavy = {"file_count": 500, "size_mb": 350.0, "dir_path": "C:/Temp"}
    mock_dev_heavy = {"dir_count": 10, "file_count": 40, "size_mb": 25.0}
    mock_start_heavy = [f"App{i}" for i in range(20)]

    with patch("fleet.core.optimizer.get_memory_status", return_value=mock_mem_heavy), \
         patch("fleet.core.optimizer.get_disk_usage", return_value=mock_disk_heavy), \
         patch("fleet.core.optimizer.get_temp_bloat_info", return_value=mock_temp_heavy), \
         patch("fleet.core.optimizer.get_dev_cache_info", return_value=mock_dev_heavy), \
         patch("fleet.core.optimizer.get_startup_apps", return_value=mock_start_heavy):
        d_heavy = get_pc_performance_diagnostics()
        assert d_heavy["health_score"] <= 55
        assert d_heavy["score_status"] == "Needs Optimization"
        recom_ids = [r["id"] for r in d_heavy["recommendations"]]
        assert "clean_temp" in recom_ids
        assert "optimize_ram" in recom_ids
        assert "purge_caches" in recom_ids
        assert "open_startup" in recom_ids

    # 2. Medium load scenario
    mock_mem_med = {"total_gb": 16.0, "avail_gb": 5.0, "used_gb": 11.0, "percent_used": 68.0}
    mock_disk_med = {"total_gb": 500.0, "free_gb": 110.0, "used_gb": 390.0, "percent_used": 78.0}
    mock_temp_med = {"file_count": 80, "size_mb": 75.0, "dir_path": "C:/Temp"}
    mock_dev_med = {"dir_count": 2, "file_count": 4, "size_mb": 1.5}
    mock_start_med = [f"App{i}" for i in range(10)]

    with patch("fleet.core.optimizer.get_memory_status", return_value=mock_mem_med), \
         patch("fleet.core.optimizer.get_disk_usage", return_value=mock_disk_med), \
         patch("fleet.core.optimizer.get_temp_bloat_info", return_value=mock_temp_med), \
         patch("fleet.core.optimizer.get_dev_cache_info", return_value=mock_dev_med), \
         patch("fleet.core.optimizer.get_startup_apps", return_value=mock_start_med):
        d_med = get_pc_performance_diagnostics()
        assert d_med["score_status"] in ["Fair", "Good"]

    # 3. Clean optimal scenario
    mock_mem_clean = {"total_gb": 32.0, "avail_gb": 22.0, "used_gb": 10.0, "percent_used": 31.0}
    mock_disk_clean = {"total_gb": 1000.0, "free_gb": 600.0, "used_gb": 400.0, "percent_used": 40.0}
    mock_temp_clean = {"file_count": 5, "size_mb": 2.0, "dir_path": "C:/Temp"}
    mock_dev_clean = {"dir_count": 0, "file_count": 0, "size_mb": 0.0}
    mock_start_clean = ["SecurityHealth"]

    with patch("fleet.core.optimizer.get_memory_status", return_value=mock_mem_clean), \
         patch("fleet.core.optimizer.get_disk_usage", return_value=mock_disk_clean), \
         patch("fleet.core.optimizer.get_temp_bloat_info", return_value=mock_temp_clean), \
         patch("fleet.core.optimizer.get_dev_cache_info", return_value=mock_dev_clean), \
         patch("fleet.core.optimizer.get_startup_apps", return_value=mock_start_clean):
        d_clean = get_pc_performance_diagnostics()
        assert d_clean["health_score"] >= 85
        assert d_clean["score_status"] == "Excellent"


def test_event_bus_optimizer_integration():
    bus = DeterministicEventBus()
    
    # 1. DIAGNOSTICS
    ev_diag = FleetEvent(sender="test", target="system", action="DIAGNOSTICS")
    res_diag = bus.dispatch(ev_diag)
    assert res_diag["status"] == "success"
    assert "health_score" in res_diag["data"]

    # 2. CLEAN_TEMP
    ev_clean = FleetEvent(sender="test", target="system", action="CLEAN_TEMP")
    res_clean = bus.dispatch(ev_clean)
    assert res_clean["status"] == "success"

    # 3. FLUSH_DNS
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Successfully flushed")
        ev_dns = FleetEvent(sender="test", target="system", action="FLUSH_DNS")
        res_dns = bus.dispatch(ev_dns)
        assert res_dns["status"] == "success"

    # 4. PURGE_CACHES
    with tempfile.TemporaryDirectory() as tmp_dir:
        ev_purge = FleetEvent(sender="test", target="system", action="PURGE_CACHES", payload={"target_path": tmp_dir})
        res_purge = bus.dispatch(ev_purge)
        assert res_purge["status"] == "success"

    # 5. OPTIMIZE_RAM
    ev_ram = FleetEvent(sender="test", target="system", action="OPTIMIZE_RAM")
    res_ram = bus.dispatch(ev_ram)
    assert res_ram["status"] == "success"

    # 6. OPEN_STARTUP
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ev_start = FleetEvent(sender="test", target="system", action="OPEN_STARTUP")
        res_start = bus.dispatch(ev_start)
        assert res_start["status"] == "success"

    # 7. UNKNOWN_ACTION
    ev_bad = FleetEvent(sender="test", target="system", action="INVALID_ACTION")
    res_bad = bus.dispatch(ev_bad)
    assert res_bad["status"] == "error"


def test_optimizer_edge_cases_and_error_handling():
    # 1. ValueError in get_top_processes
    sample_csv = (
        '"bad.exe","9999","Console","1","N/A"\n'
        '"good.exe","1111","Console","1","50,000 K"\n'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=sample_csv)
        procs = get_top_processes()
        assert len(procs) == 1
        assert procs[0]["name"] == "good.exe"

    # 2. Stat error & walk error in get_temp_bloat_info
    with tempfile.TemporaryDirectory() as tmp_dir:
        dummy_file = Path(tmp_dir) / "test_file.dat"
        dummy_file.write_text("data")
        with patch("tempfile.gettempdir", return_value=tmp_dir):
            orig_os_stat = os.stat
            def mock_stat_denied(path, *args, **kwargs):
                if "test_file.dat" in str(path):
                    raise OSError("Access denied")
                return orig_os_stat(path, *args, **kwargs)

            with patch("os.stat", side_effect=mock_stat_denied):
                res = get_temp_bloat_info()
                assert res["file_count"] == 0

            with patch("os.walk", side_effect=OSError("Walk failed")):
                res_walk = get_temp_bloat_info()
                assert res_walk["file_count"] == 0

    # 3. .pytest_cache & stat error & exception in get_dev_cache_info
    with tempfile.TemporaryDirectory() as tmp_dir:
        p_cache = Path(tmp_dir) / ".pytest_cache"
        p_cache.mkdir()
        pycache = Path(tmp_dir) / "__pycache__"
        pycache.mkdir()
        dummy = pycache / "sample.pyc"
        dummy.write_text("x")
        orig_os_stat = os.stat
        def mock_stat_err(path, *args, **kwargs):
            if str(path).endswith(".pyc") or "sample" in str(path):
                raise OSError("stat error")
            return orig_os_stat(path, *args, **kwargs)

        with patch("os.stat", side_effect=mock_stat_err):
            res = get_dev_cache_info(target_path=tmp_dir)
            assert res["dir_count"] >= 1

        with patch.object(Path, "rglob", side_effect=PermissionError("rglob failed")):
            res_err = get_dev_cache_info(target_path=tmp_dir)
            assert res_err["dir_count"] == 0

    # 4. EnumValue error in get_startup_apps
    with patch("sys.platform", "win32"):
        with patch("winreg.OpenKey"):
            with patch("winreg.QueryInfoKey", return_value=(0, 1, 0)):
                with patch("winreg.EnumValue", side_effect=OSError("Registry read error")):
                    apps = get_startup_apps()
                    assert apps == []

    # 5. rmdir error in clean_temp_files
    with tempfile.TemporaryDirectory() as tmp_dir:
        sub = Path(tmp_dir) / "locked_dir"
        sub.mkdir()
        with patch("tempfile.gettempdir", return_value=tmp_dir):
            with patch.object(Path, "rmdir", side_effect=OSError("Directory locked")):
                res_clean = clean_temp_files()
                assert res_clean["status"] == "success"

    # 6. Errors in purge_dev_caches (unlink & rmdir)
    with tempfile.TemporaryDirectory() as tmp_dir:
        pycache = Path(tmp_dir) / "__pycache__"
        pycache.mkdir()
        (pycache / "f.pyc").write_text("abc")
        (Path(tmp_dir) / "stand.pyc").write_text("def")
        with patch.object(Path, "unlink", side_effect=OSError("unlink error")):
            with patch.object(Path, "rmdir", side_effect=OSError("rmdir error")):
                res_purge = purge_dev_caches(target_path=tmp_dir)
                assert res_purge["status"] == "success"

    # 7. EmptyWorkingSet exception in optimize_ram
    import ctypes
    if hasattr(ctypes, "windll"):
        with patch("ctypes.windll.psapi.EmptyWorkingSet", side_effect=Exception("Failed")):
            res_ram = optimize_ram()
            assert res_ram["status"] == "success"
    else:
        res_ram = optimize_ram()
        assert res_ram["status"] == "success"



def test_macos_optimizer_capabilities():
    from fleet.core.optimizer import (
        _get_memory_status_darwin,
        _get_memory_status_linux,
        flush_dns_cache,
        get_startup_apps,
        open_startup_settings,
        optimize_ram,
    )

    # 1. macOS memory status calculation
    def mock_sysctl_vmstat(cmd, *args, **kwargs):
        if cmd == ["sysctl", "-n", "hw.memsize"]:
            return MagicMock(returncode=0, stdout="17179869184\n")  # 16 GB
        elif cmd == ["sysctl", "-n", "vm.pagesize"]:
            return MagicMock(returncode=0, stdout="4096\n")
        elif cmd == ["vm_stat"]:
            vm_out = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                               1048576.
Pages active:                             1500000.
Pages inactive:                            524288.
Pages purgeable:                           262144.
"""
            return MagicMock(returncode=0, stdout=vm_out)
        return MagicMock(returncode=1, stdout="")

    with patch("subprocess.run", side_effect=mock_sysctl_vmstat):
        mem_mac = _get_memory_status_darwin()
        assert mem_mac is not None
        assert mem_mac["total_gb"] == 16.0
        assert mem_mac["avail_gb"] == 7.0
        assert mem_mac["percent_used"] == 56
        assert mem_mac["status"] == "Optimal"

    # macOS memory status error fallback
    with patch("subprocess.run", side_effect=Exception("sysctl not found")):
        assert _get_memory_status_darwin() is None

    # 2. Linux memory status
    with patch.object(Path, "is_file", return_value=True), \
         patch.object(Path, "read_text", return_value="MemTotal:       16384000 kB\nMemAvailable:    8192000 kB\n"):
        mem_linux = _get_memory_status_linux()
        assert mem_linux is not None
        assert mem_linux["total_gb"] == 15.62
        assert mem_linux["avail_gb"] == 7.81

    # 3. macOS DNS flush
    with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        res_dns = flush_dns_cache()
        assert res_dns["status"] == "success"
        assert "macOS Directory Service and DNS cache" in res_dns["message"]
        # Verified dscacheutil was invoked
        called_cmds = [call[0][0] for call in mock_run.call_args_list]
        assert ["dscacheutil", "-flushcache"] in called_cmds

    # 4. macOS RAM optimization (purge command)
    with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res_opt = optimize_ram()
        assert res_opt["status"] == "success"
        called_cmds = [call[0][0] for call in mock_run.call_args_list]
        assert ["purge"] in called_cmds

    # 5. macOS Startup Settings
    with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res_open = open_startup_settings()
        assert res_open["status"] == "success"
        assert "macOS Login Items" in res_open["message"]
        assert "x-apple.systempreferences:com.apple.LoginItems-Settings.extension" in mock_run.call_args[0][0][1]

    # 6. macOS Startup Apps LaunchAgents scan
    with tempfile.TemporaryDirectory() as tmp_dir:
        mac_agent_dir = Path(tmp_dir) / "Library" / "LaunchAgents"
        mac_agent_dir.mkdir(parents=True)
        (mac_agent_dir / "com.example.teams.plist").write_text("<plist></plist>", encoding="utf-8")
        (mac_agent_dir / "com.custom.updater.plist").write_text("<plist></plist>", encoding="utf-8")

        with patch("sys.platform", "darwin"), patch.object(Path, "home", return_value=Path(tmp_dir)):
            apps = get_startup_apps()
            user_apps = [a for a in apps if a.get("scope") == "User"]
            assert len(user_apps) == 2
            app_names = [a["name"] for a in user_apps]
            assert "teams" in app_names
            assert "updater" in app_names
            assert user_apps[0]["scope"] == "User"


def test_winget_parser_and_package_classification():
    from fleet.core.optimizer import (
        _classify_package_category,
        _parse_winget_upgrade_output,
    )

    assert _classify_package_category("Firefox Browser", "Mozilla.Firefox") == "Security & Critical"
    assert _classify_package_category("Python 3.12", "Python.Python.3.12") == "Developer Tools"
    assert _classify_package_category("Spotify Music", "Spotify.Spotify") == "Application"

    sample_winget = """Name                                  Id                                Version        Available      Source
-------------------------------------------------------------------------------------------------------------
Python 3.12                           Python.Python.3.12                3.12.2         3.12.7         winget
Google Chrome                         Google.Chrome                     124.0.6367.60  125.0.6422.76  winget
Notepad++                             Notepad++.Notepad++               8.6.4          8.6.7          winget
3 upgrades available.
"""
    parsed = _parse_winget_upgrade_output(sample_winget)
    assert len(parsed) == 3
    assert parsed[0]["id"] == "Python.Python.3.12"
    assert parsed[0]["category"] == "Developer Tools"
    assert parsed[1]["id"] == "Google.Chrome"
    assert parsed[1]["category"] == "Security & Critical"
    assert parsed[2]["id"] == "Notepad++.Notepad++"
    assert parsed[2]["category"] == "Application"

    # Regex fallback without dashed separator
    fallback_out = "Docker Desktop  Docker.DockerDesktop  4.28.0  4.30.0  winget\n"
    parsed_fb = _parse_winget_upgrade_output(fallback_out)
    assert len(parsed_fb) == 1
    assert parsed_fb[0]["id"] == "Docker.DockerDesktop"
    assert _parse_winget_upgrade_output("") == []


def test_upgrade_policy_persistence():
    import fleet.core.optimizer as opt_mod
    from fleet.core.optimizer import get_upgrade_policy, set_upgrade_policy

    with tempfile.TemporaryDirectory() as tmp_dir:
        policy_file = Path(tmp_dir) / "optimizer_upgrade_policy.json"
        with patch.object(opt_mod, "_get_upgrade_policy_file", return_value=policy_file):
            pol = get_upgrade_policy()
            assert pol["auto_check_enabled"] is True
            assert pol["auto_install_security_and_patch"] is True
            assert pol["never_auto_reboot"] is True

            res = set_upgrade_policy({
                "auto_install_all_software": False,
                "check_interval_hours": 6,
                "excluded_packages": [" Some.Pkg ", ""],
            })
            assert res["auto_install_all_software"] is False
            assert res["check_interval_hours"] == 6
            assert res["excluded_packages"] == ["Some.Pkg"]

            # Corrupt file fallback
            policy_file.write_text("{corrupt json", encoding="utf-8")
            pol_fallback = get_upgrade_policy()
            assert pol_fallback["auto_check_enabled"] is True


def test_os_and_software_upgrade_scanning_cross_platform():
    import fleet.core.optimizer as opt_mod
    from fleet.core.optimizer import (
        _get_os_version_and_update_status,
        _scan_software_upgrades,
        check_os_and_software_upgrades,
    )

    # 1. Windows OS & Software Scan
    ps_json = '[{"title": "2026-11 Cumulative Security Update", "kb": "KB5039212", "mandatory": true}]'
    winget_out = (
        "Name           Id                    Version  Available  Source\n"
        "----------------------------------------------------------------\n"
        "OpenSSL Light  ShiningLight.OpenSSL  3.1.0    3.1.4      winget\n"
        "VS Code        Microsoft.VSCode      1.88.0   1.89.1     winget\n"
    )

    def win_subproc(cmd, *args, **kwargs):
        if cmd[0] == "powershell":
            return MagicMock(returncode=0, stdout=ps_json)
        if cmd[0] == "winget":
            return MagicMock(returncode=0, stdout=winget_out)
        return MagicMock(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = Path(tmp_dir) / "optimizer_upgrade_state.json"
        policy_file = Path(tmp_dir) / "optimizer_upgrade_policy.json"
        with patch.object(opt_mod, "_get_upgrade_state_file", return_value=state_file), \
             patch.object(opt_mod, "_get_upgrade_policy_file", return_value=policy_file), \
             patch("os.name", "nt"), \
             patch("sys.platform", "win32"), \
             patch("subprocess.run", side_effect=win_subproc):
            os_win = _get_os_version_and_update_status(scan_live=True)
            assert os_win["os_updates_count"] == 1
            assert os_win["os_updates"][0]["id"] == "KB5039212"

            sw_win = _scan_software_upgrades(scan_live=True)
            assert len(sw_win) == 2
            assert sw_win[0]["category"] == "Security & Critical"
            assert sw_win[1]["category"] == "Developer Tools"

            opt_mod._UPGRADE_SCAN_CACHE["timestamp"] = 0.0
            opt_mod._UPGRADE_SCAN_CACHE["data"] = None
            summary = check_os_and_software_upgrades(force_refresh=True)
            assert summary["status"] == "success"
            assert summary["total_pending_count"] == 3
            assert summary["security_critical_count"] == 2
            assert summary["overall_status"] == "Action Recommended"

            # Cached read
            summary_cached = check_os_and_software_upgrades(force_refresh=False)
            assert summary_cached["total_pending_count"] == 3

    # 2. macOS OS & Software Scan
    def mac_subproc(cmd, *args, **kwargs):
        if cmd[:2] == ["softwareupdate", "-l"]:
            return MagicMock(returncode=0, stdout="* Label: macOS Sequoia 15.1.1-24B91\n")
        if cmd[:2] == ["brew", "outdated"]:
            return MagicMock(
                returncode=0,
                stdout='{"formulae":[{"name":"git","installed_versions":["2.44.0"],"current_version":"2.45.0"}],"casks":[]}',
            )
        return MagicMock(returncode=0, stdout="")

    with patch("os.name", "posix"), \
         patch("sys.platform", "darwin"), \
         patch("subprocess.run", side_effect=mac_subproc):
        os_mac = _get_os_version_and_update_status(scan_live=True)
        assert os_mac["os_family"] == "macOS"
        assert os_mac["os_updates_count"] == 1
        sw_mac = _scan_software_upgrades(scan_live=True)
        assert len(sw_mac) == 1
        assert sw_mac[0]["source"] == "homebrew"

    # 3. Linux OS & Software Scan
    apt_sample = (
        "Listing... Done\n"
        "openssl/noble-security 3.0.13-0ubuntu3.1 amd64 [upgradable from: 3.0.13-0ubuntu3]\n"
        "curl/noble-updates 8.5.0-2ubuntu10.1 amd64 [upgradable from: 8.5.0-2ubuntu10]\n"
    )
    with patch("os.name", "posix"), \
         patch("sys.platform", "linux"), \
         patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=apt_sample)):
        os_lin = _get_os_version_and_update_status(scan_live=True)
        assert os_lin["os_updates_count"] == 1
        sw_lin = _scan_software_upgrades(scan_live=True)
        assert len(sw_lin) == 2
        assert sw_lin[0]["source"] == "apt"


def test_install_software_and_auto_upgrade_manager():
    import fleet.core.optimizer as opt_mod
    from fleet.core.optimizer import (
        install_software_upgrades,
        run_automatic_upgrade_manager,
        set_upgrade_policy,
    )

    mock_scan_data = {
        "status": "success",
        "overall_status": "Action Recommended",
        "os_info": {
            "os_family": "Windows",
            "display_version": "Windows 11 (24H2)",
            "build_number": "26200.1",
            "pending_reboot": False,
            "os_up_to_date": False,
        },
        "os_updates": [{"id": "KB2267602", "title": "Security Intelligence Update", "severity": "Critical", "source": "Windows Update"}],
        "os_updates_count": 1,
        "software_upgrades": [
            {
                "name": "Git",
                "id": "Git.Git",
                "current_version": "2.44.0",
                "available_version": "2.45.1",
                "source": "winget",
                "category": "Security & Critical",
                "is_security_or_critical": True,
            },
            {
                "name": "VLC",
                "id": "VideoLAN.VLC",
                "current_version": "3.0.18",
                "available_version": "3.0.20",
                "source": "winget",
                "category": "Application",
                "is_security_or_critical": False,
            },
        ],
        "software_upgrades_count": 2,
        "eligible_software_count": 2,
        "security_critical_count": 2,
        "total_pending_count": 3,
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        policy_file = Path(tmp_dir) / "optimizer_upgrade_policy.json"
        state_file = Path(tmp_dir) / "optimizer_upgrade_state.json"
        with patch.object(opt_mod, "_get_upgrade_policy_file", return_value=policy_file), \
             patch.object(opt_mod, "_get_upgrade_state_file", return_value=state_file), \
             patch("fleet.core.optimizer.check_os_and_software_upgrades", return_value=mock_scan_data):

            # 1. Install on Windows via winget
            with patch("os.name", "nt"), \
                 patch("sys.platform", "win32"), \
                 patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Successfully installed")):
                res_inst = install_software_upgrades(package_ids=["Git.Git"], include_os=True)
                assert res_inst["status"] == "success"
                assert res_inst["upgraded_count"] == 1
                assert res_inst["upgraded_packages"][0]["id"] == "Git.Git"
                assert res_inst["os_patch_result"] is not None

                # Run full automatic upgrade manager (security only vs all software)
                set_upgrade_policy({"auto_install_all_software": False, "auto_install_security_and_patch": True})
                res_auto = run_automatic_upgrade_manager(force_scan=False)
                assert res_auto["status"] == "success"
                assert res_auto["selected_for_upgrade_count"] == 1
                assert res_auto["upgraded_count"] == 1
                assert "VideoLAN.VLC" in res_auto["skipped_by_policy"]

            # 2. Install on macOS via brew
            with patch("os.name", "posix"), \
                 patch("sys.platform", "darwin"), \
                 patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Upgraded")):
                res_mac = install_software_upgrades(package_ids=["Git.Git"], include_os=True)
                assert res_mac["status"] == "success"
                assert res_mac["upgraded_count"] == 1

            # 3. Install on Linux via apt-get
            with patch("os.name", "posix"), \
                 patch("sys.platform", "linux"), \
                 patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Upgraded")):
                res_lin = install_software_upgrades(package_ids=["Git.Git"], include_os=True)
                assert res_lin["status"] == "success"
                assert res_lin["upgraded_count"] == 1


def test_optimizer_agent_and_event_bus_upgrades_and_mcp():
    import json
    import urllib.parse
    from fleet.agents.optimizer.agent import OptimizerAgent
    from fleet.api.optimizer_api import get_upgrades, post_run_upgrades, post_upgrade_policy
    from fleet.mcp_server import (
        fleet_manage_os_and_software_upgrades,
        fleet_optimize_and_audit,
    )

    mock_upg_status = {
        "status": "success",
        "overall_status": "Up to Date",
        "os_info": {
            "os_family": "Windows",
            "display_version": "Windows 11 (24H2)",
            "build_number": "26200.1",
            "pending_reboot": False,
            "os_up_to_date": True,
        },
        "os_updates": [],
        "os_updates_count": 0,
        "software_upgrades": [],
        "software_upgrades_count": 0,
        "eligible_software_count": 0,
        "security_critical_count": 0,
        "total_pending_count": 0,
        "policy": {
            "auto_check_enabled": True,
            "auto_install_security_and_patch": True,
            "auto_install_all_software": True,
            "auto_install_os_patches": True,
            "never_auto_reboot": True,
            "check_interval_hours": 12,
            "excluded_packages": [],
        },
    }
    mock_auto_res = {
        "status": "success",
        "message": "System OS and software packages are already up to date.",
        "upgraded_count": 0,
        "upgraded_packages": [],
        "failed_packages": [],
        "pending_reboot": False,
        "tokens_used": 0,
    }

    with patch("fleet.core.optimizer.check_os_and_software_upgrades", return_value=mock_upg_status), \
         patch("fleet.core.optimizer.run_automatic_upgrade_manager", return_value=mock_auto_res), \
         patch("fleet.server.check_os_and_software_upgrades", return_value=mock_upg_status), \
         patch("fleet.server.run_automatic_upgrade_manager", return_value=mock_auto_res):

        # 1. OptimizerAgent tasks
        bus = DeterministicEventBus()
        agent = OptimizerAgent(event_bus=bus)
        r_check = agent.execute_task("check_upgrades")
        assert r_check["status"] == "success"
        r_manage = agent.execute_task("manage_upgrades")
        assert r_manage["status"] == "success"

        # 2. EventBus actions
        assert bus.dispatch(FleetEvent(sender="test", target="system", action="CHECK_UPGRADES"))["status"] == "success"
        assert bus.dispatch(FleetEvent(sender="test", target="system", action="AUTO_UPGRADE"))["status"] == "success"
        assert bus.dispatch(FleetEvent(sender="test", target="system", action="GET_UPGRADE_POLICY"))["status"] == "success"
        assert bus.dispatch(
            FleetEvent(sender="test", target="system", action="SET_UPGRADE_POLICY", payload={"auto_install_all_software": True})
        )["status"] == "success"

        # 3. API Route Handlers
        mock_handler = MagicMock()
        get_upgrades(mock_handler, urllib.parse.urlparse("/api/optimizer/upgrades?refresh=1"))
        assert mock_handler._send_json.call_args[0][0]["status"] == "success"

        post_run_upgrades(mock_handler, {"mode": "auto_manage", "force_scan": False})
        assert mock_handler._send_json.call_args[0][0]["status"] == "success"

        post_upgrade_policy(mock_handler, {"auto_install_os_patches": True})
        assert mock_handler._send_json.call_args[0][0]["status"] == "success"

        # 4. MCP Tools
        out_status = json.loads(fleet_manage_os_and_software_upgrades(action="check"))
        assert out_status["status"] == "success"
        out_auto = json.loads(fleet_manage_os_and_software_upgrades(action="auto_manage"))
        assert out_auto["status"] == "success"
        out_pol = json.loads(fleet_manage_os_and_software_upgrades(action="get_policy"))
        assert out_pol["status"] == "success"
        out_set = json.loads(fleet_manage_os_and_software_upgrades(action="set_policy", auto_install_all_software=False))
        assert out_set["status"] == "success"
        out_audit = json.loads(fleet_optimize_and_audit(action="check_upgrades"))
        assert out_audit["status"] == "success"


