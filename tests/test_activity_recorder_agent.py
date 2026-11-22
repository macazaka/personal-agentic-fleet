"""
Comprehensive unit & integration tests for:
- Multimodal Activity (Browser & Desktop) + Synchronized Voice Narration Recorder
- Formal Requirements Document + Mermaid Process Flow & Isolated Pytest Generation
- Visible Sandbox Dry-Run, Autonomous Self-Healing & Spoken Audio Rectification
- Explicit Publish Approval Gate, Studio UI & Live Headless Ask-for-Inputs Resume
- HLD/LLD/Wiki Architecture Docs, Mermaid Validity & [REC-01]..[REC-12] Backlog
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
import urllib.parse

import pytest

from fleet.api.router import router
from fleet.core.activity_recorder import (
    RecordingSessionManager,
    coalesce_raw_events,
    compute_ws_accept_key,
    decode_ws_frame_from_bytes,
    encode_ws_frame,
    execute_recorded_workflow,
    fuse_audio_and_screen_events,
    generate_bookmarklet_snippet,
    heal_and_iterate_workflow,
    publish_recorded_agent,
    redact_sensitive_value,
    resume_workflow_run,
    run_generated_agent_unit_tests,
    run_visible_sandbox_dry_run,
    sanitize_audio_transcript,
    sanitize_recorded_event,
    synthesize_agent_from_recording,
)
from fleet.core.agent_studio import SUPPORTED_UI_BLOCKS, dry_run_agent_spec, render_declarative_ui_blocks
from fleet.core.database import FleetDatabase
from fleet.core.plugin_sandbox import ALLOWED_AGENT_PERMISSIONS
from fleet.core.registry import AgentRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent


class _DummyHandler:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {"Host": "127.0.0.1:7890"}
        self.last_json: dict = {}
        self.last_status: int = 200
        self.status_code: int = 200
        self.response_headers: dict[str, str] = {}

    def _send_json(self, data: dict, status: int = 200):
        self.last_json = data
        self.last_status = status
        self.status_code = status

    def send_error(self, code: int, message: str = ""):
        self.status_code = code
        self.last_status = code
        self.last_json = {"status": "error", "code": code, "message": message}

    def send_response(self, code: int):
        self.status_code = code

    def send_header(self, key: str, val: str):
        self.response_headers[key] = val

    def end_headers(self):
        return None


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    import fleet.api.recorder_api as rec_api
    import fleet.server as srv

    db = FleetDatabase(db_path=tmp_path / "recorder_test.db")
    mgr = RecordingSessionManager(storage_dir=tmp_path / "recordings")
    reg = AgentRegistry(
        agents_dir=REPO_ROOT / "fleet" / "agents",
        custom_agents_dir=tmp_path / "custom_agents",
        db=db,
    )
    reg.agents_dir.mkdir(parents=True, exist_ok=True)
    reg.custom_agents_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(rec_api, "get_recorder_manager", lambda: mgr)
    monkeypatch.setattr(srv, "db", db)
    monkeypatch.setattr(srv, "agent_registry", reg)
    return {"db": db, "mgr": mgr, "registry": reg, "tmp_path": tmp_path}


def _validate_mermaid_blocks(markdown_text: str, min_count: int) -> None:
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", markdown_text, flags=re.S)
    assert len(blocks) >= min_count
    supported = {"flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram", "classDiagram", "erDiagram"}
    for blk in blocks:
        first_word = blk.strip().split()[0]
        assert first_word in supported, f"Unsupported Mermaid type: {first_word}"
        # Zero raw HTML tags in Mermaid diagrams
        assert not re.search(r"<(?:br|b|i|div|span|p)\b", blk, re.I), f"HTML tag inside Mermaid block: {blk[:120]}"


def test_hld_lld_wiki_architecture_diagrams_and_rec_backlog(isolated_env):
    hld_path = REPO_ROOT / "docs" / "ACTIVITY_RECORDER_AGENT_HLD.md"
    lld_path = REPO_ROOT / "docs" / "ACTIVITY_RECORDER_AGENT_LLD.md"
    wiki_path = REPO_ROOT / "wiki" / "Activity-Recorder-to-Headless-Agent-Architecture.md"
    arch_path = REPO_ROOT / "docs" / "ARCHITECTURE.md"
    sidebar_path = REPO_ROOT / "wiki" / "_Sidebar.md"
    enhancer_path = REPO_ROOT / "fleet" / "tools" / "doc_wiki_enhancer.py"

    assert hld_path.is_file()
    assert lld_path.is_file()
    assert wiki_path.is_file()

    hld_txt = hld_path.read_text(encoding="utf-8")
    lld_txt = lld_path.read_text(encoding="utf-8")
    wiki_txt = wiki_path.read_text(encoding="utf-8")

    _validate_mermaid_blocks(hld_txt, min_count=6)
    _validate_mermaid_blocks(lld_txt, min_count=6)
    _validate_mermaid_blocks(wiki_txt, min_count=2)

    for idx in range(1, 13):
        tag = f"[REC-{idx:02d}]"
        assert tag in hld_txt, f"Missing {tag} in HLD critique"
        assert tag in wiki_txt, f"Missing {tag} in Wiki page"

    arch_txt = arch_path.read_text(encoding="utf-8")
    assert "ACTIVITY_RECORDER_AGENT_HLD.md" in arch_txt
    assert "ACTIVITY_RECORDER_AGENT_LLD.md" in arch_txt
    assert "Activity-Recorder-to-Headless-Agent-Architecture" in sidebar_path.read_text(encoding="utf-8")
    assert "Activity-Recorder-to-Headless-Agent-Architecture" in enhancer_path.read_text(encoding="utf-8")

    db: FleetDatabase = isolated_env["db"]
    db.sync_ux_roadmap_backlog()
    items = db.list_feature_backlog_items()
    for idx in range(1, 13):
        tag = f"[REC-{idx:02d}]"
        matches = [it for it in items if tag in it["title"]]
        assert len(matches) == 1, f"Expected single canonical backlog item for {tag}"
        assert matches[0]["status"] == "Completed"


def test_rfc6455_websocket_handshake_and_frame_roundtrip():
    # Official RFC 6455 Section 1.3 test vector
    assert compute_ws_accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

    for sample in (b"hello", b"x" * 300, '{"id":1,"method":"Page.enable"}'.encode("utf-8")):
        masked_frame = encode_ws_frame(sample, opcode=0x1, masked=True)
        opcode, decoded, consumed = decode_ws_frame_from_bytes(masked_frame)
        assert opcode == 0x1
        assert decoded == sample
        assert consumed == len(masked_frame)

        unmasked_frame = encode_ws_frame(sample, opcode=0x1, masked=False)
        op2, dec2, cons2 = decode_ws_frame_from_bytes(unmasked_frame)
        assert op2 == 0x1
        assert dec2 == sample
        assert cons2 == len(unmasked_frame)


def test_capture_edge_secret_redaction_screen_and_spoken_audio():
    # Password input redaction
    val_pwd, is_sec, hint = redact_sensitive_value("SuperSecret!99", field_hint="portal_password", input_type="password")
    assert is_sec is True
    assert "SuperSecret" not in val_pwd
    assert val_pwd.startswith("{{secret:")
    assert "password" in hint

    # OTP & Aadhaar/Card pattern redaction
    val_card, sec_card, _ = redact_sensitive_value("4111 2222 3333 4444", field_hint="payment_card")
    assert sec_card is True
    assert "4111" not in val_card

    # Window title & DOM payload redaction
    evt = sanitize_recorded_event({
        "channel": "desktop",
        "action": "app_switch",
        "title": "KeePassXC - Master Password",
        "locators": {"process": "keepassxc.exe", "window_title": "KeePassXC - Master Password"},
        "value": "my-vault-pass",
    })
    assert evt["sensitive"] is True
    assert "KeePassXC" not in evt["title"]
    assert "my-vault-pass" not in evt["value"]

    # Spoken transcript scrubbing
    spoken = "Type my password is Hunter2! and OTP 884210 plus PAN ABCDE1234F into the form."
    scrubbed = sanitize_audio_transcript(spoken)
    assert "Hunter2" not in scrubbed
    assert "884210" not in scrubbed
    assert "ABCDE1234F" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_multimodal_recording_encryption_coalescing_and_temporal_fusion(isolated_env):
    mgr: RecordingSessionManager = isolated_env["mgr"]
    started = mgr.start_recording(
        mode="hybrid",
        start_url="https://portal.example.com/renewals",
        launch_browser=False,
        record_audio=True,
        label="Insurance Portal Updater",
    )
    sid = started["session_id"]
    token = started["capture_token"]
    assert started["status"] == "recording"
    assert "capture_token" in started and len(token) >= 20
    bkmk = generate_bookmarklet_snippet(sid, token)
    assert bkmk.startswith("javascript:")

    # Self-click on AFCC must be filtered automatically
    self_res = mgr.ingest_event(
        {"channel": "desktop", "action": "desktop_click", "title": "Agentic Fleet Control Center - Stop"},
        session_id=sid,
        capture_token=token,
        trusted_internal=False,
    )
    assert self_res["status"] == "ignored_self_event"

    # Simulate realistic noise: multiple keystrokes + duplicate rapid click + password + desktop export
    raw_sequence = [
        {"offset_sec": 1.0, "channel": "browser", "action": "change", "url": "https://portal.example.com/renewals", "locators": {"id": "policyNo", "name": "policy_number", "label_text": "Policy Number"}, "value": "POL-1"},
        {"offset_sec": 1.4, "channel": "browser", "action": "change", "url": "https://portal.example.com/renewals", "locators": {"id": "policyNo", "name": "policy_number", "label_text": "Policy Number"}, "value": "POL-12345"},
        {"offset_sec": 2.0, "channel": "browser", "action": "change", "input_type": "password", "locators": {"id": "pinBox", "name": "portal_pin"}, "value": "9988"},
        {"offset_sec": 3.0, "channel": "browser", "action": "click", "locators": {"data_testid": "submit-btn", "text": "Check Status"}, "value": "Check Status"},
        {"offset_sec": 3.1, "channel": "browser", "action": "click", "locators": {"data_testid": "submit-btn", "text": "Check Status"}, "value": "Check Status"},
        {"offset_sec": 5.5, "channel": "desktop", "action": "app_switch", "title": "Excel Export Ledger", "locators": {"process": "excel.exe", "uia_automation_id": "GridCellA1"}},
    ]
    for ev in raw_sequence:
        res = mgr.ingest_event(ev, session_id=sid, capture_token=token, trusted_internal=False)
        assert res["status"] == "ok"

    # Synchronized spoken narration segments
    mgr.ingest_audio_segment(
        transcript="Ask me for the policy number every time and wait 2 seconds before clicking Check Status.",
        offset_sec=2.6,
        session_id=sid,
        capture_token=token,
        trusted_internal=False,
    )
    mgr.ingest_audio_segment(
        transcript="Extract the renewal status summary into Excel every hour.",
        offset_sec=5.8,
        session_id=sid,
        capture_token=token,
        trusted_internal=False,
    )

    dummy_audio = base64.b64encode(b"RIFF\x00\x00\x00\x00WAVEfmt-sample-narration").decode("ascii")
    stopped = mgr.stop_recording(session_id=sid, audio_base64=dummy_audio, audio_mime="audio/wav")
    assert stopped["status"] == "stopped"
    assert stopped["audio_saved"] is True

    # Raw encrypted files on disk MUST NOT contain plaintext secret '9988'
    enc_file = mgr._session_path(sid)
    assert enc_file.is_file()
    raw_cipher = enc_file.read_text(encoding="utf-8")
    assert raw_cipher.startswith("ENC:aes256gcm:")
    assert "9988" not in raw_cipher

    decrypted_audio = mgr.load_session_audio_bytes(sid)
    assert decrypted_audio == b"RIFF\x00\x00\x00\x00WAVEfmt-sample-narration"

    coalesced = coalesce_raw_events(mgr.load_session(sid)["events"])
    fill_events = [e for e in coalesced if e["action"] == "change" and e["locators"].get("id") == "policyNo"]
    assert len(fill_events) == 1 and fill_events[0]["value"] == "POL-12345"
    submit_clicks = [e for e in coalesced if e["action"] == "click"]
    assert len(submit_clicks) == 1


def test_11_step_closed_loop_requirements_tests_sandbox_heal_publish_and_hitl_resume(isolated_env):
    mgr: RecordingSessionManager = isolated_env["mgr"]
    reg: AgentRegistry = isolated_env["registry"]
    db: FleetDatabase = isolated_env["db"]

    # Steps 1-4: Record browser workflow + voice narration
    st = mgr.start_recording(mode="browser", start_url="https://example.org/bills", launch_browser=False, record_audio=True, label="Electricity Bill Agent")
    sid = st["session_id"]
    tok = st["capture_token"]
    mgr.ingest_event({"offset_sec": 1.0, "channel": "browser", "action": "change", "locators": {"id": "consumerNo", "name": "consumer_number", "label_text": "Consumer Number"}, "value": "CONS-771"}, sid, tok)
    mgr.ingest_event({"offset_sec": 2.0, "channel": "browser", "action": "change", "input_type": "password", "locators": {"id": "otpBox", "name": "otp_code"}, "value": "654321"}, sid, tok)
    mgr.ingest_event({"offset_sec": 3.0, "channel": "browser", "action": "click", "locators": {"data_testid": "fetch-bill", "text": "Fetch Bill"}}, sid, tok)
    mgr.ingest_audio_segment(
        transcript="Ask me for the consumer number every time and wait 2 seconds after submitting to fetch the bill.",
        offset_sec=1.5,
        session_id=sid,
        capture_token=tok,
    )
    mgr.stop_recording(session_id=sid)

    # Steps 5-7: Convert -> Requirements Doc + Mermaid Flowchart + Workflow IR + Isolated Pytest Execution
    synth = synthesize_agent_from_recording(session_id=sid, use_llm=False, auto_run_tests=True, manager=mgr)
    assert synth["status"] == "ok"
    req_doc = synth["requirements_doc"]
    assert "flowchart TD" in req_doc["mermaid_process_flow"]
    assert len(req_doc["functional_requirements"]) >= 3
    assert any(f["key"] == "consumer_number" and f["ask_on_each_run"] for f in synth["input_schema"])
    assert any(f["sensitive"] and f["default"] == "" for f in synth["input_schema"])
    assert synth["unit_test_report"]["status"] == "passed"
    assert synth["unit_test_report"]["passed"] >= 3

    # Step 8: Visible Sandbox Dry-Run (missing input prompt first, then failure injection)
    sbx_pause = run_visible_sandbox_dry_run(sid, user_inputs={}, simulate_only=True, manager=mgr)
    assert sbx_pause["status"] == "waiting_for_input"
    assert len(sbx_pause["pending_inputs"]) >= 2

    sbx_fail = run_visible_sandbox_dry_run(
        sid,
        user_inputs={"consumer_number": "CONS-888", "otp_code": "112233"},
        simulate_only=True,
        inject_failure_step=2,
        manager=mgr,
    )
    assert sbx_fail["status"] == "failed_needs_healing"
    assert sbx_fail["failed_count"] == 1

    # Steps 9-10: Self-Healing + Spoken Audio Rectification ("wait 3 seconds and ask me for billing month")
    healed = heal_and_iterate_workflow(
        session_id=sid,
        user_audio_feedback="Wait 3 seconds before clicking Fetch Bill and ask me for billing month.",
        rerun_tests=True,
        manager=mgr,
    )
    assert healed["status"] == "healed"
    assert healed["iteration_version"] == 2
    assert any("billing_month" == f["key"] for f in healed["workflow_ir"]["input_schema"])
    assert healed["unit_test_report"]["status"] == "passed"

    sbx_pass = run_visible_sandbox_dry_run(
        sid,
        user_inputs={"consumer_number": "CONS-888", "otp_code": "112233", "billing_month": "Nov-2026"},
        simulate_only=True,
        manager=mgr,
    )
    assert sbx_pass["status"] == "passed"
    assert sbx_pass["failed_count"] == 0

    # Step 11: Publish Approval Gate & Live Headless Agent Execution with HITL Ask-for-Inputs Pause/Resume
    with pytest.raises(ValueError):
        publish_recorded_agent(sid, agent_registry=reg, user_approved=False, db=db, manager=mgr)

    pub = publish_recorded_agent(sid, agent_registry=reg, user_approved=True, db=db, manager=mgr)
    assert pub["status"] == "published"
    aid = pub["agent_id"]
    assert Path(pub["requirements_path"]).is_file()
    assert Path(pub["tests_path"]).is_file()
    assert len(SUPPORTED_UI_BLOCKS) == 12  # Existing Phase 6 Studio invariant strictly preserved

    live_agent = reg.get_agent(aid)
    assert live_agent is not None
    assert "workflow_runner_card" in live_agent.get_ui_manifest()["html"]

    # Run live agent without inputs -> pauses at waiting_for_input (without persisting OTP secret)
    first_run = live_agent.execute_task("run_workflow", payload={"dry_run": True})
    assert first_run["status"] == "waiting_for_input"
    run_id = first_run["run_id"]
    ckpt_rows = db.list_custom_agent_records(aid, record_type="workflow_run", limit=5)
    assert ckpt_rows and ckpt_rows[0]["status"] == "waiting_for_input"

    # Resume with runtime inputs -> completes cleanly & clears pending state
    resumed = live_agent.execute_task(
        "run_workflow",
        payload={
            "resume_run_id": run_id,
            "inputs": {"consumer_number": "CONS-888", "otp_code": "990011", "billing_month": "Nov-2026"},
            "dry_run": True,
        },
    )
    assert resumed["status"] == "completed"
    # Secret OTP never written to checkpoint history
    ckpt_after = db.list_custom_agent_records(aid, record_type="workflow_run", limit=5)
    assert "990011" not in str(ckpt_after)


def test_recorder_and_workflow_rest_api_endpoints_and_token_auth(isolated_env):
    # 1. Start session via HTTP route
    h = _DummyHandler()
    assert router.dispatch_post(h, "/api/studio/recorder/start", {
        "mode": "browser",
        "start_url": "https://example.com/login",
        "launch_browser": False,
        "record_audio": True,
        "label": "API Workflow Test",
    })
    assert h.status_code == 200
    sid = h.last_json["session_id"]
    tok = h.last_json["capture_token"]

    # 2. Unauthorized capture_token MUST be rejected with 403
    h_bad = _DummyHandler()
    assert router.dispatch_post(h_bad, "/api/studio/recorder/event", {
        "session_id": sid,
        "capture_token": "forged-token",
        "action": "click",
        "locators": {"id": "btn1"},
    })
    assert h_bad.status_code == 403

    # 3. Valid event + mark_input + audio_segment + status
    assert router.dispatch_post(h, "/api/studio/recorder/event", {
        "session_id": sid,
        "capture_token": tok,
        "action": "change",
        "locators": {"id": "searchBox", "name": "search_query"},
        "value": "quarterly report",
    })
    assert h.last_json["status"] == "ok"

    assert router.dispatch_post(h, "/api/studio/recorder/mark_input", {
        "session_id": sid,
        "capture_token": tok,
        "label": "Report Year",
        "input_type": "number",
        "prompt_question": "Which year should I fetch?",
    })
    assert h.last_json["status"] == "ok"

    assert router.dispatch_post(h, "/api/studio/recorder/audio_segment", {
        "session_id": sid,
        "capture_token": tok,
        "offset_sec": 1.2,
        "transcript": "Search for quarterly report and ask me for report year.",
    })
    assert h.last_json["status"] == "ok"

    assert router.dispatch_get(h, "/api/studio/recorder/status", urllib.parse.urlparse("/api/studio/recorder/status?limit=10"))
    assert h.last_json["active"] is True
    assert h.last_json["events_count"] >= 2

    # 4. Stop -> List Sessions -> Convert -> Run Tests -> Sandbox Run -> Heal -> Publish
    assert router.dispatch_post(h, "/api/studio/recorder/stop", {"session_id": sid})
    assert h.last_json["status"] == "stopped"

    assert router.dispatch_get(h, "/api/studio/recorder/sessions", urllib.parse.urlparse("/api/studio/recorder/sessions"))
    assert any(s["session_id"] == sid for s in h.last_json["sessions"])

    assert router.dispatch_post(h, "/api/studio/recorder/convert", {"session_id": sid, "use_llm": False})
    assert h.last_json["status"] == "ok"
    assert "requirements_doc" in h.last_json

    assert router.dispatch_post(h, "/api/studio/recorder/run_tests", {"session_id": sid})
    assert h.last_json["status"] == "passed"

    assert router.dispatch_post(h, "/api/studio/recorder/sandbox_run", {"session_id": sid, "simulate_only": True, "inputs": {"report_year": "2026"}})
    assert h.last_json["status"] == "passed"

    assert router.dispatch_post(h, "/api/studio/recorder/heal", {"session_id": sid, "user_audio_feedback": "Wait 1 second before clicking search.", "rerun_tests": True})
    assert h.last_json["status"] == "healed"
    assert h.last_json["iteration_version"] == 2

    assert router.dispatch_post(h, "/api/studio/recorder/publish", {"session_id": sid, "user_approved": True})
    assert h.last_json["status"] == "published"
    aid = h.last_json["agent_id"]

    # 5. Live Headless Workflow Run & Resume API
    assert router.dispatch_post(h, "/api/studio/workflows/run", {"agent_id": aid, "dry_run": True, "inputs": {}})
    assert h.last_json["result"]["status"] == "waiting_for_input"
    run_id = h.last_json["result"]["run_id"]
    assert h.last_json["state"]["pending_workflow_runs"]

    assert router.dispatch_post(h, "/api/studio/workflows/resume", {
        "agent_id": aid,
        "run_id": run_id,
        "inputs": {"report_year": "2026"},
        "dry_run": True,
    })
    assert h.last_json["result"]["status"] == "completed"
    assert not h.last_json["state"]["pending_workflow_runs"]


def test_dashboard_recorder_ui_buttons_tooltips_and_js_exports():
    html = (REPO_ROOT / "fleet" / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    js = (REPO_ROOT / "fleet" / "web" / "static" / "js" / "create_agent.js").read_text(encoding="utf-8")

    assert 'id="studioActivityRecorderCard"' in html
    assert 'value="recorded_workflow"' in html
    assert 'id="btnStudioRecStart"' in html
    assert 'id="btnStudioRecPublish"' in html

    # Verify every button inside #studioActivityRecorderCard has a non-empty title attribute
    start_idx = html.index('id="studioActivityRecorderCard"')
    chunk = html[start_idx : start_idx + 12000]
    for btn_open in re.findall(r"<button\b[^>]*>", chunk, flags=re.I):
        assert 'title="' in btn_open and 'title=""' not in btn_open, f"Button missing title tooltip: {btn_open}"

    for symbol in ("StudioActivityRecorder", "runRecordedWorkflow", "resumeRecordedWorkflow", "renderWorkflowInputPrompt"):
        assert symbol in js

    dry = dry_run_agent_spec({
        "name": "Sample Recorded Flow",
        "agent_id": "sample_recorded_flow",
        "archetype": "recorded_workflow",
        "permissions": ["db:read", "db:write", "ui:render"],
        "workflow_ir": {
            "schema_version": "1.0",
            "steps": [{"step_id": "step_1", "channel": "browser", "action": "navigate", "url": "https://example.com"}],
            "input_schema": [],
        },
    })
    assert dry["status"] == "ok" and dry["ast_valid"] is True and dry["permissions_valid"] is True

    rendered = render_declarative_ui_blocks(
        agent_id="sample_rec",
        name="Sample Rec",
        icon="🎬",
        description="Test panel",
        permissions=["db:read", "db:write", "ui:render"],
        workflow_ir={"modality": "browser", "steps": [{"step_id": "step_1", "channel": "browser", "description": "Visit portal"}], "input_schema": []},
    )
    assert "sample_rec_workflow_runner_card" in rendered
    assert "sample_rec_workflow_input_prompt_box" in rendered
