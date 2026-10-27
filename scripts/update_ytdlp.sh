#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

if [ -f "backend/venv/bin/python" ]; then
    echo "Using backend virtual environment..."
    backend/venv/bin/python scripts/update_ytdlp.py
else
    echo "Using system Python..."
    python3 scripts/update_ytdlp.py
fi
