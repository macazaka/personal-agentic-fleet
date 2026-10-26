# CLAUDE.md — Anthropic Claude Code Guide for Personal Agentic Fleet

## Quick Verification Commands
- Full Preflight Gate (Doctor + 12-Layer Security + 126 Unit Tests): `python -m fleet.tools.preflight_gate`
- Fast Unit Test Suite: `python -m pytest tests/ -q --tb=short`
- Security Audit Only: `python -m fleet.security_scanner`

## 1. Fleet Rule 1: Tier 0 Cost & Token Governance (0 Tokens / $0.00 Default)
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
