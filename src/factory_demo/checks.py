from factory_demo.catalog import DEMO_MODELS
from factory_demo.environments import ENVIRONMENTS
from factory_demo.kora_api import KoraClient
from factory_demo.registration import unpriced_models

PROBE_PROMPT = "Reply with the word ready."
CLAUDE_PROBE = "anthropic/claude-haiku-5-5"
OPENAI_PROBE = "openai/gpt-5-4"


def api_checks(client: KoraClient) -> list[tuple[bool, str]]:
    listed = {m.get("id") for m in client.list_models()}
    models = [
        (f"{m.family}/{m.name}" in listed, f"model {m.family}/{m.name} listed") for m in DEMO_MODELS
    ]
    unpriced = unpriced_models(client.list_pricing())
    prices = [(not unpriced, "every demo model has a price")]
    slugs = {e.get("slug") for e in client.list_environments()}
    environment = [(e.slug in slugs, f"environment {e.slug} present") for e in ENVIRONMENTS]
    calls = [
        (probe_claude(client, CLAUDE_PROBE)[0], f"{CLAUDE_PROBE} answers through the gateway"),
        (probe_openai(client, OPENAI_PROBE)[0], f"{OPENAI_PROBE} answers through the gateway"),
    ]
    return [*models, *prices, *environment, *calls]


def probe_claude(client: KoraClient, model_id: str) -> tuple[bool, str]:
    body = {
        "model": model_id,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
    }
    status, payload = client.post_json("/v1/messages", body)
    if status == 200 and payload.get("type") == "message":
        text = "".join(part.get("text", "") for part in payload.get("content", []))
        return True, text.strip()
    return False, _describe_failure(status, payload)


def probe_openai(client: KoraClient, model_id: str) -> tuple[bool, str]:
    body = {
        "model": model_id,
        "max_completion_tokens": 20,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
    }
    status, payload = client.post_json("/v1/chat/completions", body)
    choices = payload.get("choices") or []
    if status == 200 and choices:
        return True, (choices[0].get("message", {}).get("content") or "").strip()
    return False, _describe_failure(status, payload)


def _describe_failure(status: int, payload: dict) -> str:
    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else error
    return f"HTTP {status}: {message or payload}"
