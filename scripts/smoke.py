import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.kora_api import KoraClient, load_client  # noqa: E402
from factory_demo.smoke import (  # noqa: E402
    SMOKE_RUN_LIMIT_USD,
    SMOKE_SLUG,
    build_smoke_agent,
    pick_model,
)

MODEL_DEPLOYMENT = "claude-haiku-5-5"
ENVIRONMENT_SLUG = "node-web"
BUDGET_STOP_LIMIT_USD = 0.01
SMOKE_MESSAGE = "Run node --version and stop."
BUDGET_STOP_MESSAGE = "List every file under /usr/lib, one per line, and summarise each directory."


def ensure_agent(client: KoraClient) -> dict:
    existing = [a for a in client.list_agents() if a.get("slug") == SMOKE_SLUG]
    if existing:
        return existing[0]
    model_id = pick_model(client.list_models(), MODEL_DEPLOYMENT)
    environments = [e for e in client.list_environments() if e.get("slug") == ENVIRONMENT_SLUG]
    if not environments:
        raise LookupError(f"environment {ENVIRONMENT_SLUG} not found; create it first (Task 5)")
    return client.create_agent(build_smoke_agent(model_id, environments[0]["id"]))


def wait_until_active(client: KoraClient, agent_id: str, timeout_s: int = 600) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        agent = client.get_agent(agent_id)
        if agent.get("state") == "active":
            return agent
        if time.monotonic() >= deadline:
            raise TimeoutError(f"agent still {agent.get('state')} after {timeout_s}s")
        time.sleep(5)


def show_tenant_pods() -> None:
    subprocess.run(["kubectl", "get", "pods", "-n", "kora-tenant-example"], check=False)


def run_once(client: KoraClient, agent_id: str, message: str) -> tuple[dict, dict]:
    run = client.start_run(agent_id, message)
    print(f"run {run['id']} started", flush=True)
    try:
        finished = client.wait_for_run(run["id"], timeout_s=600)
    except TimeoutError:
        show_tenant_pods()
        raise
    return finished, client.run_usage(run["id"])


def smoke(client: KoraClient, agent_id: str) -> int:
    finished, usage = run_once(client, agent_id, SMOKE_MESSAGE)
    cost = float(usage.get("spend_usd", 0))
    print(
        f"{finished['state']} spend_usd={cost:.4f} tokens={usage.get('total_tokens')}", flush=True
    )
    return 0 if finished["state"] in {"idle", "completed"} and cost > 0 else 1


def budget_stop(client: KoraClient, agent_id: str) -> int:
    client.update_agent(agent_id, {"budget": {"per_run_limit_usd": BUDGET_STOP_LIMIT_USD}})
    try:
        started = time.monotonic()
        finished, usage = run_once(client, agent_id, BUDGET_STOP_MESSAGE)
        elapsed = time.monotonic() - started
        spend = usage.get("spend_usd")
        print(f"{finished['state']} after {elapsed:.0f}s spend_usd={spend}", flush=True)
        return 0 if finished["state"] == "budget_exhausted" else 1
    finally:
        client.update_agent(agent_id, {"budget": {"per_run_limit_usd": SMOKE_RUN_LIMIT_USD}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-stop", action="store_true")
    args = parser.parse_args()
    client = load_client()
    agent = wait_until_active(client, ensure_agent(client)["id"])
    return budget_stop(client, agent["id"]) if args.budget_stop else smoke(client, agent["id"])


if __name__ == "__main__":
    raise SystemExit(main())
