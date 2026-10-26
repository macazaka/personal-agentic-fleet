"""
Unit tests for Pillar 3: Agent Sandbox Hardening & Resource Containment.
Tests OS Job Objects / POSIX Quota (ROB-05) and Socket-Level Egress Guard (ROB-10).
"""

import socket
import pytest
from unittest.mock import MagicMock, patch

from fleet.core.sandbox_quota import (
    ProcessQuotaManager,
    enforce_agent_egress,
    get_process_memory_mb,
)


def test_process_quota_manager():
    manager = ProcessQuotaManager(memory_limit_mb=500)
    assert manager.memory_limit_mb == 500
    assert manager.memory_limit_bytes == 500 * 1024 * 1024

    # Apply to current process
    applied = manager.apply_to_current_process()
    assert isinstance(applied, bool)

    # Check memory footprint query
    mem_mb = get_process_memory_mb()
    assert isinstance(mem_mb, float)
    assert mem_mb >= 0.0


def test_socket_egress_enforcement():
    # 1. Agent WITHOUT network capability: external connect is blocked with PermissionError
    with enforce_agent_egress("RestrictedAgent", ["db:read", "ui:render"]):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(PermissionError) as exc_info:
            s.connect(("93.184.216.34", 80))
        assert "does not possess declared 'network:outbound' capability" in str(exc_info.value)
        s.close()

    # 2. Agent WITH network capability: passes egress check
    with patch("socket.socket.connect", return_value=None) as mock_conn:
        with enforce_agent_egress("NetworkAgent", ["network:outbound"]):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("93.184.216.34", 80))
            assert mock_conn.called
            s.close()
