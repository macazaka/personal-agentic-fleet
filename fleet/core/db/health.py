"""
Health & Wellness domain repository mixin for FleetDatabase.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fleet.core.db.base import BaseDatabase
    _DbBase = BaseDatabase
else:
    _DbBase = object


class HealthMixin(_DbBase):
    # --- Health & Wellness Operations ---
    def get_today_hydration(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves hydration progress for the given date (default today YYYY-MM-DD in IST).
        Calculates percentage towards goal, glasses, and minutes since last glass.
        """
        now = datetime.now()
        date_str = target_date or now.strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hydration_logs WHERE date = ?", (date_str,))
            row = cursor.fetchone()
            if not row:
                goal = 2500
                cursor.execute("""
                    INSERT INTO hydration_logs (date, glasses, amount_ml, goal_ml, last_drank_at, updated_at)
                    VALUES (?, 0, 0, ?, '', ?)
                """, (date_str, goal, now.isoformat()))
                conn.commit()
                return {
                    "date": date_str,
                    "glasses": 0,
                    "amount_ml": 0,
                    "goal_ml": goal,
                    "percentage": 0.0,
                    "last_drank_at": "",
                    "next_reminder_min": 45,
                    "reminder_status": "💧 Time for a glass of water!"
                }
            d = dict(row)
            glasses = d["glasses"]
            amount_ml = d["amount_ml"]
            goal_ml = d["goal_ml"] or 2500
            pct = round(min(100.0, (amount_ml / goal_ml) * 100), 1) if goal_ml > 0 else 0.0
            last_drank = d.get("last_drank_at") or ""

            next_min = 45
            status_text = "Hydration on track"
            if last_drank:
                try:
                    last_dt = datetime.fromisoformat(last_drank)
                    diff_mins = int((now - last_dt).total_seconds() / 60)
                    next_min = max(0, 45 - diff_mins)
                    if next_min == 0:
                        status_text = "💧 Reminder: Time to drink water!"
                    else:
                        status_text = f"Next glass in {next_min} min"
                except Exception:
                    pass
            else:
                status_text = "💧 Time for your first glass today!"

            return {
                "date": date_str,
                "glasses": glasses,
                "amount_ml": amount_ml,
                "goal_ml": goal_ml,
                "percentage": pct,
                "last_drank_at": last_drank,
                "next_reminder_min": next_min,
                "reminder_status": status_text
            }

    def log_water_intake(self, glasses_delta: int = 1, amount_delta_ml: int = 250,
                         target_date: Optional[str] = None) -> Dict[str, Any]:
        """Logs water intake (increment or decrement) for today."""
        now = datetime.now()
        date_str = target_date or now.strftime("%Y-%m-%d")
        now_str = now.isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hydration_logs WHERE date = ?", (date_str,))
            row = cursor.fetchone()
            if not row:
                goal = 2500
                new_glasses = max(0, glasses_delta)
                new_amount = max(0, amount_delta_ml)
                cursor.execute("""
                    INSERT INTO hydration_logs (date, glasses, amount_ml, goal_ml, last_drank_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (date_str, new_glasses, new_amount, goal, now_str if new_glasses > 0 else "", now_str))
            else:
                cur_glasses = row["glasses"]
                cur_amount = row["amount_ml"]
                new_glasses = max(0, cur_glasses + glasses_delta)
                new_amount = max(0, cur_amount + amount_delta_ml)
                last_drank = now_str if glasses_delta > 0 else (row["last_drank_at"] or "")
                cursor.execute("""
                    UPDATE hydration_logs
                    SET glasses = ?, amount_ml = ?, last_drank_at = ?, updated_at = ?
                    WHERE date = ?
                """, (new_glasses, new_amount, last_drank, now_str, date_str))

            if amount_delta_ml > 0:
                cursor.execute("""
                    INSERT INTO health_metrics (date, metric_type, value, unit, notes, created_at)
                    VALUES (?, 'water_ml', ?, 'ml', 'Water log', ?)
                """, (date_str, float(amount_delta_ml), now_str))

            conn.commit()
            self.log_activity("HealthManager", "water_intake", f"Logged {glasses_delta:+d} glass(es) ({amount_delta_ml:+d} ml) for {date_str}")
        return self.get_today_hydration(date_str)

    def set_hydration_goal(self, goal_ml: int, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Updates the daily hydration goal."""
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hydration_logs (date, glasses, amount_ml, goal_ml, last_drank_at, updated_at)
                VALUES (?, 0, 0, ?, '', ?)
                ON CONFLICT(date) DO UPDATE SET goal_ml = excluded.goal_ml, updated_at = excluded.updated_at
            """, (date_str, max(500, goal_ml), now_str))
            conn.commit()
        return self.get_today_hydration(date_str)

    def list_medications(self, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists all active medications and checks whether each has been taken today (or target_date).
        """
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, l.status as log_status, l.taken_at
                FROM medications m
                LEFT JOIN medication_logs l ON m.id = l.medication_id AND l.date = ?
                WHERE m.active = 1
                ORDER BY m.schedule_time ASC, m.id ASC
            """, (date_str,))
            rows = cursor.fetchall()
            meds = []
            for r in rows:
                d = dict(r)
                d["taken_today"] = bool(d.get("log_status") == "taken")
                meds.append(d)
            return meds

    def add_medication(self, name: str, dosage: str = "", schedule_time: str = "09:00",
                       frequency: str = "Daily", instructions: str = "") -> int:
        """Adds a new medication or supplement to schedule."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO medications (name, dosage, schedule_time, frequency, instructions, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (name.strip(), dosage.strip(), schedule_time.strip(), frequency.strip(), instructions.strip(), now_str))
            conn.commit()
            med_id = cursor.lastrowid or 0
            self.log_activity("HealthManager", "add_medication", f"Added medication #{med_id}: {name.strip()} ({dosage.strip()} at {schedule_time})")
            return med_id

    def toggle_medication_today(self, medication_id: int, target_date: Optional[str] = None) -> bool:
        """
        Toggles taken status for a medication on target_date (default today in IST).
        Returns True if now marked taken, False if unmarked.
        """
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM medication_logs
                WHERE medication_id = ? AND date = ?
            """, (medication_id, date_str))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    DELETE FROM medication_logs
                    WHERE medication_id = ? AND date = ?
                """, (medication_id, date_str))
                conn.commit()
                self.log_activity("HealthManager", "medication_toggle", f"Unmarked medication #{medication_id} for {date_str}")
                return False
            else:
                cursor.execute("""
                    INSERT INTO medication_logs (medication_id, date, status, taken_at)
                    VALUES (?, ?, 'taken', ?)
                """, (medication_id, date_str, now_str))
                conn.commit()
                self.log_activity("HealthManager", "medication_toggle", f"Marked medication #{medication_id} taken for {date_str}")
                return True

    def delete_medication(self, medication_id: int) -> bool:
        """Deactivates/deletes a medication."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE medications SET active = 0 WHERE id = ?", (medication_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_medication(self, medication_id: int, **kwargs) -> bool:
        """Updates fields (frequency, dosage, schedule_time, instructions, name) of an existing medication."""
        allowed = {"name", "dosage", "schedule_time", "frequency", "instructions"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE medications
                SET name = COALESCE(?, name),
                    dosage = COALESCE(?, dosage),
                    schedule_time = COALESCE(?, schedule_time),
                    frequency = COALESCE(?, frequency),
                    instructions = COALESCE(?, instructions)
                WHERE id = ?
                """,
                (
                    updates.get("name"),
                    updates.get("dosage"),
                    updates.get("schedule_time"),
                    updates.get("frequency"),
                    updates.get("instructions"),
                    medication_id,
                ),
            )
            conn.commit()
            self.log_activity("HealthManager", "medication_update", f"Updated medication #{medication_id}: {updates}")
            return cursor.rowcount > 0

    def log_health_metric(self, metric_type: str, value: float, unit: str = "",
                          notes: str = "", target_date: Optional[str] = None) -> int:
        """Logs a vitals or health metric (sleep, steps, resting_hr, weight, etc.)."""
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO health_metrics (date, metric_type, value, unit, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, metric_type.strip(), float(value), unit.strip(), notes.strip(), now_str))
            conn.commit()
            metric_id = cursor.lastrowid or 0
            self.log_activity("HealthManager", "log_metric", f"Logged {metric_type}: {value} {unit} for {date_str}")
            return metric_id

    def get_health_trends(self, metric_type: Optional[str] = "water_ml", days: int = 7) -> List[Dict[str, Any]]:
        """
        Returns daily historical trend data points for the specified metric over the past N days.
        Aggregates by date if multiple entries exist on the same date.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, metric_type, AVG(value) as avg_value, MAX(value) as max_value, SUM(value) as total_value, unit
                FROM health_metrics
                WHERE metric_type = ?
                GROUP BY date, metric_type, unit
                ORDER BY date ASC
                LIMIT ?
            """, (metric_type, days))
            rows = cursor.fetchall()
            points = []
            for r in rows:
                val = r["total_value"] if metric_type in ("water_ml", "steps") else r["avg_value"]
                points.append({
                    "date": r["date"],
                    "metric_type": r["metric_type"],
                    "value": round(float(val), 1) if val is not None else 0.0,
                    "unit": r["unit"] or ""
                })
            return points

    def get_metabolic_profile(self) -> Dict[str, Any]:
        """
        Retrieves personalized metabolic health profile, goals, and comprehensive baseline diagnostics.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metabolic_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT NOT NULL,
                    program TEXT NOT NULL,
                    target_hba1c REAL NOT NULL,
                    target_date TEXT NOT NULL,
                    target_weight_kg REAL NOT NULL,
                    diet_protocol TEXT NOT NULL,
                    doctor_notes TEXT DEFAULT '',
                    baseline_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("SELECT * FROM metabolic_profile ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {}
            d = dict(row)
            if d.get("baseline_json"):
                try:
                    d["baseline"] = json.loads(d["baseline_json"])
                except Exception:
                    d["baseline"] = {}
            else:
                d["baseline"] = {}

            target_date_str = d.get("target_date", "2027-01-07")
            try:
                target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
                now = datetime.now()
                days_left = max(0, (target_dt - now).days)
                d["days_remaining"] = days_left
            except Exception:
                d["days_remaining"] = 75

            return d

    def update_metabolic_profile(self, target_weight_kg: Optional[float] = None,
                                 target_hba1c: Optional[float] = None,
                                 target_date: Optional[str] = None) -> Dict[str, Any]:
        """Updates targets in the metabolic profile."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            prof = self.get_metabolic_profile()
            if not prof:
                return {}
            new_wt = target_weight_kg if target_weight_kg is not None else prof.get("target_weight_kg", 75.0)
            new_a1c = target_hba1c if target_hba1c is not None else prof.get("target_hba1c", 6.4)
            new_date = target_date if target_date is not None else prof.get("target_date", "2027-01-07")
            cursor.execute("""
                UPDATE metabolic_profile
                SET target_weight_kg = ?, target_hba1c = ?, target_date = ?, updated_at = ?
                WHERE id = ?
            """, (new_wt, new_a1c, new_date, now_str, prof.get("id", 1)))
            conn.commit()
        return self.get_metabolic_profile()

    def get_health_dashboard_summary(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Aggregates hydration, medications, and trend metrics for the Health & Wellness dashboard."""
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        hydration = self.get_today_hydration(date_str)
        meds = self.list_medications(date_str)
        taken_count = sum(1 for m in meds if m.get("taken_today"))
        total_meds = len(meds)

        water_trends = self.get_health_trends("water_ml", 7)
        sleep_trends = self.get_health_trends("sleep_hours", 7)
        steps_trends = self.get_health_trends("steps", 7)
        hr_trends = self.get_health_trends("resting_hr", 7)
        fasting_glucose_trends = self.get_health_trends("fasting_glucose", 14)
        pp_glucose_trends = self.get_health_trends("pp_glucose", 14)
        weight_trends = self.get_health_trends("weight_kg", 14)
        bp_sys_trends = self.get_health_trends("blood_pressure_sys", 14)
        bp_dia_trends = self.get_health_trends("blood_pressure_dia", 14)

        latest_sleep = sleep_trends[-1]["value"] if sleep_trends else 7.5
        latest_steps = int(steps_trends[-1]["value"]) if steps_trends else 8420
        latest_hr = int(hr_trends[-1]["value"]) if hr_trends else 68
        latest_fasting = fasting_glucose_trends[-1]["value"] if fasting_glucose_trends else 125.0
        latest_pp = pp_glucose_trends[-1]["value"] if pp_glucose_trends else 261.0
        latest_weight = weight_trends[-1]["value"] if weight_trends else 98.0
        latest_bp = int(bp_sys_trends[-1]["value"]) if bp_sys_trends else 125
        latest_bp_dia = int(bp_dia_trends[-1]["value"]) if bp_dia_trends else 80

        metabolic = self.get_metabolic_profile()

        return {
            "date": date_str,
            "hydration": hydration,
            "metabolic_profile": metabolic,
            "medications": {
                "items": meds,
                "taken_count": taken_count,
                "total_count": total_meds,
                "all_taken": (taken_count == total_meds and total_meds > 0)
            },
            "latest_vitals": {
                "sleep_hours": latest_sleep,
                "steps": latest_steps,
                "resting_hr": latest_hr,
                "fasting_glucose": latest_fasting,
                "pp_glucose": latest_pp,
                "weight_kg": latest_weight,
                "blood_pressure_sys": latest_bp,
                "blood_pressure_dia": latest_bp_dia,
                "blood_pressure": f"{latest_bp}/{latest_bp_dia}"
            },
            "trends": {
                "water_ml": water_trends,
                "sleep_hours": sleep_trends,
                "steps": steps_trends,
                "resting_hr": hr_trends,
                "fasting_glucose": fasting_glucose_trends,
                "pp_glucose": pp_glucose_trends,
                "weight_kg": weight_trends,
                "blood_pressure_sys": bp_sys_trends,
                "blood_pressure_dia": bp_dia_trends
            }
        }




