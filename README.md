# kora factory demo

A small agent factory on [kora](https://github.com/runkora/kora) for the PlatformCon Sydney launch
video: six team agents that work a Trello board and ship a web app, a Sydney trains agent and a lunch
agent that post to Telegram. The design is in
[docs/superpowers/specs/2026-10-25-kora-factory-demo-design.md](docs/superpowers/specs/2026-10-25-kora-factory-demo-design.md);
the plans are under `docs/superpowers/plans/`.

## Session runbook

kora is cloned at `~/dev/kora`. The cluster runs in k3d on this Mac; the owner's Docker Desktop is set
to 8 CPUs and 12 GB.

1. Start Docker Desktop. Check nothing else holds port 443.
2. `cd ~/dev/kora && make up` (idempotent; the first run builds every image).
3. `make auth` once per four hours, or `make auth-refresh`. The token lands in `/tmp/kora_credentials.json`.
4. `cd ~/dev/kora-factory-demo && uv sync && uv run pytest -q`.
5. `uv run python scripts/render-secrets.py && kubectl apply -f deploy/generated/secrets.yaml`, then
   apply the providers in `deploy/providers/` (see the plan's Task 3).
6. `scripts/platform-check.sh` must print only `ok` lines before any agent work starts.

Dashboard: https://local.runkora.io, sign in as `dev@local.runkora.io`. API: https://api.local.runkora.io.
The local TLS certificate comes from mkcert; the API client verifies against `$(mkcert -CAROOT)/rootCA.pem`
or `KORA_CA_FILE`.

## Secrets

Everything secret lives in `.env` (gitignored; template in `.env.example`). `scripts/render-secrets.py`
turns it into Kubernetes Secret manifests under `deploy/generated/` (also gitignored). Nothing secret is
committed, pasted into a prompt, or shown on screen.

## Bring-up log

- 25 Oct 2026, 01:25: `make setup` 1m52s. Port 443 free. Port 5432 was held by another project's
  Postgres container, so kora's `.env` sets `DB_PORT=5433`.
- 25 Oct 2026, 01:30: a `make up` run stopped building at policy-service with exit 255 and no
  error; building that image alone worked, and rerunning `make up` resumes from the images already
  in the local registry. If it recurs, run `bash scripts/cluster/redeploy.sh <service> --build-only`.
