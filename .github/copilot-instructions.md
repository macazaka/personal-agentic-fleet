# GitHub Copilot & AI Instructions for Personal Agentic Fleet

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
