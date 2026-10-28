from __future__ import annotations
"""
Deterministic Event Bus for Personal Agentic Fleet.
Enables zero-token, in-process Agent-to-Agent (A2A) communication using typed message envelopes.
"""

import collections
from dataclasses import asdict, dataclass, field
from datetime import datetime
import logging
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger("fleet.core.event_bus")

from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.tools.system_tools import (
    find_large_files,
    organize_directory,
    scan_directory,
    send_windows_notification,
)


@dataclass
class FleetEvent:
    sender: str
    target: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DeterministicEventBus:
    """
    In-process A2A message dispatcher.
    Resolves agent actions deterministically in pure Python without LLM token spend.
    """
    def __init__(self, db: Optional[FleetDatabase] = None):
        self.db = db or FleetDatabase()
        self.briefing_engine = BriefingEngine(self.db)
        self._handlers: Dict[str, Callable[[FleetEvent], Dict[str, Any]]] = {}
        self._subscribers: Dict[str, List[Callable[[FleetEvent], None]]] = collections.defaultdict(list)
        self._sub_lock = threading.Lock()
        self._register_default_workers()

    def register_handler(self, target: str, handler: Callable[[FleetEvent], Dict[str, Any]]):
        self._handlers[target.lower()] = handler

    def subscribe(self, target: str, listener: Callable[[FleetEvent], None]) -> None:
        """Subscribes a listener callback to events targeted at 'target' (or '*' for all events)."""
        with self._sub_lock:
            self._subscribers[target.lower()].append(listener)

    def unsubscribe(self, target: str, listener: Callable[[FleetEvent], None]) -> None:
        """Unsubscribes a listener callback."""
        with self._sub_lock:
            subs = self._subscribers.get(target.lower(), [])
            if listener in subs:
                subs.remove(listener)

    def _notify_subscribers(self, event: FleetEvent) -> None:
        target_key = event.target.lower()
        with self._sub_lock:
            listeners = list(self._subscribers.get(target_key, [])) + list(self._subscribers.get("*", []))
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass

    def dispatch(self, event: FleetEvent) -> Dict[str, Any]:
        """Route event to the appropriate target worker with zero LLM overhead."""
        self._notify_subscribers(event)
        try:
            from fleet.core.mind import fleet_mind
            fleet_mind.record_synapse()
        except Exception:
            pass

        target_key = event.target.lower()
        handler = self._handlers.get(target_key)

        if not handler:
            error_msg = f"Unknown target worker: '{event.target}'. Registered: {list(self._handlers.keys())}"
            self.db.log_activity(event.sender, "event_bus_error", error_msg)
            logger.warning(
                "EventBus unknown target: '%s' from sender '%s' (action: %s)",
                event.target, event.sender, event.action,
                extra={"agent": event.sender, "action": event.action}
            )
            return {"status": "error", "message": error_msg}

        try:
            result = handler(event)
            self.db.log_activity(
                event.sender,
                f"a2a_{event.action.lower()}",
                f"Routed to {event.target} (ID: {event.correlation_id})"
            )
            # Conscious Meta-Critique Loop (Non-blocking self-evaluation)
            try:
                from fleet.core.mind import fleet_mind
                if target_key != "mind":
                    fleet_mind.critique(
                        agent=event.target,
                        action=event.action,
                        input_payload=event.payload,
                        output_result=result if isinstance(result, dict) else {"status": "success", "result": result}
                    )
            except Exception:
                pass

            return {
                "status": "success",
                "correlation_id": event.correlation_id,
                "data": result
            }
        except Exception as e:
            err = f"Execution error in {event.target}.{event.action}: {str(e)}"
            self.db.log_activity(event.sender, "event_bus_exception", err)
            logger.error(
                "EventBus execution failure in %s.%s from %s: %s",
                event.target, event.action, event.sender, e,
                exc_info=True,
                extra={"agent": event.sender, "action": event.action}
            )
            return {"status": "error", "message": err}

    def dispatch_parallel(self, events: List[FleetEvent], max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        Dispatches multiple FleetEvents concurrently using parallel worker threads.
        Fast-tracks execution while strictly maintaining Tier 0 deterministic cost ($0.00 / 0 Tokens).
        """
        from concurrent.futures import ThreadPoolExecutor
        if not events:
            return []
        workers = min(max(1, max_workers), len(events))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(self.dispatch, events))

    def _register_default_workers(self):
        self.register_handler("agenda", self._handle_agenda)
        self.register_handler("files", self._handle_files)
        self.register_handler("notification", self._handle_notification)
        self.register_handler("email", self._handle_email)
        self.register_handler("system", self._handle_system)
        self.register_handler("mind", self._handle_mind)

    # --- Worker Handlers (Tier 0: Pure Code / 0 Tokens) ---

    def _handle_agenda(self, event: FleetEvent) -> Dict[str, Any]:
        action = event.action.upper()
        p = event.payload

        if action == "GET_BRIEFING":
            return self.briefing_engine.generate_daily_briefing()

        elif action == "ADD_TASK":
            task_title = p.get("title", "Untitled Task")
            task_desc = (p.get("description") or "").strip() or f"Task: {task_title}"
            task_id = self.db.add_task(
                title=task_title,
                description=task_desc,
                priority=p.get("priority", "P2"),
                due_date=p.get("due_date"),
                assigned_agent=event.sender
            )
            return {"task_id": task_id, "created": True}

        elif action == "LIST_TASKS":
            status = p.get("status")
            limit = p.get("limit", 20)
            return {"tasks": self.db.list_tasks(status=status, limit=limit)}

        elif action == "COMPLETE_TASK":
            task_id = int(p.get("task_id", 0))
            updated = self.db.update_task_status(task_id, "completed")
            return {"task_id": task_id, "completed": updated}

        elif action == "TOGGLE_ROUTINE":
            routine_id = int(p.get("routine_id", 0))
            toggled = self.db.toggle_routine(routine_id)
            return {"routine_id": routine_id, "toggled": toggled}

        elif action == "LIST_ROUTINES":
            return {"routines": self.db.list_routines()}

        else:
            raise ValueError(f"Unknown Agenda action: {event.action}")

    def _handle_files(self, event: FleetEvent) -> Dict[str, Any]:
        action = event.action.upper()
        p = event.payload
        path = p.get("path", "~/Downloads")

        if action == "SCAN_DIR":
            return scan_directory(path)

        elif action == "FIND_LARGE_FILES":
            min_mb = p.get("min_size_mb", 100.0)
            return {"large_files": find_large_files(path, min_size_mb=min_mb)}

        elif action == "ORGANIZE_DIR":
            dry_run = p.get("dry_run", True)
            return organize_directory(path, dry_run=dry_run)

        else:
            raise ValueError(f"Unknown File action: {event.action}")

    def _handle_notification(self, event: FleetEvent) -> Dict[str, Any]:
        p = event.payload
        title = p.get("title", "Personal Agentic Fleet")
        message = p.get("message", "Notification")
        sent = send_windows_notification(title, message)
        return {"sent": sent, "title": title}

    def _handle_email(self, event: FleetEvent) -> Dict[str, Any]:
        from fleet.integrations.gmail_client import gmail_manager
        action = event.action.upper()
        p = event.payload

        if action == "CLASSIFY_RECENT":
            dry_run = p.get("dry_run", False)
            auto_archive = p.get("auto_archive_ignore", False)
            force_refresh = p.get("force_refresh", False)
            return gmail_manager.sync_and_classify(dry_run=dry_run, auto_archive_ignore=auto_archive, force_refresh=force_refresh)

        elif action == "GET_STATUS":
            from fleet.integrations.gmail_client import get_two_month_lookback_query
            return {
                "connected": gmail_manager.is_connected,
                "lookback_query": get_two_month_lookback_query()
            }

        elif action == "UNSUBSCRIBE":
            return gmail_manager.unsubscribe_from_email(
                message_id=str(p.get("message_id") or p.get("id") or ""),
                url=p.get("url"),
                unsub_type=p.get("type", "http"),
                sender=p.get("sender", ""),
                subject=p.get("subject", "")
            )

        else:
            raise ValueError(f"Unknown Email action: {event.action}")

    def _handle_system(self, event: FleetEvent) -> Dict[str, Any]:
        from fleet.core.optimizer import (
            clean_temp_files,
            flush_dns_cache,
            get_pc_performance_diagnostics,
            open_startup_settings,
            optimize_ram,
            purge_dev_caches,
        )
        action = event.action.upper()
        p = event.payload

        if action in ("DIAGNOSTICS", "GET_DIAGNOSTICS"):
            return get_pc_performance_diagnostics()
        elif action in ("CLEAN_TEMP", "CLEAN_TEMP_FILES"):
            return clean_temp_files()
        elif action in ("FLUSH_DNS", "FLUSH_DNS_CACHE"):
            return flush_dns_cache()
        elif action in ("PURGE_CACHES", "PURGE_DEV_CACHES"):
            return purge_dev_caches(p.get("target_path"))
        elif action in ("OPTIMIZE_RAM", "SWEEP_RAM"):
            return optimize_ram()
        elif action in ("OPEN_STARTUP", "OPEN_STARTUP_SETTINGS"):
            return open_startup_settings()
        elif action in ("PROACTIVE_SCAN", "AUTO_HEAL", "RUN_AUTO_HEAL"):
            from fleet.core.auto_healer import run_proactive_log_scan_and_heal
            return run_proactive_log_scan_and_heal(db=self.db)
        elif action == "PROACTIVE_SCAN_COMPLETE":
            return {"status": "received", "data": p}
        elif action in ("SETTINGS_UPDATED", "UPDATE_SETTINGS", "RELOAD_SETTINGS"):
            return {"status": "success", "action": "settings_updated", "data": p}
        else:
            raise ValueError(f"Unknown System action: {event.action}")

    def _handle_mind(self, event: FleetEvent) -> Dict[str, Any]:
        from dataclasses import asdict
        from fleet.core.mind import fleet_mind
        fleet_mind.set_db(self.db)
        action = event.action.upper()
        p = event.payload or {}

        if action in ("STATUS", "GET_STATUS"):
            return fleet_mind.get_holistic_state()
        elif action in ("CRITIQUE", "EVALUATE"):
            res = fleet_mind.critique(
                agent=p.get("agent", "Unknown"),
                action=p.get("action", "Unknown"),
                input_payload=p.get("input"),
                output_result=p.get("output"),
            )
            return asdict(res)
        elif action in ("DREAM", "RUN_DREAM_CYCLE"):
            return fleet_mind.dream(max_activities=int(p.get("max_activities", 200)))
        elif action in ("SOUL_AUDIT", "AUDIT_SOUL"):
            return asdict(fleet_mind.audit_soul())
        elif action in ("SELF_IMPROVE", "EVOLVE"):
            return fleet_mind.self_improve()
        elif action in ("HEAL", "AUTONOMIC_HEAL"):
            return fleet_mind.heal()
        else:
            raise ValueError(f"Unknown Mind action: {event.action}")


# Singleton Bus instance
bus = DeterministicEventBus()
event_bus = bus



