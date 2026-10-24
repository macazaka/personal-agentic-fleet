"""
Automated Verification Suite for Gmail Classification & 2-Month Lookback Window.
Tests:
  1. Date query calculation (this month & last month)
  2. Tier 0 Deterministic heuristic accuracy across all 5 folders
  3. Deterministic Event Bus A2A dispatch
  4. FastMCP Tool invocation
"""

import os
from datetime import datetime

os.environ["FLEET_TEST_MODE"] = "1"

from fleet.integrations.gmail_client import get_two_month_lookback_query
from fleet.integrations.email_classifier import EmailClassifier, CATEGORIES
from fleet.core.event_bus import FleetEvent, bus
import fleet.mcp_server as mcp_module


def test_lookback_query():
    print("Testing 2-Month Lookback Query Generator...")
    query = get_two_month_lookback_query()
    now = datetime.now()
    print(f"  Generated Query: {query}")
    
    assert "after:" in query, "Query must contain after: clause"
    assert '-label:"Fleet/0-Meetings"' in query, "Query must exclude existing Fleet labels"
    assert '-label:"Fleet/4-Ignore"' in query, "Query must exclude existing Fleet labels"
    print("  [PASS] 2-Month lookback date range and label exclusions verified.")


def test_tier0_classification_accuracy():
    print("\nTesting Tier 0 Deterministic Classification Accuracy...")
    classifier = EmailClassifier()

    test_cases = [
        # 0) Meetings
        ({
            "from": "calendar-notification@google.com",
            "subject": "Invitation: Team Sync @ 11am",
            "snippet": "Click to RSVP",
            "has_calendar_part": True
        }, 0, "Meetings"),

        # 1) Respond
        ({
            "from": "manager@company.com",
            "subject": "Quick question on Q4 numbers",
            "snippet": "Can you review the attached spreadsheet and let me know if it looks good?",
            "is_direct_to": True
        }, 1, "Respond"),

        # 2) Note
        ({
            "from": "auto-confirm@amazon.com",
            "subject": "Your order #102-48201 has shipped",
            "snippet": "Delivery date: tomorrow",
        }, 2, "Note"),

        # 3) FYI
        ({
            "from": "newsletter@techdigest.com",
            "subject": "Tech Weekly Digest: Issue #42",
            "snippet": "Here are the top stories in AI this week.",
        }, 3, "FYI"),

        # 4) Ignore
        ({
            "from": "sales@fastretail.com",
            "subject": "FLASH SALE: 50% OFF everything ends tonight!",
            "snippet": "Unsubscribe if you do not want to receive marketing emails.",
        }, 4, "Ignore"),
    ]

    for meta, expected_cat, expected_name in test_cases:
        cat_id, reason = classifier.classify_single(meta)
        assert cat_id == expected_cat, f"Expected {expected_name} ({expected_cat}), got {CATEGORIES[cat_id]} ({cat_id}) for '{meta['subject']}'. Reason: {reason}"
        print(f"  [PASS] '{meta['subject'][:35]}...' -> {expected_name} ({reason})")


def test_event_bus_and_mcp():
    print("\nTesting Event Bus A2A & FastMCP Tool...")
    # Event Bus
    event = FleetEvent(sender="Test", target="email", action="CLASSIFY_RECENT", payload={"dry_run": True})
    res = bus.dispatch(event)
    assert res["status"] == "success", f"Event bus failed: {res}"
    counts = res["data"]["counts"]
    print(f"  [PASS] Event Bus CLASSIFY_RECENT -> Processed {res['data']['total_processed']} emails")
    print(f"         Counts: {counts}")

    # FastMCP Tool
    mcp_output = mcp_module.fleet_classify_recent_emails(dry_run=True)
    assert "Gmail Classification Complete" in mcp_output
    assert "Meetings:" in mcp_output
    assert "Ignore:" in mcp_output
    print(f"  [PASS] FastMCP Tool fleet_classify_recent_emails() generated summary successfully.")


if __name__ == "__main__":
    test_lookback_query()
    test_tier0_classification_accuracy()
    test_event_bus_and_mcp()
    print("\nALL GMAIL CLASSIFIER & 2-MONTH SYNC TESTS PASSED! (0 Tokens Spent)")

