#!/usr/bin/env bash
# One-time setup on Ubuntu 22.04/24.04 (needs sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update
sudo apt-get install -y $(grep -vE '^\s*(#|$)' "$ROOT/requirements/system-packages.txt")
python3 -m pip install --user -r "$ROOT/requirements/python.txt" || \
  python3 -m pip install --user --break-system-packages -r "$ROOT/requirements/python.txt"
"$ROOT/scripts/check_environment.sh"
