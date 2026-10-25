#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }

not_ready=$(kubectl get pods -n kora-system --no-headers 2>/dev/null | awk '$3 != "Running" && $3 != "Completed"' | wc -l | tr -d ' ')
[ "${not_ready:-1}" = "0" ] && ok "kora-system pods ready" || bad "kora-system pods not all ready ($not_ready)"

kubectl get inferenceprovider ailabs -n kora-system >/dev/null 2>&1 && ok "provider ailabs registered" || bad "provider ailabs missing"

models=$(uv run python -c "from factory_demo.kora_api import load_client; print(' '.join(sorted(m.get('id','') for m in load_client().list_models())))" 2>/dev/null)
for m in claude-haiku-5-5 claude-sonnet-5-5 claude-fable-5-1; do
  case " $models " in *" $m "*) ok "model $m listed";; *) bad "model $m not listed";; esac
done

kubectl get sandboximage kora-node -n kora-tenant-example >/dev/null 2>&1 && ok "sandbox image kora-node present" || bad "sandbox image kora-node missing"

envs=$(uv run python -c "from factory_demo.kora_api import load_client; print(' '.join(e.get('slug','') for e in load_client().list_environments()))" 2>/dev/null)
case " $envs " in *" node-web "*) ok "environment node-web present";; *) bad "environment node-web missing";; esac

exit $fail
