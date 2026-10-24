"""
API Endpoints for Multi-Hyperscaler Providers & Developer Tools.
Supports:
  - Google (Gemini, Vertex AI, Antigravity)
  - Microsoft (Azure OpenAI, Azure AI Foundry, GitHub Copilot)
  - AWS (Amazon Bedrock, Titan, Claude on Bedrock)
  - Anthropic (Claude Code CLI, Claude Direct API)
  - Local Ollama & Offline Engines
"""

import json
import logging
from typing import Any, Dict
import urllib.parse

from fleet.api.router import router
from fleet.core.dev_tools import (
    detect_developer_tools,
    execute_claude_code,
    execute_github_copilot_command,
    sync_github_copilot_instructions,
)
from fleet.core.hyperscalers import HyperscalerGateway, SUPPORTED_PROVIDERS

logger = logging.getLogger("fleet.api.hyperscalers")


@router.get("/api/hyperscalers/providers")
def get_hyperscaler_providers(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns list of supported hyperscalers and their configured models."""
    gateway = HyperscalerGateway()
    providers = gateway.list_available_providers()
    handler._send_json({
        "status": "success",
        "providers": providers,
        "count": len(providers)
    })


@router.get("/api/hyperscalers/dev_tools")
def get_developer_tools_status(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns detection status for GitHub Copilot, Claude Code, Antigravity, and VS Code."""
    tools = detect_developer_tools()
    handler._send_json({
        "status": "success",
        "tools": tools
    })


@router.post("/api/hyperscalers/generate")
def post_hyperscaler_generate(handler: Any, body: Dict[str, Any]):
    """
    Executes a completion request through the unified HyperscalerGateway.
    Checks Tier 0 intent routing and local RAG before dispatching to the selected hyperscaler.
    """
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    provider = body.get("provider")
    model = body.get("model")
    sys_inst = body.get("system_instruction", "")

    gateway = HyperscalerGateway()
    result = gateway.complete(
        prompt=prompt,
        provider=provider,
        model=model,
        system_instruction=sys_inst
    )
    handler._send_json(result)


@router.post("/api/hyperscalers/dev_tools/claude_code")
def post_execute_claude_code(handler: Any, body: Dict[str, Any]):
    """Executes a command via Claude Code CLI with Anthropic Direct fallback."""
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    cwd = body.get("cwd")
    res = execute_claude_code(prompt=prompt, cwd=cwd)
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/copilot")
def post_execute_copilot(handler: Any, body: Dict[str, Any]):
    """Executes a command via GitHub Copilot CLI with Azure OpenAI fallback."""
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    cmd_type = body.get("type", "suggest")
    res = execute_github_copilot_command(prompt=prompt, command_type=cmd_type)
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/sync_copilot_instructions")
def post_sync_copilot_instructions(handler: Any, body: Dict[str, Any]):
    """Syncs .github/copilot-instructions.md for VS Code & Copilot alignment."""
    res = sync_github_copilot_instructions()
    handler._send_json(res)
