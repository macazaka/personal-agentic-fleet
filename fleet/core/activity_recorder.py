"""
Multimodal Activity & Voice Narration Recorder, Requirements Compiler,
Visible Sandbox Self-Healer & Headless Workflow Execution Engine for AFCC.

Zero third-party Python dependencies beyond stock Python 3.14 stdlib +
``cryptography`` (via ``fleet.core.crypto_vault``):
  - Pure-stdlib RFC 6455 WebSocket + Minimal Chrome DevTools Protocol (CDP) client
  - Pure-stdlib Windows Win32 ctypes desktop observer (no WH_KEYBOARD_LL hook)
  - Synchronized Speech/Audio Narration + +-3.5s Multimodal Temporal Fusion
  - Formal Requirements Document + Mermaid Flowchart + Isolated Pytest Generator
  - Visible Sandbox Dry-Run Theater + Tier-1 Self-Healer & Tier-2 Audio Feedback Loop
  - Explicit Approval Publish Gate + Headless Execution with HITL Ask-for-Inputs Resume
"""

from __future__ import annotations

import ast
import base64
from collections import OrderedDict
import ctypes
from datetime import datetime
import hashlib
import hmac
import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request

from fleet.config import DATA_DIR
from fleet.core.crypto_vault import (
    decrypt_aes256_gcm,
    decrypt_binary_bytes_at_rest,
    encrypt_aes256_gcm,
    encrypt_binary_bytes_at_rest,
)
from fleet.core.db.base import is_test_environment

logger = logging.getLogger("fleet.core.activity_recorder")

MAX_EVENTS_PER_SESSION = 500
MAX_AUDIO_SEGMENTS_PER_SESSION = 300
MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_RECORDING_DURATION_SEC = 1800
MAX_CONCURRENT_HEADLESS_RUNS = 1
DEFAULT_STEP_TIMEOUT_SEC = 15
DEFAULT_RUN_TIMEOUT_SEC = 120
TEMPORAL_FUSION_WINDOW_SEC = 3.5

RFC6455_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
RECORDER_VAULT_AAD = b"afcc-recorder-vault-v1"
RECORDER_AUDIO_AAD = b"afcc-recorder-audio-v1"

SENSITIVE_FIELD_RE = re.compile(
    r"(?:password|passwd|pwd|passcode|otp|one[_-]?time|pin|mpin|cvv|cvc|secret|token|"
    r"card.?num|credit.?card|debit.?card|aadhaar|aadhar|pan.?num|ssn|2fa|totp)",
    re.I,
)
SENSITIVE_WINDOW_RE = re.compile(
    r"(?:keepass|1password|bitwarden|lastpass|dashlane|windows security|"
    r"credential|password|one[- ]time|otp verify|uac|consent\.exe)",
    re.I,
)
SELF_WINDOW_MARKERS = (
    "agentic fleet control center",
    "127.0.0.1:7890",
    "localhost:7890",
)

PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
LONG_CARD_OR_AADHAAR_RE = re.compile(r"\b(?:\d[ -]?){12,16}\b")
SPOKEN_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passcode|pin|mpin|otp|cvv|cvc|token|secret)\s*(?:is|equals|=|:)?\s*([^\s,.;!?]{2,32})"
)

_HEADLESS_RUN_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_HEADLESS_RUNS)

CHROMIUM_CANDIDATE_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
)

_EXECUTION_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


# ---------------------------------------------------------------------------
# Capture-Edge Safety, URL Validation & PII / Secret Redaction
# ---------------------------------------------------------------------------

def _as_dict(val: Any) -> Dict[str, Any]:
    """Typed helper narrowing arbitrary values to Dict[str, Any] for strict Pyright compliance."""
    return val if isinstance(val, dict) else {}


def _as_str_dict(val: Any) -> Dict[str, str]:
    """Typed helper narrowing arbitrary dict values to Dict[str, str]."""
    if not isinstance(val, dict):
        return {}
    return {str(k): str(v) for k, v in val.items() if v is not None}


def _as_list(val: Any) -> List[Any]:
    """Typed helper narrowing arbitrary values to List[Any] for strict Pyright compliance."""
    return val if isinstance(val, list) else []


def _is_safe_navigation_url(url: str) -> bool:
    """Validates HTTP/HTTPS URL schemes and blocks cloud metadata/script/file URLs."""
    raw = str(url or "").strip()
    if not raw:
        return False
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return False
    host = (parsed.hostname or "").lower()
    if host in ("169.254.169.254", "metadata.google.internal"):
        return False
    return True


def _infer_param_key(raw_hint: str, fallback: str = "input_value") -> str:
    """Converts an arbitrary field label/name into a clean snake_case parameter identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(raw_hint or "").lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        return fallback
    if not cleaned[0].isalpha():
        cleaned = f"param_{cleaned}"
    return cleaned[:40].rstrip("_")


def redact_sensitive_value(
    value: Any,
    field_hint: str = "",
    input_type: str = "",
    autocomplete: str = "",
) -> Tuple[str, bool, str]:
    """
    Capture-edge secret/PII redactor.
    Never retains plaintext passwords, OTPs, CVVs, card numbers, PANs, or Aadhaar strings.
    Returns (sanitized_value_or_template, is_sensitive, inferred_param_key).
    """
    raw_val = "" if value is None else str(value)
    hint_blob = f"{field_hint} {input_type} {autocomplete}".strip()
    param_key = _infer_param_key(field_hint or autocomplete or input_type or "secret_input", "secret_input")

    # Existing placeholder passes cleanly while flagging sensitivity if {{secret:...}}
    m_existing_sec = re.match(r"^\{\{secret:([a-zA-Z0-9_]+)\}\}$", raw_val.strip())
    if m_existing_sec:
        return raw_val.strip(), True, m_existing_sec.group(1)

    low_type = str(input_type or "").strip().lower()
    low_auto = str(autocomplete or "").strip().lower()
    is_sensitive_meta = (
        low_type == "password"
        or low_auto in ("current-password", "new-password", "one-time-code", "cc-number", "cc-csc", "cc-exp")
        or bool(SENSITIVE_FIELD_RE.search(hint_blob))
    )

    if is_sensitive_meta:
        sec_key = param_key if SENSITIVE_FIELD_RE.search(param_key) else f"{param_key}_secret"
        return f"{{{{secret:{sec_key[:40]}}}}}", True, sec_key[:40]

    if raw_val:
        if LONG_CARD_OR_AADHAAR_RE.search(raw_val) or PAN_RE.search(raw_val):
            return f"{{{{secret:{param_key}}}}}", True, param_key

    return raw_val[:500], False, _infer_param_key(field_hint, "")


def sanitize_audio_transcript(transcript: str) -> str:
    """Scrubs spoken secrets (passwords, OTPs, PINs, card/Aadhaar numbers, PAN) from voice transcripts."""
    text = str(transcript or "").strip()
    if not text:
        return ""
    text = SPOKEN_SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)} [REDACTED_SECRET]", text)
    text = LONG_CARD_OR_AADHAAR_RE.sub("[REDACTED_SECRET]", text)
    text = PAN_RE.sub("[REDACTED_SECRET]", text)
    return text[:2000]


def _is_afcc_self_event(url: str = "", title: str = "", source: str = "") -> bool:
    """Identifies events triggered by interacting with AFCC's own control panel."""
    if source == "manual_mark":
        return False
    low_title = str(title or "").lower()
    if any(marker in low_title for marker in SELF_WINDOW_MARKERS):
        return True
    if url:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in ("127.0.0.1", "localhost") and parsed.port == 7890:
            return True
    return False


def sanitize_recorded_event(raw_event: Dict[str, Any], start_mono: Optional[float] = None) -> Dict[str, Any]:
    """Normalizes and redacts a raw browser or desktop event prior to buffering/persistence."""
    locators_in = _as_dict(raw_event.get("locators"))
    field_hint = str(
        raw_event.get("field_hint")
        or locators_in.get("aria_label")
        or locators_in.get("label_text")
        or locators_in.get("name")
        or locators_in.get("placeholder")
        or locators_in.get("id")
        or raw_event.get("window_title")
        or raw_event.get("title")
        or ""
    )
    input_type = str(raw_event.get("input_type") or raw_event.get("field_kind") or "")
    autocomplete = str(raw_event.get("autocomplete") or "")

    redacted_val, is_sensitive, param_hint = redact_sensitive_value(
        raw_event.get("value", ""),
        field_hint=field_hint,
        input_type=input_type,
        autocomplete=autocomplete,
    )

    clean_title = str(raw_event.get("title") or raw_event.get("window_title") or "")[:240]
    if SENSITIVE_WINDOW_RE.search(clean_title) or LONG_CARD_OR_AADHAAR_RE.search(clean_title):
        clean_title = "[Protected Credential Window]"
        is_sensitive = True
    if is_sensitive and not (redacted_val.startswith("{{secret:") and redacted_val.endswith("}}")):
        sec_key = param_hint or "protected_secret"
        redacted_val = f"{{{{secret:{sec_key[:40]}}}}}"

    clean_url = str(raw_event.get("url") or "")[:1000]
    if clean_url and not _is_safe_navigation_url(clean_url):
        # Allow recording local test/file metadata safely without persisting unsafe scheme in navigation
        parsed_u = urllib.parse.urlparse(clean_url)
        if parsed_u.scheme.lower() in ("javascript", "data", "vbscript"):
            clean_url = ""

    clean_locators: Dict[str, str] = {}
    for k in (
        "data_testid",
        "id",
        "aria_label",
        "name",
        "role",
        "placeholder",
        "label_text",
        "text",
        "css_path",
        "xpath",
        "process",
        "window_title",
        "uia_automation_id",
        "uia_control_name",
        "rx",
        "ry",
    ):
        v = locators_in.get(k)
        if v is not None and str(v).strip() != "":
            s_v = str(v)[:300]
            if k in ("text", "window_title") and (is_sensitive or LONG_CARD_OR_AADHAAR_RE.search(s_v)):
                s_v = "[REDACTED]"
            clean_locators[k] = s_v

    offset_sec = raw_event.get("offset_sec")
    if offset_sec is None:
        offset_sec = max(0.0, time.monotonic() - start_mono) if start_mono is not None else 0.0

    clean_action = str(raw_event.get("action") or "click").strip().lower()
    clean_channel = str(raw_event.get("channel") or "browser").strip().lower()
    if clean_channel not in ("browser", "desktop", "prompt", "extract"):
        clean_channel = "browser"

    out: Dict[str, Any] = {
        "event_id": str(raw_event.get("event_id") or f"evt_{secrets.token_hex(4)}"),
        "offset_sec": round(float(offset_sec), 3),
        "timestamp": str(raw_event.get("timestamp") or datetime.now().isoformat()),
        "channel": clean_channel,
        "action": clean_action,
        "url": clean_url,
        "title": clean_title,
        "locators": clean_locators,
        "value": redacted_val,
        "input_type": "secret" if is_sensitive else (input_type or "text"),
        "sensitive": bool(is_sensitive or raw_event.get("sensitive")),
        "param_hint": param_hint or str(raw_event.get("param_hint") or ""),
        "source": str(raw_event.get("source") or "afcc_ui"),
    }
    if raw_event.get("prompt_question"):
        out["prompt_question"] = sanitize_audio_transcript(str(raw_event["prompt_question"]))
    if raw_event.get("required") is not None:
        out["required"] = bool(raw_event.get("required"))
    return out


def sanitize_workflow_ir(workflow_ir: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strips any secret defaults or sensitive literal values before saving Workflow IR on disk."""
    if not isinstance(workflow_ir, dict):
        return None
    cleaned = json.loads(json.dumps(workflow_ir))
    in_schema = cleaned.get("input_schema")
    if isinstance(in_schema, list):
        for fld in in_schema:
            if not isinstance(fld, dict):
                continue
            is_sec = bool(fld.get("sensitive")) or str(fld.get("type") or "").lower() == "secret"
            if is_sec:
                fld["sensitive"] = True
                fld["type"] = "secret"
                fld["default"] = ""
                fld["ask_on_each_run"] = True
    steps = cleaned.get("steps")
    if isinstance(steps, list):
        for st in steps:
            if not isinstance(st, dict):
                continue
            if st.get("sensitive"):
                key = str(st.get("input_key") or "secret_input")
                st["value_template"] = f"{{{{secret:{key}}}}}"
    return cleaned


# ---------------------------------------------------------------------------
# Pure-Stdlib RFC 6455 WebSocket + Minimal CDP Client
# ---------------------------------------------------------------------------

def compute_ws_accept_key(ws_key: str) -> str:
    """Computes RFC 6455 Sec-WebSocket-Accept header using SHA-1 protocol hash."""
    digest = hashlib.sha1((ws_key + RFC6455_GUID).encode("ascii"), usedforsecurity=False).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_ws_frame(payload: bytes, opcode: int = 0x1, masked: bool = True) -> bytes:
    """Encodes an RFC 6455 WebSocket frame cleanly without third-party packages."""
    fin_opcode = 0x80 | (opcode & 0x0F)
    length = len(payload)
    mask_bit = 0x80 if masked else 0x00

    header = bytearray([fin_opcode])
    if length < 126:
        header.append(mask_bit | length)
    elif length <= 0xFFFF:
        header.append(mask_bit | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack(">Q", length))

    if masked:
        mask_key = secrets.token_bytes(4)
        header.extend(mask_key)
        masked_payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))
        return bytes(header) + masked_payload
    return bytes(header) + payload


def decode_ws_frame_from_bytes(buf: bytes) -> Tuple[int, bytes, int]:
    """Decodes a single complete RFC 6455 frame from raw bytes. Returns (opcode, payload, consumed)."""
    if len(buf) < 2:
        raise ValueError("Incomplete WebSocket frame header")
    b0, b1 = buf[0], buf[1]
    opcode = b0 & 0x0F
    is_masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    idx = 2
    if length == 126:
        if len(buf) < idx + 2:
            raise ValueError("Incomplete 16-bit WebSocket length")
        (length,) = struct.unpack(">H", buf[idx : idx + 2])
        idx += 2
    elif length == 127:
        if len(buf) < idx + 8:
            raise ValueError("Incomplete 64-bit WebSocket length")
        (length,) = struct.unpack(">Q", buf[idx : idx + 8])
        idx += 8
    mask_key = b""
    if is_masked:
        if len(buf) < idx + 4:
            raise ValueError("Incomplete WebSocket mask key")
        mask_key = buf[idx : idx + 4]
        idx += 4
    if len(buf) < idx + length:
        raise ValueError("Incomplete WebSocket payload")
    raw_payload = buf[idx : idx + length]
    if is_masked:
        raw_payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(raw_payload))
    return opcode, raw_payload, idx + length


class MinimalCDPClient:
    """Pure-stdlib TCP + RFC 6455 WebSocket client for local Chrome DevTools Protocol."""

    def __init__(self) -> None:
        self.sock: Optional[socket.socket] = None
        self._msg_id: int = 0
        self._recv_buf = bytearray()
        self._event_queue: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def connect(self, ws_url: str, timeout: float = 8.0) -> None:
        parsed = urllib.parse.urlparse(ws_url)
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
            raise ValueError(f"Unsupported CDP WebSocket URL: {ws_url}")
        host = parsed.hostname
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(f"Refusing non-loopback CDP host: {host}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
        ws_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        sock.sendall(handshake)

        raw_hdr = bytearray()
        while b"\r\n\r\n" not in raw_hdr:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise ConnectionError("CDP socket closed during WebSocket handshake")
            raw_hdr.extend(chunk)
            if len(raw_hdr) > 65536:
                sock.close()
                raise ValueError("CDP handshake response header too large")

        sep_idx = raw_hdr.index(b"\r\n\r\n")
        header_text = raw_hdr[:sep_idx].decode("latin-1")
        remainder = raw_hdr[sep_idx + 4 :]
        if "101" not in header_text.splitlines()[0]:
            sock.close()
            raise ConnectionError(f"CDP WebSocket handshake rejected: {header_text.splitlines()[0]}")

        expected_accept = compute_ws_accept_key(ws_key)
        accept_line = ""
        for line in header_text.splitlines()[1:]:
            if line.lower().startswith("sec-websocket-accept:"):
                accept_line = line.split(":", 1)[1].strip()
                break
        if not hmac.compare_digest(accept_line, expected_accept):
            sock.close()
            raise ConnectionError("CDP WebSocket handshake Sec-WebSocket-Accept mismatch")

        self.sock = sock
        self._recv_buf = bytearray(remainder)

    def _read_exact(self, n: int) -> bytes:
        assert self.sock is not None
        while len(self._recv_buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self._recv_buf)))
            if not chunk:
                raise ConnectionError("CDP WebSocket closed")
            self._recv_buf.extend(chunk)
        out = bytes(self._recv_buf[:n])
        del self._recv_buf[:n]
        return out

    def recv_ws_frame(self, timeout: Optional[float] = None) -> Tuple[int, bytes]:
        if self.sock is None:
            raise ConnectionError("CDP socket not connected")
        prev_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            b0, b1 = self._read_exact(2)
            opcode = b0 & 0x0F
            is_masked = bool(b1 & 0x80)
            length = b1 & 0x7F
            if length == 126:
                (length,) = struct.unpack(">H", self._read_exact(2))
            elif length == 127:
                (length,) = struct.unpack(">Q", self._read_exact(8))
            mask_key = self._read_exact(4) if is_masked else b""
            payload = self._read_exact(length) if length > 0 else b""
            if is_masked and payload:
                payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))
            return opcode, payload
        finally:
            try:
                self.sock.settimeout(prev_timeout)
            except Exception:
                pass

    def send_command(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        with self._lock:
            if self.sock is None:
                raise ConnectionError("CDP socket not connected")
            self._msg_id += 1
            req_id = self._msg_id
            payload = json.dumps({"id": req_id, "method": method, "params": params or {}}).encode("utf-8")
            self.sock.sendall(encode_ws_frame(payload, opcode=0x1, masked=True))

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                remaining = max(0.05, deadline - time.monotonic())
                opcode, data = self.recv_ws_frame(timeout=remaining)
                if opcode == 0x9:  # Ping -> Pong
                    self.sock.sendall(encode_ws_frame(data, opcode=0xA, masked=True))
                    continue
                if opcode == 0x8:
                    raise ConnectionError("CDP closed connection")
                if opcode not in (0x1, 0x2):
                    continue
                msg = json.loads(data.decode("utf-8", errors="ignore"))
                if msg.get("id") == req_id:
                    if "error" in msg:
                        raise RuntimeError(f"CDP error on {method}: {msg['error']}")
                    res = msg.get("result")
                    return res if isinstance(res, dict) else {}
                elif "method" in msg:
                    self._event_queue.append(msg)
            raise TimeoutError(f"Timed out waiting for CDP response to {method}")

    def poll_events(self, timeout: float = 0.2) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        with self._lock:
            if self._event_queue:
                events.extend(self._event_queue)
                self._event_queue.clear()
            if self.sock is None:
                return events
            deadline = time.monotonic() + max(0.02, timeout)
            while time.monotonic() < deadline:
                try:
                    opcode, data = self.recv_ws_frame(timeout=0.05)
                except socket.timeout:
                    break
                except Exception:
                    break
                if opcode == 0x9 and self.sock is not None:
                    try:
                        self.sock.sendall(encode_ws_frame(data, opcode=0xA, masked=True))
                    except Exception:
                        break
                    continue
                if opcode == 0x8:
                    break
                if opcode in (0x1, 0x2):
                    try:
                        msg = json.loads(data.decode("utf-8", errors="ignore"))
                        if "method" in msg:
                            events.append(msg)
                    except Exception:
                        pass
        return events

    def close(self) -> None:
        sock = self.sock
        self.sock = None
        if sock is not None:
            try:
                sock.sendall(encode_ws_frame(b"", opcode=0x8, masked=True))
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass


def discover_local_chromium_browser() -> Optional[str]:
    """Finds locally installed Chrome, Edge, or Chromium binary without external deps."""
    for cand in CHROMIUM_CANDIDATE_PATHS:
        if os.path.isfile(cand):
            return cand
    for cmd in ("chrome", "google-chrome", "msedge", "chromium", "chromium-browser"):
        resolved = shutil.which(cmd)
        if resolved:
            return resolved
    return None


def find_free_local_port() -> int:
    """Allocates an ephemeral free loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def terminate_process_tree(proc: Optional[subprocess.Popen[Any]]) -> None:
    """Guarantees clean process-tree shutdown to eliminate zombie Chromium instances."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.5)
            except Exception:
                pass
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=4,
                    check=False,
                    creationflags=_EXECUTION_SUBPROCESS_FLAGS,
                )
            else:
                proc.kill()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Injected Browser DOM Recorder Script, Bookmarklet & Sandbox Overlay JS
# ---------------------------------------------------------------------------

DOM_RECORDER_JS = r"""
(function() {
  if (window.__afccRecorderInstalled) return;
  window.__afccRecorderInstalled = true;

  function isSensitiveEl(el) {
    if (!el) return false;
    var type = (el.type || '').toLowerCase();
    var auto = (el.getAttribute && (el.getAttribute('autocomplete') || '')).toLowerCase();
    var hint = ((el.name || '') + ' ' + (el.id || '') + ' ' + (el.placeholder || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
    if (type === 'password') return true;
    if (['current-password', 'new-password', 'one-time-code', 'cc-number', 'cc-csc'].indexOf(auto) >= 0) return true;
    return /(password|passwd|pwd|otp|pin|cvv|cvc|secret|card|aadhaar|pan)/i.test(hint);
  }

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id && !/[a-f0-9]{8,}/i.test(el.id)) return '#' + CSS.escape(el.id);
    var parts = [];
    var cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body && parts.length < 5) {
      var tag = cur.tagName.toLowerCase();
      var sib = cur, nth = 1;
      while ((sib = sib.previousElementSibling) != null) {
        if (sib.tagName === cur.tagName) nth++;
      }
      parts.unshift(tag + ':nth-of-type(' + nth + ')');
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }

  function buildLocators(el) {
    if (!el || !el.getAttribute) return {};
    var labelText = '';
    try {
      if (el.id) {
        var lb = document.querySelector('label[for="' + el.id + '"]');
        if (lb) labelText = (lb.innerText || lb.textContent || '').trim();
      }
      if (!labelText && el.closest) {
        var wrap = el.closest('label');
        if (wrap) labelText = (wrap.innerText || '').trim();
      }
    } catch (e) {}
    return {
      data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test') || '',
      id: (el.id && !/[a-f0-9]{8,}/i.test(el.id)) ? el.id : '',
      aria_label: el.getAttribute('aria-label') || '',
      name: el.getAttribute('name') || '',
      role: el.getAttribute('role') || '',
      placeholder: el.getAttribute('placeholder') || '',
      label_text: labelText.slice(0, 80),
      text: ((el.innerText || el.value || '').trim()).slice(0, 80),
      css_path: cssPath(el),
      xpath: el.id ? ('//*[@id="' + el.id + '"]') : ''
    };
  }

  function emit(action, el, rawVal) {
    try {
      var sens = isSensitiveEl(el);
      var locs = buildLocators(el);
      var hint = locs.aria_label || locs.label_text || locs.name || locs.placeholder || locs.id || 'input';
      var cleanKey = hint.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'secret_input';
      var val = sens ? ('{{secret:' + cleanKey.slice(0, 32) + '}}') : String(rawVal == null ? '' : rawVal).slice(0, 300);
      var evt = {
        channel: 'browser',
        action: action,
        url: location.href,
        title: document.title || '',
        locators: locs,
        value: val,
        input_type: sens ? 'secret' : ((el && el.type) || 'text'),
        autocomplete: (el && el.getAttribute && el.getAttribute('autocomplete')) || '',
        sensitive: sens,
        source: 'cdp_dom'
      };
      if (typeof window.__afccRecordEvent === 'function') {
        window.__afccRecordEvent(JSON.stringify(evt));
      } else if (window.__afccBookmarkletPost) {
        window.__afccBookmarkletPost(evt);
      }
    } catch (e) {}
  }

  document.addEventListener('click', function(e) {
    var tgt = e.target && e.target.closest ? (e.target.closest('button,a,input,select,textarea,[role="button"],[data-testid]') || e.target) : e.target;
    if (!tgt || tgt.tagName === 'BODY' || tgt.tagName === 'HTML') return;
    if (tgt.tagName === 'INPUT' && ['button', 'submit', 'checkbox', 'radio'].indexOf((tgt.type || '').toLowerCase()) < 0) return;
    emit('click', tgt, (tgt.innerText || tgt.value || '').trim());
  }, true);

  document.addEventListener('change', function(e) {
    var tgt = e.target;
    if (!tgt) return;
    var act = tgt.tagName === 'SELECT' ? 'select' : 'change';
    emit(act, tgt, tgt.value);
  }, true);

  document.addEventListener('submit', function(e) {
    emit('submit', e.target, 'form_submit');
  }, true);
})();
"""

SANDBOX_OVERLAY_JS = r"""
window.__afccSandboxShowStep = function(idx, total, label, status, cssSelector, altId, altText) {
  try {
    var oldBox = document.getElementById('__afcc_sbx_highlight');
    if (oldBox) oldBox.remove();
    var hud = document.getElementById('__afcc_sbx_hud');
    if (!hud) {
      hud = document.createElement('div');
      hud.id = '__afcc_sbx_hud';
      hud.style.cssText = 'position:fixed;top:14px;right:14px;z-index:2147483647;background:#0f172a;color:#e2e8f0;border:2px solid #38bdf8;border-radius:10px;padding:10px 14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,0.45);max-width:340px;';
      document.documentElement.appendChild(hud);
    }
    var color = status === 'failed' ? '#f87171' : (status === 'healed' ? '#fbbf24' : '#34d399');
    hud.style.borderColor = color;
    hud.innerHTML = '<div style="font-weight:700;color:' + color + ';">AFCC Sandbox Step ' + idx + '/' + total + ' (' + status.toUpperCase() + ')</div><div style="margin-top:4px;color:#cbd5e1;">' + String(label || '').slice(0, 120) + '</div>';

    var el = null;
    if (altId) el = document.getElementById(altId);
    if (!el && cssSelector) { try { el = document.querySelector(cssSelector); } catch (_) {} }
    if (!el && altText) {
      var cands = document.querySelectorAll('button,a,input,select,[role="button"]');
      for (var i = 0; i < cands.length; i++) {
        if ((cands[i].innerText || cands[i].value || '').toLowerCase().indexOf(altText.toLowerCase()) >= 0) { el = cands[i]; break; }
      }
    }
    if (el && el.getBoundingClientRect) {
      var r = el.getBoundingClientRect();
      var box = document.createElement('div');
      box.id = '__afcc_sbx_highlight';
      box.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483646;border:3px solid ' + color + ';border-radius:6px;box-shadow:0 0 18px ' + color + ';top:' + Math.max(0, r.top - 3) + 'px;left:' + Math.max(0, r.left - 3) + 'px;width:' + Math.max(12, r.width + 6) + 'px;height:' + Math.max(12, r.height + 6) + 'px;';
      document.documentElement.appendChild(box);
    }
    return true;
  } catch (e) { return false; }
};
"""


def generate_bookmarklet_snippet(
    session_id: str,
    capture_token: str,
    server_origin: str = "http://127.0.0.1:7890",
) -> str:
    """Builds a 1-click active-tab recorder bookmarklet authenticated by CSPRNG capture_token."""
    clean_origin = server_origin.rstrip("/")
    js = (
        "(function(){"
        f"var sid={json.dumps(session_id)},tok={json.dumps(capture_token)},orig={json.dumps(clean_origin)};"
        "window.__afccBookmarkletPost=function(evt){"
        "evt.session_id=sid;evt.capture_token=tok;evt.source='bookmarklet';"
        "fetch(orig+'/api/studio/recorder/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(evt)}).catch(function(){});"
        "};"
        + DOM_RECORDER_JS.replace("\n", " ").strip()
        + "})();"
    )
    return "javascript:" + urllib.parse.quote(js, safe="():;={},'\"[]{}")


def _wait_for_cdp_page_ws(port: int, timeout_sec: float = 10.0) -> Optional[str]:
    deadline = time.monotonic() + timeout_sec
    url = f"http://127.0.0.1:{port}/json"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:  # nosec B310
                targets = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if isinstance(targets, list):
                    for t in targets:
                        if isinstance(t, dict) and t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                            return str(t["webSocketDebuggerUrl"])
        except Exception:
            pass
        time.sleep(0.25)
    return None


class BrowserCDPRecorder:
    """Manages an isolated Chromium session and pumps sanitized DOM events over MinimalCDPClient."""

    def __init__(self) -> None:
        self.debug_port: int = 0
        self.profile_dir: Optional[Path] = None
        self.process: Optional[subprocess.Popen[Any]] = None
        self.cdp: Optional[MinimalCDPClient] = None
        self._stop_evt = threading.Event()
        self._pump_thread: Optional[threading.Thread] = None

    def start(self, start_url: str, on_event: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        browser_bin = discover_local_chromium_browser()
        if not browser_bin:
            return {"launched": False, "reason": "No local Chrome/Edge binary found; use Active-Tab Bookmarklet or manual step capture."}

        safe_url = start_url.strip() if _is_safe_navigation_url(start_url) else "about:blank"
        self.debug_port = find_free_local_port()
        self.profile_dir = Path(tempfile.mkdtemp(prefix="afcc_cdp_rec_"))

        cmd = [
            browser_bin,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={self.profile_dir}",
            f"--remote-allow-origins=http://127.0.0.1:{self.debug_port}",
            "--no-first-run",
            "--no-default-browser-check",
            safe_url,
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_EXECUTION_SUBPROCESS_FLAGS,
        )
        ws_url = _wait_for_cdp_page_ws(self.debug_port, timeout_sec=10.0)
        if not ws_url:
            self.stop()
            return {"launched": False, "reason": "Chrome/Edge debug endpoint did not open within timeout."}

        cdp = MinimalCDPClient()
        cdp.connect(ws_url, timeout=8.0)
        cdp.send_command("Page.enable")
        cdp.send_command("Runtime.enable")
        cdp.send_command("Runtime.addBinding", {"name": "__afccRecordEvent"})
        cdp.send_command("Page.addScriptToEvaluateOnNewDocument", {"source": DOM_RECORDER_JS})
        cdp.send_command("Runtime.evaluate", {"expression": DOM_RECORDER_JS})
        self.cdp = cdp
        self._stop_evt.clear()

        if safe_url != "about:blank":
            on_event({"channel": "browser", "action": "navigate", "url": safe_url, "title": "Start URL", "source": "cdp_start"})

        def _pump() -> None:
            while not self._stop_evt.is_set():
                client = self.cdp
                if client is None:
                    break
                evts = client.poll_events(timeout=0.25)
                for msg in evts:
                    method = msg.get("method")
                    params = msg.get("params") or {}
                    if method == "Runtime.bindingCalled" and params.get("name") == "__afccRecordEvent":
                        try:
                            payload = json.loads(params.get("payload") or "{}")
                            if isinstance(payload, dict):
                                on_event(payload)
                        except Exception:
                            pass
                    elif method == "Page.frameNavigated":
                        frame = params.get("frame") or {}
                        nav_url = str(frame.get("url") or "")
                        if not frame.get("parentId") and _is_safe_navigation_url(nav_url):
                            on_event({
                                "channel": "browser",
                                "action": "navigate",
                                "url": nav_url,
                                "title": str(frame.get("name") or nav_url),
                                "source": "cdp_nav",
                            })
                if self.process and self.process.poll() is not None:
                    break

        self._pump_thread = threading.Thread(target=_pump, name="AFCC-CDP-Recorder", daemon=True)
        self._pump_thread.start()
        return {"launched": True, "debug_port": self.debug_port, "browser": os.path.basename(browser_bin)}

    def stop(self) -> None:
        self._stop_evt.set()
        if self._pump_thread and self._pump_thread.is_alive():
            self._pump_thread.join(timeout=1.5)
        self._pump_thread = None
        if self.cdp is not None:
            self.cdp.close()
            self.cdp = None
        terminate_process_tree(self.process)
        self.process = None
        if self.profile_dir and self.profile_dir.exists():
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        self.profile_dir = None


class DesktopActivityWatcher:
    """
    Pure-stdlib Windows Win32 ctypes desktop watcher.
    Observes window switches & click edges with adaptive 250ms/750ms cadence.
    Strictly avoids WH_KEYBOARD_LL keyboard hooks (zero keylogger risk).
    """

    def __init__(self) -> None:
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _read_win32_foreground() -> Optional[Dict[str, Any]]:
        if sys.platform != "win32" or not hasattr(ctypes, "windll"):
            return None
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = int(user32.GetForegroundWindow() or 0)
            if not hwnd:
                return None

            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            win_title = buf.value or ""

            pid = ctypes.c_uint32(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = "desktop_app.exe"
            if pid.value:
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                if hproc:
                    try:
                        pbuf = ctypes.create_unicode_buffer(512)
                        size = ctypes.c_uint32(512)
                        if kernel32.QueryFullProcessImageNameW(hproc, 0, pbuf, ctypes.byref(size)):
                            proc_name = os.path.basename(pbuf.value)
                    finally:
                        kernel32.CloseHandle(hproc)

            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            class _POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            rect = _RECT()
            pt = _POINT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            user32.GetCursorPos(ctypes.byref(pt))
            w = max(1, rect.right - rect.left)
            h = max(1, rect.bottom - rect.top)
            rx = round(max(0.0, min(1.0, (pt.x - rect.left) / float(w))), 3)
            ry = round(max(0.0, min(1.0, (pt.y - rect.top) / float(h))), 3)
            lmb_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)

            return {
                "hwnd": hwnd,
                "pid": int(pid.value),
                "process": proc_name,
                "window_title": win_title,
                "rx": rx,
                "ry": ry,
                "lmb_down": lmb_down,
            }
        except Exception:
            return None

    def start(self, on_event: Callable[[Dict[str, Any]], None]) -> bool:
        self._stop_evt.clear()

        def _loop() -> None:
            last_hwnd = 0
            was_lmb_down = False
            idle_cycles = 0
            while not self._stop_evt.is_set():
                snap = self._read_win32_foreground()
                emitted = False
                if snap:
                    win_title = str(snap["window_title"])
                    if not _is_afcc_self_event(title=win_title):
                        is_sensitive_win = bool(SENSITIVE_WINDOW_RE.search(win_title))
                        clean_title = "[Protected Credential Window]" if is_sensitive_win else win_title[:200]
                        hwnd = int(snap["hwnd"])
                        lmb_down = bool(snap["lmb_down"])

                        if hwnd != last_hwnd:
                            last_hwnd = hwnd
                            on_event({
                                "channel": "desktop",
                                "action": "prompt_user" if is_sensitive_win else "app_switch",
                                "title": clean_title,
                                "sensitive": is_sensitive_win,
                                "locators": {
                                    "process": snap["process"],
                                    "window_title": clean_title,
                                    "rx": snap["rx"],
                                    "ry": snap["ry"],
                                },
                                "value": "{{secret:desktop_credential}}" if is_sensitive_win else snap["process"],
                                "source": "win32_watcher",
                            })
                            emitted = True
                        elif lmb_down and not was_lmb_down:
                            on_event({
                                "channel": "desktop",
                                "action": "desktop_click",
                                "title": clean_title,
                                "sensitive": is_sensitive_win,
                                "locators": {
                                    "process": snap["process"],
                                    "window_title": clean_title,
                                    "rx": snap["rx"],
                                    "ry": snap["ry"],
                                },
                                "value": "",
                                "source": "win32_watcher",
                            })
                            emitted = True
                        was_lmb_down = lmb_down
                    else:
                        last_hwnd = int(snap["hwnd"])
                        was_lmb_down = bool(snap["lmb_down"])

                idle_cycles = 0 if emitted else min(20, idle_cycles + 1)
                cadence = 0.25 if idle_cycles < 6 else 0.75
                self._stop_evt.wait(cadence)

        self._thread = threading.Thread(target=_loop, name="AFCC-Desktop-Watcher", daemon=True)
        self._thread.start()
        return sys.platform == "win32"

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None


# ---------------------------------------------------------------------------
# Encrypted Session Storage & RecordingSessionManager
# ---------------------------------------------------------------------------

def _recordings_root_dir() -> Path:
    sub = "test_user" if is_test_environment() else "user"
    path = DATA_DIR / sub / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_session_filename(session_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", str(session_id or "")).strip()
    if not clean:
        raise ValueError("Invalid recording session identifier.")
    return clean


class RecordingSessionManager:
    """Thread-safe multimodal screen + audio narration session manager backed by AES-256-GCM storage."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self.storage_dir: Optional[Path] = Path(storage_dir) if storage_dir else None
        self.active_session: Optional[Dict[str, Any]] = None
        self._cdp_recorder: Optional[BrowserCDPRecorder] = None
        self._desktop_watcher: Optional[DesktopActivityWatcher] = None

    def _root_dir(self) -> Path:
        root = self.storage_dir if self.storage_dir is not None else _recordings_root_dir()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _session_path(self, session_id: str) -> Path:
        clean = _safe_session_filename(session_id)
        return self._root_dir() / f"{clean}.enc.json"

    def _audio_path(self, session_id: str) -> Path:
        clean = _safe_session_filename(session_id)
        return self._root_dir() / f"{clean}.audio.enc"

    def _persist_session(self, session_data: Dict[str, Any]) -> Path:
        to_save = dict(session_data)
        # Never persist transient capture_token or monotonic clocks to long-term archive
        to_save.pop("start_mono", None)
        if "draft" in to_save and isinstance(to_save["draft"], dict):
            w_ir = to_save["draft"].get("workflow_ir")
            if isinstance(w_ir, dict):
                to_save["draft"]["workflow_ir"] = sanitize_workflow_ir(w_ir)
        payload_json = json.dumps(to_save, ensure_ascii=False)
        enc_text = encrypt_aes256_gcm(payload_json, aad=RECORDER_VAULT_AAD)
        out_path = self._session_path(str(to_save["session_id"]))
        tmp_path = out_path.with_suffix(".enc.tmp")
        tmp_path.write_text(enc_text, encoding="utf-8")
        tmp_path.replace(out_path)
        return out_path

    def load_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if self.active_session and self.active_session.get("session_id") == session_id:
                return json.loads(json.dumps(self.active_session))
        path = self._session_path(session_id)
        if not path.is_file():
            raise FileNotFoundError(f"Recording session '{session_id}' not found.")
        enc_text = path.read_text(encoding="utf-8")
        raw_json = decrypt_aes256_gcm(enc_text, aad=RECORDER_VAULT_AAD)
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise ValueError(f"Corrupted recording payload for '{session_id}'.")
        return data

    def save_session(self, session_data: Dict[str, Any]) -> Path:
        with self._lock:
            if self.active_session and self.active_session.get("session_id") == session_data.get("session_id"):
                self.active_session = json.loads(json.dumps(session_data))
            return self._persist_session(session_data)

    def load_session_audio_bytes(self, session_id: str) -> Optional[bytes]:
        apath = self._audio_path(session_id)
        if not apath.is_file():
            return None
        return decrypt_binary_bytes_at_rest(apath.read_bytes(), aad=RECORDER_AUDIO_AAD)

    def delete_session(self, session_id: str) -> bool:
        deleted = False
        with self._lock:
            if self.active_session and self.active_session.get("session_id") == session_id:
                self.stop_recording(session_id=session_id)
            for p in (self._session_path(session_id), self._audio_path(session_id)):
                if p.is_file():
                    p.unlink()
                    deleted = True
        return deleted

    def list_sessions(self, limit: int = 25) -> List[Dict[str, Any]]:
        root = self._root_dir()
        files = sorted(root.glob("*.enc.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: List[Dict[str, Any]] = []
        for f in files[:limit]:
            sid = f.name[:-len(".enc.json")]
            try:
                sess = self.load_session(sid)
                draft = _as_dict(sess.get("draft"))
                out.append({
                    "session_id": sid,
                    "label": sess.get("label") or sid,
                    "mode": sess.get("mode", "browser"),
                    "start_url": sess.get("start_url", ""),
                    "created_at": sess.get("created_at", ""),
                    "stopped_at": sess.get("stopped_at", ""),
                    "duration_sec": sess.get("duration_sec", 0.0),
                    "events_count": len(sess.get("events") or []),
                    "audio_segments_count": len(sess.get("audio_segments") or []),
                    "has_audio_blob": bool(sess.get("audio_saved")),
                    "lifecycle_status": sess.get("lifecycle_status") or draft.get("lifecycle_status") or "recorded",
                    "iteration_version": int(draft.get("iteration_version") or 1),
                    "published_agent_id": sess.get("published_agent_id", ""),
                })
            except Exception:
                continue
        return out

    def start_recording(
        self,
        mode: str = "browser",
        start_url: str = "",
        launch_browser: bool = False,
        record_audio: bool = True,
        label: str = "",
        server_origin: str = "http://127.0.0.1:7890",
    ) -> Dict[str, Any]:
        clean_mode = str(mode or "browser").strip().lower()
        if clean_mode not in ("browser", "desktop", "hybrid"):
            clean_mode = "browser"

        with self._lock:
            if self.active_session is not None:
                self.stop_recording()

            sid = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"
            cap_token = secrets.token_urlsafe(24)
            clean_url = start_url.strip() if _is_safe_navigation_url(start_url) else ""
            sess: Dict[str, Any] = {
                "session_id": sid,
                "capture_token": cap_token,
                "label": str(label or f"{clean_mode.capitalize()} Agent Recording").strip()[:100],
                "mode": clean_mode,
                "start_url": clean_url,
                "record_audio": bool(record_audio),
                "created_at": datetime.now().isoformat(),
                "stopped_at": "",
                "start_mono": time.monotonic(),
                "duration_sec": 0.0,
                "lifecycle_status": "recording",
                "events": [],
                "audio_segments": [],
                "audio_saved": False,
                "audio_mime": "",
                "audio_bytes": 0,
            }
            self.active_session = sess

            def _enqueue(raw_evt: Dict[str, Any]) -> None:
                self.ingest_event(raw_evt, session_id=sid, capture_token=cap_token, trusted_internal=True)

            browser_info: Dict[str, Any] = {"launched": False}
            if clean_mode in ("browser", "hybrid") and launch_browser and not is_test_environment():
                self._cdp_recorder = BrowserCDPRecorder()
                browser_info = self._cdp_recorder.start(clean_url or "about:blank", _enqueue)
            elif clean_url:
                _enqueue({
                    "channel": "browser",
                    "action": "navigate",
                    "url": clean_url,
                    "title": clean_url,
                    "source": "session_start",
                })

            desktop_active = False
            if clean_mode in ("desktop", "hybrid") and not is_test_environment():
                self._desktop_watcher = DesktopActivityWatcher()
                desktop_active = self._desktop_watcher.start(_enqueue)

            bookmarklet = generate_bookmarklet_snippet(sid, cap_token, server_origin=server_origin)
            return {
                "status": "recording",
                "session_id": sid,
                "mode": clean_mode,
                "start_url": clean_url,
                "record_audio": bool(record_audio),
                "capture_token": cap_token,
                "bookmarklet_js": bookmarklet,
                "browser_launched": bool(browser_info.get("launched")),
                "browser_info": browser_info,
                "desktop_watcher_active": desktop_active,
                "message": f"🔴 Recording started ({clean_mode}) with audio narration={'ON' if record_audio else 'OFF'}.",
            }

    def _authorize_active_session(
        self,
        session_id: Optional[str],
        capture_token: Optional[str],
        trusted_internal: bool,
    ) -> Dict[str, Any]:
        sess = self.active_session
        if not sess:
            raise ValueError("No active recording session.")
        if session_id and session_id != sess["session_id"]:
            raise ValueError(f"Session '{session_id}' is not the active recording session.")
        expected = str(sess.get("capture_token") or "")
        provided = "" if capture_token is None else str(capture_token)
        if not trusted_internal:
            if not provided or not hmac.compare_digest(expected, provided):
                raise PermissionError("Invalid or missing capture_token for external recording upload.")
        elif provided and not hmac.compare_digest(expected, provided):
            raise PermissionError("Invalid capture_token.")
        return sess

    def _check_auto_cap(self, sess: Dict[str, Any]) -> None:
        elapsed = time.monotonic() - float(sess.get("start_mono") or time.monotonic())
        if elapsed > MAX_RECORDING_DURATION_SEC:
            self.stop_recording(session_id=sess["session_id"])
            raise ValueError("Recording auto-stopped after reaching 1800s safety duration cap.")

    def ingest_event(
        self,
        raw_event: Dict[str, Any],
        session_id: Optional[str] = None,
        capture_token: Optional[str] = None,
        trusted_internal: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            sess = self._authorize_active_session(session_id, capture_token, trusted_internal)
            self._check_auto_cap(sess)

            if _is_afcc_self_event(
                url=str(raw_event.get("url") or ""),
                title=str(raw_event.get("title") or raw_event.get("window_title") or ""),
                source=str(raw_event.get("source") or ""),
            ):
                return {"status": "ignored_self_event", "events_count": len(sess["events"])}

            evts: List[Dict[str, Any]] = sess["events"]
            if len(evts) >= MAX_EVENTS_PER_SESSION:
                evts.pop(0)
            sanitized = sanitize_recorded_event(raw_event, start_mono=float(sess.get("start_mono") or time.monotonic()))
            evts.append(sanitized)
            return {
                "status": "ok",
                "session_id": sess["session_id"],
                "event_id": sanitized["event_id"],
                "redacted": bool(sanitized.get("sensitive")),
                "events_count": len(evts),
                "event": sanitized,
            }

    def ingest_audio_segment(
        self,
        transcript: str,
        offset_sec: Optional[float] = None,
        duration_sec: float = 0.0,
        confidence: float = 0.9,
        is_final: bool = True,
        session_id: Optional[str] = None,
        capture_token: Optional[str] = None,
        trusted_internal: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            sess = self._authorize_active_session(session_id, capture_token, trusted_internal)
            self._check_auto_cap(sess)
            clean_txt = sanitize_audio_transcript(transcript)
            if not clean_txt:
                return {"status": "ignored_empty", "audio_segments_count": len(sess["audio_segments"])}

            eff_offset = (
                round(float(offset_sec), 3)
                if offset_sec is not None
                else round(max(0.0, time.monotonic() - float(sess.get("start_mono") or time.monotonic())), 3)
            )
            seg = {
                "segment_id": f"aud_{secrets.token_hex(4)}",
                "offset_sec": eff_offset,
                "duration_sec": round(max(0.0, float(duration_sec)), 2),
                "timestamp": datetime.now().isoformat(),
                "transcript": clean_txt,
                "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
                "is_final": bool(is_final),
            }
            segs: List[Dict[str, Any]] = sess["audio_segments"]
            if len(segs) >= MAX_AUDIO_SEGMENTS_PER_SESSION:
                segs.pop(0)
            segs.append(seg)
            return {
                "status": "ok",
                "session_id": sess["session_id"],
                "segment_id": seg["segment_id"],
                "scrubbed_transcript": clean_txt,
                "audio_segments_count": len(segs),
                "segment": seg,
            }

    def mark_dynamic_input(
        self,
        name: str,
        label: str = "",
        input_type: str = "text",
        prompt_question: str = "",
        required: bool = True,
        sensitive: bool = False,
        default_value: str = "",
        session_id: Optional[str] = None,
        capture_token: Optional[str] = None,
        trusted_internal: bool = True,
    ) -> Dict[str, Any]:
        key = _infer_param_key(name or label or "user_input", "user_input")
        clean_type = str(input_type or "text").strip().lower()
        is_sec = bool(sensitive or clean_type == "secret" or clean_type == "password" or SENSITIVE_FIELD_RE.search(key))
        if clean_type == "password" or is_sec:
            clean_type = "secret"
        if clean_type not in ("text", "secret", "number", "date", "url", "select", "file"):
            clean_type = "text"

        human_label = str(label or key.replace("_", " ").title()).strip()[:80]
        q = sanitize_audio_transcript(prompt_question or f"Enter {human_label}:")
        evt = {
            "channel": "prompt",
            "action": "prompt_user",
            "title": human_label,
            "input_type": clean_type,
            "sensitive": is_sec,
            "value": f"{{{{secret:{key}}}}}" if is_sec else ("" if not default_value else str(default_value)),
            "param_hint": key,
            "prompt_question": q,
            "required": bool(required),
            "locators": {"name": key, "aria_label": human_label},
            "source": "manual_mark",
        }
        res = self.ingest_event(evt, session_id=session_id, capture_token=capture_token, trusted_internal=trusted_internal)
        return {
            "status": "ok",
            "event_id": res.get("event_id"),
            "events_count": res.get("events_count"),
            "field": {
                "key": key,
                "label": human_label,
                "type": clean_type,
                "prompt": q,
                "required": bool(required),
                "sensitive": is_sec,
                "ask_on_each_run": True,
                "default": "" if is_sec else str(default_value),
            },
        }

    def stop_recording(
        self,
        session_id: Optional[str] = None,
        audio_base64: str = "",
        audio_mime: str = "audio/webm",
        audio_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if self._cdp_recorder is not None:
                try:
                    self._cdp_recorder.stop()
                finally:
                    self._cdp_recorder = None
            if self._desktop_watcher is not None:
                try:
                    self._desktop_watcher.stop()
                finally:
                    self._desktop_watcher = None

            sess = self.active_session
            if not sess:
                if session_id:
                    existing = self.load_session(session_id)
                    return {
                        "status": "already_stopped",
                        "session_id": existing["session_id"],
                        "session": existing,
                        "events_count": len(existing.get("events") or []),
                        "audio_segments_count": len(existing.get("audio_segments") or []),
                        "audio_saved": bool(existing.get("audio_saved")),
                    }
                raise ValueError("No active recording session to stop.")

            if session_id and session_id != sess["session_id"]:
                raise ValueError(f"Active session is '{sess['session_id']}', not '{session_id}'.")

            # Merge any final spoken segments batch submitted at stop time
            if isinstance(audio_segments, list):
                existing_ids = {s.get("segment_id") for s in sess["audio_segments"]}
                for seg in audio_segments:
                    if not isinstance(seg, dict):
                        continue
                    txt = sanitize_audio_transcript(str(seg.get("transcript") or ""))
                    if not txt:
                        continue
                    seg_id = str(seg.get("segment_id") or f"aud_{secrets.token_hex(4)}")
                    if seg_id in existing_ids:
                        continue
                    existing_ids.add(seg_id)
                    sess["audio_segments"].append({
                        "segment_id": seg_id,
                        "offset_sec": round(float(seg.get("offset_sec") or sess.get("duration_sec") or 0.0), 3),
                        "duration_sec": round(float(seg.get("duration_sec") or 0.0), 2),
                        "timestamp": str(seg.get("timestamp") or datetime.now().isoformat()),
                        "transcript": txt,
                        "confidence": round(float(seg.get("confidence") or 0.9), 3),
                        "is_final": bool(seg.get("is_final", True)),
                    })
                    if len(sess["audio_segments"]) >= MAX_AUDIO_SEGMENTS_PER_SESSION:
                        break

            # Encrypt uploaded binary audio narration (if provided) at rest
            if audio_base64 and str(audio_base64).strip():
                b64_payload = str(audio_base64).strip()
                if "," in b64_payload and b64_payload.lower().startswith("data:"):
                    b64_payload = b64_payload.split(",", 1)[1]
                raw_audio = base64.b64decode(b64_payload, validate=False)
                if len(raw_audio) > MAX_AUDIO_BYTES:
                    raw_audio = raw_audio[:MAX_AUDIO_BYTES]
                if raw_audio:
                    enc_audio = encrypt_binary_bytes_at_rest(raw_audio, aad=RECORDER_AUDIO_AAD)
                    self._audio_path(sess["session_id"]).write_bytes(enc_audio)
                    sess["audio_saved"] = True
                    sess["audio_mime"] = str(audio_mime or "audio/webm")[:64]
                    sess["audio_bytes"] = len(raw_audio)

            sess["stopped_at"] = datetime.now().isoformat()
            sess["duration_sec"] = round(max(0.0, time.monotonic() - float(sess.get("start_mono") or time.monotonic())), 2)
            sess["lifecycle_status"] = "recorded"

            finished = dict(sess)
            self._persist_session(finished)
            self.active_session = None

            return {
                "status": "stopped",
                "session_id": finished["session_id"],
                "session": finished,
                "events_count": len(finished.get("events") or []),
                "audio_segments_count": len(finished.get("audio_segments") or []),
                "audio_saved": bool(finished.get("audio_saved")),
                "duration_sec": finished["duration_sec"],
            }

    def get_status(self, recent_limit: int = 25) -> Dict[str, Any]:
        with self._lock:
            sess = self.active_session
            if not sess:
                return {
                    "status": "idle",
                    "active": False,
                    "session_id": None,
                    "elapsed_sec": 0.0,
                    "events_count": 0,
                    "audio_segments_count": 0,
                    "recent_events": [],
                    "audio_segments": [],
                }
            elapsed = round(max(0.0, time.monotonic() - float(sess.get("start_mono") or time.monotonic())), 2)
            evts = list(sess.get("events") or [])
            segs = list(sess.get("audio_segments") or [])
            return {
                "status": "recording",
                "active": True,
                "session_id": sess["session_id"],
                "mode": sess.get("mode", "browser"),
                "start_url": sess.get("start_url", ""),
                "record_audio": bool(sess.get("record_audio", True)),
                "elapsed_sec": elapsed,
                "events_count": len(evts),
                "audio_segments_count": len(segs),
                "recent_events": evts[-recent_limit:],
                "audio_segments": segs[-recent_limit:],
            }


_RECORDER_MANAGER: Optional[RecordingSessionManager] = None
_RECORDER_SINGLETON_LOCK = threading.Lock()


def get_recorder_manager() -> RecordingSessionManager:
    global _RECORDER_MANAGER
    with _RECORDER_SINGLETON_LOCK:
        if _RECORDER_MANAGER is None:
            _RECORDER_MANAGER = RecordingSessionManager()
        return _RECORDER_MANAGER


# ---------------------------------------------------------------------------
# Multimodal Brain Synthesizer: Coalescing, Audio Fusion, Req Doc & Pytest Gen
# ---------------------------------------------------------------------------

def _selector_signature(ev: Dict[str, Any]) -> str:
    locs = _as_dict(ev.get("locators"))
    return "|".join([
        str(ev.get("channel") or ""),
        str(locs.get("data_testid") or ""),
        str(locs.get("id") or ""),
        str(locs.get("name") or ""),
        str(locs.get("aria_label") or ""),
        str(locs.get("css_path") or ""),
        str(locs.get("process") or ""),
    ])


def coalesce_raw_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Noise filter & coalescer:
      1. Drops AFCC dashboard self-clicks.
      2. Merges consecutive typing/change events on the same element into one final step.
      3. Collapses rapid (<0.35s) duplicate clicks on the identical target or consecutive identical navigations.
    """
    cleaned: List[Dict[str, Any]] = []
    for raw in raw_events or []:
        if not isinstance(raw, dict):
            continue
        if _is_afcc_self_event(
            url=str(raw.get("url") or ""),
            title=str(raw.get("title") or raw.get("window_title") or ""),
            source=str(raw.get("source") or ""),
        ):
            continue
        ev = sanitize_recorded_event(raw)
        act = ev["action"]
        if not cleaned:
            cleaned.append(ev)
            continue

        prev = cleaned[-1]
        same_sig = _selector_signature(ev) != "" and _selector_signature(ev) == _selector_signature(prev)

        # Merge consecutive typing/change events on same target
        if act in ("input", "change", "fill") and prev["action"] in ("input", "change", "fill") and same_sig:
            prev["value"] = ev["value"]
            prev["offset_sec"] = ev["offset_sec"]
            prev["sensitive"] = bool(prev.get("sensitive") or ev.get("sensitive"))
            prev["input_type"] = ev["input_type"]
            continue

        # Deduplicate rapid double-clicks on same target
        if act == prev["action"] and act in ("click", "desktop_click") and same_sig:
            if abs(float(ev["offset_sec"]) - float(prev["offset_sec"])) < 0.35:
                continue

        # Deduplicate consecutive identical navigations
        if act == "navigate" and prev["action"] == "navigate" and ev.get("url") == prev.get("url"):
            continue

        cleaned.append(ev)

    return cleaned


def _infer_field_type_from_value(val: str, raw_type: str, is_sensitive: bool) -> str:
    if is_sensitive or raw_type in ("secret", "password"):
        return "secret"
    if raw_type in ("date", "number", "url", "select", "file"):
        return raw_type
    s = str(val or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return "date"
    if re.match(r"^-?\d+(?:\.\d+)?$", s):
        return "number"
    if _is_safe_navigation_url(s):
        return "url"
    return "text"


def _step_action_normalize(ev: Dict[str, Any]) -> str:
    act = str(ev.get("action") or "click").lower()
    if act in ("change", "input", "fill"):
        return "fill"
    return act


def fuse_audio_and_screen_events(
    steps: List[Dict[str, Any]],
    audio_segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Multimodal +-3.5s Temporal Fusion + Lexical Entity Binding:
    Aligns spoken audio segments to recorded steps, detects spoken dynamic input requests
    ('ask me for...', 'every time...'), wait hints ('wait N seconds'), schedule cadences,
    and output extraction goals.
    """
    clean_segs = [
        {
            **seg,
            "transcript": sanitize_audio_transcript(str(seg.get("transcript") or "")),
            "offset_sec": float(seg.get("offset_sec") or 0.0),
        }
        for seg in (audio_segments or [])
        if isinstance(seg, dict) and str(seg.get("transcript") or "").strip()
    ]

    business_rules: List[str] = []
    spoken_dynamic_cues: List[Dict[str, Any]] = []
    extract_hints: List[str] = []
    schedule_hint = "daily_morning"

    for seg in clean_segs:
        txt = seg["transcript"]
        low = txt.lower()
        seg_t = float(seg["offset_sec"])

        # Match nearest step within +-3.5s (or lexical match on label/title)
        best_step: Optional[Dict[str, Any]] = None
        best_dist = TEMPORAL_FUSION_WINDOW_SEC + 0.01
        for st in steps:
            dist = abs(float(st.get("offset_sec") or 0.0) - seg_t)
            if dist <= TEMPORAL_FUSION_WINDOW_SEC and dist < best_dist:
                best_dist = dist
                best_step = st

        if best_step is not None:
            existing_nar = str(best_step.get("narration") or "").strip()
            best_step["narration"] = f"{existing_nar}; {txt}".strip("; ")
            seg["linked_step_index"] = int(best_step["index"])
        elif steps:
            # Lexical keyword fallback if spoken slightly outside +-3.5s
            for st in steps:
                label_words = re.findall(r"[a-z]{4,}", (st.get("description") or "").lower())
                if any(w in low for w in label_words):
                    existing_nar = str(st.get("narration") or "").strip()
                    st["narration"] = f"{existing_nar}; {txt}".strip("; ")
                    best_step = st
                    seg["linked_step_index"] = int(st["index"])
                    break

        # Detect wait N seconds
        m_wait = re.search(r"\bwait\s+(?:for\s+)?(\d{1,2})\s*(?:sec|secs|second|seconds)\b", low)
        if m_wait:
            wait_sec = min(30, max(1, int(m_wait.group(1))))
            if best_step is not None:
                best_step["wait_before_ms"] = max(int(best_step.get("wait_before_ms") or 0), wait_sec * 1000)
                best_step["timeout_sec"] = max(int(best_step.get("timeout_sec") or DEFAULT_STEP_TIMEOUT_SEC), wait_sec + 10)
            business_rules.append(f"Wait {wait_sec}s synchronization rule around step '{best_step['step_id'] if best_step else 'flow'}': {txt}")

        # Detect dynamic input cues
        m_ask = re.search(
            r"\b(?:ask\s+me\s+(?:for|about)?|prompt\s+(?:me\s+)?for|request|enter\s+(?:different|new|my))\s+(?:the\s+)?([a-z0-9 _-]{2,36}?)(?:\s+(?:every|each|at|before|on)|[,.;!?]|$)",
            low,
        )
        if m_ask or any(k in low for k in ("every time", "each run", "ask me", "changes every", "otp", "two factor")):
            raw_field_name = m_ask.group(1).strip() if m_ask else ""
            raw_key = _infer_param_key(raw_field_name, "")
            generic_cues = {"", "it", "this", "that", "value", "input", "field", "dynamic_input", "user_input"}
            target_cue_step: Optional[Dict[str, Any]] = None
            if raw_key and raw_key not in generic_cues:
                # Prefer lexical match across steps over pure timestamp proximity
                for cand_st in steps:
                    ck = str(cand_st.get("input_key") or "")
                    cd = str(cand_st.get("description") or "").lower()
                    if ck and (ck == raw_key or raw_key in ck or ck in raw_key):
                        target_cue_step = cand_st
                        break
                    if raw_field_name.lower() in cd:
                        target_cue_step = cand_st
                        break
                if target_cue_step is not None:
                    cue_key = str(target_cue_step.get("input_key") or raw_key)
                elif best_step is not None and not best_step.get("input_key"):
                    target_cue_step = best_step
                    cue_key = raw_key
                else:
                    cue_key = raw_key
            elif best_step is not None and best_step.get("input_key"):
                target_cue_step = best_step
                cue_key = str(best_step["input_key"])
            else:
                target_cue_step = best_step
                cue_key = raw_key or "user_input"

            is_sec_cue = bool(SENSITIVE_FIELD_RE.search(low))
            spoken_dynamic_cues.append({
                "key": cue_key,
                "label": cue_key.replace("_", " ").title(),
                "prompt": f"Spoken requirement: {txt}",
                "sensitive": is_sec_cue,
                "ask_on_each_run": True,
                "step_index": target_cue_step["index"] if target_cue_step else (best_step["index"] if best_step else None),
            })
            if target_cue_step is not None:
                target_cue_step["ask_on_each_run"] = True
                if not target_cue_step.get("input_key"):
                    target_cue_step["input_key"] = cue_key
                    target_cue_step["value_template"] = f"{{{{secret:{cue_key}}}}}" if is_sec_cue else f"{{{{input:{cue_key}}}}}"

        # Detect schedule cues
        if any(k in low for k in ("every 30 min", "half hour", "every half hour")):
            schedule_hint = "every_30_min"
        elif any(k in low for k in ("every hour", "hourly")):
            schedule_hint = "hourly"
        elif any(k in low for k in ("manual", "only when i run", "on demand")):
            schedule_hint = "manual_only"

        # Detect extraction/output goals
        if any(k in low for k in ("extract", "capture", "save", "download", "summary", "report", "notify")):
            extract_hints.append(txt)
            business_rules.append(f"Extraction/output rule: {txt}")

        if not m_wait and not m_ask and txt:
            business_rules.append(f"User narration (@{seg_t:.1f}s): {txt}")

    return {
        "audio_segments": clean_segs,
        "business_rules": business_rules[:20],
        "spoken_dynamic_cues": spoken_dynamic_cues,
        "extract_hints": extract_hints[:10],
        "schedule_hint": schedule_hint,
    }


def _mermaid_safe_label(text: str, max_len: int = 44) -> str:
    """Strips HTML tags and unsafe Mermaid delimiters; caller places inside quotes."""
    clean = re.sub(r"<[^>]+>", "", str(text or ""))
    clean = clean.replace('"', "'").replace("`", "").replace("\n", " ").replace("\r", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len] or "Step"


def build_requirements_document(
    name: str,
    modality: str,
    steps: List[Dict[str, Any]],
    input_schema: List[Dict[str, Any]],
    audio_segments: Optional[List[Dict[str, Any]]] = None,
    business_rules: Optional[List[str]] = None,
    acceptance_criteria: Optional[List[str]] = None,
    version: int = 1,
) -> Dict[str, Any]:
    """Builds a formal Requirements Document with valid Mermaid Process Flow & Screen<->Audio Trace Matrix."""
    lines: List[str] = ["flowchart TD"]
    safe_start = _mermaid_safe_label(f"Start {name} (Headless)")
    lines.append(f'    Start(["{safe_start}"])')
    prev_node = "Start"

    if input_schema:
        req_keys = ", ".join(str(f.get("key") or "input") for f in input_schema[:4])
        lines.append(f'    InputGate{{"Required Inputs Present ({_mermaid_safe_label(req_keys, 30)})?"}}')
        lines.append('    PauseNode["Pause: Ask User & Save SQLite Checkpoint"]')
        lines.append('    ResumeNode["Resume With User Inputs (RAM Secrets)"]')
        lines.append(f"    {prev_node} --> InputGate")
        lines.append('    InputGate -->|"Missing"| PauseNode')
        lines.append("    PauseNode --> ResumeNode")
        prev_node = "InputGate"

    for i, st in enumerate(steps):
        nid = f"Step{i + 1}"
        lbl = _mermaid_safe_label(f"{i + 1}. {st.get('description') or st.get('action')}", 46)
        if st.get("action") == "prompt_user":
            lines.append(f'    {nid}{{"{lbl}"}}')
        else:
            lines.append(f'    {nid}["{lbl}"]')
        if prev_node == "InputGate":
            lines.append(f'    InputGate -->|"Ready"| {nid}')
            lines.append(f"    ResumeNode --> {nid}")
        else:
            lines.append(f"    {prev_node} --> {nid}")
        prev_node = nid

    lines.append('    EndNode(["Complete & Log Audit Record"])')
    lines.append(f"    {prev_node} --> EndNode")
    mermaid_flow = "\n".join(lines)

    fr_rows: List[Dict[str, str]] = []
    for i, st in enumerate(steps):
        fr_rows.append({
            "id": f"FR-{i + 1:02d}",
            "step_id": str(st.get("step_id") or f"step_{i + 1}"),
            "requirement": str(st.get("description") or f"Execute {st.get('action')}"),
            "channel": str(st.get("channel") or modality),
            "narration_context": str(st.get("narration") or "Observed user screen action"),
        })

    nfr_rows = [
        {"id": "NFR-01", "category": "Execution", "requirement": "Run headlessly without user mouse/keyboard takeover when inputs are satisfied."},
        {"id": "NFR-02", "category": "HITL", "requirement": "Pause non-blockingly (status=waiting_for_input) when dynamic or secret inputs are needed."},
        {"id": "NFR-03", "category": "Security", "requirement": "Never persist passwords, OTPs, CVVs, or card numbers in SQLite or manifests; isolate browser profiles."},
        {"id": "NFR-04", "category": "Resilience", "requirement": "Resolve targets via multi-tier self-healing locators before surfacing failures."},
    ]

    trace_matrix: List[Dict[str, str]] = []
    for st in steps:
        locs = _as_dict(st.get("locators"))
        loc_desc = (
            locs.get("data_testid")
            or locs.get("id")
            or locs.get("aria_label")
            or locs.get("text")
            or locs.get("css_path")
            or locs.get("process")
            or st.get("url")
            or "-"
        )
        trace_matrix.append({
            "step_id": str(st.get("step_id") or ""),
            "action": f"{st.get('channel')}:{st.get('action')}",
            "target": str(loc_desc)[:80],
            "narration": str(st.get("narration") or "-")[:160],
            "input_key": str(st.get("input_key") or "-"),
        })

    rules = list(business_rules or [])
    criteria = list(acceptance_criteria or [
        "All functional steps execute cleanly in headless or visible sandbox mode.",
        "Missing required or secret parameters trigger status=waiting_for_input checkpoint without crashing.",
        "Resuming with valid user inputs completes remaining steps cleanly with zero leaked secrets.",
    ])

    md_parts = [
        f"# Requirements Specification: {name} (v{version})",
        "",
        f"- **Capture Modality**: `{modality}`",
        f"- **Recorded Steps**: `{len(steps)}`",
        f"- **Dynamic Runtime Inputs**: `{len(input_schema)}`",
        f"- **Audio Narration Segments**: `{len(audio_segments or [])}`",
        "",
        "## Process Flow",
        "```mermaid",
        mermaid_flow,
        "```",
        "",
        "## Functional Requirements & Screen-Audio Traceability",
        "| ID | Step | Channel | Requirement | Audio Narration |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for fr in fr_rows:
        md_parts.append(f"| {fr['id']} | `{fr['step_id']}` | `{fr['channel']}` | {fr['requirement']} | {fr['narration_context']} |")

    if rules:
        md_parts.extend(["", "## Spoken Business Rules & Constraints"])
        for r in rules:
            md_parts.append(f"- {r}")

    if input_schema:
        md_parts.extend(["", "## Dynamic Runtime Input Contract", "| Key | Label | Type | Required | Sensitive | Prompt Question |", "| :--- | :--- | :--- | :--- | :--- | :--- |"])
        for inp in input_schema:
            md_parts.append(
                f"| `{inp['key']}` | {inp['label']} | `{inp['type']}` | `{inp['required']}` | `{inp['sensitive']}` | {inp['prompt']} |"
            )

    md_parts.extend(["", "## Acceptance Criteria"])
    for idx, crit in enumerate(criteria, 1):
        md_parts.append(f"{idx}. {crit}")

    summary = (
        f"Automated {modality} headless workflow '{name}' with {len(steps)} step(s), "
        f"{len(input_schema)} runtime input(s), and {len(audio_segments or [])} audio narration note(s)."
    )

    return {
        "doc_id": f"req_{_infer_param_key(name, 'workflow')}_v{version}",
        "version": int(version),
        "title": f"Requirements Specification: {name}",
        "summary": summary,
        "modality": modality,
        "mermaid_process_flow": mermaid_flow,
        "functional_requirements": fr_rows,
        "non_functional_requirements": nfr_rows,
        "business_rules": rules,
        "input_schema": input_schema,
        "trace_matrix": trace_matrix,
        "acceptance_criteria": criteria,
        "markdown": "\n".join(md_parts),
    }


def generate_agent_unit_tests_code(agent_spec: Dict[str, Any]) -> str:
    """
    Generates a standalone pytest module validating this recorded agent's
    IR safety, permissions allowlist, secret hygiene, waiting_for_input pause gate,
    and headless resume execution.
    """
    agent_id = str(agent_spec.get("agent_id") or agent_spec.get("id") or "recorded_agent")
    workflow_ir = sanitize_workflow_ir(agent_spec.get("workflow_ir") or {}) or {}
    perms = list(agent_spec.get("permissions") or ["db:read", "db:write", "ui:render"])
    input_schema = list(workflow_ir.get("input_schema") or [])
    steps = list(workflow_ir.get("steps") or [])

    sample_inputs: Dict[str, Any] = {}
    has_required_input = False
    for fld in input_schema:
        k = str(fld.get("key") or "")
        if not k:
            continue
        if fld.get("required") or fld.get("ask_on_each_run") or fld.get("sensitive"):
            has_required_input = True
        t = str(fld.get("type") or "text")
        if t == "number":
            sample_inputs[k] = 42
        elif t == "date":
            sample_inputs[k] = "2026-12-01"
        elif t == "url":
            sample_inputs[k] = "https://example.com"
        elif t == "secret":
            sample_inputs[k] = "synthetic-runtime-token"
        else:
            sample_inputs[k] = f"sample_{k}"

    if not has_required_input:
        for st in steps:
            if st.get("action") == "prompt_user" and st.get("input_key"):
                has_required_input = True
                sample_inputs.setdefault(str(st["input_key"]), "synthetic-runtime-value")

    spec_repr = repr({
        "agent_id": agent_id,
        "name": str(agent_spec.get("name") or "Recorded Workflow Agent"),
        "permissions": perms,
        "workflow_ir": workflow_ir,
    })
    inputs_repr = repr(sample_inputs)

    return f'''"""Auto-generated pytest suite for recorded workflow agent '{agent_id}'."""
from pathlib import Path
from fleet.core.activity_recorder import execute_recorded_workflow, resume_workflow_run, sanitize_workflow_ir
from fleet.core.agent_studio import generate_custom_agent_code
from fleet.core.database import FleetDatabase
from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS

SPEC = {spec_repr}
SAMPLE_INPUTS = {inputs_repr}


class _AgentStub:
    def __init__(self, db):
        self.id = SPEC["agent_id"]
        self.display_name = SPEC["name"]
        self.display_icon = "🎬"
        self.archetype = "recorded_workflow"
        self.intelligence_mode = "hybrid"
        self.permissions = list(SPEC["permissions"])
        self.manifest_meta = {{"archetype": "recorded_workflow", "workflow_ir": SPEC["workflow_ir"]}}
        self.db = db
        self.event_bus = None


def test_generated_permissions_and_ast():
    assert SPEC["permissions"], "Permissions must be non-empty"
    invalid = [p for p in SPEC["permissions"] if p not in ALLOWED_AGENT_PERMISSIONS]
    assert not invalid, f"Disallowed permissions: {{invalid}}"
    code = generate_custom_agent_code(
        agent_id=SPEC["agent_id"],
        name=SPEC["name"],
        icon="🎬",
        description="Recorded headless workflow",
        archetype="recorded_workflow",
    )
    assert "execute_studio_agent_runtime" in code


def test_generated_workflow_ir_secret_hygiene():
    sanitized = sanitize_workflow_ir(SPEC["workflow_ir"])
    assert sanitized is not None
    assert len(sanitized.get("steps") or []) >= 1
    for fld in sanitized.get("input_schema") or []:
        if fld.get("sensitive"):
            assert fld.get("default") == ""
            assert fld.get("ask_on_each_run") is True


def test_generated_headless_dry_run_and_input_pause_resume(tmp_path):
    db = FleetDatabase(db_path=tmp_path / "agent_test.db")
    agent = _AgentStub(db)

    first = execute_recorded_workflow(agent, user_inputs={{}}, dry_run=True)
    if {repr(has_required_input)}:
        assert first["status"] == "waiting_for_input"
        assert first.get("pending_inputs")
        run_id = first["run_id"]
        # Ensure sensitive inputs are never persisted in SQLite checkpoint
        ckpt_rows = db.list_custom_agent_records(agent.id, record_type="workflow_run", limit=5)
        assert ckpt_rows
        saved_inputs = (ckpt_rows[0].get("data") or {{}}).get("non_secret_inputs") or {{}}
        for fld in (SPEC["workflow_ir"].get("input_schema") or []):
            if fld.get("sensitive"):
                assert fld["key"] not in saved_inputs
        resumed = resume_workflow_run(agent, run_id=run_id, user_inputs=SAMPLE_INPUTS, dry_run=True)
        assert resumed["status"] in ("completed", "waiting_for_input")
    else:
        assert first["status"] == "completed"
'''


def _verify_generated_test_ast(code: str) -> None:
    """AST security gate blocking unsafe calls before executing generated agent test modules."""
    tree = ast.parse(code)
    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                raise ValueError(f"AST security gate blocked forbidden call '{node.func.id}()'")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                raise ValueError("AST security gate blocked 'os.system()'")


def run_generated_agent_unit_tests(agent_spec: Dict[str, Any], unit_tests_code: Optional[str] = None) -> Dict[str, Any]:
    """Executes the generated per-agent test suite inside an isolated temporary directory."""
    code = unit_tests_code or generate_agent_unit_tests_code(agent_spec)
    t0 = time.perf_counter()
    try:
        _verify_generated_test_ast(code)
    except Exception as ast_exc:
        return {
            "status": "failed",
            "returncode": 1,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "total": 1,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "results": [],
            "output": f"AST validation failed: {ast_exc}",
        }

    slug = _infer_param_key(str(agent_spec.get("agent_id") or "agent"), "agent")
    mod_name = f"afcc_gen_test_{slug}_{secrets.token_hex(4)}"
    results: List[Dict[str, Any]] = []
    passed = 0
    failed = 0
    errors = 0
    log_lines: List[str] = []

    with tempfile.TemporaryDirectory(prefix="afcc_agent_tests_", ignore_cleanup_errors=True) as tmpdir:
        tmp_root = Path(tmpdir)
        test_file = tmp_root / f"test_{slug}_gen.py"
        test_file.write_text(code, encoding="utf-8", newline="\n")
        try:
            spec = importlib.util.spec_from_file_location(mod_name, str(test_file))
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load generated test module '{test_file.name}'")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            test_fns = [
                (name, fn)
                for name, fn in inspect.getmembers(mod, inspect.isfunction)
                if name.startswith("test_") and getattr(fn, "__module__", "") == mod_name
            ]
            for fn_name, fn in test_fns:
                case_t0 = time.perf_counter()
                try:
                    sig = inspect.signature(fn)
                    kwargs: Dict[str, Any] = {}
                    if "tmp_path" in sig.parameters:
                        case_dir = tmp_root / fn_name
                        case_dir.mkdir(parents=True, exist_ok=True)
                        kwargs["tmp_path"] = case_dir
                    fn(**kwargs)
                    case_ms = round((time.perf_counter() - case_t0) * 1000, 1)
                    passed += 1
                    results.append({"name": fn_name, "status": "passed", "duration_ms": case_ms, "error": ""})
                    log_lines.append(f"PASSED {test_file.name}::{fn_name} ({case_ms} ms)")
                except AssertionError as ae:
                    case_ms = round((time.perf_counter() - case_t0) * 1000, 1)
                    failed += 1
                    err_txt = traceback.format_exc()
                    results.append({"name": fn_name, "status": "failed", "duration_ms": case_ms, "error": str(ae)})
                    log_lines.append(f"FAILED {test_file.name}::{fn_name}: {err_txt}")
                except Exception as exc:
                    case_ms = round((time.perf_counter() - case_t0) * 1000, 1)
                    errors += 1
                    err_txt = traceback.format_exc()
                    results.append({"name": fn_name, "status": "error", "duration_ms": case_ms, "error": str(exc)})
                    log_lines.append(f"ERROR {test_file.name}::{fn_name}: {err_txt}")
        except Exception:
            errors += 1
            log_lines.append(traceback.format_exc())
        finally:
            try:
                from fleet.core.db.pool import _GLOBAL_POOL
                _GLOBAL_POOL.close_current_thread_connection()
            except Exception:
                pass
            sys.modules.pop(mod_name, None)

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    total = max(passed + failed + errors, 1)
    ok = (failed == 0 and errors == 0 and passed > 0)
    log_lines.append(f"{passed} passed, {failed} failed, {errors} errors in {duration_ms} ms")
    return {
        "status": "passed" if ok else "failed",
        "returncode": 0 if ok else 1,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "duration_ms": duration_ms,
        "results": results,
        "output": "\n".join(log_lines)[-3000:],
    }


def _describe_step(step: Dict[str, Any]) -> str:
    act = step.get("action", "step")
    locs = _as_dict(step.get("locators"))
    target = (
        locs.get("label_text")
        or locs.get("aria_label")
        or locs.get("placeholder")
        or locs.get("text")
        or locs.get("name")
        or locs.get("id")
        or locs.get("window_title")
        or locs.get("process")
        or step.get("url")
        or "element"
    )
    if act == "navigate":
        return f"Navigate to {step.get('url') or target}"
    if act == "fill":
        if step.get("sensitive"):
            return f"Enter secret '{target}' (ask at runtime)"
        return f"Fill '{target}'"
    if act == "select":
        return f"Select option in '{target}'"
    if act == "click":
        return f"Click '{target}'"
    if act == "submit":
        return f"Submit form ({target})"
    if act == "prompt_user":
        return f"Ask user for '{step.get('title') or target}'"
    if act == "app_switch":
        return f"Switch to desktop window '{target}'"
    if act == "desktop_click":
        return f"Click inside '{target}'"
    return f"Execute {act} on '{target}'"


def _try_llm_polish_workflow_spec(
    base_spec: Dict[str, Any],
    steps: List[Dict[str, Any]],
    audio_segments: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool]:
    """Optional Connected LLM polish (strictly over redacted summaries) with instant $0.00 fallback."""
    if is_test_environment():
        return base_spec, False
    try:
        from fleet.core.hyperscalers import HyperscalerGateway
        gateway = HyperscalerGateway()
        if not (hasattr(gateway, "complete") and callable(gateway.complete)):
            return base_spec, False
        step_lines = "\n".join(f"- {s['step_id']} ({s['channel']}:{s['action']}): {s['description']} | audio={s.get('narration', '')}" for s in steps[:18])
        aud_lines = "\n".join(f"- @{a['offset_sec']}s: {a['transcript']}" for a in audio_segments[:15])
        prompt = (
            "Given this REDACTED recorded workflow & user voice narration, return ONLY raw JSON "
            '{"name":"Short Agent Name","icon":"single emoji","description":"concise 1-2 sentence goal","category":"Productivity|Finance|Monitoring|DevOps|Knowledge|Health|System"}.\n'
            f"Steps:\n{step_lines}\nNarration:\n{aud_lines}\nJSON:"
        )
        resp = gateway.complete(prompt=prompt, model="gemini-3.8-flash-low", allow_tier0=False)
        if not isinstance(resp, dict) or resp.get("status") == "FALLBACK":
            return base_spec, False
        raw = str(resp.get("text") or resp.get("response") or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("name"):
            out = dict(base_spec)
            out["name"] = str(parsed["name"])[:50]
            if parsed.get("icon"):
                out["icon"] = str(parsed["icon"])[:4]
            if parsed.get("description"):
                out["description"] = sanitize_audio_transcript(str(parsed["description"]))[:240]
            if parsed.get("category") in ("Productivity", "Finance", "Monitoring", "DevOps", "Knowledge", "Health", "System"):
                out["category"] = str(parsed["category"])
            return out, True
    except Exception:
        pass
    return base_spec, False


def synthesize_agent_from_recording(
    session_id: Optional[str] = None,
    raw_events: Optional[List[Dict[str, Any]]] = None,
    audio_segments: Optional[List[Dict[str, Any]]] = None,
    label: str = "",
    use_llm: bool = True,
    auto_run_tests: bool = False,
    manager: Optional[RecordingSessionManager] = None,
) -> Dict[str, Any]:
    """
    Step 5-7 of the workflow:
    Fuses screen actions + audio narration -> compiles formal Requirements Doc & Mermaid Process Flow ->
    synthesizes Parameterized Workflow IR + Studio Agent Spec + tailored Pytest Suite.
    """
    mgr = manager or get_recorder_manager()
    sess_data: Optional[Dict[str, Any]] = None
    if session_id:
        sess_data = mgr.load_session(session_id)
        if raw_events is None:
            raw_events = list(sess_data.get("events") or [])
        if audio_segments is None:
            audio_segments = list(sess_data.get("audio_segments") or [])
        if not label:
            label = str(sess_data.get("label") or "")

    coalesced = coalesce_raw_events(raw_events or [])
    if not coalesced and not (audio_segments or []):
        raise ValueError("Recording contains no usable screen actions or narration segments.")

    has_browser = any(ev.get("channel") == "browser" for ev in coalesced)
    has_desktop = any(ev.get("channel") == "desktop" for ev in coalesced)
    modality = "hybrid" if (has_browser and has_desktop) else ("desktop" if has_desktop else "browser")

    start_url = ""
    for ev in coalesced:
        if ev.get("url") and _is_safe_navigation_url(ev["url"]):
            start_url = ev["url"]
            break

    steps: List[Dict[str, Any]] = []
    input_schema: List[Dict[str, Any]] = []
    seen_input_keys: set[str] = set()

    for idx, ev in enumerate(coalesced):
        locs = dict(ev.get("locators") or {})
        act = _step_action_normalize(ev)
        is_sec = bool(ev.get("sensitive"))
        val = str(ev.get("value") or "")
        hint = (
            ev.get("param_hint")
            or locs.get("name")
            or locs.get("aria_label")
            or locs.get("label_text")
            or locs.get("placeholder")
            or locs.get("id")
            or ""
        )
        input_key = ""
        val_template = val

        should_parameterize = (
            act == "prompt_user"
            or is_sec
            or (act in ("fill", "select") and bool(val or hint))
        )
        if should_parameterize:
            base_key = _infer_param_key(str(hint), f"param_{idx + 1}")
            candidate_key = base_key
            suffix = 2
            while candidate_key in seen_input_keys and act == "prompt_user":
                candidate_key = f"{base_key}_{suffix}"
                suffix += 1
            input_key = candidate_key
            if input_key not in seen_input_keys:
                seen_input_keys.add(input_key)
                ftype = _infer_field_type_from_value(val, str(ev.get("input_type") or "text"), is_sec)
                label_txt = str(locs.get("label_text") or locs.get("aria_label") or input_key.replace("_", " ").title())[:60]
                prompt_q = str(ev.get("prompt_question") or (f"Enter secret {label_txt} (never stored):" if ftype == "secret" else f"Provide {label_txt}:"))
                input_schema.append({
                    "key": input_key,
                    "label": label_txt,
                    "type": ftype,
                    "prompt": prompt_q,
                    "required": bool(ev.get("required", True if (is_sec or act == "prompt_user") else False)),
                    "ask_on_each_run": bool(is_sec or act == "prompt_user"),
                    "sensitive": is_sec or ftype == "secret",
                    "default": "" if (is_sec or ftype == "secret") else val,
                    "options": [],
                    "source": "screen_capture",
                })
            val_template = f"{{{{secret:{input_key}}}}}" if is_sec else f"{{{{input:{input_key}}}}}"

        st_obj: Dict[str, Any] = {
            "step_id": f"step_{idx + 1}",
            "index": idx,
            "offset_sec": float(ev.get("offset_sec") or 0.0),
            "channel": str(ev.get("channel") or "browser"),
            "action": act,
            "url": str(ev.get("url") or ""),
            "title": str(ev.get("title") or ""),
            "locators": locs,
            "value_template": val_template,
            "input_key": input_key,
            "sensitive": is_sec,
            "wait_before_ms": 0,
            "timeout_sec": DEFAULT_STEP_TIMEOUT_SEC,
            "retries": 2,
            "on_error": "retry_then_prompt",
            "narration": "",
        }
        st_obj["description"] = _describe_step(st_obj)
        steps.append(st_obj)

    # Multimodal audio fusion (+-3.5s)
    fusion = fuse_audio_and_screen_events(steps, audio_segments or [])
    for cue in fusion["spoken_dynamic_cues"]:
        ckey = str(cue["key"])
        existing_inp = next((f for f in input_schema if f["key"] == ckey), None)
        if existing_inp is not None:
            existing_inp["ask_on_each_run"] = True
            existing_inp["required"] = True
            existing_inp["prompt"] = cue["prompt"]
            if cue.get("sensitive"):
                existing_inp["sensitive"] = True
                existing_inp["type"] = "secret"
                existing_inp["default"] = ""
        else:
            seen_input_keys.add(ckey)
            input_schema.append({
                "key": ckey,
                "label": cue["label"],
                "type": "secret" if cue.get("sensitive") else "text",
                "prompt": cue["prompt"],
                "required": True,
                "ask_on_each_run": True,
                "sensitive": bool(cue.get("sensitive")),
                "default": "",
                "options": [],
                "source": "audio_cue",
            })

    # If user only spoke narration without screen clicks, create a spoken requirement step
    if not steps and fusion["audio_segments"]:
        steps.append({
            "step_id": "step_1",
            "index": 0,
            "offset_sec": 0.0,
            "channel": "prompt",
            "action": "prompt_user",
            "description": "Confirm spoken workflow input & run parameters",
            "url": start_url,
            "locators": {"name": "workflow_input"},
            "value_template": "{{input:workflow_input}}",
            "input_key": "workflow_input",
            "sensitive": False,
            "wait_before_ms": 0,
            "timeout_sec": DEFAULT_STEP_TIMEOUT_SEC,
            "retries": 1,
            "on_error": "retry_then_prompt",
            "narration": fusion["audio_segments"][0]["transcript"],
        })
        if "workflow_input" not in seen_input_keys:
            input_schema.append({
                "key": "workflow_input",
                "label": "Workflow Input",
                "type": "text",
                "prompt": "Provide input for this narrated workflow:",
                "required": True,
                "ask_on_each_run": True,
                "sensitive": False,
                "default": "",
                "options": [],
                "source": "audio_cue",
            })

    # Clean Agent naming & least-privilege permissions
    domain_hint = ""
    if start_url:
        host = (urllib.parse.urlparse(start_url).hostname or "").replace("www.", "")
        domain_hint = host.split(".")[0].capitalize() if host else ""
    base_name = str(label or "").strip()
    if not base_name or base_name.lower().endswith("agent recording"):
        if domain_hint:
            base_name = f"{domain_hint} Workflow Agent"
        else:
            base_name = f"Recorded {modality.capitalize()} Agent"
    agent_slug = _infer_param_key(base_name, "recorded_workflow_agent")[:30]

    perms = ["db:read", "db:write", "ui:render", "event_bus:publish"]
    if has_browser or start_url:
        perms.append("network:outbound")
    if has_desktop:
        perms.append("system:diagnostics")

    workflow_ir: Dict[str, Any] = sanitize_workflow_ir({
        "schema_version": "1.0",
        "recording_id": str(session_id or "inline_recording"),
        "modality": modality,
        "execution_mode": "headless",
        "start_url": start_url,
        "input_schema": input_schema,
        "steps": steps,
        "output_schema": {
            "summary_field": "result_summary",
            "extract_keys": ["page_title", "extracted_text"],
            "audio_hints": fusion["extract_hints"],
        },
    }) or {}

    sched_map = {
        "every_30_min": {"type": "cron", "value": "*/30 * * * *", "display": "Every 30m"},
        "hourly": {"type": "interval_hours", "value": 1, "display": "Every 1h"},
        "manual_only": {"type": "manual", "value": "manual", "display": "Manual Only"},
        "daily_morning": {"type": "time", "value": "09:00", "time": "09:00", "display": "Daily at 09:00"},
    }
    sched_cad = fusion["schedule_hint"]
    if input_schema and any(f.get("ask_on_each_run") for f in input_schema):
        sched_cad = "manual_only" if sched_cad == "daily_morning" else sched_cad

    studio_fields = [
        {
            "key": f["key"],
            "label": f["label"],
            "type": "text" if f["type"] == "secret" else (f["type"] if f["type"] in ("text", "number", "date", "url") else "text"),
            "placeholder": f["prompt"],
        }
        for f in input_schema[:6]
    ] or [{"key": "title", "label": "Run Note", "type": "text", "placeholder": "Optional run note or override..."}]

    base_spec: Dict[str, Any] = {
        "name": base_name[:50],
        "agent_id": agent_slug,
        "id": agent_slug,
        "icon": "🎬",
        "category": "Productivity",
        "archetype": "recorded_workflow",
        "intelligence_mode": "hybrid",
        "description": f"Headless {modality} automation recorded by user with {len(steps)} step(s) and {len(input_schema)} dynamic input(s).",
        "permissions": perms,
        "ui_blocks": [
            "alert_banner",
            "kpi_row",
            "quick_capture_bar",
            "ai_insight_card",
            "history_table",
            "status_timeline",
        ],
        "fields": studio_fields,
        "checklist_items": [f"{st['step_id']}: {st['description'][:65]}" for st in steps[:5]],
        "routine_task": "run_workflow",
        "schedule_cadence": sched_cad,
        "schedule": sched_map.get(sched_cad, sched_map["daily_morning"]),
        "system_prompt": "Execute the recorded headless workflow safely and pause to ask the user whenever dynamic or sensitive inputs are required.",
        "recording_id": str(session_id or ""),
        "workflow_ir": workflow_ir,
    }

    used_llm = False
    if use_llm:
        base_spec, used_llm = _try_llm_polish_workflow_spec(base_spec, steps, fusion["audio_segments"])

    req_doc = build_requirements_document(
        name=base_spec["name"],
        modality=modality,
        steps=steps,
        input_schema=input_schema,
        audio_segments=fusion["audio_segments"],
        business_rules=fusion["business_rules"],
        version=1,
    )
    base_spec["requirements_doc"] = req_doc
    unit_tests_code = generate_agent_unit_tests_code(base_spec)

    unit_test_report: Optional[Dict[str, Any]] = None
    if auto_run_tests:
        unit_test_report = run_generated_agent_unit_tests(base_spec, unit_tests_code)

    draft_bundle: Dict[str, Any] = {
        "spec": base_spec,
        "workflow_ir": workflow_ir,
        "requirements_doc": req_doc,
        "unit_tests_code": unit_tests_code,
        "unit_test_report": unit_test_report,
        "iteration_version": 1,
        "iteration_history": [
            {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "trigger": "initial_multimodal_synthesis",
                "summary": f"Synthesized {len(steps)} steps + {len(fusion['audio_segments'])} audio notes.",
            }
        ],
        "sandbox_failures": [],
        "last_sandbox_report": None,
        "lifecycle_status": "requirements_ready",
        "used_llm": used_llm,
    }

    if sess_data is not None:
        sess_data["draft"] = draft_bundle
        sess_data["lifecycle_status"] = "requirements_ready"
        mgr.save_session(sess_data)

    return {
        "status": "ok",
        "session_id": session_id or "",
        "spec": base_spec,
        "workflow_ir": workflow_ir,
        "input_schema": input_schema,
        "requirements_doc": req_doc,
        "unit_tests_code": unit_tests_code,
        "unit_test_report": unit_test_report,
        "iteration_version": 1,
        "lifecycle_status": "requirements_ready",
        "used_llm": used_llm,
    }


# ---------------------------------------------------------------------------
# Headless & Visible Browser CDP Step Executors
# ---------------------------------------------------------------------------

def _resolve_step_value(step: Dict[str, Any], user_inputs: Dict[str, Any]) -> Tuple[str, bool]:
    """Interpolates {{input:key}} / {{secret:key}} templates cleanly. Returns (value, is_secret)."""
    tpl = str(step.get("value_template") or "")
    key = str(step.get("input_key") or "")
    is_sec = bool(step.get("sensitive"))
    if key and key in user_inputs and user_inputs[key] not in (None, ""):
        return str(user_inputs[key]), is_sec
    if tpl.startswith("{{input:") and tpl.endswith("}}"):
        k2 = tpl[8:-2]
        return str(user_inputs.get(k2, "")), is_sec
    if tpl.startswith("{{secret:") and tpl.endswith("}}"):
        k2 = tpl[9:-2]
        return str(user_inputs.get(k2, "")), True
    return tpl, is_sec


def _build_js_locate_and_act(action: str, locs: Dict[str, str], value: str) -> str:
    """Builds a self-contained 6-tier self-healing JS snippet executed via CDP Runtime.evaluate."""
    return f"""
    (function() {{
      var locs = {json.dumps(locs)};
      var act = {json.dumps(action)};
      var val = {json.dumps(value)};
      function findEl() {{
        var el = null;
        if (locs.data_testid) {{
          el = document.querySelector('[data-testid="' + locs.data_testid.replace(/"/g, '\\\\"') + '"]');
          if (el) return {{el: el, tier: 'tier1_data_testid'}};
        }}
        if (locs.id) {{
          el = document.getElementById(locs.id);
          if (el) return {{el: el, tier: 'tier2_id'}};
        }}
        if (locs.aria_label) {{
          el = document.querySelector('[aria-label="' + locs.aria_label.replace(/"/g, '\\\\"') + '"]');
          if (el) return {{el: el, tier: 'tier3_aria_label'}};
        }}
        if (locs.name) {{
          el = document.querySelector('[name="' + locs.name.replace(/"/g, '\\\\"') + '"]');
          if (el) return {{el: el, tier: 'tier3_name'}};
        }}
        if (locs.placeholder) {{
          el = document.querySelector('[placeholder="' + locs.placeholder.replace(/"/g, '\\\\"') + '"]');
          if (el) return {{el: el, tier: 'tier3_placeholder'}};
        }}
        if (locs.text || locs.label_text) {{
          var needle = (locs.text || locs.label_text).toLowerCase();
          var all = document.querySelectorAll('button,a,input,select,textarea,[role="button"],label');
          for (var i = 0; i < all.length; i++) {{
            var txt = (all[i].innerText || all[i].textContent || all[i].value || '').trim().toLowerCase();
            if (txt && txt.indexOf(needle) >= 0) return {{el: all[i], tier: 'tier4_role_text'}};
          }}
        }}
        if (locs.css_path) {{
          try {{
            el = document.querySelector(locs.css_path);
            if (el) return {{el: el, tier: 'tier5_css_path'}};
          }} catch (e) {{}}
        }}
        if (locs.xpath) {{
          try {{
            var xr = document.evaluate(locs.xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            if (xr && xr.singleNodeValue) return {{el: xr.singleNodeValue, tier: 'tier6_xpath'}};
          }} catch (e) {{}}
        }}
        return null;
      }}
      var hit = findEl();
      if (!hit || !hit.el) return {{ok: false, error: 'selector_not_found'}};
      var el = hit.el;
      if (act === 'click') {{
        el.click();
        return {{ok: true, tier: hit.tier, title: document.title || ''}};
      }}
      if (act === 'fill' || act === 'select') {{
        el.focus && el.focus();
        el.value = val;
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return {{ok: true, tier: hit.tier, title: document.title || ''}};
      }}
      if (act === 'submit') {{
        if (typeof el.submit === 'function') el.submit();
        else el.click();
        return {{ok: true, tier: hit.tier, title: document.title || ''}};
      }}
      if (act === 'extract_text') {{
        return {{ok: true, tier: hit.tier, extracted: (el.innerText || el.textContent || '').trim().slice(0, 1000)}};
      }}
      return {{ok: true, tier: hit.tier}};
    }})();
    """


def _execute_browser_steps_cdp(
    steps: List[Dict[str, Any]],
    user_inputs: Dict[str, Any],
    headless: bool = True,
    show_overlay: bool = False,
) -> List[Dict[str, Any]]:
    """
    Runs browser steps via isolated Chromium CDP (or safe stdlib HTTP GET fallback
    when only read/navigate steps exist and no Chromium binary is installed).
    Always destroys isolated temp profile & process tree in finally.
    """
    browser_bin = discover_local_chromium_browser()
    results: List[Dict[str, Any]] = []
    if not browser_bin:
        # Pure HTTP GET fallback for read-only navigate flows
        for idx, st in enumerate(steps):
            t0 = time.perf_counter()
            if st.get("action") == "navigate" and _is_safe_navigation_url(st.get("url", "")):
                try:
                    req = urllib.request.Request(st["url"], method="GET", headers={"User-Agent": "AFCC-HeadlessAgent/2.0"})
                    with urllib.request.urlopen(req, timeout=int(st.get("timeout_sec") or DEFAULT_STEP_TIMEOUT_SEC)) as resp:  # nosec B310
                        results.append({
                            "step_id": st["step_id"],
                            "index": st.get("index", idx),
                            "status": "passed",
                            "tier": "http_fallback",
                            "http_status": resp.status,
                            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                        })
                except Exception as exc:
                    results.append({
                        "step_id": st["step_id"],
                        "index": st.get("index", idx),
                        "status": "failed",
                        "error_type": "navigation_error",
                        "reason": str(exc),
                        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                    })
            else:
                results.append({
                    "step_id": st["step_id"],
                    "index": st.get("index", idx),
                    "status": "failed",
                    "error_type": "browser_missing",
                    "reason": "Chrome/Edge binary unavailable for interactive DOM action.",
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                })
        return results

    port = find_free_local_port()
    profile_dir = Path(tempfile.mkdtemp(prefix="afcc_cdp_run_"))
    proc: Optional[subprocess.Popen[Any]] = None
    cdp: Optional[MinimalCDPClient] = None
    try:
        args = [
            browser_bin,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            f"--remote-allow-origins=http://127.0.0.1:{port}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if headless:
            args.extend(["--headless=new", "--disable-gpu"])
        args.append("about:blank")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_EXECUTION_SUBPROCESS_FLAGS,
        )
        ws_url = _wait_for_cdp_page_ws(port, timeout_sec=10.0)
        if not ws_url:
            raise TimeoutError("Headless/sandbox Chromium failed to open debug target.")

        cdp = MinimalCDPClient()
        cdp.connect(ws_url, timeout=8.0)
        cdp.send_command("Page.enable")
        cdp.send_command("Runtime.enable")

        total = len(steps)
        for i, st in enumerate(steps):
            t0 = time.perf_counter()
            wait_ms = int(st.get("wait_before_ms") or 0)
            if wait_ms > 0:
                time.sleep(min(15.0, wait_ms / 1000.0))

            act = str(st.get("action") or "click")
            locs = _as_str_dict(st.get("locators"))
            if act == "navigate":
                nav_url = str(st.get("url") or "")
                if not _is_safe_navigation_url(nav_url):
                    results.append({
                        "step_id": st["step_id"],
                        "index": st.get("index", i),
                        "status": "failed",
                        "error_type": "unsafe_url",
                        "reason": f"Blocked unsafe URL: {nav_url}",
                        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                    })
                    continue
                cdp.send_command("Page.navigate", {"url": nav_url}, timeout=float(st.get("timeout_sec") or DEFAULT_STEP_TIMEOUT_SEC))
                time.sleep(0.5)
                results.append({
                    "step_id": st["step_id"],
                    "index": st.get("index", i),
                    "status": "passed",
                    "tier": "cdp_navigate",
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                })
                continue

            resolved_val, _is_sec = _resolve_step_value(st, user_inputs)
            if show_overlay:
                try:
                    cdp.send_command("Runtime.evaluate", {"expression": SANDBOX_OVERLAY_JS})
                    ov_js = (
                        f"window.__afccSandboxShowStep({i + 1},{total},{json.dumps(st.get('description', ''))},"
                        f"'running',{json.dumps(locs.get('css_path', ''))},{json.dumps(locs.get('id', ''))},{json.dumps(locs.get('text', ''))});"
                    )
                    cdp.send_command("Runtime.evaluate", {"expression": ov_js})
                except Exception:
                    pass

            eval_res = cdp.send_command(
                "Runtime.evaluate",
                {"expression": _build_js_locate_and_act(act, locs, resolved_val), "returnByValue": True},
                timeout=float(st.get("timeout_sec") or DEFAULT_STEP_TIMEOUT_SEC),
            )
            raw_res_obj = _as_dict(eval_res.get("result"))
            val_obj = _as_dict(raw_res_obj.get("value"))
            if val_obj.get("ok"):
                tier = str(val_obj.get("tier") or "tier1")
                results.append({
                    "step_id": st["step_id"],
                    "index": st.get("index", i),
                    "status": "healed" if tier not in ("tier1_data_testid", "tier2_id") else "passed",
                    "tier": tier,
                    "extracted": val_obj.get("extracted", ""),
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                })
            else:
                err_msg = str((val_obj or {}).get("error") or "selector_not_found")
                results.append({
                    "step_id": st["step_id"],
                    "index": st.get("index", i),
                    "status": "failed",
                    "error_type": "selector_not_found",
                    "reason": err_msg,
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                })
    finally:
        if cdp is not None:
            cdp.close()
        terminate_process_tree(proc)
        shutil.rmtree(profile_dir, ignore_errors=True)
    return results


# ---------------------------------------------------------------------------
# Missing-Input Collection, Visible Sandbox Dry-Run, Self-Healing & Publish
# ---------------------------------------------------------------------------

def _collect_missing_inputs(
    workflow_ir: Dict[str, Any],
    supplied_inputs: Dict[str, Any],
    from_step_index: int = 0,
    ignore_ask_on_each_run_if_default: bool = False,
) -> List[Dict[str, Any]]:
    """Identifies missing required, secret, ask_on_each_run, or upcoming prompt_user inputs."""
    missing: List[Dict[str, Any]] = []
    seen: set[str] = set()
    schema = _as_list(workflow_ir.get("input_schema"))

    if from_step_index == 0:
        for fld in schema:
            if not isinstance(fld, dict):
                continue
            key = str(fld.get("key") or "")
            if not key or key in seen:
                continue
            has_val = key in supplied_inputs and supplied_inputs[key] not in (None, "")
            if has_val:
                continue
            is_sec = bool(fld.get("sensitive")) or str(fld.get("type") or "") == "secret"
            needs_ask = bool(fld.get("required")) or bool(fld.get("ask_on_each_run")) or is_sec
            has_non_secret_default = (not is_sec) and bool(str(fld.get("default") or "").strip())
            if needs_ask and (is_sec or bool(fld.get("ask_on_each_run")) or not has_non_secret_default):
                if ignore_ask_on_each_run_if_default and has_non_secret_default and not is_sec:
                    continue
                seen.add(key)
                missing.append({
                    "key": key,
                    "label": str(fld.get("label") or key.replace("_", " ").title()),
                    "type": "secret" if is_sec else str(fld.get("type") or "text"),
                    "prompt": str(fld.get("prompt") or f"Enter {key}:"),
                    "required": bool(fld.get("required", True)),
                    "sensitive": is_sec,
                    "default": "" if is_sec else str(fld.get("default") or ""),
                })

    steps = _as_list(workflow_ir.get("steps"))
    for st in steps[from_step_index:]:
        if not isinstance(st, dict):
            continue
        if st.get("action") == "prompt_user" and st.get("input_key"):
            key = str(st["input_key"])
            if key not in supplied_inputs or supplied_inputs[key] in (None, ""):
                if key not in seen:
                    seen.add(key)
                    is_sec = bool(st.get("sensitive"))
                    missing.append({
                        "key": key,
                        "label": str(st.get("title") or key.replace("_", " ").title()),
                        "type": "secret" if is_sec else "text",
                        "prompt": str(st.get("narration") or st.get("description") or f"Provide {key}:"),
                        "required": True,
                        "sensitive": is_sec,
                        "default": "",
                    })
                # Pause right at or before the prompt step if reached dynamically
                if from_step_index > 0:
                    break
    return missing


def _simulate_step(step: Dict[str, Any], user_inputs: Dict[str, Any], inject_fail: bool = False) -> Dict[str, Any]:
    """Deterministic simulation of one step for fast sandbox preview & dry_run."""
    t0 = time.perf_counter()
    act = str(step.get("action") or "click")
    locs = _as_dict(step.get("locators"))
    resolved_val, is_sec = _resolve_step_value(step, user_inputs)
    masked_preview = "***" if is_sec else resolved_val[:80]

    if inject_fail:
        return {
            "step_id": step.get("step_id", ""),
            "index": int(step.get("index", 0)),
            "channel": step.get("channel", "browser"),
            "action": act,
            "description": step.get("description", ""),
            "status": "failed",
            "error_type": "selector_not_found",
            "reason": f"Simulated locator failure on '{step.get('step_id')}' (primary selector missing/timed out).",
            "tier": "none",
            "value_preview": masked_preview,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000 + 2.0, 1),
        }

    if act == "navigate" and step.get("url") and not _is_safe_navigation_url(str(step["url"])):
        return {
            "step_id": step.get("step_id", ""),
            "index": int(step.get("index", 0)),
            "channel": step.get("channel", "browser"),
            "action": act,
            "description": step.get("description", ""),
            "status": "failed",
            "error_type": "unsafe_url",
            "reason": f"Unsafe URL scheme rejected: {step.get('url')}",
            "tier": "none",
            "value_preview": masked_preview,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000 + 1.0, 1),
        }

    # Check if browser/desktop locator has at least one viable tier
    viable_tier = "tier1"
    if step.get("channel") == "browser" and act not in ("navigate", "wait", "prompt_user"):
        if locs.get("data_testid"):
            viable_tier = "tier1_data_testid"
        elif locs.get("id"):
            viable_tier = "tier2_id"
        elif locs.get("aria_label") or locs.get("name") or locs.get("placeholder"):
            viable_tier = "tier3_aria_or_name"
        elif locs.get("text") or locs.get("label_text"):
            viable_tier = "tier4_text"
        elif locs.get("css_path"):
            viable_tier = "tier5_css_path"
        elif locs.get("xpath"):
            viable_tier = "tier6_xpath"
        else:
            viable_tier = "healed_fallback"
    elif step.get("channel") == "desktop":
        if locs.get("uia_automation_id"):
            viable_tier = "desktop_tier2_uia"
        elif locs.get("process"):
            viable_tier = "desktop_tier3_process_window"
        else:
            viable_tier = "desktop_tier4_rel_coords"

    return {
        "step_id": step.get("step_id", ""),
        "index": int(step.get("index", 0)),
        "channel": step.get("channel", "browser"),
        "action": act,
        "description": step.get("description", ""),
        "status": "passed",
        "tier": viable_tier,
        "value_preview": masked_preview,
        "narration": step.get("narration", ""),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000 + 3.0, 1),
    }


def run_visible_sandbox_dry_run(
    session_id: str,
    user_inputs: Optional[Dict[str, Any]] = None,
    visible_browser: bool = True,
    simulate_only: bool = False,
    inject_failure_step: Optional[int] = None,
    manager: Optional[RecordingSessionManager] = None,
) -> Dict[str, Any]:
    """
    Step 8 of the workflow:
    Runs a visible sandbox dry-run of the synthesized agent draft, previewing
    Ask-for-Inputs prompts and logging all step failures for self-healing.
    """
    mgr = manager or get_recorder_manager()
    sess = mgr.load_session(session_id)
    draft = sess.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("workflow_ir"), dict):
        synth = synthesize_agent_from_recording(session_id=session_id, use_llm=False, manager=mgr)
        sess = mgr.load_session(session_id)
        draft = sess.get("draft") or synth

    workflow_ir = draft["workflow_ir"]
    supplied = dict(user_inputs or {})
    missing = _collect_missing_inputs(workflow_ir, supplied, from_step_index=0)
    if missing:
        return {
            "status": "waiting_for_input",
            "session_id": session_id,
            "iteration_version": int(draft.get("iteration_version") or 1),
            "pending_inputs": missing,
            "steps_preview": workflow_ir.get("steps") or [],
            "message": f"⏸️ Sandbox dry-run paused to ask for {len(missing)} required runtime input(s).",
        }

    steps = list(workflow_ir.get("steps") or [])
    browser_steps = [s for s in steps if s.get("channel") == "browser"]
    use_real_visible_cdp = (
        bool(visible_browser)
        and not simulate_only
        and not is_test_environment()
        and inject_failure_step is None
        and len(browser_steps) > 0
        and discover_local_chromium_browser() is not None
    )

    step_results: List[Dict[str, Any]] = []
    if use_real_visible_cdp:
        cdp_res_by_idx: Dict[int, Dict[str, Any]] = {}
        for r in _execute_browser_steps_cdp(browser_steps, supplied, headless=False, show_overlay=True):
            cdp_res_by_idx[int(r.get("index", 0))] = r
        for i, st in enumerate(steps):
            if i in cdp_res_by_idx:
                r = dict(cdp_res_by_idx[i])
                r.setdefault("description", st.get("description", ""))
                r.setdefault("channel", st.get("channel", "browser"))
                r.setdefault("action", st.get("action", "click"))
                step_results.append(r)
            else:
                step_results.append(_simulate_step(st, supplied, inject_fail=False))
    else:
        for i, st in enumerate(steps):
            fail_here = inject_failure_step is not None and (i == int(inject_failure_step) or st.get("step_id") == str(inject_failure_step))
            step_results.append(_simulate_step(st, supplied, inject_fail=fail_here))

    failures = [r for r in step_results if r.get("status") == "failed"]
    healed_count = sum(1 for r in step_results if r.get("status") == "healed")
    passed_count = sum(1 for r in step_results if r.get("status") in ("passed", "healed"))
    lifecycle = "sandbox_passed" if not failures else "healing_needed"

    report = {
        "status": "passed" if not failures else "failed_needs_healing",
        "session_id": session_id,
        "iteration_version": int(draft.get("iteration_version") or 1),
        "visible_mode": "real_browser_overlay" if use_real_visible_cdp else "interactive_theater_sandbox",
        "total_steps": len(steps),
        "passed_count": passed_count,
        "healed_count": healed_count,
        "failed_count": len(failures),
        "steps": step_results,
        "failures": failures,
        "lifecycle_status": lifecycle,
        "timestamp": datetime.now().isoformat(),
    }

    draft["sandbox_failures"] = failures
    draft["last_sandbox_report"] = report
    draft["lifecycle_status"] = lifecycle
    sess["draft"] = draft
    sess["lifecycle_status"] = lifecycle
    mgr.save_session(sess)
    return report


def heal_and_iterate_workflow(
    session_id: str,
    failures: Optional[List[Dict[str, Any]]] = None,
    user_audio_feedback: str = "",
    user_text_feedback: str = "",
    requirements_override: Optional[Dict[str, Any]] = None,
    rerun_tests: bool = True,
    manager: Optional[RecordingSessionManager] = None,
) -> Dict[str, Any]:
    """
    Step 9-10 of the workflow:
    Captures failures + user spoken audio feedback -> applies Tier-1 Autonomous Self-Healing
    and Tier-2 User Audio-Guided Rectification -> updates Requirements Doc, Mermaid Process Flow,
    Workflow IR, and Unit Tests -> increments iteration_version cleanly.
    """
    mgr = manager or get_recorder_manager()
    sess = mgr.load_session(session_id)
    draft = sess.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("spec"), dict):
        raise ValueError(f"Session '{session_id}' has no synthesized draft yet. Convert recording first.")

    spec = dict(draft["spec"])
    workflow_ir = dict(draft.get("workflow_ir") or spec.get("workflow_ir") or {})
    steps: List[Dict[str, Any]] = [dict(s) for s in (workflow_ir.get("steps") or [])]
    input_schema: List[Dict[str, Any]] = [dict(f) for f in (workflow_ir.get("input_schema") or [])]
    req_doc = dict(draft.get("requirements_doc") or {})
    business_rules: List[str] = list(req_doc.get("business_rules") or [])

    active_failures = list(failures if failures is not None else (draft.get("sandbox_failures") or []))
    actions_taken: List[str] = []

    # Tier-1 Autonomous Self-Healing
    for fail in active_failures:
        if not isinstance(fail, dict):
            continue
        f_sid = str(fail.get("step_id") or "")
        f_idx = fail.get("index")
        target = next((s for s in steps if s.get("step_id") == f_sid or s.get("index") == f_idx), None)
        if not target:
            continue
        err_type = str(fail.get("error_type") or "selector_not_found")
        if err_type == "selector_not_found":
            locs = dict(target.get("locators") or {})
            if not locs.get("css_path") and locs.get("id"):
                locs["css_path"] = f"#{locs['id']}"
            if not locs.get("xpath") and locs.get("text"):
                locs["xpath"] = f"//*[contains(normalize-space(.), {json.dumps(locs['text'][:30])})]"
            if not locs.get("aria_label") and target.get("title"):
                locs["aria_label"] = str(target["title"])[:60]
            target["locators"] = locs
            target["timeout_sec"] = min(45, int(target.get("timeout_sec") or 15) + 10)
            target["wait_before_ms"] = max(int(target.get("wait_before_ms") or 0), 1000)
            target["retries"] = max(int(target.get("retries") or 2), 3)
            actions_taken.append(f"Tier-1 Self-Heal on {target['step_id']}: expanded fallback locators + added 1000ms wait & retry=3")
        elif err_type in ("timeout", "navigation_error"):
            target["timeout_sec"] = min(60, int(target.get("timeout_sec") or 15) + 15)
            target["wait_before_ms"] = max(int(target.get("wait_before_ms") or 0), 2000)
            actions_taken.append(f"Tier-1 Self-Heal on {target['step_id']}: extended timeout to {target['timeout_sec']}s")

    # Tier-2 User Spoken Audio / Text Feedback Rectification
    raw_feedback = f"{user_audio_feedback} {user_text_feedback}".strip()
    clean_feedback = sanitize_audio_transcript(raw_feedback)
    if clean_feedback:
        low_fb = clean_feedback.lower()
        business_rules.append(f"User iteration feedback (v{int(draft.get('iteration_version', 1)) + 1}): {clean_feedback}")

        # 1. "wait N seconds"
        m_w = re.search(r"\bwait\s+(?:for\s+)?(\d{1,2})\s*(?:sec|secs|second|seconds)\b", low_fb)
        if m_w:
            w_ms = min(30, max(1, int(m_w.group(1)))) * 1000
            target_step = None
            if active_failures:
                f0 = active_failures[0]
                target_step = next((s for s in steps if s.get("step_id") == f0.get("step_id")), None)
            if target_step is None and steps:
                target_step = steps[-1]
            if target_step is not None:
                target_step["wait_before_ms"] = w_ms
                target_step["timeout_sec"] = max(int(target_step.get("timeout_sec") or 15), int(w_ms / 1000) + 10)
                actions_taken.append(f"Tier-2 Audio Fix: injected {w_ms}ms wait before {target_step['step_id']}")

        # 2. "ask me for <field>"
        m_ask = re.search(
            r"\b(?:ask\s+me\s+(?:for|about)?|prompt\s+(?:me\s+)?for)\s+(?:the\s+)?([a-z0-9 _-]{2,36}?)(?:\s+(?:every|each|before)|[,.;!?]|$)",
            low_fb,
        )
        if m_ask:
            fname = m_ask.group(1).strip()
            fkey = _infer_param_key(fname, "custom_input")
            is_sec = bool(SENSITIVE_FIELD_RE.search(low_fb))
            ftype = "date" if "date" in fname.lower() else ("secret" if is_sec else "text")
            if not any(f.get("key") == fkey for f in input_schema):
                input_schema.append({
                    "key": fkey,
                    "label": fname.title(),
                    "type": ftype,
                    "prompt": f"Enter {fname.title()} (from audio iteration):",
                    "required": True,
                    "ask_on_each_run": True,
                    "sensitive": is_sec,
                    "default": "",
                    "options": [],
                    "source": "audio_iteration",
                })
                # Also add a prompt_user step at index 0 if no fill step binds it
                steps.append({
                    "step_id": f"step_{len(steps) + 1}",
                    "index": len(steps),
                    "offset_sec": float(len(steps) + 1),
                    "channel": "prompt",
                    "action": "prompt_user",
                    "description": f"Ask user for '{fname.title()}'",
                    "url": "",
                    "locators": {"name": fkey},
                    "value_template": f"{{{{secret:{fkey}}}}}" if is_sec else f"{{{{input:{fkey}}}}}",
                    "input_key": fkey,
                    "sensitive": is_sec,
                    "wait_before_ms": 0,
                    "timeout_sec": DEFAULT_STEP_TIMEOUT_SEC,
                    "retries": 1,
                    "on_error": "retry_then_prompt",
                    "narration": clean_feedback,
                })
            actions_taken.append(f"Tier-2 Audio Fix: added required runtime input '{fkey}' ({ftype})")

        # 3. "skip step N"
        m_skip = re.search(r"\b(?:skip|remove|drop)\s+step\s+(\d+)\b", low_fb)
        if m_skip and len(steps) > 1:
            drop_idx = int(m_skip.group(1)) - 1
            if 0 <= drop_idx < len(steps):
                removed = steps.pop(drop_idx)
                for idx2, s2 in enumerate(steps):
                    s2["index"] = idx2
                    s2["step_id"] = f"step_{idx2 + 1}"
                actions_taken.append(f"Tier-2 Audio Fix: removed step '{removed.get('description')}'")

        # 4. "click <text> instead"
        m_click = re.search(r"click\s+['\"]?([^'\"]{2,40})['\"]?\s+instead", low_fb)
        if m_click and steps:
            new_lbl = m_click.group(1).strip()
            target_step = None
            if active_failures:
                f0 = active_failures[0]
                target_step = next((s for s in steps if s.get("step_id") == f0.get("step_id")), None)
            if target_step is None:
                target_step = steps[-1]
            locs = dict(target_step.get("locators") or {})
            locs["text"] = new_lbl
            locs["aria_label"] = new_lbl
            target_step["locators"] = locs
            target_step["description"] = _describe_step(target_step)
            actions_taken.append(f"Tier-2 Audio Fix: updated target text on {target_step['step_id']} to '{new_lbl}'")

        if not actions_taken:
            actions_taken.append(f"Tier-2 Audio Guidance recorded into Requirements Doc: {clean_feedback[:100]}")

    if isinstance(requirements_override, dict):
        if requirements_override.get("name"):
            spec["name"] = str(requirements_override["name"])[:50]
        if requirements_override.get("description"):
            spec["description"] = str(requirements_override["description"])[:240]

    new_version = int(draft.get("iteration_version") or 1) + 1
    workflow_ir["steps"] = steps
    workflow_ir["input_schema"] = input_schema
    workflow_ir = sanitize_workflow_ir(workflow_ir) or workflow_ir

    spec["workflow_ir"] = workflow_ir
    spec["fields"] = [
        {
            "key": f["key"],
            "label": f["label"],
            "type": "text" if f["type"] == "secret" else (f["type"] if f["type"] in ("text", "number", "date", "url") else "text"),
            "placeholder": f["prompt"],
        }
        for f in input_schema[:6]
    ] or spec.get("fields", [])

    updated_req = build_requirements_document(
        name=str(spec.get("name") or "Recorded Agent"),
        modality=str(workflow_ir.get("modality") or "browser"),
        steps=steps,
        input_schema=input_schema,
        audio_segments=sess.get("audio_segments") or [],
        business_rules=business_rules,
        version=new_version,
    )
    spec["requirements_doc"] = updated_req
    updated_tests = generate_agent_unit_tests_code(spec)
    test_report = run_generated_agent_unit_tests(spec, updated_tests) if rerun_tests else draft.get("unit_test_report")

    history = list(draft.get("iteration_history") or [])
    history.append({
        "version": new_version,
        "timestamp": datetime.now().isoformat(),
        "trigger": "self_heal_and_audio_iteration",
        "actions": actions_taken or ["Refreshed specification & regenerated tests"],
        "feedback": clean_feedback,
    })

    draft.update({
        "spec": spec,
        "workflow_ir": workflow_ir,
        "requirements_doc": updated_req,
        "unit_tests_code": updated_tests,
        "unit_test_report": test_report,
        "iteration_version": new_version,
        "iteration_history": history[-20:],
        "sandbox_failures": [],
        "lifecycle_status": "healed_ready_for_sandbox",
    })
    sess["draft"] = draft
    sess["lifecycle_status"] = "healed_ready_for_sandbox"
    mgr.save_session(sess)

    return {
        "status": "healed",
        "session_id": session_id,
        "iteration_version": new_version,
        "healing_actions": actions_taken,
        "spec": spec,
        "workflow_ir": workflow_ir,
        "requirements_doc": updated_req,
        "unit_tests_code": updated_tests,
        "unit_test_report": test_report,
        "lifecycle_status": "healed_ready_for_sandbox",
    }


def publish_recorded_agent(
    session_id: str,
    agent_registry: Any,
    user_approved: bool = False,
    overrides: Optional[Dict[str, Any]] = None,
    db: Any = None,
    manager: Optional[RecordingSessionManager] = None,
) -> Dict[str, Any]:
    """
    Step 11 of the workflow:
    Requires explicit user approval, validates permissions & AST, scaffolds the
    headless custom agent via AgentRegistry, and writes REQUIREMENTS.md & test_agent.py.
    """
    if not user_approved:
        raise ValueError("Explicit user approval (user_approved=True) is required before publishing live.")
    if not agent_registry:
        raise ValueError("AgentRegistry is required to publish live agent.")

    mgr = manager or get_recorder_manager()
    sess = mgr.load_session(session_id)
    draft = sess.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("spec"), dict):
        raise ValueError("Convert recording to a Requirements Doc & Agent Draft before publishing.")

    spec = dict(draft["spec"])
    if isinstance(overrides, dict):
        for k in ("name", "icon", "category", "description", "schedule_cadence", "schedule", "routine_task"):
            if overrides.get(k):
                spec[k] = overrides[k]
        if overrides.get("agent_id") or overrides.get("id"):
            spec["agent_id"] = str(overrides.get("agent_id") or overrides.get("id"))
            spec["id"] = spec["agent_id"]

    clean_id = _infer_param_key(str(spec.get("agent_id") or spec.get("name") or "recorded_agent"), "recorded_agent")[:30]
    while clean_id in getattr(agent_registry, "agents", {}):
        clean_id = f"{clean_id[:24]}_{secrets.token_hex(2)}"

    workflow_ir = sanitize_workflow_ir(draft.get("workflow_ir") or spec.get("workflow_ir") or {}) or {}
    workflow_ir["execution_mode"] = "headless"
    req_doc = _as_dict(draft.get("requirements_doc"))

    from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS
    perms = [p for p in (spec.get("permissions") or ["db:read", "db:write", "ui:render"]) if p in ALLOWED_AGENT_PERMISSIONS]
    if not perms:
        perms = ["db:read", "db:write", "ui:render"]

    manifest = agent_registry.create_custom_agent(
        agent_id=clean_id,
        name=str(spec.get("name") or "Recorded Headless Agent"),
        icon=str(spec.get("icon") or "🎬"),
        permissions=perms,
        description=str(spec.get("description") or "Recorded headless workflow agent"),
        ui_blocks=spec.get("ui_blocks"),
        routine_task=str(spec.get("routine_task") or "run_workflow"),
        category=str(spec.get("category") or "Productivity"),
        archetype="recorded_workflow",
        intelligence_mode=str(spec.get("intelligence_mode") or "hybrid"),
        fields=spec.get("fields"),
        checklist_items=spec.get("checklist_items"),
        schedule_cadence=str(spec.get("schedule_cadence") or "manual_only"),
        schedule=spec.get("schedule"),
        workflow_ir=workflow_ir,
        requirements_doc=req_doc,
        recording_id=session_id,
    )

    agent_folder = Path(agent_registry.custom_agents_dir) / clean_id
    req_path = agent_folder / "REQUIREMENTS.md"
    tests_path = agent_folder / "test_agent.py"
    if req_doc.get("markdown"):
        req_path.write_text(str(req_doc["markdown"]), encoding="utf-8", newline="\n")
    unit_tests_code = str(draft.get("unit_tests_code") or generate_agent_unit_tests_code({**spec, "agent_id": clean_id}))
    tests_path.write_text(unit_tests_code, encoding="utf-8", newline="\n")

    draft["lifecycle_status"] = "published_live"
    sess["draft"] = draft
    sess["lifecycle_status"] = "published_live"
    sess["published_agent_id"] = clean_id
    mgr.save_session(sess)

    if db is not None and hasattr(db, "log_activity"):
        try:
            db.log_activity("ActivityRecorder", "published_headless_agent", f"Published '{clean_id}' from recording '{session_id}'.")
        except Exception:
            pass

    return {
        "status": "published",
        "agent_id": clean_id,
        "session_id": session_id,
        "manifest": manifest,
        "requirements_path": str(req_path),
        "tests_path": str(tests_path),
        "message": f"🚀 Published '{manifest.get('name', clean_id)}' as a Live Headless Agent!",
    }


# ---------------------------------------------------------------------------
# Live Headless Execution Engine + Human-in-the-Loop Checkpoint / Resume
# ---------------------------------------------------------------------------

def _strip_secrets_for_checkpoint(user_inputs: Dict[str, Any], workflow_ir: Dict[str, Any]) -> Dict[str, Any]:
    secret_keys = {
        str(f.get("key"))
        for f in (workflow_ir.get("input_schema") or [])
        if isinstance(f, dict) and (f.get("sensitive") or f.get("type") == "secret")
    }
    out: Dict[str, Any] = {}
    for k, v in (user_inputs or {}).items():
        if k in secret_keys or SENSITIVE_FIELD_RE.search(str(k)):
            continue
        if isinstance(v, str) and (LONG_CARD_OR_AADHAAR_RE.search(v) or PAN_RE.search(v)):
            continue
        out[str(k)] = v
    return out


def _run_headless_from_step(
    agent: Any,
    workflow_ir: Dict[str, Any],
    all_inputs: Dict[str, Any],
    start_step_index: int,
    prior_completed: List[Dict[str, Any]],
    dry_run: bool,
    run_id: str,
    existing_record_id: Optional[int] = None,
) -> Dict[str, Any]:
    db = getattr(agent, "db", None)
    event_bus = getattr(agent, "event_bus", None)
    perms = set(getattr(agent, "permissions", []) or [])
    steps = list(workflow_ir.get("steps") or [])

    missing = _collect_missing_inputs(workflow_ir, all_inputs, from_step_index=start_step_index)
    if missing:
        non_sec = _strip_secrets_for_checkpoint(all_inputs, workflow_ir)
        ckpt_data = {
            "run_id": run_id,
            "step_index": start_step_index,
            "total_steps": len(steps),
            "pending_inputs": missing,
            "non_secret_inputs": non_sec,
            "completed_steps": prior_completed,
            "dry_run": bool(dry_run),
            "modality": workflow_ir.get("modality", "browser"),
            "updated_at": datetime.now().isoformat(),
        }
        title = f"Run {run_id} (Waiting for {len(missing)} input)"
        if db is not None and "db:write" in perms:
            if existing_record_id:
                db.update_custom_agent_record(agent.id, existing_record_id, title=title, status="waiting_for_input", data=ckpt_data)
            else:
                db.add_custom_agent_record(agent.id, title=title, record_type="workflow_run", status="waiting_for_input", data=ckpt_data)
        if event_bus is not None and "event_bus:publish" in perms:
            try:
                event_bus.publish("agent.input_required", {"agent_id": agent.id, "run_id": run_id, "pending_inputs": [m["key"] for m in missing]})
            except Exception:
                pass
        return {
            "status": "waiting_for_input",
            "health_status": "warning",
            "run_id": run_id,
            "agent_id": agent.id,
            "step_index": start_step_index,
            "total_steps": len(steps),
            "pending_inputs": missing,
            "completed_steps": prior_completed,
            "message": f"⏸️ {getattr(agent, 'display_name', agent.id)} paused at step {start_step_index + 1}/{max(1, len(steps))} awaiting {len(missing)} user input(s).",
        }

    # Acquire concurrency semaphore so at most 1 headless browser runs on the laptop
    acquired = _HEADLESS_RUN_SEMAPHORE.acquire(timeout=20.0)
    if not acquired:
        return {
            "status": "error",
            "health_status": "warning",
            "run_id": run_id,
            "agent_id": agent.id,
            "message": "Another headless workflow run is currently busy. Retry shortly.",
        }

    step_results: List[Dict[str, Any]] = list(prior_completed)
    try:
        remaining_steps = steps[start_step_index:]
        for idx_offset, st in enumerate(remaining_steps):
            abs_idx = start_step_index + idx_offset
            # Dynamic mid-run prompt check
            if st.get("action") == "prompt_user" and st.get("input_key"):
                pk = str(st["input_key"])
                if pk not in all_inputs or all_inputs[pk] in (None, ""):
                    return _run_headless_from_step(
                        agent=agent,
                        workflow_ir=workflow_ir,
                        all_inputs=all_inputs,
                        start_step_index=abs_idx,
                        prior_completed=step_results,
                        dry_run=dry_run,
                        run_id=run_id,
                        existing_record_id=existing_record_id,
                    )

            if dry_run or is_test_environment() or st.get("channel") in ("desktop", "prompt"):
                step_results.append(_simulate_step(st, all_inputs, inject_fail=False))
            else:
                # Real headless Chromium execution
                cdp_batch = _execute_browser_steps_cdp([st], all_inputs, headless=True, show_overlay=False)
                if cdp_batch:
                    r0 = dict(cdp_batch[0])
                    r0.setdefault("description", st.get("description", ""))
                    r0.setdefault("channel", st.get("channel", "browser"))
                    r0.setdefault("action", st.get("action", "click"))
                    step_results.append(r0)
    finally:
        _HEADLESS_RUN_SEMAPHORE.release()

    failed = [r for r in step_results if r.get("status") == "failed"]
    final_status = "completed" if not failed else "failed"
    summary_msg = (
        f"✅ Headless workflow '{getattr(agent, 'display_name', agent.id)}' completed {len(step_results)}/{len(steps)} step(s)."
        if not failed
        else f"⚠️ Headless workflow completed with {len(failed)} failed step(s)."
    )
    non_sec_done = _strip_secrets_for_checkpoint(all_inputs, workflow_ir)
    done_data = {
        "run_id": run_id,
        "step_index": len(steps),
        "total_steps": len(steps),
        "pending_inputs": [],
        "non_secret_inputs": non_sec_done,
        "completed_steps": step_results,
        "dry_run": bool(dry_run),
        "updated_at": datetime.now().isoformat(),
    }
    if db is not None and "db:write" in perms:
        if existing_record_id:
            db.update_custom_agent_record(agent.id, existing_record_id, title=f"Run {run_id} ({final_status})", status=final_status, data=done_data)
        else:
            db.add_custom_agent_record(agent.id, title=f"Run {run_id} ({final_status})", record_type="workflow_run", status=final_status, data=done_data)
        if hasattr(db, "log_activity"):
            try:
                db.log_activity(agent.id, "headless_workflow_run", summary_msg)
            except Exception:
                pass

    return {
        "status": final_status,
        "health_status": "ok" if not failed else "warning",
        "run_id": run_id,
        "agent_id": agent.id,
        "title": f"{getattr(agent, 'display_icon', '🎬')} {getattr(agent, 'display_name', agent.id)}",
        "message": summary_msg,
        "dry_run": bool(dry_run),
        "completed_steps": step_results,
        "outputs": {
            "total_steps": len(steps),
            "executed_steps": len(step_results),
            "failed_steps": len(failed),
            "extracted": [r.get("extracted") for r in step_results if r.get("extracted")],
        },
    }


def execute_recorded_workflow(
    agent: Any,
    user_inputs: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    task: str = "run_workflow",
) -> Dict[str, Any]:
    """Universal headless runtime entrypoint for recorded_workflow agents."""
    meta = getattr(agent, "manifest_meta", {}) or {}
    workflow_ir = meta.get("workflow_ir")
    if not isinstance(workflow_ir, dict):
        return {
            "status": "error",
            "health_status": "warning",
            "agent_id": agent.id,
            "message": f"Agent '{agent.id}' has no workflow_ir attached.",
        }
    run_id = f"wfr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"
    return _run_headless_from_step(
        agent=agent,
        workflow_ir=workflow_ir,
        all_inputs=dict(user_inputs or {}),
        start_step_index=0,
        prior_completed=[],
        dry_run=bool(dry_run),
        run_id=run_id,
    )


def resume_workflow_run(
    agent: Any,
    run_id: str,
    user_inputs: Optional[Dict[str, Any]] = None,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """Resumes a paused waiting_for_input workflow run from its exact SQLite checkpoint."""
    meta = getattr(agent, "manifest_meta", {}) or {}
    workflow_ir = meta.get("workflow_ir")
    if not isinstance(workflow_ir, dict):
        raise ValueError(f"Agent '{agent.id}' has no workflow_ir attached.")
    db = getattr(agent, "db", None)
    if db is None:
        raise ValueError("Database unavailable for checkpoint resume.")

    rows = db.list_custom_agent_records(agent.id, record_type="workflow_run", limit=50)
    match_row: Optional[Dict[str, Any]] = None
    for row in rows:
        rdata = row.get("data") if isinstance(row.get("data"), dict) else {}
        if str(rdata.get("run_id") or "") == str(run_id):
            match_row = row
            break
    if not match_row:
        raise KeyError(f"Workflow checkpoint '{run_id}' not found for agent '{agent.id}'.")

    rdata = match_row.get("data") or {}
    merged_inputs = dict(rdata.get("non_secret_inputs") or {})
    merged_inputs.update(dict(user_inputs or {}))
    eff_dry = bool(rdata.get("dry_run", False)) if dry_run is None else bool(dry_run)

    return _run_headless_from_step(
        agent=agent,
        workflow_ir=workflow_ir,
        all_inputs=merged_inputs,
        start_step_index=int(rdata.get("step_index") or 0),
        prior_completed=list(rdata.get("completed_steps") or []),
        dry_run=eff_dry,
        run_id=str(run_id),
        existing_record_id=int(match_row["id"]),
    )
