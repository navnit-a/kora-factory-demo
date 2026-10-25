SMOKE_SLUG = "smoke"
SMOKE_PROMPT = (
    'You are a smoke test. Provision a sandbox, run "node --version", '
    "report the output in one line, then stop."
)
SMOKE_RUN_LIMIT_USD = 0.2


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
        "max_concurrent_runs_per_pod": 1,
        "budget": {"per_run_limit_usd": SMOKE_RUN_LIMIT_USD},
    }


def pick_model(models: list[dict], deployment: str) -> str:
    ids = [m.get("id", "") for m in models]
    matches = [i for i in ids if i == deployment or i.endswith("/" + deployment)]
    if not matches:
        raise LookupError(f"{deployment} not in kora's model list: {', '.join(ids) or 'none'}")
    return matches[0]
