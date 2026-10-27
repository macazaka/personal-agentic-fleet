from __future__ import annotations
"""
Gmail Client & Automated Classifier Integration for Personal Agentic Fleet.
Manages OAuth2 desktop credentials, 2-month lookback window query,
folder labels (0-Meetings, 1-Respond, 2-Note, 3-FYI, 4-Ignore), and batch labeling.
Includes simulated mock mode if credentials.json is not yet provided.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fleet.config import DATA_DIR
from fleet.core.database import FleetDatabase
from fleet.integrations.email_classifier import (
    CATEGORIES,
    CATEGORY_LABEL_MAP,
    EmailClassifier,
)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def get_credentials_file() -> Path:
    """Automatically find credentials.json or any client_secret*.json in DATA_DIR."""
    standard = DATA_DIR / "credentials.json"
    if standard.exists():
        return standard
    client_secrets = sorted(DATA_DIR.glob("*client_secret*.json"))
    if client_secrets:
        return client_secrets[0]
    return standard

CREDENTIALS_FILE = get_credentials_file()
TOKEN_FILE = DATA_DIR / "gmail_token.json"



def get_two_month_lookback_query() -> str:
    """
    Computes query date starting from the 1st of the previous month.
    Excludes emails that already have one of our Fleet labels (incremental delta sync).
    """
    now = datetime.now()
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_this_month - timedelta(days=1)
    start_of_last_month = last_month_end.replace(day=1)
    date_str = start_of_last_month.strftime("%Y/%m/%d")

    # Incremental exclusion
    exclusions = " ".join([f'-label:"{label}"' for label in CATEGORY_LABEL_MAP.values()])
    return f"after:{date_str} {exclusions}"


def extract_unsubscribe_info(headers: Dict[str, str], snippet: str = "") -> Dict[str, Any]:
    """
    Extracts unsubscribe options from headers (List-Unsubscribe, List-Unsubscribe-Post)
    or body snippet per RFC 2369 / RFC 8058.
    """
    unsub_header = headers.get("list-unsubscribe", "")
    post_header = headers.get("list-unsubscribe-post", "")

    http_url = None
    mailto_url = None

    if unsub_header:
        http_matches = re.findall(r"<(https?://[^>]+)>", unsub_header)
        mailto_matches = re.findall(r"<(mailto:[^>]+)>", unsub_header)

        if http_matches:
            http_url = http_matches[0]
        if mailto_matches:
            mailto_url = mailto_matches[0]

    # If no header, check snippet for unsubscribe URL
    if not http_url and not mailto_url and snippet:
        snippet_links = re.findall(
            r"https?://[^\s<>'\"\)\]]+(?:unsubscribe|opt-out|optout|preferences)[^\s<>'\"\)\]]*",
            snippet,
            re.IGNORECASE
        )
        if snippet_links:
            http_url = snippet_links[0]

    if http_url:
        is_one_click = "list-unsubscribe=one-click" in post_header.lower()
        return {
            "can_unsubscribe": True,
            "unsubscribe_url": http_url,
            "unsubscribe_type": "one_click" if is_one_click else "http"
        }
    elif mailto_url:
        return {
            "can_unsubscribe": True,
            "unsubscribe_url": mailto_url,
            "unsubscribe_type": "mailto"
        }
    else:
        return {
            "can_unsubscribe": False,
            "unsubscribe_url": None,
            "unsubscribe_type": None
        }


class GmailManager:
    def __init__(self, db: Any = None):
        self.db: Any = db or FleetDatabase()
        self.classifier = EmailClassifier()
        self.service = None
        self.label_ids: Dict[int, str] = {}
        self.is_connected = False
        self._init_service()

    def _init_service(self):
        """Attempt to initialize the official Google API Gmail service."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            if os.environ.get("FLEET_TEST_MODE") == "1":
                # In test mode, strictly guard against live Google token refresh & network API calls
                from unittest.mock import Mock
                if not isinstance(getattr(Credentials, "from_authorized_user_file", None), Mock):
                    self.is_connected = False
                    return

            creds = None
            if TOKEN_FILE.exists():
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(TOKEN_FILE, "w") as token:
                        token.write(creds.to_json())

            if creds and creds.valid:
                self.service = build("gmail", "v1", credentials=creds)
                self.is_connected = True
                self._ensure_labels_exist()
        except Exception as e:
            self.is_connected = False
            # Silent fallback to mock mode

    def authenticate_interactive(self):
        """Called interactively by setup_gmail.py to open browser and authorize."""
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds_file = get_credentials_file()
        if not creds_file.exists():
            raise FileNotFoundError(f"Credentials file not found: {creds_file}")

        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        self.is_connected = True
        self._ensure_labels_exist()
        return creds

    def _ensure_labels_exist(self):
        """Ensure all 5 categorization labels exist in Gmail."""
        if not self.service:
            return
        try:
            existing_labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
            name_to_id = {l["name"]: l["id"] for l in existing_labels}

            for cat_id, label_name in CATEGORY_LABEL_MAP.items():
                if label_name in name_to_id:
                    self.label_ids[cat_id] = name_to_id[label_name]
                else:
                    new_label = self.service.users().labels().create(
                        userId="me",
                        body={
                            "name": label_name,
                            "labelListVisibility": "labelShow",
                            "messageListVisibility": "show"
                        }
                    ).execute()
                    self.label_ids[cat_id] = new_label["id"]
        except Exception as e:
            self.db.log_activity("GmailManager", "label_error", str(e))

    def sync_and_classify(self, dry_run: bool = False, auto_archive_ignore: bool = False,
                          force_refresh: bool = False) -> Dict[str, Any]:
        """
        Classifies all emails from this month and last month into the 5 folders.
        Caches classified emails in SQLite database (zero-token deterministic Tier 0).
        If force_refresh is False, loads directly from local database or only performs
        incremental diff fetching for newly arrived message IDs.
        """
        query = get_two_month_lookback_query()
        known_ids = self.db.get_known_email_ids()

        if not self.is_connected or not self.service:
            # Mock / disconnected mode
            if not force_refresh and known_ids:
                cached = self.db.get_classified_emails()
                if cached:
                    counts = {CATEGORIES[cid]: 0 for cid in CATEGORIES}
                    for item in cached:
                        cname = item.get("category_name", "Ignore")
                        counts[cname] = counts.get(cname, 0) + 1
                    return {
                        "status": "success",
                        "connected_to_live_gmail": False,
                        "dry_run": dry_run,
                        "query_used": query,
                        "total_processed": len(cached),
                        "counts": counts,
                        "classified_sample": cached[:10],
                        "tokens_used": 0,
                        "cost_usd": "$0.00",
                        "tier": "Tier 0 Deterministic ($0.00 / 0 Tokens)",
                        "cached": True
                    }

            raw_emails = self._get_mock_sample_emails()
            classified = self.classifier.classify_batch(raw_emails)
            self.db.save_classified_emails(classified)
        else:
            # Live connected Gmail mode
            if not force_refresh:
                new_raw_emails = self._fetch_real_emails(query, known_ids=known_ids)
                if new_raw_emails:
                    new_classified = self.classifier.classify_batch(new_raw_emails)
                    self.db.save_classified_emails(new_classified)
                    if not dry_run and self.is_connected and self.service:
                        self._apply_labels_to_gmail(new_classified, auto_archive_ignore)
                classified = self.db.get_classified_emails()
            else:
                raw_emails = self._fetch_real_emails(query, known_ids=set())
                classified = self.classifier.classify_batch(raw_emails)
                self.db.save_classified_emails(classified)
                if not dry_run and self.is_connected and self.service:
                    self._apply_labels_to_gmail(classified, auto_archive_ignore)

        # Count distribution
        counts = {CATEGORIES[cid]: 0 for cid in CATEGORIES}
        for item in classified:
            cname = item.get("category_name", "Ignore")
            counts[cname] = counts.get(cname, 0) + 1

        # Apply labels in Gmail if not dry run and connected and not cached
        applied_count = 0
        if not dry_run and self.is_connected and self.service and force_refresh:
            applied_count = self._apply_labels_to_gmail(classified, auto_archive_ignore)
        else:
            applied_count = len(classified)

        # Log action to database
        self.db.log_activity(
            "GmailManager",
            "classify_emails",
            f"Processed {len(classified)} emails (DryRun: {dry_run}, ForceRefresh: {force_refresh}). Meetings: {counts.get('Meetings', 0)}, Respond: {counts.get('Respond', 0)}, Note: {counts.get('Note', 0)}, FYI: {counts.get('FYI', 0)}, Ignore: {counts.get('Ignore', 0)}"
        )

        return {
            "status": "success",
            "connected_to_live_gmail": self.is_connected,
            "dry_run": dry_run,
            "query_used": query,
            "total_processed": len(classified),
            "counts": counts,
            "classified_sample": classified[:10],
            "tokens_used": 0,
            "cost_usd": "$0.00",
            "tier": "Tier 0 Deterministic ($0.00 / 0 Tokens)",
            "cached": not force_refresh
        }

    def _fetch_real_emails(self, query: str, max_results: int = 100,
                           known_ids: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Fetch email metadata headers from Gmail, skipping known cached IDs."""
        if not self.service:
            return self._get_mock_sample_emails()
        try:
            messages_result = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
        except Exception as e:
            self.db.log_activity("GmailManager", "fetch_error", str(e))
            self.is_connected = False
            return self._get_mock_sample_emails()

        messages = messages_result.get("messages", [])
        if known_ids is None:
            known_ids = set()
        email_list = []

        def _fetch_single_msg(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if not self.service:
                return None
            try:
                msg_data = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date", "Content-Type", "List-Unsubscribe", "List-Unsubscribe-Post"]
                ).execute()

                headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                unsub_info = extract_unsubscribe_info(headers, msg_data.get("snippet", ""))
                is_unsub = self.db.is_email_unsubscribed(msg["id"])

                return {
                    "id": msg["id"],
                    "subject": headers.get("subject", "(No Subject)"),
                    "from": headers.get("from", "Unknown"),
                    "snippet": msg_data.get("snippet", ""),
                    "body": msg_data.get("snippet", ""),
                    "mime_type": headers.get("content-type", ""),
                    "has_calendar_part": "text/calendar" in headers.get("content-type", ""),
                    "can_unsubscribe": unsub_info["can_unsubscribe"],
                    "unsubscribe_url": unsub_info["unsubscribe_url"],
                    "unsubscribe_type": unsub_info["unsubscribe_type"],
                    "unsubscribed": is_unsub
                }
            except Exception:
                return None

        for msg in messages:
            if msg.get("id") in known_ids:
                continue
            res = _fetch_single_msg(msg)
            if res:
                email_list.append(res)

        return email_list

    def _apply_labels_to_gmail(self, classified: List[Dict[str, Any]], auto_archive_ignore: bool) -> int:
        """Batch apply labels via Gmail API."""
        if not self.service:
            return 0
        grouped_by_cat: Dict[int, List[str]] = {cid: [] for cid in CATEGORIES}
        for item in classified:
            grouped_by_cat[item["category_id"]].append(item["id"])

        total_applied = 0
        for cat_id, msg_ids in grouped_by_cat.items():
            if not msg_ids:
                continue
            label_id = self.label_ids.get(cat_id)
            if not label_id:
                continue

            remove_labels = []
            if auto_archive_ignore and cat_id in (3, 4):  # Auto-archive FYI & Ignore if configured
                remove_labels.append("INBOX")

            body = {
                "ids": msg_ids,
                "addLabelIds": [label_id],
                "removeLabelIds": remove_labels
            }
            self.service.users().messages().batchModify(userId="me", body=body).execute()
            total_applied += len(msg_ids)

        return total_applied

    def unsubscribe_from_email(self, message_id: str, url: Optional[str] = None,
                               unsub_type: str = "http", sender: str = "",
                               subject: str = "") -> Dict[str, Any]:
        """
        Executes unsubscription via HTTP request or Mailto,
        labels the thread as Fleet/4-Ignore in live Gmail if connected,
        and records the unsubscription in FleetDatabase.
        """
        request_success = False
        if url and unsub_type in ("http", "one_click") and url.startswith("http"):
            try:
                import urllib.request
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PersonalFleet/1.4"}
                )
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    request_success = (200 <= resp.status < 400)
            except Exception:
                request_success = False

        if self.is_connected and self.service and message_id:
            try:
                ignore_label_id = self.label_ids.get(4)
                add_labels = [ignore_label_id] if ignore_label_id else []
                self.service.users().messages().batchModify(
                    userId="me",
                    body={
                        "ids": [message_id],
                        "addLabelIds": add_labels,
                        "removeLabelIds": ["INBOX"]
                    }
                ).execute()
            except Exception as e:
                self.db.log_activity("GmailManager", "unsubscribe_label_error", str(e))

        self.db.record_unsubscribed_email(message_id, sender, subject, url or "")
        self.db.log_activity(
            "GmailManager",
            "unsubscribe",
            f"Unsubscribed from {sender or message_id} ({subject[:30] if subject else ''})"
        )

        return {
            "status": "success",
            "message_id": message_id,
            "sender": sender,
            "url": url,
            "unsubscribed": True,
            "http_pinged": request_success
        }

    def _get_mock_sample_emails(self) -> List[Dict[str, Any]]:
        """Representative test dataset across this month and last month."""
        now = datetime.now()
        emails = [
            {
                "id": "msg_001",
                "from": "calendar-notification@google.com",
                "subject": "Invitation: Product Roadmap Sync @ Thu Oct 15, 2026 10am",
                "snippet": "You have been invited to Roadmap Sync. View invitation details and RSVP.",
                "body": (
                    "You have been invited to attend: Product Roadmap Sync\n\n"
                    "Time: Thursday, October 15, 2026 • 10:00 AM – 11:00 AM IST\n"
                    "Meeting Platform: Google Meet (https://meet.google.com/abc-road-sync)\n"
                    "Organizer: product-leads@company.com\n\n"
                    "Agenda Topics:\n"
                    "1. Review Q3 roadmap deliverables & milestone completion.\n"
                    "2. Fleet automation and Antigravity mirror integration status.\n"
                    "3. Open blockers and sprint planning.\n\n"
                    "Please reply with your RSVP (Yes / Maybe / No)."
                ),
                "mime_type": "text/calendar",
                "has_calendar_part": True,
                "can_unsubscribe": False,
                "unsubscribe_url": None,
                "unsubscribe_type": None
            },
            {
                "id": "msg_002",
                "from": "Sarah Chen <sarah.chen@company.com>",
                "subject": "Can you review the client proposal draft?",
                "snippet": "Hey, I attached the revised client proposal. Can you take a look and give me your thoughts by 4pm?",
                "body": (
                    "Hi,\n\n"
                    "I have finalized the draft for the ACME Corp enterprise client proposal.\n"
                    "Could you please take a look at the technical architecture section and pricing table?\n\n"
                    "Key points needing your sign-off:\n"
                    "- 99.9% uptime SLA commitments\n"
                    "- Resource sizing for the dedicated agent runner\n"
                    "- Milestone 1 delivery schedule (November 15)\n\n"
                    "If possible, please share your feedback by 4:00 PM today so we can send the final deck.\n\n"
                    "Thanks!\nSarah Chen\nSenior Solutions Architect"
                ),
                "is_direct_to": True,
                "can_unsubscribe": False,
                "unsubscribe_url": None,
                "unsubscribe_type": None
            },
            {
                "id": "msg_003",
                "from": "auto-confirm@amazon.com",
                "subject": "Your Order #112-9842189 has shipped",
                "snippet": "Your package containing USB-C Hub has shipped. Tracking number: 1Z99999999999.",
                "body": (
                    "Hello,\n\n"
                    "Your package has shipped and is on its way!\n\n"
                    "Order #112-9842189\n"
                    "Item: Anker 7-in-1 USB-C Hub with 4K HDMI & 100W Power Delivery\n"
                    "Quantity: 1\n"
                    "Carrier: Bluedart Express\n"
                    "Tracking ID: 1Z99999999999\n"
                    "Estimated Delivery: Tomorrow by 8:00 PM IST\n\n"
                    "Track your delivery status in your Amazon orders dashboard."
                ),
                "mime_type": "text/html",
                "can_unsubscribe": False,
                "unsubscribe_url": None,
                "unsubscribe_type": None
            },
            {
                "id": "msg_004",
                "from": "GitHub <notifications@github.com>",
                "subject": "[GitHub] Weekly Digest: 4 pull requests merged",
                "snippet": "Here is what happened in your repositories over the past week.",
                "body": (
                    "Here is your weekly activity digest across your repositories:\n\n"
                    "Merged Pull Requests (4):\n"
                    "- #104: feat: optimize PC cache cleaner and DNS flushing (merged by lead-dev)\n"
                    "- #108: fix: isolate SQLite test database from live fleet_memory (merged by qa-bot)\n"
                    "- #112: docs: update architectural diagrams and agent fleet rules (merged by lead-dev)\n"
                    "- #115: refactor: enforce zero-token deterministic email classifier (merged by lead-dev)\n\n"
                    "Active Issues: 2 issues awaiting review.\n\n"
                    "To modify your notification preferences, visit your GitHub account settings:\n"
                    "https://github.com/settings/notifications"
                ),
                "mime_type": "text/html",
                "can_unsubscribe": True,
                "unsubscribe_url": "https://github.com/settings/notifications",
                "unsubscribe_type": "http"
            },
            {
                "id": "msg_005",
                "from": "promotions@retailbrand.com",
                "subject": "FLASH SALE: 40% OFF everything this weekend only!",
                "snippet": "Shop our biggest clearance sale of the season. Don't miss out on these exclusive deals.",
                "body": (
                    "⚡ FLASH SALE: 40% OFF EVERYTHING! ⚡\n\n"
                    "Upgrade your workspace setup with our biggest seasonal discounts!\n"
                    "Save on ergonomic standing desks, mechanical keyboards, monitor arms, and accessories.\n\n"
                    "Use coupon code at checkout: FLEET40\n"
                    "Free express shipping on all domestic orders over ₹1,999.\n\n"
                    "Hurry! Sale ends this Sunday at 11:59 PM IST.\n\n"
                    "--------------------------------------------------\n"
                    "You received this marketing email because you opted in at retailbrand.com.\n"
                    "If you no longer wish to receive promotional offers, unsubscribe here:\n"
                    "https://retailbrand.com/unsubscribe?id=user984"
                ),
                "mime_type": "text/html",
                "can_unsubscribe": True,
                "unsubscribe_url": "https://retailbrand.com/unsubscribe?id=user984",
                "unsubscribe_type": "http"
            },
            {
                "id": "msg_006",
                "from": "scheduling@calendly.com",
                "subject": "New Event: Intro Call with David",
                "snippet": "A new event has been scheduled for Friday at 2:00 PM via Calendly.",
                "body": (
                    "Hi,\n\n"
                    "A new meeting has been scheduled via your Calendly booking link.\n\n"
                    "Event: Intro & Fleet Discovery Call\n"
                    "Invitee: David Miller (david.miller@partnerfirm.io)\n"
                    "Date & Time: Friday, October 16, 2026 • 2:00 PM – 2:30 PM IST\n"
                    "Location: Google Meet (meet.google.com/xyz-intro-call)\n\n"
                    "Invitee Notes:\n"
                    "\"Looking forward to exploring agentic fleet workflows, proactive daily briefings, and offline PC optimization.\"\n\n"
                    "Need to reschedule or cancel? Visit https://calendly.com/resched/intro-david-123"
                ),
                "has_calendar_part": True,
                "can_unsubscribe": False,
                "unsubscribe_url": None,
                "unsubscribe_type": None
            },
            {
                "id": "msg_007",
                "from": "billing@stripe.com",
                "subject": "Receipt for your Cloud Hosting subscription",
                "snippet": "Thank you for your payment of $29.00. View your invoice and receipt here.",
                "body": (
                    "INVOICE & RECEIPT\n"
                    "Invoice Number: INV-2026-10-8941\n"
                    "Receipt Date: October 14, 2026\n"
                    "Customer: Personal Agentic Fleet Operations\n\n"
                    "Line Items:\n"
                    "- Pro Developer Cloud Hosting & Dedicated Runner (Monthly): $29.00\n"
                    "Subtotal: $29.00 USD\n"
                    "Tax: $0.00\n"
                    "Total Paid: $29.00 USD (Charged to Visa ending in 4242)\n\n"
                    "Your next billing cycle begins on November 14, 2026.\n"
                    "Download official PDF receipt: https://billing.stripe.com/invoice/inv_8941/pdf"
                ),
                "mime_type": "text/html",
                "can_unsubscribe": False,
                "unsubscribe_url": None,
                "unsubscribe_type": None
            }
        ]
        for em in emails:
            em["unsubscribed"] = self.db.is_email_unsubscribed(em["id"])
        return emails

    def get_email_full_body(self, message_id: str) -> Dict[str, Any]:
        """Retrieve full plain text or decoded body of a specific email, checking DB cache first."""
        cached = self.db.get_cached_email_body(message_id)
        if cached and cached.get("body"):
            return {
                "id": message_id,
                "subject": cached.get("subject", ""),
                "from": cached.get("from", ""),
                "snippet": cached.get("snippet", ""),
                "body": cached.get("body", ""),
                "can_unsubscribe": cached.get("can_unsubscribe", False),
                "unsubscribe_url": cached.get("unsubscribe_url"),
                "unsubscribed": cached.get("unsubscribed", False)
            }

        for em in self._get_mock_sample_emails():
            if em["id"] == message_id:
                return {
                    "id": message_id,
                    "subject": em.get("subject", ""),
                    "from": em.get("from", ""),
                    "snippet": em.get("snippet", ""),
                    "body": em.get("body") or em.get("snippet", ""),
                    "can_unsubscribe": em.get("can_unsubscribe", False),
                    "unsubscribe_url": em.get("unsubscribe_url"),
                    "unsubscribed": self.db.is_email_unsubscribed(message_id)
                }

        if self.is_connected and self.service:
            try:
                import base64
                msg = self.service.users().messages().get(
                    userId="me", id=message_id, format="full"
                ).execute()
                payload = msg.get("payload", {})
                headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
                body_text = ""
                parts = payload.get("parts", [])
                if not parts and "body" in payload and payload["body"].get("data"):
                    body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
                else:
                    for part in parts:
                        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                            body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                            break
                        elif part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
                            body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                if not body_text:
                    body_text = msg.get("snippet", "")
                unsub = extract_unsubscribe_info(headers, msg.get("snippet", ""))
                return {
                    "id": message_id,
                    "subject": headers.get("subject", "(No Subject)"),
                    "from": headers.get("from", "Unknown"),
                    "snippet": msg.get("snippet", ""),
                    "body": body_text,
                    "can_unsubscribe": unsub["can_unsubscribe"],
                    "unsubscribe_url": unsub["unsubscribe_url"],
                    "unsubscribed": self.db.is_email_unsubscribed(message_id)
                }
            except Exception as e:
                return {"id": message_id, "body": "", "error": str(e)}

        return {"id": message_id, "body": "Email body content is not available."}


# Singleton instance
gmail_manager = GmailManager()


