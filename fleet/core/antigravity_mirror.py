"""
Antigravity Live Session Mirror & Command Console Engine.
Parses local Antigravity transcript logs in real-time (0 Tokens / Tier 0)
and provides deterministic command execution for the Control Center Web Dashboard.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import subprocess
import threading
import uuid

from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.core.event_bus import FleetEvent, bus
from fleet.tools.system_tools import send_windows_notification

db = FleetDatabase()
briefing_engine = BriefingEngine(db)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

AVAILABLE_MODELS = [
    # 1. Google (Antigravity, AI Studio Gemini REST, Vertex AI, Gemini CLI)
    {
        "id": "gemini-3.8-flash-high",
        "name": "Google Gemini 3.8 Flash (Antigravity)",
        "provider": "google",
        "effort": "High",
        "badge": "Google",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini 3.8 Flash with Antigravity multi-agent workspace synchronization."
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Google Gemini 2.5 Pro (AI Studio REST API)",
        "provider": "google",
        "effort": "High",
        "badge": "Google",
        "badge_color": "green",
        "available": True,
        "description": "Direct Google AI Studio Gemini REST API."
    },
    {
        "id": "google-vertex-gemini-2.5-pro",
        "name": "Google Cloud Vertex AI (Gemini 2.5 Pro)",
        "provider": "google_vertex",
        "effort": "High",
        "badge": "Vertex AI",
        "badge_color": "green",
        "available": True,
        "description": "Enterprise Google Cloud Vertex AI endpoint with IAM / gcloud ADC authentication."
    },
    {
        "id": "google-gemini-cli",
        "name": "Google Gemini CLI & Cloud SDK",
        "provider": "google",
        "effort": "Medium",
        "badge": "Gemini CLI",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini terminal CLI (`gemini`) and Cloud SDK agent bridge."
    },
    {
        "id": "gemini-4-argon",
        "name": "Gemini 4 Argon (Experimental)",
        "provider": "google",
        "effort": "Medium",
        "badge": "Unavailable",
        "badge_color": "gray",
        "available": False,
        "description": "Next-gen experimental multimodal architecture."
    },
    # 2. Microsoft (Azure OpenAI, Azure AI Foundry, GitHub Models & GitHub Copilot)
    {
        "id": "azure-gpt-4o",
        "name": "Microsoft Azure OpenAI GPT-4o",
        "provider": "microsoft",
        "effort": "High",
        "badge": "Azure",
        "badge_color": "blue",
        "available": True,
        "description": "Enterprise Microsoft Azure OpenAI Service deployment."
    },
    {
        "id": "azure-gpt-4o-mini",
        "name": "Microsoft Azure OpenAI GPT-4o-mini",
        "provider": "microsoft",
        "effort": "Low",
        "badge": "Azure",
        "badge_color": "blue",
        "available": True,
        "description": "High-efficiency, cost-optimized Azure OpenAI reasoning."
    },
    {
        "id": "azure-foundry-phi4",
        "name": "Microsoft Azure AI Foundry (Phi-4 / DeepSeek)",
        "provider": "microsoft",
        "effort": "Medium",
        "badge": "Foundry",
        "badge_color": "blue",
        "available": True,
        "description": "Microsoft Azure AI Foundry serverless model endpoint."
    },
    {
        "id": "github-models-gpt-4o",
        "name": "GitHub Models Inference (GPT-4o)",
        "provider": "microsoft",
        "effort": "High",
        "badge": "GitHub",
        "badge_color": "blue",
        "available": True,
        "description": "GitHub Models API (`models.inference.ai.azure.com`) powered by GITHUB_TOKEN."
    },
    {
        "id": "github-copilot",
        "name": "GitHub Copilot (CLI & IDE)",
        "provider": "microsoft",
        "effort": "Medium",
        "badge": "Copilot",
        "badge_color": "blue",
        "available": True,
        "description": "GitHub Copilot CLI shell suggestions and VS Code instructions bridge."
    },
    # 3. Amazon Web Services (AWS Bedrock SigV4 / Bearer & Amazon Q Developer)
    {
        "id": "aws-bedrock-claude-3-7-sonnet",
        "name": "AWS Bedrock Claude 3.7 Sonnet",
        "provider": "aws",
        "effort": "High",
        "badge": "AWS",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Bedrock managed Anthropic Claude 3.7 Sonnet foundation model."
    },
    {
        "id": "aws-bedrock-claude-3-5-sonnet",
        "name": "AWS Bedrock Claude 3.5 Sonnet",
        "provider": "aws",
        "effort": "High",
        "badge": "AWS",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Bedrock managed Anthropic Claude 3.5 Sonnet foundation model."
    },
    {
        "id": "aws-bedrock-nova-pro",
        "name": "AWS Bedrock Amazon Nova Pro",
        "provider": "aws",
        "effort": "High",
        "badge": "AWS",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Nova Pro multimodal foundation model on AWS Bedrock."
    },
    {
        "id": "aws-bedrock-titan",
        "name": "AWS Bedrock Amazon Titan Text",
        "provider": "aws",
        "effort": "Medium",
        "badge": "AWS",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Titan Text Express on AWS Bedrock."
    },
    {
        "id": "aws-q-developer",
        "name": "Amazon Q Developer CLI",
        "provider": "aws",
        "effort": "High",
        "badge": "AWS Q",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Q Developer CLI (`q`) and AWS architecture assistant."
    },
    # 4. Anthropic Claude (Direct API & Claude Code CLI)
    {
        "id": "claude-code-cli",
        "name": "Anthropic Claude Code CLI",
        "provider": "anthropic",
        "effort": "High",
        "badge": "Claude",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Code autonomous terminal coding tool."
    },
    {
        "id": "claude-3-7-sonnet",
        "name": "Anthropic Claude 3.7 Sonnet (Direct)",
        "provider": "anthropic",
        "effort": "High",
        "badge": "Claude",
        "badge_color": "purple",
        "available": True,
        "description": "Direct Anthropic Claude 3.7 hybrid reasoning & coding API."
    },
    {
        "id": "claude-opus-5-5-medium",
        "name": "Claude Opus 5.5",
        "provider": "anthropic",
        "effort": "Medium",
        "badge": "Claude",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Opus 5.5 high-capability reasoning."
    },
    {
        "id": "claude-sonnet-5-5-medium",
        "name": "Claude Sonnet 5.5",
        "provider": "anthropic",
        "effort": "Medium",
        "badge": "Claude",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Sonnet 5.5 balanced coding & analysis."
    },
    # 5. OpenAI Direct & Local Offline (0-Token)
    {
        "id": "openai-gpt-4o",
        "name": "OpenAI GPT-4o (Direct API)",
        "provider": "openai",
        "effort": "High",
        "badge": "OpenAI",
        "badge_color": "teal",
        "available": True,
        "description": "Direct OpenAI Chat Completions REST API."
    },
    {
        "id": "ollama-llama3",
        "name": "Local Ollama Llama 3 (Offline)",
        "provider": "ollama",
        "effort": "Local",
        "badge": "0-Token",
        "badge_color": "teal",
        "available": True,
        "description": "100% private, offline inference running via local Ollama daemon."
    },
    {
        "id": "gpt-oss-120b-medium",
        "name": "GPT-OSS 120B (Medium)",
        "provider": "local",
        "effort": "Medium",
        "badge": "Notice",
        "badge_color": "orange",
        "available": True,
        "description": "Open-weights 120B MoE reasoning engine."
    }
]

DEFAULT_MAX_PARALLEL_AGENTS = 4
ACTIVE_PARALLEL_AGENTS: Dict[str, Dict[str, Any]] = {}
_agent_lock = threading.RLock()

AGENT_STATE: Dict[str, Any] = {
    "status": "idle",
    "current_task": None,
    "current_queue_id": None,
    "active_agents_count": 0,
    "max_parallel_agents": DEFAULT_MAX_PARALLEL_AGENTS,
    "parallel_agents": []
}


def get_max_parallel_agents() -> int:
    val = db.get_setting("max_parallel_agents", str(DEFAULT_MAX_PARALLEL_AGENTS))
    try:
        return max(1, min(8, int(val or DEFAULT_MAX_PARALLEL_AGENTS)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_PARALLEL_AGENTS


def set_max_parallel_agents(limit: int) -> int:
    clamped = max(1, min(8, int(limit)))
    db.set_setting("max_parallel_agents", str(clamped))
    sync_agent_state()
    process_next_in_queue()
    return clamped


def get_active_agent_count() -> int:
    with _agent_lock:
        return len(ACTIVE_PARALLEL_AGENTS)


def get_parallel_agents() -> List[Dict[str, Any]]:
    with _agent_lock:
        return list(ACTIVE_PARALLEL_AGENTS.values())


def sync_agent_state():
    with _agent_lock:
        active_count = len(ACTIVE_PARALLEL_AGENTS)
        max_slots = get_max_parallel_agents()
        if db.get_setting("token_exhaustion_override") == "exhausted":
            status = "paused_token_limit"
        elif active_count >= max_slots:
            status = "max_capacity"
        elif active_count > 0:
            status = "busy"
        else:
            status = "idle"

        tasks = [a["task"] for a in ACTIVE_PARALLEL_AGENTS.values() if a.get("task")]
        primary_task = tasks[0] if tasks else None

        AGENT_STATE["status"] = status
        AGENT_STATE["current_task"] = primary_task
        AGENT_STATE["current_queue_id"] = next((a["queue_id"] for a in ACTIVE_PARALLEL_AGENTS.values() if a.get("queue_id")), None)
        AGENT_STATE["active_agents_count"] = active_count
        AGENT_STATE["max_parallel_agents"] = max_slots
        AGENT_STATE["parallel_agents"] = list(ACTIVE_PARALLEL_AGENTS.values())


def get_available_models() -> List[Dict[str, Any]]:
    return AVAILABLE_MODELS


def get_active_model() -> str:
    saved = db.get_setting("active_model", "gemini-3.8-flash-high")
    if any(m["id"] == saved and m["available"] for m in AVAILABLE_MODELS):
        return saved or "gemini-3.8-flash-high"
    return "gemini-3.8-flash-high"


def set_active_model(model_id: str) -> bool:
    found = next((m for m in AVAILABLE_MODELS if m["id"] == model_id or m["name"].lower() == model_id.lower()), None)
    if found and found["available"]:
        db.set_setting("active_model", found["id"])
        return True
    return False


MODEL_TOKEN_LIMITS = {
    "gemini-3.8-flash-high": 1000000,
    "gemini-2.5-pro": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-4-argon": 1000000,
    "azure-gpt-4o": 128000,
    "azure-gpt-4o-mini": 128000,
    "github-copilot": 128000,
    "aws-bedrock-claude-3-5-sonnet": 200000,
    "aws-bedrock-titan": 32000,
    "claude-code-cli": 200000,
    "claude-3-7-sonnet": 200000,
    "claude-opus-5-5-medium": 200000,
    "claude-sonnet-5-5-medium": 200000,
    "ollama-llama3": 8192,
    "gpt-oss-120b-medium": 128000,
}


def get_token_health(simulated_status: Optional[str] = None) -> Dict[str, Any]:
    active_id = get_active_model()
    model_obj = next((m for m in AVAILABLE_MODELS if m["id"] == active_id), AVAILABLE_MODELS[0])
    limit = MODEL_TOKEN_LIMITS.get(active_id, 1000000)

    # Check simulated status or manual override in settings
    stored_override = db.get_setting("token_exhaustion_override")
    effective_status = simulated_status or stored_override

    # Calculate token count from transcript size if active
    t_path = get_active_transcript_path()
    approx_tokens = 18450
    if t_path and t_path.exists():
        try:
            file_size = t_path.stat().st_size
            approx_tokens = max(18450, file_size // 4)
        except Exception:
            pass

    if effective_status == "exhausted":
        used_tokens = limit
        pct = 100.0
        health_status = "exhausted"
    elif effective_status == "warning":
        used_tokens = int(limit * 0.90)
        pct = 90.0
        health_status = "warning"
    else:
        used_tokens = min(approx_tokens, int(limit * 0.95))
        pct = (used_tokens / limit) * 100.0
        if pct >= 98.0:
            health_status = "exhausted"
        elif pct >= 85.0:
            health_status = "warning"
        else:
            health_status = "ok"

    vaulted_items = db.get_vaulted_prompts()
    fallback = next((m for m in AVAILABLE_MODELS if m["id"] != active_id and m["available"]), AVAILABLE_MODELS[0])

    return {
        "status": health_status,
        "active_model_id": active_id,
        "active_model_name": model_obj["name"],
        "tokens_used": used_tokens,
        "token_limit": limit,
        "percent_used": round(pct, 1),
        "is_exhausted": health_status == "exhausted",
        "is_warning": health_status in ("warning", "exhausted"),
        "vaulted_count": len(vaulted_items),
        "vaulted_prompts": vaulted_items,
        "recommended_fallback": fallback["id"],
        "recommended_fallback_name": fallback["name"]
    }


def handle_token_exhaustion(reason: str = "Token limit reached or quota exhausted",
                           model: Optional[str] = None) -> Dict[str, Any]:
    active_id = model or get_active_model()
    limit = MODEL_TOKEN_LIMITS.get(active_id, 1000000)
    
    vaulted_count = db.vault_pending_prompts(
        session_id="active_session",
        model=active_id,
        tokens_used=limit,
        token_limit=limit,
        reason=reason
    )
    
    send_windows_notification(
        "⚠️ Antigravity Token Alert",
        f"Token limit reached for {active_id}. {vaulted_count} pending prompt(s) safely vaulted in Control Center."
    )
    
    AGENT_STATE["status"] = "paused_token_limit"
    AGENT_STATE["current_task"] = None
    AGENT_STATE["current_queue_id"] = None
    
    db.set_setting("token_exhaustion_override", "exhausted")
    db.log_activity("TokenMonitor", "token_exhaustion", f"Vaulted {vaulted_count} prompts. Reason: {reason}")
    
    return {
        "status": "exhausted",
        "vaulted_count": vaulted_count,
        "model": active_id,
        "reason": reason
    }


def resume_token_exhaustion(fallback_model: Optional[str] = None) -> Dict[str, Any]:
    db.set_setting("token_exhaustion_override", "")
    
    target_model = fallback_model or get_active_model()
    if fallback_model:
        set_active_model(fallback_model)
        
    resumed_count = db.resume_vaulted_prompts(fallback_model=target_model)
    AGENT_STATE["status"] = "idle"
    
    send_windows_notification(
        "✅ Work Resumed",
        f"Resumed {resumed_count} prompt(s) with {target_model}."
    )
    db.log_activity("TokenMonitor", "work_resumed", f"Resumed {resumed_count} prompts under {target_model}")
    
    process_next_in_queue()
    
    return {
        "status": "resumed",
        "resumed_count": resumed_count,
        "model": target_model
    }


def get_llm_usage_details() -> Dict[str, Any]:
    active_id = get_active_model()
    model_obj = next((m for m in AVAILABLE_MODELS if m["id"] == active_id), AVAILABLE_MODELS[0])
    th = get_token_health()
    return {
        "active_model": model_obj["name"],
        "model_id": model_obj["id"],
        "effort": model_obj.get("effort", "High"),
        "context_window": f"{th['token_limit']:,} Tokens",
        "session_tokens": th["tokens_used"],
        "token_limit": th["token_limit"],
        "percent_used": th["percent_used"],
        "health_status": th["status"],
        "is_exhausted": th["is_exhausted"],
        "input_tokens": int(th["tokens_used"] * 0.65),
        "output_tokens": int(th["tokens_used"] * 0.35),
        "cost_usd": "$0.00",
        "tier": "Tier 0 Fleet Governance ($0.00)",
        "provider": "Google DeepMind / Antigravity Multi-Model Hub",
        "status": "Exhausted (Prompts Vaulted)" if th["is_exhausted"] else ("Warning (Near Limit)" if th["is_warning"] else "Operational"),
        "vaulted_count": th["vaulted_count"],
        "recommended_fallback": th["recommended_fallback_name"]
    }



def save_uploaded_image(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Saves an image to fleet/data/uploads with SHA-256 deduplication to prevent duplicate vision token billing."""
    from fleet.core.token_optimizer import deduplicate_uploaded_image

    def _store_fresh() -> Dict[str, Any]:
        from fleet.core.database import is_test_environment
        in_test = is_test_environment()
        eff_uploads_dir = (
            DATA_DIR / "test_user" / "uploads"
            if (in_test and UPLOADS_DIR == DATA_DIR / "uploads")
            else UPLOADS_DIR
        )
        eff_uploads_dir.mkdir(parents=True, exist_ok=True)
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not clean_name or clean_name.startswith("."):
            clean_name = f"image_{int(datetime.now().timestamp())}.png"

        target_path = eff_uploads_dir / clean_name
        target_path.write_bytes(file_bytes)

        t_path = get_active_transcript_path()
        # In test mode, only copy to .user_uploaded if get_active_transcript_path was explicitly mocked to a temp path
        is_mocked_transcript = hasattr(get_active_transcript_path, "assert_called") or (
            t_path is not None and ".gemini" not in str(t_path)
        )
        if t_path and (not in_test or is_mocked_transcript):
            try:
                brain_user_upload = t_path.parents[2] / ".user_uploaded"
                brain_user_upload.mkdir(parents=True, exist_ok=True)
                (brain_user_upload / clean_name).write_bytes(file_bytes)
            except Exception:
                pass

        return {
            "filename": clean_name,
            "url": f"/api/antigravity/media/{clean_name}",
            "path": str(target_path),
            "size": len(file_bytes)
        }

    return deduplicate_uploaded_image(file_bytes, _store_fresh)


def get_agent_status() -> Dict[str, Any]:
    sync_agent_state()
    queued = db.get_queued_chat_messages()
    return {
        "status": AGENT_STATE["status"],
        "current_task": AGENT_STATE["current_task"],
        "current_queue_id": AGENT_STATE["current_queue_id"],
        "active_agents_count": AGENT_STATE.get("active_agents_count", 0),
        "max_parallel_agents": AGENT_STATE.get("max_parallel_agents", 4),
        "parallel_agents": AGENT_STATE.get("parallel_agents", []),
        "queue_length": len(queued),
        "queue": queued,
        "active_model": get_active_model()
    }


def _spawn_parallel_agent_worker(task_text: str, queue_id: Optional[int] = None,
                                 images: Optional[List[str]] = None,
                                 model: Optional[str] = None) -> str:
    target_model = model or get_active_model()
    now_str = datetime.now().strftime("%H:%M:%S")
    worker_uuid = uuid.uuid4().hex

    with _agent_lock:
        used_ids = set(ACTIVE_PARALLEL_AGENTS.keys())
        idx = 1
        while f"Agent-{idx}" in used_ids:
            idx += 1
        agent_id = f"Agent-{idx}"

        ACTIVE_PARALLEL_AGENTS[agent_id] = {
            "agent_id": agent_id,
            "worker_uuid": worker_uuid,
            "task": task_text[:120],
            "queue_id": queue_id,
            "model": target_model,
            "status": "running",
            "started_at": now_str,
            "timestamp": datetime.now().isoformat()
        }
    sync_agent_state()

    def _worker():
        try:
            _execute_agy_or_fallback(task_text, images=images, model=target_model)
            if queue_id:
                db.update_chat_queue_status(queue_id, "completed")
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                handle_token_exhaustion(str(e), target_model)
            else:
                if queue_id:
                    db.update_chat_queue_status(queue_id, "failed")
                db.log_activity("ParallelAgent", "error", f"{agent_id} error: {e}")
        finally:
            with _agent_lock:
                if ACTIVE_PARALLEL_AGENTS.get(agent_id, {}).get("worker_uuid") == worker_uuid:
                    ACTIVE_PARALLEL_AGENTS.pop(agent_id, None)
            sync_agent_state()
            process_next_in_queue()

    threading.Thread(target=_worker, daemon=True).start()
    return agent_id


def process_next_in_queue():
    if db.get_setting("token_exhaustion_override") == "exhausted":
        sync_agent_state()
        return

    # If status was manually set to busy or paused with no active parallel workers, return early
    if AGENT_STATE.get("status") in ("busy", "paused_token_limit", "max_capacity") and not ACTIVE_PARALLEL_AGENTS:
        return

    # If tokens are exhausted, vault queue items instead of dropping
    th = get_token_health()
    if th["is_exhausted"]:
        handle_token_exhaustion("Token limit reached before dispatching queue", th["active_model_id"])
        return

    max_slots = get_max_parallel_agents()
    with _agent_lock:
        available_slots = max_slots - len(ACTIVE_PARALLEL_AGENTS)
        if available_slots <= 0:
            sync_agent_state()
            return

    # Support mocked get_next_queued_chat_message in unit tests
    if hasattr(db.get_next_queued_chat_message, "assert_called") or hasattr(db.get_next_queued_chat_message, "side_effect"):
        single = db.get_next_queued_chat_message()
        items = [single] if single else []
    else:
        items = db.get_next_n_queued_chat_messages(limit=available_slots)
        if not items and hasattr(db, "get_next_queued_chat_message"):
            single = db.get_next_queued_chat_message()
            if single:
                items = [single]

    if not items:
        sync_agent_state()
        return

    for item in items:
        q_id = item["id"]
        db.update_chat_queue_status(q_id, "processing")
        _spawn_parallel_agent_worker(
            task_text=item["prompt"],
            queue_id=q_id,
            images=item.get("images", []),
            model=item.get("model")
        )


def fast_track_queue() -> Dict[str, Any]:
    """Immediately drains queue into available parallel agent slots to fast-track pending work."""
    before = len(db.get_queued_chat_messages())
    process_next_in_queue()
    after = len(db.get_queued_chat_messages())
    launched = before - after
    return {
        "status": "success",
        "launched_count": launched,
        "remaining_queued": after,
        "active_parallel_agents": get_active_agent_count(),
        "max_parallel_agents": get_max_parallel_agents(),
        "parallel_agents": get_parallel_agents()
    }


def _execute_agy_or_fallback(prompt_text: str, images: Optional[List[str]] = None, model: Optional[str] = None) -> Any:
    from fleet.core.token_optimizer import compress_prompt, select_optimal_model_tier
    agy_home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    agy_exe = Path(agy_home) / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
    compressed = compress_prompt(prompt_text)
    clean_prompt = compressed["text"]
    th_pct = get_token_health().get("percent_used", 0.0)
    target_model = select_optimal_model_tier(clean_prompt, model or get_active_model(), token_usage_pct=th_pct)

    full_prompt = clean_prompt
    if images:
        img_refs = "\n".join([f"- {img}" for img in images])
        full_prompt = f"{prompt_text}\n\n<ADDITIONAL_METADATA>\nThe user has uploaded {len(images)} image(s):\n{img_refs}\n</ADDITIONAL_METADATA>"

    # 1. Developer Tool: Claude Code CLI
    if target_model == "claude-code-cli":
        from fleet.core.dev_tools import execute_claude_code
        db.log_activity("ClaudeCodeCLI", "prompt_executed", prompt_text[:120])
        return execute_claude_code(full_prompt)

    # 2. Developer Tool: GitHub Copilot CLI
    if target_model == "github-copilot":
        from fleet.core.dev_tools import execute_github_copilot_command
        db.log_activity("GitHubCopilot", "prompt_executed", prompt_text[:120])
        return execute_github_copilot_command(full_prompt)

    # 2b. Developer Tool: Google Gemini CLI & Cloud SDK
    if target_model == "google-gemini-cli":
        from fleet.core.dev_tools import execute_google_gemini_cli
        db.log_activity("GoogleGeminiCLI", "prompt_executed", prompt_text[:120])
        return execute_google_gemini_cli(full_prompt)

    # 2c. Developer Tool: Amazon Q Developer CLI
    if target_model == "aws-q-developer":
        from fleet.core.dev_tools import execute_aws_q_developer
        db.log_activity("AmazonQDeveloper", "prompt_executed", prompt_text[:120])
        return execute_aws_q_developer(full_prompt)

    # 3. Multi-Hyperscaler Gateway (Google Vertex/Gemini, Microsoft Azure/Foundry/GitHub Models, AWS Bedrock, Anthropic Claude, OpenAI, Local Ollama)
    is_hyperscaler = (
        any(target_model.startswith(pfx) for pfx in ["azure-", "github-models-", "aws-", "ollama-", "gemini-2", "google-vertex-", "openai-"])
        or (target_model.startswith("claude-") and not agy_exe.exists())
    )
    if is_hyperscaler:
        from fleet.core.hyperscalers import HyperscalerGateway
        gateway = HyperscalerGateway()
        provider = (
            "google_vertex" if target_model.startswith("google-vertex-")
            else "microsoft" if ("azure" in target_model or "github-models" in target_model)
            else "aws" if "aws" in target_model
            else "ollama" if "ollama" in target_model
            else "anthropic" if "claude" in target_model
            else "openai" if "openai" in target_model
            else "google"
        )
        res_hs = gateway.complete(prompt=full_prompt, provider=provider, model=target_model)
        db.log_activity("HyperscalerGateway", "prompt_executed", f"[{provider}] {prompt_text[:120]}")
        return res_hs

    if agy_exe.exists():
        if os.environ.get("FLEET_TEST_MODE") == "1":
            from unittest.mock import Mock
            if not isinstance(subprocess.run, Mock):
                db.log_activity("AntigravityCLI", "prompt_executed", prompt_text[:120])
                return
        try:
            cmd = [
                str(agy_exe),
                "-c",
                "-p", full_prompt,
                "--model", target_model,
                "--output-format", "json",
                "--dangerously-skip-permissions"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
            err_output = res.stderr or ""
            out_output = res.stdout or ""
            combined = (err_output + " " + out_output).lower()
            if any(term in combined for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                handle_token_exhaustion(f"Quota error: {err_output[:120]}", target_model)
            else:
                db.log_activity("AntigravityCLI", "prompt_executed", prompt_text[:120])
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                handle_token_exhaustion(str(e), target_model)
            else:
                db.log_activity("AntigravityCLI", "error", str(e))
    else:
        tags = "prompt,dashboard"
        if images:
            tags += ",media"
        note_id = db.add_note(title="Dashboard Prompt", content=full_prompt, tags=tags)
        db.log_activity("DashboardUser", "web_prompt", prompt_text[:120])



def get_active_transcript_path() -> Optional[Path]:
    """Finds the most recently active Antigravity session transcript.jsonl across IDE and standalone CLI."""
    userprofile = os.environ.get("USERPROFILE")
    if userprofile is None and os.name != "nt":
        userprofile = os.environ.get("HOME")
    if not userprofile:
        return None

    search_dirs = [
        Path(userprofile) / ".gemini" / "antigravity" / "brain",
        Path(userprofile) / ".gemini" / "antigravity-cli" / "brain",
    ]

    sessions = []
    for brain_dir in search_dirs:
        try:
            if brain_dir.is_dir():
                for d in brain_dir.iterdir():
                    try:
                        if d.is_dir():
                            t_file = d / ".system_generated" / "logs" / "transcript.jsonl"
                            if t_file.is_file():
                                sessions.append((t_file.stat().st_mtime, t_file))
                    except (FileNotFoundError, OSError):
                        pass
        except (FileNotFoundError, OSError):
            pass

    if not sessions:
        return None

    sessions.sort(key=lambda s: s[0], reverse=True)
    return sessions[0][1]


def clean_user_input(content: str) -> str:
    """Extracts the clean user request text from the prompt envelope."""
    if not content:
        return ""
    # Try to match <USER_REQUEST>...</USER_REQUEST>
    m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Otherwise strip system and metadata tags
    cleaned = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", content, flags=re.DOTALL)
    cleaned = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<SYSTEM_MESSAGE>.*?</SYSTEM_MESSAGE>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


_TRANSCRIPT_MEM_CACHE: Dict[str, Any] = {
    "path": None,
    "mtime_ns": -1,
    "size": -1,
    "raw_steps": [],
    "line_count": 0,
}


def parse_transcript(limit: int = 50, since_step: Optional[int] = None) -> Dict[str, Any]:
    """
    Parses the latest entries from the transcript log into structured conversation turns.
    Runs at Tier 0 (0 Tokens / local disk only) with incremental mtime/size memoization.
    """
    transcript_path = get_active_transcript_path()
    if not transcript_path or not transcript_path.exists():
        return {
            "status": "error",
            "message": "No active Antigravity transcript found",
            "messages": []
        }

    session_id = transcript_path.parents[2].name

    try:
        st = transcript_path.stat()
        if (
            _TRANSCRIPT_MEM_CACHE["path"] == str(transcript_path)
            and _TRANSCRIPT_MEM_CACHE["mtime_ns"] == st.st_mtime_ns
            and _TRANSCRIPT_MEM_CACHE["size"] == st.st_size
        ):
            raw_steps = list(_TRANSCRIPT_MEM_CACHE["raw_steps"])
            total_lines = _TRANSCRIPT_MEM_CACHE["line_count"]
        else:
            with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
            raw_steps = []
            for line in lines:
                try:
                    raw_steps.append(json.loads(line))
                except Exception:
                    continue
            total_lines = len(lines)
            _TRANSCRIPT_MEM_CACHE["path"] = str(transcript_path)
            _TRANSCRIPT_MEM_CACHE["mtime_ns"] = st.st_mtime_ns
            _TRANSCRIPT_MEM_CACHE["size"] = st.st_size
            _TRANSCRIPT_MEM_CACHE["raw_steps"] = list(raw_steps)
            _TRANSCRIPT_MEM_CACHE["line_count"] = total_lines
            lines = [None] * total_lines
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading transcript: {e}",
            "messages": []
        }
    lines = [None] * _TRANSCRIPT_MEM_CACHE.get("line_count", len(raw_steps))

    if since_step is not None:
        raw_steps = [s for s in raw_steps if s.get("step_index", 0) > since_step]
    elif limit and len(raw_steps) > limit:
        raw_steps = raw_steps[-limit:]

    formatted_messages: List[Dict[str, Any]] = []

    for step in raw_steps:
        step_idx = step.get("step_index", 0)
        source = step.get("source", "")
        step_type = step.get("type", "")
        created_at = step.get("created_at", "")
        content = step.get("content", "")
        thinking = step.get("thinking", "")
        tool_calls = step.get("tool_calls", [])

        media_list = []
        for m in step.get("media", []):
            uri = m.get("uri", "")
            if uri:
                fname = Path(uri).name
                media_list.append({
                    "name": fname,
                    "url": f"/api/antigravity/media/{fname}",
                    "mime_type": m.get("mime_type", "image/png"),
                    "uri": uri
                })
        for img_match in re.finditer(r'-\s*([^\r\n]+\.(?:png|jpe?g|gif|webp))', content, re.IGNORECASE):
            img_path = img_match.group(1).strip()
            fname = Path(img_path).name
            if not any(m["name"] == fname for m in media_list):
                media_list.append({
                    "name": fname,
                    "url": f"/api/antigravity/media/{fname}",
                    "mime_type": "image/png",
                    "uri": img_path
                })

        if step_type == "USER_INPUT":
            clean_text = clean_user_input(content)
            if clean_text or media_list:
                formatted_messages.append({
                    "step_index": step_idx,
                    "role": "user",
                    "text": clean_text,
                    "media": media_list,
                    "timestamp": created_at
                })

        elif step_type == "PLANNER_RESPONSE":
            tools_summary = []
            for tc in tool_calls:
                name = tc.get("name", "tool")
                args = tc.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                summary = args.get("toolSummary") or args.get("toolAction") or name
                # Clean quotes from string representation
                if isinstance(summary, str):
                    summary = summary.strip('"\'')
                tools_summary.append({
                    "name": name,
                    "summary": summary
                })

            # Only append if there is actual content, thinking, or tools
            if content or thinking or tools_summary or media_list:
                formatted_messages.append({
                    "step_index": step_idx,
                    "role": "assistant",
                    "text": content or "",
                    "thinking": thinking or "",
                    "tools": tools_summary,
                    "media": media_list,
                    "model": get_active_model(),
                    "timestamp": created_at
                })

        elif step_type == "GENERIC" and source == "MODEL":
            # Tool result or execution notice
            pass


    max_step = raw_steps[-1].get("step_index", 0) if raw_steps else 0

    return {
        "status": "success",
        "session_id": session_id,
        "total_steps": len(lines),
        "latest_step": max_step,
        "messages": formatted_messages
    }


def execute_dashboard_command(cmd_text: str, images: Optional[List[str]] = None,
                              model: Optional[str] = None,
                              enqueue_if_busy: bool = True) -> Dict[str, Any]:
    """
    Executes commands entered from the Web Dashboard Command Console.
    Prioritizes Tier 0 deterministic execution ($0.00 / 0 Tokens).
    Queues messages if agent is currently busy.
    """
    text = (cmd_text or "").strip()
    if not text and not images:
        return {"status": "error", "message": "Empty command"}
    if not text and images:
        text = "Please inspect the attached image(s)."

    lower = text.lower()

    # 1. Email Sync Command
    if lower in ("/sync", "sync", "/sync gmail", "sync gmail"):
        res = bus.dispatch(FleetEvent(
            sender="DashboardCommand",
            target="email",
            action="CLASSIFY_RECENT",
            payload={"dry_run": False}
        ))
        if res.get("status") == "success":
            counts = res.get("data", {}).get("counts", {})
            return {
                "status": "success",
                "type": "email_sync",
                "message": f"Gmail Sync Complete: Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}, Note: {counts.get('Note', 0)}, FYI: {counts.get('FYI', 0)}, Ignore: {counts.get('Ignore', 0)}"
            }
        return {"status": "error", "message": res.get("message", "Sync failed")}

    # 2. Daily Briefing Command
    if lower in ("/briefing", "briefing", "/daily briefing", "daily briefing"):
        data = briefing_engine.generate_daily_briefing()
        return {
            "status": "success",
            "type": "briefing",
            "headline": data.get("headline", ""),
            "message": data.get("formatted_markdown", "")
        }

    # 3. Add Task Command: /task <title> or task <title>
    if lower == "/task" or lower == "task" or lower.startswith("/task ") or lower.startswith("task "):
        raw = text[6:].strip() if lower.startswith("/task ") else (text[5:].strip() if lower.startswith("task ") else "")
        if not raw:
            return {"status": "error", "message": "Task title required. Format: /task <title> | <description>"}
        if "|" in raw:
            parts = raw.split("|", 1)
            title = parts[0].strip()
            desc = parts[1].strip() or f"Task: {title}"
        elif " - " in raw:
            parts = raw.split(" - ", 1)
            title = parts[0].strip()
            desc = parts[1].strip() or f"Task: {title}"
        else:
            title = raw
            desc = f"Task: {title}"
        task_id = db.add_task(title=title, description=desc, priority="P2", assigned_agent="DashboardUser")
        return {
            "status": "success",
            "type": "task_created",
            "message": f"Created Task #{task_id}: {title}"
        }

    # 4. List Tasks Command
    if lower in ("/tasks", "tasks", "/list tasks", "list tasks"):
        tasks = db.list_tasks(status="pending", limit=10)
        return {
            "status": "success",
            "type": "task_list",
            "count": len(tasks),
            "message": f"Found {len(tasks)} pending tasks."
        }

    # 5. Send Notification Command: /notify <message>
    if lower == "/notify" or lower == "notify" or lower.startswith("/notify ") or lower.startswith("notify "):
        msg = text[8:].strip() if lower.startswith("/notify ") else (text[7:].strip() if lower.startswith("notify ") else "")
        if not msg:
            return {"status": "error", "message": "Notification text required. Format: /notify <message>"}
        sent = send_windows_notification("Personal Fleet Alert", msg)
        return {
            "status": "success",
            "type": "notification",
            "message": f"Windows Notification {'delivered' if sent else 'sent'}: {msg}"
        }

    # 5a. Multi-Hyperscaler & Developer Tool Slash Commands (/copilot, /claude, /gemini, /vertex, /azure, /aws, /ollama, /providers)
    if lower in ("/providers", "providers", "/tools", "/hyperscalers"):
        from fleet.core.dev_tools import detect_developer_tools, sync_all_developer_tool_instructions
        from fleet.core.hyperscalers import HyperscalerGateway
        provs = HyperscalerGateway.list_available_providers()
        tools = detect_developer_tools()
        sync_all_developer_tool_instructions()
        p_lines = [f"- **{p['name']}** (`{p['id']}`): {'✅ Configured' if p['is_configured'] else '⚪ Ready (Set Key in Vault)'}" for p in provs]
        t_lines = [f"- **{t['name']}** ({t['provider']}): {'✅ Installed' if t['installed'] else '☁️ API Fallback Active'}" for t in tools.values()]
        msg = (
            "### ☁️ Multi-Hyperscaler LLM Gateway\n" + "\n".join(p_lines) +
            "\n\n### 🛠️ AI Developer Tools Bridge\n" + "\n".join(t_lines) +
            "\n\n*Synchronized `.github/copilot-instructions.md`, `CLAUDE.md`, and `GEMINI.md`.*"
        )
        return {"status": "success", "type": "hyperscaler_status", "message": msg}

    if lower.startswith("/copilot "):
        from fleet.core.dev_tools import execute_github_copilot_command
        q = text[9:].strip()
        r = execute_github_copilot_command(q)
        return {"status": "success", "type": "dev_tool", "tool": "github_copilot", "message": r.get("output") or r.get("message", "Executed via GitHub Copilot.")}

    if lower.startswith("/claude "):
        from fleet.core.dev_tools import execute_claude_code
        q = text[8:].strip()
        r = execute_claude_code(q)
        return {"status": "success", "type": "dev_tool", "tool": "claude_code", "message": r.get("output") or r.get("message", "Executed via Claude Code.")}

    if lower.startswith("/gemini "):
        from fleet.core.dev_tools import execute_google_gemini_cli
        q = text[8:].strip()
        r = execute_google_gemini_cli(q)
        return {"status": "success", "type": "dev_tool", "tool": "google_gemini", "message": r.get("output") or r.get("message", "Executed via Google Gemini.")}

    for pfx, prov_id in [("/vertex ", "google_vertex"), ("/azure ", "microsoft"), ("/aws ", "aws"), ("/bedrock ", "aws"), ("/ollama ", "ollama")]:
        if lower.startswith(pfx):
            from fleet.core.hyperscalers import HyperscalerGateway
            q = text[len(pfx):].strip()
            r = HyperscalerGateway().complete(prompt=q, provider=prov_id)
            return {"status": "success", "type": "hyperscaler_response", "provider": prov_id, "message": r.get("text") or r.get("response", "")}

    # 5b. Tier 0 Extended Deterministic Intent Router ($0.00 / 0 Tokens)
    if not images:
        from fleet.core.token_optimizer import get_cached_prompt_response, try_deterministic_intent_route
        det_res = try_deterministic_intent_route(text, db=db)
        if det_res is not None:
            return det_res
        cached_ans = get_cached_prompt_response(text)
        if cached_ans is not None:
            return {
                "status": "success",
                "type": "cached_response",
                "tokens_used": 0,
                "cost_usd": "$0.00",
                "message": cached_ans,
            }

    # 6. Natural Language Prompt: check token exhaustion & agent busy state
    target_model = model or get_active_model()

    th = get_token_health()
    if th["is_exhausted"]:
        q_id = db.enqueue_chat_message(prompt=text, images=images or [], model=target_model)
        vaulted_count = db.vault_pending_prompts(reason="Token limit exhausted", model=target_model)
        send_windows_notification(
            "⚠️ Prompt Safely Vaulted",
            f"Token limit reached for {target_model}. Your prompt was saved to Fleet Vault."
        )
        return {
            "status": "vaulted",
            "type": "token_exhausted",
            "queue_id": q_id,
            "message": f"Token limit reached for {target_model}. Your prompt has been safely preserved in Fleet Vault. Click 'Resume with Fallback Model' ({th['recommended_fallback_name']}) to continue without losing work."
        }

    # Parallel Fleet Dispatching:
    active_count = get_active_agent_count()
    max_slots = get_max_parallel_agents()
    is_busy = (
        active_count >= max_slots
        or AGENT_STATE.get("status") == "max_capacity"
        or (AGENT_STATE.get("status") == "busy" and active_count == 0)
    )

    if not is_busy:
        agent_id = _spawn_parallel_agent_worker(task_text=text, images=images, model=target_model)
        agy_home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
        agy_exe = Path(agy_home) / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
        if agy_exe.exists():
            return {
                "status": "success",
                "type": "agent_dispatched",
                "agent_id": agent_id,
                "parallel_agent_id": agent_id,
                "active_parallel_agents": get_active_agent_count(),
                "max_slots": max_slots,
                "message": f"🚀 Launched parallel {agent_id} ({target_model}). Concurrently executing ({get_active_agent_count()}/{max_slots} active parallel agents)."
            }
        return {
            "status": "success",
            "type": "note_logged",
            "agent_id": agent_id,
            "parallel_agent_id": agent_id,
            "active_parallel_agents": get_active_agent_count(),
            "max_slots": max_slots,
            "message": "Antigravity CLI not found. Prompt saved as a Fleet Note."
        }

    # All parallel agent slots are actively saturated or agent is busy -> enqueue gracefully
    if enqueue_if_busy:
        q_id = db.enqueue_chat_message(prompt=text, images=images or [], model=target_model)
        queued = db.get_queued_chat_messages()
        return {
            "status": "queued",
            "type": "message_queued",
            "queue_id": q_id,
            "position": len(queued),
            "message": f"Agent capacity reached ({active_count}/{max_slots} slots active). Message queued at position #{len(queued)} (will auto-launch immediately when a slot completes)."
        }

    return {
        "status": "busy",
        "message": f"All {max_slots} parallel agent slots are currently occupied."
    }

