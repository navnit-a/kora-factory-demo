import subprocess
import time
from collections.abc import Callable

from factory_demo.environments import NODE_WEB
from factory_demo.kora_api import KoraClient
from factory_demo.smoke import SMOKE_RUN_LIMIT_USD, SMOKE_SLUG, build_smoke_agent, pick_model

MODEL_DEPLOYMENT = "claude-haiku-5-5"
BUDGET_STOP_LIMIT_USD = 0.001
BUDGET_PROPAGATION_S = 40
RUN_TIMEOUT_S = 600
SMOKE_MESSAGE = "Run node --version and stop."
BUDGET_STOP_MESSAGE = "List every file under /usr/lib, one per line, and summarise each directory."
PASSING_STATES = frozenset({"idle", "completed"})


def ensure_agent(client: KoraClient) -> dict:
    existing = [a for a in client.list_agents() if a.get("slug") == SMOKE_SLUG]
    if existing:
        return existing[0]
    model_id = pick_model(client.list_models(), MODEL_DEPLOYMENT)
    environments = [e for e in client.list_environments() if e.get("slug") == NODE_WEB.slug]
    if not environments:
        raise LookupError(
            f"environment {NODE_WEB.slug} not found; run scripts/create-environment.py"
        )
    return client.create_agent(build_smoke_agent(model_id, environments[0]["id"]))


def wait_until_active(
    client: KoraClient,
    agent_id: str,
    timeout_s: int = RUN_TIMEOUT_S,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        agent = client.get_agent(agent_id)
        if agent.get("state") == "active":
            return agent
        if time.monotonic() >= deadline:
            raise TimeoutError(f"agent still {agent.get('state')} after {timeout_s}s")
        sleep(5)


def show_tenant_pods() -> None:
    subprocess.run(["kubectl", "get", "pods", "-n", "kora-tenant-example"], check=False)


def run_once(
    client: KoraClient,
    agent_id: str,
    message: str,
    timeout_s: int = RUN_TIMEOUT_S,
    show_pods: Callable[[], None] = show_tenant_pods,
) -> tuple[dict, dict]:
    run = client.start_run(agent_id, message)
    print(f"run {run['id']} started", flush=True)
    try:
        finished = client.wait_for_run(run["id"], timeout_s=timeout_s)
    except TimeoutError:
        show_pods()
        raise
    return finished, client.run_usage(run["id"])


def smoke(client: KoraClient, agent_id: str) -> int:
    finished, usage = run_once(client, agent_id, SMOKE_MESSAGE)
    cost = float(usage.get("spend_usd", 0))
    print(
        f"{finished['state']} spend_usd={cost:.4f} tokens={usage.get('total_tokens')}", flush=True
    )
    return 0 if finished["state"] in PASSING_STATES and cost > 0 else 1


def budget_stop(
    client: KoraClient, agent_id: str, sleep: Callable[[float], None] = time.sleep
) -> int:
    client.update_agent(agent_id, {"budget": {"per_run_limit_usd": BUDGET_STOP_LIMIT_USD}})
    print(f"waiting {BUDGET_PROPAGATION_S}s for the limit to reach the gateway", flush=True)
    sleep(BUDGET_PROPAGATION_S)
    try:
        started = time.monotonic()
        finished, usage = run_once(client, agent_id, BUDGET_STOP_MESSAGE)
        elapsed = time.monotonic() - started
        spend = usage.get("spend_usd")
        print(f"{finished['state']} after {elapsed:.0f}s spend_usd={spend}", flush=True)
        return 0 if finished["state"] == "budget_exhausted" else 1
    finally:
        client.update_agent(agent_id, {"budget": {"per_run_limit_usd": SMOKE_RUN_LIMIT_USD}})
