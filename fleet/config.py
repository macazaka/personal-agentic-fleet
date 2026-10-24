"""
Configuration for Personal Agentic Fleet.
Supports Google Gemini, OpenAI, Local Ollama, and an Offline Smart Heuristic mode.
"""

import os
import sys
from pathlib import Path

# Fleet Version & Minimum Runtime Requirement
VERSION = "2.0.0"
MIN_PYTHON_VERSION = (3, 10)


def check_minimum_python_version(version_info=None) -> bool:
    """Verifies that the active Python interpreter meets the minimum >= 3.10 requirement."""
    current = version_info if version_info is not None else sys.version_info
    if (current[0], current[1]) < MIN_PYTHON_VERSION:
        detected = f"{current[0]}.{current[1]}.{current[2] if len(current) > 2 else 0}"
        raise RuntimeError(
            f"[Personal Agentic Fleet] Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher is required "
            f"(detected Python {detected}). Please upgrade Python at https://www.python.org/downloads/"
        )
    return True


check_minimum_python_version()

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "fleet_memory.db"
TEST_DB_PATH = DATA_DIR / "fleet_test_memory.db"
NOTES_DIR = DATA_DIR / "notes"
NOTES_DIR.mkdir(exist_ok=True)
CHANGELOG_PATH = BASE_DIR.parent / "CHANGELOG.md"

# LLM Providers Configuration
# Can be loaded from environment variables or set directly
def get_secure_secret(key_name: str, fallback_env: str = "") -> str:
    """
    Retrieves secret prioritizing:
    1. Windows Credential Manager (DPAPI via keyring, if installed)
    2. Windows User & Process Environment Variables
    3. fleet.yaml / fleet.json configuration
    """
    # 1. Windows Credential Manager (DPAPI)
    try:
        import keyring
        val = keyring.get_password("fleet_os", key_name)
        if val:
            return val
    except Exception:
        pass

    # 2. Environment Variables
    env_name = fallback_env or key_name
    val = os.getenv(env_name)
    if val:
        return val

    # 3. fleet.yaml / fleet.json
    try:
        cfg = load_fleet_config()
        val = cfg.get("keys", {}).get(key_name)
        if val:
            return val
    except Exception:
        pass

    return ""

GEMINI_API_KEY = get_secure_secret("GEMINI_API_KEY")
OPENAI_API_KEY = get_secure_secret("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Active Provider: "gemini", "openai", "ollama", or "auto"
# "auto" detects available keys or falls back to smart offline mode
DEFAULT_PROVIDER = os.getenv("FLEET_LLM_PROVIDER", "auto")

# Personal Profile & Timezone Settings
USER_NAME = os.getenv("FLEET_USER_NAME", "User")
TIMEZONE = os.getenv("FLEET_TIMEZONE", "Asia/Kolkata")
TIMEZONE_NAME = "IST"
TIMEZONE_OFFSET = "+05:30"
BRIEFING_TIME = "08:30"
EVENING_REVIEW_TIME = "20:00"

# Notification settings
ENABLE_WINDOWS_NOTIFICATIONS = True

# Governance & Cost Optimization
# Enforces lowest token, compute, and financial cost decision making
COST_OPTIMIZATION_POLICY = "LOWEST_COST_FIRST"
PREFER_ZERO_TOKEN_CODE = True          # Use deterministic Python instead of LLM whenever possible
CONTEXT_PRUNING_MAX_TASKS = 5          # Limit payload sizes to minimize tokens
DEFAULT_MODEL_TIER = "flash_lite"      # Prioritize lightweight models before escalating


def load_fleet_config() -> dict:
    """Loads fleet configuration from fleet.json or fleet.yaml, falling back to defaults."""
    # 1. Try fleet.json first
    for parent_dir in [BASE_DIR.parent, BASE_DIR]:
        config_file_json = parent_dir / "fleet.json"
        if config_file_json.is_file():
            try:
                return json.loads(config_file_json.read_text(encoding="utf-8"))
            except Exception:
                pass

    # 2. Try fleet.yaml
    for parent_dir in [BASE_DIR.parent, BASE_DIR]:
        config_file_yaml = parent_dir / "fleet.yaml"
        if config_file_yaml.is_file():
            try:
                import yaml
                return yaml.safe_load(config_file_yaml.read_text(encoding="utf-8")) or {}
            except ImportError:
                # Built-in zero-dependency YAML parser fallback
                cfg = {"server": {}, "agents": {}}
                current_section = None
                current_agent = None
                for raw_line in config_file_yaml.read_text(encoding="utf-8").splitlines():
                    line = raw_line.split("#")[0].rstrip()
                    if not line:
                        continue
                    indent = len(raw_line) - len(raw_line.lstrip())
                    parts = line.strip().split(":", 1)
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().strip('"').strip("'")
                        if indent == 0:
                            current_section = k
                            current_agent = None
                        elif indent == 2 and current_section == "agents":
                            current_agent = k
                            cfg["agents"][current_agent] = {}
                        elif indent >= 4 and current_section == "agents" and current_agent:
                            val = v
                            if v.lower() == "true":
                                val = True
                            elif v.lower() == "false":
                                val = False
                            elif v.isdigit():
                                val = int(v)
                            cfg["agents"][current_agent][k] = val
                        elif indent >= 2 and current_section == "server":
                            cfg["server"][k] = v
                return cfg

    # 3. Default fallback configuration
    return {
        "server": {"host": "127.0.0.1", "port": 7890, "default_agent": "health"},
        "agents": {
            "health": {"enabled": True},
            "overview": {"enabled": True},
            "optimizer": {"enabled": True},
            "antigravity": {"enabled": True},
            "backlog": {"enabled": True},
            "gmail": {"enabled": False}
        }
    }
