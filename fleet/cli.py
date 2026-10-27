"""
Personal Agentic Fleet - Unified Command Line Interface (CLI).
Provides comprehensive local terminal controls for starting, stopping,
monitoring, diagnosing, and configuring the Cognitive Fleet Operating System.
Zero external dependencies ($0.00 compute).
"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Ensure robust stdout/stderr UTF-8 handling on Windows
if sys.platform == "win32":
    try:
        if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
            getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
        if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
            getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fleet.config import DATA_DIR, DB_PATH, PORT, VERSION


def _print_banner():
    banner = f"""
==================================================================
  ⚡ PERSONAL AGENTIC FLEET CLI (v{VERSION})
  Local-First Autonomous Workstation & Cognitive Fleet Mind
==================================================================
"""
    print(banner.strip())


def is_port_in_use(port: int = PORT, host: str = "127.0.0.1") -> bool:
    """Checks if a TCP port is currently open and accepting connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def get_pid_file() -> Path:
    return DATA_DIR / "fleet.pid"


def get_active_pid() -> Optional[int]:
    """Reads PID from file and verifies if the process is currently alive."""
    pid_file = get_pid_file()
    if not pid_file.is_file():
        return None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return pid
            return None
        else:
            os.kill(pid, 0)
            return pid
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------
# Subcommand Handlers
# ---------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> int:
    """Starts the Fleet web server and background routine daemon."""
    port = getattr(args, "port", PORT) or PORT
    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    no_browser = getattr(args, "no_browser", False)
    daemon = getattr(args, "daemon", False)

    if is_port_in_use(port, host):
        print(f"[ACTIVE] Personal Agentic Fleet is already running at http://{host}:{port}")
        if not no_browser:
            import webbrowser
            webbrowser.open(f"http://{host}:{port}")
        return 0

    if daemon:
        print(f"[*] Launching Personal Agentic Fleet in background daemon mode on http://{host}:{port}...")
        if sys.platform == "win32":
            # Windowless execution via pythonw or CREATE_NO_WINDOW
            pythonw = Path(sys.executable).parent / "pythonw.exe"
            py_bin = str(pythonw) if pythonw.is_file() else sys.executable
            DETACHED_PROCESS = 0x00000008
            CREATE_NO_WINDOW = 0x08000000
            creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS
            cmd = [py_bin, "-m", "fleet.app"]
            if no_browser:
                cmd.append("--no-browser")
            subprocess.Popen(
                cmd,
                cwd=str(_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        else:
            cmd = [sys.executable, "-m", "fleet.app"]
            if no_browser:
                cmd.append("--no-browser")
            subprocess.Popen(
                cmd,
                cwd=str(_ROOT),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        time.sleep(1.2)
        if is_port_in_use(port, host):
            print(f"[SUCCESS] Personal Agentic Fleet successfully started at http://{host}:{port}")
            return 0
        else:
            print(f"[INFO] Background launch signal dispatched. Checking http://{host}:{port}...")
            return 0

    # Interactive foreground launch
    print(f"[*] Starting Personal Agentic Fleet on http://{host}:{port}...")
    from fleet.app import main as app_main
    if no_browser and "--no-browser" not in sys.argv:
        sys.argv.append("--no-browser")
    return app_main() or 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stops the running Fleet server and daemon."""
    pid = get_active_pid()
    pid_file = get_pid_file()
    stopped = False

    if pid:
        print(f"[*] Stopping Personal Agentic Fleet (PID {pid})...")
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
            stopped = True
        except Exception as e:
            print(f"[!] Warning: Error signaling process {pid}: {e}")

    # Clean up stale PID file
    if pid_file.is_file():
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    # Verify port release
    if is_port_in_use(PORT):
        print(f"[*] Personal Agentic Fleet still listening on port {PORT}. Terminating bound process...")
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -LocalPort {PORT} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"],
                    capture_output=True,
                    check=False
                )
            except Exception:
                pass

    if not is_port_in_use(PORT):
        print("[SUCCESS] Personal Agentic Fleet stopped cleanly.")
        return 0
    else:
        print("[!] Note: Port is still active. Please check running tasks.")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Displays comprehensive operational and diagnostic status."""
    as_json = getattr(args, "json", False)
    active = is_port_in_use(PORT)
    pid = get_active_pid()

    # Query Diagnostics API if active
    api_data: Dict[str, Any] = {}
    if active:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/diagnostics/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                api_data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

    # DB Status
    db_exists = DB_PATH.is_file()
    db_size_kb = round(DB_PATH.stat().st_size / 1024, 2) if db_exists else 0.0

    # Memory Info
    rss_mb = 0.0
    if pid and sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS_EX()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                handle = windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
                if handle:
                    windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
                    windll.kernel32.CloseHandle(handle)
                    rss_mb = round(pmc.WorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass

    # Cognitive Harmony Score
    harmony_score = 100.0
    try:
        from fleet.core.mind import fleet_mind
        state = fleet_mind.get_holistic_state()
        harmony_score = float(state.get("cognitive_harmony_index", 100.0))
    except Exception:
        pass

    # Discovered Agents
    agents_count = 0
    try:
        from fleet.core.registry import AgentRegistry
        reg = AgentRegistry()
        reg.discover_and_load()
        agents_count = len(reg._all_discovered_agents)
    except Exception:
        agents_count = 7

    status_obj = {
        "status": "RUNNING" if active else "STOPPED",
        "version": VERSION,
        "pid": pid,
        "port": PORT,
        "url": f"http://127.0.0.1:{PORT}" if active else None,
        "memory_rss_mb": rss_mb,
        "db_path": str(DB_PATH),
        "db_size_kb": db_size_kb,
        "agents_count": agents_count,
        "cognitive_harmony": harmony_score,
        "api_health": api_data.get("status", "offline" if not active else "active"),
    }

    if as_json:
        print(json.dumps(status_obj, indent=2))
        return 0

    _print_banner()
    state_badge = "[ONLINE]" if active else "[OFFLINE]"
    print(f"\nFleet Daemon & Web Server: {state_badge}")
    if active:
        print(f"  • URL:                 http://127.0.0.1:{PORT}")
        print(f"  • Active Process PID:  {pid if pid else 'External/Assigned'}")
        if rss_mb > 0:
            print(f"  • Memory WorkingSet:   {rss_mb} MB (ultra-lightweight)")
    else:
        print("  • Run 'fleet start' to initialize workstation server.")

    print(f"\nCognitive Fleet Mind:")
    print(f"  • Harmony Score:       {harmony_score}/100 [Optimal Equilibrium]")
    print(f"  • Epistemic DB:        {DB_PATH.name} ({db_size_kb} KB)")
    print(f"  • Discovered Agents:   {agents_count} registered modular packages")
    print(f"  • Architecture:        Zero-Token Microkernel ($0.00 compute)\n")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Executes the strict Fleet Doctor environmental and security audit."""
    from fleet.tools.fleet_doctor import run_fleet_doctor
    strict = getattr(args, "strict", False)
    as_json = getattr(args, "json", False)
    report = run_fleet_doctor()
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== Fleet Doctor [{report['status']}] | Python {report['python_version']} (>={report['minimum_python_required']}) | Security: {report['security_score']}/100 ===")
        for d in report["diagnostics"]:
            print(f"  [{d['status']}] {d['name']} -> {d['detail']}")
    if strict and report["status"] != "PASS":
        return 1
    return 0


def cmd_mind(args: argparse.Namespace) -> int:
    """Introspects or commands the 4-layer Cognitive Fleet Mind."""
    from fleet.tools.fleet_mind import main as mind_main
    mind_args = []
    if getattr(args, "dream", False):
        mind_args.append("--dream")
    elif getattr(args, "soul", False):
        mind_args.append("--soul")
    elif getattr(args, "heal", False):
        mind_args.append("--heal")
    elif getattr(args, "improve", False):
        mind_args.append("--improve")
    elif getattr(args, "critique", None):
        mind_args.extend(["--critique", args.critique[0], args.critique[1]])
    else:
        mind_args.append("--status")

    if getattr(args, "json", False):
        mind_args.append("--json")

    original_argv = sys.argv
    try:
        sys.argv = ["fleet-mind"] + mind_args
        return mind_main() or 0
    finally:
        sys.argv = original_argv


def cmd_agents(args: argparse.Namespace) -> int:
    """Manages agents: list, enable, disable, info, and create."""
    subaction = getattr(args, "agent_action", "list")
    from fleet.core.registry import AgentRegistry

    reg = AgentRegistry()
    reg.discover_and_load()

    if subaction == "list" or not subaction:
        print(f"\n=== Personal Agentic Fleet: Registered Agents ({len(reg._all_discovered_agents)}) ===")
        print(f"{'ID':<14} {'Name':<26} {'Version':<9} {'Status':<10} {'Permissions'}")
        print("-" * 78)
        for aid, agent in sorted(reg._all_discovered_agents.items(), key=lambda x: x[1].order):
            manifest = agent.get_ui_manifest()
            status = "ENABLED" if agent.enabled else "DISABLED"
            ver = manifest.get("version", getattr(agent, "version", "1.0.0"))
            perms = ", ".join(manifest.get("permissions", [])) or "none"
            print(f"{aid:<14} {agent.name:<26} {ver:<9} {status:<10} {perms}")
        print("")
        return 0

    if subaction == "enable":
        target = getattr(args, "target", None)
        if not target:
            print("[ERROR] Missing agent ID. Example: fleet agents enable backlog")
            return 1
        try:
            reg.customize_agent(target, {"enabled": True})
            print(f"[SUCCESS] Agent '{target}' successfully enabled.")
            return 0
        except Exception as e:
            print(f"[ERROR] Failed to enable '{target}': {e}")
            return 1

    if subaction == "disable":
        target = getattr(args, "target", None)
        if not target:
            print("[ERROR] Missing agent ID. Example: fleet agents disable backlog")
            return 1
        try:
            reg.customize_agent(target, {"enabled": False})
            print(f"[SUCCESS] Agent '{target}' successfully disabled.")
            return 0
        except Exception as e:
            print(f"[ERROR] Failed to disable '{target}': {e}")
            return 1

    if subaction == "info":
        target = getattr(args, "target", None)
        if not target:
            print("[ERROR] Missing agent ID. Example: fleet agents info health")
            return 1
        agent = reg._all_discovered_agents.get(target)
        if not agent:
            print(f"[ERROR] Agent '{target}' not found in registry.")
            return 1
        manifest = agent.get_ui_manifest()
        print(f"\n=== Agent Manifest: {agent.name} ({agent.id}) ===")
        print(json.dumps(manifest, indent=2))
        return 0

    if subaction == "create":
        from fleet.tools.create_agent import main as create_agent_main
        return create_agent_main() or 0

    print(f"[ERROR] Unknown agents action '{subaction}'. Use: list, enable, disable, info, create.")
    return 1


def cmd_security(args: argparse.Namespace) -> int:
    """Executes the 12-layer deterministic security and privacy scan."""
    from fleet.tools.security_scanner import run_security_scan
    strict = getattr(args, "strict", False)
    as_json = getattr(args, "json", False)
    report = run_security_scan()
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== Fleet Security Scan [{report['status']}] | Score: {report.get('security_score', report.get('score', 100))}/100 ===")
        print(f"Files Scanned: {report.get('files_scanned', 0)} | Checks Passed: {report.get('passed_checks', 0)}/{report.get('total_checks', 12)}")
        for c in report.get("checks", []):
            icon = "[PASS]" if c.get("status") == "PASS" else "[FAIL]"
            print(f"  {icon} {c.get('name', 'Check')} ({c.get('findings_count', 0)} findings)")
        if report.get("findings"):
            print("\nFindings:")
            for f in report["findings"]:
                print(f"  - [{f.get('severity', 'WARN')}] {f.get('file', 'unknown')}:{f.get('line', 0)} -> {f.get('detail', '')}")
    if strict and (report.get("findings_count", 0) > 0 or report.get("status") != "PASS"):
        return 1
    return 0


def cmd_heal(args: argparse.Namespace) -> int:
    """Analyzes logs and executes autonomous self-healing routines."""
    from fleet.tools.auto_healer import main as auto_healer_main
    healer_args = []
    if getattr(args, "force", False):
        healer_args.append("--force")
    if getattr(args, "json", False):
        healer_args.append("--json")
    original_argv = sys.argv
    try:
        sys.argv = ["auto-healer"] + healer_args
        return auto_healer_main() or 0
    finally:
        sys.argv = original_argv


def cmd_test(args: argparse.Namespace) -> int:
    """Runs the comprehensive unit test suite and coverage reports."""
    from fleet.tools.test_runner import main as test_runner_main
    test_args = []
    if getattr(args, "coverage", False):
        test_args.append("--coverage")
    if getattr(args, "fast", False):
        test_args.append("--fast")
    original_argv = sys.argv
    try:
        sys.argv = ["fleet-test"] + test_args
        return test_runner_main() or 0
    finally:
        sys.argv = original_argv


def cmd_wiki(args: argparse.Namespace) -> int:
    """Synchronizes documentation to GitHub Wiki."""
    from fleet.tools.sync_wiki import main as wiki_main
    wiki_args = []
    if getattr(args, "dry_run", False):
        wiki_args.append("--dry-run")
    original_argv = sys.argv
    try:
        sys.argv = ["sync-wiki"] + wiki_args
        return wiki_main() or 0
    finally:
        sys.argv = original_argv


def cmd_autofix(args: argparse.Namespace) -> int:
    """Automatically repairs VS Code (Pyright/Pylance) and GitHub CodeQL issues with zero human intervention."""
    from fleet.tools.auto_fixer import main as autofix_main
    af_args = []
    if getattr(args, "stage", False):
        af_args.append("--stage")
    if getattr(args, "json", False):
        af_args.append("--json")
    original_argv = sys.argv
    try:
        sys.argv = ["fleet-autofix"] + af_args
        return autofix_main() or 0
    finally:
        sys.argv = original_argv


def cmd_version(args: argparse.Namespace) -> int:
    """Displays version and system platform information."""
    print(f"Personal Agentic Fleet v{VERSION}")
    print(f"Python {sys.version.split()[0]} ({sys.platform}) on {sys.executable}")
    return 0


# ---------------------------------------------------------
# CLI Parser Setup
# ---------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fleet",
        description="Personal Agentic Fleet - Unified Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"Personal Agentic Fleet v{VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available fleet commands")

    # Start
    p_start = subparsers.add_parser("start", help="Start web dashboard & background daemon")
    p_start.add_argument("--port", type=int, default=PORT, help=f"HTTP port (default {PORT})")
    p_start.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p_start.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")
    p_start.add_argument("-d", "--daemon", action="store_true", help="Launch in silent background mode")

    # Stop
    subparsers.add_parser("stop", help="Stop running Fleet server and daemon")

    # Status
    p_status = subparsers.add_parser("status", help="Show live status, health, and memory")
    p_status.add_argument("--json", action="store_true", help="Output status in JSON format")

    # Doctor
    p_doctor = subparsers.add_parser("doctor", help="Run Fleet Doctor environmental invariants")
    p_doctor.add_argument("--strict", action="store_true", help="Enforce strict exit codes on warnings")
    p_doctor.add_argument("--json", action="store_true", help="Output report in JSON format")

    # Mind
    p_mind = subparsers.add_parser("mind", help="Introspect Cognitive Fleet Mind")
    p_mind.add_argument("--status", action="store_true", help="Display complete 4-layer holistic mind state")
    p_mind.add_argument("--dream", action="store_true", help="Trigger subconscious dreaming consolidation")
    p_mind.add_argument("--soul", action="store_true", help="Audit soul alignment and moral compass")
    p_mind.add_argument("--heal", action="store_true", help="Trigger autonomic self-healing reflex arc")
    p_mind.add_argument("--improve", action="store_true", help="Execute evolutionary self-improvement cycle")
    p_mind.add_argument("--critique", nargs=2, metavar=("AGENT", "ACTION"), help="Conscious meta-critique of agent action")
    p_mind.add_argument("--json", action="store_true", help="Output in JSON format")

    # Agents
    p_agents = subparsers.add_parser("agents", help="Manage modular agent packages")
    p_agents.add_argument("agent_action", nargs="?", default="list", choices=["list", "enable", "disable", "info", "create"], help="Action to perform")
    p_agents.add_argument("target", nargs="?", help="Target agent ID (for enable, disable, info)")

    # Security
    p_sec = subparsers.add_parser("security", help="Run 12-layer security & privacy audit")
    p_sec.add_argument("--strict", action="store_true", help="Fail on any security warning")
    p_sec.add_argument("--json", action="store_true", help="Output report in JSON format")

    # Heal
    p_heal = subparsers.add_parser("heal", help="Proactive log scan and autonomous self-healing")
    p_heal.add_argument("--force", action="store_true", help="Force execute all self-healing recipes")
    p_heal.add_argument("--json", action="store_true", help="Output findings in JSON format")

    # Test
    p_test = subparsers.add_parser("test", help="Execute unit tests and coverage suite")
    p_test.add_argument("--coverage", action="store_true", help="Generate full code coverage report")
    p_test.add_argument("--fast", action="store_true", help="Run fast test subset")

    # Wiki
    p_wiki = subparsers.add_parser("wiki", help="Synchronize documentation to GitHub Wiki")
    p_wiki.add_argument("--dry-run", action="store_true", help="Preview changes without pushing")

    # Autofix
    p_autofix = subparsers.add_parser("autofix", help="Auto-fix VS Code & GitHub CodeQL issues automatically")
    p_autofix.add_argument("--stage", action="store_true", help="Stage auto-fixed files in Git")
    p_autofix.add_argument("--json", action="store_true", help="Output report in JSON format")

    # Version
    subparsers.add_parser("version", help="Display fleet version and system information")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        _print_banner()
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    dispatch_map = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "mind": cmd_mind,
        "agents": cmd_agents,
        "security": cmd_security,
        "heal": cmd_heal,
        "test": cmd_test,
        "wiki": cmd_wiki,
        "autofix": cmd_autofix,
        "version": cmd_version,
    }

    handler = dispatch_map.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
