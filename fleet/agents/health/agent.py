"""
Health & Wellness Agent for Personal Agentic Fleet.
Manages metabolic tracking, vitals, water logging, medication compliance,
6-day Akhada strength training (Mudgal, Samtola, Bhim Gadha), and FFD exercise video streaming.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent
from fleet.api import health_api


class HealthAgent(FleetAgent):
    @property
    def id(self) -> str:
        return "health"

    @property
    def name(self) -> str:
        return "Health & Wellness"

    @property
    def icon(self) -> str:
        return "🌿"

    @property
    def order(self) -> int:
        return 10

    @property
    def is_default(self) -> bool:
        return True

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "daily_water_target_liters",
                "label": "Daily Hydration Target (Liters)",
                "type": "number",
                "default": 3.5,
                "description": "Daily water consumption budget tracked in the health dashboard"
            },
            {
                "id": "daily_calorie_target",
                "label": "Daily Calorie Budget (kcal)",
                "type": "number",
                "default": 1800,
                "description": "Metabolic reversal energy intake ceiling"
            },
            {
                "id": "morning_smoothie_time",
                "label": "Morning Smoothie Toast Alert Time",
                "type": "text",
                "default": "07:30",
                "description": "Scheduled time for early green/white smoothie reminder"
            },
            {
                "id": "evening_dinner_cutoff",
                "label": "Evening Dinner Cutoff Time",
                "type": "text",
                "default": "20:30",
                "description": "Target completion time for evening meal (4th morsel rule)"
            },
            {
                "id": "strength_split_active",
                "label": "Active Strength Training Regimen",
                "type": "select",
                "options": ["traditional_6day", "push_pull_legs", "upper_lower"],
                "default": "traditional_6day",
                "description": "Akhada traditional split (Mudgal / Samtola / Bhim Gadha)"
            },
            {
                "id": "enable_meal_reminders",
                "label": "Meal & Supplement Desktop Alerts",
                "type": "boolean",
                "default": True,
                "description": "Dispatch native desktop toast reminders for quad plates and meds"
            }
        ]

    def get_omnibar_commands(self) -> List[Dict[str, Any]]:
        return [
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": "@health bp",
                "syntax": "@health record blood pressure 120/80",
                "description": "Record blood pressure systolic and diastolic (mmHg)",
                "task": "record blood pressure 120/80",
            },
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": "@health water",
                "syntax": "@health water +1",
                "description": "Log +1 glass (250ml) of water drank today",
                "task": "water",
            },
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": "@health sugar",
                "syntax": "@health record blood sugar 95",
                "description": "Record fasting blood sugar level (mg/dL)",
                "task": "record blood sugar 95",
            },
            {
                "agent_id": self.id,
                "agent_name": self.display_name,
                "icon": self.display_icon,
                "trigger": "@health split",
                "syntax": "@health split",
                "description": "Show today's 6-Day Traditional Strength Split (Mudgal/Samtola/Bhim Gadha)",
                "task": "morning_smoothie_and_workout",
            },
        ]

    def register_routes(self, router) -> None:
        # Re-export / wire the modular health routes
        router.include_router(health_api.router)

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        t_low = (task or "").lower()
        health_messages = {
            "smoothie_reminder": ("🥤 Early Morning Smoothie Time", "Drink your 250ml Green/White Smoothie on empty stomach with methi, cinnamon & haldi."),
            "breakfast_meds": ("🥗 Breakfast & Morning Prescriptions", "25-25-50% Breakfast! Take your scheduled morning supplements."),
            "lunch_meds": ("🍲 Lunch & Afternoon Prescriptions", "25% Quad Plate (Salad, Veg, Dal, Grain). Take your scheduled afternoon supplements."),
            "afternoon_snack": ("🥜 Afternoon Smoothie & Soaked Nuts", "250ml Smoothie + 5-6 soaked almonds, 4-5 walnuts & 4 tsp mixed seeds."),
            "dinner_meds": ("🍽️ Early Dinner & Evening Prescriptions", "Finish dinner before 8:30 PM (4th morsel rule). Take your scheduled evening supplements."),
            "sleep_recovery": ("💤 Sleep & Metabolic Recovery", "Wind down screens! Aim for 7-8 hours sound rest. In bed by 11:00 PM latest."),
        }
        for k, (title, msg) in health_messages.items():
            if k in t_low:
                return {"status": "success", "title": title, "message": msg}

        # Blood pressure recording: e.g. "record blood pressure 120/80" or "bp 120/80"
        if "blood pressure" in t_low or "bp" in t_low:
            import re
            m = re.search(r"(\d{2,3})\s*(?:/|\s+)\s*(\d{2,3})", task)
            if m:
                sys_val = float(m.group(1))
                dia_val = float(m.group(2))
                if self.db and hasattr(self.db, "log_health_metric"):
                    self.db.log_health_metric("blood_pressure_sys", sys_val, "mmHg", "Blood pressure systolic")
                    self.db.log_health_metric("blood_pressure_dia", dia_val, "mmHg", "Blood pressure diastolic")
                return {
                    "status": "success",
                    "title": "🩺 Blood Pressure Recorded",
                    "message": f"Recorded Blood Pressure: {int(sys_val)}/{int(dia_val)} mmHg (Systolic: {int(sys_val)} mmHg, Diastolic: {int(dia_val)} mmHg).",
                    "systolic": int(sys_val),
                    "diastolic": int(dia_val),
                    "unit": "mmHg"
                }

        # Fasting/Post-meal blood sugar recording
        if "sugar" in t_low or "glucose" in t_low or "bsl" in t_low:
            import re
            m = re.search(r"(\d{2,3}(?:\.\d+)?)", task)
            if m:
                val = float(m.group(1))
                metric_name = "pp_glucose" if "pp" in t_low or "post" in t_low else "fasting_glucose"
                label = "Post-Prandial Glucose" if metric_name == "pp_glucose" else "Fasting Blood Sugar"
                if self.db and hasattr(self.db, "log_health_metric"):
                    self.db.log_health_metric(metric_name, val, "mg/dL", label)
                return {
                    "status": "success",
                    "title": f"🩸 {label} Recorded",
                    "message": f"Recorded {label}: {val} mg/dL.",
                    "value": val,
                    "unit": "mg/dL"
                }

        # Water/Hydration quick logging
        if "water" in t_low or "hydration" in t_low:
            import re
            m = re.search(r"(\d+)", t_low)
            glasses = int(m.group(1)) if m and int(m.group(1)) <= 20 else 1
            if self.db and hasattr(self.db, "log_water_intake"):
                hyd = self.db.log_water_intake(glasses_delta=glasses, amount_delta_ml=glasses * 250)
                return {
                    "status": "success",
                    "title": f"💧 Hydration Recorded (+{glasses} glasses)",
                    "message": f"Logged +{glasses} glass(es) of water. Today's total: {hyd.get('glasses', glasses)} glasses ({hyd.get('amount_ml', glasses * 250)} ml).",
                    "hydration": hyd
                }

        if "routine" in t_low:
            routines = self.db.list_routines() if self.db and hasattr(self.db, "list_routines") else []
            pending = [r for r in routines if not r.get("completed_today")]
            return {
                "status": "success",
                "title": f"📋 Daily Routines: {len(pending)} Remaining",
                "message": f"{len(pending)} uncompleted routine(s) today.",
                "pending_routines": pending,
            }
        return {"status": "SUCCESS", "agent": self.id, "task": task}
