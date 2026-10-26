"""
Resilient HTTP Client with 3-State Circuit Breaker & Exponential Backoff for Personal Agentic Fleet.
Zero external dependencies; wraps urllib.request for multi-hyperscaler and external network calls.
"""

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


logger = logging.getLogger("fleet.http_client")


class CircuitBreakerOpenException(Exception):
    """Raised when request is fast-failed because the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    3-State Circuit Breaker:
      - CLOSED: Normal operation. Tracks consecutive failures.
      - OPEN: Trips after failure threshold. Fast-fails requests for cooldown period.
      - HALF_OPEN: Allows 1 probe request through. Resets to CLOSED on success, or back to OPEN on failure.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec

        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
        self.failure_count = 0
        self.last_failure_time = 0.0

    def before_request(self) -> None:
        """Evaluates whether request can proceed or must be fast-failed."""
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.recovery_timeout_sec:
                self.state = "HALF_OPEN"
                logger.info("[CircuitBreaker] Transitioned to HALF_OPEN (probing upstream).")
            else:
                remaining = self.recovery_timeout_sec - (now - self.last_failure_time)
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is OPEN. Upstream temporarily suspended ({remaining:.1f}s cooldown remaining)."
                )

    def on_success(self) -> None:
        """Notifies circuit breaker of successful response."""
        self.failure_count = 0
        if self.state != "CLOSED":
            logger.info("[CircuitBreaker] Upstream probe succeeded. Circuit reset to CLOSED.")
            self.state = "CLOSED"

    def on_failure(self) -> None:
        """Notifies circuit breaker of upstream failure or timeout."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state in ("CLOSED", "HALF_OPEN"):
            if self.failure_count >= self.failure_threshold or self.state == "HALF_OPEN":
                self.state = "OPEN"
                logger.warning(
                    f"[CircuitBreaker] Failure threshold ({self.failure_count}) reached. Circuit tripped to OPEN for {self.recovery_timeout_sec}s."
                )


class ResilientHttpClient:
    """
    Resilient HTTP Client with domain-level circuit breakers,
    automatic retries, and jittered exponential backoff.
    """

    def __init__(
        self,
        default_timeout: float = 15.0,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        max_backoff: float = 10.0,
    ):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, host: str) -> CircuitBreaker:
        if host not in self._circuit_breakers:
            self._circuit_breakers[host] = CircuitBreaker()
        return self._circuit_breakers[host]

    def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Tuple[int, bytes, Dict[str, str]]:
        """
        Executes an HTTP request with circuit-breaking and jittered backoff.
        Returns: (status_code, response_body_bytes, response_headers_dict)
        """
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc or "default"
        cb = self.get_circuit_breaker(host)

        req_timeout = timeout if timeout is not None else self.default_timeout
        max_attempts = (retries if retries is not None else self.max_retries) + 1

        headers = dict(headers or {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = "PersonalAgenticFleet/2.3.0 (Zero-Token Microkernel)"

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            cb.before_request()

            req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                    status = resp.status
                    body = resp.read()
                    resp_headers = dict(resp.headers)

                    cb.on_success()
                    return status, body, resp_headers

            except urllib.error.HTTPError as http_err:
                # Do not retry 4xx client errors (except 429 Rate Limit)
                if 400 <= http_err.code < 500 and http_err.code != 429:
                    cb.on_success()  # Client error, upstream itself is reachable
                    body = http_err.read()
                    return http_err.code, body, dict(http_err.headers)

                last_error = http_err
                cb.on_failure()

            except (urllib.error.URLError, TimeoutError, OSError) as net_err:
                last_error = net_err
                cb.on_failure()

            if attempt < max_attempts:
                # Truncated exponential backoff with full jitter
                backoff = min(self.max_backoff, self.base_backoff * (2 ** (attempt - 1)))
                delay = random.uniform(0.0, backoff)
                logger.debug(f"[ResilientHttp] Attempt {attempt}/{max_attempts} failed. Retrying in {delay:.2f}s...")
                time.sleep(delay)

        if last_error:
            raise last_error
        raise RuntimeError("Request failed with unknown error.")

    def request_json(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[int, Any]:
        """Convenience method returning parsed JSON payload."""
        req_headers = dict(headers or {})
        req_data = None

        if json_body is not None:
            req_headers["Content-Type"] = "application/json"
            req_data = json.dumps(json_body).encode("utf-8")

        status, body, _ = self.request(
            url=url,
            method=method,
            headers=req_headers,
            data=req_data,
            timeout=timeout
        )

        try:
            parsed_json = json.loads(body.decode("utf-8")) if body else None
        except Exception:
            parsed_json = body.decode("utf-8", errors="ignore")

        return status, parsed_json


# Global singleton client
_DEFAULT_CLIENT = ResilientHttpClient()


def get_resilient_http_client() -> ResilientHttpClient:
    """Returns singleton resilient HTTP client."""
    return _DEFAULT_CLIENT
