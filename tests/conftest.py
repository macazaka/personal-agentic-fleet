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
from pathlib import Path
import pytest

from fleet.config import DATA_DIR, TEST_DB_PATH

os.environ["FLEET_TEST_MODE"] = "1"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


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

