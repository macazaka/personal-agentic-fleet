from typing import Any, Dict, Optional
"""
Background Routine Daemon for Personal Agentic Fleet.
Monitors daily times to trigger proactive Windows Toast notifications for:
- 08:30 AM: Morning Briefing with top priorities
- 08:00 PM: Evening Wrap-up and reflection
Runs quietly in the background on your Windows laptop.
"""

import gc
import logging
import sys
import time
from datetime import datetime

logger = logging.getLogger("fleet.daemon")

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
        getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fleet.config import BRIEFING_TIME, EVENING_REVIEW_TIME, TIMEZONE_NAME
from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.tools.system_tools import send_windows_notification


class FleetDaemon:
    def __init__(self):
        from fleet.core.event_bus import bus
        self.bus = bus
        self.db = getattr(self.bus, "db", None) or FleetDatabase()
        from fleet.core.scheduler import get_fleet_scheduler
        self.scheduler = get_fleet_scheduler()
        self.last_briefing_date = ""
        self.last_evening_date = ""
        self.last_email_sync_hour = -1
        self.last_test_run_time = time.time()
        self.test_run_interval_sec = 1800  # 30 minutes
        from fleet.config import load_fleet_config
        sec_cfg = load_fleet_config().get("security", {})
        scan_mins = int(sec_cfg.get("scan_interval_minutes", 60))
        self.security_scan_interval_sec = max(60, scan_mins * 60)
        self.last_security_scan_time = time.time()
        self.health_reminders_triggered = set()
        self.last_reminder_reset_date = ""
        self.pr_review_interval_sec = 3600  # 1 hour
        self.last_pr_review_time = time.time()
        # Proactive Log Scan & Autonomous Self-Healing Pulse (Every 15 minutes by default)
        self.log_scan_interval_sec = 900  # 15 minutes
        self.last_log_scan_time = time.time() - 885
        # Cognitive Mind Cycles (Subconscious Dream & Soul Alignment)
        self.last_dream_date = ""
        self.last_soul_audit_time = time.time()
        self.soul_audit_interval_sec = 7200  # 2 hours
        self.last_pipeline_timeout_check = time.time() - 60
        self.pipeline_timeout_check_interval_sec = 90
        self.last_sentinel_triggered_sha = ""
        # Resource-Aware Pulse Deferral & Periodic Working-Set Memory Trim
        self.last_memory_trim_time = time.time()
        self.memory_trim_interval_sec = 900  # 15 minutes
        self._pulse_deferrals: Dict[str, int] = {}

    def _get_db(self) -> FleetDatabase:
        """Returns the shared FleetDatabase instance without redundant constructor/migration overhead."""
        return getattr(self.bus, "db", None) or self.db

    @staticmethod
    def _is_battery_power_low() -> bool:
        """Checks Windows battery/power-saver state without external packages (POSIX returns False)."""
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]
            sps = SYSTEM_POWER_STATUS()
            windll = getattr(ctypes, "windll", None)
            if windll and windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                ac_offline = int(sps.ACLineStatus) == 0
                pct = int(sps.BatteryLifePercent)
                saver_on = int(sps.SystemStatusFlag) == 1
                if saver_on:
                    return True
                if ac_offline and 0 < pct <= 25:
                    return True
        except Exception:
            pass
        return False

    def _should_defer_heavy_pulse(
        self,
        task_key: str,
        ram_threshold_pct: float = 85.0,
        max_deferrals: int = 3,
    ) -> bool:
        """
        Defers heavy background pulses (pytest, security scan, dream cycle) when system RAM >= threshold
        or battery saver / low battery / wake cooldown is active, with an anti-starvation cap.
        """
        defer_count = int(self._pulse_deferrals.get(task_key, 0))
        if defer_count >= max_deferrals:
            self._pulse_deferrals[task_key] = 0
            return False

        under_pressure = False
        try:
            from fleet.core.optimizer import get_memory_status
            mem = get_memory_status()
            if float(mem.get("percent_used", 0)) >= ram_threshold_pct:
                under_pressure = True
        except Exception:
            pass

        if not under_pressure:
            try:
                from fleet.core.power import power_manager
                if getattr(power_manager, "is_in_cooldown", False):
                    under_pressure = True
            except Exception:
                pass

        if not under_pressure and self._is_battery_power_low():
            under_pressure = True

        if under_pressure:
            self._pulse_deferrals[task_key] = defer_count + 1
            return True

        self._pulse_deferrals[task_key] = 0
        return False

    def _trim_idle_working_set(self) -> Dict[str, Any]:
        """Collects generational garbage, prunes dead-thread SQLite pools, and trims OS working set."""
        collected = 0
        pruned_conns = 0
        ws_trimmed = False
        try:
            collected = int(gc.collect(1))
        except Exception:
            pass
        try:
            from fleet.core.db.pool import prune_dead_thread_connections
            pruned_conns = int(prune_dead_thread_connections())
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import ctypes
                windll = getattr(ctypes, "windll", None)
                if windll:
                    handle = windll.kernel32.GetCurrentProcess()
                    ws_trimmed = bool(windll.kernel32.SetProcessWorkingSetSize(handle, ctypes.c_size_t(-1), ctypes.c_size_t(-1)))
            except Exception:
                pass
        return {
            "gc_collected": collected,
            "pruned_connections": pruned_conns,
            "working_set_trimmed": ws_trimmed,
        }

    def check_and_trigger(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_date = now.strftime("%Y-%m-%d")

        # 0. Unified Agent Scheduling Engine (YAML & Default Schedules)
        if hasattr(self, "scheduler") and self.scheduler:
            try:
                self.scheduler.check_and_run(now)
            except Exception as e:
                logger.error("Scheduler execution error in FleetDaemon: %s", e, exc_info=True)

        # 1. Morning Briefing Check (08:30)
        if current_time >= BRIEFING_TIME and self.last_briefing_date != today_date:
            from fleet.core.event_bus import FleetEvent
            # Request briefing from agenda worker via Event Bus (A2A)
            event = FleetEvent(sender="FleetDaemon", target="agenda", action="GET_BRIEFING")
            res = self.bus.dispatch(event)
            if res["status"] == "success":
                briefing = res["data"]
                stats = briefing["summary_stats"]
                headline = briefing["headline"]
                toast_title = "☀️ Good Morning! Daily Briefing Ready"
                toast_msg = f"{headline} ({stats['pending_count']} open tasks, {stats['p1_count']} P1 priorities)."
                
                # Send notification via Event Bus (A2A)
                notify_event = FleetEvent(
                    sender="FleetDaemon",
                    target="notification",
                    action="SEND_TOAST",
                    payload={"title": toast_title, "message": toast_msg}
                )
                self.bus.dispatch(notify_event)
                self.last_briefing_date = today_date
                print(f"[{now.strftime('%H:%M:%S')}] Delivered Morning Briefing Toast Notification via Event Bus.")

        # 2. Evening Wrap-Up Check (20:00)
        if current_time >= EVENING_REVIEW_TIME and self.last_evening_date != today_date:
            from fleet.core.event_bus import FleetEvent
            event = FleetEvent(sender="FleetDaemon", target="agenda", action="GET_BRIEFING")
            res = self.bus.dispatch(event)
            if res["status"] == "success":
                stats = res["data"]["summary_stats"]
                toast_title = "🌙 Evening Review Time"
                toast_msg = f"You completed {stats['completed_count']} tasks today ({stats['completion_rate']}%). Time to wrap up!"
                
                notify_event = FleetEvent(
                    sender="FleetDaemon",
                    target="notification",
                    action="SEND_TOAST",
                    payload={"title": toast_title, "message": toast_msg}
                )
                self.bus.dispatch(notify_event)
                self.last_evening_date = today_date
                print(f"[{now.strftime('%H:%M:%S')}] Delivered Evening Review Toast Notification via Event Bus.")


        # Reset health reminders on new day
        if self.last_reminder_reset_date != today_date:
            self.health_reminders_triggered.clear()
            self.last_reminder_reset_date = today_date

        # Proactive FFD Health & Metabolic Routine Reminders
        ffd_alerts = [
            ("07:15", "ffd_smoothie", "🥤 Early Morning Smoothie Time", "Drink your 250ml Green/White Smoothie on empty stomach with methi, cinnamon & haldi."),
            ("08:30", "ffd_breakfast_meds", "🥗 Breakfast & Morning Prescriptions", "25-25-50% Breakfast! Take your scheduled morning supplements."),
            ("13:30", "ffd_lunch_meds", "🍲 Lunch & Afternoon Prescriptions", "25% Quad Plate (Salad, Veg, Dal, Grain). Take your scheduled afternoon supplements."),
            ("16:15", "ffd_snack", "🥜 Afternoon Smoothie & Soaked Nuts", "250ml Smoothie + 5-6 soaked almonds, 4-5 walnuts & 4 tsp mixed seeds."),
            ("19:30", "ffd_dinner_meds", "🍽️ Early Dinner & Evening Prescriptions", "Finish dinner before 8:30 PM (4th morsel rule). Take your scheduled evening supplements."),
            ("22:30", "ffd_sleep", "💤 Sleep & Metabolic Recovery", "Wind down screens! Aim for 7-8 hours sound rest. In bed by 11:00 PM latest."),
        ]
        for rem_time, rem_key, rem_title, rem_msg in ffd_alerts:
            if current_time >= rem_time and rem_key not in self.health_reminders_triggered:
                try:
                    from fleet.core.event_bus import FleetEvent
                    self.bus.dispatch(FleetEvent(
                        sender="FleetDaemon",
                        target="notification",
                        action="SEND_TOAST",
                        payload={"title": rem_title, "message": rem_msg}
                    ))
                    self.health_reminders_triggered.add(rem_key)
                    print(f"[{now.strftime('%H:%M:%S')}] Delivered Health Routine Reminder: {rem_title}")
                except Exception as e:
                    print(f"Health reminder dispatch error: {e}")

        # 3. Scheduled Email Classification Pulse (Every 2 hours during workday: 08:00 - 18:00)
        current_hour = now.hour
        if 8 <= current_hour <= 18 and (current_hour % 2 == 0) and self.last_email_sync_hour != current_hour:
            from fleet.core.event_bus import FleetEvent
            print(f"[{now.strftime('%H:%M:%S')}] Triggering 2-hour pulse Gmail classification via Event Bus...")
            res = self.bus.dispatch(FleetEvent(
                sender="FleetDaemon",
                target="email",
                action="CLASSIFY_RECENT",
                payload={"dry_run": False}
            ))
            if res["status"] == "success":
                counts = res["data"].get("counts", {})
                print(f"[{now.strftime('%H:%M:%S')}] Gmail pulse complete. Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}")
            self.last_email_sync_hour = current_hour

        # 4. Scheduled Unit Test Suite & Code Coverage Pulse (Every 30 mins)
        now_ts = time.time()
        if (now_ts - self.last_test_run_time) >= self.test_run_interval_sec:
            if self._should_defer_heavy_pulse("test_suite"):
                logger.info("[FleetDaemon] Deferring heavy test_suite pulse by 5m due to high RAM / low power.")
                self.last_test_run_time = now_ts - self.test_run_interval_sec + 300
            else:
                try:
                    from fleet.tools.test_runner import run_test_suite_isolated
                    print(f"[{now.strftime('%H:%M:%S')}] Running scheduled unit test suite and coverage pulse in isolated child process...")
                    run_test_suite_isolated(self._get_db())
                    self.last_test_run_time = now_ts
                except Exception as e:
                    print(f"[{now.strftime('%H:%M:%S')}] Test runner daemon error: {e}")

        # 5. Scheduled Automated Security & Privacy Audit Pulse (Every 60 mins by default)
        if (now_ts - self.last_security_scan_time) >= self.security_scan_interval_sec:
            if self._should_defer_heavy_pulse("security_scan"):
                logger.info("[FleetDaemon] Deferring heavy security_scan pulse by 5m due to high RAM / low power.")
                self.last_security_scan_time = now_ts - self.security_scan_interval_sec + 300
            else:
                self.run_scheduled_security_scan(now)
                self.last_security_scan_time = now_ts

        # 6. Scheduled Admin PR Review & CI Quality Gate Pulse (Every 60 mins)
        if (now_ts - self.last_pr_review_time) >= self.pr_review_interval_sec:
            self.run_scheduled_pr_review(now)
            self.last_pr_review_time = now_ts
        if (now_ts - getattr(self, "last_pipeline_timeout_check", 0.0)) >= getattr(self, "pipeline_timeout_check_interval_sec", 90):
            self.run_post_commit_timeout_sentinel_check(now)
            self.last_pipeline_timeout_check = now_ts

        # 7. Automated Daily Database Snapshot Backup (ROB-04)
        if current_time >= "03:00" and getattr(self, "last_backup_date", "") != today_date:
            try:
                from fleet.core.db.backup import perform_database_backup, prune_old_backups
                perform_database_backup()
                prune_old_backups()
                self.last_backup_date = today_date
                print(f"[{now.strftime('%H:%M:%S')}] Daily automated SQLite snapshot backup successfully created.")
            except Exception as e:
                print(f"Backup error: {e}")

        # 8. Flush offline spooled events if network is restored (ROB-15)
        if (now_ts - getattr(self, "last_spool_flush_time", 0.0)) >= 120.0:
            try:
                from fleet.core.network_spool import flush_offline_spool
                flush_offline_spool(self.bus)
                self.last_spool_flush_time = now_ts
            except Exception:
                pass

        # 9. Scheduled Proactive Log Scan & Autonomous Improvements Pulse (Every 15 mins)
        if (now_ts - getattr(self, "last_log_scan_time", 0.0)) >= self.log_scan_interval_sec:
            self.run_scheduled_log_scan_and_heal(now)
            self.last_log_scan_time = now_ts

        # 10. Subconscious Memory Consolidation Dream Cycle (Nightly during 23:00 - 06:00 window)
        if (now.hour >= 23 or now.hour < 6) and getattr(self, "last_dream_date", "") != today_date:
            if self._should_defer_heavy_pulse("dream_cycle"):
                logger.info("[FleetDaemon] Deferring dream_cycle due to high RAM / low power.")
            else:
                try:
                    from fleet.core.mind import fleet_mind
                    fleet_mind.set_db(self._get_db())
                    dream_report = fleet_mind.dream()
                    self.last_dream_date = today_date
                    print(f"[{now.strftime('%H:%M:%S')}] Subconscious Dream Cycle complete ({dream_report.get('insights_synthesized_count', 0)} insights synthesized).")
                except Exception as e:
                    logger.debug("Dream cycle daemon warning: %s", e)

        # 11. Soul Moral Alignment Audit (Every 2 hours)
        if (now_ts - getattr(self, "last_soul_audit_time", 0.0)) >= getattr(self, "soul_audit_interval_sec", 7200):
            try:
                from fleet.core.mind import fleet_mind
                fleet_mind.set_db(self._get_db())
                audit = fleet_mind.audit_soul()
                self.last_soul_audit_time = now_ts
                if audit.status in ("DRIFTING", "DISCORDANT"):
                    print(f"[{now.strftime('%H:%M:%S')}] Soul Alignment Warning: {audit.status} ({audit.alignment_score}/100)")
            except Exception as e:
                logger.debug("Soul audit daemon warning: %s", e)

        # 12. Periodic Idle Working-Set Memory Trim & Dead-Thread Pool Prune (Every 15 mins)
        if (now_ts - getattr(self, "last_memory_trim_time", 0.0)) >= getattr(self, "memory_trim_interval_sec", 900):
            self._trim_idle_working_set()
            self.last_memory_trim_time = now_ts

    def run_scheduled_log_scan_and_heal(self, now: Optional[datetime] = None):
        """Proactively scans logs, ring buffer and crash dumps, executing autonomous improvements."""
        if now is None:
            now = datetime.now()
        try:
            from fleet.core.auto_healer import run_proactive_log_scan_and_heal
            report = run_proactive_log_scan_and_heal(db=self._get_db())
            imp_count = report.get("improvements_applied_count", 0)
            if imp_count > 0:
                print(f"[{now.strftime('%H:%M:%S')}] Proactive Auto-Healer: {imp_count} autonomous improvement(s) applied.")
                from fleet.core.event_bus import FleetEvent
                self.bus.dispatch(FleetEvent(
                    sender="FleetDaemon",
                    target="notification",
                    action="SEND_TOAST",
                    payload={
                        "title": f"🛠️ Auto-Healer: {imp_count} Improvement(s) Applied",
                        "message": f"Autonomous log analysis resolved {imp_count} diagnostic issue(s). Health score: {report.get('system_health_index')}/100.",
                    }
                ))
            return report
        except Exception as e:
            logger.error("Proactive log scan error in FleetDaemon: %s", e, exc_info=True)
            return {"status": "ERROR", "message": str(e)}


    def run_post_commit_timeout_sentinel_check(self, now: Optional[datetime] = None):
        """
        Proactively checks if the latest local HEAD commit has passed the post-push timeout (120s)
        without a complete GitHub Pipeline & CodeQL audit, and triggers a background sentinel scan.
        """
        if now is None:
            now = datetime.now()
        try:
            import json
            from fleet.tools.github_pipeline_sentinel import (
                AUDIT_REPORT_PATH,
                REPO_ROOT,
                get_local_head_sha,
                spawn_detached_post_push_sentinel,
            )

            head_sha = get_local_head_sha(REPO_ROOT)
            if not head_sha or head_sha == getattr(self, "last_sentinel_triggered_sha", ""):
                return

            needs_audit = True
            if AUDIT_REPORT_PATH.is_file():
                try:
                    rep = json.loads(AUDIT_REPORT_PATH.read_text(encoding="utf-8"))
                    rep_sha = str(rep.get("commit_sha") or "").strip().lower()
                    in_prog = int(rep.get("checks_in_progress") or 0)
                    total_chk = int(rep.get("checks_total") or 0)
                    if rep_sha.startswith(head_sha[:7]) and in_prog == 0 and total_chk >= 8:
                        needs_audit = False
                except Exception:
                    needs_audit = True

            if needs_audit:
                if spawn_detached_post_push_sentinel(repo_root=REPO_ROOT, commit_sha=head_sha, initial_delay_sec=15):
                    self.last_sentinel_triggered_sha = head_sha
                    logger.info("Triggered proactive post-commit timeout GitHub Sentinel audit for %s", head_sha[:7])
        except Exception as exc:
            logger.debug("Post-commit timeout sentinel check note: %s", exc)

    def run_scheduled_pr_review(self, now: Optional[datetime] = None):
        """Audits open PRs and CI status deterministically (Admin Only, 0 tokens)."""
        if now is None:
            now = datetime.now()
        try:
            from fleet.agents.pr_review.agent import PRReviewAgent
            agent = PRReviewAgent()
            audit_res = agent.audit_pull_requests()
            ci_res = agent.check_ci_status()
            open_count = audit_res.get("open_count", 0)
            if open_count > 0:
                print(f"[{now.strftime('%H:%M:%S')}] Admin PR Gate: {open_count} open PR(s) detected.")
            if ci_res.get("status") == "FAILING":
                fail_count = len(ci_res.get("failing_runs", []))
                print(f"[{now.strftime('%H:%M:%S')}] Admin CI Monitor: {fail_count} failing workflow run(s) on main.")
        except Exception as e:
            print(f"[{now.strftime('%H:%M:%S')}] PR review daemon error: {e}")
    def run_scheduled_security_scan(self, now: Optional[datetime] = None):
        """Runs the zero-token 6-layer security & privacy audit and alerts via Windows Toast on findings."""
        if now is None:
            now = datetime.now()
        try:
            from fleet.tools.security_scanner import run_security_scan
            from fleet.core.event_bus import FleetEvent
            print(f"[{now.strftime('%H:%M:%S')}] Running scheduled 6-layer Security & Privacy Audit...")
            report = run_security_scan()
            score = report.get("score", 0)
            status = report.get("status", "UNKNOWN")
            findings_count = report.get("total_findings", 0)
            self._get_db().log_activity(
                "SecurityScanner",
                "scheduled_scan",
                f"Automated Security Audit: Score {score}/100 [{status}] ({findings_count} findings)"
            )
            if status != "PASS" or findings_count > 0:
                self.bus.dispatch(FleetEvent(
                    sender="FleetDaemon",
                    target="notification",
                    action="SEND_TOAST",
                    payload={
                        "title": f"🛡️ Security Alert: {findings_count} Finding(s) Detected",
                        "message": f"Automated Security Scan Score: {score}/100 [{status}]. Check dashboard security report."
                    }
                ))
            return report
        except Exception as e:
            print(f"[{now.strftime('%H:%M:%S')}] Security scanner daemon error: {e}")
            return {"status": "ERROR", "message": str(e)}

    def run_loop(self, poll_interval_sec: int = 30):
        print(f"Fleet Daemon active ({TIMEZONE_NAME}).")
        print(f"  • Morning Briefing scheduled for:  {BRIEFING_TIME} {TIMEZONE_NAME}")
        print(f"  • Evening Review scheduled for:    {EVENING_REVIEW_TIME} {TIMEZONE_NAME}")
        print(f"  • Gmail Classification Pulse:      Every 2 hours (08:00 - 18:00 {TIMEZONE_NAME})")
        while True:
            try:
                self.check_and_trigger()
                time.sleep(poll_interval_sec)
            except KeyboardInterrupt:
                print("Daemon stopped.")
                break
            except Exception as e:
                print(f"Daemon error: {e}")
                time.sleep(10)


if __name__ == "__main__":
    daemon = FleetDaemon()
    daemon.run_loop()

