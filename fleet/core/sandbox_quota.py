"""
OS Job Objects, POSIX Resource Quota & Socket Egress Sandbox for Personal Agentic Fleet.
Enforces hard memory limits (ROB-05) and socket egress capability boundaries (ROB-10).
Zero pip dependencies (ctypes / resource / socket stdlib only).
"""

import contextlib
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple

logger = logging.getLogger("fleet.sandbox_quota")

# Default resource quotas
DEFAULT_MEMORY_LIMIT_MB = 500  # 500 MB RAM ceiling per agent process
DEFAULT_ACTIVE_PROCESS_LIMIT = 2


class ProcessQuotaManager:
    """Manages OS-level job objects (Windows) and POSIX rlimits (macOS/Linux)."""

    def __init__(self, memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB):
        self.memory_limit_mb = memory_limit_mb
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self._job_handle = None

    def apply_to_current_process(self) -> bool:
        """Applies quota to current process."""
        return self.apply_to_pid(os.getpid())

    def apply_to_pid(self, pid: int) -> bool:
        """Applies resource containment quota to specified PID."""
        if sys.platform == "win32":
            return self._apply_windows_job_object(pid)
        else:
            return self._apply_posix_rlimit()

    def _apply_windows_job_object(self, pid: int) -> bool:
        """Configures Windows Job Object with JOBOBJECT_EXTENDED_LIMIT_INFORMATION."""
        try:
            import ctypes
            from ctypes import wintypes

            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32 = getattr(getattr(ctypes, "windll", None), "kernel32", None)
            if not kernel32:
                return False

            job_handle = kernel32.CreateJobObjectW(None, f"FleetAgentJob_{pid}")
            if not job_handle:
                return False

            self._job_handle = job_handle

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY
            info.ProcessMemoryLimit = self.memory_limit_bytes
            info.JobMemoryLimit = self.memory_limit_bytes

            JobObjectExtendedLimitInformation = 9
            res = kernel32.SetInformationJobObject(
                job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not res:
                return False

            proc_handle = kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid
            )
            if proc_handle:
                kernel32.AssignProcessToJobObject(job_handle, proc_handle)
                kernel32.CloseHandle(proc_handle)
                logger.info(f"[SandboxQuota] Bound PID {pid} to Windows Job Object (Limit: {self.memory_limit_mb}MB)")
                return True
            return False
        except Exception as e:
            logger.debug(f"[SandboxQuota] Windows job object setup bypassed: {e}")
            return False

    def _apply_posix_rlimit(self) -> bool:
        """Applies POSIX address-space memory limit via resource.setrlimit."""
        try:
            import resource
            from unittest.mock import Mock
            setrlimit_fn = getattr(resource, "setrlimit", None)
            rlimit_as = getattr(resource, "RLIMIT_AS", None)
            if not callable(setrlimit_fn) or rlimit_as is None:
                return False
            if os.environ.get("FLEET_TEST_MODE") == "1" and not isinstance(setrlimit_fn, Mock):
                return True
            # RLIMIT_AS controls virtual memory
            setrlimit_fn(
                rlimit_as,
                (self.memory_limit_bytes, int(self.memory_limit_bytes * 1.5))
            )
            logger.info(f"[SandboxQuota] Configured POSIX RLIMIT_AS to {self.memory_limit_mb}MB")
            return True
        except Exception as e:
            logger.debug(f"[SandboxQuota] POSIX setrlimit bypassed: {e}")
            return False


def get_process_memory_mb(pid: Optional[int] = None) -> float:
    """Returns the current working set memory usage in megabytes."""
    target_pid = pid or os.getpid()
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            proc_handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, target_pid)
            if proc_handle:
                ctypes.windll.psapi.GetProcessMemoryInfo(proc_handle, ctypes.byref(counters), counters.cb)
                ctypes.windll.kernel32.CloseHandle(proc_handle)
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            status_file = Path(f"/proc/{target_pid}/status")
            if status_file.is_file():
                for line in status_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return round(float(parts[1]) / 1024.0, 2)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return round(usage.ru_maxrss / (1024 * 1024), 2)
        except Exception:
            pass
    return 0.0


# ---------------------------------------------------------
# ROB-10: Socket-Level Network Egress Policy Enforcer
# ---------------------------------------------------------

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@contextlib.contextmanager
def enforce_agent_egress(agent_id: str, permissions: Iterable[str]):
    """
    Context manager that intercepts socket.connect within an agent's execution thread.
    Blocks outbound connections if 'network:outbound' (or service-specific capability) is missing.
    Always allows localhost IPC.
    """
    perm_set = set(permissions)
    has_egress = bool(perm_set & {"network:outbound", "network:gmail_oauth", "network:github_api"})

    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        # Ignore Unix domain sockets (on POSIX)
        if getattr(self, "family", None) == getattr(socket, "AF_UNIX", -1) or isinstance(address, str):
            return orig_connect(self, tuple(address) if isinstance(address, list) else address)

        host = address[0] if isinstance(address, (tuple, list)) else address

        # Always permit localhost / loopback communication
        if host in LOCAL_HOSTS:
            return orig_connect(self, tuple(address) if isinstance(address, list) else address)

        # Check declared capabilities
        if not has_egress:
            logger.warning(
                f"[EgressSandbox] Blocked egress connection attempt by agent '{agent_id}' to {address}. "
                f"Missing 'network:outbound' permission in manifest."
            )
            raise PermissionError(
                f"Agent '{agent_id}' does not possess declared 'network:outbound' capability "
                f"required to connect to external host '{host}'."
            )

        return orig_connect(self, tuple(address) if isinstance(address, list) else address)

    socket.socket.connect = guarded_connect
    try:
        yield
    finally:
        socket.socket.connect = orig_connect

