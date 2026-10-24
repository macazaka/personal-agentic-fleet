"""Unit tests for fleet.core.briefing."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from fleet.core.briefing import BriefingEngine
from fleet.core.database import FleetDatabase


def test_briefing_engine_scenarios():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_db.db"
        db = FleetDatabase(db_path=db_path)
        engine = BriefingEngine(db)

        # Scenario 1: Empty tasks
        with patch("fleet.core.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 9, 30)  # Morning
            b = engine.generate_daily_briefing()
            assert b["greeting"] == "Good Morning"
            assert "board is clear" in b["headline"]
            assert b["summary_stats"]["total_tasks"] == 0

        # Scenario 2: Afternoon with non-P1 tasks
        db.add_task("Clean desk", description="Tidy up home office desk", priority="P2")
        db.add_task("Buy groceries", description="Weekly grocery shopping run", priority="P3")
        with patch("fleet.core.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 14, 15)  # Afternoon
            b = engine.generate_daily_briefing()
            assert b["greeting"] == "Good Afternoon"
            assert "2 open tasks" in b["headline"]
            assert len(b["top_focus"]) == 2

        # Scenario 3: Evening with multiple P1 tasks
        db.add_task("Submit Tax Return", description="File annual tax return", priority="P1")
        db.add_task("Urgent Security Patch", description="Apply critical security patch", priority="P1")
        with patch("fleet.core.briefing.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 10, 13, 21, 0)  # Evening
            b = engine.generate_daily_briefing()
            assert b["greeting"] == "Good Evening"
            assert "2 high-priority goals" in b["headline"]
            assert len(b["top_focus"]) == 3
            assert b["top_focus"][0]["priority"] == "P1"
            assert "Submit Tax Return" in b["briefing_markdown"]
            assert "upcoming_meetings" in b

        # Scenario 4: Exception during meeting fetch falls back safely
        with patch("fleet.integrations.gmail_client.gmail_manager.sync_and_classify", side_effect=RuntimeError("Offline")):
            b_fallback = engine.generate_daily_briefing()
            assert b_fallback["upcoming_meetings"] == []


def test_extract_meeting_agenda():
    from fleet.core.briefing import extract_meeting_agenda

    # 1. Google Meet & Roadmap sync
    m1 = extract_meeting_agenda(
        "Invitation: Product Roadmap Sync @ Thu Oct 15, 2026 10am",
        snippet="Join via Google Meet: meet.google.com/abc-xyz",
        sender="pm@company.com"
    )
    assert m1["platform"] == "Google Meet"
    assert "Roadmap Sync" in m1["title"]
    assert any("roadmap milestones" in p.lower() for p in m1["prep_notes"])

    # 2. Zoom & Client proposal
    m2 = extract_meeting_agenda(
        "Client Proposal Review and Pitch",
        snippet="Zoom link: zoom.us/j/12345",
        sender="sales@client.com"
    )
    assert m2["platform"] == "Zoom"
    assert any("proposal draft" in p.lower() for p in m2["prep_notes"])

    # 3. Microsoft Teams & 1:1
    m3 = extract_meeting_agenda(
        "Intro 1:1 Call with Sarah",
        snippet="Join Microsoft Teams Meeting teams.microsoft.com",
        sender="sarah@corp.com"
    )
    assert m3["platform"] == "Microsoft Teams"
    assert any("discussion topics" in p.lower() for p in m3["prep_notes"])

    # 4. Calendly & General
    m4 = extract_meeting_agenda(
        "Casual catch up",
        snippet="Scheduled via calendly.com",
        sender="contact@external.org"
    )
    assert m4["platform"] == "Calendly"
    assert any("deliverables" in p.lower() for p in m4["prep_notes"])

