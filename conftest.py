"""
Root pytest configuration and safety fixtures for Personal Agentic Fleet.
Enforces Fleet Rule 1 (Tier 0: 0 Tokens / $0.00) across all unit tests and coverage runs.
Guarantees zero token consumption and blocks external network socket connections.
"""

import os
import socket
import pytest

# Enforce Test Mode and Headless Drivers before any test modules load
os.environ["FLEET_TEST_MODE"] = "1"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


@pytest.fixture(autouse=True)
def guard_zero_tokens_and_network(monkeypatch):
    """
    Autouse fixture that prevents all tests from making outbound external socket connections
    or accidentally consuming LLM tokens.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        # Allow loopback / localhost / UNIX sockets for local IPC / mocks if needed
        if getattr(self, "family", None) == getattr(socket, "AF_UNIX", -1) or isinstance(address, str):
            return orig_connect(self, address)
        host = address[0] if isinstance(address, (tuple, list)) else address
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)
        raise RuntimeError(
            f"Blocked external network connection to {address} during tests. "
            "Fleet Rule 1 strictly mandates Tier 0 deterministic testing (0 Tokens / $0.00)."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


import sys
import types

# Cross-platform shims for CI test runner (ensures 100% pass rate on Linux/Ubuntu and Windows)
if sys.platform != "win32":
    if "winreg" not in sys.modules:
        dummy_winreg = types.ModuleType("winreg")
        dummy_winreg.HKEY_CURRENT_USER = 1
        dummy_winreg.HKEY_LOCAL_MACHINE = 2
        dummy_winreg.OpenKey = lambda *args, **kwargs: None
        dummy_winreg.QueryInfoKey = lambda *args, **kwargs: (0, 0, 0)
        dummy_winreg.EnumValue = lambda *args, **kwargs: ("app", "cmd", 0)
        dummy_winreg.CloseKey = lambda *args, **kwargs: None
        sys.modules["winreg"] = dummy_winreg

    import ctypes
    if not hasattr(ctypes, "windll"):
        class DummyWindll:
            kernel32 = types.SimpleNamespace(GlobalMemoryStatusEx=lambda *args, **kwargs: False)
            psapi = types.SimpleNamespace(EmptyWorkingSet=lambda *args, **kwargs: False)
        ctypes.windll = DummyWindll()
