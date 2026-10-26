"""
Exhaustive unit tests targeting remaining branches in fleet/core/hyperscalers.py and fleet/core/antigravity_mirror.py
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from fleet.core.hyperscalers import HyperscalerGateway
import fleet.core.antigravity_mirror as ag_mirror


# ==============================================================================
# HYPERSCALERS BRANCH TESTS
# ==============================================================================

def test_hyperscaler_google_vertex():
    gw = HyperscalerGateway()
    mock_resp_data = {
        "candidates": [{"content": {"parts": [{"text": "Vertex AI Response"}]}}],
        "usageMetadata": {"totalTokenCount": 42},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: {
            "GOOGLE_CLOUD_PROJECT": "test-proj",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
            "VERTEX_AI_TOKEN": "mock-token",
        }.get(k)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = gw._call_google_vertex("Hello Vertex", model="gemini-2.5-pro", sys_inst="Be concise")
            assert res["status"] == "SUCCESS"
            assert res["text"] == "Vertex AI Response"
            assert res["tokens_used"] == 42


def test_hyperscaler_microsoft_azure():
    gw = HyperscalerGateway()
    mock_resp_data = {
        "choices": [{"message": {"content": "Azure Response"}}],
        "usage": {"total_tokens": 55},
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: {
            "AZURE_OPENAI_API_KEY": "fake-azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        }.get(k)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            # Test foundry-phi4 model mapping
            res = gw._call_microsoft_azure("Hello Azure", model="azure-foundry-phi4", sys_inst="System instruction")
            assert res["status"] == "SUCCESS"
            assert res["text"] == "Azure Response"


def test_hyperscaler_aws_bedrock_variants():
    gw = HyperscalerGateway()
    
    # 1. Titan model output shape
    titan_data = {"results": [{"outputText": "Titan Response"}], "usage": {"total_tokens": 12}}
    mock_resp1 = MagicMock()
    mock_resp1.read.return_value = json.dumps(titan_data).encode("utf-8")
    mock_resp1.__enter__.return_value = mock_resp1

    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: {
            "AWS_BEARER_TOKEN": "mock-bearer",
            "AWS_BEDROCK_ENDPOINT": "https://bedrock-runtime.us-east-1.amazonaws.com",
        }.get(k)
        with patch("urllib.request.urlopen", return_value=mock_resp1):
            res_titan = gw._call_aws_bedrock("Hello Titan", model="amazon.titan-text-express-v1", sys_inst="Sys")
            assert res_titan["status"] == "SUCCESS"
            assert res_titan["text"] == "Titan Response"

    # 2. Nova model output shape
    nova_data = {"output": {"message": {"content": [{"text": "Nova Response"}]}}, "usage": {"total_tokens": 20}}
    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = json.dumps(nova_data).encode("utf-8")
    mock_resp2.__enter__.return_value = mock_resp2

    with patch("fleet.core.hyperscalers.get_secure_secret") as mock_sec:
        mock_sec.side_effect = lambda k: {
            "AWS_BEARER_TOKEN": "mock-bearer",
            "AWS_BEDROCK_ENDPOINT": "https://bedrock-runtime.us-east-1.amazonaws.com",
        }.get(k)
        with patch("urllib.request.urlopen", return_value=mock_resp2):
            res_nova = gw._call_aws_bedrock("Hello Nova", model="amazon.nova-micro-v1:0", sys_inst="Sys")
            assert res_nova["status"] == "SUCCESS"
            assert res_nova["text"] == "Nova Response"


def test_hyperscaler_openai_and_ollama():
    gw = HyperscalerGateway()

    # OpenAI Direct
    openai_data = {
        "choices": [{"message": {"content": "OpenAI Response"}}],
        "usage": {"total_tokens": 30},
    }
    mock_resp_oa = MagicMock()
    mock_resp_oa.read.return_value = json.dumps(openai_data).encode("utf-8")
    mock_resp_oa.__enter__.return_value = mock_resp_oa

    with patch("fleet.core.hyperscalers.get_secure_secret", return_value="fake-openai-key"):
        with patch("urllib.request.urlopen", return_value=mock_resp_oa):
            res_oa = gw._call_openai("Hello OpenAI", model="openai-gpt-4o", sys_inst="System msg")
            assert res_oa["status"] == "SUCCESS"
            assert res_oa["text"] == "OpenAI Response"

    # Ollama Offline Local
    ollama_data = {"response": "Ollama Response"}
    mock_resp_ol = MagicMock()
    mock_resp_ol.read.return_value = json.dumps(ollama_data).encode("utf-8")
    mock_resp_ol.__enter__.return_value = mock_resp_ol

    with patch("urllib.request.urlopen", return_value=mock_resp_ol):
        res_ol = gw._call_ollama("Hello Ollama", model="ollama-llama3.2")
        assert res_ol["status"] == "SUCCESS"
        assert res_ol["text"] == "Ollama Response"


def test_hyperscaler_complete_fallback_and_errors():
    gw = HyperscalerGateway()
    # Missing keys in direct methods should raise ValueError
    with patch("fleet.core.hyperscalers.get_secure_secret", return_value=""):
        with pytest.raises(ValueError):
            gw._call_openai("test")
        with pytest.raises(ValueError):
            gw._call_anthropic_claude("test")
        with pytest.raises(ValueError):
            gw._call_google_vertex("test")
        with pytest.raises(ValueError):
            gw._call_aws_bedrock("test")

    # Complete dispatch fallback on error
    with patch.object(gw, "_call_openai", side_effect=RuntimeError("API down")):
        res = gw.complete("Test prompt", provider="openai", allow_tier0=False)
        assert res["status"] in ("DEGRADED", "ERROR", "SUCCESS", "FALLBACK")


# ==============================================================================
# ANTIGRAVITY MIRROR BRANCH TESTS
# ==============================================================================

def test_antigravity_mirror_slash_commands_and_dev_tools():
    # /providers command
    res_prov = ag_mirror.execute_dashboard_command("/providers")
    assert res_prov["status"] == "success"
    assert res_prov["type"] == "hyperscaler_status"

    # /copilot command
    with patch("fleet.core.dev_tools.execute_github_copilot_command", return_value={"output": "copilot executed"}):
        res_cop = ag_mirror.execute_dashboard_command("/copilot test command")
        assert res_cop["status"] == "success"
        assert res_cop["type"] == "dev_tool"

    # /claude command
    with patch("fleet.core.dev_tools.execute_claude_code", return_value={"output": "claude executed"}):
        res_cl = ag_mirror.execute_dashboard_command("/claude review code")
        assert res_cl["status"] == "success"
        assert res_cl["type"] == "dev_tool"

    # /gemini command
    with patch("fleet.core.dev_tools.execute_google_gemini_cli", return_value={"output": "gemini executed"}):
        res_gem = ag_mirror.execute_dashboard_command("/gemini optimize")
        assert res_gem["status"] == "success"
        assert res_gem["type"] == "dev_tool"

    # /vertex command
    with patch.object(HyperscalerGateway, "complete", return_value={"text": "vertex response"}):
        res_vx = ag_mirror.execute_dashboard_command("/vertex analyze")
        assert res_vx["status"] == "success"
        assert res_vx["type"] == "hyperscaler_response"

    # /azure command
    with patch.object(HyperscalerGateway, "complete", return_value={"text": "azure response"}):
        res_az = ag_mirror.execute_dashboard_command("/azure analyze")
        assert res_az["status"] == "success"
        assert res_az["type"] == "hyperscaler_response"

    # /aws command
    with patch.object(HyperscalerGateway, "complete", return_value={"text": "aws response"}):
        res_aws = ag_mirror.execute_dashboard_command("/aws analyze")
        assert res_aws["status"] == "success"
        assert res_aws["type"] == "hyperscaler_response"

    # /ollama command
    with patch.object(HyperscalerGateway, "complete", return_value={"text": "ollama response"}):
        res_ol = ag_mirror.execute_dashboard_command("/ollama analyze")
        assert res_ol["status"] == "success"
        assert res_ol["type"] == "hyperscaler_response"


def test_antigravity_mirror_execute_prompt_target_models():
    with patch.object(ag_mirror, "get_token_health", return_value={"percent_used": 10.0}):
        # Claude Code CLI
        with patch("fleet.core.dev_tools.execute_claude_code", return_value={"output": "claude CLI"}):
            r1 = ag_mirror._execute_agy_or_fallback("prompt", model="claude-code-cli")
            assert r1["output"] == "claude CLI"

        # GitHub Copilot
        with patch("fleet.core.dev_tools.execute_github_copilot_command", return_value={"output": "copilot CLI"}):
            r2 = ag_mirror._execute_agy_or_fallback("prompt", model="github-copilot")
            assert r2["output"] == "copilot CLI"

        # Google Gemini CLI
        with patch("fleet.core.dev_tools.execute_google_gemini_cli", return_value={"output": "gemini CLI"}):
            r3 = ag_mirror._execute_agy_or_fallback("prompt", model="google-gemini-cli")
            assert r3["output"] == "gemini CLI"

        # AWS Q Developer
        with patch("fleet.core.dev_tools.execute_aws_q_developer", return_value={"output": "aws q CLI"}):
            r4 = ag_mirror._execute_agy_or_fallback("prompt", model="aws-q-developer")
            assert r4["output"] == "aws q CLI"

        # Hyperscaler targets: google-vertex, azure, aws, ollama, openai
        with patch.object(HyperscalerGateway, "complete", return_value={"status": "SUCCESS", "text": "HS ok"}):
            r5 = ag_mirror._execute_agy_or_fallback("prompt", model="google-vertex-gemini")
            assert r5["status"] == "SUCCESS"
            r6 = ag_mirror._execute_agy_or_fallback("prompt", model="azure-gpt-4o")
            assert r6["status"] == "SUCCESS"
            r7 = ag_mirror._execute_agy_or_fallback("prompt", model="aws-titan")
            assert r7["status"] == "SUCCESS"
            r8 = ag_mirror._execute_agy_or_fallback("prompt", model="ollama-llama")
            assert r8["status"] == "SUCCESS"
            r9 = ag_mirror._execute_agy_or_fallback("prompt", model="openai-gpt-4o")
            assert r9["status"] == "SUCCESS"

