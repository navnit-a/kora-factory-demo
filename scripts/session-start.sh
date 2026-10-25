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
