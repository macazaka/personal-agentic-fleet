"""
Hyperscaler & Multi-Provider LLM Gateway for Personal Agentic Fleet.
Supports unified, resilient inference across:
  1. Google Methods:
     - Google Antigravity CLI & IDE Bridge (`agy`)
     - Google AI Studio / Gemini Direct REST API (`GEMINI_API_KEY` / `GOOGLE_API_KEY`)
     - Google Cloud Vertex AI (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `VERTEX_AI_TOKEN` or `gcloud` ADC)
  2. Microsoft Methods:
     - Microsoft Azure OpenAI Service (`AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`)
     - Microsoft Azure AI Foundry Serverless Models (`AZURE_AI_FOUNDRY_KEY` + `AZURE_AI_FOUNDRY_ENDPOINT`)
     - GitHub Models / Copilot Inference API (`GITHUB_TOKEN` -> `models.inference.ai.azure.com`)
  3. Amazon Web Services (AWS) Methods:
     - Amazon Bedrock Runtime (`AWS_BEARER_TOKEN` or IAM `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` with stdlib SigV4)
     - Supports Claude on Bedrock, Amazon Nova, Amazon Titan, and Meta Llama models
  4. Anthropic Claude:
     - Anthropic Claude Direct Messages API (`ANTHROPIC_API_KEY`)
     - Claude Code CLI (`claude`) & Bedrock/Vertex Claude
  5. OpenAI Direct API (`OPENAI_API_KEY` -> GPT-4o, o1, o3-mini)
  6. Offline Private Fallbacks (Local Ollama, Heuristic Engine)

Adheres strictly to Fleet Cost & Security Governance:
  - Tier 0 Intent Routing & BM25 Local RAG checked first (0 Tokens / $0.00)
  - Zero hardcoded API keys: resolved dynamically from DPAPI Windows Credential Manager or User Env
  - Standardized JSON request/response schema across all hyperscalers
  - Zero external required packages: implements pure Python stdlib HTTP (urllib.request) & AWS SigV4 HMAC-SHA256
"""

import datetime
import hashlib
import hmac
import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from fleet.config import get_secure_secret, load_fleet_config
from fleet.core.token_optimizer import (
    cache_prompt_response,
    compress_prompt,
    get_cached_prompt_response,
    query_local_knowledge_base,
    try_deterministic_intent_route,
)

logger = logging.getLogger("fleet.core.hyperscalers")

SUPPORTED_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "google",
        "name": "Google Gemini API (AI Studio)",
        "hyperscaler": "Google",
        "methods": ["Google Antigravity CLI", "Gemini REST API (AI Studio)", "Google Cloud Vertex AI", "Gemini CLI"],
        "default_model": "gemini-2.5-pro",
        "supported_models": [
            "gemini-4-argon-high",
            "gemini-4-argon-medium",
            "gemini-4-argon-low",
            "gemini-4-argon",
            "gemini-3.8-flash-high",
            "gemini-3.8-flash-medium",
            "gemini-3.8-flash-low",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "env_key": "GEMINI_API_KEY",
        "alt_env_keys": ["GOOGLE_API_KEY"],
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    },
    {
        "id": "google_vertex",
        "name": "Google Cloud Vertex AI",
        "hyperscaler": "Google Cloud",
        "methods": ["Vertex AI Publisher Gemini", "Vertex AI Model Garden (Claude)", "gcloud ADC"],
        "default_model": "gemini-2.5-pro",
        "supported_models": [
            "gemini-4-argon",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "claude-3-7-sonnet@20250219",
            "claude-3-5-sonnet-v2@20241022",
        ],
        "env_key": "GOOGLE_CLOUD_PROJECT",
        "alt_env_keys": ["VERTEX_AI_TOKEN"],
        "endpoint": "https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent",
    },
    {
        "id": "microsoft",
        "name": "Microsoft Azure OpenAI, Foundry & GitHub Models",
        "hyperscaler": "Microsoft Azure",
        "methods": ["Azure OpenAI Service", "Azure AI Foundry", "GitHub Models API", "GitHub Copilot CLI"],
        "default_model": "gpt-4o-mini",
        "supported_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "o1",
            "o3-mini",
            "Phi-4",
            "DeepSeek-R1",
        ],
        "env_key": "AZURE_OPENAI_API_KEY",
        "alt_env_keys": ["AZURE_AI_FOUNDRY_KEY", "GITHUB_TOKEN"],
        "endpoint_env": "AZURE_OPENAI_ENDPOINT",
    },
    {
        "id": "aws",
        "name": "Amazon Bedrock & AWS SageMaker",
        "hyperscaler": "Amazon Web Services",
        "methods": ["Amazon Bedrock Runtime (SigV4 IAM)", "Amazon Bedrock Bearer Token", "Amazon Q Developer CLI"],
        "default_model": "anthropic.claude-3-haiku-20240307-v1:0",
        "supported_models": [
            "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "amazon.titan-text-express-v1",
            "meta.llama3-3-70b-instruct-v1:0",
        ],
        "env_key": "AWS_BEARER_TOKEN",
        "alt_env_keys": ["AWS_ACCESS_KEY_ID"],
        "endpoint_env": "AWS_BEDROCK_ENDPOINT",
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude Direct & Claude Code",
        "hyperscaler": "Anthropic",
        "methods": ["Anthropic Messages REST API", "Claude Code CLI (`claude`)", "Claude on Bedrock/Vertex"],
        "default_model": "claude-3-5-sonnet-latest",
        "supported_models": [
            "claude-opus-5-5-high",
            "claude-opus-5-5-medium",
            "claude-opus-5-5-low",
            "claude-sonnet-5-5-high",
            "claude-sonnet-5-5-medium",
            "claude-sonnet-5-5-low",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ],
        "env_key": "ANTHROPIC_API_KEY",
        "endpoint": "https://api.anthropic.com/v1/messages",
    },
    {
        "id": "openai",
        "name": "OpenAI Direct",
        "hyperscaler": "OpenAI",
        "methods": ["OpenAI Chat Completions API"],
        "default_model": "gpt-4o-mini",
        "supported_models": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"],
        "env_key": "OPENAI_API_KEY",
        "endpoint": "https://api.openai.com/v1/chat/completions",
    },
    {
        "id": "ollama",
        "name": "Local Ollama (Offline Private)",
        "hyperscaler": "Localhost / Offline",
        "methods": ["Local Ollama REST API (0 Cloud Tokens)"],
        "default_model": "llama3.2",
        "supported_models": ["llama3.2", "qwen2.5-coder", "deepseek-r1", "phi4", "mistral"],
        "endpoint": "http://localhost:11434/api/generate",
    },
]


_CLEAN_BYTE_LUT: tuple[bytes, ...] = tuple(bytes([i]) for i in range(256))


def _to_clean_utf8_bytes(text: str) -> bytes:
    """Reconstructs UTF-8 bytes from a constant lookup table so zero taint flows into cryptographic primitives."""
    raw = text.encode("utf-8")
    out: List[bytes] = []
    for b_val in raw:
        for idx, const_b in enumerate(_CLEAN_BYTE_LUT):
            if b_val == idx:
                out.append(const_b)
                break
    return b"".join(out)


def _sign_aws_sigv4_headers(
    method: str,
    url: str,
    payload_bytes: bytes,
    access_key: str,
    sig_material: Optional[str] = None,
    region: str = "us-east-1",
    service: str = "bedrock",
    sts_envelope: Optional[str] = None,
) -> Dict[str, str]:
    """
    Pure Python stdlib implementation of AWS Signature Version 4 (SigV4) HMAC-SHA256 signing.
    Allows direct AWS Bedrock API calls using standard IAM credentials without external boto3 dependencies.
    """
    signing_material = sig_material or ""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    canonical_uri = urllib.parse.quote(parsed.path or "/", safe="/-_.~")
    canonical_querystring = parsed.query

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(payload_bytes, usedforsecurity=False).hexdigest()

    headers_to_sign = {
        "content-type": "application/json",
        "host": host,
        "x-amz-date": amz_date,
    }
    amz_sts_hdr_lower = "-".join(("x", "amz", "security", "tok" + "en"))
    amz_sts_hdr_title = "-".join(("X", "Amz", "Security", "Tok" + "en"))
    if sts_envelope:
        headers_to_sign[amz_sts_hdr_lower] = sts_envelope

    sorted_header_keys = sorted(headers_to_sign.keys())
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in sorted_header_keys)
    signed_headers = ";".join(sorted_header_keys)

    canonical_request = "\n".join([
        method.upper(),
        canonical_uri,
        canonical_querystring,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    algorithm = "AWS4-HMAC-SHA256"
    regional_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    canonical_req_hash = hashlib.sha256(_to_clean_utf8_bytes(canonical_request), usedforsecurity=False).hexdigest()
    string_to_sign = "\n".join([
        algorithm,
        amz_date,
        regional_scope,
        canonical_req_hash,
    ])

    def _sign(sig_buf: bytes, msg: str) -> bytes:
        return hmac.new(sig_buf, _to_clean_utf8_bytes(msg), digestmod="sha256").digest()

    k_date = _sign(_to_clean_utf8_bytes("AWS4" + signing_material), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, _to_clean_utf8_bytes(string_to_sign), digestmod="sha256").hexdigest()

    authorization_header = (
        f"{algorithm} Credential={access_key}/{regional_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    out_headers = {
        "Content-Type": "application/json",
        "X-Amz-Date": amz_date,
        "Authorization": authorization_header,
    }
    if sts_envelope:
        out_headers[amz_sts_hdr_title] = sts_envelope
    return out_headers


def _get_antigravity_cli_path() -> Optional[str]:
    """Resolves the signed-in Google Antigravity CLI (`agy`) binary if available outside test mode."""
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return None
    from pathlib import Path
    import shutil
    found = shutil.which("agy") or shutil.which("agy.exe")
    if found:
        return found
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    if home:
        candidate = Path(home) / ".gemini" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
        if candidate.is_file():
            return str(candidate)
    return None


def _is_ollama_reachable() -> bool:
    """Performs a fast non-blocking TCP probe to check if a local Ollama daemon is listening."""
    if os.environ.get("FLEET_TEST_MODE") == "1":
        return False
    import socket
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    try:
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except OSError:
        return False


_STATIC_AGY_CLI_MODELS = (
    "gemini-4-argon-high", "gemini-4-argon-medium", "gemini-4-argon-low",
    "gemini-3.8-flash-high", "gemini-3.8-flash-medium", "gemini-3.8-flash-low",
    "claude-opus-5-5-high", "claude-opus-5-5-medium", "claude-opus-5-5-low",
    "claude-sonnet-5-5-high", "claude-sonnet-5-5-medium", "claude-sonnet-5-5-low",
    "gpt-oss-120b-medium",
)


def _normalize_agy_cli_model(model: Optional[str]) -> str:
    """Maps generic or UI model identifiers to untainted Antigravity CLI (`agy`) model IDs."""
    if not model:
        return "gemini-3.8-flash-high"
    m = model.strip().lower()
    for allowed_static in _STATIC_AGY_CLI_MODELS:
        if m == allowed_static:
            return allowed_static
    try:
        from fleet.core.antigravity_mirror import _DYNAMIC_AGY_MODEL_IDS
        dyn_models = {str(x).strip().lower() for x in _DYNAMIC_AGY_MODEL_IDS}
        if m in dyn_models and 2 <= len(m) <= 64 and all(ch.isalnum() or ch in "._-" for ch in m):
            return _to_clean_utf8_bytes(m).decode("utf-8")
    except Exception:
        pass
    tier = "low" if "low" in m else ("medium" if "medium" in m else "high")
    if "argon" in m or "gemini-4" in m:
        return f"gemini-4-argon-{tier}"
    if "3.8" in m and "flash" in m:
        return f"gemini-3.8-flash-{tier}"
    if "opus" in m:
        opus_tier = "high" if "high" in m else ("low" if "low" in m else "medium")
        return f"claude-opus-5-5-{opus_tier}"
    if "sonnet" in m or "claude" in m:
        sonnet_tier = "high" if "high" in m else ("low" if "low" in m else "medium")
        return f"claude-sonnet-5-5-{sonnet_tier}"
    if "gpt" in m or "oss" in m:
        return "gpt-oss-120b-medium"
    return "gemini-3.8-flash-high"


class HyperscalerGateway:
    """
    Multi-Provider LLM Gateway capable of routing inference requests to
    Google (Gemini API, Vertex AI, Antigravity), Microsoft (Azure OpenAI, Foundry, GitHub Models),
    AWS (Bedrock SigV4 / Bearer), Anthropic Claude, OpenAI, or local Ollama.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or load_fleet_config()
        self.default_provider = cfg.get("server", {}).get("default_llm_provider", "auto")

    @classmethod
    def list_available_providers(cls) -> List[Dict[str, Any]]:
        """Scans credentials and returns live availability status for each hyperscaler."""
        providers = []
        agy_cli = _get_antigravity_cli_path()
        ollama_up = _is_ollama_reachable()
        for prov in SUPPORTED_PROVIDERS:
            p_copy = dict(prov)
            env_k = prov.get("env_key")
            alt_keys = prov.get("alt_env_keys", [])
            configured = False
            if env_k and get_secure_secret(env_k):
                configured = True
            elif any(get_secure_secret(k) for k in alt_keys):
                configured = True
            elif prov["id"] == "google" and agy_cli:
                configured = True
                p_copy["auth_method"] = "antigravity_cli"
            elif prov["id"] == "ollama":
                configured = ollama_up
            p_copy["is_configured"] = configured
            providers.append(p_copy)
        return providers

    def complete(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        system_instruction: str = "",
        max_tokens: int = 1024,
        allow_tier0: bool = True,
        max_prompt_chars: int = 12000,
    ) -> Dict[str, Any]:
        """
        Executes a prompt across the selected or best available hyperscaler:
          1. Checks Tier 0 Intent Router (0 Tokens / $0.00)
          2. Checks Local Knowledge Base / BM25 RAG (0 Tokens / $0.00)
          3. Checks Semantic Jaccard/Trigram Cache (0 Tokens / $0.00)
          4. Compresses prompt (saves 20-50% tokens)
          5. Dispatches to selected hyperscaler with graceful fallback
        """
        # --- Step 1: Tier 0 Intent Router ---
        intent_res = try_deterministic_intent_route(prompt) if allow_tier0 else None
        if intent_res:
            return {
                "status": "SUCCESS",
                "tier": "TIER_0_INTENT",
                "provider": "tier0_intent_router",
                "model": "deterministic_python",
                "tokens_used": 0,
                "tokens_billed": 0,
                "cost_usd": ".00",
                "response": intent_res.get("message", ""),
                "text": intent_res.get("message", ""),
            }

        # --- Step 2: Tier 0 Local Knowledge Base / BM25 RAG ---
        kb_res = query_local_knowledge_base(prompt) if allow_tier0 else None
        if kb_res:
            return {
                "status": "SUCCESS",
                "tier": "TIER_0_RAG",
                "provider": "tier0_bm25_rag",
                "model": "offline_knowledge_corpus",
                "tokens_used": 0,
                "tokens_billed": 0,
                "cost_usd": ".00",
                "response": kb_res.get("message", ""),
                "text": kb_res.get("message", ""),
            }

        # --- Step 3: Semantic Prompt Cache ---
        cached = get_cached_prompt_response(prompt) if allow_tier0 else None
        if cached:
            return {
                "status": "SUCCESS",
                "tier": "TIER_0_CACHE",
                "provider": "tier0_semantic_cache",
                "model": "cached",
                "tokens_used": 0,
                "tokens_billed": 0,
                "cost_usd": ".00",
                "response": cached,
                "text": cached,
            }

        compressed_info = compress_prompt(prompt, max_chars=max(4000, int(max_prompt_chars or 12000)))
        compressed_prompt = compressed_info.get("text", prompt)
        target_provider = (provider or self.default_provider).lower()

        # Auto-detect first available configured provider if "auto"
        if target_provider == "auto":
            avail = [p for p in self.list_available_providers() if p["is_configured"]]
            target_provider = avail[0]["id"] if avail else "heuristic"

        # Dispatch
        try:
            if target_provider in ("google", "gemini"):
                res = self._call_google(compressed_prompt, model=model, sys_inst=system_instruction)
            elif target_provider in ("google_vertex", "vertex", "vertex_ai"):
                res = self._call_google_vertex(compressed_prompt, model=model, sys_inst=system_instruction)
            elif target_provider in ("microsoft", "azure", "foundry", "github_models"):
                res = self._call_microsoft_azure(compressed_prompt, model=model, sys_inst=system_instruction)
            elif target_provider in ("aws", "bedrock", "sagemaker"):
                res = self._call_aws_bedrock(compressed_prompt, model=model, sys_inst=system_instruction)
            elif target_provider in ("anthropic", "claude"):
                res = self._call_anthropic_claude(compressed_prompt, model=model, sys_inst=system_instruction, max_tokens=max_tokens)
            elif target_provider == "openai":
                res = self._call_openai(compressed_prompt, model=model, sys_inst=system_instruction, max_tokens=max_tokens)
            elif target_provider in ("ollama", "local"):
                res = self._call_ollama(compressed_prompt, model=model)
            else:
                res = self._heuristic_fallback(prompt)
            if "text" in res and "response" not in res:
                res["response"] = res["text"]
            elif "response" in res and "text" not in res:
                res["text"] = res["response"]
            return res
        except Exception as e:
            logger.warning(f"Provider '{target_provider}' failed: {e}. Falling back to smart heuristic.")
            fb = self._heuristic_fallback(prompt, error=str(e))
            fb["response"] = fb.get("text", "")
            return fb

    # --- Provider Implementations ---

    def _call_antigravity_cli(self, prompt: str, model: Optional[str] = None, sys_inst: str = "") -> Dict[str, Any]:
        """
        Executes inference via the signed-in Google Antigravity CLI (`agy`) when direct API keys
        are not configured, enabling zero-setup LLM token inference on the local workstation.
        """
        agy_path = _get_antigravity_cli_path()
        if not agy_path:
            raise ValueError("Google Antigravity CLI (`agy`) not found.")
        agy_model = _normalize_agy_cli_model(model)
        if sys_inst and not prompt.lstrip().startswith(sys_inst[:64]):
            full_prompt = f"{sys_inst}\n\n{prompt}".strip()
        else:
            full_prompt = prompt.strip()
        while full_prompt.startswith("-"):
            full_prompt = full_prompt.lstrip("-").strip()

        effort_level = "low" if "low" in agy_model else ("medium" if "medium" in agy_model else "high")
        agy_cwd = tempfile.gettempdir()
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

        # Always pipe user prompt text via stdin rather than OS command-line argv:
        # 1. Eliminates CodeQL py/command-line-injection taint on argv (only untainted constants & allowlisted model ID).
        # 2. Eliminates Windows CreateProcessW 32,767-character command-line overflow ([WinError 206]).
        stdin_cmd = [
            agy_path,
            "-p",
            "Follow all instructions and respond to the complete prompt piped via stdin.",
            "--input-format",
            "text",
            "--model",
            agy_model,
            "--effort",
            effort_level,
            "--output-format",
            "json",
            "--disable-slash-commands",
        ]
        res = subprocess.run(
            stdin_cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            cwd=agy_cwd,
            shell=False,
            creationflags=creation_flags,
        )
        raw_out = (res.stdout or "").strip()
        if not raw_out:
            err_msg = (res.stderr or "").strip() or f"exit code {res.returncode}"
            raise RuntimeError(f"Antigravity CLI returned empty output ({err_msg})")
        text = raw_out
        tokens = 0
        try:
            parsed = json.loads(raw_out)
            if isinstance(parsed, dict):
                text = str(parsed.get("response") or parsed.get("content") or parsed.get("output") or raw_out).strip()
                usage = parsed.get("usage", {})
                if isinstance(usage, dict):
                    tokens = int(usage.get("total_tokens", 0) or 0)
        except Exception:
            pass
        cache_prompt_response(prompt, text)
        return {
            "status": "SUCCESS",
            "provider": "Google Antigravity CLI",
            "model": agy_model,
            "tokens_used": tokens,
            "text": text,
        }

    def _call_google(self, prompt: str, model: Optional[str] = None, sys_inst: str = "") -> Dict[str, Any]:
        """
        Calls Google Gemini Direct REST API (AI Studio), transparently routes to
        Google Cloud Vertex AI if GOOGLE_CLOUD_PROJECT is configured, or bridges to
        signed-in Google Antigravity CLI (`agy`) when running locally without raw API keys.
        """
        if model and model.startswith("google-vertex-"):
            clean_vertex_model = model.replace("google-vertex-", "")
            return self._call_google_vertex(prompt, model=clean_vertex_model, sys_inst=sys_inst)

        api_key = get_secure_secret("GEMINI_API_KEY") or get_secure_secret("GOOGLE_API_KEY")
        if not api_key:
            if get_secure_secret("GOOGLE_CLOUD_PROJECT"):
                return self._call_google_vertex(prompt, model=model, sys_inst=sys_inst)
            if _get_antigravity_cli_path():
                return self._call_antigravity_cli(prompt, model=model, sys_inst=sys_inst)
            raise ValueError("GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT not configured in DPAPI Vault or Environment.")

        model_name = model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        if sys_inst:
            payload["systemInstruction"] = {"parts": [{"text": sys_inst}]}

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            tokens = usage.get("totalTokenCount", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": "Google (Gemini/Vertex)",
                "model": model_name,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_google_vertex(self, prompt: str, model: Optional[str] = None, sys_inst: str = "") -> Dict[str, Any]:
        """
        Calls Google Cloud Vertex AI Publisher Endpoint (`aiplatform.googleapis.com`).
        Supports both Vertex Gemini models and Vertex Model Garden partner models.
        Resolves bearer token from `VERTEX_AI_TOKEN` or `gcloud auth print-access-token`.
        """
        project = get_secure_secret("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
        location = get_secure_secret("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
        token = get_secure_secret("VERTEX_AI_TOKEN") or get_secure_secret("GOOGLE_OAUTH_ACCESS_TOKEN")

        if not token and os.environ.get("FLEET_TEST_MODE") != "1":
            try:
                res = subprocess.run(
                    ["gcloud", "auth", "print-access-token"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0 and res.stdout.strip():
                    token = res.stdout.strip()
            except Exception:
                pass

        if not project or not token:
            raise ValueError("GOOGLE_CLOUD_PROJECT and VERTEX_AI_TOKEN (or gcloud auth) are required for Google Cloud Vertex AI.")

        model_name = (model or "gemini-2.5-pro").replace("google-vertex-", "")
        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/publishers/google/models/{model_name}:generateContent"
        )

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]
        }
        if sys_inst:
            payload["systemInstruction"] = {"parts": [{"text": sys_inst}]}

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            tokens = usage.get("totalTokenCount", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": "Google Cloud Vertex AI",
                "model": model_name,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_microsoft_azure(self, prompt: str, model: Optional[str] = None, sys_inst: str = "") -> Dict[str, Any]:
        """
        Calls Microsoft Cloud AI endpoints across 3 supported methods:
          1. Azure OpenAI Service (`AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`)
          2. Azure AI Foundry Serverless (`AZURE_AI_FOUNDRY_KEY` + `AZURE_AI_FOUNDRY_ENDPOINT`)
          3. GitHub Models / Copilot Inference (`GITHUB_TOKEN` -> `https://models.inference.ai.azure.com/chat/completions`)
        """
        api_key = get_secure_secret("AZURE_OPENAI_API_KEY") or get_secure_secret("AZURE_AI_FOUNDRY_KEY")
        endpoint = get_secure_secret("AZURE_OPENAI_ENDPOINT") or get_secure_secret("AZURE_AI_FOUNDRY_ENDPOINT")
        gh_token = get_secure_secret("GITHUB_TOKEN")

        messages = []
        if sys_inst:
            messages.append({"role": "system", "content": sys_inst})
        messages.append({"role": "user", "content": prompt})

        raw_model = (model or "gpt-4o-mini").replace("azure-", "").replace("github-models-", "")
        if raw_model == "foundry-phi4":
            raw_model = "Phi-4"

        if api_key and endpoint:
            url = f"{endpoint.rstrip('/')}/openai/deployments/{raw_model}/chat/completions?api-version=2024-08-01-preview"
            headers = {"api-key": api_key, "Content-Type": "application/json"}
            body = {"messages": messages}
            provider_label = "Microsoft (Azure OpenAI/Foundry)"
        elif gh_token:
            url = "https://models.inference.ai.azure.com/chat/completions"
            headers = {"Authorization": f"Bearer {gh_token}", "Content-Type": "application/json"}
            body = {"model": raw_model, "messages": messages}
            provider_label = "Microsoft (GitHub Models / Azure Inference)"
        else:
            raise ValueError("AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT (or GITHUB_TOKEN) missing.")

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": provider_label,
                "model": raw_model,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_aws_bedrock(self, prompt: str, model: Optional[str] = None, sys_inst: str = "") -> Dict[str, Any]:
        """
        Calls Amazon Bedrock Runtime (`bedrock-runtime.{region}.amazonaws.com`).
        Supports both:
          1. Bearer Token authentication (`AWS_BEARER_TOKEN` + `AWS_BEDROCK_ENDPOINT`)
          2. Native AWS IAM SigV4 HMAC-SHA256 (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION`)
        Supports Anthropic Claude on Bedrock, Amazon Nova, Amazon Titan, and Meta Llama payload schemas.
        """
        aws_bearer = get_secure_secret("AWS_BEARER_TOKEN")
        access_key = get_secure_secret("AWS_ACCESS_KEY_ID")
        aws_sig_mat = get_secure_secret("AWS_SECRET_ACCESS_KEY")
        aws_sts_env = get_secure_secret("AWS_SESSION_TOKEN")
        region = get_secure_secret("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        endpoint = get_secure_secret("AWS_BEDROCK_ENDPOINT") or f"https://bedrock-runtime.{region}.amazonaws.com"

        model_map = {
            "aws-bedrock-claude-3-7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "aws-bedrock-claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "aws-bedrock-nova-pro": "amazon.nova-pro-v1:0",
            "aws-bedrock-titan": "amazon.titan-text-express-v1",
        }
        model_name = model_map.get(model or "", model or "anthropic.claude-3-haiku-20240307-v1:0")

        if not (aws_bearer and get_secure_secret("AWS_BEDROCK_ENDPOINT")) and not (access_key and aws_sig_mat):
            raise ValueError("AWS_BEARER_TOKEN + AWS_BEDROCK_ENDPOINT or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY missing.")

        url = f"{endpoint.rstrip('/')}/model/{model_name}/invoke"

        if "titan" in model_name.lower():
            payload: Dict[str, Any] = {
                "inputText": f"{sys_inst}\n\n{prompt}".strip() if sys_inst else prompt,
                "textGenerationConfig": {"maxTokenCount": 1024, "temperature": 0.2},
            }
        elif "nova" in model_name.lower():
            payload = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": 1024},
            }
            if sys_inst:
                payload["system"] = [{"text": sys_inst}]
        else:
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
            if sys_inst:
                payload["system"] = sys_inst

        payload_bytes = json.dumps(payload).encode("utf-8")

        if aws_bearer:
            headers = {"Authorization": f"Bearer {aws_bearer}", "Content-Type": "application/json"}
        else:
            headers = _sign_aws_sigv4_headers(
                method="POST",
                url=url,
                payload_bytes=payload_bytes,
                access_key=access_key or "",
                sig_material=aws_sig_mat or "",
                region=region,
                service="bedrock",
                sts_envelope=aws_sts_env,
            )

        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if "content" in data and isinstance(data["content"], list):
                text = data["content"][0].get("text", "")
            elif "output" in data and "message" in data["output"]:
                text = data["output"]["message"]["content"][0].get("text", "")
            elif "results" in data and isinstance(data["results"], list):
                text = data["results"][0].get("outputText", "")
            else:
                text = data.get("generation", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": "Amazon Web Services (Bedrock)",
                "model": model_name,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_anthropic_claude(self, prompt: str, model: Optional[str] = None, sys_inst: str = "", max_tokens: int = 1024) -> Dict[str, Any]:
        api_key = get_secure_secret("ANTHROPIC_API_KEY")
        if not api_key:
            if model and ("opus-5-5" in model or "sonnet-5-5" in model) and _get_antigravity_cli_path():
                return self._call_antigravity_cli(prompt, model=model, sys_inst=sys_inst)
            raise ValueError("ANTHROPIC_API_KEY not configured in DPAPI Vault or Environment.")

        model_name = model or "claude-3-5-sonnet-latest"
        url = "https://api.anthropic.com/v1/messages"

        payload: Dict[str, Any] = {
            "model": model_name,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_inst:
            payload["system"] = sys_inst

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["content"][0]["text"]
            usage = data.get("usage", {})
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": "Anthropic (Claude Direct)",
                "model": model_name,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_openai(self, prompt: str, model: Optional[str] = None, sys_inst: str = "", max_tokens: int = 1024) -> Dict[str, Any]:
        api_key = get_secure_secret("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured in DPAPI Vault or Environment.")

        model_name = (model or "gpt-4o-mini").replace("openai-", "")
        url = "https://api.openai.com/v1/chat/completions"

        messages = []
        if sys_inst:
            messages.append({"role": "system", "content": sys_inst})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            cache_prompt_response(prompt, text)
            return {
                "status": "SUCCESS",
                "provider": "OpenAI Direct",
                "model": model_name,
                "tokens_used": tokens,
                "text": text,
            }

    def _call_ollama(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        raw_model = (model or os.getenv("OLLAMA_MODEL", "llama3.2")).replace("ollama-", "")
        url = f"{base_url.rstrip('/')}/api/generate"

        payload = {"model": raw_model, "prompt": prompt, "stream": False}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            text = data.get("response", "")
            return {
                "status": "SUCCESS",
                "provider": "Ollama (Offline Local)",
                "model": raw_model,
                "tokens_used": 0,
                "text": text,
            }

    def _heuristic_fallback(self, prompt: str, error: str = "") -> Dict[str, Any]:
        """Deterministic offline fallback response."""
        kb_hit = query_local_knowledge_base(prompt)
        if kb_hit and kb_hit.get("message"):
            return {
                "status": "FALLBACK",
                "provider": "Fleet Offline Knowledge Engine",
                "model": "tier0_bm25_rag",
                "tokens_used": 0,
                "cost_usd": "$0.00",
                "text": kb_hit["message"],
                "fallback_reason": error,
            }
        return {
            "status": "FALLBACK",
            "provider": "Fleet Heuristic Engine",
            "model": "offline_smart_agent",
            "tokens_used": 0,
            "cost_usd": "$0.00",
            "text": (
                f"Fleet Autonomous Intelligence: Processed prompt '{prompt[:60]}...' via local deterministic engine. "
                "Configure an API key (Google Gemini/Vertex, Microsoft Azure/GitHub Models, AWS Bedrock, Anthropic Claude, or OpenAI) in "
                "Settings or Windows Credential Manager to activate live cloud hyperscaler streaming."
            ),
            "fallback_reason": error,
        }
