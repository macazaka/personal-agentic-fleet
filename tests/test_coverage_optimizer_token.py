"""
Exhaustive unit tests targeting remaining branches in fleet/core/optimizer.py and fleet/core/token_optimizer.py
"""

import io
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch
import pytest

import fleet.core.optimizer as opt_mod
import fleet.core.token_optimizer as tok_mod


# ==============================================================================
# OPTIMIZER BRANCH TESTS
# ==============================================================================

def test_optimizer_darwin_memory():
    mock_run = MagicMock()
    def side_effect(cmd, **kwargs):
        if "hw.memsize" in cmd:
            return MagicMock(returncode=0, stdout="17179869184\n")
        elif "vm.pagesize" in cmd:
            return MagicMock(returncode=0, stdout="4096\n")
        elif "vm_stat" in cmd:
            return MagicMock(returncode=0, stdout="Pages free: 100000.\nPages inactive: 50000.\n")
        return MagicMock(returncode=1, stdout="")

    mock_run.side_effect = side_effect
    with patch("subprocess.run", mock_run):
        mem = opt_mod._get_memory_status_darwin()
        assert mem is not None
        assert mem["total_gb"] == 16.0


def test_optimizer_linux_memory(tmp_path):
    proc_meminfo = (
        "MemTotal:       16384000 kB\n"
        "MemAvailable:    8192000 kB\n"
        "MemFree:         4096000 kB\n"
    )
    with patch.object(Path, "is_file", return_value=True):
        with patch.object(Path, "read_text", return_value=proc_meminfo):
            mem = opt_mod._get_memory_status_linux()
            assert mem is not None
            assert mem["total_gb"] > 15.0


def test_optimizer_ram_darwin_and_linux():
    # Darwin
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run") as mock_sub:
            with patch.object(opt_mod, "get_memory_status", return_value={"avail_gb": 8.0, "percent_used": 50}):
                res_d = opt_mod.optimize_ram()
                assert res_d["status"] == "success"
                mock_sub.assert_called_with(["purge"], capture_output=True, timeout=5)

    # Linux
    with patch("sys.platform", "linux"):
        with patch("ctypes.CDLL") as mock_cdll:
            with patch.object(opt_mod, "get_memory_status", return_value={"avail_gb": 8.0, "percent_used": 50}):
                res_l = opt_mod.optimize_ram()
                assert res_l["status"] == "success"


def test_optimizer_startup_settings():
    # Darwin
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run") as mock_sub:
            res_d = opt_mod.open_startup_settings()
            assert res_d["status"] == "success"

    # Windows
    with patch("sys.platform", "win32"):
        with patch("os.name", "nt"):
            with patch("subprocess.run") as mock_sub:
                res_w = opt_mod.open_startup_settings()
                assert res_w["status"] == "success"

    # Linux - launcher success
    with patch("sys.platform", "linux"):
        with patch("fleet.core.optimizer.os.name", "posix"):
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                res_l1 = opt_mod.open_startup_settings()
                assert res_l1["status"] == "success"

            # Linux - xdg-open fallback
            def side_effect(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "xdg-open":
                    return MagicMock(returncode=0)
                return MagicMock(returncode=1)

            with patch("fleet.core.optimizer.Path") as mock_p:
                mock_p.home.return_value = MagicMock()
                with patch("subprocess.run", side_effect=side_effect):
                    res_l2 = opt_mod.open_startup_settings()
                    assert res_l2["status"] == "success"


def test_optimizer_flush_dns_multiplatform():
    # Darwin
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run") as mock_sub:
            res_d = opt_mod.flush_dns_cache()
            assert res_d["status"] == "success"

    # Linux
    with patch("sys.platform", "linux"):
        with patch("subprocess.run") as mock_sub:
            res_l = opt_mod.flush_dns_cache()
            assert res_l["status"] == "success"


# ==============================================================================
# TOKEN OPTIMIZER BRANCH TESTS
# ==============================================================================

def test_token_optimizer_empty_and_fuzzy():
    # Empty inputs
    assert tok_mod.compute_prompt_similarity("", "") == 0.0
    assert tok_mod.get_cached_prompt_response("") is None
    tok_mod.cache_prompt_response("", "")
    assert tok_mod.query_local_knowledge_base("") is None
    assert tok_mod.compress_prompt("") == {"text": "", "chars_saved": 0, "tokens_saved": 0}

    # Fuzzy match
    tok_mod.cache_prompt_response("What is the morning smoothie recipe?", "Drink green smoothie with haldi.")
    # Similar paraphrased question
    fuzzy_ans = tok_mod.get_cached_prompt_response("morning smoothie recipe instructions?", fuzzy_threshold=0.60)
    assert fuzzy_ans == "Drink green smoothie with haldi."

    # Cache expiration eviction
    tok_mod._PROMPT_CACHE["test_expired"] = {
        "ts": time.time() - (tok_mod.PROMPT_CACHE_TTL_SEC + 100),
        "prompt": "expired prompt",
        "tokens": set(),
        "response": "old response",
    }
    # Trigger eviction pass
    tok_mod.get_cached_prompt_response("some other question")
    assert "test_expired" not in tok_mod._PROMPT_CACHE


def test_token_optimizer_minify_and_truncate():
    # Broken syntax triggers regex fallback in minify_python_code_snippet
    broken_code = "def invalid_syntax: ((\n    # remove this line\n    x = 1\n"
    res = tok_mod.minify_python_code_snippet(broken_code)
    assert "# remove this line" not in res
    assert "x = 1" in res

    # Middle-truncation of oversized prompts
    huge_prompt = "A" * 15000
    compressed = tok_mod.compress_prompt(huge_prompt, max_chars=1000)
    assert "...[Pruned" in compressed["text"]
    assert len(compressed["text"]) < 2000


def test_token_optimizer_coalesce_and_deduplicate():
    # Coalesce with <= 1 item
    assert tok_mod.coalesce_queued_prompts([]) == []
    single_item = [{"id": 1, "prompt": "task 1", "images": []}]
    assert tok_mod.coalesce_queued_prompts(single_item) == single_item

    # Coalesce multi-item batch
    batch_items = [
        {"id": 1, "prompt": "first task", "images": []},
        {"id": 2, "prompt": "second task", "images": []},
    ]
    coalesced = tok_mod.coalesce_queued_prompts(batch_items)
    assert len(coalesced) == 1
    assert "Task 1" in coalesced[0]["prompt"]
    assert "Task 2" in coalesced[0]["prompt"]

    # Image deduplication
    img_bytes = b"fake_png_binary_data_12345"
    meta1 = tok_mod.deduplicate_uploaded_image(img_bytes, lambda: {"path": "uploads/img1.png"})
    assert meta1["deduplicated"] is False

    meta2 = tok_mod.deduplicate_uploaded_image(img_bytes, lambda: {"path": "uploads/img2.png"})
    assert meta2["deduplicated"] is True


def test_token_optimizer_deterministic_intents():
    mock_db = MagicMock()
    mock_db.update_task_status.return_value = True

    # PC Optimizer intents
    with patch("fleet.core.optimizer.flush_dns_cache", return_value={"message": "dns cleared"}):
        with patch("fleet.core.optimizer.optimize_ram", return_value={"message": "ram freed"}):
            with patch("fleet.core.optimizer.clean_temp_files", return_value={"reclaimed_mb": 50}):
                r_dns = tok_mod.try_deterministic_intent_route("flush dns")
                assert r_dns["status"] == "success"

                r_ram = tok_mod.try_deterministic_intent_route("optimize ram")
                assert r_ram["status"] == "success"

                r_temp = tok_mod.try_deterministic_intent_route("clean temp")
                assert r_temp["status"] == "success"

                r_opt = tok_mod.try_deterministic_intent_route("/optimize")
                assert r_opt["status"] == "success"

    # Task completion intent
    r_done = tok_mod.try_deterministic_intent_route("/done 42", db=mock_db)
    assert r_done["status"] == "success"

    # Task completion intent when db returns False
    mock_db.update_task_status.return_value = False
    r_done_fail = tok_mod.try_deterministic_intent_route("/done 99", db=mock_db)
    assert r_done_fail["status"] == "error"

    # SBOM generation intent
    with patch("fleet.tools.sbom_generator.generate_sbom", return_value={"bomFormat": "CycloneDX", "component_count": 50}):
        r_sbom = tok_mod.try_deterministic_intent_route("/sbom")
        assert r_sbom["status"] == "success"
