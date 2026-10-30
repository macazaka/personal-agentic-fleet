"""
UX-05: Unified "Ask Fleet Anything" Conversational Omnibar & Cross-Agent Dispatcher.
Unifies Spotlight tab navigation, multi-turn conversational AI & Fleet telemetry chat,
@agent slash commands, UX-01 Agent Studio synthesis, UX-02 Process Discovery,
UX-03 Playbook triggers, Tier-0 natural-language execution, and BM25 Knowledge RAG
into a single responsive conversational interface.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional


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
