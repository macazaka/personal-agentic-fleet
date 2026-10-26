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
    import ctypes
    if hasattr(ctypes, "windll"):
        with patch("ctypes.windll.kernel32.GlobalMemoryStatusEx", side_effect=Exception("ctypes failed")):
            mem = get_memory_status()
            assert mem["total_gb"] == 16.0
            assert mem["percent_used"] == 50
    else:
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

    # Exception path
    with patch("winreg.OpenKey", side_effect=FileNotFoundError("Key missing")):
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
            assert len(apps) == 2
            app_names = [a["name"] for a in apps]
            assert "teams" in app_names
            assert "updater" in app_names
            assert apps[0]["scope"] == "User"
