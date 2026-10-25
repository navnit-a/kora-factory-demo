#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
KORA_DIR="${KORA_DIR:-$HOME/dev/kora}"

docker info >/dev/null 2>&1 || { echo "Docker Desktop is not running"; exit 1; }
caffeinate -dimsu -w $$ &
echo "caffeinate armed for this shell (pid $$)"

(cd "$KORA_DIR" && make up)
(cd "$KORA_DIR" && make auth-refresh) || (cd "$KORA_DIR" && make auth)

scripts/platform-check.sh
uv run python scripts/factory.py status

BRIDGE_PID_FILE=deploy/generated/bridge.pid
if [ -f "$BRIDGE_PID_FILE" ] && kill -0 "$(cat "$BRIDGE_PID_FILE")" 2>/dev/null; then
  echo "ideas bridge already running (pid $(cat "$BRIDGE_PID_FILE"))"
elif grep -q '^KORA_BRIDGE_TOKEN=' .env 2>/dev/null; then
  mkdir -p deploy/generated
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid uv run --env-file .env python scripts/ideas-bridge.py >> deploy/generated/bridge.log 2>&1 &
  else
    nohup uv run --env-file .env python scripts/ideas-bridge.py >> deploy/generated/bridge.log 2>&1 &
  fi
  echo $! > "$BRIDGE_PID_FILE"
  echo "ideas bridge started (pid $(cat "$BRIDGE_PID_FILE")); log in deploy/generated/bridge.log"
else
  echo "ideas bridge not started: run uv run python scripts/create-bridge-token.py first"
fi
echo "resume with: uv run python scripts/factory.py resume --cadence recording"
