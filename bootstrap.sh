#!/usr/bin/env bash
# Personal Agentic Fleet — POSIX (macOS / Linux) Self-Bootstrapping & Security Provisioner
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=================================================================="
echo "  Personal Agentic Fleet — Bootstrap & Security Provisioner"
echo "=================================================================="

find_valid_python() {
    for candidate in "$REPO_ROOT/.venv/bin/python" python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                command -v "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN="$(find_valid_python || true)"

if [ -z "$PYTHON_BIN" ]; then
    echo "[!] Python >= 3.10 not found. Attempting automated install..."
    if command -v brew >/dev/null 2>&1; then
        brew install python@3.12
    elif command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3
    fi
    PYTHON_BIN="$(find_valid_python || true)"
    if [ -z "$PYTHON_BIN" ]; then
        echo "[ERROR] Python >= 3.10 is required. Install from https://www.python.org/downloads/"
        exit 1
    fi
fi

PY_VER="$("$PYTHON_BIN" -c 'import sys; print(sys.version.split()[0])')"
echo "[OK] Verified Python Interpreter: $PYTHON_BIN (v$PY_VER >= 3.10)"

# Initialize fleet.yaml if missing
if [ ! -f "$REPO_ROOT/fleet.yaml" ] && [ -f "$REPO_ROOT/fleet.yaml.example" ]; then
    cp "$REPO_ROOT/fleet.yaml.example" "$REPO_ROOT/fleet.yaml"
    echo "[OK] Created local fleet.yaml from fleet.yaml.example"
fi

# Harden user vault permissions (chmod 700)
mkdir -p "$REPO_ROOT/fleet/data/user"
chmod 700 "$REPO_ROOT/fleet/data/user"
echo "[OK] Hardened permissions (0700) on fleet/data/user/"

export PYTHONPATH="$REPO_ROOT"
"$PYTHON_BIN" -m fleet.tools.install_git_hooks
"$PYTHON_BIN" -m fleet.tools.fleet_doctor --strict

