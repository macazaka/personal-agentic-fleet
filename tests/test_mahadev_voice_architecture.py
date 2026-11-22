"""Comprehensive tests for Mahadev Voice & Biometric Cockpit architecture, docs, backlog, and MV-01..MV-10."""

from __future__ import annotations

import base64
from pathlib import Path
import re
import threading
import urllib.parse

import pytest

from fleet.core.database import FleetDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent


class _DummyHandler:
    def __init__(self):
        self.last_json: dict = {}
        self.last_status: int = 200
        self.headers_sent: dict[str, str] = {}
        self.status_code: int = 200
        self.body_bytes: bytes = b""
        self.wfile = self

    def _send_json(self, data: dict, status: int = 200):
        self.last_json = data
        self.last_status = status

    def send_response(self, status: int):
        self.status_code = status

    def send_header(self, key: str, value: str):
        self.headers_sent[key] = value

    def end_headers(self):
        return None

    def write(self, data: bytes):
        self.body_bytes = data


@pytest.fixture
def isolated_db(tmp_path):
    return FleetDatabase(db_path=tmp_path / "isolated_mv.db")


def test_mahadev_architecture_docs_diagrams_and_backlog_registration(isolated_db):
    doc_path = REPO_ROOT / "docs" / "MAHADEV_VOICE_BIOMETRIC_ARCHITECTURE.md"
    wiki_path = REPO_ROOT / "wiki" / "Mahadev-Voice-and-Biometric-Cockpit-Architecture.md"
    arch_doc = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    sidebar_md = REPO_ROOT / "wiki" / "_Sidebar.md"
    enhancer_py = REPO_ROOT / "fleet" / "tools" / "doc_wiki_enhancer.py"

    assert doc_path.is_file()
    assert wiki_path.is_file()
    doc_txt = doc_path.read_text(encoding="utf-8")

    # Verify at least 6 supported Mermaid diagrams and zero legacy J.A.R.V.I.S. branding
    mermaid_blocks = re.findall(r"```mermaid\s+([A-Za-z0-9_-]+)", doc_txt)
    assert len(mermaid_blocks) >= 6
    supported = {"flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram", "classDiagram", "erDiagram"}
    assert all(b in supported for b in mermaid_blocks)
    assert "J.A.R.V.I.S." not in doc_txt
    assert "MV-01" in doc_txt and "MV-10" in doc_txt

    assert "MAHADEV_VOICE_BIOMETRIC_ARCHITECTURE.md" in arch_doc.read_text(encoding="utf-8")
    assert "Mahadev-Voice-and-Biometric-Cockpit-Architecture" in sidebar_md.read_text(encoding="utf-8")
    assert "Mahadev-Voice-and-Biometric-Cockpit-Architecture" in enhancer_py.read_text(encoding="utf-8")

    isolated_db.sync_ux_roadmap_backlog()
    items = isolated_db.list_feature_backlog_items()
    for idx in range(1, 11):
        tag = f"[MV-{idx:02d}]"
        matched = [it for it in items if tag in it["title"]]
        assert len(matched) == 1, f"Expected single backlog entry for {tag}"
        assert matched[0]["status"] == "Completed"


def test_mv01_atomic_encrypted_audio_validation_nosniff_and_lightweight_get(isolated_db, monkeypatch, tmp_path):
    import fleet.api.settings_api as settings_api
    import fleet.server as srv

    monkeypatch.setattr(srv, "db", isolated_db)
    monkeypatch.setattr(settings_api, "DATA_DIR", tmp_path)
    settings_api._invalidate_voiceprint_mem_cache()

    h = _DummyHandler()

    # 1. Invalid MIME / non-audio data URL rejected with 400
    settings_api.save_voiceprint_profile_endpoint(
        h,
        {"profile": {"pitchMeanHz": 115}, "audio_data_url": "data:text/html;base64,PHNjcmlwdD4=", "confirmed": True},
    )
    assert h.last_status == 400
    assert h.last_json["audio_saved"] is False

    # 2. Oversized payload (> 12 MB) rejected cleanly with 413
    oversized_b64 = base64.b64encode(b"\x01" * (settings_api.MAX_VOICEPRINT_AUDIO_BYTES + 128)).decode("ascii")
    settings_api.save_voiceprint_profile_endpoint(
        h,
        {"profile": {"pitchMeanHz": 115}, "audio_data_url": f"data:audio/wav;base64,{oversized_b64}", "confirmed": True},
    )
    assert h.last_status == 413
    assert h.last_json["audio_saved"] is False

    # 3. Valid WAV writes encrypted-only audio (never plaintext RIFF header on disk) and no plaintext JSON vault
    wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 32
    wav_url = "data:audio/wav;base64," + base64.b64encode(wav_bytes).decode("ascii")
    settings_api.save_voiceprint_profile_endpoint(
        h,
        {"profile": {"pitchMeanHz": 110, "vtlCm": 17.5}, "audio_data_url": wav_url, "confirmed": True},
    )
    assert h.last_status == 200
    assert h.last_json["audio_saved"] is True

    wav_disk = tmp_path / "user" / "voiceprint_sample.wav"
    assert wav_disk.is_file()
    disk_bytes = wav_disk.read_bytes()
    assert not disk_bytes.startswith(b"RIFF"), "Audio file on disk must be encrypted at rest, never plaintext RIFF"

    # 4. Lightweight GET /api/voice/voiceprint?include_audio=0 omits audio_data_url; default includes it
    settings_api.get_voiceprint_profile_endpoint(h, urllib.parse.urlparse("/api/voice/voiceprint?include_audio=0"))
    assert h.last_json["audio_saved"] is True
    assert h.last_json["audio_url"] == "/api/voice/voiceprint/audio"
    assert h.last_json["audio_data_url"] == ""

    settings_api.get_voiceprint_profile_endpoint(h, urllib.parse.urlparse("/api/voice/voiceprint"))
    assert h.last_json["audio_data_url"] == wav_url

    # 5. Binary replay sets X-Content-Type-Options: nosniff + Cache-Control: no-store
    h_bin = _DummyHandler()
    settings_api.get_voiceprint_audio_replay_endpoint(h_bin, urllib.parse.urlparse("/api/voice/voiceprint/audio"))
    assert h_bin.status_code == 200
    assert h_bin.headers_sent.get("X-Content-Type-Options") == "nosniff"
    assert h_bin.headers_sent.get("Cache-Control") == "no-store"
    assert h_bin.body_bytes == wav_bytes
    settings_api._invalidate_voiceprint_mem_cache()


def test_mv02_mv03_mv04_js_contracts_and_server_biometric_enforcement(isolated_db, monkeypatch):
    import fleet.api.settings_api as settings_api
    import fleet.server as srv

    ag_js = (REPO_ROOT / "fleet" / "web" / "static" / "js" / "antigravity.js").read_text(encoding="utf-8")

    # MV-02: harmonized 34300 VTL constant, min calibration frame gate, fail-closed speaker lock
    assert "34300" in ag_js and "35000" not in ag_js
    assert "MIN_CALIBRATION_VOICED_FRAMES = 8" in ag_js
    assert "Speaker Lock requires voiced acoustic frames" in ag_js

    # MV-03 & MV-04: idle mic auto-release, visibility/pagehide guards, _speechEpoch, keepalive & ASR backoff
    assert "MIC_IDLE_RELEASE_MS = 15000" in ag_js
    assert "pagehide" in ag_js and "visibilitychange" in ag_js
    assert "_speechEpoch" in ag_js
    assert "_ttsKeepaliveTimer" in ag_js
    assert "_recConsecutiveErrors" in ag_js
    assert "ambientNoiseRms" in ag_js

    # MV-02 Server-side enforce_biometric HTTP 403 rejection vs owner 200 acceptance
    monkeypatch.setattr(srv, "db", isolated_db)
    settings_api._invalidate_voiceprint_mem_cache()
    h = _DummyHandler()
    owner_profile = {
        "pitchMeanHz": 110,
        "pitchStdHz": 14,
        "pitchMinHz": 90,
        "pitchMaxHz": 135,
        "centroidMeanHz": 1200,
        "f1MeanHz": 470,
        "f2MeanHz": 1450,
        "f3MeanHz": 2520,
        "vtlCm": 17.4,
        "chestResonanceRatio": 1.45,
        "rolloffMeanHz": 2250,
        "subBandVector": [0.46, 0.44, 0.38, 0.34, 0.29, 0.25, 0.20, 0.14],
        "strictnessThreshold": 78,
    }
    settings_api.save_voiceprint_profile_endpoint(h, {"profile": owner_profile, "confirmed": True})

    child_sample = {
        "pitchMeanHz": 270,
        "centroidMeanHz": 1950,
        "f1MeanHz": 720,
        "f2MeanHz": 2150,
        "f3MeanHz": 3350,
        "vtlCm": 12.0,
        "chestResonanceRatio": 0.40,
        "rolloffMeanHz": 3200,
        "subBandVector": [0.14, 0.21, 0.34, 0.46, 0.49, 0.42, 0.33, 0.28],
    }
    settings_api.post_voice_stream_endpoint(
        h,
        {
            "transcript": "Mahadev, give me my daily briefing",
            "biometric_sample": child_sample,
            "enforce_biometric": True,
        },
    )
    assert h.last_status == 403
    assert h.last_json["biometric_rejected"] is True

    owner_sample = dict(owner_profile)
    owner_sample["pitchMeanHz"] = 112
    h_ok = _DummyHandler()
    settings_api.post_voice_stream_endpoint(
        h_ok,
        {
            "transcript": "Mahadev, what time is it?",
            "biometric_sample": owner_sample,
            "enforce_biometric": True,
        },
    )
    assert h_ok.last_status == 200
    assert h_ok.last_json["biometric_audit"]["allowed"] is True
    settings_api._invalidate_voiceprint_mem_cache()


def test_mv05_thread_safety_and_cache_coherency(isolated_db, monkeypatch):
    import fleet.api.settings_api as settings_api
    import fleet.core.omnibar_dispatcher as omni
    import fleet.server as srv

    monkeypatch.setattr(srv, "db", isolated_db)
    settings_api._invalidate_voiceprint_mem_cache()

    h = _DummyHandler()
    settings_api.save_voiceprint_profile_endpoint(
        h,
        {
            "profile": {
                "pitchMeanHz": 128,
                "pitchStdHz": 15,
                "vtlCm": 17.1,
                "chestResonanceRatio": 1.38,
                "strictnessThreshold": 78,
                "autoRefineEnabled": True,
            },
            "confirmed": True,
        },
    )

    # Updating threshold via update_settings_only must update _VOICEPRINT_MEM_CACHE cleanly (no stale reads)
    settings_api.post_verify_voiceprint_sandbox_endpoint(
        h,
        {"update_settings_only": True, "strictness_threshold": 85},
    )
    cached = settings_api._get_cached_decrypted_voiceprint(isolated_db, "jarvis_voiceprint_profile")
    assert cached is not None
    assert cached["strictnessThreshold"] == 85

    # Concurrent dispatcher calls under _VOICE_STATE_LOCK complete with zero exceptions
    errors: list[Exception] = []

    def _worker(i: int):
        try:
            omni.transcribe_and_dispatch_voice_command(
                f"What time is it {i}?",
                db=isolated_db,
                channel="stream",
            )
            omni.get_jarvis_voice_diagnostics()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    settings_api._invalidate_voiceprint_mem_cache()


def test_mv06_mv07_mv08_latency_channels_whisper_and_mobile_relay(isolated_db, monkeypatch):
    import fleet.api.mobile_tri_device_api as mobile_api
    import fleet.api.settings_api as settings_api
    import fleet.core.omnibar_dispatcher as omni
    import fleet.server as srv

    monkeypatch.setattr(srv, "db", isolated_db)

    before_diag = omni.get_jarvis_voice_diagnostics()
    before_total = before_diag["telemetry"]["total_voice_turns"]
    before_stream = before_diag["channels"]["stream"]
    before_mob = before_diag["channels"]["mobile_relay"]

    # 1. Stream call with whisper_mode=True clamps to single clause and logs activity
    h_stream = _DummyHandler()
    settings_api.post_voice_stream_endpoint(
        h_stream,
        {
            "transcript": "Mahadev, give me my daily briefing",
            "whisper_mode": True,
            "concise_mode": True,
        },
    )
    assert h_stream.last_status == 200
    assert h_stream.last_json["whisper_mode"] is True
    assert len(h_stream.last_json["spoken_stream_clauses"]) == 1
    assert h_stream.last_json["dispatch_latency_ms"] >= 0.0

    # 2. Mobile relay reuses shared wake-word stripping and increments mobile_relay counter
    isolated_db.set_setting("voice_wake_word", "Mahadev")
    h_mob = _DummyHandler()
    mobile_api.post_mobile_voice_relay_endpoint(
        h_mob,
        {"transcript": "Namaste Mahadev, what time is it?", "device": "Apple Watch Ultra"},
    )
    assert h_mob.last_json["status"] == "ok"
    assert h_mob.last_json["command_routed"] == "what time is it?"

    after_diag = omni.get_jarvis_voice_diagnostics()
    assert after_diag["telemetry"]["total_voice_turns"] >= before_total + 2
    assert after_diag["channels"]["stream"] >= before_stream + 1
    assert after_diag["channels"]["mobile_relay"] >= before_mob + 1
    assert after_diag["latency"]["samples"] >= 1
    assert after_diag["latency"]["p95_dispatch_ms"] >= 0.0

    logs = isolated_db.get_recent_activities(limit=10)
    actions = [str(x.get("action") or "") for x in logs]
    assert "voice_stream_turn" in actions
    assert "mobile_voice_relay" in actions


def test_mv09_mv10_enrolled_anchor_anti_drift_reset_and_enriched_diagnostics(isolated_db, monkeypatch):
    import fleet.api.settings_api as settings_api
    import fleet.server as srv

    monkeypatch.setattr(srv, "db", isolated_db)
    settings_api._invalidate_voiceprint_mem_cache()

    h = _DummyHandler()
    baseline = {
        "pitchMeanHz": 106,
        "pitchStdHz": 14,
        "pitchMinHz": 88,
        "pitchMaxHz": 128,
        "centroidMeanHz": 1220,
        "f1MeanHz": 475,
        "f2MeanHz": 1460,
        "f3MeanHz": 2540,
        "vtlCm": 17.3,
        "chestResonanceRatio": 1.44,
        "rolloffMeanHz": 2290,
        "subBandVector": [0.45, 0.44, 0.39, 0.35, 0.30, 0.25, 0.20, 0.14],
        "strictnessThreshold": 78,
        "autoRefineEnabled": True,
    }
    settings_api.save_voiceprint_profile_endpoint(h, {"profile": baseline, "confirmed": True})
    enrolled = h.last_json["profile"]
    assert enrolled["enrolledAnchor"]["pitchMeanHz"] == 106
    assert enrolled["enrolledAnchor"]["vtlCm"] == 17.3

    # Push 45 shifted owner observations (F0 +24 Hz within 28Hz obs gate, VTL -1.8 cm, Chest -0.40) -> anchor clamp holds!
    cur = dict(enrolled)
    for _ in range(45):
        cur = settings_api.auto_refine_voiceprint_profile(
            cur,
            {"pitchMeanHz": cur["pitchMeanHz"] + 22, "vtlCm": 15.0, "chestResonanceRatio": 0.95},
            learning_rate=0.20,
        )
    assert cur["pitchMeanHz"] <= 106 + 14
    assert cur["vtlCm"] >= round(17.3 - 0.9, 2)
    assert cur["chestResonanceRatio"] >= round(1.44 - 0.25, 2)

    # Simulate persisted drift via auto_refine endpoint, inspect diagnostics, then reset_to_anchor
    for _ in range(5):
        settings_api.save_voiceprint_profile_endpoint(
            h,
            {"auto_refine": True, "learning_rate": 0.20, "observation": {"pitchMeanHz": 120, "vtlCm": 16.8}},
        )

    h_diag = _DummyHandler()
    settings_api.get_voice_diagnostics_endpoint(h_diag, urllib.parse.urlparse("/api/voice/diagnostics"))
    diag = h_diag.last_json
    assert "latency" in diag and "channels" in diag and "biometric_security" in diag
    assert diag["biometric_security"]["enrolled"] is True
    assert diag["biometric_security"]["has_anchor"] is True
    assert diag["biometric_security"]["drift_from_anchor_hz"] > 0

    h_reset = _DummyHandler()
    settings_api.save_voiceprint_profile_endpoint(h_reset, {"reset_to_anchor": True})
    assert h_reset.last_status == 200
    assert h_reset.last_json["status"] == "reset_to_anchor"
    assert h_reset.last_json["profile"]["pitchMeanHz"] == 106
    assert h_reset.last_json["profile"]["autoRefinementCount"] == 0

    dash_html = (REPO_ROOT / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "voiceEngineDiagnosticsBox" in dash_html
    assert "resetVoiceprintToAnchor()" in dash_html
    settings_api._invalidate_voiceprint_mem_cache()
