"""
Tests for Personal Agentic Fleet - Unified Command Line Interface (CLI).
Verifies all subcommands, arguments, json formatting, and error handling.
Consumes $0.00 / 0 LLM tokens.
"""

import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from fleet.cli import build_parser, main
import fleet.config as config


class TestFleetCLI(unittest.TestCase):
    """Exhaustive test suite for fleet.cli."""

    def setUp(self):
        self.held_stdout = io.StringIO()
        self.held_stderr = io.StringIO()
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.held_stdout
        sys.stderr = self.held_stderr

    def tearDown(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

    def test_parser_creation(self):
        parser = build_parser()
        self.assertIsNotNone(parser)
        self.assertEqual(parser.prog, "fleet")

    def test_cli_no_args_prints_help(self):
        ret = main([])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("PERSONAL AGENTIC FLEET CLI", output)
        self.assertIn("start", output)

    def test_cli_version(self):
        ret = main(["version"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn(config.VERSION, output)

    def test_cli_status(self):
        ret = main(["status"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("Cognitive Fleet Mind", output)
        self.assertIn("Harmony Score", output)

    def test_cli_status_json(self):
        ret = main(["status", "--json"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        data = json.loads(output)
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertIn("cognitive_harmony", data)

    def test_cli_agents_list(self):
        ret = main(["agents", "list"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("Registered Agents", output)
        self.assertIn("health", output)

    def test_cli_agents_info(self):
        ret = main(["agents", "info", "health"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("Agent Manifest: Health & Wellness", output)
        self.assertIn("db:read", output)

    def test_cli_agents_info_missing_target(self):
        ret = main(["agents", "info"])
        self.assertEqual(ret, 1)
        output = self.held_stdout.getvalue()
        self.assertIn("[ERROR] Missing agent ID", output)

    def test_cli_agents_info_invalid_target(self):
        ret = main(["agents", "info", "non_existent_agent_xyz"])
        self.assertEqual(ret, 1)
        output = self.held_stdout.getvalue()
        self.assertIn("not found in registry", output)

    def test_cli_agents_enable_disable(self):
        # Disable
        ret = main(["agents", "disable", "backlog"])
        self.assertEqual(ret, 0)
        # Enable
        ret = main(["agents", "enable", "backlog"])
        self.assertEqual(ret, 0)

    def test_cli_agents_enable_missing_target(self):
        ret = main(["agents", "enable"])
        self.assertEqual(ret, 1)
        output = self.held_stdout.getvalue()
        self.assertIn("[ERROR] Missing agent ID", output)

    def test_cli_agents_disable_missing_target(self):
        ret = main(["agents", "disable"])
        self.assertEqual(ret, 1)
        output = self.held_stdout.getvalue()
        self.assertIn("[ERROR] Missing agent ID", output)

    def test_cli_doctor(self):
        ret = main(["doctor"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("Fleet Doctor [PASS]", output)

    def test_cli_doctor_json(self):
        ret = main(["doctor", "--json"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        data = json.loads(output)
        self.assertEqual(data["status"], "PASS")

    def test_cli_security(self):
        ret = main(["security"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("Fleet Security Scan [PASS]", output)

    def test_cli_security_json(self):
        ret = main(["security", "--json"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        data = json.loads(output)
        self.assertEqual(data["status"], "PASS")

    def test_cli_mind_status(self):
        ret = main(["mind", "--status"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        self.assertIn("COGNITIVE MIND STATUS", output)

    def test_cli_mind_json(self):
        ret = main(["mind", "--json"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        data = json.loads(output)
        self.assertIn("cognitive_harmony_index", data)

    def test_cli_heal_json(self):
        ret = main(["heal", "--json"])
        self.assertEqual(ret, 0)
        output = self.held_stdout.getvalue()
        data = json.loads(output)
        self.assertIn("scan_id", data)

    def test_cli_start_already_running(self):
        with patch("fleet.cli.is_port_in_use", return_value=True):
            ret = main(["start", "--no-browser"])
            self.assertEqual(ret, 0)
            output = self.held_stdout.getvalue()
            self.assertIn("already running", output)

    def test_cli_stop(self):
        with patch("fleet.cli.get_active_pid", return_value=None), \
             patch("fleet.cli.is_port_in_use", return_value=False):
            ret = main(["stop"])
            self.assertEqual(ret, 0)
            output = self.held_stdout.getvalue()
            self.assertIn("stopped cleanly", output)

    def test_cli_wiki_dry_run(self):
        with patch("fleet.tools.sync_wiki.main", return_value=0):
            ret = main(["wiki", "--dry-run"])
            self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()

