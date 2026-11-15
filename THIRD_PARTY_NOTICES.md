# 📜 Third-Party Open-Source Notices & Scientific Credits

**Personal Agentic Fleet — Agentic Fleet Control Center (AFCC)** is distributed under the **[Apache License 2.0](LICENSE)**.

This document provides full attribution, copyright notices, and license terms for all open-source software libraries, fonts, web standards, and published scientific algorithms used in or alongside this project.

---

## 🏗️ 1. Core Architectural Footprint (Zero Mandatory Third-Party Runtime Dependencies)

The core Personal Agentic Fleet microkernel (`fleet/server.py`, `fleet/core/*`, `fleet/api/*`, `fleet/agents/*`) and the frontend web cockpit (`fleet/web/static/js/*`, `fleet/web/static/css/*`) are engineered with **zero mandatory third-party runtime packages** (`dependencies = []` in [`pyproject.toml`](pyproject.toml)):

| Component | License | Author / Steward | Scope in Personal Agentic Fleet |
| :--- | :--- | :--- | :--- |
| **Python Standard Library** (`http.server`, `sqlite3`, `ssl`, `hashlib`, `hmac`, `secrets`, `urllib`, `wave`, `math`) | **PSF-2.0** (Python Software Foundation License v2) | Python Software Foundation | Core HTTP/HTTPS server, SQLite persistence, PBKDF2/HMAC cryptography, and CLI tooling |
| **W3C Web Audio API & MediaStream API** (`AudioContext`, `AnalyserNode`, `BiquadFilterNode`, `MediaRecorder`) | **W3C Royalty-Free Standard** | W3C Audio Working Group | Real-time 100 Hz–7.5 kHz DSP band-pass filtering, adaptive VAD endpointing, and 12-D acoustic voiceprint extraction |
| **W3C Web Speech API** (`SpeechRecognition`, `speechSynthesis`) | **W3C Community Group Specification** | W3C Speech API Community Group | Local/browser speech-to-text recognition and multi-language TTS synthesis |

---

## 🔐 2. Optional Production & Integration Libraries

When optional features (AES-256-GCM hardware vault, OS keychain integration, YAML configs, Google Workspace OAuth2, PDF extraction, or MCP SDK fallback) are enabled via `pip install -e ".[full]"`, the following open-source packages are used via lazy/optional imports:

| Package | Version Constraint | SPDX License | Copyright / Author | Where Used in Codebase |
| :--- | :--- | :--- | :--- | :--- |
| **[`cryptography`](https://github.com/pyca/cryptography)** | `>=50.0.0` | `Apache-2.0 OR BSD-3-Clause` | Copyright © Individual Contributors / Python Cryptographic Authority (PyCA) | [`fleet/core/crypto_vault.py`](fleet/core/crypto_vault.py) (AES-256-GCM at-rest encryption) & [`fleet/core/local_tls.py`](fleet/core/local_tls.py) (local X.509 Root CA & SAN TLS certificate generation) |
| **[`keyring`](https://github.com/jaraco/keyring)** | `>=24.0.0` | `MIT` | Copyright © Kang Zhang, Jason R. Coombs (`jaraco`) | OS-native credential vault integration (Windows Credential Locker, macOS Keychain, Linux SecretService) |
| **[`PyYAML`](https://github.com/yaml/pyyaml)** | `>=6.0` | `MIT` | Copyright © 2017–2026 Ingy döt Net; Copyright © 2006–2016 Kirill Simonov | Optional YAML configuration parsing (`fleet.yaml`, `schedules.yaml`) |
| **[`google-api-python-client`](https://github.com/googleapis/google-api-python-client)** | `>=2.100.0` | `Apache-2.0` | Copyright © Google LLC | [`fleet/integrations/gmail_client.py`](fleet/integrations/gmail_client.py) & [`fleet/api/health_api.py`](fleet/api/health_api.py) (optional Gmail & YouTube OAuth2 client) |
| **[`google-auth-httplib2`](https://github.com/googleapis/google-auth-library-python-httplib2)** | `>=0.1.1` | `Apache-2.0` | Copyright © Google LLC | [`fleet/integrations/gmail_client.py`](fleet/integrations/gmail_client.py) (HTTP transport adapter for Google Auth) |
| **[`google-auth-oauthlib`](https://github.com/googleapis/google-auth-library-python-oauthlib)** | `>=1.1.0` | `Apache-2.0` | Copyright © Google LLC | [`fleet/integrations/gmail_client.py`](fleet/integrations/gmail_client.py) & [`fleet/api/health_api.py`](fleet/api/health_api.py) (OAuth 2.0 installed-app flow) |
| **[`pypdf`](https://github.com/py-pdf/pypdf)** | Optional | `BSD-3-Clause` | Copyright © 2006–2008 Mathieu Fenniak; Copyright © 2022–2026 Martin Thoma & contributors | [`fleet/core/document_extractor.py`](fleet/core/document_extractor.py) (optional PDF text extraction fallback) |
| **[`mcp`](https://github.com/modelcontextprotocol/python-sdk)** | Optional | `MIT` | Copyright © Anthropic, PBC | [`fleet/mcp_server.py`](fleet/mcp_server.py) (optional FastMCP SDK transport alongside built-in stdlib JSON-RPC 2.0 server) |

---

## 🧪 3. Development, Testing, Static Analysis & Standalone Demo Libraries

Installed via `pip install -e ".[dev]"` or invoked by local/CI quality gates:

| Package | Version Constraint | SPDX License | Copyright / Author | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **[`pytest`](https://github.com/pytest-dev/pytest)** | `>=9.0.3` | `MIT` | Copyright © 2004–2026 Holger Krekel and pytest-dev team | Unit & integration test runner (`tests/`, [`fleet/tools/test_runner.py`](fleet/tools/test_runner.py)) |
| **[`coverage`](https://github.com/nedbat/coveragepy)** | `>=7.3.0` | `Apache-2.0` | Copyright © 2004–2026 Ned Batchelder | Code coverage measurement ([`fleet/tools/test_runner.py`](fleet/tools/test_runner.py)) |
| **[`pyright`](https://github.com/microsoft/pyright)** | Latest | `MIT` | Copyright © Microsoft Corporation | Static type checking gate ([`fleet/tools/vscode_check.py`](fleet/tools/vscode_check.py)) |
| **[`ruff`](https://github.com/astral-sh/ruff)** | Latest | `MIT` | Copyright © 2022–2026 Charles Marsh / Astral Software Inc. | Fast Python linter & formatter in GitHub Actions CI |
| **[`setuptools`](https://github.com/pypa/setuptools)** | `>=61.0` | `MIT` | Copyright © Python Packaging Authority (PyPA) | PEP 517 build backend in [`pyproject.toml`](pyproject.toml) |
| **[`pygame-ce`](https://github.com/pygame-community/pygame-ce)** | `>=2.5.0` | `LGPL-2.1-or-later` | Copyright © Pygame Community Edition Developers | Optional dynamic import used solely in standalone [`pong.py`](pong.py) demo (never imported by `fleet/`) |

---

## 🎨 4. Typography & Visual Assets

| Asset | License | Author | Usage |
| :--- | :--- | :--- | :--- |
| **[Inter Typeface](https://rsms.me/inter/)** | **SIL Open Font License 1.1 (OFL-1.1)** | Copyright © 2016–2026 The Inter Project Authors (Rasmus Andersson) | UI typography stylesheet referenced in [`fleet/web/templates/dashboard.html`](fleet/web/templates/dashboard.html) with system-ui fallback |

---

## 🧬 5. Published Open Scientific & Acoustic DSP Algorithms (First-Party Implementations)

The 12-Dimensional Speaker Biometric Engine, Child/Impostor Rejection Guard, and Real-Time Voice Activity Detector in [`fleet/web/static/js/antigravity.js`](fleet/web/static/js/antigravity.js) and [`fleet/api/settings_api.py`](fleet/api/settings_api.py) are written from scratch in first-party JavaScript and Python, drawing upon the following peer-reviewed acoustic literature:

1. **Normalized Square Difference Function (NSDF) / McLeod Pitch Method (MPM)**:
   - *Citation*: Phillip McLeod and Geoff Wyvill (2005), *"A Smarter Way to Find Pitch"*, Proceedings of the International Computer Music Conference (ICMC 2005), pp. 138–141.
   - *Application*: First-peak clarity threshold (`>= 0.82` of global maximum) in `computeAutocorrelationPitchHz()` to prevent sub-harmonic octave-halving where a child's `260 Hz` voice could otherwise alias to `130 Hz`.
2. **YIN Fundamental Frequency ($F_0$) Estimator**:
   - *Citation*: Alain de Cheveigné and Hideki Kawahara (2002), *"YIN, a fundamental frequency estimator for speech and music"*, Journal of the Acoustical Society of America (JASA), 111(4), pp. 1917–1930.
   - *Application*: Parabolic lag interpolation and cumulative difference thresholding for frame-level $F_0$ tracking over `65 Hz – 450 Hz`.
3. **Quarter-Wave Vocal Tract Resonance ($F_1, F_2, F_3$) & Vocal Tract Length ($VTL$) Model**:
   - *Citation*: Gunnar Fant (1960), *Acoustic Theory of Speech Production*, Mouton & Co., The Hague.
   - *Application*: Estimation of physical Vocal Tract Length ($VTL \approx \frac{(2k - 1) \cdot c}{4 \cdot F_k}$ for $k \in \{1, 2, 3\}$, $c = 35,000\text{ cm/s}$) to separate adult vocal tracts (`~15.5–19.5 cm`) from child vocal tracts (`~10.5–13.5 cm`).
4. **Bark Critical-Band Psychoacoustic Scale**:
   - *Citation*: Eberhard Zwicker (1961), *"Subdivision of the Audible Frequency Range into Critical Bands (Frequenzgruppen)"*, Journal of the Acoustical Society of America (JASA), 33(2), p. 248.
   - *Application*: 8-band L2-normalized Bark sub-band energy vector (`80–200 Hz`, `200–350 Hz`, `350–570 Hz`, `570–840 Hz`, `840–1370 Hz`, `1370–2150 Hz`, `2150–3400 Hz`, `3400–6400 Hz`) for cosine-similarity speaker timbre matching.

---

## 📄 6. Full License Texts of Third-Party Licenses

### 6.1 Apache License, Version 2.0 (`cryptography`, `google-api-python-client`, `google-auth-*`, `coverage`)

Licensed under the Apache License, Version 2.0 (the "License"); you may not use these components except in compliance with the License. A full copy of the Apache License 2.0 is included in the repository root [`LICENSE`](LICENSE) file and at `http://www.apache.org/licenses/LICENSE-2.0`.

---

### 6.2 MIT License (`keyring`, `PyYAML`, `mcp`, `pytest`, `pyright`, `ruff`, `setuptools`)

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### 6.3 3-Clause BSD License (`cryptography`, `pypdf`)

```text
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

### 6.4 SIL Open Font License 1.1 (`Inter` Typeface)

```text
Copyright (c) 2016-2026 The Inter Project Authors (https://github.com/rsms/inter)
This Font Software is licensed under the SIL Open Font License, Version 1.1.
Full license text: https://scripts.sil.org/OFL
```
