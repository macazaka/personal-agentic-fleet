"""Unit tests for fleet.config."""
from pathlib import Path
import fleet.config as cfg


def test_config_paths():
    assert isinstance(cfg.BASE_DIR, Path)
    assert isinstance(cfg.DATA_DIR, Path)
    assert isinstance(cfg.DB_PATH, Path)
    assert isinstance(cfg.TEST_DB_PATH, Path)
    assert isinstance(cfg.NOTES_DIR, Path)
    assert cfg.DATA_DIR.exists()
    assert cfg.NOTES_DIR.exists()


def test_config_constants():
    assert cfg.VERSION == "2.5.0"
    assert cfg.CHANGELOG_PATH.exists()
    assert cfg.CHANGELOG_PATH.is_file()
    import fleet
    assert fleet.__version__ == cfg.VERSION
    assert cfg.TIMEZONE == "Asia/Kolkata"
    assert cfg.TIMEZONE_NAME == "IST"
    assert cfg.TIMEZONE_OFFSET == "+05:30"
    assert cfg.BRIEFING_TIME == "08:30"
    assert cfg.EVENING_REVIEW_TIME == "20:00"
    assert cfg.ENABLE_WINDOWS_NOTIFICATIONS is True
    assert cfg.COST_OPTIMIZATION_POLICY == "LOWEST_COST_FIRST"
    assert cfg.PREFER_ZERO_TOKEN_CODE is True
    assert cfg.CONTEXT_PRUNING_MAX_TASKS == 5
    assert cfg.DEFAULT_MODEL_TIER == "flash_lite"
