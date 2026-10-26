"""Unit tests for fleet.app."""
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

import fleet.app as app_mod


@pytest.fixture(autouse=True)
def preserve_env():
    old_prod = os.environ.get("FLEET_PRODUCTION_SERVER")
    yield
    if old_prod is None:
        os.environ.pop("FLEET_PRODUCTION_SERVER", None)
    else:
        os.environ["FLEET_PRODUCTION_SERVER"] = old_prod


def test_is_port_in_use():
    with patch("socket.socket") as mock_sock:
        instance = MagicMock()
        mock_sock.return_value.__enter__.return_value = instance

        instance.connect_ex.return_value = 0
        assert app_mod.is_port_in_use(7890) is True

        instance.connect_ex.return_value = 1
        assert app_mod.is_port_in_use(7890) is False


def test_open_browser_delayed():
    with patch("time.sleep"):
        with patch("webbrowser.open") as mock_open:
            app_mod.open_browser_delayed("http://127.0.0.1:7890", delay=0.01)
            mock_open.assert_called_once()


def test_app_main_scenarios():
    # Scenario 1: Port is already active
    with patch("fleet.app.is_port_in_use", return_value=True):
        with patch("webbrowser.open") as mock_open:
            with patch.object(sys, "argv", ["app.py"]):
                app_mod.main()
                mock_open.assert_called_once()

    # Scenario 2: Port already active with --no-browser
    with patch("fleet.app.is_port_in_use", return_value=True):
        with patch("webbrowser.open") as mock_open:
            with patch.object(sys, "argv", ["app.py", "--no-browser"]):
                app_mod.main()
                mock_open.assert_not_called()

    # Scenario 3: Launch new instance with --no-browser
    with patch("fleet.app.is_port_in_use", return_value=False):
        with patch("fleet.app.start_server") as mock_server:
            with patch("threading.Thread") as mock_thread:
                with patch.object(sys, "argv", ["app.py", "--no-browser"]):
                    app_mod.main()
                    mock_server.assert_called_once()

    # Scenario 4: Launch new instance with default args (browser enabled)
    with patch("fleet.app.is_port_in_use", return_value=False):
        with patch("fleet.app.start_server") as mock_server:
            with patch("threading.Thread") as mock_thread:
                with patch.object(sys, "argv", ["app.py"]):
                    app_mod.main()
                    mock_server.assert_called_once()

    # Scenario 5: Server raises exception
    with patch("fleet.app.is_port_in_use", return_value=False):
        with patch("fleet.app.start_server", side_effect=RuntimeError("Bind error")):
            with patch("threading.Thread"):
                with patch.object(sys, "argv", ["app.py", "--no-browser"]):
                    app_mod.main()  # Should handle gracefully without raising


def test_app_pythonw_redirect():
    # Test stdout None handling logic
    with patch.object(sys, "stdout", None):
        with patch.object(sys, "stderr", None):
            with patch("builtins.open", create=True) as mock_open:
                mock_fp = MagicMock()
                mock_open.return_value = mock_fp
                fp = app_mod.setup_streams()
                assert fp == mock_fp
                # Test excepthook
                if sys.excepthook:
                    sys.excepthook(RuntimeError, RuntimeError("Test error"), None)
                    mock_fp.flush.assert_called()

    # Test open_browser_delayed exception branch
    with patch("webbrowser.open", side_effect=Exception("Failed open")):
        app_mod.open_browser_delayed("http://127.0.0.1:7890", delay=0.0)


def test_app_pid_and_server_exceptions():
    from pathlib import Path

    # 1. PID file write exception
    with patch("fleet.app.is_port_in_use", return_value=False):
        with patch.object(Path, "write_text", side_effect=OSError("Read-only")):
            with patch("fleet.app.start_server"):
                with patch("threading.Thread"):
                    with patch.object(sys, "argv", ["app.py", "--no-browser"]):
                        app_mod.main()

    # 2. Server exception with sys.stdout and sys.stderr flushing
    with patch("fleet.app.is_port_in_use", return_value=False):
        with patch("fleet.app.start_server", side_effect=Exception("Server fatal error")):
            with patch("threading.Thread"):
                with patch.object(sys, "argv", ["app.py", "--no-browser"]):
                    app_mod.main()

    # 3. win32 reconfigure exception branch (lines 44-47)
    with patch.object(sys, "stdout", MagicMock(reconfigure=MagicMock(side_effect=Exception("reconfigure fail")))):
        with patch.object(sys, "platform", "win32"):
            app_mod.setup_streams()




