#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "========================================="
echo "Starting Video Summarizer Web Server..."
echo "========================================="

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 server.py
