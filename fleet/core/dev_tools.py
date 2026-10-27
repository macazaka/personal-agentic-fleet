import re
"""
Developer Tools Integration Bridge for Personal Agentic Fleet.
Enables seamless interoperability with state-of-the-art AI developer tools across all hyperscalers:
  1. GitHub Copilot (Microsoft / GitHub) - Copilot CLI bridge (`gh copilot`) & `.github/copilot-instructions.md` sync
  2. Claude Code CLI (Anthropic) - Autonomous terminal coding assistant (`claude`) execution & `CLAUDE.md` sync
  3. Google Antigravity CLI (`agy`) & Google Gemini CLI (`gemini` / `gcloud`) - Multi-agent IDE & CLI mirror & `GEMINI.md` sync
  4. Amazon Q Developer CLI (`q` / `aws`) - AWS terminal coding assistant & Bedrock fallback
  5. Cursor / VS Code / Aider & Local Ollama CLI
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
    Returns status, path, and capabilities for:
      - antigravity (Google Antigravity CLI)
      - gemini_cli (Google Gemini CLI / Cloud SDK)
      - claude_code (Anthropic Claude Code CLI)
      - github_copilot (GitHub CLI + Copilot extension)
      - aws_q (Amazon Q Developer CLI / AWS CLI)
      - vscode (Visual Studio Code)
      - cursor (Cursor AI IDE)
      - ollama (Local Ollama daemon)
    """
    user_home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")

    # 1. Google Antigravity CLI
    agy_path = shutil.which("agy") or shutil.which("agy.exe")
    if not agy_path:
        for c in [
            user_home / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy"),
            Path("/opt/homebrew/bin/agy"),
            Path("/usr/local/bin/agy"),
        ]:
            if c.is_file():
                agy_path = str(c)
                break

    # 2. Google Gemini CLI / Google Cloud SDK
    gemini_path = (
        shutil.which("gemini")
        or shutil.which("gemini.cmd")
        or shutil.which("gcloud")
        or shutil.which("gcloud.cmd")
    )
    if not gemini_path:
        for c in [
            user_home / "AppData" / "Roaming" / "npm" / ("gemini.cmd" if os.name == "nt" else "gemini"),
            Path("/opt/homebrew/bin/gemini"),
            Path("/usr/local/bin/gemini"),
        ]:
            if c.is_file():
                gemini_path = str(c)
                break

    # 3. Anthropic Claude Code CLI (@anthropic-ai/claude-code)
    claude_path = shutil.which("claude") or shutil.which("claude.cmd")
    if not claude_path:
        for c in [
            user_home / "AppData" / "Roaming" / "npm" / ("claude.cmd" if os.name == "nt" else "claude"),
            Path("/opt/homebrew/bin/claude"),
            Path("/usr/local/bin/claude"),
        ]:
            if c.is_file():
                claude_path = str(c)
                break

    # 4. GitHub CLI & Copilot extension
    gh_path = shutil.which("gh") or shutil.which("gh.exe")
    if not gh_path:
        for c in [Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")]:
            if c.is_file():
                gh_path = str(c)
                break
    has_copilot_ext = False
    if gh_path and os.environ.get("FLEET_TEST_MODE") != "1":
        try:
            res = subprocess.run([gh_path, "copilot", "--version"], capture_output=True, text=True, timeout=3)
            has_copilot_ext = (res.returncode == 0)
        except Exception:
            pass

    # 5. Amazon Q Developer CLI / AWS CLI
    aws_q_path = shutil.which("q") or shutil.which("aws") or shutil.which("aws.exe")
    if not aws_q_path:
        for c in [
            Path("/opt/homebrew/bin/q"),
            Path("/opt/homebrew/bin/aws"),
            Path("/usr/local/bin/q"),
            Path("/usr/local/bin/aws"),
        ]:
            if c.is_file():
                aws_q_path = str(c)
                break

    # 6. VS Code
    code_path = shutil.which("code") or shutil.which("code.cmd")
    if not code_path:
        for c in [
            user_home / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "bin" / ("code.cmd" if os.name == "nt" else "code"),
            Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
            Path("/opt/homebrew/bin/code"),
            Path("/usr/local/bin/code"),
        ]:
            if c.is_file():
                code_path = str(c)
                break

    # 7. Cursor AI Editor
    cursor_path = shutil.which("cursor") or shutil.which("cursor.cmd")
    if not cursor_path:
        for c in [
            user_home / "AppData" / "Local" / "Programs" / "cursor" / "resources" / "app" / "bin" / ("cursor.cmd" if os.name == "nt" else "cursor"),
            Path("/Applications/Cursor.app/Contents/Resources/app/bin/cursor"),
        ]:
            if c.is_file():
                cursor_path = str(c)
                break

    # 8. Ollama Local Engine
    ollama_path = shutil.which("ollama") or shutil.which("ollama.exe")
    if not ollama_path:
        for c in [
            user_home / "AppData" / "Local" / "Programs" / "Ollama" / ("ollama.exe" if os.name == "nt" else "ollama"),
            Path("/usr/local/bin/ollama"),
            Path("/opt/homebrew/bin/ollama"),
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
        ]:
            if c.is_file():
                ollama_path = str(c)
                break

    return {
        "antigravity": {
            "name": "Google Antigravity CLI",
            "provider": "Google",
            "installed": bool(agy_path),
            "path": agy_path,
            "category": "agent_cli",
            "capabilities": ["multi_agent", "code_generation", "workspace_sync"],
        },
        "gemini_cli": {
            "name": "Google Gemini CLI & Cloud SDK",
            "provider": "Google Cloud",
            "installed": bool(gemini_path),
            "path": gemini_path,
            "category": "developer_tool",
            "capabilities": ["vertex_ai", "gemini_api", "cloud_deploy"],
        },
        "claude_code": {
            "name": "Claude Code CLI",
            "provider": "Anthropic",
            "installed": bool(claude_path),
            "path": claude_path,
            "category": "developer_tool",
            "capabilities": ["terminal_coding", "git_operations", "code_editing"],
        },
        "github_copilot": {
            "name": "GitHub Copilot (CLI & IDE)",
            "provider": "Microsoft / GitHub",
            "installed": bool(gh_path),
            "has_copilot_cli": has_copilot_ext,
            "path": gh_path,
            "category": "developer_tool",
            "capabilities": ["code_completion", "shell_suggestion", "pr_explanation"],
        },
        "aws_q": {
            "name": "Amazon Q Developer & AWS CLI",
            "provider": "Amazon Web Services",
            "installed": bool(aws_q_path),
            "path": aws_q_path,
            "category": "developer_tool",
            "capabilities": ["aws_bedrock", "cloud_architecture", "iam_security"],
        },
        "vscode": {
            "name": "Visual Studio Code",
            "provider": "Microsoft",
            "installed": bool(code_path),
            "path": code_path,
            "category": "editor",
            "capabilities": ["copilot_chat", "ide_workspace"],
        },
        "cursor": {
            "name": "Cursor AI Code Editor",
            "provider": "Cursor / Multi-LLM",
            "installed": bool(cursor_path),
            "path": cursor_path,
            "category": "editor",
            "capabilities": ["composer", "multi_file_edit", "mcp_client"],
        },
        "ollama": {
            "name": "Ollama Local Engine",
            "provider": "Local / Open Source",
            "installed": bool(ollama_path),
            "path": ollama_path,
            "category": "local_llm",
            "capabilities": ["offline_inference", "zero_token_cost", "privacy_vault"],
        },
    }


def _sanitize_cli_prompt(prompt: str) -> str:
    """Sanitizes prompt to prevent command line argument and flag injection (CWE-078)."""
    if not isinstance(prompt, str):
        return ""
    # Strip non-printable/control characters and shell metacharacters
    clean = re.sub(r"[\x00-\x1f\x7f-\x9f;&|><`$\\]", " ", prompt).strip()
    while clean.startswith("-"):
        clean = clean.lstrip("-").strip()
    return clean[:4096]


def execute_claude_code(
    prompt: str,
    cwd: Optional[str] = None,
    dangerously_skip_permissions: bool = True,
) -> Dict[str, Any]:
    """
    Executes a task via Anthropic's Claude Code CLI tool (`claude -p`).
    Falls back gracefully to Anthropic Direct API via HyperscalerGateway if the CLI is not installed.
    """
    safe_prompt = _sanitize_cli_prompt(prompt)
    if not safe_prompt:
        return {"status": "error", "tool": "claude_code", "message": "Invalid or empty prompt"}

    tools = detect_developer_tools()
    claude_info = tools.get("claude_code", {})

    if claude_info.get("installed") and claude_info.get("path"):
        exec_path = str(claude_info["path"])
        cmd = [exec_path, "-p"]
        if dangerously_skip_permissions:
            cmd.insert(1, "--dangerously-skip-permissions")

        try:
            res = subprocess.run(
                cmd,
                input=safe_prompt,
                capture_output=True,
                text=True,
                shell=False,
                cwd=str(BASE_DIR.parent),
                timeout=120,
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "claude_code",
                "provider": "anthropic",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "tool": "claude_code", "message": "Claude Code task timed out after 120s"}
        except Exception as e:
            return {"status": "error", "tool": "claude_code", "message": str(e)}

    # Fallback to Anthropic Claude Direct API via HyperscalerGateway
    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    llm_res = gateway.complete(prompt=safe_prompt, provider="anthropic", model="claude-3-5-sonnet-20241022")
    return {
        "status": "success" if (llm_res.get("response") or llm_res.get("text")) else "error",
        "tool": "claude_code_api_fallback",
        "provider": "anthropic",
        "output": llm_res.get("response") or llm_res.get("text", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00"),
    }


def execute_github_copilot_command(
    prompt: str,
    command_type: str = "suggest",
) -> Dict[str, Any]:
    """
    Executes a shell suggestion or explanation query using GitHub Copilot CLI (`gh copilot`).
    Falls back to Microsoft Azure OpenAI / GitHub Models via HyperscalerGateway if GitHub CLI is unavailable.
    """
    safe_prompt = _sanitize_cli_prompt(prompt)
    if not safe_prompt:
        return {"status": "error", "tool": "github_copilot_cli", "message": "Invalid or empty prompt"}

    tools = detect_developer_tools()
    gh_info = tools.get("github_copilot", {})

    if gh_info.get("installed") and gh_info.get("has_copilot_cli") and gh_info.get("path"):
        exec_path = str(gh_info["path"])
        subcmd = "suggest" if command_type == "suggest" else "explain"
        cmd = [exec_path, "copilot", subcmd]
        try:
            res = subprocess.run(
                cmd,
                input=safe_prompt,
                capture_output=True,
                text=True,
                shell=False,
                timeout=30,
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "github_copilot_cli",
                "provider": "microsoft",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode,
            }
        except Exception as e:
            return {"status": "error", "tool": "github_copilot_cli", "message": str(e)}

    # Fallback to Azure OpenAI / GitHub Models via HyperscalerGateway
    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    sys_inst = "You are GitHub Copilot assisting with CLI shell commands and code solutions."
    llm_res = gateway.complete(prompt=safe_prompt, provider="microsoft", model="gpt-4o-mini", system_instruction=sys_inst)
    return {
        "status": "success" if (llm_res.get("response") or llm_res.get("text")) else "error",
        "tool": "github_copilot_azure_fallback",
        "provider": "microsoft",
        "output": llm_res.get("response") or llm_res.get("text", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00"),
    }


def execute_google_gemini_cli(
    prompt: str,
    model: str = "gemini-2.5-pro",
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a task via Google Gemini CLI (`gemini -p`) or falls back to
    Google Gemini REST API / Google Cloud Vertex AI via HyperscalerGateway.
    """
    safe_prompt = _sanitize_cli_prompt(prompt)
    if not safe_prompt:
        return {"status": "error", "tool": "google_gemini_cli", "message": "Invalid or empty prompt"}

    tools = detect_developer_tools()
    gem_info = tools.get("gemini_cli", {})
    gem_path = gem_info.get("path") or ""

    if gem_info.get("installed") and gem_path and "gemini" in Path(gem_path).name.lower():
        exec_path = str(gem_path)
        cmd = [exec_path, "-p"]
        try:
            res = subprocess.run(
                cmd,
                input=safe_prompt,
                capture_output=True,
                text=True,
                shell=False,
                cwd=str(BASE_DIR.parent),
                timeout=90,
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "google_gemini_cli",
                "provider": "google",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode,
            }
        except Exception as e:
            return {"status": "error", "tool": "google_gemini_cli", "message": str(e)}

    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    llm_res = gateway.complete(prompt=safe_prompt, provider="google", model=model)
    return {
        "status": "success" if (llm_res.get("response") or llm_res.get("text")) else "error",
        "tool": "google_gemini_api_fallback",
        "provider": "google",
        "output": llm_res.get("response") or llm_res.get("text", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00"),
    }


def execute_aws_q_developer(
    prompt: str,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a task via Amazon Q Developer CLI (`q chat`) or falls back to
    Amazon Bedrock (Claude / Nova / Titan) via HyperscalerGateway.
    """
    safe_prompt = _sanitize_cli_prompt(prompt)
    if not safe_prompt:
        return {"status": "error", "tool": "aws_q_developer_cli", "message": "Invalid or empty prompt"}

    tools = detect_developer_tools()
    q_info = tools.get("aws_q", {})
    q_path = q_info.get("path") or ""

    if q_info.get("installed") and q_path and Path(q_path).stem.lower() == "q":
        exec_path = str(q_path)
        cmd = [exec_path, "chat", "--no-interactive"]
        try:
            res = subprocess.run(
                cmd,
                input=safe_prompt,
                capture_output=True,
                text=True,
                shell=False,
                cwd=str(BASE_DIR.parent),
                timeout=90,
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "tool": "aws_q_developer_cli",
                "provider": "aws",
                "output": res.stdout,
                "error": res.stderr if res.returncode != 0 else "",
                "exit_code": res.returncode,
            }
        except Exception as e:
            return {"status": "error", "tool": "aws_q_developer_cli", "message": str(e)}

    from fleet.core.hyperscalers import HyperscalerGateway
    gateway = HyperscalerGateway()
    sys_inst = "You are Amazon Q Developer assisting with AWS architecture, Bedrock, and software engineering."
    llm_res = gateway.complete(prompt=prompt, provider="aws", system_instruction=sys_inst)
    return {
        "status": "success" if (llm_res.get("response") or llm_res.get("text")) else "error",
        "tool": "aws_bedrock_fallback",
        "provider": "aws",
        "output": llm_res.get("response") or llm_res.get("text", ""),
        "tokens_used": llm_res.get("tokens_used", 0),
        "cost_usd": llm_res.get("cost_usd", "$0.00"),
    }


_SHARED_ARCHITECTURAL_RULES = """## 1. Fleet Rule 1: Tier 0 Cost & Token Governance (0 Tokens / $0.00 Default)
- Personal Agentic Fleet is architected to operate at Tier 0 whenever possible.
- Never make outbound external LLM API calls when deterministic regex, local SQLite lookups, or local BM25 RAG can solve the user's intent.
- Preserve SHA-256 caching and prompt compression (`fleet/core/token_optimizer.py`).

## 2. Multi-Hyperscaler & Developer Tool Architecture
- The fleet works seamlessly across all major hyperscalers and AI developer tools:
  - **Google**: Google Antigravity CLI (`agy`), Google Gemini REST API (`generativelanguage.googleapis.com`), Google Cloud Vertex AI (`aiplatform.googleapis.com`), and Google Gemini CLI (`gemini`).
  - **Microsoft & GitHub**: Azure OpenAI Service (GPT-4o, GPT-4o-mini, o1, o3-mini), Azure AI Foundry (Phi-4, DeepSeek-R1), GitHub Models (`models.inference.ai.azure.com`), and GitHub Copilot (`gh copilot` & VS Code).
  - **Amazon Web Services (AWS)**: Amazon Bedrock Runtime with pure-stdlib SigV4 IAM & Bearer auth (Claude 3.7/3.5 Sonnet, Amazon Nova Pro, Amazon Titan, Meta Llama 3.3) and Amazon Q Developer CLI (`q`).
  - **Anthropic Claude**: Claude Code CLI (`claude`), Anthropic Direct Messages API (Claude 3.7 Sonnet, Claude 3.5 Sonnet/Haiku, Claude 3 Opus).
  - **Offline / Local**: Ollama / vLLM (Llama 3.2, Qwen 2.5 Coder, DeepSeek-R1, Mistral).
- Always route LLM completions through `HyperscalerGateway` in `fleet/core/hyperscalers.py` and developer tool invocations through `fleet/core/dev_tools.py`.

## 3. Platform & Security Rules
- All code must run natively on both **Windows 10/11** and **Linux/Ubuntu** (Python 3.10–3.14).
- Zero external socket calls during unit tests (enforced by `conftest.py` socket guard).
- Never commit raw API keys or PII: use `get_secure_secret()` or the Windows DPAPI vault (`fleet/core/crypto_vault.py`).
- Maintain a 100/100 score on the Fleet 12-layer security scanner (`python -m fleet.tools.preflight_gate`).
"""


def sync_github_copilot_instructions(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generates and syncs `.github/copilot-instructions.md` with Fleet's architectural rules,
    Tier 0 token conservation mandates, and code style guidelines so GitHub Copilot
    in VS Code and GitHub CLI is automatically context-aware.
    """
    root = repo_root or BASE_DIR.parent
    copilot_file = root / ".github" / "copilot-instructions.md"
    copilot_file.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "# GitHub Copilot & AI Instructions for Personal Agentic Fleet\n\n"
        "You are assisting with the **Personal Agentic Fleet** codebase. Always follow these core architectural rules:\n\n"
        + _SHARED_ARCHITECTURAL_RULES
    )
    copilot_file.write_text(content.strip() + "\n", encoding="utf-8")
    return {
        "status": "synced",
        "path": str(copilot_file),
        "size_bytes": len(content.encode("utf-8")),
        "message": "Successfully synchronized .github/copilot-instructions.md for GitHub Copilot.",
    }


def sync_claude_code_instructions(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generates and syncs `CLAUDE.md` in the repository root so Anthropic's Claude Code CLI (`claude`)
    automatically loads Fleet's test commands, Tier 0 governance, and multi-hyperscaler rules.
    """
    root = repo_root or BASE_DIR.parent
    claude_file = root / "CLAUDE.md"

    content = (
        "# CLAUDE.md — Anthropic Claude Code Guide for Personal Agentic Fleet\n\n"
        "## Quick Verification Commands\n"
        "- Full Preflight Gate (Doctor + 12-Layer Security + 126 Unit Tests): `python -m fleet.tools.preflight_gate`\n"
        "- Fast Unit Test Suite: `python -m pytest tests/ -q --tb=short`\n"
        "- Security Audit Only: `python -m fleet.security_scanner`\n\n"
        + _SHARED_ARCHITECTURAL_RULES
    )
    claude_file.write_text(content.strip() + "\n", encoding="utf-8")
    return {
        "status": "synced",
        "path": str(claude_file),
        "size_bytes": len(content.encode("utf-8")),
        "message": "Successfully synchronized CLAUDE.md for Anthropic Claude Code.",
    }


def sync_gemini_instructions(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generates and syncs `GEMINI.md` in the repository root for Google Gemini CLI and Google Cloud Code / Antigravity.
    """
    root = repo_root or BASE_DIR.parent
    gemini_file = root / "GEMINI.md"

    content = (
        "# GEMINI.md — Google Gemini CLI & Vertex AI Guide for Personal Agentic Fleet\n\n"
        "You are operating inside the **Personal Agentic Fleet** workspace.\n\n"
        + _SHARED_ARCHITECTURAL_RULES
    )
    gemini_file.write_text(content.strip() + "\n", encoding="utf-8")
    return {
        "status": "synced",
        "path": str(gemini_file),
        "size_bytes": len(content.encode("utf-8")),
        "message": "Successfully synchronized GEMINI.md for Google Gemini CLI & Antigravity.",
    }


def sync_all_developer_tool_instructions(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Synchronizes instruction files for all major AI developer tools in one operation:
      - `.github/copilot-instructions.md` (GitHub Copilot)
      - `CLAUDE.md` (Anthropic Claude Code)
      - `GEMINI.md` (Google Gemini CLI & Antigravity)
    """
    r1 = sync_github_copilot_instructions(repo_root=repo_root)
    r2 = sync_claude_code_instructions(repo_root=repo_root)
    r3 = sync_gemini_instructions(repo_root=repo_root)
    return {
        "status": "synced",
        "synced_files": [r1["path"], r2["path"], r3["path"]],
        "message": "Synchronized .github/copilot-instructions.md, CLAUDE.md, and GEMINI.md across workspace.",
    }
