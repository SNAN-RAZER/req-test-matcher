#!/usr/bin/env bash
# Debian/Ubuntu: never pip-install into system Python (PEP 668).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "Install Python first: sudo apt install python3 python3-venv python3-full"
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv || {
    echo "venv failed. Try: sudo apt install python3-venv python3-full"
    exit 1
  }
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if command -v npm >/dev/null; then
  (cd web && npm install && npm run build)
else
  echo "npm not found. Install with: sudo apt install npm"
  echo "Then: cd web && npm install && npm run build"
fi

exec .venv/bin/python -m app.main
