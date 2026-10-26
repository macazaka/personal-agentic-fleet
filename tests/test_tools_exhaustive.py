"""
Exhaustive Unit Tests for fleet.tools:
- install_service
- crash_reporter
- github_branch_protection
- preflight_gate
- fleet_doctor
- sbom_generator
- security_scanner
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

import fleet.tools.install_service as install_svc
import fleet.tools.crash_reporter as crash_rep
import fleet.tools.github_branch_protection as gbp
import fleet.tools.preflight_gate as pfg
import fleet.tools.fleet_doctor as fdoc
import fleet.tools.sbom_generator as sbom_gen
import fleet.tools.security_scanner as sec_scan


# ---------------------------------------------------------------------------
# 1. install_service tests
# ---------------------------------------------------------------------------
def test_install_service_windows(tmp_path):
    # Missing VBS
    with patch.object(install_svc, "get_repo_root", return_value=tmp_path):
        res = install_svc.install_windows_task()
        assert res["status"] == "error"

        # Create dummy VBS
        (tmp_path / "start_control_center.vbs").write_text("' dummy", encoding="utf-8")
        
        # Subprocess success
        mock_proc = MagicMock(returncode=0, stdout="Success", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            res2 = install_svc.install_windows_task()
            assert res2["status"] == "success"

        # Subprocess failure
        mock_proc_fail = MagicMock(returncode=1, stdout="", stderr="Access denied")
        with patch("subprocess.run", return_value=mock_proc_fail):
            res3 = install_svc.install_windows_task()
            assert res3["status"] == "error"


def test_uninstall_windows_service():
    mock_proc = MagicMock(returncode=0, stdout="Success", stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        res = install_svc.uninstall_windows_task()
        assert res["status"] == "success"

    mock_proc_fail = MagicMock(returncode=1, stdout="", stderr="Task not found")
    with patch("subprocess.run", return_value=mock_proc_fail):
        res2 = install_svc.uninstall_windows_task()
        assert res2["status"] == "warn"


def test_install_service_macos_and_linux(tmp_path):
    with patch.object(install_svc, "get_repo_root", return_value=tmp_path), \
         patch("pathlib.Path.home", return_value=tmp_path):
        
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            # macOS
            res_mac = install_svc.install_macos_launchagent()
            assert res_mac["status"] == "success"

            res_un_mac = install_svc.uninstall_macos_launchagent()
            assert res_un_mac["status"] == "success"

            # Missing plist
            res_un_mac2 = install_svc.uninstall_macos_launchagent()
            assert res_un_mac2["status"] == "warn"

            # Linux
            res_lin = install_svc.install_linux_systemd()
            assert res_lin["status"] == "success"

            res_un_lin = install_svc.uninstall_linux_systemd()
            assert res_un_lin["status"] == "success"


def test_install_service_dispatch_and_cli():
    with patch.object(install_svc, "install_windows_task", return_value={"status": "win_ok"}), \
         patch.object(install_svc, "install_macos_launchagent", return_value={"status": "mac_ok"}), \
         patch.object(install_svc, "install_linux_systemd", return_value={"status": "lin_ok"}), \
         patch.object(install_svc, "uninstall_windows_task", return_value={"status": "win_un_ok"}), \
         patch.object(install_svc, "uninstall_macos_launchagent", return_value={"status": "mac_un_ok"}), \
         patch.object(install_svc, "uninstall_linux_systemd", return_value={"status": "lin_un_ok"}):
        
        with patch("sys.platform", "win32"):
            assert install_svc.install_service()["status"] == "win_ok"
            assert install_svc.uninstall_service()["status"] == "win_un_ok"

        with patch("sys.platform", "darwin"):
            assert install_svc.install_service()["status"] == "mac_ok"
            assert install_svc.uninstall_service()["status"] == "mac_un_ok"

        with patch("sys.platform", "linux"):
            assert install_svc.install_service()["status"] == "lin_ok"
            assert install_svc.uninstall_service()["status"] == "lin_un_ok"

    # CLI test
    with patch("sys.argv", ["install_service.py", "--install"]), \
         patch.object(install_svc, "install_service", return_value={"status": "success", "message": "done"}):
        assert install_svc.main() is None

    with patch("sys.argv", ["install_service.py", "--uninstall"]), \
         patch.object(install_svc, "uninstall_service", return_value={"status": "success", "message": "done"}):
        assert install_svc.main() is None


# ---------------------------------------------------------------------------
# 2. crash_reporter tests
# ---------------------------------------------------------------------------
def test_crash_reporter_sanitization():
    # String redacting
    test_token = "sk-" + "12345678901234567890123456789012"
    raw = f"My secret token is {test_token} and bearer my_secret_token_1234567890"
    sanitized = crash_rep.sanitize_sensitive_data(raw)
    assert "sk-" not in sanitized
    assert "[REDACTED" in sanitized

    # Dict and list redacting
    nested = {
        "api_key": "secret_abc",
        "normal_field": "hello",
        "sub": ["bearer xyz_long_secret_bearer_token", 123]
    }
    s_nested = crash_rep.sanitize_sensitive_data(nested)
    assert s_nested["api_key"] == "[REDACTED]"
    assert s_nested["normal_field"] == "hello"
    assert s_nested["sub"][1] == 123


def test_crash_reporter_lifecycle(tmp_path):
    with patch.object(crash_rep, "CRASH_REPORTS_DIR", tmp_path / "crashes"):
        snap = crash_rep.get_system_snapshot()
        assert "platform" in snap
        assert "python_version" in snap

        try:
            raise ValueError("Test crash error with token=12345")
        except ValueError as err:
            rep_path = crash_rep.generate_crash_report(type(err), err, err.__traceback__, thread_name="test-worker")
            assert rep_path.is_file()

        reports = crash_rep.list_crash_reports()
        assert len(reports) == 1
        assert reports[0]["exception_type"] == "ValueError"

        # Prune test
        pruned = crash_rep.prune_old_crash_reports(keep=0)
        assert pruned == 1
        assert len(crash_rep.list_crash_reports()) == 0


# ---------------------------------------------------------------------------
# 3. github_branch_protection tests
# ---------------------------------------------------------------------------
def test_github_branch_protection_verify(tmp_path):
    # 1. Missing files
    res = gbp.verify_branch_protection(repo_root=tmp_path)
    assert res["status"] == "FAIL"

    # 2. Setup valid structure
    gh_dir = tmp_path / ".github"
    gh_dir.mkdir(parents=True)
    rulesets_dir = gh_dir / "rulesets"
    rulesets_dir.mkdir(parents=True)

    bp_json = {
        "target": "branch",
        "enforcement": "active",
        "rules": [{"type": t} for t in gbp.REQUIRED_RULESET_TYPES]
    }
    (gh_dir / "branch-protection.json").write_text(json.dumps(bp_json), encoding="utf-8")

    for f_name in gbp.EXPECTED_RULESET_FILES:
        (rulesets_dir / f_name).write_text(
            json.dumps({"name": f_name, "enforcement": "active", "rules": [{"type": "deletion"}]}),
            encoding="utf-8"
        )

    (gh_dir / "CODEOWNERS").write_text("* @maintainer\n", encoding="utf-8")

    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-push").write_text("#!/bin/sh\n# Main Branch Protection\nexit 0\n", encoding="utf-8")

    res2 = gbp.verify_branch_protection(repo_root=tmp_path)
    assert res2["status"] == "PASS"
    assert len(res2["issues"]) == 0


def test_github_branch_protection_apply_remote(tmp_path):
    # Token missing
    with patch.dict(os.environ, {}, clear=True):
        res = gbp.apply_remote_branch_protection(repo_root=tmp_path)
        assert res["status"] == "IMPORT_READY"

    # Setup ruleset files
    rulesets_dir = tmp_path / ".github" / "rulesets"
    rulesets_dir.mkdir(parents=True)
    for f_name in gbp.EXPECTED_RULESET_FILES:
        (rulesets_dir / f_name).write_text(json.dumps({"name": f_name, "rules": []}), encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"id": 101, "name": "Fleet Main Protection"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_mock_token"}), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        res2 = gbp.apply_remote_branch_protection(repo_root=tmp_path)
        assert res2["status"] == "APPLIED"


def test_github_branch_protection_cli():
    mock_res = {
        "status": "PASS",
        "issues": [],
        "rulesets_verified": ["01-main-immutable-and-signed.json"],
        "protected_branch": "main",
        "policy_file": ".github/branch-protection.json",
        "codeowners_file": ".github/CODEOWNERS",
        "local_pre_push_guard": True,
    }
    with patch.object(gbp, "verify_branch_protection", return_value=mock_res):
        with patch("sys.argv", ["gbp.py"]):
            assert gbp.main() == 0
        with patch("sys.argv", ["gbp.py", "--strict"]):
            assert gbp.main() == 0

    with patch.object(gbp, "verify_branch_protection", return_value=mock_res), \
         patch.object(gbp, "apply_remote_branch_protection", return_value={"status": "APPLIED", "detail": "All ok"}):
        with patch("sys.argv", ["gbp.py", "--apply-remote"]):
            assert gbp.main() == 0


# ---------------------------------------------------------------------------
# 4. preflight_gate tests
# ---------------------------------------------------------------------------
def test_preflight_gate_package_isolation(tmp_path):
    agents_dir = tmp_path / "fleet" / "agents"
    agents_dir.mkdir(parents=True)

    # Missing manifest
    bad_agent = agents_dir / "bad_agent"
    bad_agent.mkdir()
    res = pfg.verify_agent_package_isolation(repo_root=tmp_path)
    assert res["status"] == "FAIL"

    # Complete valid agent
    valid_agent = agents_dir / "good_agent"
    valid_agent.mkdir()
    (valid_agent / "manifest.json").write_text(json.dumps({
        "id": "good_agent",
        "name": "Good Agent",
        "version": "1.0.0",
        "permissions": ["db:read"]
    }), encoding="utf-8")
    (valid_agent / "agent.py").write_text("class GoodAgent: pass\n", encoding="utf-8")
    ui_dir = valid_agent / "ui"
    ui_dir.mkdir()
    (ui_dir / "panel.html").write_text("<div>Good Agent UI</div>", encoding="utf-8")

    # Remove bad agent
    bad_agent.rmdir()

    res2 = pfg.verify_agent_package_isolation(repo_root=tmp_path)
    assert res2["status"] == "PASS"


def test_preflight_gate_documentation_integrity(tmp_path):
    # Missing all docs
    res = pfg.verify_documentation_integrity(repo_root=tmp_path)
    assert res["status"] == "FAIL"

    # Create required documents with > 500 chars
    long_content = "# Doc Title\n\n" + ("Comprehensive documentation content line.\n" * 20)
    for doc in pfg.REQUIRED_DOCUMENTS:
        p = tmp_path / doc
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(long_content, encoding="utf-8")

    res2 = pfg.verify_documentation_integrity(repo_root=tmp_path)
    assert res2["status"] == "PASS"


def test_preflight_gate_runner():
    # 1. Full pass
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "PASS", "python_version": "3.14.7", "security_score": 100}), \
         patch.object(pfg, "run_security_scan", return_value={"status": "PASS", "total_findings": 0}), \
         patch.object(pfg, "verify_agent_package_isolation", return_value={"status": "PASS", "verified_agents": 5}), \
         patch.object(pfg, "verify_documentation_integrity", return_value={"status": "PASS", "verified_files": 13, "total_required": 13}), \
         patch("subprocess.run", return_value=MagicMock(returncode=0)):
        assert pfg.run_preflight_gate() == 0

    # 2. Stage 1 Doctor fail
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "FAIL", "security_score": 50, "diagnostics": [{"name": "Check", "status": "FAIL", "detail": "Err"}]}):
        assert pfg.run_preflight_gate() == 1

    # 3. Stage 2 Security fail
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "PASS", "python_version": "3.14.7", "security_score": 100}), \
         patch.object(pfg, "run_security_scan", return_value={"status": "FAIL", "total_findings": 2, "findings": [{"severity": "CRITICAL", "file": "f.py", "line": 1, "detail": "err"}]}):
        assert pfg.run_preflight_gate() == 1

    # 4. Stage 3 Isolation fail
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "PASS", "python_version": "3.14.7", "security_score": 100}), \
         patch.object(pfg, "run_security_scan", return_value={"status": "PASS", "total_findings": 0}), \
         patch.object(pfg, "verify_agent_package_isolation", return_value={"status": "FAIL", "findings": ["Missing manifest"]}):
        assert pfg.run_preflight_gate() == 1

    # 5. Stage 4 Docs fail
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "PASS", "python_version": "3.14.7", "security_score": 100}), \
         patch.object(pfg, "run_security_scan", return_value={"status": "PASS", "total_findings": 0}), \
         patch.object(pfg, "verify_agent_package_isolation", return_value={"status": "PASS", "verified_agents": 5}), \
         patch.object(pfg, "verify_documentation_integrity", return_value={"status": "FAIL", "findings": ["Missing README.md"]}):
        assert pfg.run_preflight_gate() == 1

    # 6. Stage 5 Tests fail
    with patch.object(pfg, "run_fleet_doctor", return_value={"status": "PASS", "python_version": "3.14.7", "security_score": 100}), \
         patch.object(pfg, "run_security_scan", return_value={"status": "PASS", "total_findings": 0}), \
         patch.object(pfg, "verify_agent_package_isolation", return_value={"status": "PASS", "verified_agents": 5}), \
         patch.object(pfg, "verify_documentation_integrity", return_value={"status": "PASS", "verified_files": 13, "total_required": 13}), \
         patch("subprocess.run", return_value=MagicMock(returncode=2)):
        assert pfg.run_preflight_gate() == 2


# ---------------------------------------------------------------------------
# 5. fleet_doctor & sbom_generator tests
# ---------------------------------------------------------------------------
def test_fleet_doctor_cli():
    mock_rep = {
        "status": "PASS",
        "diagnostics": [],
        "security_score": 100,
        "python_version": "3.14.7",
        "minimum_python_required": "3.10",
    }
    with patch.object(fdoc, "run_fleet_doctor", return_value=mock_rep):
        with patch("sys.argv", ["fdoc.py", "--json"]):
            fdoc.main()
        with patch("sys.argv", ["fdoc.py"]):
            fdoc.main()

    fail_rep = dict(mock_rep, status="FAIL", security_score=50, diagnostics=[{"name": "x", "status": "FAIL", "detail": "y"}])
    with patch.object(fdoc, "run_fleet_doctor", return_value=fail_rep):
        with patch("sys.argv", ["fdoc.py", "--strict"]), pytest.raises(SystemExit) as exc:
            fdoc.main()
        assert exc.value.code == 1


def test_sbom_generator(tmp_path):
    res = sbom_gen.generate_sbom(repo_root=pfg._ROOT, save_to_disk=False)
    assert res["bomFormat"] == "CycloneDX"

    with patch("sys.argv", ["sbom_generator.py"]):
        assert sbom_gen.main() == 0


# ---------------------------------------------------------------------------
# 6. security_scanner tests
# ---------------------------------------------------------------------------
def test_security_scanner_rules(tmp_path):
    # 1. Clean content
    clean_hits = sec_scan.scan_text_for_secrets("print('Safe code')", "clean.py")
    assert clean_hits == []

    # 2. Secret detection
    prefix = "AIza"
    suffix = "SyD_fake_key_1234567890123456789012"
    secret_text = f"KEY = '{prefix}{suffix}'"
    hits = sec_scan.scan_text_for_secrets(secret_text, "secret.py")
    assert len(hits) > 0
    assert hits[0]["severity"] == "CRITICAL"

    # 3. CLI options
    with patch.object(sec_scan, "run_security_scan", return_value={"status": "PASS", "findings_count": 0, "findings": [], "files_scanned": 10, "passed_checks": 6, "total_checks": 6, "security_score": 100, "checks": []}):
        with patch("sys.argv", ["sec_scan.py", "--json"]):
            sec_scan.main()
        with patch("sys.argv", ["sec_scan.py"]):
            sec_scan.main()

    with patch.object(sec_scan, "run_security_scan", return_value={"status": "FAIL", "findings_count": 1, "findings": [{"severity": "HIGH", "file": "x.py", "line": 1, "detail": "leak"}], "files_scanned": 10, "passed_checks": 5, "total_checks": 6, "security_score": 90, "checks": []}):
        with patch("sys.argv", ["sec_scan.py", "--strict"]), pytest.raises(SystemExit) as exc:
            sec_scan.main()
        assert exc.value.code == 1
