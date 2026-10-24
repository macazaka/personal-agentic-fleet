"""Unit tests for fleet.integrations.gmail_client."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fleet.core.database import FleetDatabase
from fleet.integrations.gmail_client import (
    GmailManager,
    extract_unsubscribe_info,
    get_credentials_file,
    get_two_month_lookback_query,
)


def test_lookback_query_and_credentials():
    query = get_two_month_lookback_query()
    assert "after:" in query
    assert "Fleet/0-Meetings" in query

    creds_file = get_credentials_file()
    assert isinstance(creds_file, Path)

    # Test get_credentials_file variations
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_data = Path(tmpdir)
        with patch("fleet.integrations.gmail_client.DATA_DIR", tmp_data):
            # 1. Neither exists -> returns standard
            assert get_credentials_file() == tmp_data / "credentials.json"

            # 2. client_secret exists
            cs_file = tmp_data / "client_secret_123.json"
            cs_file.write_text("{}", encoding="utf-8")
            assert get_credentials_file() == cs_file

            # 3. standard credentials.json exists -> takes precedence
            std_file = tmp_data / "credentials.json"
            std_file.write_text("{}", encoding="utf-8")
            assert get_credentials_file() == std_file



def test_gmail_manager_mock_and_sync():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test.db")
        mgr = GmailManager(db=db)

        # In offline/test mode, should gracefully fall back to mock
        assert isinstance(mgr.is_connected, bool)

        # Mock service behavior
        mock_service = MagicMock()
        mgr.service = mock_service
        mgr.is_connected = True

        # Mock label list
        mock_service.users().labels().list().execute.return_value = {
            "labels": [{"id": "lbl_0", "name": "Fleet/0-Meetings"}]
        }
        mock_service.users().labels().create().execute.return_value = {"id": "lbl_created"}

        mgr._ensure_labels_exist()
        assert 0 in mgr.label_ids
        assert mgr.label_ids[0] == "lbl_0"

        # Test exception branch in _ensure_labels_exist (lines 127-128)
        mock_service.users().labels().list().execute.side_effect = RuntimeError("Label list error")
        mgr._ensure_labels_exist()
        mock_service.users().labels().list().execute.side_effect = None


        # Mock messages list
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg_123"}]
        }
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg_123",
            "snippet": "Can you review?",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Quick question?"},
                    {"name": "From", "value": "boss@work.com"}
                ]
            }
        }
        mock_service.users().messages().batchModify().execute.return_value = {}

        # Run sync_and_classify (dry run)
        res = mgr.sync_and_classify(dry_run=True, auto_archive_ignore=True)
        assert res["status"] == "success"
        assert res["total_processed"] >= 1

        # Run sync_and_classify (live apply)
        mgr.label_ids = {0: "lbl_0", 1: "lbl_1", 2: "lbl_2", 3: "lbl_3", 4: "lbl_4"}
        res_live = mgr.sync_and_classify(dry_run=False, auto_archive_ignore=True)
        assert res_live["status"] == "success"
        mock_service.users().messages().batchModify.assert_called()

        # Offline fallback when no service
        mgr.service = None
        mgr.is_connected = False
        res_offline = mgr.sync_and_classify(dry_run=True)
        assert res_offline["status"] == "success"
        assert res_offline["connected_to_live_gmail"] is False


def test_gmail_auth_and_refresh():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_token = Path(tmpdir) / "token.json"
        tmp_creds = Path(tmpdir) / "credentials.json"

        # 1. Interactive Auth - Missing creds file
        with patch("fleet.integrations.gmail_client.get_credentials_file", return_value=tmp_creds):
            mgr = GmailManager.__new__(GmailManager)
            mgr.db = FleetDatabase(db_path=Path(tmpdir) / "test.db")
            mgr.service = None
            mgr.label_ids = {}
            import pytest
            with pytest.raises(FileNotFoundError):
                mgr.authenticate_interactive()

        # 2. Interactive Auth - Success path
        tmp_creds.write_text('{"installed": {}}', encoding="utf-8")
        with patch("fleet.integrations.gmail_client.get_credentials_file", return_value=tmp_creds):
            with patch("fleet.integrations.gmail_client.TOKEN_FILE", tmp_token):
                with patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file") as mock_flow:
                    flow_inst = MagicMock()
                    mock_flow.return_value = flow_inst
                    mock_creds_obj = MagicMock()
                    mock_creds_obj.to_json.return_value = '{"token": "fake"}'
                    flow_inst.run_local_server.return_value = mock_creds_obj

                    with patch("googleapiclient.discovery.build") as mock_build:
                        mock_build.return_value = MagicMock()
                        with patch.object(mgr, "_ensure_labels_exist"):
                            creds = mgr.authenticate_interactive()
                            assert creds == mock_creds_obj

        # 3. Token refresh on init
        tmp_token.write_text('{"token": "expired"}', encoding="utf-8")
        with patch("fleet.integrations.gmail_client.TOKEN_FILE", tmp_token):
            with patch("google.oauth2.credentials.Credentials.from_authorized_user_file") as mock_from_file:
                mock_c = MagicMock()
                mock_c.expired = True
                mock_c.refresh_token = "ref_123"
                mock_c.valid = True
                mock_c.to_json.return_value = '{"token": "refreshed"}'
                mock_from_file.return_value = mock_c

                with patch("googleapiclient.discovery.build") as mock_b:
                    mock_b.return_value = MagicMock()
                    with patch("google.auth.transport.requests.Request"):
                        with patch.object(GmailManager, "_ensure_labels_exist"):
                            ref_mgr = GmailManager(db=FleetDatabase(db_path=Path(tmpdir) / "test2.db"))
                            assert ref_mgr.is_connected is True

        # 4. Corrupted token exception in init
        tmp_token.write_text('corrupted', encoding="utf-8")
        with patch("fleet.integrations.gmail_client.TOKEN_FILE", tmp_token):
            err_mgr = GmailManager(db=FleetDatabase(db_path=Path(tmpdir) / "test3.db"))
            assert err_mgr.is_connected is False

        # 5. _ensure_labels_exist when service is None
        err_mgr.service = None
        err_mgr._ensure_labels_exist()

        # 6. _apply_labels_to_gmail with missing label id
        err_mgr.service = MagicMock()
        err_mgr.label_ids = {}  # No label mapped
        applied = err_mgr._apply_labels_to_gmail([{"id": "m1", "category_id": 0}], auto_archive_ignore=True)
        assert applied == 0


def test_extract_unsubscribe_info():
    # 1. Header with HTTP and mailto
    h1 = {"list-unsubscribe": "<https://example.com/unsub?id=123>, <mailto:unsub@example.com>"}
    info1 = extract_unsubscribe_info(h1)
    assert info1["can_unsubscribe"] is True
    assert info1["unsubscribe_url"] == "https://example.com/unsub?id=123"
    assert info1["unsubscribe_type"] == "http"

    # 2. Header with one-click post
    h2 = {
        "list-unsubscribe": "<https://example.com/oneclick>",
        "list-unsubscribe-post": "List-Unsubscribe=One-Click"
    }
    info2 = extract_unsubscribe_info(h2)
    assert info2["can_unsubscribe"] is True
    assert info2["unsubscribe_url"] == "https://example.com/oneclick"
    assert info2["unsubscribe_type"] == "one_click"

    # 3. Header with only mailto
    h3 = {"list-unsubscribe": "<mailto:leave-list@example.com?subject=unsubscribe>"}
    info3 = extract_unsubscribe_info(h3)
    assert info3["can_unsubscribe"] is True
    assert info3["unsubscribe_url"] == "mailto:leave-list@example.com?subject=unsubscribe"
    assert info3["unsubscribe_type"] == "mailto"

    # 4. Snippet fallback with URL
    h4 = {}
    snip4 = "Click here to unsubscribe: https://newsletter.com/opt-out?u=892 or manage preferences"
    info4 = extract_unsubscribe_info(h4, snippet=snip4)
    assert info4["can_unsubscribe"] is True
    assert "https://newsletter.com/opt-out?u=892" in info4["unsubscribe_url"]
    assert info4["unsubscribe_type"] == "http"

    # 5. Empty / no unsubscribe
    h5 = {}
    info5 = extract_unsubscribe_info(h5, snippet="Hey, let's meet tomorrow.")
    assert info5["can_unsubscribe"] is False
    assert info5["unsubscribe_url"] is None
    assert info5["unsubscribe_type"] is None


def test_gmail_unsubscribe_methods():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test_unsub.db")
        mgr = GmailManager(db=db)

        # 1. Unsubscribe with HTTP URL (mock urlopen success)
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_open.return_value = mock_resp

            res = mgr.unsubscribe_from_email(
                message_id="msg_004",
                url="https://github.com/settings/notifications",
                unsub_type="http",
                sender="notifications@github.com",
                subject="Weekly Digest"
            )
            assert res["status"] == "success"
            assert res["unsubscribed"] is True
            assert res["http_pinged"] is True
            assert db.is_email_unsubscribed("msg_004") is True

        # 2. Unsubscribe with HTTP exception / network error
        with patch("urllib.request.urlopen", side_effect=RuntimeError("Network offline")):
            res2 = mgr.unsubscribe_from_email(
                message_id="msg_005",
                url="https://retailbrand.com/unsubscribe?id=user984",
                unsub_type="http",
                sender="promotions@retailbrand.com",
                subject="Sale"
            )
            assert res2["status"] == "success"
            assert res2["unsubscribed"] is True
            assert res2["http_pinged"] is False
            assert db.is_email_unsubscribed("msg_005") is True

        # 3. Unsubscribe with live Gmail service connected
        mock_svc = MagicMock()
        mgr.service = mock_svc
        mgr.is_connected = True
        mgr.label_ids = {4: "lbl_ignore"}

        res3 = mgr.unsubscribe_from_email(
            message_id="msg_live",
            url=None,
            unsub_type="mailto",
            sender="spam@promo.com",
            subject="Spam"
        )
        assert res3["status"] == "success"
        mock_svc.users().messages().batchModify.assert_called_with(
            userId="me",
            body={
                "ids": ["msg_live"],
                "addLabelIds": ["lbl_ignore"],
                "removeLabelIds": ["INBOX"]
            }
        )

        # 4. Unsubscribe error branch in batchModify
        mock_svc.users().messages().batchModify.side_effect = RuntimeError("API rate limit")
        res4 = mgr.unsubscribe_from_email(message_id="msg_err", sender="err@promo.com")
        assert res4["status"] == "success"
        mock_svc.users().messages().batchModify.side_effect = None

        # 5. Check mock sample emails include unsubscribe metadata
        mock_emails = mgr._get_mock_sample_emails()
        gh_item = next(e for e in mock_emails if e["id"] == "msg_004")
        assert gh_item["can_unsubscribe"] is True
        assert gh_item["unsubscribed"] is True

        cal_item = next(e for e in mock_emails if e["id"] == "msg_001")
        assert cal_item["can_unsubscribe"] is False
        assert cal_item["unsubscribed"] is False


def test_fetch_real_emails_error_handling():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test_fetch_err.db")
        mgr = GmailManager(db=db)

        # 1. service is None
        mgr.service = None
        emails = mgr._fetch_real_emails("after:2026/01/01")
        assert len(emails) > 0

        # 2. list().execute() raises Exception
        mock_svc = MagicMock()
        mock_svc.users().messages().list.side_effect = RuntimeError("Quota exceeded")
        mgr.service = mock_svc
        mgr.is_connected = True
        emails_err = mgr._fetch_real_emails("after:2026/01/01")
        assert len(emails_err) > 0
        assert mgr.is_connected is False


def test_get_email_full_body():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test_body.db")
        mgr = GmailManager(db=db)

        # 1. Mock sample email body retrieval
        res_mock = mgr.get_email_full_body("msg_001")
        assert res_mock["id"] == "msg_001"
        assert "Roadmap Sync" in res_mock["body"]
        assert "subject" in res_mock

        # 2. Live connected service with decoded base64 body
        mock_svc = MagicMock()
        mgr.service = mock_svc
        mgr.is_connected = True

        import base64
        sample_b64 = base64.urlsafe_b64encode(b"Hello from decoded email body!").decode("utf-8")
        mock_svc.users().messages().get().execute.return_value = {
            "id": "msg_live_99",
            "snippet": "Live snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Live Test Subject"},
                    {"name": "From", "value": "tester@domain.com"}
                ],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": sample_b64}}
                ]
            }
        }
        res_live = mgr.get_email_full_body("msg_live_99")
        assert res_live["id"] == "msg_live_99"
        assert res_live["body"] == "Hello from decoded email body!"
        assert res_live["subject"] == "Live Test Subject"

        # 3. Live connected service with payload body (non-multipart)
        mock_svc.users().messages().get().execute.return_value = {
            "id": "msg_live_single",
            "snippet": "Single body",
            "payload": {
                "headers": [],
                "body": {"data": sample_b64}
            }
        }
        res_single = mgr.get_email_full_body("msg_live_single")
        assert res_single["body"] == "Hello from decoded email body!"

        # 4. Error during get().execute()
        mock_svc.users().messages().get().execute.side_effect = RuntimeError("Network error")
        res_err = mgr.get_email_full_body("msg_err_fetch")
        assert res_err["body"] == ""
        assert "error" in res_err

        # 5. Non-existent and offline fallback
        mgr.is_connected = False
        mgr.service = None
        res_none = mgr.get_email_full_body("non_existent_id")
        assert "not available" in res_none["body"]


def test_incremental_caching_and_known_ids():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "test_cache.db")
        mgr = GmailManager(db=db)

        # 1. Initial mock sync populates DB cache
        res1 = mgr.sync_and_classify(dry_run=True, force_refresh=False)
        assert res1["status"] == "success"
        assert res1["total_processed"] > 0
        known = db.get_known_email_ids()
        assert len(known) > 0

        # 2. Second mock sync with force_refresh=False uses cache
        res2 = mgr.sync_and_classify(dry_run=True, force_refresh=False)
        assert res2["status"] == "success"
        assert res2.get("cached") is True
        assert res2["total_processed"] == res1["total_processed"]

        # 3. Force refresh re-runs
        res3 = mgr.sync_and_classify(dry_run=True, force_refresh=True)
        assert res3["status"] == "success"

        # 4. Cached full body retrieval
        cached_body = mgr.get_email_full_body("msg_001")
        assert cached_body["id"] == "msg_001"
        assert len(cached_body["body"]) > 0

        # 5. Incremental _fetch_real_emails with known_ids
        mock_service = MagicMock()
        mgr.service = mock_service
        mgr.is_connected = True

        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg_001"}, {"id": "msg_new_999"}]
        }
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg_new_999",
            "snippet": "New unread email",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "New message"},
                    {"name": "From", "value": "sender@test.com"}
                ]
            }
        }

        # Passing known_ids = {"msg_001"} should ONLY fetch msg_new_999
        mock_service.users().messages().get.reset_mock()
        fetched = mgr._fetch_real_emails("query", known_ids={"msg_001"})
        assert len(fetched) == 1
        assert fetched[0]["id"] == "msg_new_999"
        # get() was only called once, NOT for msg_001!
        assert mock_service.users().messages().get.call_count == 1

        # 6. Live connected sync_and_classify branches (incremental vs force_refresh)
        mgr.label_ids = {0: "lbl_0", 1: "lbl_1", 2: "lbl_2", 3: "lbl_3", 4: "lbl_4"}
        res_live_inc = mgr.sync_and_classify(dry_run=False, force_refresh=False)
        assert res_live_inc["status"] == "success"

        res_live_force = mgr.sync_and_classify(dry_run=False, force_refresh=True)
        assert res_live_force["status"] == "success"





