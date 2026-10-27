"""
Deterministic Agent Scheduling Engine for Personal Agentic Fleet.
Enables users to schedule agent tasks at specific times of day, recurring intervals,
or standard cron expressions via YAML configuration with built-in default schedules.
Runs 100% deterministically at Tier 0 ($0.00 / 0 Tokens).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from fleet.config import BASE_DIR, DATA_DIR, TIMEZONE, TIMEZONE_NAME, load_fleet_config
from fleet.core.database import FleetDatabase
from fleet.core.event_bus import FleetEvent, bus
from fleet.core.yaml_helper import dump_yaml, load_yaml_file, safe_load_yaml, save_yaml_file
from fleet.tools.system_tools import send_windows_notification

logger = logging.getLogger("fleet.scheduler")


def parse_interval_to_seconds(
    val: Union[int, float, str, None],
    hours: Union[int, float, None] = None,
    minutes: Union[int, float, None] = None,
    seconds: Union[int, float, None] = None,
) -> int:
    """Computes total interval in seconds from multiple possible inputs."""
    tot = 0
    if seconds is not None:
        tot += int(seconds)
    if minutes is not None:
        tot += int(minutes * 60)
    if hours is not None:
        tot += int(hours * 3600)

    if tot > 0:
        return tot

    if val is None:
        return 3600  # Default 1 hour

    if isinstance(val, (int, float)):
        return max(1, int(val))

    s = str(val).strip().lower()
    if s.endswith("h"):
        try:
            return max(1, int(float(s[:-1]) * 3600))
        except ValueError:
            pass
    elif s.endswith("m"):
        try:
            return max(1, int(float(s[:-1]) * 60))
        except ValueError:
            pass
    elif s.endswith("s"):
        try:
            return max(1, int(float(s[:-1])))
        except ValueError:
            pass
    elif s.endswith("d"):
        try:
            return max(1, int(float(s[:-1]) * 86400))
        except ValueError:
            pass
    try:
        return max(1, int(s))
    except ValueError:
        return 3600


def match_cron_field(field_pattern: str, val: int, min_val: int, max_val: int) -> bool:
    """Matches a single cron field (*, */N, N, N-M, N,M)."""
    p = field_pattern.strip()
    if p == "*":
        return True

    # Step: */N
    if p.startswith("*/"):
        try:
            step = int(p[2:])
            return step > 0 and (val - min_val) % step == 0
        except ValueError:
            return False

    # List: A,B,C
    if "," in p:
        return any(match_cron_field(part, val, min_val, max_val) for part in p.split(","))

    # Range: A-B
    if "-" in p:
        try:
            start, end = map(int, p.split("-", 1))
            return start <= val <= end
        except ValueError:
            return False

    # Single number
    try:
        return int(p) == val
    except ValueError:
        return False


def match_cron(cron_expr: str, dt: datetime) -> bool:
    """Evaluates a standard 5-part cron expression (minute hour day month day_of_week)."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    min_p, hour_p, day_p, mon_p, dow_p = parts

    # Python weekday(): 0 = Monday, 6 = Sunday. Cron: 0 = Sunday, 1 = Monday, ..., 7 = Sunday
    cron_dow = (dt.weekday() + 1) % 7

    return (
        match_cron_field(min_p, dt.minute, 0, 59)
        and match_cron_field(hour_p, dt.hour, 0, 23)
        and match_cron_field(day_p, dt.day, 1, 31)
        and match_cron_field(mon_p, dt.month, 1, 12)
        and (match_cron_field(dow_p, cron_dow, 0, 7) or (dow_p == "7" and cron_dow == 0))
    )


# Built-in Default Schedules
DEFAULT_SCHEDULES: List[Dict[str, Any]] = [
    {
        "id": "overview_morning_briefing",
        "agent": "overview",
        "task": "morning_briefing",
        "description": "Daily morning briefing with top priorities and open tasks",
        "schedule_type": "time_of_day",
        "time": "08:30",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "enabled": True,
        "notify": True,
    },
    {
        "id": "overview_evening_review",
        "agent": "overview",
        "task": "evening_review",
        "description": "Evening review and reflection on tasks completed during the day",
        "schedule_type": "time_of_day",
        "time": "20:00",
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_smoothie_reminder",
        "agent": "health",
        "task": "smoothie_reminder",
        "description": "Early morning 250ml smoothie on empty stomach with methi, cinnamon & haldi",
        "schedule_type": "time_of_day",
        "time": "07:15",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_breakfast_meds",
        "agent": "health",
        "task": "breakfast_meds",
        "description": "Breakfast (25-25-50% quad plate) and morning prescription supplements",
        "schedule_type": "time_of_day",
        "time": "08:30",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_lunch_meds",
        "agent": "health",
        "task": "lunch_meds",
        "description": "Lunch quad plate and afternoon prescription supplements",
        "schedule_type": "time_of_day",
        "time": "13:30",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_afternoon_snack",
        "agent": "health",
        "task": "afternoon_snack",
        "description": "Afternoon smoothie and 5-6 soaked almonds, walnuts & mixed seeds",
        "schedule_type": "time_of_day",
        "time": "16:15",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_dinner_meds",
        "agent": "health",
        "task": "dinner_meds",
        "description": "Early dinner (4th morsel rule before 8:30 PM) and evening supplements",
        "schedule_type": "time_of_day",
        "time": "19:30",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "health_sleep_recovery",
        "agent": "health",
        "task": "sleep_recovery",
        "description": "Screens cutoff, metabolic recovery wind-down and sleep preparation",
        "schedule_type": "time_of_day",
        "time": "22:30",
        "enabled": True,
        "notify": True,
    },
    {
        "id": "optimizer_quick_optimize",
        "agent": "optimizer",
        "task": "quick_optimize",
        "description": "Periodic RAM optimization, memory telemetry logging and DNS cache flush",
        "schedule_type": "interval",
        "interval_hours": 6,
        "enabled": True,
        "notify": False,
    },
    {
        "id": "gmail_sync_and_classify",
        "agent": "gmail",
        "task": "sync_and_classify",
        "description": "Bi-hourly email classification pulse during workday",
        "schedule_type": "interval",
        "interval_hours": 2,
        "active_hours": "08:00-18:00",
        "weekdays_only": True,
        "enabled": False,
        "notify": False,
    },
    {
        "id": "antigravity_process_queue",
        "agent": "antigravity",
        "task": "process_queue",
        "description": "Process pending queued prompts, refresh transcript mirror and check token budgets",
        "schedule_type": "interval",
        "interval_minutes": 5,
        "enabled": True,
        "notify": False,
    },
    {
        "id": "backlog_grooming",
        "agent": "backlog",
        "task": "backlog_grooming",
        "description": "Weekly backlog grooming, priority evaluation (P1/P2/P3) and task hygiene",
        "schedule_type": "time_of_day",
        "time": "09:00",
        "days": ["monday"],
        "enabled": True,
        "notify": False,
    },
    {
        "id": "pr_review_check_ci",
        "agent": "pr_review",
        "task": "check_ci_status",
        "description": "Hourly audit of GitHub pull requests and main branch CI quality gates",
        "schedule_type": "interval",
        "interval_hours": 1,
        "enabled": False,
        "notify": False,
    },
]


class FleetScheduler:
    """
    Unified, deterministic agent task scheduler.
    Loads default schedules and merges user customizations from YAML/JSON files.
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        event_bus=None,
        db: Optional[FleetDatabase] = None,
        registry=None,
    ):
        self.config_dir = Path(config_dir) if config_dir else BASE_DIR.parent
        self.bus = event_bus or bus
        self.db = db or FleetDatabase()
        self.registry = registry
        self.timezone = TIMEZONE
        self.schedules: List[Dict[str, Any]] = []
        self._last_run_state: Dict[str, Dict[str, Any]] = {}
        self._triggered_today: Set[Tuple[str, str, str]] = set()  # (rule_id, date_str, time_str)
        self._last_day_str: str = ""

        self.reload()

    def _get_overrides_file(self) -> Path:
        from fleet.core.database import is_test_environment
        sub_vault = "test_user" if is_test_environment() else "user"
        p = DATA_DIR / sub_vault / "schedule_overrides.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def load_overrides(self) -> Dict[str, Any]:
        f = self._get_overrides_file()
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_overrides(self, overrides: Dict[str, Any]) -> None:
        f = self._get_overrides_file()
        try:
            f.write_text(json.dumps(overrides, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving schedule overrides: {e}")

    def reload(self) -> List[Dict[str, Any]]:
        """
        Reloads schedules prioritizing:
        1. User schedules.yaml (in root or fleet/data/user/schedules.yaml)
        2. schedules block in fleet.yaml / fleet.json
        3. fleet/config/schedules.yaml (default YAML)
        4. In-memory DEFAULT_SCHEDULES
        5. Applied runtime overrides from schedule_overrides.json
        """
        raw_rules: List[Dict[str, Any]] = []

        # 1. Base defaults from fleet/config/schedules.yaml or DEFAULT_SCHEDULES
        default_file = BASE_DIR / "config" / "schedules.yaml"
        if default_file.is_file():
            default_data = load_yaml_file(default_file)
            if isinstance(default_data, dict) and "schedules" in default_data:
                raw_rules.extend(default_data["schedules"])
            elif isinstance(default_data, list):
                raw_rules.extend(default_data)

        if not raw_rules:
            raw_rules = [dict(s) for s in DEFAULT_SCHEDULES]

        rules_by_id: Dict[str, Dict[str, Any]] = {}
        for r in raw_rules:
            rid = str(r.get("id") or f"{r.get('agent')}_{r.get('task')}")
            entry = dict(r)
            entry["id"] = rid
            rules_by_id[rid] = entry

        # 2. Check fleet.yaml / fleet.json
        try:
            cfg = load_fleet_config()
            if isinstance(cfg, dict):
                # Global schedules block
                if "schedules" in cfg and isinstance(cfg["schedules"], list):
                    for ur in cfg["schedules"]:
                        urid = str(ur.get("id") or f"{ur.get('agent')}_{ur.get('task')}")
                        if urid in rules_by_id:
                            rules_by_id[urid].update(ur)
                        else:
                            rules_by_id[urid] = dict(ur, id=urid)

                # Per-agent schedule block: agents.<id>.schedule or agents.<id>.schedules
                agents_cfg = cfg.get("agents", {})
                if isinstance(agents_cfg, dict):
                    for aid, acfg in agents_cfg.items():
                        if isinstance(acfg, dict):
                            sched_cfg = acfg.get("schedule") or acfg.get("schedules")
                            if isinstance(sched_cfg, dict):
                                sid = f"{aid}_{sched_cfg.get('task', 'run')}"
                                base = rules_by_id.get(sid, {"agent": aid, "id": sid})
                                base.update(sched_cfg)
                                rules_by_id[sid] = base
                            elif isinstance(sched_cfg, list):
                                for item in sched_cfg:
                                    if isinstance(item, dict):
                                        sid = item.get("id") or f"{aid}_{item.get('task', 'run')}"
                                        base = rules_by_id.get(sid, {"agent": aid, "id": sid})
                                        base.update(item)
                                        rules_by_id[sid] = base
        except Exception as e:
            logger.warning(f"Error loading fleet config schedules: {e}")

        # 3. Check standalone user schedules.yaml
        candidate_paths = [
            self.config_dir / "schedules.yaml",
            self.config_dir / "schedules.yml",
            DATA_DIR / "user" / "schedules.yaml",
            BASE_DIR / "schedules.yaml",
        ]
        for cpath in candidate_paths:
            if cpath.is_file():
                try:
                    udata = load_yaml_file(cpath)
                    u_list = udata.get("schedules") if isinstance(udata, dict) else udata
                    if isinstance(u_list, list):
                        for ur in u_list:
                            if isinstance(ur, dict):
                                urid = str(ur.get("id") or f"{ur.get('agent')}_{ur.get('task')}")
                                if urid in rules_by_id:
                                    rules_by_id[urid].update(ur)
                                else:
                                    rules_by_id[urid] = dict(ur, id=urid)
                        break
                except Exception as e:
                    logger.warning(f"Could not load custom {cpath}: {e}")

        # 4. Merge persistent overrides (toggles, edits from Web Dashboard/API)
        overrides = self.load_overrides()
        for oid, o_data in overrides.items():
            if oid in rules_by_id and isinstance(o_data, dict):
                rules_by_id[oid].update(o_data)

        # Normalize and store final rules
        self.schedules = []
        for rid, r in rules_by_id.items():
            norm_rule = self._normalize_rule(r)
            self.schedules.append(norm_rule)

        return self.schedules

    def _normalize_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures all necessary rule fields are populated with clean types."""
        rid = str(rule.get("id") or f"{rule.get('agent')}_{rule.get('task')}")
        agent = str(rule.get("agent") or "overview")
        task = str(rule.get("task") or "run")
        desc = str(rule.get("description") or f"Scheduled task: {task} ({agent})")

        schedule_type = str(rule.get("schedule_type") or "").lower()
        if not schedule_type:
            if "cron" in rule:
                schedule_type = "cron"
            elif any(k in rule for k in ("interval_hours", "interval_minutes", "interval_seconds", "every")):
                schedule_type = "interval"
            elif "time" in rule or "times" in rule:
                schedule_type = "time_of_day"
            else:
                schedule_type = "interval"

        # Days of week filter
        days = rule.get("days")
        if isinstance(days, str):
            days = [d.strip().lower() for d in days.split(",")]
        elif isinstance(days, list):
            days = [str(d).strip().lower() for d in days]
        else:
            days = []

        # Times list
        times = rule.get("times")
        if isinstance(times, str):
            times = [t.strip() for t in times.split(",")]
        elif isinstance(times, list):
            times = [str(t).strip() for t in times]
        elif rule.get("time"):
            times = [str(rule["time"]).strip()]
        else:
            times = []

        interval_sec = parse_interval_to_seconds(
            rule.get("every") or rule.get("interval"),
            hours=rule.get("interval_hours"),
            minutes=rule.get("interval_minutes"),
            seconds=rule.get("interval_seconds"),
        )

        st = self._last_run_state.get(rid, {})
        if "last_run_timestamp" not in st and schedule_type == "interval":
            self._last_run_state[rid] = {"last_run_timestamp": time.time(), "last_status": "IDLE"}
            st = self._last_run_state[rid]

        return {
            "id": rid,
            "agent": agent,
            "task": task,
            "description": desc,
            "schedule_type": schedule_type,
            "time": times[0] if len(times) == 1 else None,
            "times": times,
            "interval_seconds": interval_sec,
            "interval_hours": rule.get("interval_hours"),
            "interval_minutes": rule.get("interval_minutes"),
            "cron": rule.get("cron"),
            "days": days,
            "weekdays_only": bool(rule.get("weekdays_only", False)),
            "active_hours": rule.get("active_hours"),
            "enabled": bool(rule.get("enabled", True)),
            "notify": bool(rule.get("notify", False)),
            "payload": rule.get("payload") or {},
            "last_run_at": st.get("last_run_at"),
            "last_status": st.get("last_status", "IDLE"),
            "last_result": st.get("last_result", ""),
            "run_count": st.get("run_count", 0),
        }

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Returns all registered agent schedules with live execution states."""
        return list(self.schedules)

    def toggle_schedule(self, schedule_id: str, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles or sets the enabled status of a schedule."""
        for r in self.schedules:
            if r["id"] == schedule_id:
                new_state = (not r["enabled"]) if enabled is None else bool(enabled)
                r["enabled"] = new_state
                overrides = self.load_overrides()
                if schedule_id not in overrides:
                    overrides[schedule_id] = {}
                overrides[schedule_id]["enabled"] = new_state
                self.save_overrides(overrides)
                return {
                    "status": "success",
                    "id": schedule_id,
                    "enabled": new_state,
                    "message": f"Schedule '{schedule_id}' is now {'enabled' if new_state else 'disabled'}.",
                }
        return {"status": "error", "message": f"Schedule '{schedule_id}' not found."}

    def check_and_run(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Evaluates all enabled schedules against the provided or current datetime.
        Runs matching agent tasks and returns a list of results.
        """
        if now is None:
            now = datetime.now()

        today_date = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M")
        weekday_name = now.strftime("%A").lower()
        weekday_abbr = now.strftime("%a").lower()
        is_weekday = now.weekday() < 5
        now_ts = time.time()

        # Reset daily trigger cache on new day
        if self._last_day_str != today_date:
            self._triggered_today.clear()
            self._last_day_str = today_date

        results: List[Dict[str, Any]] = []

        for rule in self.schedules:
            if not rule.get("enabled", True):
                continue

            # Day of week filter
            if rule.get("weekdays_only") and not is_weekday:
                continue

            days = rule.get("days", [])
            if days and weekday_name not in days and weekday_abbr not in days:
                continue

            # Active hours filter: e.g. "08:00-18:00"
            active_h = rule.get("active_hours")
            if active_h and "-" in active_h:
                try:
                    start_h, end_h = active_h.split("-", 1)
                    if not (start_h.strip() <= current_time_str <= end_h.strip()):
                        continue
                except Exception:
                    pass

            stype = rule.get("schedule_type", "interval")
            should_run = False
            trigger_context = ""

            # 1. Time of Day
            if stype == "time_of_day":
                target_times = rule.get("times") or ([rule["time"]] if rule.get("time") else [])
                for t in target_times:
                    cache_key = (rule["id"], today_date, t)
                    if current_time_str >= t and cache_key not in self._triggered_today:
                        should_run = True
                        trigger_context = f"time_of_day:{t}"
                        self._triggered_today.add(cache_key)
                        break

            # 2. Interval
            elif stype == "interval":
                interval_sec = rule.get("interval_seconds", 3600)
                last_ts = self._last_run_state.get(rule["id"], {}).get("last_run_timestamp", 0.0)
                if (now_ts - last_ts) >= interval_sec:
                    should_run = True
                    trigger_context = f"interval:{interval_sec}s"

            # 3. Cron
            elif stype == "cron":
                cron_str = rule.get("cron", "")
                minute_key = (rule["id"], today_date, current_time_str)
                if cron_str and match_cron(cron_str, now) and minute_key not in self._triggered_today:
                    should_run = True
                    trigger_context = f"cron:{cron_str}"
                    self._triggered_today.add(minute_key)

            if should_run:
                res = self.run_task(rule, trigger_context=trigger_context, now=now)
                results.append(res)

        return results

    def run_task(
        self,
        rule: Dict[str, Any],
        trigger_context: str = "manual",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Executes a scheduled agent task deterministically (Tier 0: $0.00 / 0 Tokens).
        Dispatches via AgentRegistry, Event Bus, or dedicated agent worker handlers.
        """
        if now is None:
            now = datetime.now()

        rid = rule["id"]
        agent_id = rule.get("agent", "overview")
        task_name = rule.get("task", "run")
        payload = dict(rule.get("payload") or {})
        start_ts = time.time()

        result_data: Dict[str, Any] = {}
        status = "SUCCESS"
        error_msg = ""

        try:
            # 1. Check if agent instance exists in AgentRegistry
            agent_inst = None
            if self.registry:
                agent_inst = self.registry.agents.get(agent_id)

            if agent_inst and hasattr(agent_inst, "execute_task"):
                result_data = agent_inst.execute_task(task_name, payload)
            else:
                # 2. Built-in deterministic worker execution
                result_data = self._dispatch_builtin_agent_task(agent_id, task_name, payload, rule)

        except Exception as e:
            status = "ERROR"
            error_msg = str(e)
            result_data = {"error": error_msg}
            logger.error(f"Error executing scheduled task {rid}: {e}", exc_info=True, extra={"action": "scheduler_task_error", "agent": agent_id})

        duration = round(time.time() - start_ts, 3)
        now_iso = now.isoformat()

        # Update live state
        self._last_run_state[rid] = {
            "last_run_at": now_iso,
            "last_run_timestamp": time.time(),
            "last_status": status,
            "last_result": str(result_data.get("summary") or result_data.get("message") or status),
            "run_count": self._last_run_state.get(rid, {}).get("run_count", 0) + 1,
            "duration_sec": duration,
        }
        rule.update(self._last_run_state[rid])

        # Audit log in FleetDatabase
        try:
            self.db.log_activity(
                f"Scheduler:{agent_id}",
                f"schedule_{task_name}",
                f"{status} [{trigger_context}] duration: {duration}s: {str(result_data)[:140]}",
            )
        except Exception:
            pass

        # Optional Notification Dispatch
        if rule.get("notify", False) and status == "SUCCESS":
            title = result_data.get("title") or f"⏰ Fleet Schedule: {rule.get('description', task_name)}"
            msg = result_data.get("message") or f"Agent {agent_id} completed {task_name}."
            try:
                self.bus.dispatch(FleetEvent(
                    sender="FleetScheduler",
                    target="notification",
                    action="SEND_TOAST",
                    payload={"title": title, "message": msg},
                ))
            except Exception:
                send_windows_notification(title, msg)

        return {
            "id": rid,
            "agent": agent_id,
            "task": task_name,
            "status": status,
            "duration": duration,
            "timestamp": now_iso,
            "result": result_data,
        }

    def _dispatch_builtin_agent_task(
        self,
        agent_id: str,
        task_name: str,
        payload: Dict[str, Any],
        rule: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deterministic built-in dispatch logic for all 7 standard fleet agents."""
        t_low = task_name.lower()
        a_low = agent_id.lower()

        # 1. Overview Agent Tasks
        if a_low == "overview":
            if "briefing" in t_low or "morning" in t_low:
                from fleet.core.briefing import BriefingEngine
                be = BriefingEngine(self.db)
                data = be.generate_daily_briefing()
                stats = data.get("summary_stats", {})
                return {
                    "status": "success",
                    "title": "☀️ Good Morning! Daily Briefing Ready",
                    "message": f"{data.get('headline', '')} ({stats.get('pending_count', 0)} open tasks, {stats.get('p1_count', 0)} P1 priorities).",
                    "briefing": data,
                }
            elif "evening" in t_low or "review" in t_low:
                from fleet.core.briefing import BriefingEngine
                be = BriefingEngine(self.db)
                data = be.generate_daily_briefing()
                stats = data.get("summary_stats", {})
                return {
                    "status": "success",
                    "title": "🌙 Evening Review Time",
                    "message": f"You completed {stats.get('completed_count', 0)} tasks today ({stats.get('completion_rate', 0)}%). Time to wrap up!",
                    "briefing": data,
                }

        # 2. Health Agent Tasks
        elif a_low == "health":
            health_messages = {
                "smoothie_reminder": ("🥤 Early Morning Smoothie Time", "Drink your 250ml Green/White Smoothie on empty stomach with methi, cinnamon & haldi."),
                "breakfast_meds": ("🥗 Breakfast & Morning Prescriptions", "25-25-50% Breakfast! Take your scheduled morning supplements."),
                "lunch_meds": ("🍲 Lunch & Afternoon Prescriptions", "25% Quad Plate (Salad, Veg, Dal, Grain). Take your scheduled afternoon supplements."),
                "afternoon_snack": ("🥜 Afternoon Smoothie & Soaked Nuts", "250ml Smoothie + 5-6 soaked almonds, 4-5 walnuts & 4 tsp mixed seeds."),
                "dinner_meds": ("🍽️ Early Dinner & Evening Prescriptions", "Finish dinner before 8:30 PM (4th morsel rule). Take your scheduled evening supplements."),
                "sleep_recovery": ("💤 Sleep & Metabolic Recovery", "Wind down screens! Aim for 7-8 hours sound rest. In bed by 11:00 PM latest."),
            }
            if t_low in health_messages:
                title, msg = health_messages[t_low]
                return {"status": "success", "title": title, "message": msg}
            elif "routine" in t_low:
                routines = self.db.list_routines()
                pending = [r for r in routines if not r.get("completed_today")]
                return {
                    "status": "success",
                    "title": f"📋 Daily Routines: {len(pending)} Remaining",
                    "message": f"{len(pending)} uncompleted routine(s) today.",
                    "pending_routines": pending,
                }

        # 3. PC Optimizer Agent Tasks
        elif a_low == "optimizer":
            from fleet.core.optimizer import flush_dns_cache, get_memory_status, optimize_ram
            res_opt = optimize_ram()
            res_dns = flush_dns_cache()
            mem = get_memory_status()
            return {
                "status": "success",
                "title": "🚀 PC Optimizer Pulse Complete",
                "message": f"RAM Optimized ({mem.get('percent_used', 0)}% used), DNS Cache Cleared.",
                "memory": mem,
                "ram_result": res_opt,
                "dns_result": res_dns,
            }

        # 4. Gmail Agent Tasks
        elif a_low == "gmail":
            res = self.bus.dispatch(FleetEvent(
                sender="FleetScheduler",
                target="email",
                action="CLASSIFY_RECENT",
                payload={"dry_run": False},
            ))
            counts = res.get("data", {}).get("counts", {}) if res.get("status") == "success" else {}
            return {
                "status": res.get("status", "success"),
                "title": "📬 Gmail Triage Pulse",
                "message": f"Gmail Pulse: Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}",
                "counts": counts,
            }

        # 5. Antigravity Agent Tasks
        elif a_low == "antigravity":
            from fleet.core.antigravity_mirror import get_token_health, process_next_in_queue
            process_next_in_queue()
            th = get_token_health()
            return {
                "status": "success",
                "title": "🤖 Antigravity Queue & Token Pulse",
                "message": f"Queue processed. Tokens: {th.get('percent_used', 0)}% used ({th.get('status', 'Optimal')}).",
                "token_health": th,
            }

        # 6. Backlog Agent Tasks
        elif a_low == "backlog":
            stats = self.db.get_feature_backlog_stats()
            return {
                "status": "success",
                "title": "📋 Feature Backlog Hygiene",
                "message": f"Backlog: {stats.get('total', 0)} items ({stats.get('in_progress', 0)} in progress, {stats.get('todo', 0)} todo).",
                "stats": stats,
            }

        # 7. PR Review Agent Tasks
        elif a_low == "pr_review":
            from fleet.agents.pr_review.agent import PRReviewAgent
            agent = PRReviewAgent()
            audit_res = agent.audit_pull_requests()
            ci_res = agent.check_ci_status()
            return {
                "status": "success",
                "title": "🛡️ PR & CI Quality Gate",
                "message": f"Open PRs: {audit_res.get('open_count', 0)}, CI Status: {ci_res.get('status', 'UNKNOWN')}",
                "audit": audit_res,
                "ci": ci_res,
            }

        # General Event Bus Dispatch Fallback
        res = self.bus.dispatch(FleetEvent(
            sender="FleetScheduler",
            target=agent_id,
            action=task_name.upper(),
            payload=payload,
        ))
        return {
            "status": res.get("status", "success"),
            "data": res.get("data", {}),
            "message": res.get("message", f"Dispatched {task_name} to {agent_id}"),
        }

    def run_now(
        self,
        schedule_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        task: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually runs a schedule or agent task immediately on demand."""
        target_rule = None
        if schedule_id:
            for r in self.schedules:
                if r["id"] == schedule_id:
                    target_rule = r
                    break

        if not target_rule:
            if agent_id and task:
                target_rule = {
                    "id": f"{agent_id}_{task}_adhoc",
                    "agent": agent_id,
                    "task": task,
                    "schedule_type": "ad_hoc",
                    "enabled": True,
                    "notify": True,
                }
            elif schedule_id:
                return {"status": "error", "message": f"Schedule '{schedule_id}' not found."}
            else:
                return {"status": "error", "message": "Either schedule_id or both agent and task are required."}

        return self.run_task(target_rule, trigger_context="manual_api_trigger")


# Singleton Scheduler Instance
_GLOBAL_SCHEDULER: Optional[FleetScheduler] = None


def get_fleet_scheduler(reload: bool = False) -> FleetScheduler:
    """Returns the singleton FleetScheduler instance."""
    global _GLOBAL_SCHEDULER
    if _GLOBAL_SCHEDULER is None:
        _GLOBAL_SCHEDULER = FleetScheduler()
    elif reload:
        _GLOBAL_SCHEDULER.reload()
    return _GLOBAL_SCHEDULER
