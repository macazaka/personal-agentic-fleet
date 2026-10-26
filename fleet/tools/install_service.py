"""
Workstation Service Daemonization Installer for Personal Agentic Fleet.
Configures background service autostart across Windows (Task Scheduler), macOS (LaunchAgents), and Linux (systemd).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Windows Task Scheduler Implementation
# ---------------------------------------------------------------------------
def install_windows_task() -> Dict[str, Any]:
    repo = get_repo_root()
    vbs_path = repo / "start_control_center.vbs"
    task_name = "PersonalAgenticFleet"

    if not vbs_path.is_file():
        return {"status": "error", "message": f"Launcher '{vbs_path}' not found."}

    cmd = [
        "schtasks.exe", "/Create",
        "/TN", task_name,
        "/TR", f"wscript.exe \"{vbs_path}\"",
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/F"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        return {"status": "success", "message": f"Registered Windows Scheduled Task '{task_name}' on user logon."}
    return {"status": "error", "message": res.stderr.strip() or res.stdout.strip()}


def uninstall_windows_task() -> Dict[str, Any]:
    task_name = "PersonalAgenticFleet"
    cmd = ["schtasks.exe", "/Delete", "/TN", task_name, "/F"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        return {"status": "success", "message": f"Deleted Windows Scheduled Task '{task_name}'."}
    return {"status": "warn", "message": res.stderr.strip() or res.stdout.strip()}


# ---------------------------------------------------------------------------
# macOS LaunchAgent Implementation
# ---------------------------------------------------------------------------
def install_macos_launchagent() -> Dict[str, Any]:
    repo = get_repo_root()
    agent_id = "com.fleet.agentic"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_file = plist_dir / f"{agent_id}.plist"

    python_bin = sys.executable
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{agent_id}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>-m</string>
        <string>fleet.app</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{repo}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{repo}/fleet/data/fleet_app.log</string>
    <key>StandardErrorPath</key>
    <string>{repo}/fleet/data/fleet_app.log</string>
</dict>
</plist>
"""
    plist_file.write_text(plist_content, encoding="utf-8")

    # Load via launchctl
    subprocess.run(["launchctl", "unload", str(plist_file)], capture_output=True, check=False)
    res = subprocess.run(["launchctl", "load", str(plist_file)], capture_output=True, text=True, check=False)

    return {
        "status": "success" if res.returncode == 0 else "warn",
        "plist_path": str(plist_file),
        "message": f"Installed macOS LaunchAgent at '{plist_file}'."
    }


def uninstall_macos_launchagent() -> Dict[str, Any]:
    agent_id = "com.fleet.agentic"
    plist_file = Path.home() / "Library" / "LaunchAgents" / f"{agent_id}.plist"
    if plist_file.is_file():
        subprocess.run(["launchctl", "unload", str(plist_file)], capture_output=True, check=False)
        plist_file.unlink()
        return {"status": "success", "message": f"Uninstalled LaunchAgent '{agent_id}'."}
    return {"status": "warn", "message": "LaunchAgent plist file not found."}


# ---------------------------------------------------------------------------
# Linux systemd User Service Implementation
# ---------------------------------------------------------------------------
def install_linux_systemd() -> Dict[str, Any]:
    repo = get_repo_root()
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / "fleet.service"

    python_bin = sys.executable
    service_content = f"""[Unit]
Description=Personal Agentic Fleet Microkernel Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory={repo}
ExecStart={python_bin} -m fleet.app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=FLEET_HOST=0.0.0.0

[Install]
WantedBy=default.target
"""
    service_file.write_text(service_content, encoding="utf-8")

    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, check=False)
    res = subprocess.run(["systemctl", "--user", "enable", "--now", "fleet.service"], capture_output=True, text=True, check=False)

    return {
        "status": "success" if res.returncode == 0 else "warn",
        "service_path": str(service_file),
        "message": "Installed and started systemd user service 'fleet.service'."
    }


def uninstall_linux_systemd() -> Dict[str, Any]:
    subprocess.run(["systemctl", "--user", "stop", "fleet.service"], capture_output=True, check=False)
    subprocess.run(["systemctl", "--user", "disable", "fleet.service"], capture_output=True, check=False)
    service_file = Path.home() / ".config" / "systemd" / "user" / "fleet.service"
    if service_file.is_file():
        service_file.unlink()
    return {"status": "success", "message": "Disabled and removed systemd user service."}


def install_service() -> Dict[str, Any]:
    if sys.platform == "win32":
        return install_windows_task()
    elif sys.platform == "darwin":
        return install_macos_launchagent()
    else:
        return install_linux_systemd()


def uninstall_service() -> Dict[str, Any]:
    if sys.platform == "win32":
        return uninstall_windows_task()
    elif sys.platform == "darwin":
        return uninstall_macos_launchagent()
    else:
        return uninstall_linux_systemd()


def main():
    parser = argparse.ArgumentParser(description="Fleet Workstation Service Daemonization Installer")
    parser.add_argument("--install", action="store_true", help="Install and enable autostart service on current OS")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall and disable autostart service")
    args = parser.parse_args()

    if args.uninstall:
        res = uninstall_service()
        print(f"[{res['status'].upper()}] {res['message']}")
    else:
        res = install_service()
        print(f"[{res['status'].upper()}] {res['message']}")


if __name__ == "__main__":
    main()
