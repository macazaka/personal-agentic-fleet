"""
Unit tests for fleet.core.hyperscalers (Multi-Hyperscaler LLM Gateway).
Tests zero-token local routing, dynamic credentials, and mock API calls across:
  - Google Gemini / Vertex AI
  - Microsoft Azure OpenAI / Foundry
  - Amazon Bedrock / AWS SageMaker
  - Anthropic Claude
  - Local Ollama / Offline Fallback
"""
from io import BytesIO
import json
import urllib.request
from unittest.mock import MagicMock, patch

import pytest
from fleet.core.hyperscalers import HyperscalerGateway, SUPPORTED_PROVIDERS


@pytest.fixture
def gateway():
    return HyperscalerGateway()


def test_list_available_providers(gateway):
    providers = gateway.list_available_providers()
    assert len(providers) >= 6
    ids = [p["id"] for p in providers]
    assert "google" in ids
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

    res = gateway.complete(prompt="A test prompt without credentials", provider="google", allow_tier0=False)
    assert res["status"] in ("NO_CREDENTIALS", "ERROR", "FALLBACK")
