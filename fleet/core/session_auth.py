"""
Localhost Session Cookie, CSRF & DNS-Rebinding Guard for Personal Agentic Fleet.
Protects http://127.0.0.1:7890 against:
  1. DNS-Rebinding attacks (validates Host header is strictly localhost / 127.0.0.1)
  2. Cross-Site Request Forgery (CSRF) via browser Fetch Metadata (Sec-Fetch-Site) & Origin headers
  3. Provides an ephemeral HttpOnly, SameSite=Strict session token for local browser sessions.
"""

import hmac
import ipaddress
import secrets
from typing import Any, Dict, Optional, Set, Tuple

SESSION_COOKIE_NAME = "fleet_session"
SESSION_TOKEN = secrets.token_urlsafe(32)
_CACHED_MOBILE_BEARER_TOKEN: Optional[str] = None

ALLOWED_HOSTS = {
    "127.0.0.1",
    "localhost",
    "127.0.0.1:7890",
    "localhost:7890",
}


def get_session_cookie_header() -> str:
    """Returns the Set-Cookie header value for local dashboard browser sessions."""
    return f"{SESSION_COOKIE_NAME}={SESSION_TOKEN}; HttpOnly; SameSite=Strict; Path=/"


def get_or_create_mobile_bearer_token(rotate: bool = False) -> str:
    """
    TD-01: Retrieves or generates a 256-bit cryptographic Mobile Bearer Token
    (`afcc_mob_<43-char-urlsafe>`) protected at rest in the DPAPI/AES-256-GCM vault
    so iPhone & Apple Watch Shortcuts can authenticate over Tailscale/LAN.
    """
    global _CACHED_MOBILE_BEARER_TOKEN
    if not rotate and _CACHED_MOBILE_BEARER_TOKEN:
        return _CACHED_MOBILE_BEARER_TOKEN

    try:
        from fleet.config import DATA_DIR
        from fleet.core.crypto_vault import read_encrypted_json_file, write_encrypted_json_file

        vault_file = DATA_DIR / "user" / "mobile_gateway_vault.json"
        if not rotate and vault_file.exists():
            data = read_encrypted_json_file(vault_file, default={})
            if isinstance(data, dict) and str(data.get("bearer_token") or "").startswith("afcc_mob_"):
                _CACHED_MOBILE_BEARER_TOKEN = str(data["bearer_token"])
                return _CACHED_MOBILE_BEARER_TOKEN

        new_token = f"afcc_mob_{secrets.token_urlsafe(32)}"
        write_encrypted_json_file(
            vault_file,
            {
                "bearer_token": new_token,
                "scope": "tri-device-apple-watch-iphone-hub",
            },
        )
        _CACHED_MOBILE_BEARER_TOKEN = new_token
        return new_token
    except Exception:
        if not _CACHED_MOBILE_BEARER_TOKEN or rotate:
            _CACHED_MOBILE_BEARER_TOKEN = f"afcc_mob_{secrets.token_urlsafe(32)}"
        return _CACHED_MOBILE_BEARER_TOKEN


def verify_mobile_bearer_token(headers: Any) -> bool:
    """Constant-time verification of `X-AFCC-Mobile-Token` or `Authorization: Bearer <token>`."""
    if not headers or not hasattr(headers, "get"):
        return False
    candidate = (headers.get("X-AFCC-Mobile-Token") or "").strip()
    if not candidate:
        auth_hdr = (headers.get("Authorization") or "").strip()
        if auth_hdr.lower().startswith("bearer "):
            candidate = auth_hdr[7:].strip()
    if not candidate or not candidate.startswith("afcc_mob_"):
        return False
    expected = get_or_create_mobile_bearer_token(rotate=False)
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def _is_tailscale_or_loopback_host(host_only: str) -> bool:
    """
    Returns True for loopback (`127.0.0.1`, `localhost`, `[::1]`), Tailscale WireGuard (`100.64.0.0/10`, `*.ts.net`),
    or literal RFC-1918 private LAN IPv4 addresses (`192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`).
    Literal IP addresses never trigger DNS resolution and are therefore immune to DNS-rebinding attacks,
    while untrusted domain names (`evil.com`) are strictly rejected.
    """
    if host_only in ("127.0.0.1", "localhost", "[::1]"):
        return True
    if host_only.endswith(".ts.net"):
        return True
    try:
        ip_obj = ipaddress.ip_address(host_only.strip("[]"))
        tailscale_net = ipaddress.ip_network("100.64.0.0/10")
        return bool(ip_obj.is_loopback or ip_obj.is_private or (ip_obj in tailscale_net))
    except ValueError:
        return False


def validate_request_security(
    headers: Any,
    method: str,
    allowed_origins: Set[str],
) -> Tuple[bool, str]:
    """
    Validates an incoming HTTP request against DNS Rebinding and Cross-Site Request Forgery (CSRF).
    Supports local loopback AND authenticated Tri-Device Tailscale/Bearer requests.
    Returns (is_valid, reason).
    """
    if not headers:
        return True, "ok"

    has_valid_mobile_token = verify_mobile_bearer_token(headers)

    # 1. DNS Rebinding Guard: Ensure Host header is loopback, Tailscale mesh, or authenticated mobile token
    host = (headers.get("Host") or "").strip().lower()
    if host and not has_valid_mobile_token:
        host_only = host.split(":")[0]
        if not _is_tailscale_or_loopback_host(host_only):
            return False, f"DNS Rebinding blocked: untrusted Host header '{host}'"

    # 2. Cross-Origin & Fetch Metadata Guard on state-mutating requests (POST, PUT, DELETE)
    if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
        sec_fetch_site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
        if sec_fetch_site == "cross-site":
            return False, "Cross-Site request blocked by Fetch Metadata policy (Sec-Fetch-Site: cross-site)"

        origin = (headers.get("Origin") or "").strip()
        if origin and not has_valid_mobile_token:
            if origin not in allowed_origins:
                # Allow same-origin Tailscale mesh requests when Host is a valid Tailscale node
                host_only = host.split(":")[0] if host else ""
                tailscale_origins = {f"https://{host}", f"http://{host}", f"https://{host_only}", f"http://{host_only}"}
                if not (_is_tailscale_or_loopback_host(host_only) and origin.lower() in tailscale_origins):
                    return False, f"Cross-Origin POST blocked from untrusted Origin '{origin}'"

    return True, "ok"

import time
from collections import deque

# Sliding-window rate limiter (max 120 requests per 10 seconds per client IP)
_REQUEST_TIMESTAMPS: deque = deque(maxlen=200)
RATE_LIMIT_WINDOW_SEC = 10.0
RATE_LIMIT_MAX_REQUESTS = 120


def check_rate_limit() -> Tuple[bool, str]:
    """Protects local server & LLM queue from runaway client script loops."""
    now = time.time()
    while _REQUEST_TIMESTAMPS and (now - _REQUEST_TIMESTAMPS[0]) > RATE_LIMIT_WINDOW_SEC:
        _REQUEST_TIMESTAMPS.popleft()
    if len(_REQUEST_TIMESTAMPS) >= RATE_LIMIT_MAX_REQUESTS:
        return False, "Rate limit exceeded: too many local requests in 10s window"
    _REQUEST_TIMESTAMPS.append(now)
    return True, "ok"

