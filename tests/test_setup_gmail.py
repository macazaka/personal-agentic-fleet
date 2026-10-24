"""Unit tests for fleet.setup_gmail."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import fleet.setup_gmail as setup_mod


def test_print_step_by_step_guide(capsys):
    setup_mod.print_step_by_step_guide()
    captured = capsys.readouterr()
    assert "HOW TO GET YOUR GMAIL CREDENTIALS" in captured.out


def test_authenticate_and_verify_success(capsys):
    with patch("fleet.setup_gmail.GmailManager") as mock_mgr_cls:
        mgr_inst = MagicMock()
        mock_mgr_cls.return_value = mgr_inst

        # Mock service and users
        mock_service = MagicMock()
        mgr_inst.service = mock_service

        mock_profile = {"emailAddress": "testuser@gmail.com", "messagesTotal": 1234}
        mock_service.users().getProfile().execute.return_value = mock_profile

        # Mock labels
        mock_service.users().labels().list().execute.return_value = {
            "labels": [{"name": "Fleet/0-Meetings", "id": "lbl_0"}]
        }
        mock_service.users().labels().create().execute.return_value = {"id": "lbl_new"}

        # Mock sync_and_classify
        mgr_inst.sync_and_classify.return_value = {
            "total_processed": 50,
            "counts": {"Meetings": 10, "Respond": 5, "Note": 15, "FYI": 10, "Ignore": 10}
        }

        setup_mod.authenticate_and_verify()
        captured = capsys.readouterr()
        assert "Connected to Gmail Account: testuser@gmail.com" in captured.out
        assert "Successfully processed 50 emails" in captured.out


def test_authenticate_and_verify_error(capsys):
    with patch("fleet.setup_gmail.GmailManager", side_effect=RuntimeError("Auth failed")):
        setup_mod.authenticate_and_verify()
        captured = capsys.readouterr()
        assert "Error during authentication" in captured.out


def test_setup_gmail_main():
    # 1. Credentials file does not exist
    mock_file = MagicMock()
    mock_file.exists.return_value = False
    mock_file.resolve.return_value = "credentials.json"
    with patch("fleet.setup_gmail.CREDENTIALS_FILE", mock_file):
        with patch.object(setup_mod, "print_step_by_step_guide") as mock_guide:
            setup_mod.main()
            mock_guide.assert_called_once()

    # 2. Credentials file exists
    mock_file_exists = MagicMock()
    mock_file_exists.exists.return_value = True
    with patch("fleet.setup_gmail.CREDENTIALS_FILE", mock_file_exists):
        with patch.object(setup_mod, "authenticate_and_verify") as mock_auth:
            setup_mod.main()
            mock_auth.assert_called_once()


