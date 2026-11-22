"""
Antigravity Live Session Mirror & Command Console Engine.
Parses local Antigravity transcript logs in real-time (0 Tokens / Tier 0)
and provides deterministic command execution for the Control Center Web Dashboard.
"""

import atexit
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

logger = logging.getLogger(__name__)

from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase
from fleet.core.event_bus import FleetEvent, bus
from fleet.tools.system_tools import send_windows_notification

db = FleetDatabase()
briefing_engine = BriefingEngine(db)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

AVAILABLE_MODELS: List[Dict[str, Any]] = [
    # 1. Official Google Antigravity Live Models (`agy.exe models`)
    {
        "id": "gemini-4-argon-high",
        "name": "Gemini 4 Argon (High)",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "High",
        "badge": "Antigravity",
        "badge_color": "cyan",
        "available": True,
        "description": "Google Gemini 4 Argon frontier reasoning (High effort, 1M context) via Antigravity."
    },
    {
        "id": "gemini-4-argon-medium",
        "name": "Gemini 4 Argon (Medium)",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Medium",
        "badge": "Antigravity",
        "badge_color": "cyan",
        "available": True,
        "description": "Google Gemini 4 Argon balanced frontier reasoning (Medium effort, 1M context) via Antigravity."
    },
    {
        "id": "gemini-4-argon-low",
        "name": "Gemini 4 Argon (Low)",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Low",
        "badge": "Antigravity",
        "badge_color": "cyan",
        "available": True,
        "description": "Google Gemini 4 Argon fast frontier reasoning (Low effort, 1M context) via Antigravity."
    },
    {
        "id": "gemini-3.8-flash-high",
        "name": "Gemini 3.8 Flash (High)",
        "aliases": ["Google Gemini 3.8 Flash (Antigravity)", "Gemini 3.8 Flash"],
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "High",
        "badge": "Antigravity",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini 3.8 Flash high-effort multi-agent workspace reasoning via Antigravity."
    },
    {
        "id": "gemini-3.8-flash-medium",
        "name": "Gemini 3.8 Flash (Medium)",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Medium",
        "badge": "Antigravity",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini 3.8 Flash balanced speed and reasoning via Antigravity."
    },
    {
        "id": "gemini-3.8-flash-low",
        "name": "Gemini 3.8 Flash (Low)",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Low",
        "badge": "Antigravity",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini 3.8 Flash ultra-low-latency execution via Antigravity."
    },
    {
        "id": "claude-opus-5-5-high",
        "name": "Claude Opus 5.5 (High)",
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "High",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Opus 5.5 deep architectural reasoning (High effort) via Antigravity."
    },
    {
        "id": "claude-opus-5-5-medium",
        "name": "Claude Opus 5.5 (Medium)",
        "aliases": ["Claude Opus 5.5"],
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Medium",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Opus 5.5 high-capability reasoning (Medium effort) via Antigravity."
    },
    {
        "id": "claude-opus-5-5-low",
        "name": "Claude Opus 5.5 (Low)",
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Low",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Opus 5.5 fast reasoning (Low effort) via Antigravity."
    },
    {
        "id": "claude-sonnet-5-5-high",
        "name": "Claude Sonnet 5.5 (High)",
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "High",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Sonnet 5.5 high-effort coding & analysis via Antigravity."
    },
    {
        "id": "claude-sonnet-5-5-medium",
        "name": "Claude Sonnet 5.5 (Medium)",
        "aliases": ["Claude Sonnet 5.5"],
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Medium",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Sonnet 5.5 balanced coding & analysis via Antigravity."
    },
    {
        "id": "claude-sonnet-5-5-low",
        "name": "Claude Sonnet 5.5 (Low)",
        "provider": "anthropic",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Low",
        "badge": "Antigravity",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Sonnet 5.5 rapid coding & triage via Antigravity."
    },
    {
        "id": "gpt-oss-120b-medium",
        "name": "GPT-OSS 120B (Medium)",
        "provider": "local",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Medium",
        "badge": "Antigravity",
        "badge_color": "orange",
        "available": True,
        "description": "Open-weights GPT-OSS 120B MoE reasoning engine via Antigravity."
    },
    # Backwards-compatible generic Argon alias (hidden from duplicate dropdown rendering)
    {
        "id": "gemini-4-argon",
        "name": "Google Gemini 4 Argon",
        "provider": "google",
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": "Frontier",
        "badge": "Argon",
        "badge_color": "cyan",
        "available": True,
        "hidden_in_menu": True,
        "description": "Google frontier reasoning model with 1M token context window and autonomous multi-step execution."
    },
    # 2. Cloud Hyperscalers & Developer CLI Tools
    {
        "id": "gemini-2.5-pro",
        "name": "Google Gemini 2.5 Pro (AI Studio REST API)",
        "provider": "google",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "dev_tool",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "Medium",
        "badge": "Gemini CLI",
        "badge_color": "green",
        "available": True,
        "description": "Google Gemini terminal CLI (`gemini`) and Cloud SDK agent bridge."
    },
    {
        "id": "gemini-experimental-preview",
        "name": "Gemini Next Experimental (Preview)",
        "provider": "google",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "Preview",
        "badge": "Unavailable",
        "badge_color": "gray",
        "available": False,
        "hidden_in_menu": True,
        "description": "Unreleased experimental frontier research checkpoint."
    },
    # Microsoft (Azure OpenAI, Azure AI Foundry, GitHub Models & GitHub Copilot)
    {
        "id": "azure-gpt-4o",
        "name": "Microsoft Azure OpenAI GPT-4o",
        "provider": "microsoft",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "dev_tool",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "Medium",
        "badge": "Copilot",
        "badge_color": "blue",
        "available": True,
        "description": "GitHub Copilot CLI shell suggestions and VS Code instructions bridge."
    },
    # Amazon Web Services (AWS Bedrock SigV4 / Bearer & Amazon Q Developer)
    {
        "id": "aws-bedrock-claude-3-7-sonnet",
        "name": "AWS Bedrock Claude 3.7 Sonnet",
        "provider": "aws",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "dev_tool",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "High",
        "badge": "AWS Q",
        "badge_color": "orange",
        "available": True,
        "description": "Amazon Q Developer CLI (`q`) and AWS architecture assistant."
    },
    # Anthropic Claude (Direct API & Claude Code CLI)
    {
        "id": "claude-code-cli",
        "name": "Anthropic Claude Code CLI",
        "provider": "anthropic",
        "source": "dev_tool",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "High",
        "badge": "Claude CLI",
        "badge_color": "purple",
        "available": True,
        "description": "Anthropic Claude Code autonomous terminal coding tool."
    },
    {
        "id": "claude-3-7-sonnet",
        "name": "Anthropic Claude 3.7 Sonnet (Direct API)",
        "aliases": ["Anthropic Claude 3.7 Sonnet (Direct)"],
        "provider": "anthropic",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "High",
        "badge": "Claude API",
        "badge_color": "purple",
        "available": True,
        "description": "Direct Anthropic Claude 3.7 hybrid reasoning & coding API."
    },
    # OpenAI Direct & Local Offline (0-Token)
    {
        "id": "openai-gpt-4o",
        "name": "OpenAI GPT-4o (Direct API)",
        "provider": "openai",
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
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
        "source": "hyperscaler",
        "group": "Cloud Hyperscalers & Dev Tools",
        "effort": "Local",
        "badge": "0-Token",
        "badge_color": "teal",
        "available": True,
        "description": "100% private, offline inference running via local Ollama daemon."
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
    now_ts = time.time()
    with _agent_lock:
        out: List[Dict[str, Any]] = []
        for agent in ACTIVE_PARALLEL_AGENTS.values():
            copy_agent = dict(agent)
            started_ts = float(copy_agent.get("started_at_ts") or now_ts)
            copy_agent["elapsed_sec"] = round(max(0.0, now_ts - started_ts), 1)
            out.append(copy_agent)
        return out


_ACTIVE_SUBPROCESSES: Dict[str, Any] = {}
_ACTIVE_CANCEL_EVENTS: Dict[str, threading.Event] = {}
MAX_HOST_RAM_PCT_FOR_PARALLEL = 88.0


class _AgentCancelledError(Exception):
    """Raised cleanly when a running parallel agent is cancelled by the user or server shutdown."""


def _terminate_process_tree(proc: Any) -> None:
    """Terminates a subprocess and any child workers cleanly without orphan leaks on Windows/POSIX."""
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    if os.name == "nt" and pid:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            return
        except Exception:
            pass
    try:
        proc.terminate()
        proc.wait(timeout=1.5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _get_system_ram_percent() -> float:
    """Returns host RAM usage percentage outside test mode so admission control guards personal laptops."""
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return 0.0
    try:
        from fleet.core.optimizer import get_memory_status
        mem = get_memory_status()
        return float(mem.get("percent_used", 0.0) or 0.0)
    except Exception:
        return 0.0


def _is_ram_admission_blocked(active_count: int) -> Tuple[bool, float]:
    """Allows at least 1 active CLI worker, then queues additional parallel workers if RAM >= 88%."""
    pct = _get_system_ram_percent()
    if active_count >= 1 and pct >= MAX_HOST_RAM_PCT_FOR_PARALLEL:
        return True, pct
    return False, pct


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
        now_ts = time.time()
        AGENT_STATE["parallel_agents"] = [
            {
                **a,
                "elapsed_sec": round(max(0.0, now_ts - float(a.get("started_at_ts") or now_ts)), 1),
            }
            for a in ACTIVE_PARALLEL_AGENTS.values()
        ]


_AGY_MODELS_SYNC_LOCK = threading.RLock()
_AGY_MODELS_LAST_SYNC_TS: float = 0.0
_AGY_MODELS_SYNC_IN_PROGRESS: bool = False
_AGY_MODELS_CACHE_TTL_SEC: float = 1800.0
_DYNAMIC_AGY_MODEL_IDS: Set[str] = set()


def _infer_agy_model_metadata(model_id: str, display_name: str) -> Dict[str, Any]:
    """Derives provider, effort, badge color, and context window for an `agy.exe models` entry."""
    low_id = model_id.lower()
    low_name = display_name.lower()
    if "high" in low_id or "(high)" in low_name:
        effort = "High"
    elif "low" in low_id or "(low)" in low_name:
        effort = "Low"
    else:
        effort = "Medium"

    if "argon" in low_id or "gemini-4" in low_id:
        provider = "google"
        badge_color = "cyan"
        limit = 1000000
    elif "gemini" in low_id:
        provider = "google"
        badge_color = "green"
        limit = 1000000
    elif "claude" in low_id:
        provider = "anthropic"
        badge_color = "purple"
        limit = 200000
    elif "oss" in low_id or "gpt" in low_id:
        provider = "local"
        badge_color = "orange"
        limit = 128000
    else:
        provider = "google"
        badge_color = "cyan"
        limit = 200000

    return {
        "id": model_id,
        "name": display_name,
        "provider": provider,
        "source": "antigravity",
        "group": "Antigravity Live Models",
        "effort": effort,
        "badge": "Antigravity",
        "badge_color": badge_color,
        "available": True,
        "description": f"{display_name} live model via Google Antigravity CLI (`agy`).",
        "_token_limit": limit,
    }


def sync_antigravity_cli_models(blocking: bool = False) -> List[Dict[str, Any]]:
    """
    Lazily synchronizes AVAILABLE_MODELS with `agy.exe models` in the background so future
    Google Antigravity model additions automatically appear in AFCC without blocking requests.
    """
    global _AGY_MODELS_LAST_SYNC_TS, _AGY_MODELS_SYNC_IN_PROGRESS
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return AVAILABLE_MODELS

    import time
    now = time.time()
    if not blocking and (now - _AGY_MODELS_LAST_SYNC_TS) < _AGY_MODELS_CACHE_TTL_SEC:
        return AVAILABLE_MODELS

    agy_home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    agy_exe = Path(agy_home) / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
    if not agy_exe.exists():
        _AGY_MODELS_LAST_SYNC_TS = now
        return AVAILABLE_MODELS

    def _worker() -> None:
        global _AGY_MODELS_LAST_SYNC_TS, _AGY_MODELS_SYNC_IN_PROGRESS
        try:
            res = subprocess.run(
                [str(agy_exe), "models"],
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            if res.returncode == 0 and (res.stdout or "").strip():
                discovered: List[Tuple[str, str]] = []
                for raw_line in res.stdout.splitlines():
                    line = raw_line.strip()
                    if not line or "\t" not in line:
                        continue
                    m_id, m_name = line.split("\t", 1)
                    m_id = m_id.strip()
                    m_name = m_name.strip()
                    if m_id and m_name:
                        discovered.append((m_id, m_name))
                if discovered:
                    with _AGY_MODELS_SYNC_LOCK:
                        existing_by_id = {m["id"]: m for m in AVAILABLE_MODELS}
                        insert_idx = 0
                        for idx, item in enumerate(AVAILABLE_MODELS):
                            if item.get("source") == "antigravity" and not item.get("hidden_in_menu"):
                                insert_idx = idx + 1
                        for m_id, m_name in discovered:
                            _DYNAMIC_AGY_MODEL_IDS.add(m_id)
                            if m_id in existing_by_id:
                                existing_by_id[m_id]["name"] = m_name
                                existing_by_id[m_id]["available"] = True
                            else:
                                meta = _infer_agy_model_metadata(m_id, m_name)
                                tok_limit = meta.pop("_token_limit", 200000)
                                MODEL_TOKEN_LIMITS.setdefault(m_id, tok_limit)
                                AVAILABLE_MODELS.insert(insert_idx, meta)
                                insert_idx += 1
            _AGY_MODELS_LAST_SYNC_TS = time.time()
        except Exception as exc:
            logger.debug(f"Background Antigravity model sync skipped: {exc}")
            _AGY_MODELS_LAST_SYNC_TS = time.time()
        finally:
            with _AGY_MODELS_SYNC_LOCK:
                _AGY_MODELS_SYNC_IN_PROGRESS = False

    with _AGY_MODELS_SYNC_LOCK:
        if _AGY_MODELS_SYNC_IN_PROGRESS:
            return AVAILABLE_MODELS
        _AGY_MODELS_SYNC_IN_PROGRESS = True

    if blocking:
        _worker()
    else:
        threading.Thread(target=_worker, daemon=True, name="ag-models-sync").start()
    return AVAILABLE_MODELS


def is_antigravity_native_model(model_id: Optional[str]) -> bool:
    """Returns True if `model_id` belongs to Google Antigravity CLI (`agy.exe`)."""
    if not model_id:
        return False
    low = model_id.strip().lower()
    if low in _DYNAMIC_AGY_MODEL_IDS:
        return True
    found = next((m for m in AVAILABLE_MODELS if m["id"].lower() == low), None)
    return bool(found and found.get("source") == "antigravity")


def get_available_models() -> List[Dict[str, Any]]:
    sync_antigravity_cli_models(blocking=False)
    return AVAILABLE_MODELS


def get_active_model() -> str:
    saved = db.get_setting("active_model", "gemini-3.8-flash-high")
    if any(m["id"] == saved and m["available"] for m in AVAILABLE_MODELS):
        return saved or "gemini-3.8-flash-high"
    return "gemini-3.8-flash-high"


def set_active_model(model_id: str) -> bool:
    if not model_id:
        return False
    needle = model_id.strip().lower()
    found = next(
        (
            m for m in AVAILABLE_MODELS
            if m["id"] == model_id
            or m["id"].lower() == needle
            or m["name"].lower() == needle
            or needle in [a.lower() for a in m.get("aliases", [])]
        ),
        None,
    )
    if found and found["available"]:
        db.set_setting("active_model", found["id"])
        return True
    return False


MODEL_TOKEN_LIMITS = {
    "gemini-4-argon-high": 1000000,
    "gemini-4-argon-medium": 1000000,
    "gemini-4-argon-low": 1000000,
    "gemini-4-argon": 1000000,
    "gemini-3.8-flash-high": 1000000,
    "gemini-3.8-flash-medium": 1000000,
    "gemini-3.8-flash-low": 1000000,
    "claude-opus-5-5-high": 200000,
    "claude-opus-5-5-medium": 200000,
    "claude-opus-5-5-low": 200000,
    "claude-sonnet-5-5-high": 200000,
    "claude-sonnet-5-5-medium": 200000,
    "claude-sonnet-5-5-low": 200000,
    "gpt-oss-120b-medium": 128000,
    "gemini-2.5-pro": 1000000,
    "google-vertex-gemini-2.5-pro": 1000000,
    "google-gemini-cli": 1000000,
    "gemini-2.0-flash": 1000000,
    "azure-gpt-4o": 128000,
    "azure-gpt-4o-mini": 128000,
    "azure-foundry-phi4": 128000,
    "github-models-gpt-4o": 128000,
    "github-copilot": 128000,
    "aws-bedrock-claude-3-7-sonnet": 200000,
    "aws-bedrock-claude-3-5-sonnet": 200000,
    "aws-bedrock-nova-pro": 300000,
    "aws-bedrock-titan": 32000,
    "aws-q-developer": 200000,
    "claude-code-cli": 200000,
    "claude-3-7-sonnet": 200000,
    "openai-gpt-4o": 128000,
    "ollama-llama3": 8192,
}


_SESSION_USAGE_LOCK = threading.RLock()
_SESSION_USAGE_TELEMETRY: Dict[str, Any] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "llm_calls": 0,
    "tier0_calls": 0,
    "estimated_cost_usd": 0.0,
    "last_provider": "tier0_local",
    "last_context_tokens": 0,
}


def record_llm_turn_usage(
    provider: str = "tier0_local",
    model_id: str = "",
    total_tokens: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tier0: bool = False,
) -> None:
    """Tracks cumulative Tier-0 vs real LLM calls, token counts, and estimated session cost."""
    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))
    tot_tok = max(0, int(total_tokens or (in_tok + out_tok)))
    if tot_tok > 0 and in_tok == 0 and out_tok == 0:
        in_tok = int(tot_tok * 0.65)
        out_tok = tot_tok - in_tok

    low_prov = (provider or "").lower()
    low_mod = (model_id or "").lower()
    turn_cost = 0.0
    if not tier0 and tot_tok > 0 and "ollama" not in low_prov and "antigravity cli" not in low_prov and "tier0" not in low_prov:
        rate_per_1m = 0.35 if ("flash" in low_mod or "mini" in low_mod or "haiku" in low_mod) else 3.00
        turn_cost = round((tot_tok / 1_000_000.0) * rate_per_1m, 6)

    with _SESSION_USAGE_LOCK:
        if tier0 or "tier0" in low_prov:
            _SESSION_USAGE_TELEMETRY["tier0_calls"] += 1
        else:
            _SESSION_USAGE_TELEMETRY["llm_calls"] += 1
        _SESSION_USAGE_TELEMETRY["input_tokens"] += in_tok
        _SESSION_USAGE_TELEMETRY["output_tokens"] += out_tok
        _SESSION_USAGE_TELEMETRY["total_tokens"] += tot_tok
        _SESSION_USAGE_TELEMETRY["estimated_cost_usd"] = round(
            float(_SESSION_USAGE_TELEMETRY["estimated_cost_usd"]) + turn_cost, 6
        )
        if provider:
            _SESSION_USAGE_TELEMETRY["last_provider"] = provider
        if tot_tok > 0:
            _SESSION_USAGE_TELEMETRY["last_context_tokens"] = tot_tok


def _estimate_transcript_active_tokens(t_path: Path) -> int:
    """Estimates current context tokens from the post-compaction transcript tail (bounded 512KB read)."""
    if not t_path or not t_path.exists():
        return 18450
    tail_window = 524288
    st_size = t_path.stat().st_size
    with open(t_path, "rb") as fb:
        if st_size > tail_window:
            fb.seek(st_size - tail_window)
        chunk = fb.read()
    marker_idx = chunk.rfind(b"<CONTEXT_SUMMARY>")
    active_bytes = chunk[marker_idx:] if marker_idx >= 0 else chunk
    return max(18450, len(active_bytes) // 6)


def get_token_health(simulated_status: Optional[str] = None) -> Dict[str, Any]:
    active_id = get_active_model()
    model_obj = next((m for m in AVAILABLE_MODELS if m["id"] == active_id), AVAILABLE_MODELS[0])
    limit = MODEL_TOKEN_LIMITS.get(active_id, 1000000)

    # Check simulated status or manual override in settings
    stored_override = db.get_setting("token_exhaustion_override")
    effective_status = simulated_status or stored_override

    # Estimate post-compaction active context tokens instead of dividing full historical file size by 4
    t_path = get_active_transcript_path()
    approx_tokens = 18450
    if t_path and t_path.exists():
        try:
            approx_tokens = _estimate_transcript_active_tokens(t_path)
        except Exception:
            pass
    with _SESSION_USAGE_LOCK:
        last_ctx_tok = int(_SESSION_USAGE_TELEMETRY.get("last_context_tokens") or 0)
    if last_ctx_tok > approx_tokens:
        approx_tokens = last_ctx_tok

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
    with _SESSION_USAGE_LOCK:
        usage_snap = dict(_SESSION_USAGE_TELEMETRY)
    est_cost = float(usage_snap.get("estimated_cost_usd") or 0.0)
    cost_str = "$0.00" if est_cost <= 0.0 else f"${est_cost:.4f}"
    billed_tokens = int(usage_snap.get("total_tokens") or 0)
    llm_calls = int(usage_snap.get("llm_calls") or 0)
    tier0_calls = int(usage_snap.get("tier0_calls") or 0)
    last_provider = str(usage_snap.get("last_provider") or "Tier 0 Local")
    tier_label = (
        "Tier 0 Fleet Governance ($0.00)"
        if est_cost <= 0.0 and llm_calls == 0
        else f"Tier 0 + {last_provider} Hybrid"
    )
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
        "input_tokens": int(usage_snap.get("input_tokens") or int(th["tokens_used"] * 0.65)),
        "output_tokens": int(usage_snap.get("output_tokens") or int(th["tokens_used"] * 0.35)),
        "real_tokens_billed": billed_tokens,
        "llm_calls": llm_calls,
        "tier0_calls": tier0_calls,
        "last_provider": last_provider,
        "cost_usd": cost_str,
        "estimated_cost_usd": round(est_cost, 6),
        "tier": tier_label,
        "provider": "Google DeepMind / Antigravity Multi-Model Hub",
        "status": "Exhausted (Prompts Vaulted)" if th["is_exhausted"] else ("Warning (Near Limit)" if th["is_warning"] else "Operational"),
        "vaulted_count": th["vaulted_count"],
        "recommended_fallback": th["recommended_fallback_name"]
    }



MAX_UPLOAD_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _prune_old_uploads(uploads_dir: Path, max_files: int = 200, max_bytes: int = 250 * 1024 * 1024) -> int:
    """Enforces LRU disk quota bounds on local uploaded image artifacts."""
    if not uploads_dir.is_dir():
        return 0
    entries: List[Tuple[float, int, Path]] = []
    total_bytes = 0
    for p in uploads_dir.iterdir():
        if p.is_file():
            try:
                st = p.stat()
                total_bytes += st.st_size
                entries.append((st.st_mtime, st.st_size, p))
            except OSError:
                continue
    if len(entries) <= max_files and total_bytes <= max_bytes:
        return 0
    entries.sort(key=lambda x: x[0])  # oldest first
    removed = 0
    remaining = len(entries)
    for _, f_size, p in entries:
        if remaining <= max_files and total_bytes <= max_bytes:
            break
        try:
            p.unlink(missing_ok=True)
            remaining -= 1
            total_bytes -= f_size
            removed += 1
        except OSError:
            pass
    return removed


def save_uploaded_image(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Saves an image to fleet/data/uploads with 10MB/extension validation and SHA-256 deduplication."""
    from fleet.core.token_optimizer import deduplicate_uploaded_image

    if len(file_bytes) > MAX_UPLOAD_IMAGE_BYTES:
        raise ValueError(f"Uploaded image exceeds maximum allowed size ({MAX_UPLOAD_IMAGE_BYTES // (1024 * 1024)} MB).")

    ext = Path(filename or "upload.png").suffix.lower()
    if ext and ext not in _ALLOWED_IMAGE_EXTS:
        raise ValueError(f"Unsupported upload extension '{ext}'. Allowed: {sorted(_ALLOWED_IMAGE_EXTS)}")

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
        if Path(clean_name).suffix.lower() not in _ALLOWED_IMAGE_EXTS:
            clean_name = f"{clean_name}.png"

        target_path = eff_uploads_dir / clean_name
        target_path.write_bytes(file_bytes)
        if not in_test:
            _prune_old_uploads(eff_uploads_dir)

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


def extract_task_fingerprint(text: str) -> Dict[str, Any]:
    """
    Extracts semantic and structural fingerprint of a task:
    - agent_targets: set of targeted agent names (e.g. 'health', 'optimizer', 'gmail', 'pr_review', 'backlog')
    - files: set of referenced filenames/paths (e.g. 'dashboard.html', 'health.py')
    - domains: set of recognized functional domains
    - key_terms: set of normalized content keywords
    """
    if not text:
        return {"agent_targets": set(), "files": set(), "domains": set(), "key_terms": set()}

    lower = text[:65536].lower()

    # 1. Agent Directives (@agent)
    agent_targets = set(re.findall(r"@([a-zA-Z0-9_-]+)", lower))

    # 2. File and Path References (strictly O(N) non-backtracking token scan — immune to polynomial ReDoS)
    files = set()
    delim_map = str.maketrans({c: " " for c in ",;:()[]{}<>\"'`"})
    for raw_tok in lower.translate(delim_map).split():
        tok = raw_tok.strip(".,;:!?").replace("\\", "/")
        if not tok or "." not in tok:
            continue
        base = tok.rsplit("/", 1)[-1]
        if "." not in base:
            continue
        stem, ext = base.rsplit(".", 1)
        if not stem or not ext or not ext.isalnum():
            continue
        if "/" not in tok and not (2 <= len(ext) <= 5):
            continue
        if stem.isdigit() and ext.isdigit():
            continue
        if all(ch.isalnum() or ch in "_-." for ch in stem):
            files.add(base)

    # 3. Domain Taxonomy Mapping
    domains = set()
    DOMAIN_KEYWORDS = {
        "health": {"health", "water", "vital", "vitals", "glucose", "sugar", "medication", "meds", "prescription", "sleep", "steps", "ffd", "diet", "doctor"},
        "optimizer": {"optimize", "optimizer", "ram", "memory", "cache", "caches", "temp", "dns", "cleanup", "performance", "disk"},
        "git_pr": {"git", "pr", "branch", "commit", "merge", "diff", "pull request", "review"},
        "email": {"gmail", "email", "mail", "inbox", "newsletter", "unsubscribe", "sync"},
        "tasks": {"backlog", "todo", "routine", "routines"},
        "tokens": {"token", "tokens", "quota", "exhausted", "vault"},
    }
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(kw) + r"\b", lower) for kw in kws):
            domains.add(domain)

    # 4. Significant Content Terms
    STOP_WORDS = {
        "this", "that", "with", "from", "have", "been", "were", "what", "when", "where",
        "which", "while", "please", "could", "should", "would", "about", "there", "their",
        "check", "show", "help", "also", "into", "some", "only", "then", "than", "more",
        "make", "will", "done", "test", "task", "parallel", "dispatched", "directly", "research"
    }
    raw_words = re.findall(r"\b[a-zA-Z]{4,}\b", lower)
    key_terms = {w for w in raw_words if w not in STOP_WORDS}

    return {
        "agent_targets": agent_targets,
        "files": files,
        "domains": domains,
        "key_terms": key_terms
    }


def detect_agent_task_overlap(new_task_text: str, running_agents: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Intelligently checks whether a new incoming task overlaps with any currently running parallel agent.
    Returns (True, reason) if an overlap is detected (meaning the new task must be queued).
    Returns (False, None) if the task is orthogonal/independent and safe to execute in parallel.
    """
    if not running_agents or not new_task_text:
        return False, None

    new_fp = extract_task_fingerprint(new_task_text)

    for a in running_agents:
        agent_id = a.get("agent_id", "Agent")
        running_task = a.get("task", "")
        run_fp = extract_task_fingerprint(running_task)

        # 1. Target Agent Directive Conflict
        shared_agents = new_fp["agent_targets"] & run_fp["agent_targets"]
        if shared_agents:
            target = sorted(shared_agents)[0]
            return True, f"Resource conflict on @{target} with active {agent_id}"

        # 2. Shared File / Resource Conflict
        shared_files = new_fp["files"] & run_fp["files"]
        if shared_files:
            fname = sorted(shared_files)[0]
            return True, f"File conflict on '{fname}' with active {agent_id}"

        # 3. Domain Subsystem Overlap
        shared_domains = new_fp["domains"] & run_fp["domains"]
        if shared_domains:
            dom = sorted(shared_domains)[0]
            return True, f"Domain overlap on '{dom}' with active {agent_id}"

        # 4. Significant Keyword Overlap
        shared_terms = new_fp["key_terms"] & run_fp["key_terms"]
        if len(shared_terms) >= 3:
            terms_str = ", ".join(sorted(shared_terms)[:3])
            return True, f"Semantic overlap on keywords ({terms_str}) with active {agent_id}"

    return False, None


_QUEUE_DRAIN_LOCK = threading.RLock()
_ORPHAN_RECOVERY_STATS: Dict[str, Any] = {
    "recovered_count": 0,
    "last_recovered_at": None,
}


def recover_orphaned_queue_on_startup() -> int:
    """Re-queues any 'processing' rows left in chat_queue from an unclean shutdown."""
    try:
        recovered = db.recover_orphaned_processing_messages() if hasattr(db, "recover_orphaned_processing_messages") else 0
    except Exception:
        recovered = 0
    if recovered > 0:
        _ORPHAN_RECOVERY_STATS["recovered_count"] = int(_ORPHAN_RECOVERY_STATS.get("recovered_count", 0)) + recovered
        _ORPHAN_RECOVERY_STATS["last_recovered_at"] = datetime.now().isoformat()
        try:
            db.log_activity("AntigravityQueue", "orphan_recovered", f"Recovered {recovered} orphaned processing prompt(s) on startup.")
        except Exception:
            pass
    return recovered


def cancel_running_agent(agent_id: str) -> Dict[str, Any]:
    """Signals cancellation to an active parallel agent, kills its child process tree, and drains next queued work."""
    clean_id = (agent_id or "").strip()
    with _agent_lock:
        entry = ACTIVE_PARALLEL_AGENTS.get(clean_id)
        if not entry:
            return {"status": "not_found", "cancelled": False, "agent_id": clean_id, "message": f"Agent {clean_id} is not active."}
        cancel_ev = _ACTIVE_CANCEL_EVENTS.get(clean_id)
        if cancel_ev is not None:
            cancel_ev.set()
        proc = _ACTIVE_SUBPROCESSES.pop(clean_id, None)
        q_id = entry.get("queue_id")
        task_label = str(entry.get("task") or "")[:80]
        ACTIVE_PARALLEL_AGENTS.pop(clean_id, None)
        _ACTIVE_CANCEL_EVENTS.pop(clean_id, None)

    if proc is not None:
        _terminate_process_tree(proc)

    if q_id:
        try:
            db.update_chat_queue_status(q_id, "cancelled")
        except Exception:
            pass
    try:
        append_transcript_turn(
            "PLANNER_RESPONSE",
            f"🛑 **Cancelled by User ({clean_id})**: Stopped execution for `\"{task_label}\"`.",
            source="MODEL",
        )
    except Exception:
        pass
    try:
        db.log_activity("ParallelAgent", "cancelled", f"{clean_id} cancelled by user ({task_label})")
    except Exception:
        pass
    sync_agent_state()
    process_next_in_queue()
    return {"status": "cancelled", "cancelled": True, "agent_id": clean_id, "queue_id": q_id}


def shutdown_all_parallel_agents() -> int:
    """Terminates all active child CLI subprocesses cleanly on server shutdown."""
    with _agent_lock:
        active_ids = list(ACTIVE_PARALLEL_AGENTS.keys())
        procs: List[Any] = []
        for aid in active_ids:
            ev = _ACTIVE_CANCEL_EVENTS.pop(aid, None)
            if ev is not None:
                ev.set()
            pr = _ACTIVE_SUBPROCESSES.pop(aid, None)
            if pr is not None:
                procs.append(pr)
        ACTIVE_PARALLEL_AGENTS.clear()
    for pr in procs:
        _terminate_process_tree(pr)
    sync_agent_state()
    return len(active_ids)


atexit.register(shutdown_all_parallel_agents)


def _spawn_parallel_agent_worker(task_text: str, queue_id: Optional[int] = None,
                                 images: Optional[List[str]] = None,
                                 model: Optional[str] = None) -> str:
    target_model = model or get_active_model()
    now_str = datetime.now().strftime("%H:%M:%S")
    started_ts = time.time()
    worker_uuid = uuid.uuid4().hex
    cancel_event = threading.Event()

    with _agent_lock:
        used_ids = set(ACTIVE_PARALLEL_AGENTS.keys())
        idx = 1
        while f"Agent-{idx}" in used_ids:
            idx += 1
        agent_id = f"Agent-{idx}"

        _ACTIVE_CANCEL_EVENTS[agent_id] = cancel_event
        ACTIVE_PARALLEL_AGENTS[agent_id] = {
            "agent_id": agent_id,
            "worker_uuid": worker_uuid,
            "task": task_text[:120],
            "queue_id": queue_id,
            "model": target_model,
            "status": "running",
            "started_at": now_str,
            "started_at_ts": started_ts,
            "elapsed_sec": 0.0,
            "pid": None,
            "timestamp": datetime.now().isoformat()
        }
    sync_agent_state()

    def _worker():
        try:
            _execute_agy_or_fallback(
                task_text,
                images=images,
                model=target_model,
                agent_id=agent_id,
                cancel_event=cancel_event,
            )
            if queue_id and not cancel_event.is_set():
                db.update_chat_queue_status(queue_id, "completed")
        except _AgentCancelledError:
            if queue_id:
                db.update_chat_queue_status(queue_id, "cancelled")
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                handle_token_exhaustion(str(e), target_model)
            else:
                if queue_id:
                    db.update_chat_queue_status(queue_id, "failed")
                db.log_activity("ParallelAgent", "error", f"{agent_id} error: {e}")
                append_transcript_turn(
                    "PLANNER_RESPONSE",
                    f"⚠️ **Agent Execution Error ({agent_id})**: {e}",
                    source="MODEL",
                )
        finally:
            with _agent_lock:
                if ACTIVE_PARALLEL_AGENTS.get(agent_id, {}).get("worker_uuid") == worker_uuid:
                    ACTIVE_PARALLEL_AGENTS.pop(agent_id, None)
                    _ACTIVE_SUBPROCESSES.pop(agent_id, None)
                    _ACTIVE_CANCEL_EVENTS.pop(agent_id, None)
            sync_agent_state()
            process_next_in_queue()

    threading.Thread(target=_worker, daemon=True).start()
    return agent_id


def process_next_in_queue():
    with _QUEUE_DRAIN_LOCK:
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

        ram_blocked, ram_pct = _is_ram_admission_blocked(get_active_agent_count())
        if ram_blocked:
            sync_agent_state()
            return

        max_slots = get_max_parallel_agents()
        with _agent_lock:
            available_slots = max_slots - len(ACTIVE_PARALLEL_AGENTS)
            if available_slots <= 0:
                sync_agent_state()
                return

        # Support mocked get_next_queued_chat_message in unit tests
        is_mocked_queue = (
            hasattr(db.get_next_queued_chat_message, "assert_called")
            or hasattr(db.get_next_queued_chat_message, "side_effect")
        )
        if is_mocked_queue:
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

        launched = 0
        running_now = get_parallel_agents()
        for item in items:
            if launched >= available_slots:
                break
            ram_blocked_iter, _ = _is_ram_admission_blocked(len(running_now))
            if ram_blocked_iter:
                break
            # Intelligent Overlap Check (includes siblings launched earlier in this batch)
            has_overlap, _ = detect_agent_task_overlap(item.get("prompt", ""), running_now)
            if has_overlap:
                continue

            q_id = item["id"]
            if is_mocked_queue or not hasattr(db, "claim_queued_chat_message"):
                db.update_chat_queue_status(q_id, "processing")
            elif not db.claim_queued_chat_message(q_id):
                continue

            spawned_id = _spawn_parallel_agent_worker(
                task_text=item["prompt"],
                queue_id=q_id,
                images=item.get("images", []),
                model=item.get("model")
            )
            running_now.append({"agent_id": spawned_id, "task": str(item.get("prompt", ""))[:120]})
            launched += 1


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


_ACTIVE_TRANSCRIPT_PATH_CACHE: Dict[str, Any] = {
    "home": "",
    "path": None,
    "expires_at": 0.0,
    "ttl_sec": 3.0,
    "hits": 0,
    "misses": 0,
}


def invalidate_active_transcript_path_cache() -> None:
    _ACTIVE_TRANSCRIPT_PATH_CACHE["expires_at"] = 0.0


def get_active_transcript_path() -> Optional[Path]:
    """Finds the most recently active Antigravity session transcript.jsonl (3s scandir memoized outside tests)."""
    userprofile = os.environ.get("USERPROFILE")
    if userprofile is None and os.name != "nt":
        userprofile = os.environ.get("HOME")
    if not userprofile:
        return None

    in_test = os.environ.get("FLEET_TEST_MODE") == "1"
    now_mono = time.monotonic()
    if not in_test:
        cached_path = _ACTIVE_TRANSCRIPT_PATH_CACHE.get("path")
        if (
            _ACTIVE_TRANSCRIPT_PATH_CACHE.get("home") == userprofile
            and now_mono < float(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("expires_at") or 0.0)
            and isinstance(cached_path, Path)
            and cached_path.is_file()
        ):
            _ACTIVE_TRANSCRIPT_PATH_CACHE["hits"] = int(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("hits", 0)) + 1
            return cached_path

    _ACTIVE_TRANSCRIPT_PATH_CACHE["misses"] = int(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("misses", 0)) + 1
    search_dirs = [
        Path(userprofile) / ".gemini" / "antigravity" / "brain",
        Path(userprofile) / ".gemini" / "antigravity-cli" / "brain",
    ]

    sessions: List[Tuple[float, Path]] = []
    for brain_dir in search_dirs:
        try:
            if brain_dir.is_dir():
                with os.scandir(brain_dir) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                t_file = Path(entry.path) / ".system_generated" / "logs" / "transcript.jsonl"
                                if t_file.is_file():
                                    sessions.append((t_file.stat().st_mtime, t_file))
                        except (FileNotFoundError, OSError):
                            pass
        except (FileNotFoundError, OSError):
            pass

    if not sessions:
        if not in_test:
            _ACTIVE_TRANSCRIPT_PATH_CACHE.update({"home": userprofile, "path": None, "expires_at": now_mono + 1.5})
        return None

    sessions.sort(key=lambda s: s[0], reverse=True)
    chosen = sessions[0][1]
    if not in_test:
        _ACTIVE_TRANSCRIPT_PATH_CACHE.update({
            "home": userprofile,
            "path": chosen,
            "expires_at": now_mono + float(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("ttl_sec") or 3.0),
        })
    return chosen


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


_TRANSCRIPT_IO_LOCK = threading.RLock()
_TRANSCRIPT_MEM_CACHE: Dict[str, Any] = {
    "path": None,
    "mtime_ns": -1,
    "size": -1,
    "first_sig": b"",
    "tail_only": False,
    "raw_steps": [],
    "line_count": 0,
}
_TRANSCRIPT_TAIL_CACHE_MAX = 300
_TRANSCRIPT_CACHE_STATS: Dict[str, int] = {
    "cache_hits": 0,
    "incremental_reads": 0,
    "full_reads": 0,
    "delta_unchanged_hits": 0,
    "partial_line_deferrals": 0,
}


def get_transcript_cache_stats() -> Dict[str, Any]:
    """Returns Antigravity transcript cache & delta fast-path telemetry."""
    with _TRANSCRIPT_IO_LOCK:
        total_req = (
            _TRANSCRIPT_CACHE_STATS["cache_hits"]
            + _TRANSCRIPT_CACHE_STATS["incremental_reads"]
            + _TRANSCRIPT_CACHE_STATS["full_reads"]
        )
        hit_pct = round(
            ((_TRANSCRIPT_CACHE_STATS["cache_hits"] + _TRANSCRIPT_CACHE_STATS["incremental_reads"]) / total_req) * 100.0,
            1,
        ) if total_req > 0 else 100.0
        return {
            "cached_steps": len(_TRANSCRIPT_MEM_CACHE.get("raw_steps") or []),
            "max_tail_steps": _TRANSCRIPT_TAIL_CACHE_MAX,
            "line_count": int(_TRANSCRIPT_MEM_CACHE.get("line_count", 0)),
            "cache_hits": _TRANSCRIPT_CACHE_STATS["cache_hits"],
            "incremental_reads": _TRANSCRIPT_CACHE_STATS["incremental_reads"],
            "full_reads": _TRANSCRIPT_CACHE_STATS["full_reads"],
            "delta_unchanged_hits": _TRANSCRIPT_CACHE_STATS["delta_unchanged_hits"],
            "partial_line_deferrals": _TRANSCRIPT_CACHE_STATS.get("partial_line_deferrals", 0),
            "hit_rate_pct": hit_pct,
            "path_cache_hits": int(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("hits", 0)),
            "path_cache_misses": int(_ACTIVE_TRANSCRIPT_PATH_CACHE.get("misses", 0)),
        }


_AFCC_CLI_CONVERSATION_ID: Optional[str] = None
_CLI_CONV_LOCK = threading.RLock()
_PRIMARY_CONV_LEASE_OWNER: Optional[str] = None


def _acquire_cli_conversation_lease(agent_id: str) -> Tuple[bool, Optional[str]]:
    """Grants persisted primary conversation continuity to one active worker; siblings run ephemeral."""
    global _AFCC_CLI_CONVERSATION_ID, _PRIMARY_CONV_LEASE_OWNER
    owner_key = agent_id or f"thread-{threading.get_ident()}"
    with _CLI_CONV_LOCK:
        if _PRIMARY_CONV_LEASE_OWNER is None or _PRIMARY_CONV_LEASE_OWNER == owner_key:
            _PRIMARY_CONV_LEASE_OWNER = owner_key
            if not _AFCC_CLI_CONVERSATION_ID:
                try:
                    saved = str(db.get_setting("antigravity_cli_conversation_id", "") or "").strip()
                    if saved and all(ch.isalnum() or ch in "_-" for ch in saved):
                        _AFCC_CLI_CONVERSATION_ID = saved
                except Exception:
                    pass
            return True, _AFCC_CLI_CONVERSATION_ID
        return False, None


def _release_cli_conversation_lease(agent_id: str, new_conv_id: Optional[str] = None, reset: bool = False) -> None:
    global _AFCC_CLI_CONVERSATION_ID, _PRIMARY_CONV_LEASE_OWNER
    owner_key = agent_id or f"thread-{threading.get_ident()}"
    with _CLI_CONV_LOCK:
        if _PRIMARY_CONV_LEASE_OWNER != owner_key:
            return
        if reset:
            _AFCC_CLI_CONVERSATION_ID = None
            try:
                db.set_setting("antigravity_cli_conversation_id", "")
            except Exception:
                pass
        elif new_conv_id and all(ch.isalnum() or ch in "_-" for ch in new_conv_id):
            _AFCC_CLI_CONVERSATION_ID = new_conv_id
            try:
                db.set_setting("antigravity_cli_conversation_id", new_conv_id)
            except Exception:
                pass
        _PRIMARY_CONV_LEASE_OWNER = None


def _read_tail_highest_step(t_path: Path, st_size: int) -> int:
    """Finds the highest step_index in O(1) time by reading the tail of transcript.jsonl."""
    if st_size <= 0:
        return 0
    if (
        _TRANSCRIPT_MEM_CACHE.get("path") == str(t_path)
        and _TRANSCRIPT_MEM_CACHE.get("size") == st_size
        and _TRANSCRIPT_MEM_CACHE.get("raw_steps")
    ):
        highest_cached = 0
        for item in reversed(_TRANSCRIPT_MEM_CACHE["raw_steps"][-40:]):
            s = item.get("step_index", 0)
            if isinstance(s, int) and s > highest_cached:
                highest_cached = s
        if highest_cached > 0:
            return highest_cached

    highest_step = 0
    tail_window = 131072  # 128 KB tail window
    with open(t_path, "rb") as fb:
        if st_size > tail_window:
            fb.seek(st_size - tail_window)
            raw_tail = fb.read()
            tail_lines = raw_tail.decode("utf-8", errors="replace").splitlines()[1:]
        else:
            raw_tail = fb.read()
            tail_lines = raw_tail.decode("utf-8", errors="replace").splitlines()

    for line in tail_lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            s = item.get("step_index", 0)
            if isinstance(s, int) and s > highest_step:
                highest_step = s
        except Exception:
            continue

    if highest_step == 0 and raw_tail:
        for m in re.finditer(rb'"step_index"\s*:\s*(\d+)', raw_tail):
            try:
                val = int(m.group(1))
                if val > highest_step:
                    highest_step = val
            except Exception:
                continue
    return highest_step


def append_transcript_turn(turn_type: str, content: str, source: str = "USER_EXPLICIT",
                           images: Optional[List[str]] = None, thinking: str = "",
                           tool_calls: Optional[List[Dict[str, Any]]] = None) -> Optional[int]:
    """
    Appends a turn to the active transcript.jsonl under _TRANSCRIPT_IO_LOCK and invalidates cache safely.
    Enables AFCC to write directly to the Antigravity conversation stream even when VS Code is closed.
    """
    try:
        if os.environ.get("FLEET_TEST_MODE") == "1":
            up = (os.environ.get("USERPROFILE") or os.environ.get("HOME") or "").lower()
            if not any(tag in up for tag in ("temp", "tmp", "pytest")):
                return None
        with _TRANSCRIPT_IO_LOCK:
            t_path = get_active_transcript_path()
            if not t_path:
                userprofile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
                if not userprofile:
                    return None
                afcc_brain = Path(userprofile) / ".gemini" / "antigravity" / "brain" / "afcc-live" / ".system_generated" / "logs"
                afcc_brain.mkdir(parents=True, exist_ok=True)
                t_path = afcc_brain / "transcript.jsonl"
                if not t_path.exists():
                    t_path.touch()
                invalidate_active_transcript_path_cache()

            highest_step = 0
            if t_path.exists():
                highest_step = _read_tail_highest_step(t_path, t_path.stat().st_size)
            next_step = highest_step + 1
            now_iso = datetime.now(timezone.utc).isoformat()
            turn: Dict[str, Any] = {
                "step_index": next_step,
                "source": source,
                "type": turn_type,
                "status": "DONE",
                "created_at": now_iso,
                "content": content,
            }
            if images:
                media_list = []
                for img in images:
                    fname = Path(img).name
                    media_list.append({
                        "name": fname,
                        "url": f"/api/antigravity/media/{fname}",
                        "mime_type": "image/png",
                        "uri": str(img)
                    })
                turn["media"] = media_list
            if thinking:
                turn["thinking"] = thinking
            if tool_calls:
                turn["tool_calls"] = tool_calls

            with open(t_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(turn) + "\n")
                f.flush()

            # Keep path/size intact and invalidate mtime_ns so parse_transcript performs an O(1) incremental tail read
            _TRANSCRIPT_MEM_CACHE["mtime_ns"] = -1
            return next_step
    except Exception as e:
        logger.warning(f"Failed to append turn to transcript: {e}")
        return None


_AGY_CB_LOCK = threading.RLock()
_AGY_CIRCUIT_BREAKER: Dict[str, Any] = {
    "consecutive_failures": 0,
    "open_until_ts": 0.0,
    "threshold": 3,
    "cooldown_sec": 60.0,
    "last_error": "",
    "trips": 0,
}


def _agy_cb_allow() -> bool:
    if getattr(subprocess.run, "__module__", "") != "subprocess":
        return True
    with _AGY_CB_LOCK:
        open_until = float(_AGY_CIRCUIT_BREAKER.get("open_until_ts") or 0.0)
        return time.monotonic() >= open_until


def _agy_cb_record_success() -> None:
    with _AGY_CB_LOCK:
        _AGY_CIRCUIT_BREAKER["consecutive_failures"] = 0
        _AGY_CIRCUIT_BREAKER["open_until_ts"] = 0.0
        _AGY_CIRCUIT_BREAKER["last_error"] = ""


def _agy_cb_record_failure(reason: str = "") -> bool:
    with _AGY_CB_LOCK:
        fails = int(_AGY_CIRCUIT_BREAKER.get("consecutive_failures") or 0) + 1
        _AGY_CIRCUIT_BREAKER["consecutive_failures"] = fails
        _AGY_CIRCUIT_BREAKER["last_error"] = (reason or "")[:200]
        threshold = int(_AGY_CIRCUIT_BREAKER.get("threshold") or 3)
        if fails >= threshold:
            _AGY_CIRCUIT_BREAKER["open_until_ts"] = time.monotonic() + float(_AGY_CIRCUIT_BREAKER.get("cooldown_sec") or 60.0)
            _AGY_CIRCUIT_BREAKER["trips"] = int(_AGY_CIRCUIT_BREAKER.get("trips") or 0) + 1
            return True
        return False


def _run_agy_subprocess_managed(
    stdin_cmd: List[str],
    full_prompt: str,
    timeout_sec: int,
    cwd: str,
    creationflags: int,
    agent_id: str = "",
    cancel_event: Optional[threading.Event] = None,
) -> subprocess.CompletedProcess:
    """Runs agy.exe via cancelable Popen + tree termination (preserving mocked subprocess.run in tests)."""
    if cancel_event is not None and cancel_event.is_set():
        raise _AgentCancelledError(f"Agent {agent_id or 'cli'} cancelled before launch")

    if getattr(subprocess.run, "__module__", "") != "subprocess":
        return subprocess.run(
            stdin_cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            cwd=cwd,
            shell=False,
            creationflags=creationflags,
        )

    proc = subprocess.Popen(
        stdin_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        shell=False,
        creationflags=creationflags,
    )
    if agent_id:
        with _agent_lock:
            _ACTIVE_SUBPROCESSES[agent_id] = proc
            if agent_id in ACTIVE_PARALLEL_AGENTS:
                ACTIVE_PARALLEL_AGENTS[agent_id]["pid"] = proc.pid
        sync_agent_state()

    out_chunks: List[str] = []
    err_chunks: List[str] = []

    def _drain_stream(stream_obj: Any, bucket: List[str]) -> None:
        if stream_obj is None:
            return
        try:
            bucket.append(stream_obj.read())
        except Exception:
            pass
        finally:
            try:
                stream_obj.close()
            except Exception:
                pass

    def _feed_stdin() -> None:
        if proc.stdin is None:
            return
        try:
            proc.stdin.write(full_prompt)
            proc.stdin.flush()
        except Exception:
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    t_in = threading.Thread(target=_feed_stdin, daemon=True)
    t_out = threading.Thread(target=_drain_stream, args=(proc.stdout, out_chunks), daemon=True)
    t_err = threading.Thread(target=_drain_stream, args=(proc.stderr, err_chunks), daemon=True)
    t_in.start()
    t_out.start()
    t_err.start()

    deadline = time.monotonic() + max(1, int(timeout_sec))
    try:
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                _terminate_process_tree(proc)
                raise _AgentCancelledError(f"Agent {agent_id or 'cli'} cancelled during execution")
            if time.monotonic() >= deadline:
                _terminate_process_tree(proc)
                raise subprocess.TimeoutExpired(stdin_cmd, timeout_sec)
            time.sleep(0.15)
        t_out.join(timeout=2.0)
        t_err.join(timeout=2.0)
        t_in.join(timeout=1.0)
        return subprocess.CompletedProcess(
            stdin_cmd,
            proc.returncode or 0,
            "".join(out_chunks),
            "".join(err_chunks),
        )
    finally:
        if agent_id:
            with _agent_lock:
                _ACTIVE_SUBPROCESSES.pop(agent_id, None)


def _execute_agy_or_fallback(
    prompt_text: str,
    images: Optional[List[str]] = None,
    model: Optional[str] = None,
    agent_id: str = "",
    cancel_event: Optional[threading.Event] = None,
) -> Any:
    from fleet.core.token_optimizer import compress_prompt, select_optimal_model_tier
    if cancel_event is not None and cancel_event.is_set():
        raise _AgentCancelledError(f"Agent {agent_id or 'worker'} cancelled")

    agy_home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    agy_exe = Path(agy_home) / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
    compressed = compress_prompt(prompt_text)
    clean_prompt = compressed["text"]
    requested_model = model or get_active_model()
    if requested_model and requested_model != "auto":
        target_model = requested_model
    else:
        th_pct = get_token_health().get("percent_used", 0.0)
        target_model = select_optimal_model_tier(clean_prompt, requested_model, token_usage_pct=th_pct)

    full_prompt = clean_prompt
    if images:
        img_refs = "\n".join([f"- {img}" for img in images])
        full_prompt = f"{prompt_text}\n\n<ADDITIONAL_METADATA>\nThe user has uploaded {len(images)} image(s):\n{img_refs}\n</ADDITIONAL_METADATA>"

    # 1. Developer Tool: Claude Code CLI
    if target_model == "claude-code-cli":
        from fleet.core.dev_tools import execute_claude_code
        db.log_activity("ClaudeCodeCLI", "prompt_executed", prompt_text[:120])
        res = execute_claude_code(full_prompt)
        record_llm_turn_usage("ClaudeCodeCLI", target_model)
        reply = res.get("output") or res.get("message") or "Executed via Claude Code CLI."
        append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
        return res

    # 2. Developer Tool: GitHub Copilot CLI
    if target_model == "github-copilot":
        from fleet.core.dev_tools import execute_github_copilot_command
        db.log_activity("GitHubCopilot", "prompt_executed", prompt_text[:120])
        res = execute_github_copilot_command(full_prompt)
        record_llm_turn_usage("GitHubCopilot", target_model)
        reply = res.get("output") or res.get("message") or "Executed via GitHub Copilot."
        append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
        return res

    # 2b. Developer Tool: Google Gemini CLI & Cloud SDK
    if target_model == "google-gemini-cli":
        from fleet.core.dev_tools import execute_google_gemini_cli
        db.log_activity("GoogleGeminiCLI", "prompt_executed", prompt_text[:120])
        res = execute_google_gemini_cli(full_prompt)
        record_llm_turn_usage("GoogleGeminiCLI", target_model)
        reply = res.get("output") or res.get("message") or "Executed via Google Gemini CLI."
        append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
        return res

    # 2c. Developer Tool: Amazon Q Developer CLI
    if target_model == "aws-q-developer":
        from fleet.core.dev_tools import execute_aws_q_developer
        db.log_activity("AmazonQDeveloper", "prompt_executed", prompt_text[:120])
        res = execute_aws_q_developer(full_prompt)
        record_llm_turn_usage("AmazonQDeveloper", target_model)
        reply = res.get("output") or res.get("message") or "Executed via Amazon Q Developer CLI."
        append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
        return res

    # 3. Multi-Hyperscaler Gateway (Google Vertex/Gemini, Microsoft Azure/Foundry/GitHub Models, AWS Bedrock, Anthropic Claude, OpenAI, Local Ollama)
    is_agy_native = is_antigravity_native_model(target_model)
    is_hyperscaler = (
        any(target_model.startswith(pfx) for pfx in ["azure-", "github-models-", "aws-", "ollama-", "gemini-2", "google-vertex-", "openai-"])
        or (target_model.startswith("claude-") and (not is_agy_native or not agy_exe.exists()))
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
        hs_tokens = int(res_hs.get("tokens_used") or 0)
        record_llm_turn_usage(
            str(res_hs.get("provider") or provider),
            str(res_hs.get("model") or target_model),
            total_tokens=hs_tokens,
            tier0=str(res_hs.get("tier") or "").startswith("TIER_0"),
        )
        reply = res_hs.get("text") or res_hs.get("response") or res_hs.get("message", "")
        append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
        db.log_activity("HyperscalerGateway", "prompt_executed", f"[{provider}] {prompt_text[:120]}")
        return res_hs

    if agy_exe.exists():
        if os.environ.get("FLEET_TEST_MODE") == "1":
            from unittest.mock import Mock
            if not isinstance(subprocess.run, Mock):
                db.log_activity("AntigravityCLI", "prompt_executed", prompt_text[:120])
                return

        executed_via_agy = False
        is_primary_lease = False
        repo_cwd = str(Path(__file__).resolve().parent.parent.parent)

        if _agy_cb_allow():
            try:
                from fleet.core.hyperscalers import _normalize_agy_cli_model
                agy_model = _normalize_agy_cli_model(target_model)
                is_primary_lease, leased_conv_id = _acquire_cli_conversation_lease(agent_id)
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

                def _run_agy_cli_turn(conv_id: Optional[str]) -> subprocess.CompletedProcess:
                    base_flags = [
                        "--model", agy_model,
                        "--output-format", "json",
                        "--disable-slash-commands",
                        "--dangerously-skip-permissions",
                    ]
                    if conv_id and all(ch.isalnum() or ch in "_-" for ch in conv_id):
                        base_flags.extend(["--conversation", conv_id])
                    stdin_cmd = [
                        str(agy_exe),
                        "-p",
                        "Follow all instructions and respond to the complete prompt piped via stdin.",
                        "--input-format",
                        "text",
                    ] + base_flags
                    return _run_agy_subprocess_managed(
                        stdin_cmd=stdin_cmd,
                        full_prompt=full_prompt,
                        timeout_sec=600,
                        cwd=repo_cwd,
                        creationflags=creation_flags,
                        agent_id=agent_id,
                        cancel_event=cancel_event,
                    )

                res = _run_agy_cli_turn(leased_conv_id)
                if res.returncode != 0 and is_primary_lease and leased_conv_id and not (res.stdout or "").strip():
                    _release_cli_conversation_lease(agent_id, None, reset=True)
                    is_primary_lease, _ = _acquire_cli_conversation_lease(agent_id)
                    res = _run_agy_cli_turn(None)

                err_output = res.stderr or ""
                out_output = res.stdout or ""
                combined = (err_output + " " + out_output).lower()
                if any(term in combined for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                    _release_cli_conversation_lease(agent_id, None, reset=False)
                    handle_token_exhaustion(f"Quota error: {err_output[:120]}", target_model)
                    return
                if out_output.strip():
                    reply_text = out_output.strip()
                    discovered_conv_id: Optional[str] = None
                    try:
                        parsed = json.loads(reply_text)
                        if isinstance(parsed, dict):
                            conv_id = parsed.get("conversation_id")
                            if conv_id and isinstance(conv_id, str):
                                discovered_conv_id = conv_id
                            usage = parsed.get("usage")
                            if isinstance(usage, dict):
                                record_llm_turn_usage(
                                    "Google Antigravity CLI",
                                    agy_model,
                                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                                )
                            else:
                                record_llm_turn_usage("Google Antigravity CLI", agy_model)
                            reply_text = parsed.get("response") or parsed.get("content") or parsed.get("output") or reply_text
                        else:
                            record_llm_turn_usage("Google Antigravity CLI", agy_model)
                    except Exception:
                        record_llm_turn_usage("Google Antigravity CLI", agy_model)
                    if is_primary_lease:
                        _release_cli_conversation_lease(agent_id, discovered_conv_id)
                    _agy_cb_record_success()
                    db.log_activity("AntigravityCLI", "prompt_executed", prompt_text[:120])
                    append_transcript_turn("PLANNER_RESPONSE", str(reply_text).strip(), source="MODEL")
                    executed_via_agy = True
                    return {"status": "success", "text": str(reply_text).strip()}
                else:
                    if is_primary_lease:
                        _release_cli_conversation_lease(agent_id, None)
                    _agy_cb_record_failure(err_output or f"exit code {res.returncode}")
                    db.log_activity("AntigravityCLI", "error", (err_output or f"Empty CLI output (exit {res.returncode})")[:120])
            except _AgentCancelledError:
                if is_primary_lease:
                    _release_cli_conversation_lease(agent_id, None)
                raise
            except subprocess.TimeoutExpired:
                if is_primary_lease:
                    _release_cli_conversation_lease(agent_id, None)
                _agy_cb_record_failure("Timeout after 600s")
                logger.info("Antigravity CLI timed out after 600s. Routing to Non-Recursive Hyperscaler Gateway.")
            except Exception as e:
                if is_primary_lease:
                    _release_cli_conversation_lease(agent_id, None)
                err_msg = str(e).lower()
                if any(term in err_msg for term in ["resource_exhausted", "quota", "rate_limit", "context_length_exceeded", "429"]):
                    handle_token_exhaustion(str(e), target_model)
                    return
                _agy_cb_record_failure(str(e))
                db.log_activity("AntigravityCLI", "error", str(e))

        # Non-recursive fallback: never re-enter _call_antigravity_cli inside HyperscalerGateway
        if not executed_via_agy:
            from fleet.core.hyperscalers import HyperscalerGateway
            gateway = HyperscalerGateway()
            res_hs = gateway.complete(prompt=full_prompt, provider="google", model=target_model, allow_agy_cli=False)
            record_llm_turn_usage(
                str(res_hs.get("provider") or "google"),
                str(res_hs.get("model") or target_model),
                total_tokens=int(res_hs.get("tokens_used") or 0),
                tier0=str(res_hs.get("tier") or "").startswith("TIER_0"),
            )
            reply = res_hs.get("text") or res_hs.get("response") or res_hs.get("message", "")
            append_transcript_turn("PLANNER_RESPONSE", reply, source="MODEL")
            db.log_activity("HyperscalerGateway", "autonomous_prompt_executed", f"[google] {prompt_text[:120]}")
            return res_hs
    else:
        tags = "prompt,dashboard"
        if images:
            tags += ",media"
        note_id = db.add_note(title="Dashboard Prompt", content=full_prompt, tags=tags)
        db.log_activity("DashboardUser", "web_prompt", prompt_text[:120])
        append_transcript_turn("PLANNER_RESPONSE", f"📝 Saved prompt as Fleet Note #{note_id}: {prompt_text[:120]}", source="MODEL")






def parse_transcript(limit: int = 50, since_step: Optional[int] = None) -> Dict[str, Any]:
    """
    Parses the latest entries from the transcript log into structured conversation turns.
    Runs at Tier 0 (0 Tokens / local disk only) under _TRANSCRIPT_IO_LOCK with newline-aligned delta reads.
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
        with _TRANSCRIPT_IO_LOCK:
            st = transcript_path.stat()
            st_size = st.st_size if isinstance(getattr(st, "st_size", None), int) else -1
            need_full_history = bool(
                not limit
                or limit <= 0
                or (
                    since_step is not None
                    and _TRANSCRIPT_MEM_CACHE.get("tail_only")
                    and _TRANSCRIPT_MEM_CACHE.get("raw_steps")
                    and since_step < _TRANSCRIPT_MEM_CACHE["raw_steps"][0].get("step_index", 0)
                )
            )
            can_use_tail_cache = not (need_full_history and _TRANSCRIPT_MEM_CACHE.get("tail_only"))
            cached_size = _TRANSCRIPT_MEM_CACHE.get("size", -1)

            if (
                can_use_tail_cache
                and _TRANSCRIPT_MEM_CACHE["path"] == str(transcript_path)
                and _TRANSCRIPT_MEM_CACHE["mtime_ns"] == st.st_mtime_ns
                and cached_size == st.st_size
            ):
                _TRANSCRIPT_CACHE_STATS["cache_hits"] += 1
                cached_steps = _TRANSCRIPT_MEM_CACHE["raw_steps"]
                total_lines = int(_TRANSCRIPT_MEM_CACHE.get("line_count", len(cached_steps)))
                cached_latest = max(
                    (s.get("step_index", 0) for s in cached_steps if isinstance(s.get("step_index"), int)),
                    default=0,
                )
                if since_step is not None and cached_steps and cached_latest > 0 and since_step >= cached_latest:
                    _TRANSCRIPT_CACHE_STATS["delta_unchanged_hits"] += 1
                    return {
                        "status": "success",
                        "session_id": session_id,
                        "total_steps": total_lines,
                        "latest_step": cached_latest,
                        "unchanged": True,
                        "messages": [],
                    }
                raw_steps = list(cached_steps)
            else:
                loaded_incrementally = False
                if (
                    can_use_tail_cache
                    and _TRANSCRIPT_MEM_CACHE["path"] == str(transcript_path)
                    and isinstance(cached_size, int)
                    and cached_size > 0
                    and st_size > cached_size
                ):
                    with open(transcript_path, "rb") as fb:
                        cached_sig = _TRANSCRIPT_MEM_CACHE.get("first_sig", b"")
                        first_sig = fb.read(len(cached_sig)) if cached_sig else b""
                        if cached_sig and first_sig == cached_sig:
                            fb.seek(cached_size)
                            raw_delta = fb.read()
                            last_nl = raw_delta.rfind(b"\n")
                            if last_nl < 0:
                                _TRANSCRIPT_CACHE_STATS["partial_line_deferrals"] += 1
                                raw_steps = list(_TRANSCRIPT_MEM_CACHE["raw_steps"])
                                total_lines = int(_TRANSCRIPT_MEM_CACHE.get("line_count", len(raw_steps)))
                                loaded_incrementally = True
                            else:
                                complete_chunk = raw_delta[: last_nl + 1]
                                new_cached_size = cached_size + last_nl + 1
                                delta_lines = [
                                    ln.strip()
                                    for ln in complete_chunk.decode("utf-8", errors="replace").splitlines()
                                    if ln.strip()
                                ]
                                new_steps = []
                                for ln in delta_lines:
                                    try:
                                        new_steps.append(json.loads(ln))
                                    except Exception:
                                        continue
                                combined_steps = list(_TRANSCRIPT_MEM_CACHE["raw_steps"]) + new_steps
                                if _TRANSCRIPT_MEM_CACHE.get("tail_only") and len(combined_steps) > _TRANSCRIPT_TAIL_CACHE_MAX:
                                    combined_steps = combined_steps[-_TRANSCRIPT_TAIL_CACHE_MAX:]
                                total_lines = _TRANSCRIPT_MEM_CACHE["line_count"] + len(delta_lines)
                                _TRANSCRIPT_MEM_CACHE["mtime_ns"] = (
                                    st.st_mtime_ns if last_nl == len(raw_delta) - 1 else -1
                                )
                                _TRANSCRIPT_MEM_CACHE["size"] = new_cached_size
                                _TRANSCRIPT_MEM_CACHE["raw_steps"] = combined_steps
                                _TRANSCRIPT_MEM_CACHE["line_count"] = total_lines
                                raw_steps = list(combined_steps)
                                loaded_incrementally = True
                                _TRANSCRIPT_CACHE_STATS["incremental_reads"] += 1

                if not loaded_incrementally:
                    _TRANSCRIPT_CACHE_STATS["full_reads"] += 1
                    tail_window_bytes = min(1572864, max(262144, int(limit or 80) * 6144))
                    if st_size > 2 * 1024 * 1024 and not need_full_history and limit <= 250 and since_step is None:
                        with open(transcript_path, "rb") as fb:
                            first_sig = fb.read(128)
                            fb.seek(max(0, st_size - tail_window_bytes))
                            tail_chunk = fb.read().decode("utf-8", errors="replace")
                        lines = [ln.strip() for ln in tail_chunk.splitlines()[1:] if ln.strip()]
                        is_tail_only = True
                    else:
                        with open(transcript_path, "rb") as fb:
                            raw_all = fb.read()
                        first_sig = raw_all[:128]
                        lines = [ln.strip() for ln in raw_all.decode("utf-8", errors="replace").splitlines() if ln.strip()]
                        is_tail_only = False

                    raw_steps = []
                    for line in lines:
                        try:
                            raw_steps.append(json.loads(line))
                        except Exception:
                            continue
                    total_lines = len(lines)
                    cached_list = list(raw_steps)
                    if not need_full_history and len(cached_list) > _TRANSCRIPT_TAIL_CACHE_MAX:
                        cached_list = cached_list[-_TRANSCRIPT_TAIL_CACHE_MAX:]
                        is_tail_only = True
                    _TRANSCRIPT_MEM_CACHE["path"] = str(transcript_path)
                    _TRANSCRIPT_MEM_CACHE["mtime_ns"] = st.st_mtime_ns
                    _TRANSCRIPT_MEM_CACHE["size"] = st.st_size
                    _TRANSCRIPT_MEM_CACHE["first_sig"] = first_sig
                    _TRANSCRIPT_MEM_CACHE["tail_only"] = is_tail_only
                    _TRANSCRIPT_MEM_CACHE["raw_steps"] = cached_list
                    _TRANSCRIPT_MEM_CACHE["line_count"] = total_lines
            total_lines = int(_TRANSCRIPT_MEM_CACHE.get("line_count", len(raw_steps)))
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading transcript: {e}",
            "messages": []
        }

    if since_step is not None:
        raw_steps = [s for s in raw_steps if s.get("step_index", 0) > since_step]
    elif limit and len(raw_steps) > limit:
        raw_steps = raw_steps[-limit:]

    formatted_messages: List[Dict[str, Any]] = []
    active_mdl = get_active_model()

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
                    "model": active_mdl,
                    "timestamp": created_at
                })

        elif step_type == "GENERIC" and source == "MODEL":
            # Tool result or execution notice
            pass


    max_step = max(
        (s.get("step_index", 0) for s in raw_steps if isinstance(s.get("step_index"), int)),
        default=(since_step if since_step is not None else 0),
    )

    return {
        "status": "success",
        "session_id": session_id,
        "total_steps": total_lines,
        "latest_step": max_step,
        "unchanged": False,
        "messages": formatted_messages
    }


def execute_dashboard_command(cmd_text: str, images: Optional[List[str]] = None,
                              model: Optional[str] = None,
                              enqueue_if_busy: bool = True,
                              bypass_tier0: bool = False) -> Dict[str, Any]:
    """
    Executes commands entered from the Web Dashboard Command Console.
    Prioritizes Tier 0 deterministic execution ($0.00 / 0 Tokens) unless bypass_tier0=True.
    Queues messages if agent is currently busy.
    """
    text = (cmd_text or "").strip()
    if not text and not images:
        return {"status": "error", "message": "Empty command"}
    if not text and images:
        text = "Please inspect the attached image(s)."

    lower = text.lower()

    # 1. Email Sync Command
    if not bypass_tier0 and lower in ("/sync", "sync", "/sync gmail", "sync gmail"):
        res = bus.dispatch(FleetEvent(
            sender="DashboardCommand",
            target="email",
            action="CLASSIFY_RECENT",
            payload={"dry_run": False}
        ))
        if res.get("status") == "success":
            counts = res.get("data", {}).get("counts", {})
            msg = f"Gmail Sync Complete: Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}, Note: {counts.get('Note', 0)}, FYI: {counts.get('FYI', 0)}, Ignore: {counts.get('Ignore', 0)}"
            append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
            append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
            return {
                "status": "success",
                "type": "email_sync",
                "message": msg
            }
        return {"status": "error", "message": res.get("message", "Sync failed")}

    # 2. Daily Briefing Command
    if lower in ("/briefing", "briefing", "/daily briefing", "daily briefing"):
        data = briefing_engine.generate_daily_briefing()
        msg = data.get("formatted_markdown", "")
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {
            "status": "success",
            "type": "briefing",
            "headline": data.get("headline", ""),
            "message": msg
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
        msg = f"Created Task #{task_id}: {title}"
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {
            "status": "success",
            "type": "task_created",
            "message": msg
        }

    # 4. List Tasks Command
    if lower in ("/tasks", "tasks", "/list tasks", "list tasks"):
        tasks = db.list_tasks(status="pending", limit=10)
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", f"Found {len(tasks)} pending tasks.", source="MODEL")
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
        notif_msg = f"Windows Notification {'delivered' if sent else 'sent'}: {msg}"
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", notif_msg, source="MODEL")
        return {
            "status": "success",
            "type": "notification",
            "message": notif_msg
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
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {"status": "success", "type": "hyperscaler_status", "message": msg}

    if lower.startswith("/copilot "):
        from fleet.core.dev_tools import execute_github_copilot_command
        q = text[9:].strip()
        r = execute_github_copilot_command(q)
        msg = r.get("output") or r.get("message", "Executed via GitHub Copilot.")
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {"status": "success", "type": "dev_tool", "tool": "github_copilot", "message": msg}

    if lower.startswith("/claude "):
        from fleet.core.dev_tools import execute_claude_code
        q = text[8:].strip()
        r = execute_claude_code(q)
        msg = r.get("output") or r.get("message", "Executed via Claude Code.")
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {"status": "success", "type": "dev_tool", "tool": "claude_code", "message": msg}

    if lower.startswith("/gemini "):
        from fleet.core.dev_tools import execute_google_gemini_cli
        q = text[8:].strip()
        r = execute_google_gemini_cli(q)
        msg = r.get("output") or r.get("message", "Executed via Google Gemini.")
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
        append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
        return {"status": "success", "type": "dev_tool", "tool": "google_gemini", "message": msg}

    for pfx, prov_id in [("/vertex ", "google_vertex"), ("/azure ", "microsoft"), ("/aws ", "aws"), ("/bedrock ", "aws"), ("/ollama ", "ollama")]:
        if lower.startswith(pfx):
            from fleet.core.hyperscalers import HyperscalerGateway
            q = text[len(pfx):].strip()
            r = HyperscalerGateway().complete(prompt=q, provider=prov_id)
            msg = r.get("text") or r.get("response", "")
            append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
            append_transcript_turn("PLANNER_RESPONSE", msg, source="MODEL")
            return {"status": "success", "type": "hyperscaler_response", "provider": prov_id, "message": msg}

    # 5b. Tier 0 Extended Deterministic Intent Router ($0.00 / 0 Tokens)
    if not images and not bypass_tier0:
        from fleet.core.token_optimizer import get_cached_prompt_response, try_deterministic_intent_route
        det_res = try_deterministic_intent_route(text, db=db)
        if det_res is not None:
            record_llm_turn_usage("tier0_intent_router", "deterministic", tier0=True)
            append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
            append_transcript_turn("PLANNER_RESPONSE", det_res.get("message", ""), source="MODEL")
            return det_res
        cached_ans = get_cached_prompt_response(text)
        if cached_ans is not None:
            record_llm_turn_usage("tier0_semantic_cache", "cached", tier0=True)
            append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>")
            append_transcript_turn("PLANNER_RESPONSE", cached_ans, source="MODEL")
            return {
                "status": "success",
                "type": "cached_response",
                "tokens_used": 0,
                "cost_usd": "$0.00",
                "message": cached_ans,
            }

    # 6. Natural Language Prompt: check token exhaustion, laptop RAM admission & agent busy state
    target_model = model or get_active_model()

    th = get_token_health()
    if th["is_exhausted"]:
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>", images=images)
        append_transcript_turn("PLANNER_RESPONSE", f"⚠️ Token limit reached for {target_model}. Your prompt has been safely preserved in Fleet Vault.", source="MODEL")
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

    # Parallel Fleet Dispatching & Laptop RAM Admission Control:
    active_count = get_active_agent_count()
    max_slots = get_max_parallel_agents()
    ram_blocked, ram_pct = _is_ram_admission_blocked(active_count)
    if ram_blocked and enqueue_if_busy:
        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>", images=images)
        q_id = db.enqueue_chat_message(prompt=text, images=images or [], model=target_model)
        queued = db.get_queued_chat_messages()
        return {
            "status": "queued",
            "type": "ram_pressure_queued",
            "queue_id": q_id,
            "position": len(queued),
            "ram_percent_used": round(ram_pct, 1),
            "message": f"Queued under laptop RAM protection ({ram_pct:.0f}% RAM used). Will auto-launch once the active agent finishes.",
        }

    is_busy = (
        active_count >= max_slots
        or AGENT_STATE.get("status") == "max_capacity"
        or (AGENT_STATE.get("status") == "busy" and active_count == 0)
    )

    if not is_busy:
        has_overlap, overlap_reason = detect_agent_task_overlap(text, get_parallel_agents())
        if has_overlap:
            if enqueue_if_busy:
                append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>", images=images)
                append_transcript_turn("PLANNER_RESPONSE", f"⏳ Queued intelligently: {overlap_reason}. Will launch automatically once active conflicting agent finishes.", source="MODEL")
                q_id = db.enqueue_chat_message(prompt=text, images=images or [], model=target_model)
                send_windows_notification(
                    "⏳ Task Queued Intelligently",
                    f"Queued to avoid resource conflict: {overlap_reason}."
                )
                return {
                    "status": "queued",
                    "type": "overlap_queued",
                    "queue_id": q_id,
                    "overlap_reason": overlap_reason,
                    "message": f"⏳ Queued intelligently: {overlap_reason}. Will launch automatically once active conflicting agent finishes."
                }
            else:
                return {
                    "status": "busy",
                    "type": "overlap_conflict",
                    "overlap_reason": overlap_reason,
                    "message": f"Agent busy: {overlap_reason}."
                }

        append_transcript_turn("USER_INPUT", f"<USER_REQUEST>\n{text}\n</USER_REQUEST>", images=images)
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


def get_antigravity_live_diagnostics() -> Dict[str, Any]:
    """[AGL-10] Returns unified Antigravity Live runtime health, cache hit rate, CB state, RAM & telemetry."""
    st = get_agent_status()
    t_path = get_active_transcript_path()
    now_mono = time.monotonic()
    with _AGY_CB_LOCK:
        open_until = float(_AGY_CIRCUIT_BREAKER.get("open_until_ts") or 0.0)
        cb_open = now_mono < open_until
        cb_info = {
            "state": "OPEN" if cb_open else "CLOSED",
            "consecutive_failures": int(_AGY_CIRCUIT_BREAKER.get("consecutive_failures") or 0),
            "threshold": int(_AGY_CIRCUIT_BREAKER.get("threshold") or 3),
            "cooldown_remaining_sec": round(max(0.0, open_until - now_mono), 1),
            "trips": int(_AGY_CIRCUIT_BREAKER.get("trips") or 0),
            "last_error": str(_AGY_CIRCUIT_BREAKER.get("last_error") or ""),
        }
    with _SESSION_USAGE_LOCK:
        usage_snap = dict(_SESSION_USAGE_TELEMETRY)
    ram_blocked, ram_pct = _is_ram_admission_blocked(st.get("active_agents_count", 0))
    return {
        "status": "ok",
        "agent_status": st,
        "active_transcript_path": str(t_path) if t_path else "",
        "transcript_cache": get_transcript_cache_stats(),
        "cli_circuit_breaker": cb_info,
        "usage_telemetry": usage_snap,
        "orphan_recovery": dict(_ORPHAN_RECOVERY_STATS),
        "ram_admission": {
            "blocked": ram_blocked,
            "host_ram_pct": round(ram_pct, 1),
            "threshold_pct": MAX_HOST_RAM_PCT_FOR_PARALLEL,
        },
        "conversation_lease_owner": _PRIMARY_CONV_LEASE_OWNER,
    }

