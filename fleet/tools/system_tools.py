"""
System and OS integration tools for Windows.
Includes native notifications, disk health, directory scanning, and safe file organization.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from fleet.config import ENABLE_WINDOWS_NOTIFICATIONS


FILE_CATEGORIES = {
    "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".csv", ".epub", ".md"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"],
    "Installers": [".exe", ".msi", ".iso"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Audio": [".mp3", ".wav", ".flac", ".m4a", ".aac"],
    "Video": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql"]
}


def send_windows_notification(title: str, message: str) -> bool:
    """Send a native Windows Toast notification without external pip packages."""
    if not ENABLE_WINDOWS_NOTIFICATIONS:
        return False
    try:
        # PowerShell script to show a native Windows toast notification
        # Escaping quotes safely
        safe_title = title.replace('"', '`"')
        safe_msg = message.replace('"', '`"')
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{safe_title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{safe_msg}")) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Personal Agentic Fleet")
        $notifier.Show($toast)
        """
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script],
                       capture_output=True, timeout=5, check=False)
        return True
    except Exception:
        # Fallback print if notification subsystem is unavailable
        return False


def get_disk_usage(path: str = "C:") -> Dict[str, Any]:
    """Get total, used, and free disk space in GB."""
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            "path": path,
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception as e:
        return {"error": str(e)}


def scan_directory(dir_path: str) -> Dict[str, Any]:
    """Scan a folder and categorize files by type, count, and size."""
    target = Path(dir_path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        return {"error": f"Path '{dir_path}' does not exist or is not a directory"}

    category_counts = {cat: 0 for cat in FILE_CATEGORIES}
    category_counts["Other"] = 0
    total_size = 0
    total_files = 0

    for item in target.iterdir():
        if item.is_file():
            total_files += 1
            size = item.stat().st_size
            total_size += size
            ext = item.suffix.lower()

            matched = False
            for cat, extensions in FILE_CATEGORIES.items():
                if ext in extensions:
                    category_counts[cat] += 1
                    matched = True
                    break
            if not matched:
                category_counts["Other"] += 1

    return {
        "directory": str(target),
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "categories": {k: v for k, v in category_counts.items() if v > 0}
    }


def find_large_files(dir_path: str, min_size_mb: float = 100.0, limit: int = 15) -> List[Dict[str, Any]]:
    """Locate large files in a folder to help reclaim disk space."""
    target = Path(dir_path).expanduser().resolve()
    if not target.exists():
        return []

    large_files = []
    min_bytes = int(min_size_mb * 1024 * 1024)

    try:
        for root, _, files in os.walk(target):
            for f in files:
                file_path = Path(root) / f
                try:
                    size = file_path.stat().st_size
                    if size >= min_bytes:
                        large_files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "size_mb": round(size / (1024 * 1024), 2)
                        })
                except (PermissionError, FileNotFoundError):
                    continue
    except Exception:
        pass

    large_files.sort(key=lambda x: x["size_mb"], reverse=True)
    return large_files[:limit]


def organize_directory(dir_path: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Organize loose files in a folder into subdirectories based on their categories.
    If dry_run is True, returns a preview without moving files.
    """
    target = Path(dir_path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        return {"error": f"Path '{dir_path}' does not exist"}

    moves = []
    for item in target.iterdir():
        if item.is_file():
            ext = item.suffix.lower()
            dest_category = "Other"
            for cat, extensions in FILE_CATEGORIES.items():
                if ext in extensions:
                    dest_category = cat
                    break

            dest_folder = target / dest_category
            dest_file = dest_folder / item.name

            moves.append({
                "file": item.name,
                "category": dest_category,
                "destination": str(dest_file)
            })

            if not dry_run:
                dest_folder.mkdir(exist_ok=True)
                # Handle filename collisions
                final_dest = dest_file
                counter = 1
                while final_dest.exists():
                    final_dest = dest_folder / f"{item.stem}_{counter}{item.suffix}"
                    counter += 1
                shutil.move(str(item), str(final_dest))

    return {
        "directory": str(target),
        "dry_run": dry_run,
        "files_count": len(moves),
        "actions": moves[:30],  # sample up to 30 actions
        "status": "Preview only (run with dry_run=False to apply)" if dry_run else "Successfully organized"
    }
