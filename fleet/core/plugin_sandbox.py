"""
Plugin Capability Sandboxing, Dry-Run Savepoint Simulation & Undo Journal (UX-08)
for Personal Agentic Fleet.

Ensures third-party and built-in agents declare explicit least-privilege permissions
in `manifest.json` and enforces capability boundaries at runtime:
  - `ScopedDatabaseProxy` blocks write/delete DB calls if agent lacks `db:write`
  - `ScopedDatabaseProxy(dry_run=True)` intercepts and records all mutating calls
    without persisting changes to disk (`UX-08` Safe Dry-Run Sandbox)
  - Live mutations through `ScopedDatabaseProxy` automatically write reversible
    pre-mutation snapshots to `agent_undo_journal` (`UX-08` 1-Click Undo Rollback)
  - `get_sanitized_plugin_env()` strips sensitive environment secrets before subprocess execution
"""

from contextlib import contextmanager
from datetime import datetime
import os
from typing import Any, Dict, Generator, Iterable, List, Optional, Set

ALLOWED_AGENT_PERMISSIONS: Set[str] = {
    "db:read",
    "db:write",
    "event_bus:publish",
    "event_bus:subscribe",
    "filesystem:videos",
    "filesystem:temp",
    "network:gmail_oauth",
    "network:github_api",
    "network:outbound",
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
    """
    Restricts an agent's access to `FleetDatabase` methods based on manifest permissions,
    supports `dry_run=True` simulation mode (`UX-08`), and records undo journal snapshots.
    """

    def __init__(
        self,
        raw_db: Any,
        agent_id: str,
        permissions: List[str],
        dry_run: bool = False,
    ):
        self._raw_db = raw_db
        self._agent_id = agent_id
        self._permissions = set(permissions)
        self.dry_run: bool = bool(dry_run)
        self.recorded_mutations: List[Dict[str, Any]] = []

    @contextmanager
    def dry_run_session(self) -> Generator[List[Dict[str, Any]], None, None]:
        """Context manager that temporarily switches this proxy into Dry-Run simulation mode."""
        prev = self.dry_run
        self.dry_run = True
        self.recorded_mutations.clear()
        try:
            yield self.recorded_mutations
        finally:
            self.dry_run = prev

    def _capture_prior_state(self, name: str, args: tuple, kwargs: dict) -> Optional[Dict[str, Any]]:
        """Fetches prior row state before a live mutation so it can be undone in 1 click."""
        try:
            if name in ("complete_task", "delete_task", "update_task"):
                tid = args[0] if args else kwargs.get("task_id") or kwargs.get("id")
                if tid is not None and hasattr(self._raw_db, "get_all_tasks"):
                    for t in self._raw_db.get_all_tasks() or []:
                        if str(t.get("id")) == str(tid):
                            return dict(t)
            elif name == "set_setting":
                key = args[0] if args else kwargs.get("key")
                if key and hasattr(self._raw_db, "get_setting"):
                    sentinel = "__MISSING__"
                    val = self._raw_db.get_setting(str(key), sentinel)
                    return {"existed": val != sentinel, "value": "" if val == sentinel else val}
            elif name == "update_feature_backlog_item":
                bid = args[0] if args else kwargs.get("item_id")
                if bid is not None and hasattr(self._raw_db, "list_feature_backlog_items"):
                    for item in self._raw_db.list_feature_backlog_items() or []:
                        if str(item.get("id")) == str(bid):
                            return dict(item)
        except Exception:
            pass
        return None

    def _record_live_undo(self, name: str, args: tuple, kwargs: dict, result: Any, prior: Optional[Dict[str, Any]]) -> None:
        if not hasattr(self._raw_db, "record_agent_undo_entry"):
            return
        try:
            if name == "add_task":
                title = args[0] if args else kwargs.get("title", "")
                self._raw_db.record_agent_undo_entry(
                    agent_id=self._agent_id,
                    operation="add_task",
                    target_table="tasks",
                    target_id=str(result or ""),
                    prior_state={},
                    new_state={"id": result, "title": title},
                )
            elif name in ("complete_task", "delete_task", "update_task"):
                tid = args[0] if args else kwargs.get("task_id") or kwargs.get("id")
                self._raw_db.record_agent_undo_entry(
                    agent_id=self._agent_id,
                    operation=name,
                    target_table="tasks",
                    target_id=str(tid or ""),
                    prior_state=prior or {},
                    new_state={"args": list(args), "kwargs": kwargs},
                )
            elif name == "set_setting":
                key = args[0] if args else kwargs.get("key", "")
                val = args[1] if len(args) > 1 else kwargs.get("value", "")
                self._raw_db.record_agent_undo_entry(
                    agent_id=self._agent_id,
                    operation="set_setting",
                    target_table="settings",
                    target_id=str(key),
                    prior_state=prior or {"existed": False, "value": ""},
                    new_state={"key": key, "value": val},
                )
            elif name == "update_feature_backlog_item":
                bid = args[0] if args else kwargs.get("item_id", "")
                self._raw_db.record_agent_undo_entry(
                    agent_id=self._agent_id,
                    operation="update_feature_backlog_item",
                    target_table="feature_backlog",
                    target_id=str(bid),
                    prior_state=prior or {},
                    new_state=kwargs,
                )
        except Exception:
            pass

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
            raise PermissionError(
                f"Agent '{self._agent_id}' attempted mutating operation '{name}()' without 'db:write' permission"
            )

        def _wrapped_mutation(*args: Any, **kwargs: Any) -> Any:
            if self.dry_run:
                mutation_entry = {
                    "agent_id": self._agent_id,
                    "operation": name,
                    "args": [str(a) for a in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                    "timestamp": datetime.now().isoformat(),
                }
                self.recorded_mutations.append(mutation_entry)
                if name.startswith("add_"):
                    return 0
                return True

            prior = self._capture_prior_state(name, args, kwargs)
            result = attr(*args, **kwargs)
            self._record_live_undo(name, args, kwargs, result, prior)
            return result

        return _wrapped_mutation


def simulate_agent_task_dry_run(
    agent: Any,
    task: str = "default",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes `agent.execute_task(task, payload)` inside a `ScopedDatabaseProxy(dry_run=True)`
    sandbox so zero database writes are persisted, returning the proposed changes diff.
    """
    orig_db = getattr(agent, "db", None)
    raw_db = getattr(orig_db, "_raw_db", orig_db)
    perms = list(ALLOWED_AGENT_PERMISSIONS)
    if isinstance(orig_db, ScopedDatabaseProxy):
        perms = list(orig_db._permissions)

    dry_proxy = ScopedDatabaseProxy(
        raw_db=raw_db,
        agent_id=getattr(agent, "id", "agent"),
        permissions=perms,
        dry_run=True,
    )
    try:
        agent.db = dry_proxy
        result = agent.execute_task(task, payload or {})
    finally:
        agent.db = orig_db

    return {
        "status": "ok",
        "dry_run": True,
        "agent_id": getattr(agent, "id", "agent"),
        "task": task,
        "proposed_mutations_count": len(dry_proxy.recorded_mutations),
        "proposed_mutations": list(dry_proxy.recorded_mutations),
        "simulated_result": result,
    }


def get_sanitized_plugin_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Returns a sanitized environment mapping with all sensitive tokens and secrets stripped."""
    source = os.environ if base_env is None else base_env
    sanitized = {}
    for k, v in source.items():
        k_upper = k.upper()
        if any(kw in k_upper for kw in _SENSITIVE_ENV_KEYWORDS):
            continue
        sanitized[k] = v
    return sanitized
