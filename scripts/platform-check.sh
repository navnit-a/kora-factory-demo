#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }

not_ready=$(kubectl get pods -n kora-system --no-headers 2>/dev/null | awk '$3 != "Running" && $3 != "Completed"' | wc -l | tr -d ' ')
[ "${not_ready:-1}" = "0" ] && ok "kora-system pods ready" || bad "kora-system pods not all ready ($not_ready)"

for provider in ailabs-claude ailabs-openai; do
  kubectl get inferenceprovider "$provider" -n kora-system >/dev/null 2>&1 && ok "provider $provider registered" || bad "provider $provider missing"
done

kubectl get sandboximage kora-node -n kora-tenant-example >/dev/null 2>&1 && ok "sandbox image kora-node present" || bad "sandbox image kora-node missing"

uv run python scripts/api-check.py || fail=1

exit $fail
