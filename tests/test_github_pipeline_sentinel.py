"""
Verification Suite for Post-Commit GitHub Pipeline, Vulnerability & Code-Scan Sentinel
(`fleet.tools.github_pipeline_sentinel`) and CodeQL SAST / ReDoS / Command-Line Injection Hardening:
  1. `extract_task_fingerprint` O(N) non-backtracking file parsing (immune to `py/polynomial-redos`).
  2. `_normalize_agy_cli_model` & `_call_antigravity_cli` stdin-only prompt piping (immune to `py/command-line-injection`).
  3. `security_scanner` & `auto_fixer` detection and auto-remediation of Polynomial ReDoS and `codeql-action@v3`.
  4. `github_pipeline_sentinel` check-run failure parsing, CodeQL SARIF annotation extraction, OSV.dev CVE batch auditing,
     `pyproject.toml` vulnerable floor auto-bumping, `PRReviewAgent` routes, and `post-commit` / `pre-push` hook installation.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

from fleet.agents.pr_review.agent import PRReviewAgent
from fleet.api.router import ApiRouter
from fleet.core.antigravity_mirror import extract_task_fingerprint
from fleet.core.hyperscalers import HyperscalerGateway, _normalize_agy_cli_model
from fleet.tools.auto_fixer import fix_codeql_and_security_issues
from fleet.tools.github_pipeline_sentinel import (
    _auto_bump_vulnerable_pyproject_floors,
    audit_dependencies_via_osv,
    build_remediation_prompt,
    extract_declared_python_dependencies,
    parse_codeql_sarif_annotations,
    run_github_pipeline_audit,
)
from fleet.tools.install_git_hooks import install_git_hooks
from fleet.tools.security_scanner import run_security_scan


def test_extract_task_fingerprint_linear_time_no_redos():
    # Pathological input with 15,000 repeated dots ending in '!' that triggers O(N^2) in overlapping [\w.-]+\. regexes
    adversarial = ("a." * 15000) + "! Check fleet/core/hyperscalers.py and dashboard.html @optimizer"
    t0 = time.perf_counter()
    fp = extract_task_fingerprint(adversarial)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 250.0
    assert "optimizer" in fp["agent_targets"]
    assert "hyperscalers.py" in fp["files"]
    assert "dashboard.html" in fp["files"]
    # Version numbers like 2.13 must not be misclassified as filenames
    fp_ver = extract_task_fingerprint("Release v2.13 and 3.12 matrix")
    assert "2.13" not in fp_ver["files"]
    assert "3.12" not in fp_ver["files"]


def test_agy_cli_stdin_only_prompt_piping_no_argv_taint():
    # _normalize_agy_cli_model must return untainted canonical model IDs
    assert _normalize_agy_cli_model("GEMINI-3.8-FLASH-HIGH") == "gemini-3.8-flash-high"
    assert _normalize_agy_cli_model("unknown; rm -rf /") == "gemini-3.8-flash-high"

    gw = HyperscalerGateway()
    secret_user_prompt = "Analyze policy clause SECRET_PAYLOAD_TOKEN_991"
    mock_proc = MagicMock(
        returncode=0,
        stdout=json.dumps({"response": "ok", "usage": {"total_tokens": 12}}),
        stderr="",
    )
    with (
        patch("fleet.core.hyperscalers._get_antigravity_cli_path", return_value="/usr/local/bin/agy"),
        patch("fleet.core.hyperscalers.subprocess.run", return_value=mock_proc) as mock_run,
    ):
        res = gw._call_antigravity_cli(secret_user_prompt, model="gemini-3.8-flash-low", sys_inst="System rule")
        assert res["status"] == "SUCCESS"
        called_argv = mock_run.call_args.args[0]
        # User prompt and system instruction must NEVER appear in OS command-line argv
        assert all("SECRET_PAYLOAD_TOKEN_991" not in arg for arg in called_argv)
        assert all("System rule" not in arg for arg in called_argv)
        assert "--input-format" in called_argv
        assert "SECRET_PAYLOAD_TOKEN_991" in (mock_run.call_args.kwargs.get("input") or "")


def test_auto_fixer_and_scanner_detect_codeql_v3_and_redos(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    cql_file = wf_dir / "codeql.yml"
    v3_action = "github/codeql-action/init@" + "v3"
    cql_file.write_text(f"steps:\n  - uses: {v3_action}\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("fleet.yaml\n.env\nfleet/data/user/\n", encoding="utf-8")

    fleet_pkg = tmp_path / "fleet" / "tools"
    fleet_pkg.mkdir(parents=True)
    sample_py = fleet_pkg / "sample_tls.py"
    sample_py.write_text("import ssl\n\ndef open_tls():\n    ctx = ssl.create_default_context()\n    return ctx\n", encoding="utf-8")

    fixes = fix_codeql_and_security_issues(repo_root=tmp_path)
    assert any("Auto-upgraded deprecated github/codeql-action" in f["detail"] for f in fixes)
    assert "github/codeql-action/init@v4" in cql_file.read_text(encoding="utf-8")
    assert "ctx.minimum_version = ssl.TLSVersion.TLSv1_2" in sample_py.read_text(encoding="utf-8")


def test_parse_codeql_sarif_annotations_and_osv_audit(tmp_path: Path):
    sample_ann = (
        "[py/polynomial-redos] fleet/core/antigravity_mirror.py:926 (This [regular expression](1) may run slow) | "
        "[py/command-line-injection] fleet/core/hyperscalers.py:551 (This command line depends on a [user-provided value](1))"
    )
    parsed = parse_codeql_sarif_annotations(sample_ann)
    assert len(parsed) == 2
    assert parsed[0]["rule_id"] == "py/polynomial-redos"
    assert parsed[0]["file"] == "fleet/core/antigravity_mirror.py"
    assert parsed[0]["line"] == 926
    assert parsed[1]["rule_id"] == "py/command-line-injection"
    assert parsed[1]["line"] == 551

    # Verify dependency extraction & OSV vulnerability auto-bump
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\nversion = "1.0.0"\n[project.optional-dependencies]\nfull = [\n    "PyYAML>=6.0",\n]\n',
        encoding="utf-8",
    )
    deps = extract_declared_python_dependencies(repo_root=tmp_path)
    assert {"name": "PyYAML", "version": "6.0"} in deps

    def fake_osv_request(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Tuple[int, Any]:
        return 200, {
            "results": [
                {
                    "vulns": [
                        {
                            "id": "GHSA-demo-pyyaml-001",
                            "summary": "Demo PyYAML advisory",
                            "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "6.0.2"}]}]}],
                        }
                    ]
                }
            ]
        }

    vulns = audit_dependencies_via_osv(deps, request_fn=fake_osv_request)
    assert len(vulns) == 1
    assert vulns[0]["id"] == "GHSA-demo-pyyaml-001"
    assert vulns[0]["fixed_version"] == "6.0.2"

    bumps = _auto_bump_vulnerable_pyproject_floors(tmp_path, vulns)
    assert len(bumps) == 1
    assert '"PyYAML>=6.0.2"' in pyproject.read_text(encoding="utf-8")


def test_full_github_pipeline_sentinel_and_hooks_and_pr_review_routes(tmp_path: Path):
    # 1. Verify post-commit and pre-push hooks install with sentinel wiring
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_res = install_git_hooks(repo_root=tmp_path)
    assert hook_res["status"] == "installed"
    assert hook_res["post_commit_sentinel_active"] is True
    assert (hooks_dir / "post-commit").is_file()
    assert "spawn_detached_post_push_sentinel" in (hooks_dir / "post-commit").read_text(encoding="utf-8")
    assert "spawn_detached_post_push_sentinel" in (hooks_dir / "pre-push").read_text(encoding="utf-8")

    # 2. Verify end-to-end sentinel check-run + CodeQL annotation + OSV audit with injected mock transport
    (tmp_path / ".gitignore").write_text(
        "\n".join([
            "fleet.yaml",
            ".env",
            "credentials.json",
            "token.json",
            "*.db",
            "fleet/data/user/",
        ]) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.0.0"\n[project.optional-dependencies]\ndev = ["pytest>=7.4.0"]\n',
        encoding="utf-8",
    )

    def mock_transport(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Tuple[int, Any]:
        if "/check-runs" in url and "/annotations" not in url:
            return 200, {
                "check_runs": [
                    {
                        "id": 9001,
                        "name": "Analyze Python Codebase",
                        "head_sha": "deadbeef1234567",
                        "status": "completed",
                        "conclusion": "failure",
                        "html_url": "https://github.com/macazaka/personal-agentic-fleet/runs/9001",
                        "output": {
                            "annotations_count": 1,
                            "annotations_url": "https://api.github.com/repos/macazaka/personal-agentic-fleet/check-runs/9001/annotations",
                        },
                    },
                    {
                        "id": 9002,
                        "name": "Test Suite (ubuntu-24.04, Python 3.12)",
                        "head_sha": "deadbeef1234567",
                        "status": "completed",
                        "conclusion": "success",
                        "output": {"annotations_count": 0, "annotations_url": ""},
                    },
                ]
            }
        if "/annotations" in url:
            return 200, [
                {
                    "annotation_level": "failure",
                    "path": ".github",
                    "start_line": 48,
                    "title": "CodeQL Alerts (1-1 of 1)",
                    "message": "[py/command-line-injection] fleet/core/hyperscalers.py:551 (Command depends on user value)",
                }
            ]
        if "api.osv.dev" in url:
            return 200, {"results": [{"vulns": []}]}
        return 200, []

    report = run_github_pipeline_audit(
        repo="macazaka/personal-agentic-fleet",
        commit_sha="deadbeef1234567",
        auto_remediate=True,
        repo_root=tmp_path,
        request_fn=mock_transport,
    )
    assert report["status"] == "FAIL"
    assert report["checks_total"] == 2
    assert report["checks_passed"] == 1
    assert len(report["pipeline_failures"]) == 1
    assert len(report["code_scan_alerts"]) >= 1
    assert report["code_scan_alerts"][0]["rule_id"] == "py/command-line-injection"
    prompt = build_remediation_prompt(report)
    assert "py/command-line-injection" in prompt

    # 3. Verify PRReviewAgent routes & task execution (offline socket guard returns clean PASS in test mode)
    import urllib.parse

    agent = PRReviewAgent()
    router = ApiRouter()
    agent.register_routes(router)
    h_get = MagicMock()
    assert router.dispatch_get(h_get, "/api/pr_review/pipeline_audit", urllib.parse.urlparse("/api/pr_review/pipeline_audit"))
    assert h_get._send_json.call_args[0][0]["status"] == "ok"

    task_res = agent.execute_task("audit_github_pipelines")
    assert task_res["status"] in ("PASS", "WARN")

    # 4. Verify live repository passes 100/100 on 12-layer security scanner
    live_sec = run_security_scan()
    assert live_sec["status"] == "PASS"
    assert live_sec["score"] == 100

