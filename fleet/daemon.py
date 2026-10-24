"""
Background Routine Daemon for Personal Agentic Fleet.
Monitors daily times to trigger proactive Windows Toast notifications for:
- 08:30 AM: Morning Briefing with top priorities
- 08:00 PM: Evening Wrap-up and reflection
Runs quietly in the background on your Windows laptop.
"""

import sys
import time
from datetime import datetime

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
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

    def check_and_trigger(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_date = now.strftime("%Y-%m-%d")

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
            try:
                from fleet.tools.test_runner import run_test_suite_isolated
                print(f"[{now.strftime('%H:%M:%S')}] Running scheduled unit test suite and coverage pulse in isolated child process...")
                db_inst = getattr(self.bus, "db", None) or FleetDatabase()
                run_test_suite_isolated(db_inst)
                self.last_test_run_time = now_ts
            except Exception as e:
                print(f"[{now.strftime('%H:%M:%S')}] Test runner daemon error: {e}")

        # 5. Scheduled Automated Security & Privacy Audit Pulse (Every 60 mins by default)
        if (now_ts - self.last_security_scan_time) >= self.security_scan_interval_sec:
            self.run_scheduled_security_scan(now)
            self.last_security_scan_time = now_ts

    def run_scheduled_security_scan(self, now: datetime = None):
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
            db_inst = getattr(self.bus, "db", None) or FleetDatabase()
            db_inst.log_activity(
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

