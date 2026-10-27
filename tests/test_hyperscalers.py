"""
Unit tests for fleet.core.hyperscalers (Multi-Hyperscaler LLM Gateway).
Tests zero-token local routing, dynamic credentials, and mock API calls across:
  - Google Gemini (AI Studio REST) & Google Cloud Vertex AI
  - Microsoft Azure OpenAI, Azure AI Foundry & GitHub Models
  - Amazon Bedrock (Bearer & IAM SigV4 across Claude, Nova, Titan)
  - Anthropic Claude Direct
  - OpenAI Direct & Local Ollama / Offline Fallback
"""
import json
import urllib.request
from unittest.mock import MagicMock, patch

import pytest
from fleet.core.hyperscalers import HyperscalerGateway, SUPPORTED_PROVIDERS, _sign_aws_sigv4_headers


@pytest.fixture
def gateway():
    return HyperscalerGateway()


def test_list_available_providers(gateway):
    providers = gateway.list_available_providers()
    assert len(providers) >= 7
    ids = [p["id"] for p in providers]
    assert "google" in ids
    assert "google_vertex" in ids
    assert "microsoft" in ids
    assert "aws" in ids
    assert "anthropic" in ids
    assert "openai" in ids
    assert "ollama" in ids


def test_tier0_deterministic_intent_intercept(gateway):
    res = gateway.complete(prompt="/security", allow_tier0=True)
    assert res["status"] == "SUCCESS"
    assert res["tier"] == "TIER_0_INTENT"
    assert res["tokens_billed"] == 0
    assert "0.00" in res["cost_usd"] or res["cost_usd"] == ".00"
    assert "security" in res["text"].lower() or "score" in res["text"].lower()


def test_tier0_rag_intercept(gateway):
    res = gateway.complete(prompt="How do I prepare the FFD green smoothie?", allow_tier0=True)
    assert res["status"] == "SUCCESS"
    assert res["tier"] in ("TIER_0_INTENT", "TIER_0_RAG")
    assert res["tokens_billed"] == 0
    assert "0.00" in res["cost_usd"] or res["cost_usd"] == ".00"
    assert "smoothie" in res["text"].lower()


def test_google_gemini_mock(gateway, monkeypatch):
    mock_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello from Google Gemini Cloud!"}]
                }
            }
        ]
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key_12345")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Explain quantum entanglement", provider="google", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "google" in res["provider"].lower()
    assert "Google Gemini Cloud" in res["text"]


def test_google_vertex_ai_mock(gateway, monkeypatch):
    mock_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello from Google Cloud Vertex AI!"}]
                }
            }
        ],
        "usageMetadata": {"totalTokenCount": 42}
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fleet-vertex-proj")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("VERTEX_AI_TOKEN", "test_vertex_token_12345")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Vertex AI architecture analysis", provider="google_vertex", model="gemini-2.5-pro", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "Vertex AI" in res["provider"]
    assert "Google Cloud Vertex AI" in res["text"]


def test_microsoft_azure_mock(gateway, monkeypatch):
    mock_payload = {
        "choices": [
            {"message": {"content": "Hello from Microsoft Azure OpenAI!"}}
        ]
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test_azure_key_12345")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fleet-resource.openai.azure.com")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Calculate the prime numbers under 20", provider="microsoft", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "microsoft" in res["provider"].lower()
    assert "Microsoft Azure OpenAI" in res["text"]


def test_microsoft_github_models_mock(gateway, monkeypatch):
    mock_payload = {
        "choices": [
            {"message": {"content": "Hello from GitHub Models on Azure Inference!"}}
        ]
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "test_github_models_token_12345")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Review pull request diff", provider="github_models", model="gpt-4o", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "GitHub Models" in res["provider"]
    assert "GitHub Models on Azure Inference" in res["text"]


def test_aws_bedrock_mock(gateway, monkeypatch):
    mock_payload = {
        "content": [
            {"text": "Hello from Amazon Bedrock Anthropic Claude!"}
        ]
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("AWS_BEARER_TOKEN", "test_aws_token_12345")
    monkeypatch.setenv("AWS_BEDROCK_ENDPOINT", "https://bedrock-runtime.us-east-1.amazonaws.com")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Give a haiku on clouds", provider="aws", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert any(k in res["provider"].lower() for k in ("aws", "amazon", "bedrock"))
    assert "Amazon Bedrock" in res["text"]


def test_aws_bedrock_sigv4_and_nova_mock(gateway, monkeypatch):
    headers = _sign_aws_sigv4_headers(
        method="POST",
        url="https://bedrock-runtime.us-east-1.amazonaws.com/model/amazon.nova-pro-v1:0/invoke",
        payload_bytes=b'{"messages":[]}',
        access_key="test_aws_key_id_12345",
        sig_material="test_aws_sig_mat_12345",
        region="us-east-1",
    )
    assert "AWS4-HMAC-SHA256" in headers["Authorization"]
    assert "X-Amz-Date" in headers

    mock_payload = {
        "output": {
            "message": {
                "content": [{"text": "Hello from Amazon Nova Pro via SigV4!"}]
            }
        }
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.delenv("AWS_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test_aws_key_id_12345")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_aws_secret_key_12345")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Nova test", provider="aws", model="aws-bedrock-nova-pro", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "Amazon Nova Pro" in res["text"]


def test_anthropic_claude_mock(gateway, monkeypatch):
    mock_payload = {
        "content": [
            {"text": "Hello from Anthropic Claude API!"}
        ]
    }
    class MockResp:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_claude_key_12345")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: MockResp())

    res = gateway.complete(prompt="Summarize the theory of relativity", provider="anthropic", allow_tier0=False)
    assert res["status"] == "SUCCESS"
    assert "anthropic" in res["provider"].lower()
    assert "Anthropic Claude" in res["text"]


def test_missing_credentials_graceful_fallback(gateway, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    res = gateway.complete(prompt="A test prompt without credentials", provider="google", allow_tier0=False)
    assert res["status"] in ("NO_CREDENTIALS", "ERROR", "FALLBACK")
