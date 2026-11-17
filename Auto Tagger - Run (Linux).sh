#!/usr/bin/env bash
cd "$(dirname "$0")"

if [ ! -f "venv/bin/python" ]; then
    echo "[ERROR] Virtual environment 'venv' not found!"
    echo "Please run \"./Auto Photo Tagger - Install (Linux).sh\" first."
    exit 1
fi

"venv/bin/python" app/main.py "$@"
