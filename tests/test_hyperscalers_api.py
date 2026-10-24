"""
Unit tests for Multi-Hyperscaler & Developer Tools REST API endpoints.
"""

from unittest.mock import MagicMock, patch
import urllib.parse

from fleet.api.hyperscalers_api import (
    get_developer_tools_status,
    get_hyperscaler_providers,
    post_execute_claude_code,
    post_execute_copilot,
    post_hyperscaler_generate,
    post_sync_copilot_instructions,
)


def test_get_hyperscaler_providers():
    mock_handler = MagicMock()
    parsed_url = urllib.parse.urlparse("http://127.0.0.1:7890/api/hyperscalers/providers")
    get_hyperscaler_providers(mock_handler, parsed_url)

    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["status"] == "success"
    assert "providers" in payload
    provider_ids = [p["id"] for p in payload["providers"]]
    assert "google" in provider_ids
    assert "microsoft" in provider_ids
    assert "aws" in provider_ids
    assert "anthropic" in provider_ids
    assert "ollama" in provider_ids


def test_get_developer_tools_status():
    mock_handler = MagicMock()
    parsed_url = urllib.parse.urlparse("http://127.0.0.1:7890/api/hyperscalers/dev_tools")
    get_developer_tools_status(mock_handler, parsed_url)

    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["status"] == "success"
    assert "claude_code" in payload["tools"]
    assert "github_copilot" in payload["tools"]
    assert "antigravity" in payload["tools"]


def test_post_hyperscaler_generate_intent_intercept():
    mock_handler = MagicMock()
    body = {"prompt": "/security", "provider": "google"}
    post_hyperscaler_generate(mock_handler, body)

    assert mock_handler._send_json.called
    payload = mock_handler._send_json.call_args[0][0]
    assert payload["status"] == "SUCCESS"
    assert payload["tier"] == "TIER_0_INTENT"
    assert payload["tokens_billed"] == 0
    assert "0.00" in payload["cost_usd"] or payload["cost_usd"] == ".00"


def test_post_hyperscaler_generate_missing_prompt():
    mock_handler = MagicMock()
    post_hyperscaler_generate(mock_handler, {})
    assert mock_handler._send_json.called
    assert mock_handler._send_json.call_args[0][1] == 400


def test_post_execute_claude_code_and_copilot_endpoints():
    mock_handler = MagicMock()
    with patch("fleet.api.hyperscalers_api.execute_claude_code") as mock_cc:
        mock_cc.return_value = {"status": "success", "tool": "claude_code", "output": "Refactored"}
        post_execute_claude_code(mock_handler, {"prompt": "Refactor test"})
        assert mock_handler._send_json.called
        assert mock_handler._send_json.call_args[0][0]["output"] == "Refactored"

    mock_handler.reset_mock()
    with patch("fleet.api.hyperscalers_api.execute_github_copilot_command") as mock_copilot:
        mock_copilot.return_value = {"status": "success", "tool": "github_copilot_cli", "output": "git push"}
        post_execute_copilot(mock_handler, {"prompt": "push command"})
        assert mock_handler._send_json.called
        assert mock_handler._send_json.call_args[0][0]["output"] == "git push"

    mock_handler.reset_mock()
    with patch("fleet.api.hyperscalers_api.sync_github_copilot_instructions") as mock_sync:
        mock_sync.return_value = {"status": "synced"}
        post_sync_copilot_instructions(mock_handler, {})
        assert mock_handler._send_json.called
        assert mock_handler._send_json.call_args[0][0]["status"] == "synced"
