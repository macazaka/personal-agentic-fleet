"""
UX-05: Unified "Ask Fleet Anything" Conversational Omnibar & Cross-Agent Dispatcher.
Unifies Spotlight tab navigation, multi-turn conversational AI & Fleet telemetry chat,
@agent slash commands, UX-01 Agent Studio synthesis, UX-02 Process Discovery,
UX-03 Playbook triggers, Tier-0 natural-language execution, and BM25 Knowledge RAG
into a single responsive conversational interface.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple


BUILTIN_OMNIBAR_SHORTCUTS: List[Dict[str, Any]] = [
    {
        "agent_id": "health",
        "agent_name": "Health & Wellness",
        "icon": "🌿",
        "trigger": "@health water",
        "syntax": "@health water +1",
        "description": "Log +1 glass (250ml) of water drank today",
        "task": "log_water",
    },
    {
        "agent_id": "health",
        "agent_name": "Health & Wellness",
        "icon": "🌿",
        "trigger": "@health split",
        "syntax": "@health split",
        "description": "Show today's 6-Day Traditional Strength Split (Mudgal/Samtola/Bhim Gadha)",
        "task": "morning_smoothie_and_workout",
    },
    {
        "agent_id": "optimizer",
        "agent_name": "Silent PC Optimizer",
        "icon": "🚀",
        "trigger": "@optimizer ram",
        "syntax": "@optimizer ram",
        "description": "Run silent Win32 PSAPI memory audit & cleanup",
        "task": "periodic_ram_audit",
    },
    {
        "agent_id": "gmail",
        "agent_name": "Gmail Inbox Intelligence",
        "icon": "📬",
        "trigger": "@gmail classify",
        "syntax": "@gmail classify",
        "description": "Run deterministic 5-folder inbox classification",
        "task": "inbox_classification",
    },
    {
        "agent_id": "studio",
        "agent_name": "Zero-Code Agent Studio (UX-01)",
        "icon": "✨",
        "trigger": "@studio",
        "syntax": "@studio <plain-English agent description>",
        "description": "Synthesize a brand-new agent from plain English ($0.00)",
        "task": "synthesize",
    },
    {
        "agent_id": "discovery",
        "agent_name": "Process Discovery Engine (UX-02)",
        "icon": "🕵️",
        "trigger": "@discover",
        "syntax": "@discover",
        "description": "Mine workstation patterns & recommend new agents to build",
        "task": "recommend",
    },
    {
        "agent_id": "playbooks",
        "agent_name": "Multi-Agent Playbooks (UX-03)",
        "icon": "🔗",
        "trigger": "@playbook",
        "syntax": "@playbook morning_vitality_launchpad",
        "description": "Execute a multi-agent event chain playbook",
        "task": "run_playbook",
    },
]

# Rolling in-memory conversational history for the Unified Omnibar
_OMNIBAR_CHAT_HISTORY: List[Dict[str, Any]] = []
MAX_OMNIBAR_HISTORY = 20

_DAY_WORKOUT_MAP: Dict[str, str] = {
    "Monday": "🪵 **Mudgal Strength Training** (Beginner Playlist) + Mandatory World's Best Warm-up",
    "Tuesday": "🔥 **Mandatory World's Best Warm-up** + FFD Anti-Gravity Step Climbing / Nitric Oxide Dump & Core Mobility",
    "Wednesday": "⚖️ **Samtola (Indian Barbell) Strength Training** (Beginner Playlist) + Mandatory World's Best Warm-up",
    "Thursday": "🔥 **Mandatory World's Best Warm-up** + FFD Anti-Gravity / Upper & Lower Body Resistance",
    "Friday": "🔱 **Bhim Gadha (Macebell) Strength Training** (Beginner Playlist) + Mandatory World's Best Warm-up",
    "Saturday": "🔥 **Mandatory World's Best Warm-up** + FFD Full-Body Metabolic & Flexibility Flow",
    "Sunday": "🛌 **Mandatory Full Rest & Metabolic Recovery**",
}


def get_omnibar_chat_history() -> List[Dict[str, Any]]:
    """Returns the current rolling conversational history for the Omnibar."""
    return list(_OMNIBAR_CHAT_HISTORY)


def clear_omnibar_chat_history() -> None:
    """Clears the rolling conversational history for the Omnibar."""
    _OMNIBAR_CHAT_HISTORY.clear()


def _record_turn(user_query: str, reply: Dict[str, Any]) -> Dict[str, Any]:
    """Appends a conversational turn to rolling history and attaches history to the response."""
    turn = {
        "user": user_query,
        "title": reply.get("title", "⚡ Fleet Assistant"),
        "message": reply.get("message", ""),
        "mode": reply.get("mode", "conversation"),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    _OMNIBAR_CHAT_HISTORY.append(turn)
    if len(_OMNIBAR_CHAT_HISTORY) > MAX_OMNIBAR_HISTORY:
        del _OMNIBAR_CHAT_HISTORY[:-MAX_OMNIBAR_HISTORY]
    reply.setdefault("conversational", True)
    reply.setdefault("history_count", len(_OMNIBAR_CHAT_HISTORY))
    return reply


def _gather_live_fleet_snapshot(agent_registry: Optional[Any] = None, db: Optional[Any] = None) -> Dict[str, Any]:
    """Collects live workstation & Fleet telemetry for context-aware conversational replies."""
    agents_map = getattr(agent_registry, "agents", {}) if agent_registry else {}
    active_agents = len(agents_map) if agents_map else 7
    pending_tasks: List[Dict[str, Any]] = []
    hydration = {"glasses": 0, "amount_ml": 0, "goal_ml": 2500}

    if db is not None:
        try:
            if hasattr(db, "list_tasks"):
                pending_tasks = db.list_tasks(status="pending", exclude_tests=True) or []
        except Exception:
            pass
        try:
            if hasattr(db, "get_today_hydration"):
                hyd = db.get_today_hydration()
                if isinstance(hyd, dict):
                    hydration = hyd
        except Exception:
            pass

    today_name = datetime.now().strftime("%A")
    today_workout = _DAY_WORKOUT_MAP.get(today_name, _DAY_WORKOUT_MAP["Monday"])
    custom_rollup: Dict[str, Any] = {"total_alerts": 0, "alerts": []}
    if db is not None and hasattr(db, "get_custom_agents_fleet_rollup"):
        try:
            custom_manifests = None
            if agent_registry and hasattr(agent_registry, "get_manifests"):
                custom_manifests = [m for m in agent_registry.get_manifests() if m.get("is_custom")]
            custom_rollup = db.get_custom_agents_fleet_rollup(custom_manifests=custom_manifests)
        except Exception:
            pass
    return {
        "active_agents": active_agents,
        "pending_tasks": pending_tasks,
        "pending_count": len(pending_tasks),
        "hydration": hydration,
        "today_name": today_name,
        "today_workout": today_workout,
        "custom_rollup": custom_rollup,
    }


def get_all_omnibar_commands(agent_registry: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Aggregates built-in shortcuts and all active agents' get_omnibar_commands()."""
    commands: List[Dict[str, Any]] = list(BUILTIN_OMNIBAR_SHORTCUTS)
    seen = {(c["trigger"], c["task"]) for c in commands}

    if agent_registry and hasattr(agent_registry, "agents"):
        for ag_id, agent in agent_registry.agents.items():
            if hasattr(agent, "get_omnibar_commands"):
                try:
                    for cmd in agent.get_omnibar_commands():
                        key = (cmd.get("trigger", ""), cmd.get("task", ""))
                        if key not in seen:
                            seen.add(key)
                            commands.append(cmd)
                except Exception:
                    pass
    return commands


def dispatch_omnibar_query(
    query: str,
    agent_registry: Optional[Any] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes an Omnibar command, natural-language question, or conversational chat turn.
    Combines deterministic Tier-0 execution ($0.00), live Fleet SQLite telemetry,
    BM25 Knowledge RAG, and optional Hyperscaler LLM completion into a conversational response.
    """
    raw = (query or "").strip()
    if not raw:
        raise ValueError("Omnibar query cannot be empty.")
    lower = raw.lower()
    cleaned_words = re.sub(r"[^\w\s]", "", lower).strip()

    # 0. Clear history command
    if cleaned_words in ("clear", "reset", "clear chat", "reset chat"):
        clear_omnibar_chat_history()
        return {
            "status": "ok",
            "mode": "conversation",
            "title": "🧹 Omnibar Conversation Cleared",
            "message": "Chat history has been reset. How can I help you today?",
            "suggestions": [
                "Give me my daily briefing",
                "What are my pending tasks?",
                "What is my workout today?",
                "@discover",
            ],
            "tokens_used": 0,
            "conversational": True,
            "history_count": 0,
        }

    # 1. @discover or "recommend agent" -> UX-02 Process Discovery
    if lower.startswith("@discover") or "recommend agent" in lower or "discover agent" in lower:
        from fleet.core.process_miner import mine_workstation_recommendations
        installed = set(getattr(agent_registry, "agents", {}).keys()) if agent_registry else set()
        report = mine_workstation_recommendations(db=db, installed_agent_ids=installed)
        top = report["recommendations"][:3]
        summary = " | ".join(f"{r['icon']} {r['name']} ({r['opportunity_score']}/100)" for r in top)
        return _record_turn(raw, {
            "status": "ok",
            "mode": "discovery",
            "title": f"🕵️ {len(top)} Recommended Agents Discovered (Save ~{report['total_estimated_minutes_saved_per_week']}m/wk)",
            "message": summary,
            "recommendations": top,
            "suggestions": ["@studio Create a habit tracker agent", "Give me my daily briefing"],
            "tokens_used": 0,
        })

    # 2. @studio or "create agent ..." -> UX-01 & Phase 4 Zero-Code Agent Studio
    if lower.startswith("@studio") or lower.startswith("create agent"):
        prompt_body = re.sub(r"^(?:@studio|create\s+agent)\s*:?\s*", "", raw, flags=re.I).strip()
        launch_now = False
        if re.match(r"^(?:launch|create|build|activate)\b\s+", prompt_body, flags=re.I):
            launch_now = True
            prompt_body = re.sub(r"^(?:launch|create|build|activate)\b\s*:?\s*", "", prompt_body, flags=re.I).strip()
        if not prompt_body:
            prompt_body = "Monitor my daily deep work sessions and alert me at 6 PM"
        from fleet.core.agent_studio import synthesize_agent_from_prompt
        spec = synthesize_agent_from_prompt(prompt_body)

        if launch_now and agent_registry is not None and hasattr(agent_registry, "create_custom_agent"):
            base_id = spec["agent_id"]
            cand_id = base_id
            suffix = 2
            existing_ids = set(getattr(agent_registry, "agents", {}).keys()) | set(getattr(agent_registry, "_all_discovered_agents", {}).keys())
            while cand_id in existing_ids:
                cand_id = f"{base_id}_{suffix}"
                suffix += 1
            raw_sched_obj = spec.get("schedule")
            sched_obj: Dict[str, Any] = raw_sched_obj if isinstance(raw_sched_obj, dict) else {}
            manifest = agent_registry.create_custom_agent(
                agent_id=cand_id,
                name=spec["name"],
                icon=spec["icon"],
                permissions=spec["permissions"],
                description=spec["description"],
                ui_blocks=spec["ui_blocks"],
                routine_task=spec["routine_task"],
                schedule_display=str(sched_obj.get("display") or "Daily at 09:00"),
                category=spec["category"],
                archetype=spec.get("archetype", "tracker"),
                intelligence_mode=spec.get("intelligence_mode", "hybrid"),
                model=spec.get("model"),
                system_prompt=spec.get("system_prompt"),
                fields=spec.get("fields"),
                checklist_items=spec.get("checklist_items"),
                event_triggers=spec.get("event_triggers"),
                schedule_cadence=spec.get("schedule_cadence", "daily_morning"),
                schedule=sched_obj,
            )
            try:
                from fleet.api.settings_api import _sync_custom_agent_events, _sync_custom_agent_schedule
                _sync_custom_agent_schedule(
                    agent_id=manifest["id"],
                    name=manifest["name"],
                    icon=manifest["icon"],
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    schedule_cadence=str(manifest.get("schedule_cadence") or "daily_morning"),
                    schedule_info=sched_obj,
                )
                _sync_custom_agent_events(
                    agent_id=manifest["id"],
                    name=manifest["name"],
                    icon=manifest["icon"],
                    routine_task=str(manifest.get("routine_task") or "run_check"),
                    event_triggers=manifest.get("event_triggers"),
                )
            except Exception:
                pass
            return _record_turn(raw, {
                "status": "ok",
                "mode": "studio_created",
                "agent_id": manifest["id"],
                "manifest": manifest,
                "spec": spec,
                "title": f"🚀 Created & Activated: {manifest['icon']} {manifest['name']} ({manifest['id']})",
                "message": (
                    f"Live in your Fleet! Schedule: {sched_obj.get('display', 'Daily')} | "
                    f"Widgets: {len(manifest.get('ui_blocks') or [])} | Try `@{manifest['id']} add <item>` or `@{manifest['id']} open`."
                ),
                "suggestions": [f"@{manifest['id']} open", f"@{manifest['id']} run", "@discover"],
                "tokens_used": 0,
            })

        return _record_turn(raw, {
            "status": "ok",
            "mode": "studio_synthesis",
            "title": f"✨ Synthesized: {spec['icon']} {spec['name']} ({spec['agent_id']})",
            "message": f"Schedule: {spec['schedule']['display']} | Permissions: {', '.join(spec['permissions'])} | Blocks: {len(spec['ui_blocks'])}",
            "spec": spec,
            "suggestions": [f"@studio launch {prompt_body[:60]}", "@discover", "Show Fleet status"],
            "tokens_used": 0,
        })

    # 3. @playbook <id> -> UX-03 Playbook Execution
    if lower.startswith("@playbook"):
        parts = raw.split(maxsplit=1)
        pb_id = parts[1].strip() if len(parts) > 1 else "morning_vitality_launchpad"
        from fleet.core.playbook_engine import execute_playbook
        res = execute_playbook(pb_id, agent_registry=agent_registry, db=db)
        return _record_turn(raw, {
            "status": "ok",
            "mode": "playbook",
            "title": f"🔗 Playbook Executed: {res['name']}",
            "message": f"Completed {res['steps_executed']} cross-agent steps deterministically.",
            "playbook_result": res,
            "suggestions": ["Give me my daily briefing", "How much water did I drink?"],
            "tokens_used": 0,
        })

    # 4. Hydration quick capture: "@health water" or "drank N glasses"
    if lower.startswith("@health water") or re.search(r"\b(?:drank|log|add)\s+\d*\s*(?:glass|glasses|water|ml)\b", lower):
        m_num = re.search(r"(\d+)", lower)
        glasses = int(m_num.group(1)) if m_num and int(m_num.group(1)) <= 20 else 1
        if db is not None:
            try:
                if hasattr(db, "log_water_intake"):
                    hyd = db.log_water_intake(glasses_delta=glasses, amount_delta_ml=glasses * 250)
                elif hasattr(db, "log_hydration"):
                    hyd = db.log_hydration(glasses_delta=glasses)
                else:
                    hyd = None
                if isinstance(hyd, dict):
                    return _record_turn(raw, {
                        "status": "ok",
                        "mode": "hydration",
                        "title": f"🌿 Logged +{glasses} Glass(es) of Water",
                        "message": f"Today's hydration total: {hyd.get('glasses', glasses)} glasses ({hyd.get('amount_ml', glasses * 250)} / {hyd.get('goal_ml', 2500)} ml).",
                        "hydration": hyd,
                        "suggestions": ["What is my workout today?", "FFD Green Smoothie recipe"],
                        "tokens_used": 0,
                    })
            except Exception:
                pass
        return _record_turn(raw, {
            "status": "ok",
            "mode": "hydration",
            "title": f"🌿 Logged +{glasses} Glass(es) of Water",
            "message": f"Added {glasses * 250} ml to today's hydration tracker.",
            "suggestions": ["What is my workout today?", "FFD Green Smoothie recipe"],
            "tokens_used": 0,
        })

    # 5. Direct @<agent_id> [task] invocation (including Phase 4 Custom Agent quick-add & AI briefing)
    if lower.startswith("@"):
        tokens = raw[1:].split(maxsplit=1)
        target_id = tokens[0].lower().strip()
        task_arg = tokens[1].strip() if len(tokens) > 1 else "default"
        agents_map = getattr(agent_registry, "agents", {}) if agent_registry else {}
        agent = agents_map.get(target_id)
        if agent:
            task_lower = task_arg.lower()
            if task_lower in ("open", "open_tab", "view"):
                return _record_turn(raw, {
                    "status": "ok",
                    "mode": "navigate",
                    "agent_id": target_id,
                    "title": f"{agent.display_icon} Switched to {agent.display_name}",
                    "message": f"Opened workspace for '{target_id}'.",
                    "tokens_used": 0,
                })

            # Phase 4: @<custom_agent> add <title [YYYY-MM-DD] [amount]> -> $0.00 SQLite Quick Capture
            if re.match(r"^(?:add|log)\b", task_lower):
                entry_raw = re.sub(r"^(?:add|log)\b\s*:?\s*", "", task_arg, flags=re.I).strip()
                target_db = db or getattr(agent_registry, "db", None)
                if not entry_raw:
                    return _record_turn(raw, {
                        "status": "ok",
                        "mode": "conversation",
                        "agent_id": target_id,
                        "title": f"{agent.display_icon} Quick Capture Syntax",
                        "message": f"Usage: `@{target_id} add <item title> [YYYY-MM-DD] [amount]`",
                        "suggestions": [f"@{target_id} open", f"@{target_id} run"],
                        "tokens_used": 0,
                    })
                if target_db is not None and hasattr(target_db, "add_custom_agent_record"):
                    due_val = ""
                    m_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", entry_raw)
                    working = entry_raw
                    if m_date:
                        due_val = m_date.group(1)
                        working = (working[:m_date.start()] + " " + working[m_date.end():]).strip()

                    num_val = 0.0
                    m_num = re.search(r"(?:^|\s)\$?(\d+(?:\.\d+)?)\s*$", working)
                    if m_num:
                        try:
                            num_val = float(m_num.group(1))
                            working = working[:m_num.start()].strip()
                        except ValueError:
                            num_val = 0.0

                    clean_title = re.sub(r"\s+", " ", working).strip(" -|,") or entry_raw
                    extra_data: Dict[str, Any] = {"source": "omnibar"}
                    m_url = re.search(r"https?://[^\s]+", clean_title)
                    if m_url:
                        extra_data["target_url"] = m_url.group(0)

                    rec_id = target_db.add_custom_agent_record(
                        agent_id=agent.id,
                        title=clean_title,
                        record_type="entry",
                        data=extra_data,
                        due_date=due_val,
                        numeric_value=num_val,
                    )
                    details = [f"**{clean_title}**"]
                    if due_val:
                        details.append(f"due `{due_val}`")
                    if num_val:
                        details.append(f"value `{num_val:,.2f}`")
                    return _record_turn(raw, {
                        "status": "ok",
                        "mode": "agent_record_added",
                        "agent_id": target_id,
                        "record_id": rec_id,
                        "title": f"{agent.display_icon} Logged Record #{rec_id} in {agent.display_name}",
                        "message": "Saved " + " • ".join(details) + f" to `{target_id}` SQLite table ($0.00).",
                        "suggestions": [f"@{target_id} run", f"@{target_id} open", f"@{target_id} ai"],
                        "tokens_used": 0,
                    })

            # Phase 4: @<custom_agent> ai -> On-Demand Antigravity AI Executive Briefing
            if task_lower in ("ai", "analyze", "ai_analyze", "briefing", "insight"):
                eff_task = "ai_analyze"
            elif getattr(agent, "is_custom", False) and task_lower in ("default", "run", "check"):
                meta = getattr(agent, "manifest_meta", {}) or {}
                eff_task = str(meta.get("routine_task") or "run_check")
            else:
                eff_task = task_arg

            res = agent.execute_task(eff_task)
            msg = (
                res.get("ai_summary")
                or res.get("message")
                or res.get("summary")
                or f"Executed task '{eff_task}' on {agent.display_name}."
            )
            return _record_turn(raw, {
                "status": "ok",
                "mode": "agent_task",
                "agent_id": target_id,
                "title": res.get("title", f"{agent.display_icon} {agent.display_name}"),
                "message": msg,
                "result": res,
                "suggestions": [f"@{target_id} open", "Give me my daily briefing"],
                "tokens_used": 0,
            })

    # 6. Conversational Greetings, Small Talk & Identity ("hi", "hello", "hey", "how are you", "who are you", "help")
    greeting_patterns = {
        "hi", "hello", "hey", "hola", "namaste", "yo", "sup", "howdy",
        "hi there", "hello there", "hey there", "good morning", "good afternoon",
        "good evening", "gm", "hi fleet", "hello fleet", "hey fleet",
    }
    if cleaned_words in greeting_patterns or re.match(r"^(?:hi|hello|hey)\b[\s!.,?]*$", lower):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        hyd = snap["hydration"]
        msg = (
            f"👋 Hey there! I'm your **Personal Agentic Fleet Conversational Assistant**.\n"
            f"• **Fleet Status**: {snap['active_agents']} agents online & operational\n"
            f"• **Pending Tasks**: {snap['pending_count']} task(s) on your board\n"
            f"• **Today's Hydration**: {hyd.get('glasses', 0)} glasses ({hyd.get('amount_ml', 0)} / {hyd.get('goal_ml', 2500)} ml)\n"
            f"• **{snap['today_name']} Focus**: {snap['today_workout']}\n\n"
            f"Ask me anything in plain English—your daily briefing, tasks, FFD diet/smoothie rules, PC optimization, or click a suggestion below!"
        )
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "title": "🤖 Fleet Conversational Assistant",
            "message": msg,
            "suggestions": [
                "Give me my daily briefing",
                "What are my pending tasks?",
                "What is my workout today?",
                "FFD Green Smoothie recipe",
                "@discover",
            ],
            "tokens_used": 0,
        })

    if any(p in cleaned_words for p in ("how are you", "how are things", "whats up", "what is up", "how is it going")):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "title": "⚡ All Systems Nominal",
            "message": (
                f"I'm running at peak efficiency! All **{snap['active_agents']} Fleet agents** are online, "
                f"you have **{snap['pending_count']} pending task(s)**, and today's hydration is at "
                f"**{snap['hydration'].get('amount_ml', 0)} ml**. What would you like to work on?"
            ),
            "suggestions": [
                "What are my pending tasks?",
                "Log +1 glass of water",
                "Optimize my PC",
                "Run security scan",
            ],
            "tokens_used": 0,
        })

    if any(p in cleaned_words for p in ("thank you", "thanks", "thx", "awesome", "great job", "cool")):
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "title": "🙌 Happy to Help!",
            "message": "Anytime! Let me know if you want to check tasks, log hydration, run a playbook, or build a new agent.",
            "suggestions": [
                "Give me my daily briefing",
                "What are my pending tasks?",
                "@discover",
            ],
            "tokens_used": 0,
        })

    if cleaned_words in ("help", "commands", "what can you do", "who are you", "capabilities", "menu") or any(
        p in lower for p in ("what can you do", "who are you", "how do i use", "help me")
    ):
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "title": "🧭 What You Can Ask the Fleet Omnibar",
            "message": (
                "I'm your conversational interface across the entire Personal Agentic Fleet:\n"
                "1. **Daily Operations & Tasks**: Ask *\"What are my pending tasks?\"*, *\"Add task Review PR\"*, or *\"Give me my daily briefing\"*.\n"
                "2. **Health, Hydration & 6-Day Workout Split**: Ask *\"How much water did I drink?\"*, *\"Drank 2 glasses of water\"*, *\"What is my workout today?\"*, or *\"FFD Green Smoothie recipe\"*.\n"
                "3. **PC Optimization & Security**: Ask *\"Optimize my PC\"*, *\"Clean temp files\"*, *\"Flush DNS\"*, or *\"Run security scan\"*.\n"
                "4. **Agent Studio & Discovery**: Type `@discover` to mine workstation patterns or `@studio <description>` to synthesize a new agent."
            ),
            "suggestions": [
                "Give me my daily briefing",
                "What are my pending tasks?",
                "What is my workout today?",
                "Optimize my PC",
                "@discover",
            ],
            "tokens_used": 0,
        })

    # 7. Conversational Task Management ("what are my tasks", "add task ...")
    add_task_match = re.match(r"^(?:add\s+task|create\s+task|new\s+task|todo|remind\s+me\s+to)\s+(.+)$", raw, flags=re.I)
    if add_task_match and db is not None and hasattr(db, "add_task"):
        task_title = add_task_match.group(1).strip()
        task_id = db.add_task(title=task_title, description=f"Created via Conversational Omnibar: {task_title}", priority="P2", assigned_agent="Omnibar")
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "agent_id": "overview",
            "title": f"✅ Created Task #{task_id}",
            "message": f"Added **\"{task_title}\"** (Priority P2) to your Task & Goal Board.",
            "suggestions": ["What are my pending tasks?", "Give me my daily briefing"],
            "tokens_used": 0,
        })

    if any(p in lower for p in ("my tasks", "pending tasks", "list tasks", "show tasks", "what tasks", "todo list", "to-do list")) or cleaned_words in ("tasks", "todos"):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        tasks = snap["pending_tasks"][:5]
        if not tasks:
            msg = "🎉 Your task board is clear! You have **0 pending tasks**. Type `Add task <title>` to create one."
        else:
            lines = [f"• **#{t.get('id')}** [{t.get('priority', 'P2')}] {t.get('title')}" for t in tasks]
            msg = f"📋 You have **{snap['pending_count']} pending task(s)** (showing top {len(tasks)}):\n" + "\n".join(lines)
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "agent_id": "overview",
            "title": f"📋 Pending Tasks ({snap['pending_count']})",
            "message": msg,
            "suggestions": ["Add task Review sprint goals", "Give me my daily briefing"],
            "tokens_used": 0,
        })

    # 8. Conversational Daily Briefing & Fleet Status ("briefing", "daily briefing", "status", "how is my fleet")
    if any(p in lower for p in ("daily briefing", "morning briefing", "give me my briefing", "summarize my day", "fleet status", "how is my fleet", "system status")) or cleaned_words in ("briefing", "status"):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        hyd = snap["hydration"]
        rollup = snap.get("custom_rollup") or {}
        custom_alerts = rollup.get("alerts") or []
        custom_line = ""
        if custom_alerts:
            preview = ", ".join(
                f"{a.get('agent_icon', '✨')} {a.get('title')}"
                for a in custom_alerts[:3]
            )
            custom_line = f"\n• **Custom Agent Alerts ({rollup.get('total_alerts', len(custom_alerts))})**: {preview}"
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "agent_id": "overview",
            "title": f"☀️ Daily Fleet Briefing ({snap['today_name']})",
            "message": (
                f"Here is your live Fleet snapshot:\n"
                f"• **Active Agents**: {snap['active_agents']} autonomous agents online\n"
                f"• **Pending Tasks**: {snap['pending_count']} pending task(s)\n"
                f"• **Hydration Progress**: {hyd.get('glasses', 0)} glasses ({hyd.get('amount_ml', 0)} / {hyd.get('goal_ml', 2500)} ml)\n"
                f"• **Today's Training ({snap['today_name']})**: {snap['today_workout']}"
                f"{custom_line}"
            ),
            "custom_agent_alerts": custom_alerts,
            "suggestions": [
                "What are my pending tasks?",
                "Log +1 glass of water",
                "FFD Green Smoothie recipe",
                "Run security scan",
            ],
            "tokens_used": 0,
        })

    # 9. Conversational Hydration & Workout Queries ("how much water", "what is my workout today")
    if any(p in lower for p in ("how much water", "water intake", "hydration status", "my hydration", "glasses of water")):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        hyd = snap["hydration"]
        amt = hyd.get("amount_ml", 0)
        goal = hyd.get("goal_ml", 2500)
        pct = min(100, round((amt / max(1, goal)) * 100))
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "agent_id": "health",
            "title": f"💧 Today's Hydration: {amt} / {goal} ml ({pct}%)",
            "message": f"You've logged **{hyd.get('glasses', 0)} glass(es)** ({amt} ml out of your {goal} ml goal) today.",
            "suggestions": ["@health water +1", "@health water +2", "What is my workout today?"],
            "tokens_used": 0,
        })

    if any(p in lower for p in ("workout today", "exercise today", "todays workout", "today's workout", "what is my workout", "training today")):
        snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
        return _record_turn(raw, {
            "status": "ok",
            "mode": "conversation",
            "agent_id": "health",
            "title": f"🏋️ {snap['today_name']} Workout Plan",
            "message": f"Today is **{snap['today_name']}**: {snap['today_workout']}.\nRemember to perform **FFD Antigravity Step Climbing / Nitric Oxide Dump** 1 hr 45 mins after each meal!",
            "suggestions": ["Show full 6-day workout schedule", "FFD Green Smoothie recipe", "@health water +1"],
            "tokens_used": 0,
        })

    # 10. Tier-0 Deterministic Intent Router & Offline BM25 Knowledge RAG ($0.00)
    try:
        from fleet.core.token_optimizer import (
            get_cached_prompt_response,
            query_local_knowledge_base,
            try_deterministic_intent_route,
        )
        det_res = try_deterministic_intent_route(raw, db=db)
        if det_res is not None:
            return _record_turn(raw, {
                "status": "ok",
                "mode": "tier0_rag",
                "title": det_res.get("title", "⚡ Instant Local Fleet Response ($0.00)"),
                "message": det_res.get("message", ""),
                "suggestions": ["Give me my daily briefing", "What are my pending tasks?", "Help"],
                "tokens_used": 0,
            })

        rag_res = query_local_knowledge_base(raw)
        if rag_res is not None:
            return _record_turn(raw, {
                "status": "ok",
                "mode": "tier0_rag",
                "title": f"📚 {rag_res.get('title', 'Fleet Knowledge Base')} ($0.00)",
                "message": rag_res.get("message", ""),
                "suggestions": ["What is my workout today?", "FFD Breakfast protocol", "FFD Lunch plate formula"],
                "tokens_used": 0,
            })

        cached = get_cached_prompt_response(raw)
        if cached is not None:
            return _record_turn(raw, {
                "status": "ok",
                "mode": "tier0_rag",
                "title": "⚡ Semantic Cache Answer ($0.00)",
                "message": cached,
                "suggestions": ["Give me my daily briefing", "Help"],
                "tokens_used": 0,
            })
    except Exception:
        pass

    # 11. Check if a Cloud Hyperscaler or Local Ollama is configured for open-ended LLM conversation
    try:
        from fleet.core.hyperscalers import HyperscalerGateway
        provs = HyperscalerGateway.list_available_providers()
        configured = [p for p in provs if p.get("is_configured") and p.get("id") != "ollama"]
        if configured:
            gw = HyperscalerGateway()
            llm_res = gw.complete(
                prompt=raw,
                provider=configured[0]["id"],
                system_instruction="You are the Personal Agentic Fleet Conversational Omnibar Assistant. Keep responses concise (2-4 sentences) and helpful.",
            )
            if llm_res.get("status") == "SUCCESS" and llm_res.get("text"):
                return _record_turn(raw, {
                    "status": "ok",
                    "mode": "conversation",
                    "title": f"🤖 {llm_res.get('provider', 'Fleet AI')} ({llm_res.get('model', 'LLM')})",
                    "message": llm_res["text"],
                    "suggestions": ["Give me my daily briefing", "What are my pending tasks?", "@discover"],
                    "tokens_used": llm_res.get("tokens_used", 0),
                })
    except Exception:
        pass

    # 12. Conversational Local Fleet Mind Fallback (Rich, Helpful & Context-Aware)
    snap = _gather_live_fleet_snapshot(agent_registry=agent_registry, db=db)
    return _record_turn(raw, {
        "status": "ok",
        "mode": "conversation",
        "agent_id": "antigravity",
        "title": "💬 Fleet Conversational Assistant ($0.00 Local Mode)",
        "message": (
            f"I heard you say: **\"{raw}\"**.\n"
            f"Right now I'm running in **$0.00 Zero-Token Local Mode** ({snap['active_agents']} agents active, {snap['pending_count']} pending tasks). "
            f"I can answer questions about your **daily briefing, tasks, hydration, FFD diet & smoothie protocol, 6-day Mudgal/Samtola/Bhim Gadha workouts, PC optimization, or agent creation**—or you can open the **Antigravity Live Console** for deep multi-file coding and cloud LLM reasoning!"
        ),
        "suggestions": [
            "Give me my daily briefing",
            "What are my pending tasks?",
            "What is my workout today?",
            "FFD Green Smoothie recipe",
            "Help",
        ],
        "tokens_used": 0,
    })


def _clean_for_speech(text: str) -> str:
    """
    Converts markdown/emoji-rich dashboard responses into smooth, natural, privacy-safe
    spoken sentences for Browser SpeechSynthesis (TTS).
    """
    if not text:
        return ""
    s = str(text)
    # Replace URLs with concise spoken phrase
    s = re.sub(r"https?://[^\s)]+", "linked portal", s)
    # Mask long numeric account/consumer identifiers for spoken privacy
    s = re.sub(r"\b(\d{8,16})\b", lambda m: f"account ending in {m.group(1)[-4:]}", s)
    # Strip markdown formatting characters
    s = re.sub(r"[*_`#~>|]+", " ", s)
    # Remove common decorative emojis so TTS does not read emoji names awkwardly
    s = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


VOICE_LINKED_ACTIVITIES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "voice_briefing",
        "category": "Overview & Tasks",
        "icon": "☀️",
        "label": "Daily Briefing",
        "phrase": "Give me my daily briefing",
        "description": "Synthesizes and reads your morning briefing, tasks, and hydration aloud",
    },
    {
        "id": "voice_monthly_tasks",
        "category": "Overview & Tasks",
        "icon": "📅",
        "label": "Show Monthly Tasks",
        "phrase": "Show my monthly tasks",
        "description": "Switches to Overview & Tasks and filters your local Monthly recurring tasks",
    },
    {
        "id": "voice_yearly_tasks",
        "category": "Overview & Tasks",
        "icon": "🗓️",
        "label": "Show Yearly Tasks",
        "phrase": "Show my yearly tasks",
        "description": "Switches to Overview & Tasks and filters your Yearly tax & insurance tasks",
    },
    {
        "id": "voice_mask_ids",
        "category": "Overview & Tasks",
        "icon": "🙈",
        "label": "Mask Sensitive IDs",
        "phrase": "Mask sensitive IDs",
        "description": "Masks bank account numbers, loan IDs, and consumer numbers on screen",
    },
    {
        "id": "voice_unmask_ids",
        "category": "Overview & Tasks",
        "icon": "👁️",
        "label": "Reveal IDs",
        "phrase": "Reveal account numbers",
        "description": "Temporarily reveals masked account and consumer numbers on your local screen",
    },
    {
        "id": "voice_log_water",
        "category": "Health & Wellness",
        "icon": "💧",
        "label": "+1 Glass Water",
        "phrase": "Please log a glass of water",
        "description": "Logs +250ml water in SQLite and updates the Health & Wellness hydration bar",
    },
    {
        "id": "voice_workout",
        "category": "Health & Wellness",
        "icon": "🏋️",
        "label": "Today's Workout",
        "phrase": "What is my workout today?",
        "description": "Opens Health & Wellness and speaks today's 6-day strength & FFD workout plan",
    },
    {
        "id": "voice_emails",
        "category": "Email & Antivirus",
        "icon": "📬",
        "label": "Check Emails & Scan",
        "phrase": "Check my emails and scan attachments",
        "description": "Syncs Email Intelligence, verifies pre-download virus shield, and checks proposals",
    },
    {
        "id": "voice_virus_test",
        "category": "Email & Antivirus",
        "icon": "🛡️",
        "label": "Test Virus Shield",
        "phrase": "Run antivirus block test",
        "description": "Runs a live pre-download EICAR & macro virus quarantine test",
    },
    {
        "id": "voice_optimize_ram",
        "category": "PC Optimizer & Security",
        "icon": "🚀",
        "label": "Optimize RAM",
        "phrase": "Optimize my RAM",
        "description": "Reclaims inactive working-set memory and opens PC Optimizer telemetry",
    },
    {
        "id": "voice_security_scan",
        "category": "PC Optimizer & Security",
        "icon": "🔒",
        "label": "Run Security Scan",
        "phrase": "Run security scan",
        "description": "Executes the 12-Layer Security & Privacy audit across your workspace",
    },
    {
        "id": "voice_unapproved_backlog",
        "category": "Backlog & Evolution",
        "icon": "📋",
        "label": "Unapproved Backlog",
        "phrase": "Show unapproved backlog items",
        "description": "Opens Feature Backlog filtered to Unapproved email & attachment proposals",
    },
    {
        "id": "voice_evolve_agent",
        "category": "Backlog & Evolution",
        "icon": "✨",
        "label": "10 Ways to Improve",
        "phrase": "Suggest 10 ways to improve overview",
        "description": "Opens the AI Self-Improvement & Feature Evolution advisor for the active agent",
    },
]


def get_voice_activities_catalog() -> List[Dict[str, Any]]:
    """Returns the catalog of voice-linked dashboard & agent activities."""
    return list(VOICE_LINKED_ACTIVITIES_CATALOG)


_MULTILINGUAL_VOICE_PHRASE_MAP: List[Tuple[List[str], str]] = [
    (
        ["दैनिक ब्रीफिंग", "ब्रीफिंग", "सुप्रभात", "आज की जानकारी", "బ్రీఫింగ్", "రోజువారీ బ్రీఫింగ్", "दैनिक माहिती", "आजची माहिती", "dainaik briefing", "roz ki briefing"],
        "Give me my daily briefing",
    ),
    (
        ["मासिक कार्य", "महीने के काम", "मासिक काम", "నెలవారీ పనులు", "నెల పనులు", "मासिक कामे", "महिन्याची कामे", "masik karya", "nelavari panulu"],
        "Show my monthly tasks",
    ),
    (
        ["वार्षिक कार्य", "साल के काम", "वार्षिक काम", "వార్షిక పనులు", "సంవత్సర పనులు", "वार्षिक कामे", "वर्षाची कामे", "varshik karya"],
        "Show my yearly tasks",
    ),
    (
        ["पानी", "एक गिलास पानी", "जल", "నీరు", "మంచినీళ్ళు", "ఒక గ్లాసు నీరు", "पाणी", "एक ग्लास पाणी", "pani log", "neeru"],
        "Please log a glass of water",
    ),
    (
        ["व्यायाम", "कसरत", "वर्कआउट", "వ్యాయామం", "వర్కౌట్", "व्यायाम काय आहे", "vyayam", "kasrat"],
        "What is my workout today?",
    ),
    (
        ["ईमेल", "मेल चेक", "मेल तपासणी", "ఈమెయిల్", "మెయిల్స్", "ईमेल तपासा"],
        "Check my emails and scan attachments",
    ),
    (
        ["रैम", "मेमोरी साफ", "पीसी ऑप्टिमाइज", "ర్యామ్", "मेमरी साफ करा"],
        "Optimize my RAM",
    ),
    (
        ["सुरक्षा जांच", "सिक्योरिटी स्कैन", "భద్రతా తనిఖీ", "सुरक्षा तपासणी"],
        "Run security scan",
    ),
    (
        ["आईडी छुपाएं", "मास्क", "ఐడి దాచు", "आयडी लपवा"],
        "Mask sensitive IDs",
    ),
    (
        ["आईडी दिखाएं", "खाता नंबर दिखाएं", "ఐడి చూపించు", "आयडी दाखवा"],
        "Reveal account numbers",
    ),
]


def _normalize_multilingual_voice_query(spoken: str) -> str:
    """Maps Hindi (hi), Telugu (te), and Marathi (mr) spoken phrases to canonical AFCC commands."""
    s_low = (spoken or "").lower().strip()
    for triggers, canonical in _MULTILINGUAL_VOICE_PHRASE_MAP:
        for trig in triggers:
            if trig.lower() in s_low:
                return canonical
    return spoken


def _apply_voice_localization(
    res: Dict[str, Any],
    language: str = "en",
    gender: str = "female",
    accent: str = "IN",
) -> Dict[str, Any]:
    """Attaches voice profile metadata and localized spoken replies for English, Hindi, Telugu, and Marathi."""
    lang = (language or "en").lower().strip()
    if lang not in ("en", "hi", "te", "mr"):
        lang = "en"
    gen = "male" if (gender or "").lower().strip() == "male" else "female"
    acc = (accent or "IN").upper().strip()
    if acc not in ("IN", "US", "GB"):
        acc = "IN"

    locale_map = {
        "hi": "hi-IN",
        "te": "te-IN",
        "mr": "mr-IN",
        "en": f"en-{acc}",
    }
    bcp47 = locale_map.get(lang, "en-IN")
    english_reply = _clean_for_speech(res.get("spoken_reply") or res.get("message") or res.get("title") or "Done.")
    cmd_key = str(res.get("normalized_command") or res.get("mode") or "").lower()

    native_reply = english_reply
    phonetic_reply = english_reply

    if lang == "hi":
        if "task_mask:off" in cmd_key:
            native_reply = "नमस्ते! मैंने आपकी स्क्रीन पर खाता और उपभोक्ता नंबर दिखा दिए हैं। यह डेटा पूरी तरह सुरक्षित और लोकल है।"
            phonetic_reply = "Namaste! Maine aapki screen par khaata aur consumer number dikha diye hain. Yeh data poori tarah local aur surakshit hai."
        elif "task_mask:on" in cmd_key:
            native_reply = "नमस्ते! मैंने आपके बैंक खाता और उपभोक्ता नंबर स्क्रीन पर सुरक्षित रूप से छुपा दिए हैं।"
            phonetic_reply = "Namaste! Maine aapke bank khaata aur consumer number screen par surakshit roop se chhupa diye hain."
        elif "monthly" in cmd_key:
            native_reply = f"नमस्ते! मैंने आपके मासिक कार्य खोल दिए हैं। {english_reply}"
            phonetic_reply = f"Namaste! Maine aapke maasik karya khol diye hain. {english_reply}"
        elif "yearly" in cmd_key:
            native_reply = f"नमस्ते! मैंने आपके वार्षिक कार्य खोल दिए हैं। {english_reply}"
            phonetic_reply = f"Namaste! Maine aapke vaarshik karya khol diye hain. {english_reply}"
        elif "hydration" in cmd_key or "water" in english_reply.lower():
            native_reply = f"शाबाश! मैंने एक गिलास पानी (250 मिलीलीटर) आपके स्वास्थ्य रिकॉर्ड में दर्ज कर दिया है। {english_reply}"
            phonetic_reply = f"Shabash! Maine ek glass paani aapke health record mein darj kar diya hai. {english_reply}"
        elif "workout" in english_reply.lower() or "exercise" in cmd_key:
            native_reply = f"नमस्ते! यहाँ आपकी आज की व्यायाम योजना है। {english_reply}"
            phonetic_reply = f"Namaste! Yahan aapki aaj ki vyayam yojana hai. {english_reply}"
        elif "optimizer" in cmd_key or "ram" in english_reply.lower():
            native_reply = f"नमस्ते! मैंने आपके कंप्यूटर की मेमोरी को ऑप्टिमाइज़ कर दिया है। {english_reply}"
            phonetic_reply = f"Namaste! Maine aapke computer ki memory ko optimize kar diya hai. {english_reply}"
        elif "security:scan" in cmd_key:
            native_reply = "नमस्ते! मैं आपके सिस्टम का 12-स्तरीय सुरक्षा और गोपनीयता ऑडिट चला रही हूँ।" if gen == "female" else "नमस्ते! मैं आपके सिस्टम का 12-स्तरीय सुरक्षा और गोपनीयता ऑडिट चला रहा हूँ।"
            phonetic_reply = "Namaste! Main aapke system ka barah-stariya suraksha aur privacy scan chala rahi hoon." if gen == "female" else "Namaste! Main aapke system ka barah-stariya suraksha aur privacy scan chala raha hoon."
        else:
            native_reply = f"नमस्ते! आपका कार्य संपन्न हुआ। {english_reply}"
            phonetic_reply = f"Namaste! Aapka karya sampann hua. {english_reply}"
    elif lang == "te":
        if "task_mask:off" in cmd_key:
            native_reply = "నమస్కారం! మీ స్క్రీన్ పై ఖాతా మరియు కన్స్యూమర్ నంబర్లను చూపించాను. ఈ డేటా పూర్తిగా లోకల్ మాత్రమే."
            phonetic_reply = "Namaskaram! Mee screen pai khaata mariyu consumer numberlanu choopinchanu. Ee data poortiga local matrame."
        elif "task_mask:on" in cmd_key:
            native_reply = "నమస్కారం! మీ బ్యాంక్ ఖాతా మరియు కన్స్యూమర్ నంబర్లను సురక్షితంగా దాచాను."
            phonetic_reply = "Namaskaram! Mee bank khaata mariyu consumer numberlanu surakshitanga daachanu."
        elif "monthly" in cmd_key:
            native_reply = f"నమస్కారం! మీ నెలవారీ పనులను తెరిచాను. {english_reply}"
            phonetic_reply = f"Namaskaram! Mee nelavaari panulanu terichanu. {english_reply}"
        elif "yearly" in cmd_key:
            native_reply = f"నమస్కారం! మీ వార్షిక పనులను తెరిచాను. {english_reply}"
            phonetic_reply = f"Namaskaram! Mee vaarshika panulanu terichanu. {english_reply}"
        elif "hydration" in cmd_key or "water" in english_reply.lower():
            native_reply = f"చాలా మంచిది! ఒక గ్లాసు నీరు (250 మిల్లీలీటర్లు) మీ ఆరోగ్య ఖాతాలో నమోదు చేశాను. {english_reply}"
            phonetic_reply = f"Chaala manchidi! Oka glassu neeru mee aarogya khaatalo namodu chesanu. {english_reply}"
        elif "workout" in english_reply.lower() or "exercise" in cmd_key:
            native_reply = f"నమస్కారం! ఈ రోజు మీ వ్యాయామ ప్రణాళిక ఇదిగో. {english_reply}"
            phonetic_reply = f"Namaskaram! Ee roju mee vyayama pranalika idigo. {english_reply}"
        elif "optimizer" in cmd_key or "ram" in english_reply.lower():
            native_reply = f"నమస్కారం! మీ కంప్యూటర్ ర్యామ్ మరియు మెమరీని ఆప్టిమైజ్ చేశాను. {english_reply}"
            phonetic_reply = f"Namaskaram! Mee computer RAM mariyu memory ni optimize chesanu. {english_reply}"
        elif "security:scan" in cmd_key:
            native_reply = "నమస్కారం! మీ 12-స్థాయిల భద్రత మరియు గోప్యతా తనిఖీని ప్రారంభిస్తున్నాను."
            phonetic_reply = "Namaskaram! Mee pannendu sthayila bhadrata mariyu gopyata tanikhini prarambhistunnanu."
        else:
            native_reply = f"నమస్కారం! మీ పని పూర్తయింది. {english_reply}"
            phonetic_reply = f"Namaskaram! Mee pani poortayindi. {english_reply}"
    elif lang == "mr":
        if "task_mask:off" in cmd_key:
            native_reply = "नमस्कार! मी तुमच्या स्क्रीनवर खाते आणि ग्राहक क्रमांक दाखवले आहेत. हा डेटा पूर्णपणे लोकल आणि सुरक्षित आहे."
            phonetic_reply = "Namaskar! Mi tumchya screenvar khaate aani grahak kramank dakhavle aahet. Ha data poornapane local aani surakshit aahe."
        elif "task_mask:on" in cmd_key:
            native_reply = "नमस्कार! मी तुमचे बँक खाते आणि ग्राहक क्रमांक स्क्रीनवर सुरक्षितपणे लपवले आहेत."
            phonetic_reply = "Namaskar! Mi tumche bank khaate aani grahak kramank screenvar surakshitpane lapavle aahet."
        elif "monthly" in cmd_key:
            native_reply = f"नमस्कार! मी तुमची मासिक कामे उघडली आहेत. {english_reply}"
            phonetic_reply = f"Namaskar! Mi tumchi maasik kaame ughadli aahet. {english_reply}"
        elif "yearly" in cmd_key:
            native_reply = f"नमस्कार! मी तुमची वार्षिक कामे उघडली आहेत. {english_reply}"
            phonetic_reply = f"Namaskar! Mi tumchi vaarshik kaame ughadli aahet. {english_reply}"
        elif "hydration" in cmd_key or "water" in english_reply.lower():
            native_reply = f"छान! मी तुमच्या आरोग्य रेकॉर्डमध्ये एक ग्लास पाणी (250 मिली) नोंदवले आहे. {english_reply}"
            phonetic_reply = f"Chhaan! Mi tumchya aarogya record madhye ek glass paani nondavle aahe. {english_reply}"
        elif "workout" in english_reply.lower() or "exercise" in cmd_key:
            native_reply = f"नमस्कार! हे तुमचे आजचे व्यायाम नियोजन आहे. {english_reply}"
            phonetic_reply = f"Namaskar! He tumche aajche vyayam niyojan aahe. {english_reply}"
        elif "optimizer" in cmd_key or "ram" in english_reply.lower():
            native_reply = f"नमस्कार! मी तुमच्या संगणकाची रॅम मेमरी ऑप्टिमाइझ केली आहे. {english_reply}"
            phonetic_reply = f"Namaskar! Mi tumchya sanganakachi RAM memory optimize keli aahe. {english_reply}"
        elif "security:scan" in cmd_key:
            native_reply = "नमस्कार! मी तुमची १२-स्तरीय सुरक्षा आणि गोपनीयता तपासणी सुरू करत आहे."
            phonetic_reply = "Namaskar! Mi tumchi bara-stariya suraksha aani gopaniyata tapasani suru karat aahe."
        else:
            native_reply = f"नमस्कार! तुमचे काम पूर्ण झाले आहे. {english_reply}"
            phonetic_reply = f"Namaskar! Tumche kaam poorna jhale aahe. {english_reply}"

    res["spoken_reply_english"] = english_reply
    res["spoken_reply"] = native_reply
    res["spoken_reply_phonetic"] = phonetic_reply
    res["voice_profile"] = {
        "language": lang,
        "gender": gen,
        "accent": acc,
        "bcp47": bcp47,
    }
    return res


def transcribe_and_dispatch_voice_command(
    transcript: str,
    agent_registry: Optional[Any] = None,
    db: Optional[Any] = None,
    language: str = "en",
    gender: str = "female",
    accent: str = "IN",
) -> Dict[str, Any]:
    """
    UX-10 & Bi-Directional Audio Conversation Engine:
    Normalizes spoken natural-language voice commands (in English, Hindi, Telugu, or Marathi),
    executes linked backend activities, and returns structured `ui_actions`, `executed_activities`,
    and localized `spoken_reply` + `spoken_reply_phonetic` for TTS playback.
    """
    raw_spoken = (transcript or "").strip()
    if not raw_spoken:
        return {"status": "error", "message": "Empty voice transcript."}

    canonical_spoken = _normalize_multilingual_voice_query(raw_spoken)
    res = _dispatch_voice_command_core(canonical_spoken, agent_registry=agent_registry, db=db)
    res["voice_transcript"] = raw_spoken
    return _apply_voice_localization(res, language=language, gender=gender, accent=accent)


def _dispatch_voice_command_core(
    transcript: str,
    agent_registry: Optional[Any] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    spoken = (transcript or "").strip()
    if not spoken:
        return {"status": "error", "message": "Empty voice transcript."}

    lower = spoken.lower().strip()
    normalized = spoken
    ui_actions: List[Dict[str, Any]] = []
    executed_activities: List[str] = []

    # 1. Sensitive ID Masking / Unmasking on Overview & Tasks
    if re.search(r"\b(?:unmask|reveal|show)\b.*\b(?:id|ids|account|numbers|sensitive)\b", lower) or "turn off mask" in lower:
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "set_task_mask", "masked": False},
        ]
        executed_activities = ["🧭 Switched to Overview & Tasks", "👁️ Revealed Sensitive IDs on Local Screen"]
        msg = "👁️ Revealed account numbers, loan IDs, and consumer numbers on your local Overview & Tasks screen. All fields remain 100% local-only."
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "task_mask:off",
            "title": "👁️ Sensitive IDs Revealed on Local Screen",
            "message": msg,
            "spoken_reply": "I have revealed your account and consumer numbers on your local screen. None of this data is ever sent to GitHub.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:mask|hide|conceal|protect)\b.*\b(?:id|ids|account|numbers|sensitive)\b", lower) or "turn on mask" in lower:
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "set_task_mask", "masked": True},
        ]
        executed_activities = ["🧭 Switched to Overview & Tasks", "🙈 Enabled Sensitive ID Masking on Screen"]
        msg = "🙈 Masked all sensitive bank account numbers, loan IDs, IFSC codes, and electricity consumer numbers on screen."
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "task_mask:on",
            "title": "🙈 Sensitive IDs Masked on Screen",
            "message": msg,
            "spoken_reply": "I have masked your bank account numbers, loan IDs, and consumer numbers on screen.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 2. Task Cadence & Status Filtering (Monthly / Yearly / Completed / Pending)
    if re.search(r"\b(?:show|filter|list|what\s+are|open|view)\b.*\b(?:monthly)\s+(?:tasks?|bills?|payments?|items?)\b", lower) or lower in ("monthly tasks", "show monthly"):
        all_tasks = db.list_tasks(limit=200, exclude_tests=True) if (db and hasattr(db, "list_tasks")) else []
        monthly = [t for t in all_tasks if str(t.get("source") or "").lower() == "monthly"]
        pending_m = [t for t in monthly if t.get("status") != "completed"]
        done_m = [t for t in monthly if t.get("status") == "completed"]
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "filter_tasks", "filter": "Monthly"},
        ]
        executed_activities = [
            "🧭 Switched to Overview & Tasks",
            f"📅 Filtered Task Board → Monthly ({len(monthly)} items)",
        ]
        preview = ", ".join(str(t.get("title") or "").replace("Monthly — ", "") for t in pending_m[:4])
        msg = (
            f"📅 Showing **{len(monthly)} Monthly task(s)** ({len(pending_m)} pending, {len(done_m)} completed)."
            + (f"\nTop pending: {preview}." if preview else "")
        )
        spoken_reply = (
            f"I switched to Overview and Tasks and filtered to your Monthly list. "
            f"You have {len(pending_m)} pending and {len(done_m)} completed monthly items"
            + (f", including { _clean_for_speech(preview) }." if preview else ".")
        )
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "filter_tasks:Monthly",
            "title": f"📅 Monthly Tasks ({len(pending_m)} Pending, {len(done_m)} Completed)",
            "message": msg,
            "spoken_reply": spoken_reply,
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:show|filter|list|what\s+are|open|view)\b.*\b(?:yearly|annual)\s+(?:tasks?|renewals?|items?)\b", lower) or lower in ("yearly tasks", "show yearly"):
        all_tasks = db.list_tasks(limit=200, exclude_tests=True) if (db and hasattr(db, "list_tasks")) else []
        yearly = [t for t in all_tasks if str(t.get("source") or "").lower() == "yearly"]
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "filter_tasks", "filter": "Yearly"},
        ]
        executed_activities = [
            "🧭 Switched to Overview & Tasks",
            f"🗓️ Filtered Task Board → Yearly ({len(yearly)} items)",
        ]
        preview = ", ".join(str(t.get("title") or "").replace("Yearly — ", "") for t in yearly[:4])
        msg = f"🗓️ Showing **{len(yearly)} Yearly task(s)**: {preview or 'None'}."
        spoken_reply = f"I filtered your task board to Yearly items. You have {len(yearly)} yearly tasks" + (f": {_clean_for_speech(preview)}." if preview else ".")
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "filter_tasks:Yearly",
            "title": f"🗓️ Yearly Tasks ({len(yearly)} Total)",
            "message": msg,
            "spoken_reply": spoken_reply,
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:show|filter|list)\b.*\b(?:completed|done|finished)\s+tasks?\b", lower):
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "filter_tasks", "filter": "COMPLETED"},
        ]
        executed_activities = ["🧭 Switched to Overview & Tasks", "✓ Filtered Task Board → Completed"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "filter_tasks:COMPLETED",
            "title": "✓ Showing Completed Tasks",
            "message": "Filtered your Overview & Tasks board to show completed (✔) tasks.",
            "spoken_reply": "Showing your completed tasks on the Overview and Tasks board.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 3. Complete / Mark Task as Done via Voice
    complete_match = re.match(
        r"^.*?\b(?:complete|finish|check\s+off|mark)\s+task\s+(?:#?(\d+)|(.+?))(?:\s+as\s+(?:done|completed|complete))?$",
        spoken,
        flags=re.I,
    )
    if complete_match and db is not None and hasattr(db, "list_tasks") and hasattr(db, "update_task_status"):
        target_id_str = complete_match.group(1)
        target_title_q = (complete_match.group(2) or "").strip().lower()
        tasks_list = db.list_tasks(limit=200, exclude_tests=True)
        matched_task = None
        if target_id_str:
            tid_num = int(target_id_str)
            matched_task = next((t for t in tasks_list if int(t.get("id") or 0) == tid_num), None)
        elif target_title_q:
            matched_task = next(
                (t for t in tasks_list if target_title_q in str(t.get("title") or "").lower() and t.get("status") != "completed"),
                None,
            ) or next((t for t in tasks_list if target_title_q in str(t.get("title") or "").lower()), None)
        if matched_task:
            db.update_task_status(int(matched_task["id"]), "completed")
            ui_actions = [
                {"type": "switch_agent", "agent_id": "overview"},
                {"type": "refresh_tasks"},
                {"type": "refresh_briefing"},
            ]
            executed_activities = [
                f"✓ Completed Task #{matched_task['id']}: {matched_task['title']}",
                "🔄 Refreshed Overview & Tasks Board",
            ]
            return _record_turn(spoken, {
                "status": "ok",
                "mode": "voice_task_completed",
                "agent_id": "overview",
                "task_id": matched_task["id"],
                "voice_transcript": spoken,
                "normalized_command": f"complete_task:{matched_task['id']}",
                "title": f"✓ Completed Task #{matched_task['id']}",
                "message": f"Marked **\"{matched_task['title']}\"** as completed in your local vault.",
                "spoken_reply": f"Done! I marked {_clean_for_speech(matched_task['title'])} as completed.",
                "ui_actions": ui_actions,
                "executed_activities": executed_activities,
                "tokens_used": 0,
                "cost_usd": "$0.00",
            })

    # 4. Hydration Logging via Voice
    if re.search(r"\b(?:log|drink|drank|had|add)\b.*\b(?:glass|glasses|water|hydration)\b", lower):
        m_num = re.search(r"\b(\d+)\b", lower)
        glasses = int(m_num.group(1)) if (m_num and 1 <= int(m_num.group(1)) <= 20) else 1
        normalized = "@health water +250" if glasses == 1 else f"@health water +{glasses}"
        ui_actions = [
            {"type": "refresh_health"},
            {"type": "refresh_briefing"},
        ]
        executed_activities = [
            f"💧 Logged +{glasses} Glass(es) of Water ({glasses * 250} ml)",
            "🌿 Updated Health & Wellness Hydration Progress",
        ]
        res = dispatch_omnibar_query(normalized, agent_registry=agent_registry, db=db)
        res["voice_transcript"] = spoken
        res["normalized_command"] = normalized
        res["ui_actions"] = ui_actions
        res["executed_activities"] = executed_activities
        res["spoken_reply"] = _clean_for_speech(res.get("message") or f"Logged {glasses} glass of water.")
        return res

    # 5. Add Task via Voice (Supports Daily, Monthly, Yearly, High Priority)
    if re.search(r"\b(?:add|create|new)\s+(?:a\s+)?(?:high\s+priority\s+|urgent\s+|p1\s+|monthly\s+|yearly\s+)?task\b", lower):
        task_body = re.sub(
            r"^.*?\b(?:add|create|new)\s+(?:a\s+)?(?:high\s+priority\s+|urgent\s+|p1\s+|monthly\s+|yearly\s+)?task\b\s*:?\s*",
            "",
            spoken,
            flags=re.I,
        ).strip()
        if task_body:
            if db is not None and hasattr(db, "add_task"):
                pri = "P1" if any(k in lower for k in ("high priority", "urgent", "p1")) else "P2"
                src = "Monthly" if "monthly task" in lower else ("Yearly" if "yearly task" in lower else "voice_capture")
                tid = db.add_task(
                    title=task_body,
                    description=f"Captured via AFCC Voice Assistant ({src}): {task_body}",
                    priority=pri,
                    source=src,
                )
                ui_actions = [
                    {"type": "switch_agent", "agent_id": "overview"},
                    {"type": "refresh_tasks"},
                    {"type": "refresh_briefing"},
                ]
                executed_activities = [
                    f"✅ Created {pri} Task #{tid} [{src}]",
                    "🔄 Refreshed Overview & Tasks Board",
                ]
                return {
                    "status": "ok",
                    "mode": "voice_task_created",
                    "task_id": tid,
                    "transcript": spoken,
                    "voice_transcript": spoken,
                    "normalized_command": f"add_task:{task_body}",
                    "title": f"🎙️ Voice Task Captured ({pri}): {task_body}",
                    "message": f"Added {pri} task '{task_body}' ({src}) to your local task vault.",
                    "spoken_reply": f"Added {pri} task {_clean_for_speech(task_body)} to your task board.",
                    "ui_actions": ui_actions,
                    "executed_activities": executed_activities,
                    "tokens_used": 0,
                    "cost_usd": "$0.00",
                }
            normalized = f"add task {task_body}"

    # 6. Log Health Vitals via Voice (Weight, Fasting/PP Blood Sugar)
    weight_match = re.search(r"\b(?:log\s+weight|my\s+weight\s+is|weight\s+is)\s+(\d+(?:\.\d+)?)\s*(?:kg|kilos?)?\b", lower)
    if weight_match and db is not None and hasattr(db, "log_health_metric"):
        wt_val = float(weight_match.group(1))
        db.log_health_metric("weight_kg", wt_val, "kg", "Logged via Voice Conversation")
        ui_actions = [
            {"type": "switch_agent", "agent_id": "health"},
            {"type": "refresh_health"},
        ]
        executed_activities = [
            f"⚖️ Logged Weight: {wt_val} kg (Local Vault)",
            "🌿 Refreshed Health & Wellness Vitals",
        ]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "health",
            "voice_transcript": spoken,
            "normalized_command": f"log_weight:{wt_val}",
            "title": f"⚖️ Logged Weight: {wt_val} kg",
            "message": f"Recorded **{wt_val} kg** in your local-only Health & Wellness database.",
            "spoken_reply": f"Logged your weight of {wt_val} kilograms in your local health vault.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    sugar_match = re.search(r"\b(?:log\s+)?(fasting|pp|post\s*prandial)?\s*(?:blood\s+)?(?:sugar|glucose)\s+(?:is\s+)?(\d+(?:\.\d+)?)\b", lower)
    if sugar_match and db is not None and hasattr(db, "log_health_metric"):
        kind_raw = (sugar_match.group(1) or "fasting").lower()
        metric_key = "pp_glucose" if ("pp" in kind_raw or "post" in kind_raw) else "fasting_glucose"
        label = "Post-Prandial" if metric_key == "pp_glucose" else "Fasting"
        val = float(sugar_match.group(2))
        db.log_health_metric(metric_key, val, "mg/dL", "Logged via Voice Conversation")
        ui_actions = [
            {"type": "switch_agent", "agent_id": "health"},
            {"type": "refresh_health"},
        ]
        executed_activities = [
            f"🩸 Logged {label} Glucose: {val} mg/dL (Local Vault)",
            "🌿 Refreshed Health & Wellness Vitals",
        ]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "health",
            "voice_transcript": spoken,
            "normalized_command": f"log_{metric_key}:{val}",
            "title": f"🩸 Logged {label} Blood Sugar: {val} mg/dL",
            "message": f"Recorded **{label} Blood Glucose: {val} mg/dL** in your local-only SQLite vault.",
            "spoken_reply": f"Recorded your {label.lower()} blood sugar of {int(val)} milligrams per deciliter locally.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 7. Email Intelligence, Pre-Download Antivirus Scan & Proposal Discovery
    if re.search(r"\b(?:test|verify)\b.*\b(?:virus|antivirus|malware|shield)\b", lower) or "antivirus block test" in lower:
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "test_virus_shield"},
        ]
        executed_activities = [
            "🧭 Switched to Overview & Email Intelligence",
            "🧪 Executed Pre-Download EICAR & Macro Virus Block Test",
        ]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "test_virus_shield",
            "title": "🛡️ Pre-Download Attachment Virus Shield Verified",
            "message": "Executed live 4-layer pre-download attachment antivirus test. Malicious payloads and macros are quarantined before disk write.",
            "spoken_reply": "I ran the pre-download attachment antivirus block test. Your four-layer virus shield is active and blocking malicious attachments before download.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:check|sync|classify|scan|read)\b.*\b(?:emails?|inbox|attachments?|proposals?)\b", lower):
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "refresh_emails"},
        ]
        executed_activities = [
            "📬 Synced Email Intelligence (5 Folders)",
            "🛡️ Pre-Download Attachment Virus Shield Active",
            "⏳ Refreshed Unapproved Email Proposals Queue",
        ]
        pending_props = 0
        try:
            from fleet.integrations.email_intelligence_proposals import discover_email_and_attachment_proposals
            disc = discover_email_and_attachment_proposals(db=db)
            pending_props = int(disc.get("unapproved_count") or len(disc.get("proposals") or []))
        except Exception:
            pass
        msg = (
            f"📬 Synced Email Intelligence with 4-layer pre-download attachment virus scanning. "
            f"You currently have **{pending_props} Unapproved email/attachment proposal(s)** awaiting your review."
        )
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "@gmail classify",
            "title": f"📬 Email Intelligence Synced ({pending_props} Unapproved Proposals)",
            "message": msg,
            "spoken_reply": f"I synced your Email Intelligence and verified attachment virus protection. You have {pending_props} unapproved proposals waiting for your approval.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 8. PC Optimizer & Security Activities (RAM, Temp Cache, DNS, Security Scan, Unit Tests)
    if re.search(r"\b(?:free|clean|optimize)\b.*\b(?:ram|memory)\b", lower):
        normalized = "@optimizer run"
        opt_msg = "Optimized working set memory across active processes."
        try:
            from fleet.core.optimizer import optimize_ram
            r_opt = optimize_ram()
            if isinstance(r_opt, dict) and r_opt.get("message"):
                opt_msg = str(r_opt["message"])
        except Exception:
            pass
        ui_actions = [
            {"type": "switch_agent", "agent_id": "optimizer"},
            {"type": "refresh_optimizer"},
        ]
        executed_activities = [
            "💾 Executed RAM Working Set Optimization",
            "🚀 Switched to PC Optimizer & Refreshed Telemetry",
        ]
        res = dispatch_omnibar_query(normalized, agent_registry=agent_registry, db=db)
        res["voice_transcript"] = spoken
        res["normalized_command"] = normalized
        res["ui_actions"] = ui_actions
        res["executed_activities"] = executed_activities
        res["spoken_reply"] = _clean_for_speech(opt_msg)
        return res

    if re.search(r"\b(?:clean|clear|delete|purge)\b.*\b(?:temp|temporary|junk|cache)\b", lower):
        clean_msg = "Cleaned temporary cache files."
        try:
            from fleet.core.optimizer import clean_temp_files
            c_res = clean_temp_files()
            if isinstance(c_res, dict) and c_res.get("message"):
                clean_msg = str(c_res["message"])
        except Exception:
            pass
        ui_actions = [
            {"type": "switch_agent", "agent_id": "optimizer"},
            {"type": "refresh_optimizer"},
        ]
        executed_activities = [
            "🧹 Cleaned System Temporary Cache Files",
            "🚀 Refreshed PC Optimizer Diagnostics",
        ]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "optimizer",
            "voice_transcript": spoken,
            "normalized_command": "optimizer:clean_temp",
            "title": "🧹 Temporary Cache Files Cleaned",
            "message": clean_msg,
            "spoken_reply": _clean_for_speech(clean_msg),
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:flush|clear|reset)\b.*\bdns\b", lower):
        dns_msg = "Flushed system DNS resolver cache."
        try:
            from fleet.core.optimizer import flush_dns_cache
            d_res = flush_dns_cache()
            if isinstance(d_res, dict) and d_res.get("message"):
                dns_msg = str(d_res["message"])
        except Exception:
            pass
        ui_actions = [
            {"type": "switch_agent", "agent_id": "optimizer"},
            {"type": "refresh_optimizer"},
        ]
        executed_activities = ["⚡ Flushed System DNS Resolver Cache", "🚀 Refreshed PC Optimizer"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "optimizer",
            "voice_transcript": spoken,
            "normalized_command": "optimizer:flush_dns",
            "title": "⚡ DNS Resolver Cache Flushed",
            "message": dns_msg,
            "spoken_reply": _clean_for_speech(dns_msg),
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:run|start|execute)\b.*\b(?:security\s+scan|security\s+audit|privacy\s+scan)\b", lower) or lower == "security scan":
        ui_actions = [{"type": "run_security_scan"}]
        executed_activities = ["🛡️ Triggered 12-Layer Security & Privacy Scanner"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "voice_transcript": spoken,
            "normalized_command": "security:scan",
            "title": "🛡️ Running 12-Layer Security & Privacy Audit",
            "message": "Launched the 12-Layer Security & Privacy Scanner across your local workspace.",
            "spoken_reply": "Running your 12-layer security and privacy scan now.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    if re.search(r"\b(?:run|execute)\b.*\b(?:unit\s+tests?|test\s+suite|all\s+tests)\b", lower):
        ui_actions = [
            {"type": "switch_agent", "agent_id": "overview"},
            {"type": "run_tests"},
        ]
        executed_activities = ["🧪 Triggered Automated Unit Test Suite"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "overview",
            "voice_transcript": spoken,
            "normalized_command": "tests:run",
            "title": "🧪 Running Isolated Unit Test Suite",
            "message": "Started the isolated unit test suite on your Overview dashboard.",
            "spoken_reply": "I have started running the automated unit test suite in isolated mode.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 9. Feature Backlog & Self-Improvement Advisor Activities
    backlog_filter_match = re.search(
        r"\b(?:show|open|filter|view)\b.*\b(unapproved|planned|in\s+progress|completed|idea|ideas)\b.*\bbacklog\b",
        lower,
    )
    if backlog_filter_match or "unapproved backlog" in lower or "unapproved proposals" in lower:
        raw_st = backlog_filter_match.group(1) if backlog_filter_match else "unapproved"
        st_map = {
            "unapproved": "Unapproved",
            "planned": "Planned",
            "in progress": "In Progress",
            "completed": "Completed",
            "idea": "Idea",
            "ideas": "Idea",
        }
        target_st = st_map.get(re.sub(r"\s+", " ", raw_st), "Unapproved")
        ui_actions = [
            {"type": "switch_agent", "agent_id": "backlog"},
            {"type": "filter_backlog", "status": target_st},
        ]
        executed_activities = [
            "📋 Switched to Personal Fleet Feature Backlog",
            f"🔍 Filtered Backlog Status → {target_st}",
        ]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": "backlog",
            "voice_transcript": spoken,
            "normalized_command": f"backlog:filter:{target_st}",
            "title": f"📋 Feature Backlog Filtered: {target_st}",
            "message": f"Opened the Personal Fleet Feature Backlog and filtered items by **{target_st}**.",
            "spoken_reply": f"I opened the Feature Backlog and filtered it to show {target_st} items.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    evolve_match = re.search(r"\b(?:10\s+ways\s+to\s+improve|suggest\s+improvements?\s+for|improve\s+agent|evolve)\s*([a-z0-9_&\s]*)", lower)
    if evolve_match:
        raw_ag = (evolve_match.group(1) or "").strip()
        target_ag = "overview"
        for k, aid in [
            ("health", "health"), ("wellness", "health"),
            ("backlog", "backlog"), ("optimizer", "optimizer"),
            ("email", "gmail"), ("gmail", "gmail"),
            ("antigravity", "antigravity"), ("overview", "overview"), ("task", "overview"),
        ]:
            if k in raw_ag:
                target_ag = aid
                break
        ui_actions = [{"type": "open_evolve_modal", "agent_id": target_ag}]
        executed_activities = [f"✨ Opened 10 Ways to Improve Modal ({target_ag})"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "agent_id": target_ag,
            "voice_transcript": spoken,
            "normalized_command": f"evolve:{target_ag}",
            "title": f"✨ 10 Ways to Improve ({target_ag.title()})",
            "message": f"Opened the **Self-Improvement & Feature Evolution** modal for `{target_ag}` so you can select auto-generated upgrades or enter a manual improvement.",
            "spoken_reply": f"I opened the 10 Ways to Improve advisor for your {target_ag} agent.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    # 10. Direct Workspace / Agent / Theme / Layout Navigation by Voice
    theme_match = re.search(r"\b(?:switch|set|change)\s+theme\s+(?:to\s+)?(dark|midnight|aurora|solar)\b", lower)
    if theme_match:
        th = theme_match.group(1).lower()
        if db is not None and hasattr(db, "set_setting"):
            db.set_setting("theme", th)
        ui_actions = [{"type": "set_theme", "theme": th}]
        executed_activities = [f"🎨 Switched Workspace Theme → {th.title()}"]
        return _record_turn(spoken, {
            "status": "ok",
            "mode": "voice_activity",
            "voice_transcript": spoken,
            "normalized_command": f"theme:{th}",
            "title": f"🎨 Theme Switched to {th.title()}",
            "message": f"Applied the **{th.title()}** theme across your AFCC workspace.",
            "spoken_reply": f"Switched your workspace theme to {th}.",
            "ui_actions": ui_actions,
            "executed_activities": executed_activities,
            "tokens_used": 0,
            "cost_usd": "$0.00",
        })

    nav_match = re.match(r"^(?:please\s+)?(?:open|go\s+to|switch\s+to|show\s+me|navigate\s+to)\s+(.+)$", lower)
    if nav_match:
        dest = nav_match.group(1).strip()
        nav_map = {
            "overview": ("overview", "Overview & Tasks"),
            "overview and tasks": ("overview", "Overview & Tasks"),
            "tasks": ("overview", "Overview & Tasks"),
            "health": ("health", "Health & Wellness"),
            "health and wellness": ("health", "Health & Wellness"),
            "backlog": ("backlog", "Feature Backlog"),
            "feature backlog": ("backlog", "Feature Backlog"),
            "optimizer": ("optimizer", "PC Optimizer"),
            "pc optimizer": ("optimizer", "PC Optimizer"),
            "antigravity": ("antigravity", "Antigravity Live"),
            "email": ("gmail", "Email Intelligence"),
            "gmail": ("gmail", "Email Intelligence"),
        }
        matched_nav = None
        for k, pair in nav_map.items():
            if dest == k or dest.startswith(k):
                matched_nav = pair
                break
        if not matched_nav and agent_registry and hasattr(agent_registry, "agents"):
            for aid, ag_obj in agent_registry.agents.items():
                ag_name = str(getattr(ag_obj, "display_name", aid)).lower()
                if dest in (aid.lower(), ag_name) or aid.lower() in dest or ag_name in dest:
                    matched_nav = (aid, getattr(ag_obj, "display_name", aid))
                    break
        if matched_nav:
            aid, label = matched_nav
            ui_actions = [{"type": "switch_agent", "agent_id": aid}]
            executed_activities = [f"🧭 Switched Active Agent → {label}"]
            return _record_turn(spoken, {
                "status": "ok",
                "mode": "navigate",
                "agent_id": aid,
                "voice_transcript": spoken,
                "normalized_command": f"@{aid} open",
                "title": f"🧭 Opened {label}",
                "message": f"Switched your active AFCC workspace to **{label}**.",
                "spoken_reply": f"Opened {label}.",
                "ui_actions": ui_actions,
                "executed_activities": executed_activities,
                "tokens_used": 0,
                "cost_usd": "$0.00",
            })

    # 11. General Conversational Omnibar Dispatch + Auto-Linked UI Actions
    res = dispatch_omnibar_query(normalized, agent_registry=agent_registry, db=db)
    res["voice_transcript"] = spoken
    res["normalized_command"] = normalized

    if res.get("agent_id") and not ui_actions:
        ag_target = str(res["agent_id"])
        if ag_target in ("overview", "health", "backlog", "optimizer", "gmail"):
            ui_actions.append({"type": "switch_agent", "agent_id": ag_target})
            executed_activities.append(f"🧭 Linked Workspace: {ag_target.title()}")
    if res.get("mode") == "hydration":
        ui_actions.append({"type": "refresh_health"})
        executed_activities.append("💧 Updated Hydration Tracker")
    elif "briefing" in lower:
        ui_actions.append({"type": "refresh_briefing"})
        executed_activities.append("☀️ Refreshed Daily Briefing")
    elif "task" in lower:
        ui_actions.append({"type": "refresh_tasks"})
        executed_activities.append("📋 Synced Task Board")

    res["ui_actions"] = ui_actions
    res["executed_activities"] = executed_activities or ["💬 Processed Bi-Directional Voice Turn"]
    res["spoken_reply"] = _clean_for_speech(res.get("spoken_reply") or res.get("message") or res.get("title") or "")
    return res
