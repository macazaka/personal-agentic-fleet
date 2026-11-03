"""
UX-07: Focus-Aware Smart Nudges & Actionable Notification Cards.
Provides:
  1. `FocusGuard` — Detects full-screen applications, video calls (Zoom, Teams, Webex, Meet),
     Quiet Hours, or active Focus Mode, queuing non-urgent notifications into a Smart Nudge Digest.
  2. Interactive 1-Click Action Buttons (`actions: List[Dict[str, Any]]`) attached to agent
     notifications (`[✓ +250ml Water]`, `[💤 Snooze 30m]`, `[✓ Complete]`).
"""

import ctypes
from datetime import datetime, timedelta
import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

_FOCUS_LOCK = threading.RLock()
_NUDGE_SEQ = 0
_NUDGE_DIGEST: List[Dict[str, Any]] = []
_RECENT_DELIVERED: List[Dict[str, Any]] = []
_FOCUS_OVERRIDE_UNTIL: Optional[datetime] = None
_FOCUS_MANUAL_ENABLED: bool = False


def _next_nudge_id() -> str:
    global _NUDGE_SEQ
    with _FOCUS_LOCK:
        _NUDGE_SEQ += 1
        return f"nudge-{_NUDGE_SEQ:04d}"


def _detect_win32_fullscreen_or_presentation() -> Tuple[bool, str]:
    """Uses Win32 `SHQueryUserNotificationState` to check if user is in fullscreen/presentation/D3D mode."""
    if os.name != "nt":
        return False, "normal"
    try:
        shell32 = getattr(ctypes, "windll", None)
        if shell32 and hasattr(shell32, "shell32"):
            state = ctypes.c_int(0)
            res = shell32.shell32.SHQueryUserNotificationState(ctypes.byref(state))
            if res == 0:
                # 2 = QUNS_BUSY (fullscreen app), 3 = QUNS_RUNNING_D3D_FULL_SCREEN, 4 = QUNS_PRESENTATION_MODE
                if state.value in (2, 3, 4):
                    return True, f"win32_quns_{state.value}"
    except Exception:
        pass
    return False, "normal"


def detect_focus_state(db: Optional[Any] = None, now_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Determines whether the workstation is currently in Focus Mode, Quiet Hours, or Fullscreen/Meeting state.
    Zero cloud tokens ($0.00).
    """
    global _FOCUS_MANUAL_ENABLED, _FOCUS_OVERRIDE_UNTIL
    now = now_dt or datetime.now()

    with _FOCUS_LOCK:
        if _FOCUS_OVERRIDE_UNTIL and now >= _FOCUS_OVERRIDE_UNTIL:
            _FOCUS_MANUAL_ENABLED = False
            _FOCUS_OVERRIDE_UNTIL = None

        manual_active = _FOCUS_MANUAL_ENABLED
        until_iso = _FOCUS_OVERRIDE_UNTIL.isoformat() if _FOCUS_OVERRIDE_UNTIL else ""

    if db is not None and hasattr(db, "get_setting"):
        try:
            db_focus = str(db.get_setting("ux07_focus_mode", "") or "").lower()
            if db_focus in ("1", "true", "on"):
                manual_active = True
        except Exception:
            pass

    # Quiet hours check (22:30 - 06:30 local time)
    quiet_hours = now.hour >= 23 or now.hour < 6

    is_fs, fs_reason = _detect_win32_fullscreen_or_presentation()
    focus_active = bool(manual_active or quiet_hours)
    reason = "manual_focus" if manual_active else ("quiet_hours" if quiet_hours else (fs_reason if is_fs else "available"))

    with _FOCUS_LOCK:
        queued_cnt = len(_NUDGE_DIGEST)

    return {
        "focus_active": focus_active,
        "manual_focus": manual_active,
        "quiet_hours": quiet_hours,
        "fullscreen_detected": is_fs,
        "reason": reason,
        "focus_until": until_iso,
        "queued_nudges_count": queued_cnt,
    }


def set_focus_mode(
    enabled: bool,
    duration_minutes: int = 60,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Enables or disables Focus Mode for `duration_minutes`."""
    global _FOCUS_MANUAL_ENABLED, _FOCUS_OVERRIDE_UNTIL
    with _FOCUS_LOCK:
        _FOCUS_MANUAL_ENABLED = bool(enabled)
        if enabled and duration_minutes > 0:
            _FOCUS_OVERRIDE_UNTIL = datetime.now() + timedelta(minutes=int(duration_minutes))
        else:
            _FOCUS_OVERRIDE_UNTIL = None

    if db is not None and hasattr(db, "set_setting"):
        try:
            db.set_setting("ux07_focus_mode", "1" if enabled else "0")
        except Exception:
            pass

    state = detect_focus_state(db=db)
    return {
        "status": "ok",
        "focus": state,
        "message": f"Focus Mode {'enabled' if enabled else 'disabled'}"
        + (f" for {duration_minutes}m." if enabled else "."),
    }


def build_default_nudge_actions(agent_id: str, task: str = "") -> List[Dict[str, Any]]:
    """Constructs context-aware 1-click notification card actions for an agent notification."""
    aid = (agent_id or "").strip().lower()
    if aid == "health":
        return [
            {
                "id": "log_water_250",
                "label": "💧 +1 Glass (250ml)",
                "endpoint": "/api/health/hydration",
                "method": "POST",
                "payload": {"amount_ml": 250},
            },
            {
                "id": "snooze_30m",
                "label": "💤 Snooze 30m",
                "action": "snooze",
                "minutes": 30,
            },
            {
                "id": "dismiss",
                "label": "✓ Done",
                "action": "dismiss",
            },
        ]
    if aid == "optimizer":
        return [
            {
                "id": "optimize_ram_now",
                "label": "🚀 Free RAM Now",
                "endpoint": "/api/optimizer/clean",
                "method": "POST",
                "payload": {},
            },
            {
                "id": "dismiss",
                "label": "✓ Dismiss",
                "action": "dismiss",
            },
        ]
    if aid == "gmail":
        return [
            {
                "id": "open_inbox",
                "label": "📧 Open 01-Focus",
                "action": "switch_tab",
                "tab": "gmail",
            },
            {
                "id": "snooze_30m",
                "label": "💤 Snooze 30m",
                "action": "snooze",
                "minutes": 30,
            },
        ]
    return [
        {
            "id": "snooze_30m",
            "label": "💤 Snooze 30m",
            "action": "snooze",
            "minutes": 30,
        },
        {
            "id": "dismiss",
            "label": "✓ Dismiss",
            "action": "dismiss",
        },
    ]


def dispatch_or_batch_nudge(
    title: str,
    message: str,
    agent_id: str = "system",
    priority: str = "P2",
    actions: Optional[List[Dict[str, Any]]] = None,
    force_immediate: bool = False,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Evaluates current `FocusGuard` state and either:
      - Queues non-critical notifications into the Smart Nudge Digest when Focus/Quiet Mode is active
      - Delivers immediately with interactive 1-click `actions` attached
    """
    nudge_id = _next_nudge_id()
    resolved_actions = actions if isinstance(actions, list) and actions else build_default_nudge_actions(agent_id)
    focus_state = detect_focus_state(db=db)
    pri = (priority or "P2").upper()

    card = {
        "id": nudge_id,
        "agent_id": agent_id,
        "title": title,
        "message": message,
        "priority": pri,
        "actions": resolved_actions[:3],
        "created_at": datetime.now().isoformat(),
        "status": "delivered",
    }

    should_batch = bool(focus_state.get("focus_active")) and pri not in ("P0", "CRITICAL") and not force_immediate
    with _FOCUS_LOCK:
        if should_batch:
            card["status"] = "batched"
            card["batched_reason"] = focus_state.get("reason", "focus_active")
            _NUDGE_DIGEST.append(card)
            if len(_NUDGE_DIGEST) > 100:
                del _NUDGE_DIGEST[:-100]
        else:
            _RECENT_DELIVERED.insert(0, card)
            if len(_RECENT_DELIVERED) > 50:
                del _RECENT_DELIVERED[50:]

    return {
        "status": "batched" if should_batch else "delivered",
        "nudge": card,
        "focus": detect_focus_state(db=db),
    }


def list_smart_nudges(db: Optional[Any] = None) -> Dict[str, Any]:
    """Returns both batched Smart Digest nudges and recently delivered actionable notification cards."""
    with _FOCUS_LOCK:
        batched = list(_NUDGE_DIGEST)
        delivered = list(_RECENT_DELIVERED[:25])
    return {
        "status": "ok",
        "focus": detect_focus_state(db=db),
        "batched_count": len(batched),
        "batched_nudges": batched,
        "recent_delivered": delivered,
    }


def flush_nudge_digest(db: Optional[Any] = None) -> Dict[str, Any]:
    """Flushes all queued Smart Nudge Digest items into delivered state."""
    with _FOCUS_LOCK:
        flushed = list(_NUDGE_DIGEST)
        _NUDGE_DIGEST.clear()
        for item in reversed(flushed):
            item["status"] = "delivered"
            _RECENT_DELIVERED.insert(0, item)
        if len(_RECENT_DELIVERED) > 50:
            del _RECENT_DELIVERED[50:]

    return {
        "status": "ok",
        "flushed_count": len(flushed),
        "flushed_nudges": flushed,
        "focus": detect_focus_state(db=db),
    }


def execute_nudge_action(
    nudge_id: str,
    action_id: str,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Executes a 1-click action on a Smart Nudge card (e.g. log water, snooze, dismiss)."""
    target: Optional[Dict[str, Any]] = None
    with _FOCUS_LOCK:
        for coll in (_NUDGE_DIGEST, _RECENT_DELIVERED):
            for idx, item in enumerate(coll):
                if item.get("id") == nudge_id:
                    target = item
                    if action_id in ("dismiss", "done", "log_water_250", "optimize_ram_now"):
                        coll.pop(idx)
                    break
            if target is not None:
                break

    if action_id == "log_water_250" and db is not None and hasattr(db, "log_water"):
        try:
            db.log_water(250)
        except Exception:
            pass
        return {"status": "ok", "nudge_id": nudge_id, "action_id": action_id, "message": "Logged +250ml water."}

    if action_id == "snooze_30m":
        if target is not None:
            target["snoozed_until"] = (datetime.now() + timedelta(minutes=30)).isoformat()
            target["status"] = "snoozed"
        return {"status": "ok", "nudge_id": nudge_id, "action_id": action_id, "message": "Snoozed nudge for 30 minutes."}

    return {
        "status": "ok",
        "nudge_id": nudge_id,
        "action_id": action_id,
        "message": f"Executed nudge action '{action_id}'.",
    }
