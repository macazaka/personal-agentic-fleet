"""Unit tests for fleet.tools.system_tools."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import fleet.tools.system_tools as sys_tools


def test_send_windows_notification():
    # Success path
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert sys_tools.send_windows_notification("Title", "Message") is True

    # Disabled notification path
    with patch("fleet.tools.system_tools.ENABLE_WINDOWS_NOTIFICATIONS", False):
        assert sys_tools.send_windows_notification("Title", "Message") is False

    # Exception path
    with patch("subprocess.run", side_effect=Exception("Failed")):
        assert sys_tools.send_windows_notification("Title", "Message") is False


def test_get_disk_usage():
    target_drive = "C:" if os.name == "nt" else "/"
    usage = sys_tools.get_disk_usage(target_drive)
    assert "total_gb" in usage
    assert "free_gb" in usage
    assert "percent_used" in usage

    # Default None path
    default_usage = sys_tools.get_disk_usage()
    assert "total_gb" in default_usage

    # Invalid path / exception
    invalid_drive = "NON_EXISTENT_DRIVE_LETTER:\\" if os.name == "nt" else "/non_existent_folder_abc123"
    err_usage = sys_tools.get_disk_usage(invalid_drive)
    assert "error" in err_usage or "total_gb" in err_usage


def test_directory_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create test files
        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4" + b"0" * 1024)
        (tmp_path / "pic.png").write_bytes(b"\x89PNG" + b"0" * 2048)
        (tmp_path / "script.py").write_text("print('hello')", encoding="utf-8")
        (tmp_path / "unknown.xyz").write_bytes(b"data")

        # 1. Scan directory
        scan_res = sys_tools.scan_directory(str(tmp_path))
        assert scan_res["total_files"] == 4
        assert scan_res["categories"]["Documents"] == 1
        assert scan_res["categories"]["Images"] == 1
        assert scan_res["categories"]["Code"] == 1
        assert scan_res["categories"]["Other"] == 1

        # Non-existent scan
        bad_scan = sys_tools.scan_directory(str(tmp_path / "missing"))
        assert "error" in bad_scan

        # 2. Find large files
        large = sys_tools.find_large_files(str(tmp_path), min_size_mb=0.001, limit=5)
        assert len(large) >= 1
        bad_large = sys_tools.find_large_files(str(tmp_path / "missing"))
        assert bad_large == []

        # 3. Organize directory (dry run)
        org_dry = sys_tools.organize_directory(str(tmp_path), dry_run=True)
        assert org_dry["files_count"] == 4
        assert "Preview only" in org_dry["status"]
        assert (tmp_path / "doc.pdf").exists()

        # Organize directory (actual execution)
        org_act = sys_tools.organize_directory(str(tmp_path), dry_run=False)
        assert org_act["files_count"] == 4
        assert (tmp_path / "Documents" / "doc.pdf").exists()
        assert (tmp_path / "Images" / "pic.png").exists()

        # Non-existent organize
        bad_org = sys_tools.organize_directory(str(tmp_path / "missing"))
        assert "error" in bad_org

        # Organize directory with filename collision
        (tmp_path / "extra.pdf").write_bytes(b"%PDF-1.4 extra")
        # Pre-create Documents/extra.pdf so collision occurs
        (tmp_path / "Documents" / "extra.pdf").write_bytes(b"existing")
        org_collision = sys_tools.organize_directory(str(tmp_path), dry_run=False)
        assert (tmp_path / "Documents" / "extra_1.pdf").exists()


def test_find_large_files_permission_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "f1.txt").write_text("hello")
        orig_stat = Path.stat
        def mock_stat_locked(self, *args, **kwargs):
            if str(self).endswith(".txt") or "f1" in str(self):
                raise PermissionError("Locked")
            return orig_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", side_effect=mock_stat_locked):
            res = sys_tools.find_large_files(str(tmp_path), min_size_mb=0.0)
            assert res == []

        # Test exception on os.walk (lines 125-126)
        with patch("os.walk", side_effect=Exception("walk fail")):
            res_err = sys_tools.find_large_files(str(tmp_path), min_size_mb=0.0)
            assert res_err == []



