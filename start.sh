#!/usr/bin/env bash
# VeriSight Interactive Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Activate virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if [ $# -eq 0 ]; then
    python3 main.py start
else
    python3 main.py "$@"
fi
