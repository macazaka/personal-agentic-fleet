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


def get_sanitized_plugin_env(allowed_env_keys: Iterable[str] = ()) -> Dict[str, str]:
    """
    Returns a sanitized copy of os.environ with all secret/token/key variables stripped,
    unless explicitly listed in allowed_env_keys.
    """
    allow_set = {k.upper() for k in allowed_env_keys}
    clean_env: Dict[str, str] = {}
    for k, v in os.environ.items():
        k_up = k.upper()
        if k_up in allow_set:
            clean_env[k] = v
            continue
        if any(word in k_up for word in _SENSITIVE_ENV_KEYWORDS):
            continue
        clean_env[k] = v
    return clean_env


class ScopedDatabaseProxy:
    """
    Capability-enforcing proxy around FleetDatabase for modular agents.
    Enforces 'db:read' and 'db:write' permissions declared in the agent's manifest.json.
    """

    def __init__(self, db: Any, agent_id: str, permissions: Iterable[str]):
        self._db = db
        self._agent_id = agent_id
        self._permissions: Set[str] = set(permissions)

    def __getattr__(self, name: str) -> Any:
        if self._db is None:
            raise RuntimeError(f"Database not initialized for agent '{self._agent_id}'")

        attr = getattr(self._db, name)
        if not callable(attr):
            return attr

        is_read_op = name.startswith(_READ_METHOD_PREFIXES)
        if is_read_op:
            if "db:read" not in self._permissions and "db:write" not in self._permissions:
                raise PermissionError(
                    f"Plugin Sandbox Violation: Agent '{self._agent_id}' attempted read '{name}' without 'db:read' permission."
                )
        else:
            if "db:write" not in self._permissions:
                raise PermissionError(
                    f"Plugin Sandbox Violation: Agent '{self._agent_id}' attempted write/mutation '{name}' without 'db:write' permission."
                )
        return attr
