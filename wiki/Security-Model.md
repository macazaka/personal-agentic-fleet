# Security Model & Cryptographic Vault

The Personal Agentic Fleet is architected on a zero-trust, local-first foundation. Sensitive credentials, user tokens, and private databases never leave your physical workstation.

---

## The 12-Layer Security Scanner

Before every commit, the automated pre-commit hook runs the **12-Layer Security Scanner** (`fleet/tools/security_scanner.py`):

1. **API Keys & Secret Scanner**: High-confidence entropy checks for Google, AWS, Azure, GitHub, OpenAI, and Anthropic API keys.
2. **PII & Git History Audit**: Scans all tracked files and commit history against `fleet/data/user/pii_blocklist.json`.
3. **Git Hygiene & File Exclusion**: Asserts sensitive databases (`*.db`, `*.dpapi`) are strictly gitignored.
4. **Static Application Security Testing (SAST & CodeQL Guard)**:
   - Rejects `shell=True` on any subprocess call (CWE-078).
   - Rejects incomplete URL substring sanitization (CWE-020).
   - Rejects weak hashing algorithms (`md5`/`sha1`) without `usedforsecurity=False` (CWE-327).
   - Rejects dynamic f-strings in `cursor.execute(...)` (CWE-089 SQL Injection).
5. **Localhost HTTP Boundary**: Blocks external binding; restricts default listening socket to `127.0.0.1`.
6. **Scoped User Data Vault**: Verifies user-specific credentials reside exclusively in `fleet/data/user/`.
7. **At-Rest DPAPI & PBKDF2 Vault**: Verifies cryptographic roundtrip and HMAC tamper detection.
8. **CSP & DNS-Rebinding Defense**: Enforces strict Content-Security-Policy and rejects cross-site Host headers.
9. **Plugin Capability Sandboxing**: Rejects undeclared permissions in `manifest.json`.
10. **Supply Chain SBOM Provenance**: Verifies CycloneDX SBOM integrity and Dependabot configuration.
11. **Zero-Token Cost Governance**: Asserts background daemons never invoke paid LLM APIs ($0.00 audit).
12. **Runtime Python >=3.10 Guard**: Pinning minimum Python version and self-bootstrapping integrity.

---

## At-Rest Cryptographic Vault

Sensitive database fields and API tokens are encrypted at rest:

- **Key Derivation**: Implements **NIST SP 800-132 PBKDF2-HMAC-SHA256** with 100,000 iterations to derive keystreams and dedicated MAC subkeys.
- **OS Platform Vaults**:
  - **Windows**: Windows Data Protection API (`DPAPI`) via `ctypes.windll.crypt32` bound to the active user login session.
  - **macOS**: Apple Keychain service integration via `/usr/bin/security`.
  - **Linux**: Freedesktop SecretService integration via `secret-tool`.
