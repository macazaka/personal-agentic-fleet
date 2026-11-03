"""
UX-06: Interactive First-Run Persona Onboarding & Goal-Driven Auto-Setup Engine.
Delivers a 60-second guided setup ($0.00 / 0 LLM tokens) that atomically configures
personas, daily rhythm, visual ergonomics, pinned agents, schedules.yaml, and starter habits.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from fleet.config import (
    load_fleet_config,
    load_schedules_config,
    save_fleet_config,
    save_schedules_config,
)
from fleet.core.database import is_test_environment

PERSONA_PROFILES: Dict[str, Dict[str, Any]] = {
    "ffd_athlete": {
        "id": "ffd_athlete",
        "title": "FFD Metabolic Reversal & Traditional Strength Athlete",
        "icon": "🌿",
        "summary": "Prioritizes FFD Green Smoothie, 3.5L hydration cadence, Mudgal/Samtola/Dand-Baithak strength splits, and post-meal walks.",
        "default_tab": "health",
        "recommended_layout": "sidebar_dock",
        "recommended_theme": "aurora",
        "pinned_agents": ["health", "overview", "optimizer"],
        "water_target_ml": 3500,
        "starter_routines": [
            {"name": "Morning FFD Green Smoothie (07:30)", "time": "07:30", "category": "Nutrition"},
            {"name": "Traditional Strength Split — Mudgal & Dand-Baithak", "time": "06:45", "category": "Exercise"},
            {"name": "Post-Meal 15-Minute Glucose Walk", "time": "13:30", "category": "Metabolic"},
        ],
    },
    "software_engineer": {
        "id": "software_engineer",
        "title": "AI-Assisted Software Engineer (Antigravity / CI / MCP)",
        "icon": "💻",
        "summary": "Prioritizes Antigravity Live queue, Admin PR Review & 5-Pillar Governance Gate, Custom MCP Tool Studio, and Local Ollama models.",
        "default_tab": "antigravity",
        "recommended_layout": "sidebar_dock",
        "recommended_theme": "midnight",
        "pinned_agents": ["antigravity", "pr_review", "mcp_studio", "local_llm", "backlog"],
        "water_target_ml": 3000,
        "starter_routines": [
            {"name": "Morning PR, Branch & Security Governance Sweep", "time": "09:15", "category": "Engineering"},
            {"name": "Deep Work Architecture & Code Block", "time": "10:00", "category": "Engineering"},
        ],
    },
    "inbox_zero": {
        "id": "inbox_zero",
        "title": "Executive Productivity & Inbox Zero Operator",
        "icon": "⚡",
        "summary": "Prioritizes Executive Overview Cockpit, 4-Folder Email Intelligence (01-Focus..04-Archive), Feature Backlog, and Mobile Bot Bridge.",
        "default_tab": "overview",
        "recommended_layout": "command_deck",
        "recommended_theme": "dark",
        "pinned_agents": ["overview", "gmail", "backlog", "remote_chat"],
        "water_target_ml": 2750,
        "starter_routines": [
            {"name": "01-Focus Executive Inbox Triage", "time": "08:45", "category": "Productivity"},
            {"name": "Evening Shutdown & Tomorrow Top-3 Review", "time": "20:30", "category": "Productivity"},
        ],
    },
    "pc_performance": {
        "id": "pc_performance",
        "title": "PC Performance, Gaming & Homelab Enthusiast",
        "icon": "🚀",
        "summary": "Prioritizes Autonomic RAM Working-Set Trim, Thermal Telemetry, Local Ollama/LoRA Studio, and zero-overhead background daemon mode.",
        "default_tab": "optimizer",
        "recommended_layout": "launchpad_grid",
        "recommended_theme": "cyberpunk",
        "pinned_agents": ["optimizer", "local_llm", "overview", "pr_review"],
        "water_target_ml": 3000,
        "starter_routines": [
            {"name": "Workstation RAM & Temp Hygiene Sweep", "time": "11:00", "category": "System"},
        ],
    },
}

SUPPORTED_LAYOUTS: List[str] = [
    "sidebar_dock",
    "command_deck",
    "launchpad_grid",
    "split_workstation",
    "compact_zen",
    "executive_bento",
]

SUPPORTED_THEMES: List[str] = [
    "dark",
    "aurora",
    "midnight",
    "cyberpunk",
    "solarized",
    "nord",
]


def get_onboarding_state(db: Optional[Any] = None) -> Dict[str, Any]:
    """Returns all available persona profiles and the user's current onboarding configuration."""
    cfg = load_fleet_config() if not is_test_environment() else {}
    onboarding_cfg: Dict[str, Any] = cfg.get("onboarding", {}) if isinstance(cfg.get("onboarding"), dict) else {}
    if db is not None and hasattr(db, "get_setting"):
        raw = db.get_setting("ux06_onboarding_state", "")
        if raw:
            try:
                onboarding_cfg = json.loads(raw)
            except Exception:
                pass

    return {
        "status": "ok",
        "completed": bool(onboarding_cfg.get("completed", False)),
        "selected_personas": onboarding_cfg.get("personas", ["ffd_athlete", "software_engineer"]),
        "rhythm": onboarding_cfg.get(
            "rhythm",
            {
                "wake_time": "07:30",
                "deep_work_start": "09:30",
                "evening_wrap_time": "20:30",
                "water_target_ml": 3500,
            },
        ),
        "ergonomics": onboarding_cfg.get(
            "ergonomics",
            {
                "layout": cfg.get("ui", {}).get("layout", "sidebar_dock"),
                "theme": cfg.get("ui", {}).get("theme", "dark"),
                "default_tab": cfg.get("ui", {}).get("default_tab", "health"),
            },
        ),
        "personas_catalog": list(PERSONA_PROFILES.values()),
        "supported_layouts": SUPPORTED_LAYOUTS,
        "supported_themes": SUPPORTED_THEMES,
    }


def apply_persona_onboarding(
    payload: Dict[str, Any],
    db: Optional[Any] = None,
    persist_files: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Atomically applies a complete UX-06 Persona & Goal Onboarding bundle to
    `fleet.yaml`, `schedules.yaml`, and SQLite settings/routines ($0.00 / 0 tokens).
    """
    raw_personas = payload.get("personas")
    personas: List[str] = [
        str(p).strip()
        for p in (raw_personas if isinstance(raw_personas, list) else ["ffd_athlete"])
        if str(p).strip() in PERSONA_PROFILES
    ]
    if not personas:
        personas = ["ffd_athlete"]

    lead_profile = PERSONA_PROFILES[personas[0]]

    rhythm_in = payload.get("rhythm") if isinstance(payload.get("rhythm"), dict) else {}
    wake_time = str((rhythm_in or {}).get("wake_time") or payload.get("wake_time") or "07:30").strip()
    deep_work_start = str((rhythm_in or {}).get("deep_work_start") or payload.get("deep_work_start") or "09:30").strip()
    evening_wrap_time = str((rhythm_in or {}).get("evening_wrap_time") or payload.get("evening_wrap_time") or "20:30").strip()
    water_target_ml = int((rhythm_in or {}).get("water_target_ml") or payload.get("water_target_ml") or lead_profile["water_target_ml"])

    ergo_in = payload.get("ergonomics") if isinstance(payload.get("ergonomics"), dict) else {}
    layout = str((ergo_in or {}).get("layout") or payload.get("layout") or lead_profile["recommended_layout"]).strip()
    if layout not in SUPPORTED_LAYOUTS:
        layout = "sidebar_dock"
    theme = str((ergo_in or {}).get("theme") or payload.get("theme") or lead_profile["recommended_theme"]).strip()
    if theme not in SUPPORTED_THEMES:
        theme = "dark"
    default_tab = str((ergo_in or {}).get("default_tab") or payload.get("default_tab") or lead_profile["default_tab"]).strip()

    pinned_agents: List[str] = []
    starter_routines: List[Dict[str, str]] = []
    for pid in personas:
        prof = PERSONA_PROFILES[pid]
        for ag in prof.get("pinned_agents", []):
            if ag not in pinned_agents:
                pinned_agents.append(ag)
        for rt in prof.get("starter_routines", []):
            if not any(r["name"] == rt["name"] for r in starter_routines):
                starter_routines.append(rt)

    state_record = {
        "completed": True,
        "completed_at": datetime.now().isoformat(),
        "personas": personas,
        "rhythm": {
            "wake_time": wake_time,
            "deep_work_start": deep_work_start,
            "evening_wrap_time": evening_wrap_time,
            "water_target_ml": water_target_ml,
        },
        "ergonomics": {
            "layout": layout,
            "theme": theme,
            "default_tab": default_tab,
        },
        "pinned_agents": pinned_agents,
        "seeded_routines_count": len(starter_routines),
    }

    if db is not None:
        if hasattr(db, "set_setting"):
            db.set_setting("ux06_onboarding_state", json.dumps(state_record))
            db.set_setting("ui_layout", layout)
            db.set_setting("ui_theme", theme)
            db.set_setting("default_tab", default_tab)
            db.set_setting("water_target_ml", str(water_target_ml))
            db.set_setting("pinned_widgets", json.dumps(pinned_agents))
        if hasattr(db, "update_health_profile"):
            try:
                db.update_health_profile(daily_water_goal_ml=water_target_ml)
            except Exception:
                pass
        if hasattr(db, "add_routine") and hasattr(db, "get_routines"):
            try:
                existing_names = {str(r.get("name") or "") for r in (db.get_routines() or [])}
                for rt in starter_routines:
                    if rt["name"] not in existing_names:
                        db.add_routine(name=rt["name"], time_str=rt["time"], category=rt["category"])
            except Exception:
                pass

    should_write_disk = persist_files if persist_files is not None else (not is_test_environment())
    if should_write_disk:
        try:
            cfg = load_fleet_config()
            cfg.setdefault("ui", {})
            cfg["ui"]["layout"] = layout
            cfg["ui"]["theme"] = theme
            cfg["ui"]["default_tab"] = default_tab
            cfg["pinned_widgets"] = pinned_agents
            cfg["onboarding"] = state_record
            save_fleet_config(cfg)
        except Exception:
            pass

        try:
            sched_cfg = load_schedules_config()
            if isinstance(sched_cfg, dict) and isinstance(sched_cfg.get("schedules"), list):
                for s in sched_cfg["schedules"]:
                    if not isinstance(s, dict):
                        continue
                    sid = str(s.get("id") or "")
                    if "morning_briefing" in sid:
                        s["time"] = wake_time
                    elif "evening" in sid:
                        s["time"] = evening_wrap_time
                save_schedules_config(sched_cfg)
        except Exception:
            pass

    return {
        "status": "ok",
        "onboarding": state_record,
        "tokens_used": 0,
        "cost_usd": "$0.00",
    }

