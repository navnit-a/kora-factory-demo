SMOKE_SLUG = "smoke"
SMOKE_PROMPT = (
    "You are the platform smoke test for a kora agent factory. Your run proves that an agent can "
    "start a sandbox and run a command in it, so the rest of the factory can be trusted. "
    'Provision a sandbox in your default environment, run "node --version" in it, and reply '
    "with one line: the version it printed. Then stop: make no further tool calls. "
    "If the sandbox fails to start or the command fails, reply with one line saying what failed "
    "and stop."
)
SMOKE_RUN_LIMIT_USD = 0.2
SMOKE_RUNS_PER_POD = 4


def build_smoke_agent(model_id: str, environment_id: str) -> dict:
    return {
        "name": "Smoke test",
        "slug": SMOKE_SLUG,
        "description": "Runs node --version in a sandbox to prove the platform works end to end.",
        "system_prompt": SMOKE_PROMPT,
        "framework": "claude-code",
        "identity_mode": "autonomous",
        "model_id": model_id,
        "environments": [{"environment_id": environment_id, "is_default": True}],
        "max_concurrent_runs_per_pod": SMOKE_RUNS_PER_POD,
        "budget": {"per_run_limit_usd": SMOKE_RUN_LIMIT_USD},
    }


def pick_model(models: list[dict], deployment: str) -> str:
    ids = [m.get("id", "") for m in models]
    matches = [i for i in ids if i == deployment or i.endswith("/" + deployment)]
    if not matches:
        raise LookupError(f"{deployment} not in kora's model list: {', '.join(ids) or 'none'}")
    return matches[0]
