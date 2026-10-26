"""
At-Rest Cryptographic Vault for Personal Agentic Fleet.
Provides transparent at-rest encryption for sensitive database settings, tokens, and notes:
  1. Primary (Windows): Native Windows Data Protection API (DPAPI) via ctypes.windll.crypt32
     (CryptProtectData / CryptUnprotectData) bound to the logged-in Windows user credentials.
  2. Portable Fallback & Authenticated Envelope: 256-bit Master Key stored in Windows Credential
     Manager (DPAPI keyring) or user-scoped DPAPI keyfile (fleet/data/user/master.dpapi) with
     HMAC-SHA256 authenticated SHA-256 CTR stream encryption.
Zero external C-compiler dependencies; uses 100% Python standard library.
"""

import base64
import ctypes
from ctypes import POINTER, Structure, byref, c_buffer, c_char
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Optional

from fleet.config import DATA_DIR, get_secure_secret

USER_DATA_DIR = DATA_DIR / "user"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def set_secure_secret(key_name: str, secret_value: str) -> bool:
    """Stores a secret in OS Credential Vault (Windows Credential Manager / macOS Keychain) and os.environ."""
    os.environ[key_name] = secret_value
    try:
        import keyring
        keyring.set_password("fleet_os", key_name, secret_value)
        return True
    except Exception:
        pass

    # Native macOS Keychain fallback via /usr/bin/security
    if sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["/usr/bin/security", "add-generic-password", "-s", "fleet_os", "-a", key_name, "-w", secret_value, "-U"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            pass

    return False

ENCRYPTION_PREFIX = "ENC:v1:"
DPAPI_PREFIX = "ENC:dpapi:"
MASTER_KEY_FILE = USER_DATA_DIR / "master.dpapi"


class _DATA_BLOB(Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", POINTER(c_char)),
    ]


def _dpapi_encrypt_bytes(raw_bytes: bytes) -> Optional[bytes]:
    """Encrypts bytes using native Windows OS kernel DPAPI (crypt32.dll)."""
    if sys.platform != "win32" or not hasattr(ctypes, "windll"):
        return None
    try:
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        buf = c_buffer(raw_bytes, len(raw_bytes))
        blob_in = _DATA_BLOB(len(raw_bytes), buf)
        blob_out = _DATA_BLOB()

        res = ctypes.windll.crypt32.CryptProtectData(
            byref(blob_in),
            "PersonalAgenticFleetVault",
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            byref(blob_out),
        )
        if not res:
            return None
        try:
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            return encrypted
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


def _dpapi_decrypt_bytes(enc_bytes: bytes) -> Optional[bytes]:
    """Decrypts bytes using native Windows OS kernel DPAPI (crypt32.dll)."""
    if sys.platform != "win32" or not hasattr(ctypes, "windll"):
        return None
    try:
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        buf = c_buffer(enc_bytes, len(enc_bytes))
        blob_in = _DATA_BLOB(len(enc_bytes), buf)
        blob_out = _DATA_BLOB()

        res = ctypes.windll.crypt32.CryptUnprotectData(
            byref(blob_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            byref(blob_out),
        )
        if not res:
            return None
        try:
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            return decrypted
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


def get_or_create_master_key() -> bytes:
    """
    Retrieves or generates a 256-bit (32-byte) master key protected by Windows DPAPI /
    Windows Credential Manager.
    """
    # 1. Check environment / Credential Manager first
    stored_hex = get_secure_secret("FLEET_DB_MASTER_KEY", "")
    if stored_hex and len(stored_hex) == 64:
        try:
            return bytes.fromhex(stored_hex)
        except ValueError:
            pass

    # 2. Check local DPAPI-protected master key file in fleet/data/user/master.dpapi
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if MASTER_KEY_FILE.is_file():
        try:
            raw_file = MASTER_KEY_FILE.read_bytes()
            dec = _dpapi_decrypt_bytes(raw_file)
            if dec and len(dec) == 32:
                return dec
            if len(raw_file) == 32:
                return raw_file
        except Exception:
            pass

    # 3. Generate a fresh 256-bit cryptographic key
    new_key = secrets.token_bytes(32)
    set_secure_secret("FLEET_DB_MASTER_KEY", new_key.hex())
    try:
        dpapi_blob = _dpapi_encrypt_bytes(new_key)
        MASTER_KEY_FILE.write_bytes(dpapi_blob if dpapi_blob else new_key)
        if os.name != "nt":
            MASTER_KEY_FILE.chmod(0o600)
    except Exception:
        pass
    return new_key


def _stream_xor_crypt(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """Deterministic SHA-256 counter-mode keystream XOR."""
    out = bytearray(len(data))
    block_count = (len(data) + 31) // 32
    for counter in range(block_count):
        counter_bytes = counter.to_bytes(8, "big")
        keystream = hashlib.sha256(key + nonce + counter_bytes).digest()
        start = counter * 32
        end = min(start + 32, len(data))
        for i in range(start, end):
            out[i] = data[i] ^ keystream[i - start]
    return bytes(out)


def encrypt_sensitive_text(plaintext: str) -> str:
    """
    Encrypts a plaintext string at rest using authenticated encryption (HMAC-SHA256 + SHA256-CTR)
    backed by the Windows DPAPI master key. Idempotent if already encrypted.
    """
    if not plaintext or plaintext.startswith((ENCRYPTION_PREFIX, DPAPI_PREFIX)):
        return plaintext

    key = get_or_create_master_key()
    nonce = secrets.token_bytes(16)
    pt_bytes = plaintext.encode("utf-8")
    ciphertext = _stream_xor_crypt(pt_bytes, key, nonce)
    mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    payload = base64.urlsafe_b64encode(nonce + mac + ciphertext).decode("ascii")
    return f"{ENCRYPTION_PREFIX}{payload}"


def decrypt_sensitive_text(value: str) -> str:
    """
    Decrypts an ENC:v1:... or ENC:dpapi:... string after verifying its HMAC-SHA256 integrity tag.
    Returns plaintext unmodified if not prefixed.
    """
    if not value:
        return value

    if value.startswith(DPAPI_PREFIX):
        raw_b64 = value[len(DPAPI_PREFIX):]
        dec = _dpapi_decrypt_bytes(base64.urlsafe_b64decode(raw_b64.encode("ascii")))
        if dec is None:
            raise ValueError("DPAPI decryption failed or unauthorized user context")
        return dec.decode("utf-8")

    if not value.startswith(ENCRYPTION_PREFIX):
        return value

    raw_b64 = value[len(ENCRYPTION_PREFIX):]
    blob = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
    if len(blob) < 48:
        raise ValueError("Corrupted encrypted payload")

    nonce = blob[:16]
    mac = blob[16:48]
    ciphertext = blob[48:]

    key = get_or_create_master_key()
    expected_mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Cryptographic HMAC verification failed: ciphertext tampered or wrong key")

    pt_bytes = _stream_xor_crypt(ciphertext, key, nonce)
    return pt_bytes.decode("utf-8")
