"""
Developer Tools Integration Bridge for Personal Agentic Fleet.
Enables interoperability with state-of-the-art AI developer tools:
  1. GitHub Copilot (Microsoft) - Copilot CLI bridge (`gh copilot`) & `.github/copilot-instructions.md` sync
  2. Claude Code CLI (Anthropic) - Autonomous terminal coding assistant (`claude`) execution & fallback
  3. Google Antigravity CLI (Google) - IDE & CLI agent mirror
  4. Ollama CLI - Local offline inference
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from fleet.config import BASE_DIR, load_fleet_config

logger = logging.getLogger("fleet.core.dev_tools")


def detect_developer_tools() -> Dict[str, Dict[str, Any]]:
    """
    Detects installed AI developer CLI tools and environments on the host system.
    Returns status, path, and version info for:
      - antigravity (Google Antigravity CLI)
      - claude_code (Anthropic Claude Code CLI)
      - github_copilot (GitHub CLI + Copilot extension)
      - vscode (Visual Studio Code)
      - ollama (Local Ollama daemon)
    """
    user_home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")
    
    # 1. Google Antigravity
    agy_path = shutil.which("agy") or shutil.which("agy.exe")
    if not agy_path:
        candidate = user_home / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
        if candidate.is_file():
            agy_path = str(candidate)

    # 2. Claude Code CLI (@anthropic-ai/claude-code)
    claude_path = shutil.which("claude") or shutil.which("claude.cmd")
    if not claude_path:
        npm_global = user_home / "AppData" / "Roaming" / "npm" / ("claude.cmd" if os.name == "nt" else "claude")
        if npm_global.is_file():
            claude_path = str(npm_global)

    # 3. GitHub CLI & Copilot extension
    gh_path = shutil.which("gh") or shutil.which("gh.exe")
    has_copilot_ext = False
    if gh_path:
        try:
            res = subprocess.run([gh_path, "copilot", "--version"], capture_output=True, text=True, timeout=3)
            has_copilot_ext = (res.returncode == 0)
        except Exception:
            pass

    # 4. VS Code
    code_path = shutil.which("code") or shutil.which("code.cmd")
    if not code_path:
        candidate_code = user_home / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "bin" / ("code.cmd" if os.name == "nt" else "code")
        if candidate_code.is_file():
            code_path = str(candidate_code)

    # 5. Ollama
    ollama_path = shutil.which("ollama") or shutil.which("ollama.exe")
    if not ollama_path:
        candidate_ollama = user_home / "AppData" / "Local" / "Programs" / "Ollama" / ("ollama.exe" if os.name == "nt" else "ollama")
        if candidate_ollama.is_file():
            ollama_path = str(candidate_ollama)

    return {
        "antigravity": {
            "name": "Google Antigravity CLI",
            "provider": "Google",
            "installed": bool(agy_path),
            "path": agy_path,
            "category": "agent_cli",
            "capabilities": ["multi_agent", "code_generation", "workspace_sync"]
        },
        "claude_code": {
            "name": "Claude Code CLI",
            "provider": "Anthropic",
            "installed": bool(claude_path),
            "path": claude_path,
            "category": "developer_tool",
            "capabilities": ["terminal_coding", "git_operations", "code_editing"]
        },
        "github_copilot": {
            "name": "GitHub Copilot (CLI & IDE)",
            "provider": "Microsoft / GitHub",
            "installed": bool(gh_path),
            "has_copilot_cli": has_copilot_ext,
            "path": gh_path,
            "category": "developer_tool",
            "capabilities": ["code_completion", "shell_suggestion", "pr_explanation"]
        },
        "vscode": {
            "name": "Visual Studio Code",
            "provider": "Microsoft",
            "installed": bool(code_path),
            "path": code_path,
            "category": "editor",
            "capabilities": ["copilot_chat", "ide_workspace"]
        },
        "ollama": {
            "name": "Ollama Local Engine",
            "provider": "Local / Open Source",
            "installed": bool(ollama_path),
            "path": ollama_path,
            "category": "local_llm",
            "capabilities": ["offline_inference", "zero_token_cost", "privacy_vault"]
        }
    }


def execute_claude_code(
    prompt: str,
    cwd: Optional[str] = None,
    dangerously_skip_permissions: bool = True
) -> Dict[str, Any]:
    """
    Executes a task via Anthropic's Claude Code CLI tool.
    Falls back gracefully to Anthropic Direct API if the CLI is not installed.
    """
    tools = detect_developer_tools()
    claude_info = tools["claude_code"]
    
    if claude_info["installed"] and claude_info["path"]:
        cmd = [claude_info["path"], "-p", prompt]
        if dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")
            
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or str(BASE_DIR.parent),
                timeout=120
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "claude_code",
                "provider": "anthropic",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "tool": "claude_code", "message": "Claude Code task timed out after 120s"}
        except Exception as e:
            return {"status": "error", "tool": "claude_code", "message": str(e)}

    # Fallback to Anthropic Claude Direct API via HyperscalerGateway
    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    llm_res = gateway.complete(prompt=prompt, provider="anthropic", model="claude-3-5-sonnet-20241022")
    return {
        "status": "success" if llm_res.get("response") else "error",
        "tool": "claude_code_api_fallback",
        "provider": "anthropic",
        "output": llm_res.get("response", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00")
    }


def execute_github_copilot_command(
    prompt: str,
    command_type: str = "suggest"
) -> Dict[str, Any]:
    """
    Executes a shell suggestion or explanation query using GitHub Copilot CLI (`gh copilot`).
    Falls back to Microsoft Azure OpenAI if GitHub CLI is unavailable.
    """
    tools = detect_developer_tools()
    gh_info = tools["github_copilot"]
    
    if gh_info["installed"] and gh_info["has_copilot_cli"] and gh_info["path"]:
        subcmd = "suggest" if command_type == "suggest" else "explain"
        cmd = [gh_info["path"], "copilot", subcmd, prompt]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "github_copilot_cli",
                "provider": "microsoft",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode
            }
        except Exception as e:
            return {"status": "error", "tool": "github_copilot_cli", "message": str(e)}

    # Fallback to Azure OpenAI GPT-4o via HyperscalerGateway
    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    sys_inst = "You are GitHub Copilot assisting with CLI shell commands and code solutions."
    llm_res = gateway.complete(prompt=prompt, provider="microsoft", model="gpt-4o-mini", system_instruction=sys_inst)
    return {
        "status": "success" if llm_res.get("response") else "error",
        "tool": "github_copilot_azure_fallback",
        "provider": "microsoft",
        "output": llm_res.get("response", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00")
    }


def sync_github_copilot_instructions(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generates and syncs `.github/copilot-instructions.md` with Fleet's architectural rules,
    Tier 0 token conservation mandates, and code style guidelines so GitHub Copilot
    in VS Code is automatically context-aware.
    """
    root = repo_root or BASE_DIR.parent
    copilot_file = root / ".github" / "copilot-instructions.md"
    copilot_file.parent.mkdir(parents=True, exist_ok=True)
    
    content = """# GitHub Copilot & AI Instructions for Personal Agentic Fleet

You are assisting with the **Personal Agentic Fleet** codebase. Always follow these core architectural rules:

## 1. Fleet Rule 1: Tier 0 Cost & Token Governance (0 Tokens / $0.00 Default)
- Personal Agentic Fleet is architected to operate at Tier 0 whenever possible.
- Never make outbound external LLM API calls when deterministic regex, local SQLite lookups, or local BM25 RAG can solve the user's intent.
- Preserve SHA-256 caching and prompt compression (`fleet/core/token_optimizer.py`).

## 2. Multi-Hyperscaler Architecture
- The fleet works with multiple hyperscalers and models:
  - **Google**: Google Antigravity CLI (`agy`), Google Gemini API (`generativelanguage.googleapis.com`), and Google Cloud Vertex AI.
  - **Microsoft**: Azure OpenAI Service (GPT-4o, GPT-4o-mini), Azure AI Foundry (Phi-3.5/Phi-4), and GitHub Copilot.
  - **Amazon Web Services (AWS)**: Amazon Bedrock (Claude 3.5 Sonnet, Amazon Titan, Meta Llama 3) and SageMaker.
  - **Anthropic Claude**: Claude Code CLI (`claude`), Claude Direct API (Claude 3.7 Sonnet, Claude 3.5 Haiku, Claude 3 Opus).
  - **Offline / Local**: Ollama / vLLM (Llama 3, Mistral, Qwen).
- Always use the unified gateway `HyperscalerGateway` in `fleet/core/hyperscalers.py` rather than hardcoding vendor SDKs.

## 3. Platform & Security Rules
- All code must run natively on both **Windows 10/11** and **Linux/Ubuntu**.
- Zero external socket calls during tests (enforced by `conftest.py` socket guard).
- Never commit raw API keys or PII: use `get_secure_secret()` or Windows DPAPI vault.
- Maintain 100/100 score on the Fleet 12-layer security scanner (`fleet.tools.security_scanner`).
"""
    copilot_file.write_text(content.strip() + "\n", encoding="utf-8")
    return {
        "status": "synced",
        "path": str(copilot_file),
        "size_bytes": len(content.encode("utf-8")),
        "message": "Successfully synchronized .github/copilot-instructions.md for GitHub Copilot."
    }
