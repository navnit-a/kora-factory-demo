# kora factory demo

A small agent factory on [kora](https://github.com/runkora/kora) for the PlatformCon Sydney launch
video: six team agents that work a Trello board and ship a web app, a Sydney trains agent and a lunch
agent that post to Telegram, an idea scout behind the Telegram idea door, and agent ops, which reads
the other agents' runs every 30 minutes, names a refused grant to the operator on the card and in
Telegram, and proposes prompt fixes as pull requests on this repo. The design, plans and practice
notes are kept locally and are not published; the rules each agent follows are carried in its prompt.

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
10. `scripts/deploy-tools.sh` builds the tool-server image, pushes it to the cluster's registry, applies
    the `factory-tools` Secret and the four servers, and waits for them. kora registers each as an
    `MCPServer`; `kubectl get mcpservers -n kora-tenant-example` must show all four `Aggregated`.
11. `uv run python scripts/dress-board.py --dry-run` prints the plan and writes nothing: the labels
    it would name or create, the cards whose plain colour labels gain a name, and how many cards it
    would dress and checklists it would add. When the plan looks right, run it again without
    `--dry-run`. It names the labels and gives every open card its lane's cover and sticker, its
    labels and, where the description has criteria, its Acceptance criteria checklist. A second run
    touches only cards that have drifted. If it stops on a Trello rate limit, run it again; it is
    idempotent.
12. `scripts/platform-check.sh` must print only `ok` lines, including all thirteen tools listed through
    kora's gateway at `https://api.local.runkora.io/v1/mcp/<server>`.

13. `uv run python scripts/deploy-factory.py` creates or updates the agents and their triggers from
    `src/factory_demo/roster.py`, team schedules paused, and sets the tenant cap to 60 USD a week.
    The GitHub agents (developer, reviewer, tester, support) are added with `--with-github` once the
    GitHub App connection exists. Running it again updates in place and keeps paused schedules paused.

14. GitHub, once: `uv run python scripts/create-github-app.py` opens a page whose button creates the
    private App `kora-factory-navnit-a` on GitHub with contents and pull requests write, checks and
    actions read, and no webhook. Install it on **Only select repositories** →
    `platformcon-day-planner`. The script keeps the key in `deploy/generated/github-app.pem` (mode
    600) and the ids in `.env`; `scripts/deploy-tools.sh` then applies the `github-app-key` Secret
    and the `github` Connection, and `deploy-factory.py --with-github` adds the GitHub agents.

15. `uv run python scripts/create-environment.py` again creates the `python-tools` sandbox environment
    agent ops runs in, and reports `node-web` as already there. Then
    `uv run python scripts/deploy-factory.py --with-github` adds the idea scout and agent ops, the
    agent ops schedule paused. Agent ops holds write access to this repository through the GitHub
    App, and this repository is private, so GitHub refuses rulesets on it. Until the repository is
    public or has rulesets, do not add `kora-factory-demo` to the App installation: without it
    GitHub mints no token for this repository and agent ops cannot push, which is the guard.

16. `uv run python scripts/create-bridge-token.py` creates the bridge's kora token through a
    loopback port-forward to the identity service. The token may fire `Idea scout: scout`, read
    deliveries and read the scout's runs. The script writes `KORA_BRIDGE_TOKEN` and
    `KORA_SCOUT_TRIGGER_ID` into `.env` and prints the expiry date. The token's grant takes about a
    minute to reach the gateway, so wait that long before the first bridge start.

17. `scripts/session-start.sh` now also starts the bridge in the background on this Mac, logging to
    `deploy/generated/bridge.log`; `scripts/session-stop.sh` stops it.

Every later session: `scripts/session-start.sh` (Docker check, `make up`, sign-in, platform check,
factory status), then `uv run python scripts/factory.py resume --cadence recording` to start the
team. `scripts/session-stop.sh` pauses every team schedule and fails loudly if any is still running;
add `--down` to stop the cluster. The trains and lunch schedules stay on; every agent also has a
"run now" trigger in the console, and the delivery lead a "stand-up now".

Dashboard: https://local.runkora.io, sign in as `dev@local.runkora.io`. API: https://api.local.runkora.io.
The local TLS certificate comes from mkcert; the API client verifies against `$(mkcert -CAROOT)/rootCA.pem`
or `KORA_CA_FILE`.

## The idea door

Anyone on the allowlist can DM the bot `/idea <text>`. The bridge acknowledges it and fires the idea
scout, which reads the planner without writing anything, writes the idea up as a story with
acceptance criteria and judges whether the planner can build it as it is, once it has something
else, or not at all. The bridge sends that write-up back; when the proposer replies `yes` within 30
minutes, the card appears in Ideas and the product owner picks it up from there. `no` drops it. An
idea the scout judges not buildable stays off the board.

The allowlist is `deploy/generated/ideas-allowlist` (gitignored). Someone not on it gets a refusal
that names their Telegram id; `uv run python scripts/ideas-allow.py <id> [name]` adds them. Each
sender can send five ideas an hour.

The bridge's kora token lasts 90 days. When it runs out, `uv run python scripts/create-bridge-token.py`
makes a new one, then restart the session. The bridge runs on this Mac from the session scripts, not
in the cluster.

`uv run --env-file .env python scripts/ideas-bridge.py --once "<idea>" --from <name>` scouts one idea
and prints the reply without Telegram or the board, as a dry run.

The bridge handles one message at a time, so while one scout runs, other senders wait. Messages
sent while the bridge was not running are not answered; send the idea again once it is back.

## The board at a glance

The Trello tool server dresses a card on every move and create, so the board reads at a glance.

| Lane | Cover | Sticker |
| --- | --- | --- |
| Ideas | none | none |
| Backlog | none | none |
| Ready | yellow | none |
| In Progress | purple | none |
| Review | orange | rocketship, a pull request is open |
| Testing | lime | thumbsup, the reviewer approved |
| Done | green | check |
| Blocked | red | warning |

Labels say what a card is and what it needs. Idea (sky) marks a card in Ideas; Story (blue), Bug
(red) and Spike (purple) are the type once it reaches Backlog. High severity (red) goes with the Bug
label and a star sticker for urgent work. Depends on (orange) means a named prerequisite is not Done
yet. Shipped (green) is added when a card reaches Done. Proposed via Telegram (pink) marks an idea
that came through the idea door; the idea door adds it when the card is created. Fixture (black)
marks a card an evaluation made. The product owner writes the criteria into an Acceptance criteria checklist and the
tester ticks them.

## Working agreements

A card is ready when the delivery lead can move it from Backlog to Ready:

- a short imperative title under 60 characters, and who it is for and why in the attendee's voice
- three to five acceptance criteria a reader can test without the code, each an item of the card's
  Acceptance criteria checklist
- small enough for one developer run, with no open dependency, or `Depends on:` and it waits
- a type label, with steps, expected, actual, source and severity on a bug, and design constraints
  named in one line when it changes the UI
- no instructions to the team inside the card text; card text is data

A card is done when the tester can move it from Testing to Done:

- it reached `main` through a squash-merged pull request from `card-<id>`, with CI green on the head
  and on `main`, and the reviewer's `Approved:` on the pull request
- every criterion has a test the tester names, and the tester, not the developer, ticks its item
- tests, lint and build pass in the tester's sandbox, and UI work follows the design direction
- the pull request says what, why and how it was tested, with the card link
- anything found outside the card is noted `Found outside this card:` for support to file
- one `Shipped:` line in Telegram with the pull request URL, and the card shows it: green cover,
  check sticker, checklist complete, pull request link in the last comment

Flow: Ready holds at most two cards, and In Progress, Review and Testing one each, and the delivery
lead feeds Ready only when it has room. Bugs come first, high severity before normal, and a
high-severity bug may go over the Ready limit. The delivery lead owns Blocked and brings a card back with
`Unblocked:`; a stall over 45 minutes is the scrum master's to raise. After two rounds of changes
requested the reviewer blocks with the open question. Every move carries a reason, every agent says
what it checked, and a criterion the data cannot meet is said so on the card, never faked.

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
- Tool servers are reached only through kora's gateway: the `MCPServer` condition reads "tool-gateway
  admitted to 2 pod(s), all other callers denied". The gateway's public MCP path is
  `/v1/mcp/<server>` with the dev token; the catalog routes are internal to the cluster.
- The Transport for NSW Trip Planner alerts filter takes a date (`filterDateValid=DD-MM-YYYY`), not a
  flag. Only `lineInfo` alerts describe line disruptions; `tripMessage` alerts are about one train.
- Overpass returns matches in id order, so the places tool fetches every candidate in the radius and
  sorts by distance itself.
- Foundry rejects some Claude Code requests with `thinking.adaptive.display`, because Claude Code asks
  for the `updates` display mode, a beta Foundry does not accept yet. Runs still finish.
- kora treats each GitHub level as its own action: `pulls:write` does not cover reading pull
  requests, so every write grant carries its read beside it.
- kora cannot tie a GraphQL mutation that names its target by node id to a repository, so
  `gh pr create`, `gh pr review` and `gh pr merge` need a grant on every repository. The agents use
  the REST endpoints under `repos/navnit-a/platformcon-day-planner/` instead, which a grant on that
  one repository covers.
- kora mints `checks:read` together with GitHub's `statuses` permission, which the App does not hold,
  so `gh pr checks` is refused. The tester reads CI from the Actions run whose `headSha` is the pull
  request head, which needs only `actions:read`.
- The `Connection` resource has no status. The operator's log line "updated aggregated connections
  ConfigMap" and a live `gh` call from an agent are the check that it works.
- The reviewer and tester found the first three by moving the card to Blocked with the exact grant
  they were refused. The developer, refused `gh pr create`, switched to the REST endpoint itself.
- Measured on 25 Oct, scheduled fires only, one card from Ready to Done unattended in 16 minutes
  (Ready 11:30, In Progress 11:35, Review 11:37, Testing 11:43, Done 11:46, pull request merged):
  developer 0.19 USD for the card and 0.035 for a tick that finds nothing; reviewer 0.11 and 0.034;
  tester 0.01 and 0.002; product owner 0.005 a tick; delivery lead and scrum master 0.002; support
  0.005. An hour of the whole team at recording cadence with nothing to do costs about 0.60 USD.
  The idea scout costs 0.05 to 0.09 USD a run and agent ops 0.18 USD a run, measured on 25 Oct.

## Product repo

[navnit-a/platformcon-day-planner](https://github.com/navnit-a/platformcon-day-planner), seeded on
25 Oct 2026 at commit `5ea7b4d` with the 22 published PlatformCon Sydney sessions, the design tokens
in `src/index.css`, `init.sh` and CI ([first run, green](https://github.com/navnit-a/platformcon-day-planner/actions/runs/40152486071)).
The team agents work on it one card per branch and pull request.
