#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
KORA_DIR="${KORA_DIR:-$HOME/dev/kora}"

echo "Reminder: pause every factory schedule before leaving (sub-project 3 adds this here)."
if [ "${1:-}" = "--down" ]; then
  (cd "$KORA_DIR" && make down)
  echo "cluster and backing services stopped; data kept"
else
  echo "cluster left running; pass --down to stop it"
fi
