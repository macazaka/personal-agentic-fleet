"""
Pytest configuration for Personal Agentic Fleet.
Enforces strict test isolation:
- Sets FLEET_TEST_MODE = "1"
- Sets headless SDL drivers
- Initializes clean test database (fleet_test_memory.db)
- Ensures the production database (fleet_memory.db) is never written to during tests.
"""
import os
import sys
import types
from pathlib import Path
import pytest

from fleet.config import DATA_DIR, TEST_DB_PATH

os.environ["FLEET_TEST_MODE"] = "1"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

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

# Zero-dependency Google OAuth shims for CI runner when optional vendor SDKs are absent
for mod_name in [
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "googleapiclient",
    "googleapiclient.discovery",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

if not hasattr(sys.modules["google.auth.transport.requests"], "Request"):
    sys.modules["google.auth.transport.requests"].Request = type("Request", (), {})
if not hasattr(sys.modules["google.oauth2.credentials"], "Credentials"):
    sys.modules["google.oauth2.credentials"].Credentials = type(
        "Credentials",
        (),
        {"from_authorized_user_file": lambda *a, **k: None}
    )
if not hasattr(sys.modules["google_auth_oauthlib.flow"], "InstalledAppFlow"):
    sys.modules["google_auth_oauthlib.flow"].InstalledAppFlow = type(
        "InstalledAppFlow",
        (),
        {"from_client_secrets_file": lambda *a, **k: None}
    )
if not hasattr(sys.modules["googleapiclient.discovery"], "build"):
    sys.modules["googleapiclient.discovery"].build = lambda *a, **k: None


@pytest.fixture(autouse=True, scope="session")
def isolate_test_session():
    """Session-level isolation ensuring production database is protected."""
    # Ensure test database starts clean
    for ext in ("", "-shm", "-wal"):
        p = Path(str(TEST_DB_PATH) + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    yield

    # Teardown test database files
    for ext in ("", "-shm", "-wal"):
        p = Path(str(TEST_DB_PATH) + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

