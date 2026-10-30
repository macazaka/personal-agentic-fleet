"""Unit tests for fleet.core.database."""
import tempfile
from pathlib import Path
from fleet.core.database import FleetDatabase


def test_database_lifecycle():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_db.db"
        db = FleetDatabase(db_path=db_path)

        # 1. Task Operations
        task_id = db.add_task(
            title="Deploy release v1.0",
            description="Production deployment",
            priority="P1",
            due_date="2026-10-15",
            assigned_agent="DeployAgent"
        )
        assert task_id == 1

        task2 = db.add_task(title="Low priority item", description="Low priority task details", priority="P3")
        assert task2 == 2

        # Task with empty description for testing require_description filter
        task_empty_desc = db.add_task(title="Empty desc task", description="", priority="P2")

        # List pending tasks with description required by default
        pending = db.list_tasks(status="pending")
        assert len(pending) == 2
        assert pending[0]["id"] == 1  # P1 comes before P3
        assert all(t["id"] != task_empty_desc for t in pending)

        # List all tasks with require_description=False includes empty desc
        raw_pending = db.list_tasks(status="pending", require_description=False)
        assert len(raw_pending) == 3

        # List all tasks (require_description=True by default)
        all_tasks = db.list_tasks()
        assert len(all_tasks) == 2
        db.delete_task(task_empty_desc)

        # Update task status
        ok = db.update_task_status(task_id, "completed")
        assert ok is True
        bad = db.update_task_status(999, "completed")
        assert bad is False

        # Filter completed
        completed = db.list_tasks(status="completed")
        assert len(completed) == 1
        assert completed[0]["id"] == task_id

        # Delete task
        del_ok = db.delete_task(task2)
        assert del_ok is True
        del_bad = db.delete_task(999)
        assert del_bad is False
        assert len(db.list_tasks()) == 1

        # 2. Memory Operations
        db.set_memory("preferences", "theme", "dark")
        db.set_memory("preferences", "theme", "neon_dark")  # Upsert
        val = db.get_memory("theme")
        assert val == "neon_dark"
        assert db.get_memory("non_existent") is None

        mems = db.list_memories(category="preferences")
        assert len(mems) == 1
        assert mems[0]["key"] == "theme"

        all_mems = db.list_memories()
        assert len(all_mems) == 1

        # 3. Activity Logging
        db.log_activity("Tester", "action_1", "Ran test")
        db.log_activity("Tester", "action_2", "Passed test")
        logs = db.get_recent_activities(limit=5)
        assert len(logs) >= 2

        # 4. Notes
        note_id = db.add_note(title="Meeting Notes", content="Discussed roadmap", tags="meeting,q4")
        assert note_id == 1
        notes = db.list_notes(limit=5)
        assert len(notes) == 1
        assert notes[0]["title"] == "Meeting Notes"

        search_res = db.search_notes("roadmap")
        assert len(search_res) == 1
        assert db.search_notes("unrelated_query") == []

        # 5. Routines
        routines = db.list_routines()
        assert len(routines) == 5  # Default seeded
        assert routines[0]["completed_today"] is False

        r_id = routines[0]["id"]
        toggled = db.toggle_routine(r_id)
        assert toggled is True

        routines_after = db.list_routines()
        r_updated = next(r for r in routines_after if r["id"] == r_id)
        assert r_updated["completed_today"] is True

        # Toggle back
        untoggled = db.toggle_routine(r_id)
        assert untoggled is True
        assert db.toggle_routine(999) is False

        # Add new routine
        new_r = db.add_routine("Evening Yoga", "21:00", "wellness")
        assert new_r > 0
        assert len(db.list_routines()) == 6

        # 6. Test Runs Tracking
        assert db.get_latest_test_run() is None
        run_id = db.save_test_run(
            total_tests=50,
            passed_tests=50,
            failed_tests=0,
            pass_pct=100.0,
            coverage_pct=98.5,
            duration_sec=1.1,
            status="PASS",
            details_json='{"status": "PASS"}'
        )
        assert run_id == 1
        latest = db.get_latest_test_run()
        assert latest is not None
        assert latest["pass_pct"] == 100.0
        assert latest["coverage_pct"] == 98.5

        runs_list = db.list_test_runs(limit=5)
        assert len(runs_list) == 1

        # 7. Settings
        assert db.get_setting("custom_key", "default_val") == "default_val"
        db.set_setting("custom_key", "new_val")
        assert db.get_setting("custom_key") == "new_val"
        db.set_setting("custom_key", "updated_val")
        assert db.get_setting("custom_key") == "updated_val"

        # 8. Chat Queue
        assert db.get_queued_chat_messages() == []
        assert db.get_next_queued_chat_message() is None

        q1 = db.enqueue_chat_message(prompt="Analyze this code", images=["img1.png", "img2.png"], model="claude-opus-5-5-medium")
        assert q1 > 0
        q2 = db.enqueue_chat_message(prompt="Second message", images=[], model="gemini-3.8-flash-high")
        assert q2 > q1

        queued = db.get_queued_chat_messages()
        assert len(queued) == 2
        assert queued[0]["id"] == q1
        assert queued[0]["images"] == ["img1.png", "img2.png"]
        assert queued[0]["model"] == "claude-opus-5-5-medium"

        next_msg = db.get_next_queued_chat_message()
        assert next_msg is not None
        assert next_msg["id"] == q1

        # Update status
        up_ok = db.update_chat_queue_status(q1, "processing")
        assert up_ok is True
        assert len(db.get_queued_chat_messages()) == 1

        up_done = db.update_chat_queue_status(q1, "completed")
        assert up_done is True

        # Cancel remaining message
        canc_ok = db.cancel_queued_chat_message(q2)
        assert canc_ok is True
        assert db.cancel_queued_chat_message(999) is False
        assert db.get_queued_chat_messages() == []

        # 9. Feature Backlog Operations
        backlog_items = db.list_feature_backlog_items()
        assert len(backlog_items) == 5  # Pre-seeded default backlog
        stats = db.get_feature_backlog_stats()
        assert stats["total"] == 5

        # Add item
        b_id = db.add_feature_backlog_item(
            title="Export Activity to PDF",
            description="Generate monthly PDF reports of all fleet activity.",
            category="Integration",
            priority="P1",
            status="Planned",
            target_version="v1.4.0"
        )
        assert b_id > 0
        assert len(db.list_feature_backlog_items()) == 6

        # Filters
        p1_items = db.list_feature_backlog_items(category="Integration")
        assert len(p1_items) >= 1

        v14_items = db.list_feature_backlog_items(target_version="v1.4.0")
        assert len(v14_items) >= 1

        planned_items = db.list_feature_backlog_items(status="Planned")
        assert len(planned_items) >= 1

        all_items = db.list_feature_backlog_items(status="ALL", category="ALL", target_version="ALL")
        assert len(all_items) == 6

        # Update item
        up_b = db.update_feature_backlog_item(b_id, status="In Progress", priority="P1")
        assert up_b is True
        up_bad = db.update_feature_backlog_item(b_id, invalid_field="x")
        assert up_bad is False

        # Delete item
        del_b = db.delete_feature_backlog_item(b_id)
        assert del_b is True
        del_b_bad = db.delete_feature_backlog_item(9999)
        assert del_b_bad is False
        assert len(db.list_feature_backlog_items()) == 5

        # 10. Unsubscribed Emails Operations
        assert db.is_email_unsubscribed("msg_unsub_1") is False
        row_id1 = db.record_unsubscribed_email(
            message_id="msg_unsub_1",
            sender="news@deals.com",
            subject="50% Off Everything",
            unsubscribe_url="https://deals.com/unsub?id=123"
        )
        assert row_id1 > 0
        assert db.is_email_unsubscribed("msg_unsub_1") is True

        # Test conflict update
        row_id1_up = db.record_unsubscribed_email(
            message_id="msg_unsub_1",
            sender="news_updated@deals.com",
            subject="Updated deals",
            unsubscribe_url="https://deals.com/unsub?id=999"
        )
        assert db.is_email_unsubscribed("msg_unsub_1") is True

        unsub_list = db.list_unsubscribed_emails()
        assert len(unsub_list) == 1
        assert unsub_list[0]["message_id"] == "msg_unsub_1"
        assert unsub_list[0]["sender"] == "news_updated@deals.com"

        # 11. Token Preservation Vault Operations
        assert db.get_vaulted_prompts() == []
        assert db.get_latest_token_vault_event() is None

        # Enqueue 2 prompts to test vaulting
        q_v1 = db.enqueue_chat_message(prompt="Work to vault 1", model="gemini-3.8-flash-high")
        q_v2 = db.enqueue_chat_message(prompt="Work to vault 2", model="gemini-3.8-flash-high")
        assert len(db.get_queued_chat_messages()) == 2

        # Vault pending prompts
        vaulted_count = db.vault_pending_prompts(
            session_id="test_sess",
            model="gemini-3.8-flash-high",
            tokens_used=1000000,
            token_limit=1000000,
            reason="Exceeded context quota"
        )
        assert vaulted_count == 2
        assert db.get_queued_chat_messages() == []
        vaulted_items = db.get_vaulted_prompts()
        assert len(vaulted_items) == 2
        assert vaulted_items[0]["status"] == "vaulted"

        event = db.get_latest_token_vault_event()
        assert event is not None
        assert event["model"] == "gemini-3.8-flash-high"
        assert event["reason"] == "Exceeded context quota"

        # Resume vaulted prompts with fallback model
        resumed_count = db.resume_vaulted_prompts(fallback_model="gemini-3.8-flash")
        assert resumed_count == 2
        assert db.get_vaulted_prompts() == []
        queued_resumed = db.get_queued_chat_messages()
        assert len(queued_resumed) == 2
        assert queued_resumed[0]["model"] == "gemini-3.8-flash"
        assert queued_resumed[0]["status"] == "queued"

        # Resume vaulted prompts without fallback model (retains current model)
        db.vault_pending_prompts("Quota", "gemini-3.8-flash-high")
        resumed_same_model = db.resume_vaulted_prompts(fallback_model=None)
        assert resumed_same_model >= 1

        # Corrupted JSON branches in token vault & queue
        with db._get_connection() as conn:
            conn.execute("INSERT INTO chat_queue (prompt, model, status, images_json, created_at, updated_at) VALUES ('bad json', 'flash', 'vaulted', 'invalid-json', '2026-10-14', '2026-10-14')")
            conn.execute("INSERT INTO token_preservation_vault (session_id, reason, model, preserved_prompts_json, status, created_at) VALUES ('sess_corrupt', 'test', 'flash', 'invalid-json', 'active', '2026-10-14')")
            conn.commit()
        vaulted_items = db.get_vaulted_prompts()
        assert any(v["images"] == [] for v in vaulted_items)
        latest_event = db.get_latest_token_vault_event()
        assert latest_event is not None
        assert latest_event["preserved_prompts"] == []

        # 12. Parallel queue retrieval (get_next_n_queued_chat_messages)
        next_two = db.get_next_n_queued_chat_messages(limit=2)
        assert len(next_two) == 2
        next_one = db.get_next_n_queued_chat_messages(limit=1)
        assert len(next_one) == 1
        assert next_one[0]["id"] == next_two[0]["id"]


def test_database_test_isolation():
    from fleet.config import DB_PATH, TEST_DB_PATH
    from fleet.core.database import is_test_environment, get_effective_db_path, FleetDatabase
    from unittest.mock import patch

    # 1. Test environment detection
    assert is_test_environment() is True

    # 2. Path routing under test mode
    eff = get_effective_db_path()
    assert eff == TEST_DB_PATH
    assert eff != DB_PATH

    # 3. Path routing when not in test mode
    with patch("fleet.core.database.is_test_environment", return_value=False):
        assert get_effective_db_path() == DB_PATH

    # 4. Custom path is preserved
    custom = Path("my_custom.db")
    assert get_effective_db_path(custom) == custom

    # 5. FleetDatabase with default path routes to TEST_DB_PATH under test mode
    test_db = FleetDatabase()
    assert test_db.db_path == TEST_DB_PATH

    # 6. Hard Firewall: Even explicitly passing DB_PATH during tests redirects to TEST_DB_PATH
    assert get_effective_db_path(DB_PATH) == TEST_DB_PATH
    explicit_prod_db = FleetDatabase(db_path=DB_PATH)
    assert explicit_prod_db.db_path == TEST_DB_PATH

    # 7. Connection pool firewall redirects DB_PATH to TEST_DB_PATH in test mode
    from fleet.core.db.pool import pool
    conn = pool.get_connection(DB_PATH)
    assert conn is not None
    assert getattr(pool._local, "db_path", None) == TEST_DB_PATH.resolve()

    # 8. AgentRegistry and FleetScheduler isolate overrides and custom_agents under test_user
    from fleet.core.registry import AgentRegistry
    from fleet.core.scheduler import FleetScheduler
    reg = AgentRegistry()
    assert "test_user" in str(reg.custom_agents_dir)
    assert "test_user" in str(reg._get_overrides_file())
    sched = FleetScheduler()
    assert "test_user" in str(sched._get_overrides_file())


def test_email_caching_and_health_operations():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db = FleetDatabase(db_path=Path(tmpdir) / "health_test.db")

        # 1. Email Caching Operations
        assert db.save_classified_emails([]) == 0
        emails = [
            {
                "id": "msg_c1",
                "subject": "Q3 Roadmap Sync",
                "from": "pm@team.com",
                "snippet": "Agenda details attached",
                "body": "Hi, here is the full roadmap details...",
                "category_id": 0,
                "category_name": "Meetings",
                "reason": "Calendar invite",
                "can_unsubscribe": False
            },
            {
                "id": "msg_c2",
                "subject": "Clearance Sale 50% Off",
                "from": "promo@store.com",
                "snippet": "Biggest sale of the year",
                "body": "Shop now for 50% discount",
                "category_id": 4,
                "category_name": "Ignore",
                "reason": "Marketing promo",
                "can_unsubscribe": True,
                "unsubscribe_url": "https://store.com/unsub"
            }
        ]
        saved = db.save_classified_emails(emails)
        assert saved == 2

        known = db.get_known_email_ids()
        assert "msg_c1" in known
        assert "msg_c2" in known

        cached_all = db.get_classified_emails()
        assert len(cached_all) == 2

        cached_meetings = db.get_classified_emails(category_name="Meetings")
        assert len(cached_meetings) == 1
        assert cached_meetings[0]["id"] == "msg_c1"

        body_data = db.get_cached_email_body("msg_c1")
        assert body_data is not None
        assert "full roadmap details" in body_data["body"]
        assert db.get_cached_email_body("non_existent") is None

        # Test empty msg_id skips cleanly
        assert db.save_classified_emails([{"id": "", "subject": "No id"}]) == 0

        # Test unsubscription update
        assert db.update_email_unsubscribed("msg_c2") is True
        assert db.update_email_unsubscribed("unknown_id") is False
        updated_c2 = db.get_cached_email_body("msg_c2")
        assert updated_c2["unsubscribed"] is True

        # 2. Hydration Tracking Operations
        hyd_today = db.get_today_hydration()
        assert hyd_today["glasses"] == 0
        assert hyd_today["percentage"] == 0.0

        # Log intake for brand new date (row does not exist yet)
        logged_new = db.log_water_intake(glasses_delta=1, amount_delta_ml=250, target_date="2027-01-01")
        assert logged_new["glasses"] == 1
        assert logged_new["amount_ml"] == 250

        # Test invalid date string in last_drank_at (handles exception cleanly)
        with db._get_connection() as conn:
            conn.execute("UPDATE hydration_logs SET last_drank_at = 'invalid-iso' WHERE date = '2027-01-01'")
            conn.commit()
        hyd_invalid = db.get_today_hydration(target_date="2027-01-01")
        assert hyd_invalid["glasses"] == 1

        # Log intake
        logged = db.log_water_intake(glasses_delta=1, amount_delta_ml=250)
        assert logged["glasses"] == 1
        assert logged["amount_ml"] == 250
        assert logged["percentage"] > 0
        assert logged["last_drank_at"] != ""

        # Log another glass
        logged2 = db.log_water_intake(glasses_delta=2, amount_delta_ml=500)
        assert logged2["glasses"] == 3
        assert logged2["amount_ml"] == 750

        # Decrement (undo)
        logged_undo = db.log_water_intake(glasses_delta=-1, amount_delta_ml=-250)
        assert logged_undo["glasses"] == 2
        assert logged_undo["amount_ml"] == 500

        # Update goal
        goal_res = db.set_hydration_goal(goal_ml=3000)
        assert goal_res["goal_ml"] == 3000

        # 3. Medications Operations
        default_meds = db.list_medications()
        assert len(default_meds) >= 3  # Seeded default meds
        first_med_id = default_meds[0]["id"]

        # Add custom medication
        new_med_id = db.add_medication(
            name="CoQ10 200mg",
            dosage="1 softgel",
            schedule_time="10:00",
            frequency="Daily",
            instructions="Take with healthy fats"
        )
        assert new_med_id > 0
        meds_after_add = db.list_medications()
        assert any(m["id"] == new_med_id for m in meds_after_add)

        # Toggle taken today
        now_taken = db.toggle_medication_today(new_med_id)
        assert now_taken is True
        meds_taken = db.list_medications()
        assert next(m for m in meds_taken if m["id"] == new_med_id)["taken_today"] is True

        # Toggle back (unmark)
        unmarked = db.toggle_medication_today(new_med_id)
        assert unmarked is False
        meds_unmarked = db.list_medications()
        assert next(m for m in meds_unmarked if m["id"] == new_med_id)["taken_today"] is False

        # Update medication frequency and dosage
        upd_ok = db.update_medication(new_med_id, frequency="Monthly", dosage="1000mg")
        assert upd_ok is True
        meds_updated = db.list_medications()
        updated_item = next(m for m in meds_updated if m["id"] == new_med_id)
        assert updated_item["frequency"] == "Monthly"
        assert updated_item["dosage"] == "1000mg"

        # Delete medication
        del_med = db.delete_medication(new_med_id)
        assert del_med is True
        meds_active = db.list_medications()
        assert all(m["id"] != new_med_id for m in meds_active)

        # 4. Health Metrics & Trends Operations
        metric_id = db.log_health_metric(metric_type="weight_kg", value=72.5, unit="kg", notes="Morning weight")
        assert metric_id > 0

        trends = db.get_health_trends(metric_type="weight_kg", days=7)
        assert len(trends) > 0
        assert any(t["value"] == 72.5 for t in trends)

        # 5. Dashboard Summary
        summary = db.get_health_dashboard_summary()
        assert "hydration" in summary
        assert "medications" in summary
        assert "latest_vitals" in summary
        assert "trends" in summary
        assert summary["hydration"]["glasses"] == 2


