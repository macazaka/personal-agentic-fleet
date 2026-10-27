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
