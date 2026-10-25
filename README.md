# kora factory demo

A small agent factory on [kora](https://github.com/runkora/kora) for the PlatformCon Sydney launch
video: six team agents that work a Trello board and ship a web app, a Sydney trains agent and a lunch
agent that post to Telegram. The design and plans are kept locally under `docs/superpowers/`, which
is not published. The rules every agent and tool follows are in
[docs/agent-practices.md](docs/agent-practices.md), and the team's delivery rules in
[docs/sdlc-practices.md](docs/sdlc-practices.md).

## Session runbook

kora is cloned at `~/dev/kora`. The cluster runs in k3d on this Mac; Docker Desktop is set to 8 CPUs
and 12 GB. Every script prints a one-line hint and exits 2 when the kora token is missing or expired.

First time, or after `make reset`:

1. Start Docker Desktop. Check nothing else holds port 443; if something does, the dashboard and API
   are on `:8443` and `KORA_API_URL` in `.env` must say so.
2. `cd ~/dev/kora && make up`. Run one at a time; two runs at once collide in Helm.
3. `cd ~/dev/kora && make redeploy-sandbox-images`, set `node: {enabled: true}` under
   `agents.sandboxImages.bundled` in `deploy/reference/values/kora.local.yaml`, then
   `cd deploy/reference && helmfile -e local apply --selector name=kora`.
4. `cd ~/dev/kora && make auth` and sign in as `dev@local.runkora.io` / `password`. The token lasts four
   hours; `make auth-refresh` renews it.
5. `cd ~/dev/kora-factory-demo && uv sync && uv run pytest -q`.
6. Secrets and providers:

   ```bash
   uv run python scripts/render-secrets.py
   kubectl apply -f deploy/generated/secrets.yaml
   set -a && . ./.env && set +a
   for f in deploy/providers/*.yaml; do envsubst < "$f" | kubectl apply -f -; done
   ```

7. `uv run python scripts/register-models.py` registers the five virtual models and their prices.
8. `uv run python scripts/create-environment.py` creates the `node-web` sandbox environment.
9. `uv run python scripts/smoke.py` must end with `idle spend_usd=` above zero, and
   `uv run python scripts/smoke.py --budget-stop` must end with `budget_exhausted`.
10. `scripts/platform-check.sh` must print only `ok` lines.

Every later session: start Docker, `make up`, `make auth-refresh`, then `scripts/platform-check.sh`.

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
- 25 Oct 2026, 01:40: platform up after four `make up` runs. A Helm upgrade collided with the first
  install, and the kora-identity OIDC check fired seconds before the provider logged as initialised;
  `make cluster-deploy` on its own finished the tenant step. Port 443 free, so no `:8443`.

## Findings that shape the factory

- kora's native `azure` provider cannot call Claude on Foundry: it sets only an `api-key` header and
  the Anthropic SDK refuses to send without credentials it recognises. The `compatible` provider on
  `<resource>/anthropic/v1` works, with price overrides set to the published list prices.
- GPT-5.5 and GPT-5.4 work through kora's native `azure` provider on the same Foundry resource and key.
- Prices match Anthropic's list prices, which Foundry bills at: Haiku 5.5 $0.10 in and $0.50 out per
  million tokens for prompts up to 100K tokens, Sonnet 5.5 $2 and $10, Fable 5.1 $10 and $50.
- A run started through the API ends its turn as `idle` and keeps its pod slot until the idle timeout
  (20 minutes for a person, 5 for a trigger). kora's run DELETE removes the run from history.
- Budget changes take about 30 seconds to reach the gateway, and the call in flight when a limit is
  crossed still completes. A Haiku 5.5 run of a small task costs about $0.002.
- Foundry rejects some Claude Code requests with `thinking.adaptive.display`, because Claude Code asks
  for the `updates` display mode, a beta Foundry does not accept yet. Runs still finish.
