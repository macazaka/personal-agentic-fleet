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
        # Allow loopback / localhost for local IPC / mocks if needed
        host = address[0] if isinstance(address, (tuple, list)) else address
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)
        raise RuntimeError(
            f"Blocked external network connection to {address} during tests. "
            "Fleet Rule 1 strictly mandates Tier 0 deterministic testing (0 Tokens / $0.00)."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

