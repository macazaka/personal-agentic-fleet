"""
Base database connection & schema management for Personal Agentic Fleet.
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fleet.config import DATA_DIR, DB_PATH, TEST_DB_PATH

logger = logging.getLogger("fleet.core.db")


def is_test_environment() -> bool:
    """Detects whether code is executing within a test runner or pytest environment."""
    return (
        os.environ.get("FLEET_TEST_MODE") == "1"
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def get_effective_db_path(custom_path: Optional[Path] = None) -> Path:
    """Returns the effective SQLite database path, strictly isolating test runs from production."""
    # Production Workstation Control Center server is strictly bound to production database
    if os.environ.get("FLEET_PRODUCTION_SERVER") == "1":
        return custom_path or DB_PATH

    if custom_path is not None:
        return custom_path

    db_module = sys.modules.get("fleet.core.database")
    check_fn = getattr(db_module, "is_test_environment", is_test_environment) if db_module else is_test_environment
    if check_fn():
        return TEST_DB_PATH
    return DB_PATH


class BaseDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        self._custom_db_path = db_path
        self.db_path = get_effective_db_path(db_path)
        self._init_db()

    def log_activity(self, agent: str, action: str, details: str = "") -> None:
        """Stub for activity logging, implemented by SystemMixin in FleetDatabase."""
        pass

    def _get_connection(self) -> sqlite3.Connection:
        from fleet.core.db.pool import get_pooled_connection
        effective = get_effective_db_path(self._custom_db_path)
        self.db_path = effective
        conn = get_pooled_connection(self.db_path, timeout=10.0)
        # Self-healing schema: auto-create tables if missing
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='hydration_logs'")
        if not cursor.fetchone():
            self._create_schema(conn)
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            pass
        try:
            from fleet.core.db.migrations import apply_migrations
            apply_migrations(self.db_path)
        except Exception as e:
            logger.warning("Database migration non-fatal warning on %s: %s", self.db_path, e, exc_info=True)
    def _create_schema(self, conn: sqlite3.Connection):
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except Exception:
            pass
        with conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    source TEXT DEFAULT 'Manual',
                    priority TEXT DEFAULT 'P2',
                    status TEXT DEFAULT 'pending',
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    assigned_agent TEXT DEFAULT 'AgendaAgent'
                )
            """)

            # Auto-migrate tasks table for source column if missing
            try:
                cursor.execute("PRAGMA table_info(tasks)")
                task_cols = [row["name"] for row in cursor.fetchall()]
                if "source" not in task_cols:
                    cursor.execute("ALTER TABLE tasks ADD COLUMN source TEXT DEFAULT 'Manual'")
            except Exception:
                pass

            # User & Agent Memories (Personal preferences, habits, facts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Activity Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Notes / Second Brain table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Daily Routines & Habits table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS routines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    time_target TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    last_completed_date TEXT DEFAULT ''
                )
            """)

            # Seed default daily routines if empty
            cursor.execute("SELECT COUNT(*) as count FROM routines")
            if cursor.fetchone()["count"] == 0:
                default_routines = [
                    ("Morning Review & Coffee", "08:30", "morning"),
                    ("Deep Focus Work Session", "10:00", "focus"),
                    ("Lunch & Screen Break", "13:00", "wellness"),
                    ("Afternoon Task Sprint", "15:30", "focus"),
                    ("Evening Wrap-Up & Planning", "20:00", "evening"),
                ]
                cursor.executemany("""
                    INSERT INTO routines (title, time_target, category, last_completed_date)
                    VALUES (?, ?, ?, '')
                """, default_routines)

            # Automated Test Runs tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_tests INTEGER NOT NULL,
                    passed_tests INTEGER NOT NULL,
                    failed_tests INTEGER NOT NULL,
                    pass_pct REAL NOT NULL,
                    coverage_pct REAL NOT NULL,
                    duration_sec REAL NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}'
                )
            """)

            # Settings / Key-Value Preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Persistent Zero-Token Prompt Response Cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompt_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    prompt_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)

            # Chat Message Queue for Antigravity LLM execution
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt TEXT NOT NULL,
                    images_json TEXT DEFAULT '[]',
                    model TEXT DEFAULT 'gemini-3.8-flash-high',
                    status TEXT DEFAULT 'queued',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Feature Backlog Management table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feature_backlog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'Core',
                    priority TEXT DEFAULT 'P2',
                    status TEXT DEFAULT 'Idea',
                    target_version TEXT DEFAULT 'v1.4.0',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cursor.execute("SELECT COUNT(*) as count FROM feature_backlog")
            if cursor.fetchone()["count"] == 0:
                now_str = datetime.now().isoformat()
                default_backlog = [
                    ("Voice Commands & Native TTS Audio Briefing", "Hands-free voice query input and spoken morning briefing audio generation.", "AI/LLM", "P1", "Planned", "v1.4.0", now_str, now_str),
                    ("Telegram & WhatsApp Remote Bot Interface", "Control Personal Fleet securely from mobile via bidirectional chat bot.", "Integration", "P1", "Planned", "v1.4.0", now_str, now_str),
                    ("Calendar & Google Meet Auto-Agenda Prep", "Analyze incoming calendar invites and automatically generate brief context notes.", "Automation", "P2", "In Progress", "v1.4.0", now_str, now_str),
                    ("Custom MCP Tool Creator UI", "Visual interface to define and test new MCP tool servers directly in dashboard.", "Core", "P2", "Idea", "v1.5.0", now_str, now_str),
                    ("Local Ollama Offline LLM Fine-Tuning", "Offline private local model fallback with LoRA fine-tuning on personal habits.", "AI/LLM", "P3", "Idea", "v2.0.0", now_str, now_str),
                ]
                cursor.executemany("""
                    INSERT INTO feature_backlog (title, description, category, priority, status, target_version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, default_backlog)

            # Unsubscribed Emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unsubscribed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    sender TEXT DEFAULT '',
                    subject TEXT DEFAULT '',
                    unsubscribe_url TEXT DEFAULT '',
                    unsubscribed_at TEXT NOT NULL
                )
            """)

            # Token Preservation Vault table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_preservation_vault (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    token_limit INTEGER DEFAULT 1000000,
                    status TEXT DEFAULT 'exhausted',
                    reason TEXT DEFAULT 'Token limit reached or quota exhausted',
                    preserved_prompts_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
            """)

            # Classified Emails Cache table (Incremental sync & token/traffic saving)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classified_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    subject TEXT DEFAULT '',
                    sender TEXT DEFAULT '',
                    snippet TEXT DEFAULT '',
                    body TEXT DEFAULT '',
                    category_id INTEGER DEFAULT 4,
                    category_name TEXT DEFAULT 'Ignore',
                    reason TEXT DEFAULT '',
                    can_unsubscribe INTEGER DEFAULT 0,
                    unsubscribe_url TEXT DEFAULT '',
                    unsubscribe_type TEXT DEFAULT '',
                    unsubscribed INTEGER DEFAULT 0,
                    received_date TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Health: Medications & Supplements schedule
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS medications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    dosage TEXT DEFAULT '',
                    schedule_time TEXT DEFAULT '09:00',
                    frequency TEXT DEFAULT 'Daily',
                    instructions TEXT DEFAULT '',
                    active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            # Seed default medications if table is empty
            cursor.execute("SELECT COUNT(*) as count FROM medications")
            if cursor.fetchone()["count"] == 0:
                now_str = datetime.now().isoformat()
                default_meds = [
                    ("Vitamin D3 60,000 IU", "1 Capsule", "09:00", "Weekly", "Take with milk or breakfast", 1, now_str),
                    ("Omega-3 Fish Oil (EPA/DHA)", "1000 mg", "13:30", "Daily", "Take immediately after lunch", 1, now_str),
                    ("Multivitamin & Zinc", "1 Tablet", "20:30", "Daily", "Take after dinner with water", 1, now_str),
                ]
                cursor.executemany("""
                    INSERT INTO medications (name, dosage, schedule_time, frequency, instructions, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, default_meds)

            # Health: Daily Medication Intake Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS medication_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medication_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT DEFAULT 'taken',
                    taken_at TEXT NOT NULL,
                    UNIQUE(medication_id, date)
                )
            """)

            # Health: Daily Hydration Tracker Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hydration_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    glasses INTEGER DEFAULT 0,
                    amount_ml INTEGER DEFAULT 0,
                    goal_ml INTEGER DEFAULT 2500,
                    last_drank_at TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                )
            """)

            # Health: Health Metrics & Vitals History (for trend charts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)

            # Offline Event Spool (ROB-15)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offline_spool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT DEFAULT '{}',
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)

            # Seed historical 7-day health trend metrics if empty
            cursor.execute("SELECT COUNT(*) as count FROM health_metrics")
            if cursor.fetchone()["count"] == 0:
                from datetime import timedelta
                base_date = datetime.now()
                sample_trends = []
                history_data = [
                    (6, 2250, 7.2, 7800, 71),
                    (5, 2500, 7.8, 9200, 68),
                    (4, 2000, 6.5, 6400, 74),
                    (3, 2750, 8.0, 10500, 67),
                    (2, 2500, 7.4, 8900, 69),
                    (1, 2250, 7.1, 8100, 70),
                    (0, 1750, 7.5, 6800, 68),
                ]
                for days_ago, water, sleep, steps, hr in history_data:
                    dt = (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    now_iso = datetime.now().isoformat()
                    sample_trends.extend([
                        (dt, "water_ml", float(water), "ml", "Daily hydration", now_iso),
                        (dt, "sleep_hours", float(sleep), "hrs", "Night sleep", now_iso),
                        (dt, "steps", float(steps), "steps", "Daily pedometer", now_iso),
                        (dt, "resting_hr", float(hr), "bpm", "Resting heart rate", now_iso),
                    ])
                cursor.executemany("""
                    INSERT INTO health_metrics (date, metric_type, value, unit, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, sample_trends)

            # Auto-Improvements Table for autonomous self-healing log triage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_improvements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    action_taken TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metrics_before TEXT DEFAULT '{}',
                    metrics_after TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_auto_improvements_created
                ON auto_improvements(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_auto_improvements_type_status
                ON auto_improvements(issue_type, status)
            """)

            # Cognitive Mind Tables (Brain, Consciousness, Subconsciousness, Soul)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mind_critiques (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    critique_score REAL NOT NULL,
                    critique_notes TEXT NOT NULL,
                    corrective_action TEXT DEFAULT '',
                    input_summary TEXT DEFAULT '',
                    output_summary TEXT DEFAULT '',
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mind_critiques_created
                ON mind_critiques(created_at)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mind_dream_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_events_count INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    actionable_recommendation TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mind_dream_created
                ON mind_dream_insights(created_at)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mind_soul_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL,
                    alignment_score REAL NOT NULL,
                    violations_count INTEGER DEFAULT 0,
                    violations_json TEXT DEFAULT '[]',
                    recommendations_json TEXT DEFAULT '[]',
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mind_soul_created
                ON mind_soul_audits(created_at)
            """)

            conn.commit()

    def set_encrypted_setting(self, key: str, plaintext_value: str) -> None:
        """Encrypts a sensitive setting value at rest using the DPAPI Crypto Vault before saving to SQLite."""
        from fleet.core.crypto_vault import encrypt_sensitive_text
        enc_val = encrypt_sensitive_text(plaintext_value)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, enc_val),
            )
            conn.commit()

    def get_encrypted_setting(self, key: str, default: str = "") -> str:
        """Reads and transparently decrypts an encrypted setting from SQLite."""
        from fleet.core.crypto_vault import decrypt_sensitive_text
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if not row:
                return default
            return decrypt_sensitive_text(row["value"])

