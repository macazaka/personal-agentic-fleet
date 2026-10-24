"""
Localhost Session Cookie, CSRF & DNS-Rebinding Guard for Personal Agentic Fleet.
Protects http://127.0.0.1:7890 against:
  1. DNS-Rebinding attacks (validates Host header is strictly localhost / 127.0.0.1)
  2. Cross-Site Request Forgery (CSRF) via browser Fetch Metadata (Sec-Fetch-Site) & Origin headers
  3. Provides an ephemeral HttpOnly, SameSite=Strict session token for local browser sessions.
"""

import secrets
from typing import Any, Dict, Set, Tuple

SESSION_COOKIE_NAME = "fleet_session"
SESSION_TOKEN = secrets.token_urlsafe(32)

ALLOWED_HOSTS = {
    "127.0.0.1",
    "localhost",
    "127.0.0.1:7890",
    "localhost:7890",
}


def get_session_cookie_header() -> str:
    """Returns the Set-Cookie header value for local dashboard browser sessions."""
    return f"{SESSION_COOKIE_NAME}={SESSION_TOKEN}; HttpOnly; SameSite=Strict; Path=/"


def validate_request_security(
    headers: Any,
    method: str,
    allowed_origins: Set[str],
) -> Tuple[bool, str]:
    """
    Validates an incoming HTTP request against DNS Rebinding and Cross-Site Request Forgery (CSRF).
    Returns (is_valid, reason).
    """
    if not headers:
        return True, "ok"

    # 1. DNS Rebinding Guard: If Host header is present, ensure it is strictly loopback
    host = (headers.get("Host") or "").strip().lower()
    if host:
        host_only = host.split(":")[0]
        if host_only not in ("127.0.0.1", "localhost", "[::1]"):
            return False, f"DNS Rebinding blocked: untrusted Host header '{host}'"

    # 2. Cross-Origin & Fetch Metadata Guard on state-mutating requests (POST, PUT, DELETE)
    if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
        origin = (headers.get("Origin") or "").strip()
        if origin and origin not in allowed_origins:
            return False, f"Cross-Origin POST blocked from untrusted Origin '{origin}'"

        sec_fetch_site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
        if sec_fetch_site == "cross-site":
            return False, "Cross-Site request blocked by Fetch Metadata policy (Sec-Fetch-Site: cross-site)"

    return True, "ok"

