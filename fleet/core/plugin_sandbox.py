"""
Plugin Capability Sandboxing & Permission Enforcement for Personal Agentic Fleet.
Ensures third-party community agents declare explicit least-privilege permissions in manifest.json
and enforces capability boundaries at runtime:
  - ScopedDatabaseProxy blocks write/delete DB calls if agent lacks 'db:write'
  - get_sanitized_plugin_env() strips sensitive environment secrets before subprocess execution
"""

import os
from typing import Any, Dict, Iterable, List, Set

ALLOWED_AGENT_PERMISSIONS: Set[str] = {
    "db:read",
    "db:write",
    "event_bus:publish",
    "event_bus:subscribe",
    "filesystem:videos",
    "filesystem:temp",
    "network:gmail_oauth",
    "network:github_api",
    "system:diagnostics",
    "ui:render",
}

# Read-only prefixes on FleetDatabase methods
_READ_METHOD_PREFIXES = (
    "get_",
    "list_",
    "fetch_",
    "search_",
    "count_",
    "is_",
    "has_",
)

# Secret environment variable patterns stripped from untrusted plugin subprocesses
_SENSITIVE_ENV_KEYWORDS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "PAT",
    "PRIVATE",
)


def validate_manifest_permissions(agent_id: str, permissions: Iterable[str]) -> List[str]:
    """Validates that an agent's manifest permissions are recognized capabilities."""
    unknown = [p for p in permissions if p not in ALLOWED_AGENT_PERMISSIONS]
    return unknown


class ScopedDatabaseProxy:
    """Restricts an agent's access to FleetDatabase methods based on manifest permissions."""

    def __init__(self, raw_db: Any, agent_id: str, permissions: List[str]):
        self._raw_db = raw_db
        self._agent_id = agent_id
        self._permissions = set(permissions)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._raw_db, name)
        if not callable(attr):
            return attr

        # Read operations require 'db:read'
        if any(name.startswith(pfx) for pfx in _READ_METHOD_PREFIXES):
            if "db:read" not in self._permissions:
                raise PermissionError(f"Agent '{self._agent_id}' lacks 'db:read' permission to call '{name}()'")
            return attr

        # Mutating operations require 'db:write'
        if "db:write" not in self._permissions:
            raise PermissionError(f"Agent '{self._agent_id}' attempted mutating operation '{name}()' without 'db:write' permission")

        return attr


def get_sanitized_plugin_env(base_env: Dict[str, str] = None) -> Dict[str, str]:
    """Returns a sanitized environment mapping with all sensitive tokens and secrets stripped."""
    source = os.environ if base_env is None else base_env
    sanitized = {}
    for k, v in source.items():
        k_upper = k.upper()
        if any(kw in k_upper for kw in _SENSITIVE_ENV_KEYWORDS):
            continue
        sanitized[k] = v
    return sanitized
