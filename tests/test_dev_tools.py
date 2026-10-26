"""
Unit tests for Developer Tools integration (GitHub Copilot, Claude Code, Google Gemini CLI, Amazon Q, Antigravity, Cursor, Ollama).
"""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

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


def test_detect_developer_tools():
    tools = detect_developer_tools()
    assert "antigravity" in tools
    assert "gemini_cli" in tools
    assert "claude_code" in tools
    assert "github_copilot" in tools
    assert "aws_q" in tools
    assert "vscode" in tools
    assert "cursor" in tools
    assert "ollama" in tools

    assert tools["claude_code"]["provider"] == "Anthropic"
    assert tools["github_copilot"]["provider"] == "Microsoft / GitHub"
    assert tools["antigravity"]["provider"] == "Google"
    assert tools["gemini_cli"]["provider"] == "Google Cloud"
    assert tools["aws_q"]["provider"] == "Amazon Web Services"
    assert tools["ollama"]["provider"] == "Local / Open Source"


def test_execute_claude_code_cli_success():
    mock_run_res = MagicMock(returncode=0, stdout="Claude Code completed successfully", stderr="")
    with patch("fleet.core.dev_tools.detect_developer_tools") as mock_detect:
        mock_detect.return_value = {
            "claude_code": {"installed": True, "path": "claude"}
        }
        with patch("subprocess.run", return_value=mock_run_res) as mock_sub:
            res = execute_claude_code("Refactor authentication module")
            assert res["status"] == "success"
            assert res["tool"] == "claude_code"
            assert "Claude Code completed" in res["output"]
            mock_sub.assert_called_once()


def test_execute_claude_code_fallback_to_anthropic_api():
    with patch("fleet.core.dev_tools.detect_developer_tools") as mock_detect:
        mock_detect.return_value = {
            "claude_code": {"installed": False, "path": None}
        }
        with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
            mock_complete.return_value = {
                "response": "Direct Claude response",
                "tokens_used": 150,
                "cost_usd": "$0.00"
            }
            res = execute_claude_code("Explain architecture")
            assert res["status"] == "success"
            assert res["tool"] == "claude_code_api_fallback"
            assert res["output"] == "Direct Claude response"
            mock_complete.assert_called_once()


def test_execute_github_copilot_command_cli_success():
    mock_run_res = MagicMock(returncode=0, stdout="git commit -m 'feat: update'", stderr="")
    with patch("fleet.core.dev_tools.detect_developer_tools") as mock_detect:
        mock_detect.return_value = {
            "github_copilot": {"installed": True, "has_copilot_cli": True, "path": "gh"}
        }
        with patch("subprocess.run", return_value=mock_run_res) as mock_sub:
            res = execute_github_copilot_command("git command to commit changes", command_type="suggest")
            assert res["status"] == "success"
            assert res["tool"] == "github_copilot_cli"
            assert "git commit" in res["output"]
            mock_sub.assert_called_once()


def test_execute_github_copilot_fallback_to_azure():
    with patch("fleet.core.dev_tools.detect_developer_tools") as mock_detect:
        mock_detect.return_value = {
            "github_copilot": {"installed": False, "has_copilot_cli": False, "path": None}
        }
        with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
            mock_complete.return_value = {
                "response": "Use git status to inspect working tree",
                "tokens_used": 45,
                "cost_usd": "$0.00"
            }
            res = execute_github_copilot_command("how to check git status")
            assert res["status"] == "success"
            assert res["tool"] == "github_copilot_azure_fallback"
            assert "git status" in res["output"]


def test_execute_google_gemini_cli_and_aws_q_fallbacks():
    with patch("fleet.core.dev_tools.detect_developer_tools") as mock_detect:
        mock_detect.return_value = {
            "gemini_cli": {"installed": False, "path": None},
            "aws_q": {"installed": False, "path": None},
        }
        with patch("fleet.core.hyperscalers.HyperscalerGateway.complete") as mock_complete:
            mock_complete.return_value = {"response": "Vertex & Bedrock ready", "tokens_used": 20, "cost_usd": "$0.00"}
            res_gem = execute_google_gemini_cli("Deploy Cloud Run service")
            assert res_gem["status"] == "success"
            assert res_gem["tool"] == "google_gemini_api_fallback"

            res_q = execute_aws_q_developer("Create IAM role for Bedrock")
            assert res_q["status"] == "success"
            assert res_q["tool"] == "aws_bedrock_fallback"


def test_sync_github_copilot_and_all_instructions():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        res = sync_github_copilot_instructions(repo_root=repo_root)
        assert res["status"] == "synced"
        copilot_md = repo_root / ".github" / "copilot-instructions.md"
        assert copilot_md.is_file()
        content = copilot_md.read_text(encoding="utf-8")
        assert "Tier 0" in content
        assert "HyperscalerGateway" in content

        res_all = sync_all_developer_tool_instructions(repo_root=repo_root)
        assert res_all["status"] == "synced"
        assert (repo_root / "CLAUDE.md").is_file()
        assert (repo_root / "GEMINI.md").is_file()
