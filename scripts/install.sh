#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'from app import create_app; create_app(); print("Database initialized; existing data preserved.")'
