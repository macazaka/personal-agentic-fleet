"""
API Endpoints for Multi-Hyperscaler Providers & Developer Tools.
Supports:
  - Google (Gemini AI Studio REST, Google Cloud Vertex AI, Google Gemini CLI, Google Antigravity)
  - Microsoft (Azure OpenAI, Azure AI Foundry, GitHub Models, GitHub Copilot)
  - AWS (Amazon Bedrock SigV4 / Bearer, Nova, Titan, Claude on Bedrock, Amazon Q Developer CLI)
  - Anthropic (Claude Code CLI, Claude Direct Messages API)
  - OpenAI Direct & Local Ollama Offline Engines
"""

import json
import logging
from typing import Any, Dict
import urllib.parse

from fleet.api.router import router
from fleet.core.crypto_vault import set_secure_secret
from fleet.core.dev_tools import (
    detect_developer_tools,
    execute_aws_q_developer,
    execute_claude_code,
    execute_github_copilot_command,
    execute_google_gemini_cli,
    sync_all_developer_tool_instructions,
    sync_claude_code_instructions,
    sync_gemini_instructions,
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
        "count": len(providers),
    })


@router.get("/api/hyperscalers/dev_tools")
def get_developer_tools_status(handler: Any, parsed_url: urllib.parse.ParseResult):
    """Returns detection status for GitHub Copilot, Claude Code, Antigravity, Gemini CLI, Amazon Q, Cursor, VS Code, and Ollama."""
    tools = detect_developer_tools()
    handler._send_json({
        "status": "success",
        "tools": tools,
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
        system_instruction=sys_inst,
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
    """Executes a command via GitHub Copilot CLI with Azure OpenAI / GitHub Models fallback."""
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    cmd_type = body.get("type", "suggest")
    res = execute_github_copilot_command(prompt=prompt, command_type=cmd_type)
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/gemini_cli")
def post_execute_gemini_cli(handler: Any, body: Dict[str, Any]):
    """Executes a command via Google Gemini CLI with Gemini REST / Vertex AI fallback."""
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    model = body.get("model", "gemini-2.5-pro")
    res = execute_google_gemini_cli(prompt=prompt, model=model)
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/aws_q")
def post_execute_aws_q(handler: Any, body: Dict[str, Any]):
    """Executes a command via Amazon Q Developer CLI with AWS Bedrock fallback."""
    prompt = body.get("prompt", "")
    if not prompt:
        handler._send_json({"status": "error", "message": "Missing prompt"}, 400)
        return

    res = execute_aws_q_developer(prompt=prompt)
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/sync_copilot_instructions")
def post_sync_copilot_instructions(handler: Any, body: Dict[str, Any]):
    """Syncs .github/copilot-instructions.md for VS Code & Copilot alignment."""
    res = sync_github_copilot_instructions()
    handler._send_json(res)


@router.post("/api/hyperscalers/dev_tools/sync_all_instructions")
def post_sync_all_instructions(handler: Any, body: Dict[str, Any]):
    """Syncs .github/copilot-instructions.md, CLAUDE.md, and GEMINI.md across workspace."""
    res = sync_all_developer_tool_instructions()
    handler._send_json(res)


@router.post("/api/hyperscalers/configure_key")
def post_configure_hyperscaler_key(handler: Any, body: Dict[str, Any]):
    """Stores an API key or endpoint in Windows Credential Manager (DPAPI keyring) and runtime environment."""
    key_name = (body.get("key_name") or "").strip()
    secret_val = (body.get("secret_value") or "").strip()
    allowed_keys = {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "VERTEX_AI_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_AI_FOUNDRY_KEY",
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "GITHUB_TOKEN",
        "AWS_BEARER_TOKEN",
        "AWS_BEDROCK_ENDPOINT",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    }
    if key_name not in allowed_keys or not secret_val:
        handler._send_json({"status": "error", "message": f"Invalid key_name '{key_name}' or empty value"}, 400)
        return

    stored_dpapi = set_secure_secret(key_name, secret_val)
    handler._send_json({
        "status": "success",
        "key_name": key_name,
        "stored_in_dpapi_keyring": stored_dpapi,
        "message": f"Configured {key_name} in Fleet secure vault.",
    })
