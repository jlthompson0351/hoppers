#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

export LCS_HW_MODE="${LCS_HW_MODE:-sim}"
export LCS_HOST="${LCS_HOST:-0.0.0.0}"
export LCS_PORT="${LCS_PORT:-8080}"

python -m src.app


