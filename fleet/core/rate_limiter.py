"""
Localhost Token-Bucket Rate Limiter & DoS Shield for Personal Agentic Fleet.
Protects web dashboard endpoints from excessive flooding via pure standard library.
"""

import threading
import time
from typing import Dict, Tuple


class TokenBucket:
    """Token bucket rate limiter bucket."""

    def __init__(self, rate: float = 60.0, capacity: float = 100.0):
        self.rate = float(rate)  # Tokens added per second
        self.capacity = float(capacity)  # Maximum burst capacity
        self.tokens = float(capacity)
        self.last_update = time.time()

    def consume(self, tokens: float = 1.0) -> Tuple[bool, float]:
        """
        Attempts to consume tokens.
        Returns: (allowed: bool, retry_after_sec: float)
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Replenish tokens
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0

        needed = tokens - self.tokens
        retry_after = needed / self.rate
        return False, retry_after


class RateLimiter:
    """Manages rate limit buckets per client key or endpoint."""

    def __init__(self, default_rate: float = 60.0, default_capacity: float = 100.0):
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str, tokens: float = 1.0) -> Tuple[bool, float]:
        """
        Checks whether request for key is allowed under rate limits.
        Returns: (allowed: bool, retry_after_sec: float)
        """
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rate=self.default_rate, capacity=self.default_capacity)

            # Cleanup if too many buckets
            if len(self._buckets) > 1000:
                now = time.time()
                self._buckets = {k: b for k, b in self._buckets.items() if now - b.last_update < 300}

            return self._buckets[key].consume(tokens=tokens)

    check_rate_limit = check


# Global singleton limiter (60 req/s, burst 100)
rate_limiter = RateLimiter(default_rate=60.0, default_capacity=100.0)
rate_limiter.check_rate_limit = rate_limiter.check
_SERVER_RATE_LIMITER = rate_limiter


def check_rate_limit(key: str) -> Tuple[bool, float]:
    """Helper to check rate limit for client IP or route."""
    return rate_limiter.check(key)
