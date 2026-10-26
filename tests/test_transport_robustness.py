"""
Unit tests for Transport Robustness: Circuit Breaker, Rate Limiter, and Offline Spooling.
"""

import time
import pytest

from fleet.core.http_client import CircuitBreaker, CircuitBreakerOpenException, ResilientHttpClient
from fleet.core.rate_limiter import TokenBucket, RateLimiter
from fleet.core.network_spool import spool_offline_event, list_spooled_events, flush_offline_spool


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=0.2)

    # Initial state
    assert cb.state == "CLOSED"
    cb.before_request()

    # Failures
    cb.on_failure()
    cb.on_failure()
    assert cb.state == "CLOSED"

    # Trip to OPEN
    cb.on_failure()
    assert cb.state == "OPEN"

    # Must fast fail when OPEN
    with pytest.raises(CircuitBreakerOpenException):
        cb.before_request()

    # Wait for cooldown
    time.sleep(0.25)
    cb.before_request()
    assert cb.state == "HALF_OPEN"

    # Probe success resets to CLOSED
    cb.on_success()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


def test_token_bucket_rate_limiter():
    bucket = TokenBucket(rate=10.0, capacity=5.0)

    # Burst 5 tokens
    for _ in range(5):
        allowed, _ = bucket.consume(1.0)
        assert allowed is True

    # 6th token should be blocked
    allowed, retry_after = bucket.consume(1.0)
    assert allowed is False
    assert retry_after > 0.0

    # Wait 0.15s to replenish ~1.5 tokens
    time.sleep(0.15)
    allowed, _ = bucket.consume(1.0)
    assert allowed is True


from unittest.mock import patch


def test_offline_spooling():
    # Spool event
    spool_id = spool_offline_event(
        target="email",
        action="SYNC_EMAILS",
        payload={"force": True}
    )
    assert spool_id > 0

    pending = list_spooled_events(status="pending")
    assert any(e["id"] == spool_id for e in pending)

    class MockEventBus:
        def dispatch(self, event):
            return {"status": "success"}

    # 1. When network is unavailable: flush skips
    with patch("fleet.core.network_spool.is_network_available", return_value=False):
        res_offline = flush_offline_spool(MockEventBus())
        assert res_offline["status"] == "skipped"

    # 2. When network is restored: flush executes
    with patch("fleet.core.network_spool.is_network_available", return_value=True):
        res_online = flush_offline_spool(MockEventBus())
        assert res_online["status"] == "success"
        assert res_online["flushed_count"] >= 1
