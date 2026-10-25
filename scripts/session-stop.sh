#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
KORA_DIR="${KORA_DIR:-$HOME/dev/kora}"

BRIDGE_PID_FILE=deploy/generated/bridge.pid
if [ -f "$BRIDGE_PID_FILE" ]; then
  BRIDGE_PID="$(cat "$BRIDGE_PID_FILE")"
  BRIDGE_PGID="$(ps -o pgid= -p "$BRIDGE_PID" 2>/dev/null | tr -d ' ' || true)"
  OWN_PGID="$(ps -o pgid= -p $$ | tr -d ' ')"
  if [ -n "$BRIDGE_PGID" ] && [ "$BRIDGE_PGID" != "$OWN_PGID" ]; then
    kill -TERM -- "-$BRIDGE_PGID" 2>/dev/null || true
    echo "ideas bridge stopped (process group $BRIDGE_PGID)"
  elif [ -n "$BRIDGE_PGID" ]; then
    kill -TERM "$BRIDGE_PID" 2>/dev/null || true
    echo "ideas bridge stopped (pid $BRIDGE_PID)"
  fi
  rm -f "$BRIDGE_PID_FILE"
fi

(cd "$KORA_DIR" && make auth-refresh) || (cd "$KORA_DIR" && make auth)
if ! uv run python scripts/factory.py pause; then
  echo "factory not fully paused; the cluster is left running so you can retry" >&2
  exit 1
fi
uv run python scripts/factory.py status

if [ "${1:-}" = "--down" ]; then
  (cd "$KORA_DIR" && make down)
  echo "cluster and backing services stopped; data kept"
else
  echo "cluster left running; pass --down to stop it"
fi
