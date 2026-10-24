"""
Root pytest configuration and safety fixtures for Personal Agentic Fleet.
Enforces Fleet Rule 1 (Tier 0: 0 Tokens / $0.00) across all unit tests and coverage runs.
Guarantees zero token consumption and blocks external network socket connections.
"""

import os
import socket
import sys
import types
import pytest

# Enforce Test Mode and Headless Drivers before any test modules load
os.environ["FLEET_TEST_MODE"] = "1"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


# Cross-platform shims for CI test runner (ensures 100% pass rate on Linux/Ubuntu and Windows)
if sys.platform != "win32":
    if "winreg" not in sys.modules:
        dummy_winreg = types.ModuleType("winreg")
        dummy_winreg.HKEY_CLASSES_ROOT = 0
        dummy_winreg.HKEY_CURRENT_USER = 1
        dummy_winreg.HKEY_LOCAL_MACHINE = 2
        dummy_winreg.HKEY_USERS = 3
        dummy_winreg.HKEY_CURRENT_CONFIG = 4
        class DummyKey:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        dummy_winreg.OpenKey = lambda *args, **kwargs: DummyKey()
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


# Zero-dependency Google OAuth hierarchy shims for CI runner when vendor packages are absent
google = sys.modules.setdefault("google", types.ModuleType("google"))
google_auth = sys.modules.setdefault("google.auth", types.ModuleType("google.auth"))
setattr(google, "auth", google_auth)

google_transport = sys.modules.setdefault("google.auth.transport", types.ModuleType("google.auth.transport"))
setattr(google_auth, "transport", google_transport)

google_requests = sys.modules.setdefault("google.auth.transport.requests", types.ModuleType("google.auth.transport.requests"))
setattr(google_transport, "requests", google_requests)
if not hasattr(google_requests, "Request"):
    setattr(google_requests, "Request", type("Request", (), {}))

google_oauth2 = sys.modules.setdefault("google.oauth2", types.ModuleType("google.oauth2"))
setattr(google, "oauth2", google_oauth2)

google_creds = sys.modules.setdefault("google.oauth2.credentials", types.ModuleType("google.oauth2.credentials"))
setattr(google_oauth2, "credentials", google_creds)
if not hasattr(google_creds, "Credentials"):
    setattr(google_creds, "Credentials", type("Credentials", (), {"from_authorized_user_file": lambda *a, **k: None}))

google_oauthlib = sys.modules.setdefault("google_auth_oauthlib", types.ModuleType("google_auth_oauthlib"))
flow_mod = sys.modules.setdefault("google_auth_oauthlib.flow", types.ModuleType("google_auth_oauthlib.flow"))
setattr(google_oauthlib, "flow", flow_mod)
if not hasattr(flow_mod, "InstalledAppFlow"):
    setattr(flow_mod, "InstalledAppFlow", type("InstalledAppFlow", (), {"from_client_secrets_file": lambda *a, **k: None}))

googleapiclient = sys.modules.setdefault("googleapiclient", types.ModuleType("googleapiclient"))
discovery_mod = sys.modules.setdefault("googleapiclient.discovery", types.ModuleType("googleapiclient.discovery"))
setattr(googleapiclient, "discovery", discovery_mod)
if not hasattr(discovery_mod, "build"):
    setattr(discovery_mod, "build", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def guard_zero_tokens_and_network(monkeypatch):
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
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
