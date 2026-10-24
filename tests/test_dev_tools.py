"""
Unit tests for Developer Tools integration (GitHub Copilot, Claude Code, Antigravity, Ollama).
"""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

from fleet.core.dev_tools import (
    detect_developer_tools,
    execute_claude_code,
    execute_github_copilot_command,
    sync_github_copilot_instructions,
)


def test_detect_developer_tools():
    tools = detect_developer_tools()
    assert "antigravity" in tools
    assert "claude_code" in tools
    assert "github_copilot" in tools
    assert "vscode" in tools
    assert "ollama" in tools

    assert tools["claude_code"]["provider"] == "Anthropic"
    assert tools["github_copilot"]["provider"] == "Microsoft / GitHub"
    assert tools["antigravity"]["provider"] == "Google"
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


def test_sync_github_copilot_instructions():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        res = sync_github_copilot_instructions(repo_root=repo_root)
        assert res["status"] == "synced"
        copilot_md = repo_root / ".github" / "copilot-instructions.md"
        assert copilot_md.is_file()
        content = copilot_md.read_text(encoding="utf-8")
        assert "Tier 0 Cost & Token Governance" in content
        assert "Multi-Hyperscaler Architecture" in content
        assert "Google" in content
        assert "Microsoft" in content
        assert "AWS" in content
        assert "Anthropic" in content
